from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import requests

from common.utils import configure_root_logging
from database.cleaning_audits import record_earnings_audit_run
from database.selector_reference import list_active_tradable_symbols, upsert_earnings_calendar
from service.finnhub.clientFinnhub import MIN_REQUEST_INTERVAL_SECONDS, fetch_multiple_symbols_earnings_calendar

LOGGER = logging.getLogger(__name__)
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_run_id(prefix: str) -> str:
    return f"{prefix}-{_utc_now_naive().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"


def _emit_run_summary(summary: dict[str, object]) -> None:
    print(
        f"{RUN_SUMMARY_PREFIX}{json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)}",
        flush=True,
    )


def sync_earnings_calendar(
    *,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int | None = None,
    sleep_seconds: float = MIN_REQUEST_INTERVAL_SECONDS,
) -> dict[str, int]:
    if sleep_seconds < 0:
        raise ValueError("sleep_seconds doit être supérieur ou égal à 0.")

    start = from_date or date.today() - timedelta(days=7)
    end = to_date or date.today() + timedelta(days=30)
    symbols = list_active_tradable_symbols(limit=limit)
    summary = {"symbols": len(symbols), "rows_upserted": 0}
    if not symbols:
        return summary

    session = requests.Session()
    try:
        rows = fetch_multiple_symbols_earnings_calendar(
            symbols,
            from_date=start.isoformat(),
            to_date=end.isoformat(),
            sleep_seconds=sleep_seconds,
            session=session,
        )
    finally:
        session.close()

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

    summary["rows_upserted"] = upsert_earnings_calendar(normalized_rows)
    LOGGER.info(
        "Sync earnings calendar | symbols=%s rows_upserted=%s from=%s to=%s",
        len(symbols),
        summary["rows_upserted"],
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
    summary: dict[str, int]
    try:
        summary = sync_earnings_calendar(
            from_date=date.fromisoformat(args.from_date) if args.from_date else None,
            to_date=date.fromisoformat(args.to_date) if args.to_date else None,
            limit=args.limit,
            sleep_seconds=args.sleep_seconds,
        )
    except Exception as exc:  # noqa: BLE001
        status = "failed"
        error_message = repr(exc)
        summary = {"symbols": 0, "rows_upserted": 0}
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
            "audit_status": status,
            **summary,
        }
    )


if __name__ == "__main__":
    main()

