"""Job nightly de réconciliation J+1 broker statement ↔ fills internes.

Point d'entrée canonique Sprint S3 :

```powershell
python -m execution_engine.reconcile_statement --account default --trade-date 2026-05-21
python -m execution_engine.reconcile_statement --account default --statement-path .\alpaca_j1.csv
```
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from database.connection import get_sqlalchemy_engine
from database.run_business_summaries import persist_run_business_summary
from service.alpaca.reconciliation import (
    build_reconciliation_summary,
    parse_statement_csv,
    persist_statements,
    reconcile,
)

LOGGER = logging.getLogger(__name__)
STEP_KEY = "execution_reconciliation_j1"


def _parse_trade_date(raw_value: str | None) -> date:
    if not raw_value:
        return (datetime.now(UTC) - timedelta(days=1)).date()
    return datetime.strptime(raw_value, "%Y-%m-%d").date()


def _load_statement_activities(
    *,
    statement_path: str | None,
    trade_date: date,
    account_id: str,
    broker_mode: str,
    no_fetch: bool,
) -> tuple[list[dict[str, Any]], str, bool]:
    if statement_path:
        path = Path(statement_path)
        suffix = path.suffix.lower()
        if suffix != ".csv":
            raise ValueError(
                "Seul le format CSV Alpaca J+1 est automatisé pour le moment "
                f"(reçu: {path.name})."
            )
        return parse_statement_csv(path), "csv", False
    if no_fetch:
        return [], "persisted_only", False

    from service.alpaca.statements import fetch_account_activities
    from service.alpaca.trading_client import AlpacaTradingClient

    client = AlpacaTradingClient(broker_mode=broker_mode, account_id=account_id)
    start_dt = datetime.combine(trade_date, datetime.min.time())
    end_dt = datetime.combine(trade_date + timedelta(days=1), datetime.min.time())
    activities = fetch_account_activities(client, since=start_dt, until=end_dt)
    return [dict(item) for item in activities], "alpaca_api", True


def run_reconciliation_job(
    *,
    account_id: str,
    trade_date: date,
    broker_mode: str = "paper",
    statement_path: str | None = None,
    no_fetch: bool = False,
    report_out: Path | None = None,
) -> dict[str, Any]:
    engine = get_sqlalchemy_engine()
    activities, source_kind, fetched_from_api = _load_statement_activities(
        statement_path=statement_path,
        trade_date=trade_date,
        account_id=account_id,
        broker_mode=broker_mode,
        no_fetch=no_fetch,
    )
    inserted = persist_statements(engine, account_id, activities) if activities else 0
    diffs = reconcile(engine, account_id=account_id, trade_date=trade_date)
    summary = build_reconciliation_summary(
        account_id=account_id,
        trade_date=trade_date,
        diffs=diffs,
        source_kind=source_kind,
        activity_count=len(activities),
        inserted=inserted,
        fetched_from_api=fetched_from_api,
        statement_path=str(statement_path).strip() or None,
    )
    now_utc = datetime.now(UTC)
    persist_run_business_summary(
        summary=summary,
        step_key=STEP_KEY,
        run_kind="step",
        status=str(summary.get("status") or "WARNING"),
        summary_run_id=str(summary.get("run_id") or "") or None,
        source_run_id=str(summary.get("run_id") or "") or None,
        entity_run_id=f"{account_id}:{trade_date.isoformat()}",
        account_id=account_id,
        trade_date=trade_date,
        started_at=now_utc,
        finished_at=now_utc,
        engine=engine,
    )
    payload = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    if report_out is not None:
        report_out.parent.mkdir(parents=True, exist_ok=True)
        report_out.write_text(payload, encoding="utf-8")
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Réconciliation nightly J+1 broker statement ↔ fills internes.")
    parser.add_argument("--account", default="default")
    parser.add_argument("--trade-date", "--date", dest="trade_date", default=None, help="YYYY-MM-DD (défaut: J-1)")
    parser.add_argument("--broker-mode", choices=("paper", "live"), default="paper")
    parser.add_argument("--statement-path", default=None, help="Chemin vers un export Alpaca J+1 au format CSV")
    parser.add_argument("--no-fetch", action="store_true", help="N'appelle pas Alpaca ; exploite uniquement les statements déjà persistés ou le CSV fourni")
    parser.add_argument("--report-out", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_arg_parser().parse_args(argv)
    try:
        trade_date = _parse_trade_date(args.trade_date)
        summary = run_reconciliation_job(
            account_id=str(args.account or "default"),
            trade_date=trade_date,
            broker_mode=str(args.broker_mode or "paper"),
            statement_path=str(args.statement_path).strip() or None,
            no_fetch=bool(args.no_fetch),
            report_out=args.report_out,
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("reconcile_statement failed: %s", exc, exc_info=True)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 1 if int(summary.get("diff_count", 0) or 0) > 0 else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


