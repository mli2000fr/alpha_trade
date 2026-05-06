"""Orchestrateur du pipeline EODHD.

Toutes les fonctions patchées par ``tests/test_import_eodhd_bar.py`` sont
appelées via le **shim** :mod:`dataIntegrityEngine.import_eodhd_bar`
(``import dataIntegrityEngine.import_eodhd_bar as _shim``). Ainsi
``monkeypatch.setattr(import_eodhd_bar, "fetch_eod_bulk", ...)`` reste
effectif après le découpage.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from service.eodhd.adapters import (
    DATA_SOURCE_EODHD,
    eodhd_to_split_only,
    to_stock_bars_daily_row,
    to_stock_bars_row,
)
from service.eodhd.cache import EodhdDiskCache
from service.eodhd.clientEodhd import (
    EodhdBarsFetchError,
    EodhdCircuitOpen,
    EodhdSymbolNotFound,
)
from service.eodhd.quota import (
    EodhdQuotaExceeded,
    EodhdQuotaTracker,
    get_default_tracker,
)

from dataIntegrityEngine.eodhd import transforms as _transforms
from dataIntegrityEngine.eodhd.progress import (
    build_run_id,
    emit_live_progress_summary,
    should_log_symbol_progress,
    utc_now_naive,
)

LOGGER = logging.getLogger("dataIntegrityEngine.import_eodhd_bar")

DEFAULT_PER_SYMBOL_LIMIT = 100
DEFAULT_BULK_PUBLISH_OFFSET_HOURS = 2
DEFAULT_WRITE_COMMIT_EVERY_SYMBOLS = 100


def _shim():
    """Retourne le module shim (import paresseux pour éviter la circularité)."""
    from dataIntegrityEngine import import_eodhd_bar as shim_mod
    return shim_mod


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

    shim = _shim()
    inserted_daily = shim._upsert_stock_bars_daily(session, rows_daily)
    inserted_bars = shim._upsert_stock_bars(session, rows_bars)
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
    emit_live_progress_summary(summary)
    return [], []


def resolve_target_date(config: dict, today: Optional[date] = None) -> str:
    """J-1 ouvré ; tient compte du décalage de publication EODHD."""
    from common.utils import getLastDateMarche

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
    _ = offset_hours  # noqa: hint pour future utilisation
    return d.isoformat()


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
    shim = _shim()
    cfg = config if config is not None else shim._load_config_safe()
    started_at = utc_now_naive()
    target_date = target_date or resolve_target_date(cfg)
    target_date_value = date.fromisoformat(target_date)
    cache = cache or EodhdDiskCache(
        Path((cfg.get("eodhd") or {}).get("cache_dir", "artifacts/eodhd_cache"))
    )
    tracker = tracker or get_default_tracker()
    commit_every_symbols = max(int(write_commit_every_symbols or 0), 0)

    summary: dict[str, Any] = {
        "run_id": build_run_id(),
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
        "stooq_cross_check_enabled": bool(enable_stooq_cross_check),
        "eodhd": {},
        "cross_check_stooq": {"anomalies_count": 0, "failed": False, "skipped": True},
    }

    own_session = False
    if session is None:
        from database.connection import SessionLocal

        session = SessionLocal()
        own_session = True

    try:
        # 1) Univers cible
        if symbols:
            universe = [s.strip().upper() for s in symbols if s and s.strip()]
        else:
            universe = shim._get_active_tradable_symbols(session)
        summary["targeted_symbols"] = len(universe)
        summary["current_symbol_total"] = len(universe)
        LOGGER.info("[eodhd] univers ciblé : %d symboles", len(universe))
        emit_live_progress_summary(summary)

        if not universe:
            LOGGER.warning("[eodhd] univers vide -> sortie")
            return finalize(summary, started_at, tracker)

        latest_bar_dates = shim._get_latest_bar_dates(session, universe)
        summary["symbols_with_existing_history"] = len(latest_bar_dates)

        # 2) Bulk (1 appel)
        try:
            bulk_payload = shim.fetch_eod_bulk(date=target_date, tracker=tracker)
        except (EodhdBarsFetchError, EodhdQuotaExceeded, EodhdCircuitOpen) as exc:
            LOGGER.error("[eodhd] bulk indisponible : %s", exc)
            summary["errors"] += 1
            summary["bulk_size"] = 0
            bulk_payload = []
            if isinstance(exc, EodhdCircuitOpen):
                summary["stopped_reason"] = "circuit_open_on_bulk"
                return finalize(summary, started_at, tracker)

        summary["bulk_size"] = len(bulk_payload)
        indexed = _transforms.index_bulk_by_project_symbol(bulk_payload, set(universe))
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
            if should_log_symbol_progress(index, total_symbols):
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
                emit_live_progress_summary(summary)
            raw_bars: list[dict] = []
            target_date_covered_by_bulk = False

            if entry is None and _transforms.is_known_unsupported_fallback_symbol(symbol):
                LOGGER.info(
                    "[eodhd] fallback per-symbol ignoré pour symbole preferred/series non supporté: %s",
                    symbol,
                )
                summary["unsupported_fallback_symbols"] += 1
                if not dry_run:
                    shim.update_bars_available_false(symbol)
                    summary["metadata_marked_unavailable"] += 1
                continue

            if entry is not None:
                try:
                    raw_bar = _transforms.bulk_entry_to_raw_bar(entry, target_date)
                except (KeyError, TypeError, ValueError) as exc:
                    LOGGER.warning("[eodhd] entry invalide %s: %s", symbol, exc)
                    summary["errors"] += 1
                    continue
                raw_bar_date = _transforms.normalize_date(raw_bar.get("date"))
                if last_known_date is None or (raw_bar_date is not None and raw_bar_date > last_known_date):
                    raw_bars.append(raw_bar)
                    target_date_covered_by_bulk = raw_bar_date == target_date_value
                else:
                    summary["up_to_date_symbols"] += 1
            elif last_known_date is not None and last_known_date >= target_date_value:
                summary["up_to_date_symbols"] += 1

            range_start, range_end = _transforms.resolve_missing_fetch_window(
                last_known_date,
                target_date_value,
                target_date_covered_by_bulk=target_date_covered_by_bulk,
            )

            if range_start and range_end:
                try:
                    range_rows = shim.fetch_eod(symbol, start=range_start, end=range_end, tracker=tracker)
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
                    normalized_rows = _transforms.rows_to_raw_bars(range_rows)
                    if normalized_rows:
                        raw_bars = normalized_rows + raw_bars
                        summary["catchup_symbols"] += 1
                        summary["catchup_days_requested"] += (
                            date.fromisoformat(range_end) - date.fromisoformat(range_start)
                        ).days + 1
                        if entry is None:
                            summary["per_symbol_recovered"] += 1
            elif entry is None and last_known_date is None and recovered_missing_without_history < recovered_budget:
                try:
                    range_rows = shim.fetch_eod(symbol, start=target_date, end=target_date, tracker=tracker)
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
                    normalized_rows = _transforms.rows_to_raw_bars(range_rows)
                    if normalized_rows:
                        raw_bars.extend(normalized_rows)
                        summary["per_symbol_recovered"] += 1
                finally:
                    recovered_missing_without_history += 1

            if tracker.is_circuit_open():
                summary["stopped_reason"] = summary.get("stopped_reason") or "circuit_open_after_fetch"
                LOGGER.warning("[eodhd] circuit-breaker ouvert après fetch -> arrêt propre de l'ingestion")
                break

            raw_bars = _transforms.dedupe_raw_bars_by_date(raw_bars)
            if not raw_bars:
                continue

            splits = shim._cached_fetch_splits(symbol, cache=cache, tracker=tracker)
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
            emit_live_progress_summary(summary)
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
        return finalize(summary, started_at, tracker)
    finally:
        if own_session:
            session.close()


def finalize(
    summary: dict[str, Any], started_at: datetime, tracker: EodhdQuotaTracker
) -> dict[str, Any]:
    finished_at = utc_now_naive()
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


__all__ = [
    "DEFAULT_PER_SYMBOL_LIMIT",
    "DEFAULT_BULK_PUBLISH_OFFSET_HOURS",
    "DEFAULT_WRITE_COMMIT_EVERY_SYMBOLS",
    "_flush_pending_write_rows",
    "resolve_target_date",
    "run_eodhd_ingestion",
    "finalize",
]

