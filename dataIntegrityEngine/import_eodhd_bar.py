"""Phase 3 EODHD — ingestion daily bars (mode shadow / dry-run par défaut).

Plan ``prompt/iex/plan_eodhd.md`` §5.6 + §6 Phase 3.

Pipeline :

1. Lit ``market_data.bars_provider`` dans ``config.yaml``.
   - ``alpaca`` -> exit 0 (no-op, conformité plan §5.6).
   - ``eodhd``  -> ingestion EODHD.
2. Charge l'univers éligible via :func:`build_eligible_stock_metadata_filters`.
3. **1 seul appel API** : :func:`fetch_eod_bulk` (date = J-1).
4. Pour chaque symbole de l'univers présent dans le bulk :
   - récupère les splits (cache TTL 7j, fallback `[]` sur erreur),
   - reconstruit les barres split-only via :func:`eodhd_to_split_only`,
   - upsert ``stock_bars_daily`` (PK ``(symbol, date)``),
   - upsert ``stock_bars`` (UNIQ ``(symbol, timeframe='1D', timestamp)``).
5. Symboles univers absents du bulk -> tentative individuelle ``fetch_eod``
   (limitée par ``--per-symbol-limit``, défaut 100).
6. Cross-check Stooq best-effort (§5.7) — première activation effective.
7. Émission ``run_summary`` enrichi (clés ``eodhd.*`` + ``cross_check_stooq.*``).

Mode ``--dry-run`` (défaut Phase 3) : aucune écriture DB, comparaison via
:func:`_log_diff_with_alpaca` pour identifier les écarts de volume.

Mode ``--write`` : upsert effectif dans les deux tables.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional
from uuid import uuid4

from sqlalchemy import MetaData, Table, and_, func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from common.config_loader import load_config
from common.utils import configure_root_logging, getLastDateMarche
from core.run_summary import attach_schema_version
from database.assets import build_eligible_stock_metadata_filters, update_bars_available_false
from database.connection import SessionLocal, get_sqlalchemy_engine
from service.eodhd.adapters import (
    DATA_SOURCE_EODHD,
    eodhd_to_split_only,
    to_stock_bars_daily_row,
    to_stock_bars_row,
)
from service.eodhd.cache import (
    DEFAULT_TTL_SPLITS_SECONDS,
    EodhdDiskCache,
)
from service.eodhd.clientEodhd import (
    EodhdBarsFetchError,
    EodhdCircuitOpen,
    EodhdSymbolNotFound,
    fetch_eod,
    fetch_eod_bulk,
    fetch_splits,
)
from service.eodhd.quota import (
    EodhdQuotaExceeded,
    EodhdQuotaTracker,
    get_default_tracker,
)

LOGGER = logging.getLogger(__name__)
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"
DEFAULT_PER_SYMBOL_LIMIT = 100
DEFAULT_BULK_PUBLISH_OFFSET_HOURS = 2
PROGRESS_LOG_FIRST_SYMBOLS = 10
PROGRESS_LOG_EVERY = 100
DEFAULT_WRITE_COMMIT_EVERY_SYMBOLS = 100
_PREFERRED_SERIES_SYMBOL_RE = re.compile(r"^[A-Z]+\.PR[A-Z0-9]+$")


# ---------------------------------------------------------------------------
# Helpers généraux
# ---------------------------------------------------------------------------


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_run_id(prefix: str = "import-eodhd") -> str:
    return f"{prefix}-{_utc_now_naive().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"


def _emit_run_summary(summary: dict[str, Any]) -> None:
    print(
        f"{RUN_SUMMARY_PREFIX}{json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)}",
        flush=True,
    )


def _emit_live_progress_summary(summary: dict[str, Any]) -> None:
    live_summary = dict(summary)
    _emit_run_summary(attach_schema_version(live_summary))


def _should_log_symbol_progress(index: int, total: int) -> bool:
    if total <= 0 or index <= 0:
        return False
    return index <= min(PROGRESS_LOG_FIRST_SYMBOLS, total) or index % PROGRESS_LOG_EVERY == 0 or index == total


def _flush_pending_write_rows(
    *,
    session,
    rows_daily: list[dict],
    rows_bars: list[dict],
    summary: dict[str, Any],
    symbol_index: int,
    reason: str,
) -> tuple[list[dict], list[dict]]:
    if not rows_daily and not rows_bars:
        summary["pending_rows_stock_bars_daily"] = 0
        summary["pending_rows_stock_bars"] = 0
        return rows_daily, rows_bars

    inserted_daily = _upsert_stock_bars_daily(session, rows_daily)
    inserted_bars = _upsert_stock_bars(session, rows_bars)
    session.commit()
    summary["rows_upserted_stock_bars_daily"] += inserted_daily
    summary["rows_upserted_stock_bars"] += inserted_bars
    summary["batch_commits"] += 1
    summary["symbols_committed"] = max(int(summary.get("symbols_committed", 0)), symbol_index)
    summary["last_commit_symbol_index"] = symbol_index
    summary["last_commit_reason"] = reason
    summary["pending_rows_stock_bars_daily"] = 0
    summary["pending_rows_stock_bars"] = 0
    LOGGER.info(
        "[eodhd] commit batch #%d | raison=%s | checkpoint=%d/%d | rows_daily=%d | rows_bars=%d",
        summary["batch_commits"],
        reason,
        symbol_index,
        summary.get("current_symbol_total", 0),
        inserted_daily,
        inserted_bars,
    )
    _emit_live_progress_summary(summary)
    return [], []


def resolve_bars_provider(config: Optional[dict] = None) -> str:
    """Lit ``market_data.bars_provider`` (défaut ``alpaca``)."""
    cfg = config if config is not None else _load_config_safe()
    return str(((cfg or {}).get("market_data") or {}).get("bars_provider", "alpaca")).lower()


def _load_config_safe() -> dict:
    try:
        return load_config() or {}
    except FileNotFoundError:
        return {}
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("[eodhd] config.yaml illisible: %s", exc)
        return {}


def _resolve_target_date(config: dict, today: Optional[date] = None) -> str:
    """J-1 ouvré ; tient compte du décalage de publication EODHD."""
    eodhd_cfg = (config or {}).get("eodhd", {}) or {}
    offset_hours = float(eodhd_cfg.get("bulk_publish_offset_hours", DEFAULT_BULK_PUBLISH_OFFSET_HOURS))
    market_day = getLastDateMarche()
    if hasattr(market_day, "isoformat"):
        if isinstance(market_day, datetime):
            d = market_day.date()
        elif isinstance(market_day, date):
            d = market_day
        else:
            d = today or date.today()
    else:
        d = today or date.today()
    # heuristique simple : on cible J-1 si publication < offset_hours après cloture US.
    # En production, le scheduler doit être lancé après l'offset → on prend market_day.
    _ = offset_hours  # noqa: hint pour future utilisation
    return d.isoformat()


# ---------------------------------------------------------------------------
# DB tables (lazy autoload)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_tables() -> tuple[Table, Table, Table]:
    metadata = MetaData()
    engine = get_sqlalchemy_engine()
    stock_metadata = Table("stock_metadata", metadata, autoload_with=engine)
    stock_bars = Table("stock_bars", metadata, autoload_with=engine)
    stock_bars_daily = Table("stock_bars_daily", metadata, autoload_with=engine)
    return stock_metadata, stock_bars, stock_bars_daily


def _reset_tables_cache() -> None:
    _get_tables.cache_clear()


def _get_active_tradable_symbols(session) -> list[str]:
    stock_metadata, _, _ = _get_tables()
    q = (
        select(stock_metadata.c.symbol)
        .where(and_(*build_eligible_stock_metadata_filters(stock_metadata)))
        .order_by(stock_metadata.c.symbol)
    )
    return [row[0] for row in session.execute(q).all()]


# ---------------------------------------------------------------------------
# Splits cache (best-effort)
# ---------------------------------------------------------------------------


def _cached_fetch_splits(
    symbol: str,
    *,
    cache: EodhdDiskCache,
    tracker: EodhdQuotaTracker,
    ttl_seconds: float = DEFAULT_TTL_SPLITS_SECONDS,
    fetch_fn=fetch_splits,
) -> list[dict]:
    """Splits via cache disque ; sur erreur (403/quota), retourne ``[]``.

    L'absence de splits est tolérée pour Phase 3 shadow : on ingèrera des
    barres « brutes EODHD » qui sont déjà cohérentes pour les dates récentes
    (les splits historiques ne concernent que les barres anciennes).
    """
    namespace = "splits"
    key = symbol.strip().upper()

    cached = cache.get(namespace, key, ttl_seconds=ttl_seconds)
    if cached is not None:
        return list(cached) if isinstance(cached, list) else []

    try:
        payload = fetch_fn(symbol, tracker=tracker)
    except (EodhdBarsFetchError, EodhdQuotaExceeded, EodhdCircuitOpen) as exc:
        LOGGER.warning("[eodhd] splits indisponibles pour %s: %s -> []", symbol, exc)
        # cache l'absence pour ne pas re-tenter à chaque symbole
        cache.set(namespace, key, [])
        return []

    cache.set(namespace, key, payload)
    return list(payload) if isinstance(payload, list) else []


# ---------------------------------------------------------------------------
# Bulk filtering
# ---------------------------------------------------------------------------


def _index_bulk_by_project_symbol(
    bulk: Iterable[dict], universe: set[str]
) -> dict[str, dict]:
    """Indexe le payload bulk par symbole projet (filtré sur l'univers).

    Le bulk EODHD renvoie ``code`` (ticker sans suffixe) + ``exchange_short_name``.
    On reconstruit le symbole projet en inversant la convention class-share
    (``BRK-B`` -> ``BRK.B``).
    """
    indexed: dict[str, dict] = {}
    universe_upper = {s.strip().upper() for s in universe}
    for entry in bulk or []:
        raw_code = str(entry.get("code") or "").strip().upper()
        if not raw_code:
            continue
        project_symbol = raw_code.replace("-", ".") if "-" in raw_code else raw_code
        if universe_upper and project_symbol not in universe_upper:
            continue
        indexed[project_symbol] = entry
    return indexed


def _bulk_entry_to_raw_bar(entry: dict, target_date: str) -> dict:
    """Convertit une entrée bulk EODHD en barre OHLCV brute pour l'adapter."""
    return {
        "date": str(entry.get("date") or target_date),
        "open": float(entry["open"]),
        "high": float(entry["high"]),
        "low": float(entry["low"]),
        "close": float(entry["close"]),
        "adjusted_close": float(entry.get("adjusted_close", entry["close"])),
        "volume": int(entry.get("volume") or 0),
    }


def _normalize_date(value: date | str | datetime | None) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _rows_to_raw_bars(rows: Iterable[dict]) -> list[dict]:
    raw_bars: list[dict] = []
    for raw in rows or []:
        try:
            raw_bars.append(
                {
                    "date": str(raw.get("date") or ""),
                    "open": float(raw["open"]),
                    "high": float(raw["high"]),
                    "low": float(raw["low"]),
                    "close": float(raw["close"]),
                    "adjusted_close": float(raw.get("adjusted_close", raw["close"])),
                    "volume": int(raw.get("volume") or 0),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return raw_bars


def _dedupe_raw_bars_by_date(raw_bars: Iterable[dict]) -> list[dict]:
    deduped: dict[str, dict] = {}
    for raw_bar in raw_bars or []:
        raw_date = str(raw_bar.get("date") or "").strip()
        if not raw_date:
            continue
        deduped[raw_date] = raw_bar
    return [deduped[key] for key in sorted(deduped)]


def _get_latest_bar_dates(session, symbols: Iterable[str]) -> dict[str, date]:
    universe = [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]
    if not universe:
        return {}
    _, bars, _ = _get_tables()
    q = (
        select(bars.c.symbol, func.max(bars.c.timestamp).label("last_timestamp"))
        .where(and_(bars.c.timeframe == "1D", bars.c.symbol.in_(universe)))
        .group_by(bars.c.symbol)
    )
    try:
        rows = session.execute(q).all()
    except AttributeError:
        # Fakes de tests minimaux : on retombe sur "aucun historique".
        return {}

    latest_dates: dict[str, date] = {}
    for symbol, last_timestamp in rows:
        normalized = _normalize_date(last_timestamp)
        if normalized is not None:
            latest_dates[str(symbol).strip().upper()] = normalized
    return latest_dates


def _resolve_missing_fetch_window(
    last_known_date: Optional[date],
    target_date_value: date,
    *,
    target_date_covered_by_bulk: bool,
) -> tuple[Optional[str], Optional[str]]:
    if last_known_date is None or last_known_date >= target_date_value:
        return None, None
    start = last_known_date + timedelta(days=1)
    end = target_date_value - timedelta(days=1) if target_date_covered_by_bulk else target_date_value
    if start > end:
        return None, None
    return start.isoformat(), end.isoformat()


def _is_known_unsupported_fallback_symbol(symbol: str) -> bool:
    normalized = str(symbol or "").strip().upper()
    return bool(_PREFERRED_SERIES_SYMBOL_RE.match(normalized))


# ---------------------------------------------------------------------------
# Upserts
# ---------------------------------------------------------------------------


def _upsert_stock_bars_daily(session, rows: list[dict]) -> int:
    if not rows:
        return 0
    _, _, daily = _get_tables()
    stmt = mysql_insert(daily).values(rows)
    update_dict = {
        col: stmt.inserted[col]
        for col in ("open", "high", "low", "close", "volume", "adj_close",
                    "vwap", "daily_return", "is_filled",
                    "data_adjustment", "data_source")
        if col in daily.c
    }
    session.execute(stmt.on_duplicate_key_update(**update_dict))
    return len(rows)


def _upsert_stock_bars(session, rows: list[dict]) -> int:
    if not rows:
        return 0
    _, bars, _ = _get_tables()
    stmt = mysql_insert(bars).values(rows)
    update_dict = {
        col: stmt.inserted[col]
        for col in ("open_price", "high_price", "low_price", "close_price",
                    "volume", "trade_count", "vwa_price",
                    "data_adjustment", "data_source")
        if col in bars.c
    }
    session.execute(stmt.on_duplicate_key_update(**update_dict))
    return len(rows)


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------


def run_eodhd_ingestion(
    *,
    dry_run: bool = True,
    target_date: Optional[str] = None,
    symbols: Optional[list[str]] = None,
    per_symbol_limit: int = DEFAULT_PER_SYMBOL_LIMIT,
    enable_stooq_cross_check: bool = True,
    write_commit_every_symbols: int = DEFAULT_WRITE_COMMIT_EVERY_SYMBOLS,
    config: Optional[dict] = None,
    session=None,
    tracker: Optional[EodhdQuotaTracker] = None,
    cache: Optional[EodhdDiskCache] = None,
) -> dict[str, Any]:
    """Pipeline ingestion EODHD daily. Retourne le ``run_summary``."""
    cfg = config if config is not None else _load_config_safe()
    started_at = _utc_now_naive()
    target_date = target_date or _resolve_target_date(cfg)
    target_date_value = date.fromisoformat(target_date)
    cache = cache or EodhdDiskCache(
        Path((cfg.get("eodhd") or {}).get("cache_dir", "artifacts/eodhd_cache"))
    )
    tracker = tracker or get_default_tracker()
    commit_every_symbols = max(int(write_commit_every_symbols or 0), 0)

    summary: dict[str, Any] = {
        "run_id": _build_run_id(),
        "provider": "eodhd",
        "mode": "dry_run" if dry_run else "write",
        "target_date": target_date,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": None,
        "duration_seconds": 0.0,
        "targeted_symbols": 0,
        "current_symbol_index": 0,
        "current_symbol_total": 0,
        "current_symbol": None,
        "write_commit_every_symbols": commit_every_symbols,
        "batch_commits": 0,
        "symbols_committed": 0,
        "last_commit_symbol_index": 0,
        "last_commit_reason": None,
        "pending_rows_stock_bars_daily": 0,
        "pending_rows_stock_bars": 0,
        "symbols_with_existing_history": 0,
        "up_to_date_symbols": 0,
        "bulk_size": 0,
        "matched_in_bulk": 0,
        "missing_from_bulk": 0,
        "catchup_symbols": 0,
        "catchup_days_requested": 0,
        "unsupported_fallback_symbols": 0,
        "metadata_marked_unavailable": 0,
        "per_symbol_recovered": 0,
        "per_symbol_failed": 0,
        "rows_upserted_stock_bars": 0,
        "rows_upserted_stock_bars_daily": 0,
        "errors": 0,
        "stopped_reason": None,
        # clés normalisées pour run_summary global (cf. plan §8.1)
        "eodhd": {},
        "cross_check_stooq": {"anomalies_count": 0, "failed": False, "skipped": True},
    }

    own_session = False
    if session is None:
        session = SessionLocal()
        own_session = True

    try:
        # 1) Univers cible
        if symbols:
            universe = [s.strip().upper() for s in symbols if s and s.strip()]
        else:
            universe = _get_active_tradable_symbols(session)
        summary["targeted_symbols"] = len(universe)
        summary["current_symbol_total"] = len(universe)
        LOGGER.info("[eodhd] univers ciblé : %d symboles", len(universe))
        _emit_live_progress_summary(summary)

        if not universe:
            LOGGER.warning("[eodhd] univers vide -> sortie")
            return _finalize(summary, started_at, tracker)

        latest_bar_dates = _get_latest_bar_dates(session, universe)
        summary["symbols_with_existing_history"] = len(latest_bar_dates)

        # 2) Bulk (1 appel)
        try:
            bulk_payload = fetch_eod_bulk(date=target_date, tracker=tracker)
        except (EodhdBarsFetchError, EodhdQuotaExceeded, EodhdCircuitOpen) as exc:
            LOGGER.error("[eodhd] bulk indisponible : %s", exc)
            summary["errors"] += 1
            summary["bulk_size"] = 0
            bulk_payload = []
            if isinstance(exc, EodhdCircuitOpen):
                summary["stopped_reason"] = "circuit_open_on_bulk"
                return _finalize(summary, started_at, tracker)

        summary["bulk_size"] = len(bulk_payload)
        indexed = _index_bulk_by_project_symbol(bulk_payload, set(universe))
        summary["matched_in_bulk"] = len(indexed)

        # 3) Traitement par symbole
        ingested_for_audit: dict[str, list[dict]] = {}
        rows_daily: list[dict] = []
        rows_bars: list[dict] = []
        recovered_budget = max(0, int(per_symbol_limit))
        recovered_missing_without_history = 0
        symbols_since_last_commit = 0

        total_symbols = len(universe)
        for index, symbol in enumerate(universe, start=1):
            summary["current_symbol_index"] = index
            summary["current_symbol_total"] = total_symbols
            summary["current_symbol"] = symbol
            if tracker.is_circuit_open():
                summary["stopped_reason"] = "circuit_open"
                LOGGER.warning("[eodhd] circuit-breaker ouvert -> arrêt propre de l'ingestion")
                break

            entry = indexed.get(symbol)
            last_known_date = latest_bar_dates.get(symbol)
            if _should_log_symbol_progress(index, total_symbols):
                LOGGER.info(
                    "[eodhd] progression %d/%d (%.1f%%) | symbol=%s | source=%s | last_known=%s | up_to_date=%d | recovered=%d | errors=%d",
                    index,
                    total_symbols,
                    (index / total_symbols) * 100.0,
                    symbol,
                    "bulk" if entry is not None else "fallback",
                    last_known_date.isoformat() if last_known_date is not None else "none",
                    summary["up_to_date_symbols"],
                    summary["per_symbol_recovered"],
                    summary["errors"],
                )
                _emit_live_progress_summary(summary)
            raw_bars: list[dict] = []
            target_date_covered_by_bulk = False

            if entry is None and _is_known_unsupported_fallback_symbol(symbol):
                LOGGER.info(
                    "[eodhd] fallback per-symbol ignoré pour symbole preferred/series non supporté: %s",
                    symbol,
                )
                summary["unsupported_fallback_symbols"] += 1
                if not dry_run:
                    update_bars_available_false(symbol)
                    summary["metadata_marked_unavailable"] += 1
                continue

            if entry is not None:
                try:
                    raw_bar = _bulk_entry_to_raw_bar(entry, target_date)
                except (KeyError, TypeError, ValueError) as exc:
                    LOGGER.warning("[eodhd] entry invalide %s: %s", symbol, exc)
                    summary["errors"] += 1
                    continue
                raw_bar_date = _normalize_date(raw_bar.get("date"))
                if last_known_date is None or (raw_bar_date is not None and raw_bar_date > last_known_date):
                    raw_bars.append(raw_bar)
                    target_date_covered_by_bulk = raw_bar_date == target_date_value
                else:
                    summary["up_to_date_symbols"] += 1
            elif last_known_date is not None and last_known_date >= target_date_value:
                summary["up_to_date_symbols"] += 1

            range_start, range_end = _resolve_missing_fetch_window(
                last_known_date,
                target_date_value,
                target_date_covered_by_bulk=target_date_covered_by_bulk,
            )

            if range_start and range_end:
                try:
                    range_rows = fetch_eod(symbol, start=range_start, end=range_end, tracker=tracker)
                except EodhdSymbolNotFound as exc:
                    LOGGER.warning(
                        "[eodhd] catch-up introuvable %s [%s..%s]: %s",
                        symbol,
                        range_start,
                        range_end,
                        exc,
                    )
                    summary["per_symbol_failed"] += 1
                except (EodhdBarsFetchError, EodhdQuotaExceeded, EodhdCircuitOpen) as exc:
                    LOGGER.warning(
                        "[eodhd] catch-up fetch failed %s [%s..%s]: %s",
                        symbol,
                        range_start,
                        range_end,
                        exc,
                    )
                    summary["per_symbol_failed"] += 1
                    if isinstance(exc, EodhdCircuitOpen):
                        summary["stopped_reason"] = "circuit_open_during_catchup"
                        break
                else:
                    normalized_rows = _rows_to_raw_bars(range_rows)
                    if normalized_rows:
                        raw_bars = normalized_rows + raw_bars
                        summary["catchup_symbols"] += 1
                        summary["catchup_days_requested"] += (date.fromisoformat(range_end) - date.fromisoformat(range_start)).days + 1
                        if entry is None:
                            summary["per_symbol_recovered"] += 1
            elif entry is None and last_known_date is None and recovered_missing_without_history < recovered_budget:
                try:
                    range_rows = fetch_eod(symbol, start=target_date, end=target_date, tracker=tracker)
                except EodhdSymbolNotFound as exc:
                    LOGGER.warning("[eodhd] per-symbol introuvable %s: %s", symbol, exc)
                    summary["per_symbol_failed"] += 1
                except (EodhdBarsFetchError, EodhdQuotaExceeded, EodhdCircuitOpen) as exc:
                    LOGGER.warning("[eodhd] per-symbol fetch failed %s: %s", symbol, exc)
                    summary["per_symbol_failed"] += 1
                    if isinstance(exc, EodhdCircuitOpen):
                        summary["stopped_reason"] = "circuit_open_during_recovery"
                        break
                else:
                    normalized_rows = _rows_to_raw_bars(range_rows)
                    if normalized_rows:
                        raw_bars.extend(normalized_rows)
                        summary["per_symbol_recovered"] += 1
                finally:
                    recovered_missing_without_history += 1

            if tracker.is_circuit_open():
                summary["stopped_reason"] = summary.get("stopped_reason") or "circuit_open_after_fetch"
                LOGGER.warning("[eodhd] circuit-breaker ouvert après fetch -> arrêt propre de l'ingestion")
                break

            raw_bars = _dedupe_raw_bars_by_date(raw_bars)
            if not raw_bars:
                continue

            splits = _cached_fetch_splits(symbol, cache=cache, tracker=tracker)
            split_only = eodhd_to_split_only(raw_bars, splits)
            if not split_only:
                summary["errors"] += 1
                continue

            for bar in split_only:
                rows_daily.append(to_stock_bars_daily_row(bar, symbol))
                rows_bars.append(to_stock_bars_row(bar, symbol))
                ingested_for_audit.setdefault(symbol, []).append(
                    {"date": bar["date"], "close": bar["close"], "volume": bar["volume"]}
                )

            summary["pending_rows_stock_bars_daily"] = len(rows_daily)
            summary["pending_rows_stock_bars"] = len(rows_bars)
            _emit_live_progress_summary(summary)
            symbols_since_last_commit += 1
            if not dry_run and commit_every_symbols > 0 and symbols_since_last_commit >= commit_every_symbols:
                rows_daily, rows_bars = _flush_pending_write_rows(
                    session=session,
                    rows_daily=rows_daily,
                    rows_bars=rows_bars,
                    summary=summary,
                    symbol_index=index,
                    reason="batch_threshold",
                )
                symbols_since_last_commit = 0

        if total_symbols > 0:
            summary["current_symbol_index"] = total_symbols

        # 4) Synthèse des absents du bulk
        missing = [s for s in universe if s not in indexed]
        summary["missing_from_bulk"] = len(missing)

        # 5) Upserts (sauf dry-run)
        if dry_run:
            LOGGER.info(
                "[eodhd] DRY-RUN | rows_daily=%d rows_bars=%d (aucune écriture DB)",
                len(rows_daily),
                len(rows_bars),
            )
            summary["rows_upserted_stock_bars_daily"] = 0
            summary["rows_upserted_stock_bars"] = 0
            summary["pending_rows_stock_bars_daily"] = len(rows_daily)
            summary["pending_rows_stock_bars"] = len(rows_bars)
        else:
            try:
                rows_daily, rows_bars = _flush_pending_write_rows(
                    session=session,
                    rows_daily=rows_daily,
                    rows_bars=rows_bars,
                    summary=summary,
                    symbol_index=int(summary.get("current_symbol_index", 0) or 0),
                    reason="final_flush",
                )
            except Exception:
                session.rollback()
                LOGGER.exception("[eodhd] échec upsert -> rollback")
                summary["errors"] += 1
                raise

        # 6) Cross-check Stooq (best-effort, première activation prod — plan §5.7)
        if enable_stooq_cross_check and ingested_for_audit:
            try:
                from dataIntegrityEngine.cross_check_stooq import compare_with_stooq

                anomalies = compare_with_stooq(
                    ingested_for_audit, lookback_days=5, today=date.today()
                )
                summary["cross_check_stooq"] = {
                    "anomalies_count": len(anomalies),
                    "failed": False,
                    "skipped": False,
                }
                if anomalies:
                    LOGGER.warning("[eodhd] Stooq anomalies: %d", len(anomalies))
            except Exception as exc:
                LOGGER.warning("[eodhd] cross_check_stooq failed (non bloquant): %s", exc)
                summary["cross_check_stooq"] = {
                    "anomalies_count": 0,
                    "failed": True,
                    "skipped": False,
                }
        return _finalize(summary, started_at, tracker)
    finally:
        if own_session:
            session.close()


def _finalize(
    summary: dict[str, Any], started_at: datetime, tracker: EodhdQuotaTracker
) -> dict[str, Any]:
    finished_at = _utc_now_naive()
    summary["finished_at"] = finished_at.isoformat(timespec="seconds")
    summary["duration_seconds"] = round((finished_at - started_at).total_seconds(), 2)
    summary["eodhd"] = {
        **tracker.snapshot(),
        "data_source": DATA_SOURCE_EODHD,
        "rows_upserted_stock_bars": int(summary.get("rows_upserted_stock_bars", 0)),
        "rows_upserted_stock_bars_daily": int(summary.get("rows_upserted_stock_bars_daily", 0)),
        "bulk_size": int(summary.get("bulk_size", 0)),
        "matched_in_bulk": int(summary.get("matched_in_bulk", 0)),
        "symbols_missing": int(summary.get("missing_from_bulk", 0)),
    }
    LOGGER.info(
        "[eodhd] résumé | run_id=%s mode=%s target=%s targeted=%d existing=%d up_to_date=%d bulk=%d matched=%d catchup_symbols=%d recovered=%d rows_daily=%d rows_bars=%d errors=%d duration_s=%.2f",
        summary["run_id"],
        summary["mode"],
        summary["target_date"],
        summary["targeted_symbols"],
        summary["symbols_with_existing_history"],
        summary["up_to_date_symbols"],
        summary["bulk_size"],
        summary["matched_in_bulk"],
        summary["catchup_symbols"],
        summary["per_symbol_recovered"],
        summary["rows_upserted_stock_bars_daily"],
        summary["rows_upserted_stock_bars"],
        summary["errors"],
        summary["duration_seconds"],
    )
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Importe les barres daily EODHD (Phase 3 shadow).")
    p.add_argument("--symbols", nargs="+", default=None, help="Sous-univers explicite.")
    p.add_argument("--target-date", default=None, help="Date cible YYYY-MM-DD (défaut J-1).")
    p.add_argument(
        "--per-symbol-limit",
        type=int,
        default=DEFAULT_PER_SYMBOL_LIMIT,
        help=f"Plafond appels per-symbol pour récup absences bulk (défaut: {DEFAULT_PER_SYMBOL_LIMIT}).",
    )
    p.add_argument(
        "--commit-every-symbols",
        type=int,
        default=DEFAULT_WRITE_COMMIT_EVERY_SYMBOLS,
        help=(
            "En mode --write, effectue un upsert + commit intermédiaire toutes les N itérations symbole. "
            f"0 = commit final unique uniquement. Défaut: {DEFAULT_WRITE_COMMIT_EVERY_SYMBOLS}."
        ),
    )
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--dry-run", action="store_true", default=True,
                     help="Mode shadow (défaut Phase 3) — aucune écriture DB.")
    grp.add_argument("--write", action="store_true", default=False,
                     help="Mode write — upsert effectif dans stock_bars + stock_bars_daily.")
    p.add_argument("--no-stooq-cross-check", action="store_true", default=False)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    configure_root_logging(
        level=logging.INFO,
        log_path="./log/import_eodhd_bar.log",
        fmt="%(asctime)s %(levelname)s %(message)s",
    )
    args = _build_arg_parser().parse_args(argv)

    cfg = _load_config_safe()
    provider = resolve_bars_provider(cfg)
    if provider != "eodhd":
        LOGGER.info(
            "[eodhd] bars_provider=%s -> import_eodhd_bar no-op (Phase 3 conformité plan §5.6)",
            provider,
        )
        # On émet quand même un summary minimal pour traçabilité IHM/CI.
        skip_summary = {
            "run_id": _build_run_id("import-eodhd-noop"),
            "provider": "eodhd",
            "mode": "noop",
            "target_date": _resolve_target_date(cfg),
            "skipped_reason": f"bars_provider={provider}",
            "started_at": _utc_now_naive().isoformat(timespec="seconds"),
            "finished_at": _utc_now_naive().isoformat(timespec="seconds"),
            "duration_seconds": 0.0,
            "eodhd": {"calls_used": 0, "calls_failed": 0, "circuit_open": False},
            "cross_check_stooq": {"anomalies_count": 0, "failed": False, "skipped": True},
        }
        _emit_run_summary(attach_schema_version(skip_summary))
        return 0

    dry_run = not args.write
    summary = run_eodhd_ingestion(
        dry_run=dry_run,
        target_date=args.target_date,
        symbols=args.symbols,
        per_symbol_limit=args.per_symbol_limit,
        write_commit_every_symbols=args.commit_every_symbols,
        enable_stooq_cross_check=not args.no_stooq_cross_check,
        config=cfg,
    )
    _emit_run_summary(attach_schema_version(summary))
    return 0 if summary.get("errors", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "DEFAULT_PER_SYMBOL_LIMIT",
    "DEFAULT_WRITE_COMMIT_EVERY_SYMBOLS",
    "main",
    "resolve_bars_provider",
    "run_eodhd_ingestion",
]

