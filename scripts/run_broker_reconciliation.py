"""Sprint S12.3 — CLI nightly de réconciliation broker statements.

Usage::

    python scripts/run_broker_reconciliation.py --account default --date 2026-05-05
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

LOGGER = logging.getLogger("scripts.run_broker_reconciliation")


def _parse_date(s: str | None) -> date:
    if not s:
        return (datetime.utcnow() - timedelta(days=1)).date()
    return datetime.strptime(s, "%Y-%m-%d").date()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Nightly Alpaca account-activities reconciliation.")
    p.add_argument("--account", default="default")
    p.add_argument("--date", default=None, help="YYYY-MM-DD (défaut : J-1).")
    p.add_argument("--broker-mode", choices=("paper", "live"), default="paper")
    p.add_argument("--no-fetch", action="store_true",
                   help="Skip fetch (réconcilie uniquement ce qui est déjà persisté).")
    p.add_argument("--report-out", type=Path, default=None)
    args = p.parse_args(argv)

    trade_date = _parse_date(args.date)

    try:
        from database.audit_chain import AuditChainRepository
        from database.connection import get_sqlalchemy_engine
        from service.alerting import build_notifier_from_env
        from service.alpaca.reconciliation import persist_statements, reconcile
        from service.alpaca.statements import fetch_account_activities
        from service.alpaca.trading_client import AlpacaTradingClient
    except Exception as exc:  # pragma: no cover
        LOGGER.error("Imports indisponibles: %s", exc)
        return 2

    engine = get_sqlalchemy_engine()
    inserted = 0
    if not args.no_fetch:
        client = AlpacaTradingClient(broker_mode=args.broker_mode, account_id=args.account)
        activities = fetch_account_activities(
            client,
            since=datetime.combine(trade_date, datetime.min.time()),
            until=datetime.combine(trade_date + timedelta(days=1), datetime.min.time()),
        )
        inserted = persist_statements(engine, args.account, activities)
        LOGGER.info("Fetched/persisted %d activities for %s.", inserted, trade_date)

    diffs = reconcile(engine, account_id=args.account, trade_date=trade_date)
    summary = {
        "account": args.account,
        "trade_date": str(trade_date),
        "inserted": inserted,
        "diff_count": len(diffs),
        "diffs": [d.to_dict() for d in diffs],
    }
    payload = json.dumps(summary, indent=2, sort_keys=True, default=str)
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(payload, encoding="utf-8")
    print(payload)

    # Audit chain (best-effort).
    try:
        AuditChainRepository(engine).append(
            "broker_reconciliation",
            f"{args.account}-{trade_date}",
            {k: v for k, v in summary.items() if k != "diffs"},
        )
    except Exception:  # noqa: BLE001
        pass

    if diffs:
        try:
            notifier = build_notifier_from_env()
            notifier.send(
                subject=f"[reconciliation] {len(diffs)} divergence(s) {args.account}/{trade_date}",
                body=payload[:4000],
                severity="warning" if len(diffs) < 5 else "critical",
            )
        except Exception:  # noqa: BLE001
            LOGGER.debug("Notifier indisponible.", exc_info=True)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

