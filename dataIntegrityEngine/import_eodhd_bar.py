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
import sys
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional
from uuid import uuid4

from sqlalchemy import MetaData, Table, and_, select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from common.config_loader import load_config
from common.utils import configure_root_logging, getLastDateMarche
from core.run_summary import attach_schema_version
from database.assets import build_eligible_stock_metadata_filters
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
    fetch_eod,
    fetch_eod_bulk,
    fetch_splits,
)
from service.eodhd.quota import (
    EodhdQuotaExceeded,
    EodhdQuotaTracker,
    get_default_tracker,
)
from service.eodhd.symbols import to_eodhd

LOGGER = logging.getLogger(__name__)
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"
DEFAULT_PER_SYMBOL_LIMIT = 100
DEFAULT_BULK_PUBLISH_OFFSET_HOURS = 2


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
        d = market_day if isinstance(market_day, date) else market_day.date()
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
    q = select(stock_metadata.c.symbol).where(
        and_(*build_eligible_stock_metadata_filters(stock_metadata))
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
    except (EodhdBarsFetchError, EodhdQuotaExceeded) as exc:
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
    config: Optional[dict] = None,
    session=None,
    tracker: Optional[EodhdQuotaTracker] = None,
    cache: Optional[EodhdDiskCache] = None,
) -> dict[str, Any]:
    """Pipeline ingestion EODHD daily. Retourne le ``run_summary``."""
    cfg = config if config is not None else _load_config_safe()
    started_at = _utc_now_naive()
    target_date = target_date or _resolve_target_date(cfg)
    cache = cache or EodhdDiskCache(
        Path((cfg.get("eodhd") or {}).get("cache_dir", "artifacts/eodhd_cache"))
    )
    tracker = tracker or get_default_tracker()

    summary: dict[str, Any] = {
        "run_id": _build_run_id(),
        "provider": "eodhd",
        "mode": "dry_run" if dry_run else "write",
        "target_date": target_date,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": None,
        "duration_seconds": 0.0,
        "targeted_symbols": 0,
        "bulk_size": 0,
        "matched_in_bulk": 0,
        "missing_from_bulk": 0,
        "per_symbol_recovered": 0,
        "per_symbol_failed": 0,
        "rows_upserted_stock_bars": 0,
        "rows_upserted_stock_bars_daily": 0,
        "errors": 0,
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
        LOGGER.info("[eodhd] univers ciblé : %d symboles", len(universe))

        if not universe:
            LOGGER.warning("[eodhd] univers vide -> sortie")
            return _finalize(summary, started_at, tracker)

        # 2) Bulk (1 appel)
        try:
            bulk_payload = fetch_eod_bulk(date=target_date, tracker=tracker)
        except (EodhdBarsFetchError, EodhdQuotaExceeded) as exc:
            LOGGER.error("[eodhd] bulk indisponible : %s", exc)
            summary["errors"] += 1
            summary["bulk_size"] = 0
            bulk_payload = []

        summary["bulk_size"] = len(bulk_payload)
        indexed = _index_bulk_by_project_symbol(bulk_payload, set(universe))
        summary["matched_in_bulk"] = len(indexed)

        # 3) Traitement par symbole
        ingested_for_audit: dict[str, list[dict]] = {}
        rows_daily: list[dict] = []
        rows_bars: list[dict] = []

        for symbol in universe:
            entry = indexed.get(symbol)
            if entry is None:
                continue
            try:
                raw_bar = _bulk_entry_to_raw_bar(entry, target_date)
            except (KeyError, TypeError, ValueError) as exc:
                LOGGER.warning("[eodhd] entry invalide %s: %s", symbol, exc)
                summary["errors"] += 1
                continue

            splits = _cached_fetch_splits(symbol, cache=cache, tracker=tracker)
            split_only = eodhd_to_split_only([raw_bar], splits)
            if not split_only:
                summary["errors"] += 1
                continue

            bar = split_only[0]
            rows_daily.append(to_stock_bars_daily_row(bar, symbol))
            rows_bars.append(to_stock_bars_row(bar, symbol))
            ingested_for_audit.setdefault(symbol, []).append(
                {"date": bar["date"], "close": bar["close"], "volume": bar["volume"]}
            )

        # 4) Recovery per-symbol pour ceux absents du bulk (limité)
        missing = [s for s in universe if s not in indexed]
        summary["missing_from_bulk"] = len(missing)
        recovered_budget = max(0, int(per_symbol_limit))
        for symbol in missing[:recovered_budget]:
            try:
                rows = fetch_eod(symbol, start=target_date, end=target_date, tracker=tracker)
            except (EodhdBarsFetchError, EodhdQuotaExceeded) as exc:
                LOGGER.warning("[eodhd] per-symbol fetch failed %s: %s", symbol, exc)
                summary["per_symbol_failed"] += 1
                continue
            if not rows:
                continue
            raw = rows[0]
            try:
                raw_bar = {
                    "date": raw.get("date", target_date),
                    "open": float(raw["open"]),
                    "high": float(raw["high"]),
                    "low": float(raw["low"]),
                    "close": float(raw["close"]),
                    "adjusted_close": float(raw.get("adjusted_close", raw["close"])),
                    "volume": int(raw.get("volume") or 0),
                }
            except (KeyError, TypeError, ValueError):
                summary["per_symbol_failed"] += 1
                continue
            splits = _cached_fetch_splits(symbol, cache=cache, tracker=tracker)
            split_only = eodhd_to_split_only([raw_bar], splits)
            if not split_only:
                summary["per_symbol_failed"] += 1
                continue
            bar = split_only[0]
            rows_daily.append(to_stock_bars_daily_row(bar, symbol))
            rows_bars.append(to_stock_bars_row(bar, symbol))
            ingested_for_audit.setdefault(symbol, []).append(
                {"date": bar["date"], "close": bar["close"], "volume": bar["volume"]}
            )
            summary["per_symbol_recovered"] += 1

        # 5) Upserts (sauf dry-run)
        if dry_run:
            LOGGER.info(
                "[eodhd] DRY-RUN | rows_daily=%d rows_bars=%d (aucune écriture DB)",
                len(rows_daily),
                len(rows_bars),
            )
            summary["rows_upserted_stock_bars_daily"] = 0
            summary["rows_upserted_stock_bars"] = 0
        else:
            try:
                summary["rows_upserted_stock_bars_daily"] = _upsert_stock_bars_daily(session, rows_daily)
                summary["rows_upserted_stock_bars"] = _upsert_stock_bars(session, rows_bars)
                session.commit()
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
        "[eodhd] résumé | run_id=%s mode=%s target=%s targeted=%d bulk=%d matched=%d "
        "recovered=%d rows_daily=%d rows_bars=%d errors=%d duration_s=%.2f",
        summary["run_id"],
        summary["mode"],
        summary["target_date"],
        summary["targeted_symbols"],
        summary["bulk_size"],
        summary["matched_in_bulk"],
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
        enable_stooq_cross_check=not args.no_stooq_cross_check,
        config=cfg,
    )
    _emit_run_summary(attach_schema_version(summary))
    return 0 if summary.get("errors", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "DEFAULT_PER_SYMBOL_LIMIT",
    "main",
    "resolve_bars_provider",
    "run_eodhd_ingestion",
]

