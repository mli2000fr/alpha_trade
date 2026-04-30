from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests

from common.utils import configure_root_logging
from database.cleaning_audits import record_earnings_audit_run
from database.selector_reference import list_active_tradable_symbols, upsert_earnings_calendar
from service.finnhub.clientFinnhub import MIN_REQUEST_INTERVAL_SECONDS, fetch_earnings_calendar

LOGGER = logging.getLogger(__name__)
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIN_BATCH_SIZE = 25
MAX_BATCH_SIZE = 100
DEFAULT_BATCH_SIZE = 50
DEFAULT_RESUME = True
DEFAULT_BOOKMARK_PATH = PROJECT_ROOT / "artifacts" / "finnhub_cache" / "sync_earnings_calendar_bookmark.json"


class SyncEarningsCalendarError(RuntimeError):
    def __init__(self, message: str, *, summary: dict[str, object]) -> None:
        super().__init__(message)
        self.summary = dict(summary)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_run_id(prefix: str) -> str:
    return f"{prefix}-{_utc_now_naive().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"


def _emit_run_summary(summary: dict[str, object]) -> None:
    print(
        f"{RUN_SUMMARY_PREFIX}{json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)}",
        flush=True,
    )


def _coerce_bookmark_path(path: str | Path | None) -> Path:
    return Path(path) if path is not None else DEFAULT_BOOKMARK_PATH


def _default_bookmark_state(*, context: dict[str, object]) -> dict[str, Any]:
    return {
        "completed_symbols": [],
        "started_at": None,
        "last_updated_at": None,
        "context": context,
    }


def load_bookmark(path: str | Path | None = None) -> dict[str, Any]:
    resolved = _coerce_bookmark_path(path)
    if not resolved.exists():
        return _default_bookmark_state(context={})
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - bookmark best-effort.
        LOGGER.warning("Sync earnings calendar | bookmark illisible (%s) -> reset", exc)
        return _default_bookmark_state(context={})
    if not isinstance(payload, dict):
        LOGGER.warning("Sync earnings calendar | bookmark invalide (payload non-dict) -> reset")
        return _default_bookmark_state(context={})
    payload.setdefault("completed_symbols", [])
    payload.setdefault("started_at", None)
    payload.setdefault("last_updated_at", None)
    payload.setdefault("context", {})
    return payload


def save_bookmark(path: str | Path | None, state: dict[str, Any]) -> None:
    resolved = _coerce_bookmark_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(state, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def clear_bookmark(path: str | Path | None = None) -> None:
    resolved = _coerce_bookmark_path(path)
    if resolved.exists():
        resolved.unlink()


def _normalize_bookmark_symbols(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return sorted({str(symbol).strip().upper() for symbol in values if str(symbol).strip()})


def _build_bookmark_context(*, start: date, end: date, limit: int | None) -> dict[str, object]:
    return {
        "from_date": start.isoformat(),
        "to_date": end.isoformat(),
        "limit": limit,
    }


def _resolve_bookmark_state(
    path: Path,
    *,
    resume: bool,
    context: dict[str, object],
) -> tuple[dict[str, Any], set[str]]:
    if not resume:
        if path.exists():
            LOGGER.info("Sync earnings calendar | bookmark ignore car --no-resume actif | path=%s", path)
        return _default_bookmark_state(context=context), set()

    state = load_bookmark(path)
    previous_context = state.get("context")
    if previous_context != context:
        if _normalize_bookmark_symbols(state.get("completed_symbols")):
            LOGGER.info(
                "Sync earnings calendar | bookmark reset (contexte différent) | path=%s previous=%s current=%s",
                path,
                previous_context,
                context,
            )
        return _default_bookmark_state(context=context), set()

    completed_symbols = set(_normalize_bookmark_symbols(state.get("completed_symbols")))
    state["completed_symbols"] = sorted(completed_symbols)
    state["context"] = context
    return state, completed_symbols


def _normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, object]]:
    normalized_rows: list[dict[str, object]] = []
    for row in rows:
        earnings_date = row.get("date") or row.get("earningsDate")
        if not earnings_date:
            continue
        normalized_rows.append(
            {
                "symbol": str(row.get("symbol") or "").strip().upper(),
                "earnings_date": earnings_date,
                "eps_estimate": row.get("epsEstimate"),
                "eps_actual": row.get("epsActual"),
                "revenue_estimate": row.get("revenueEstimate"),
                "revenue_actual": row.get("revenueActual"),
                "fiscal_period": row.get("quarter") or row.get("fiscalPeriod"),
            }
        )
    return normalized_rows


def _validate_batch_size(batch_size: int) -> None:
    if batch_size < MIN_BATCH_SIZE or batch_size > MAX_BATCH_SIZE:
        raise ValueError(
            f"batch_size doit être compris entre {MIN_BATCH_SIZE} et {MAX_BATCH_SIZE} symboles."
        )


def sync_earnings_calendar(
    *,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int | None = None,
    sleep_seconds: float = MIN_REQUEST_INTERVAL_SECONDS,
    log_every: int = 25,
    batch_size: int = DEFAULT_BATCH_SIZE,
    resume: bool = DEFAULT_RESUME,
    bookmark_path: str | Path | None = None,
) -> dict[str, object]:
    if sleep_seconds < 0:
        raise ValueError("sleep_seconds doit être supérieur ou égal à 0.")
    _validate_batch_size(batch_size)

    start = from_date or date.today() - timedelta(days=7)
    end = to_date or date.today() + timedelta(days=30)
    symbols = list_active_tradable_symbols(limit=limit)
    resolved_bookmark_path = _coerce_bookmark_path(bookmark_path)
    bookmark_context = _build_bookmark_context(start=start, end=end, limit=limit)
    bookmark_state, completed_symbols = _resolve_bookmark_state(
        resolved_bookmark_path,
        resume=resume,
        context=bookmark_context,
    )
    pending_symbols = [symbol for symbol in symbols if symbol not in completed_symbols]
    summary: dict[str, object] = {
        "symbols": len(symbols),
        "symbols_pending": len(pending_symbols),
        "symbols_skipped_resume": len(symbols) - len(pending_symbols),
        "completed_symbols": 0,
        "failed_symbols": 0,
        "symbols_remaining": len(pending_symbols),
        "rows_upserted": 0,
        "batches_processed": 0,
        "batch_size": batch_size,
        "resume_enabled": bool(resume),
        "bookmark_path": str(resolved_bookmark_path),
    }
    LOGGER.info(
        "Sync earnings calendar start | symbols=%s pending=%s skipped_resume=%s from=%s to=%s limit=%s sleep_seconds=%s log_every=%s batch_size=%s resume=%s bookmark=%s",
        len(symbols),
        len(pending_symbols),
        len(symbols) - len(pending_symbols),
        start,
        end,
        limit,
        sleep_seconds,
        log_every,
        batch_size,
        resume,
        resolved_bookmark_path,
    )
    if not symbols:
        LOGGER.warning("Sync earnings calendar skipped | aucun symbole actif/tradable trouvé.")
        return summary
    if not pending_symbols:
        LOGGER.info("Sync earnings calendar skipped | aucun symbole restant après reprise | bookmark=%s", resolved_bookmark_path)
        clear_bookmark(resolved_bookmark_path)
        summary["symbols_remaining"] = 0
        return summary

    session = requests.Session()
    try:
        total_pending = len(pending_symbols)
        total_batches = (total_pending + batch_size - 1) // batch_size
        for batch_index, batch_start in enumerate(range(0, total_pending, batch_size), start=1):
            batch_symbols = pending_symbols[batch_start:batch_start + batch_size]
            batch_rows: list[dict[str, object]] = []
            batch_successful_symbols: list[str] = []
            batch_failed_symbols: list[str] = []
            batch_raw_rows = 0

            for symbol_offset, symbol in enumerate(batch_symbols, start=1):
                global_index = batch_start + symbol_offset
                try:
                    fetched_rows = fetch_earnings_calendar(
                        symbol,
                        from_date=start.isoformat(),
                        to_date=end.isoformat(),
                        session=session,
                    )
                    batch_raw_rows += len(fetched_rows)
                    batch_rows.extend(_normalize_rows(fetched_rows))
                    batch_successful_symbols.append(symbol)
                except Exception:
                    batch_failed_symbols.append(symbol)
                    LOGGER.exception(
                        "Erreur Finnhub earnings calendar | symbol=%s progress=%s/%s batch=%s/%s",
                        symbol,
                        global_index,
                        total_pending,
                        batch_index,
                        total_batches,
                    )
                if log_every > 0 and (global_index == 1 or global_index % log_every == 0 or global_index == total_pending):
                    LOGGER.info(
                        "Finnhub earnings calendar progress | processed=%s/%s records=%s completed=%s failed=%s latest_symbol=%s",
                        global_index,
                        total_pending,
                        batch_raw_rows + int(summary["rows_upserted"]),
                        int(summary["completed_symbols"]) + len(batch_successful_symbols),
                        int(summary["failed_symbols"]) + len(batch_failed_symbols),
                        symbol,
                    )
                if global_index < total_pending:
                    time.sleep(sleep_seconds)

            LOGGER.info(
                "Sync earnings calendar fetched | batch=%s/%s symbols=%s raw_rows=%s failed_symbols=%s",
                batch_index,
                total_batches,
                len(batch_symbols),
                batch_raw_rows,
                len(batch_failed_symbols),
            )
            LOGGER.info(
                "Sync earnings calendar normalized | batch=%s/%s normalized_rows=%s",
                batch_index,
                total_batches,
                len(batch_rows),
            )
            batch_upserted = upsert_earnings_calendar(batch_rows)
            summary["rows_upserted"] = int(summary["rows_upserted"]) + batch_upserted
            summary["completed_symbols"] = int(summary["completed_symbols"]) + len(batch_successful_symbols)
            summary["failed_symbols"] = int(summary["failed_symbols"]) + len(batch_failed_symbols)
            summary["batches_processed"] = int(summary["batches_processed"]) + 1
            summary["symbols_remaining"] = total_pending - int(summary["completed_symbols"])

            if batch_successful_symbols:
                completed_symbols.update(batch_successful_symbols)
                bookmark_state["completed_symbols"] = sorted(completed_symbols)
                bookmark_state["started_at"] = bookmark_state.get("started_at") or _utc_now_naive().isoformat(timespec="seconds")
                bookmark_state["last_updated_at"] = _utc_now_naive().isoformat(timespec="seconds")
                bookmark_state["context"] = bookmark_context
                save_bookmark(resolved_bookmark_path, bookmark_state)

            LOGGER.info(
                "Sync earnings calendar batch committed | batch=%s/%s successful_symbols=%s failed_symbols=%s rows_upserted=%s total_rows_upserted=%s bookmark=%s",
                batch_index,
                total_batches,
                len(batch_successful_symbols),
                len(batch_failed_symbols),
                batch_upserted,
                summary["rows_upserted"],
                resolved_bookmark_path,
            )
    except Exception as exc:
        raise SyncEarningsCalendarError(repr(exc), summary=summary) from exc
    finally:
        session.close()

    if int(summary["failed_symbols"]) == 0:
        clear_bookmark(resolved_bookmark_path)
        summary["symbols_remaining"] = 0
        LOGGER.info("Sync earnings calendar completed | bookmark cleared | path=%s", resolved_bookmark_path)
    else:
        LOGGER.warning(
            "Sync earnings calendar partial | failed_symbols=%s remaining=%s bookmark_retained=%s",
            summary["failed_symbols"],
            summary["symbols_remaining"],
            resolved_bookmark_path,
        )

    LOGGER.info(
        "Sync earnings calendar | symbols=%s pending=%s completed=%s failed=%s rows_upserted=%s batches_processed=%s from=%s to=%s",
        len(symbols),
        len(pending_symbols),
        summary["completed_symbols"],
        summary["failed_symbols"],
        summary["rows_upserted"],
        summary["batches_processed"],
        start,
        end,
    )
    return summary


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Synchronise le calendrier earnings Finnhub dans stock_earnings_calendar")
    parser.add_argument("--from-date", type=str, default=None, help="Date de début ISO (YYYY-MM-DD)")
    parser.add_argument("--to-date", type=str, default=None, help="Date de fin ISO (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=None, help="Nombre maximum de symboles")
    parser.add_argument("--sleep-seconds", type=float, default=MIN_REQUEST_INTERVAL_SECONDS, help="Pause entre deux appels Finnhub")
    parser.add_argument("--log-every", type=int, default=25, help="Journalise la progression tous les N symboles (0 pour désactiver)")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Nombre de symboles traités puis commités par batch ({MIN_BATCH_SIZE}-{MAX_BATCH_SIZE}).",
    )
    parser.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_RESUME,
        help="Reprend depuis le bookmark local des symboles déjà traités (`--no-resume` pour forcer un rerun complet).",
    )
    return parser


def main() -> None:
    configure_root_logging(
        level=logging.INFO,
        log_path="./log/sync_earnings_calendar.log",
        fmt="%(asctime)s %(levelname)s %(message)s",
    )
    args = _build_arg_parser().parse_args()
    started_at = _utc_now_naive()
    run_id = _build_run_id("sync-earnings")
    status: str = "success"
    error_message: str | None = None
    summary: dict[str, object] = {
        "symbols": 0,
        "rows_upserted": 0,
        "failed_symbols": 0,
        "batches_processed": 0,
        "batch_size": args.batch_size,
        "resume_enabled": bool(args.resume),
    }
    try:
        summary = sync_earnings_calendar(
            from_date=date.fromisoformat(args.from_date) if args.from_date else None,
            to_date=date.fromisoformat(args.to_date) if args.to_date else None,
            limit=args.limit,
            sleep_seconds=args.sleep_seconds,
            log_every=args.log_every,
            batch_size=args.batch_size,
            resume=bool(args.resume),
        )
    except SyncEarningsCalendarError as exc:
        status = "failed"
        error_message = repr(exc.__cause__ or exc)
        summary = dict(exc.summary)
    except Exception as exc:  # noqa: BLE001
        status = "failed"
        error_message = repr(exc)
        finished_at = _utc_now_naive()
        # Phase 3.1.d — audit dédié earnings.
        record_earnings_audit_run(
            run_id=run_id,
            started_at=started_at,
            finished_at=finished_at,
            symbols_requested=int(summary.get("symbols", 0)),
            rows_upserted=int(summary.get("rows_upserted", 0)),
            status="failed",
            error_message=error_message,
        )
        raise
    if status == "success" and int(summary.get("failed_symbols", 0) or 0) > 0:
        status = "partial"
    finished_at = _utc_now_naive()
    # Phase 3.1.d — audit dédié earnings (best-effort).
    record_earnings_audit_run(
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        symbols_requested=int(summary.get("symbols", 0)),
        rows_upserted=int(summary.get("rows_upserted", 0)),
        status="success",
        error_message=None,
    )
    _emit_run_summary(
        {
            "run_id": run_id,
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": finished_at.isoformat(timespec="seconds"),
            "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
            "from_date": args.from_date,
            "to_date": args.to_date,
            "requested_limit": args.limit,
            "sleep_seconds": args.sleep_seconds,
            "log_every": args.log_every,
            "batch_size": args.batch_size,
            "resume": bool(args.resume),
            "audit_status": status,
            **summary,
        }
    )


if __name__ == "__main__":
    main()

