"""Sprint S21.4 — CLI génération rapport mensuel signé depuis ``broker_statements``.

Usage::

    python scripts/run_monthly_broker_report.py \\
        --account ACCOUNT_ID --month 2026-04 \\
        --secret-env ALPHA_TRADE_REPORT_SECRET \\
        --db-url sqlite:///alpha_trade.db \\
        --out artifacts/reports/

Génère ``<out>/monthly_<account>_<YYYY-MM>.json`` signé HMAC-SHA256.
"""
from __future__ import annotations

import argparse
import calendar
import json
import os
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine

from reporting.monthly_report import build_monthly_report
from service.alpaca.statements import load_monthly_inputs_from_db


def _month_bounds(month: str) -> tuple[date, date]:
    """``YYYY-MM`` → ``(period_start, period_end)`` (period_end exclusif au mois suivant)."""
    year, mon = (int(x) for x in month.split("-", 1))
    last_day = calendar.monthrange(year, mon)[1]
    start = date(year, mon, 1)
    end = date(year, mon, last_day)  # inclusive (rapport)
    return start, end


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", required=True)
    parser.add_argument("--month", required=True, help="YYYY-MM")
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--secret-env", default="ALPHA_TRADE_REPORT_SECRET")
    parser.add_argument("--out", default="artifacts/reports")
    args = parser.parse_args(argv)

    secret = os.getenv(args.secret_env, "").encode("utf-8")
    if not secret:
        print(f"ERROR: ${args.secret_env} non défini", file=sys.stderr)
        return 2

    period_start, period_end = _month_bounds(args.month)
    engine = create_engine(args.db_url, future=True)
    inputs = load_monthly_inputs_from_db(
        engine, account_id=args.account,
        period_start=period_start, period_end=period_end,
    )
    report = build_monthly_report(inputs, secret=secret)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"monthly_{args.account}_{args.month}.json"
    out_path.write_text(report.to_json(), encoding="utf-8")
    print(json.dumps({"account": args.account, "month": args.month,
                      "path": str(out_path), "fills": report.fills_count,
                      "trades": report.trades_count,
                      "realized_pnl": report.realized_pnl}, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

