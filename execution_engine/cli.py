"""CLI du module execution_engine."""
from __future__ import annotations

import argparse
import logging
from datetime import date, datetime

from database.run_business_summaries import emit_run_summary, persist_run_business_summary
from execution_engine.audit import build_execution_run_summary
from execution_engine.config import ExecutionConfig
from execution_engine.db_io import ExecutionRepository
from execution_engine.broker_adapter import BrokerAdapter
from execution_engine.executor import ProductionExecutor
from execution_engine.oco_manager import OcoManager
from service.alpaca.trading_client import AlpacaTradingClient
from common.utils import configure_root_logging


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Alpha Trade — Production Executor")
    p.add_argument("--trade-date", type=str, default=None)
    p.add_argument("--risk-run-id", type=str, default=None)
    p.add_argument("--broker-mode", type=str, default="paper", choices=["paper", "live"])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--entry-order-type", type=str, default="market", choices=["market", "limit"])
    p.add_argument("--limit-price-buffer-bps", type=int, default=10)
    p.add_argument("--profit-taker-pct", type=float, default=0.08)
    p.add_argument("--trailing-stop-pct", type=float, default=0.05)
    p.add_argument("--max-order-retries", type=int, default=3)
    p.add_argument("--poll-interval-seconds", type=float, default=2.0)
    p.add_argument("--fill-timeout-seconds", type=int, default=120)
    p.add_argument("--cancel-timeout-seconds", type=int, default=30)
    p.add_argument("--allow-outside-rth", action="store_true")
    p.add_argument("--max-slippage-bps", type=int, default=30)
    p.add_argument("--execution-batch-size", type=int, default=20)
    p.add_argument("--inter-order-delay-ms", type=int, default=350)
    p.add_argument("--account-type", type=str, default="margin", choices=["margin", "cash"])
    p.add_argument("--pdt-rule", type=str, default="auto", choices=["auto", "off"])
    p.add_argument("--swing-only", action="store_true")
    p.add_argument("--account", type=str, default=None, help="Account ID multi-comptes (défaut: premier compte)")
    p.add_argument("--log-level", type=str, default="INFO")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    configure_root_logging(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        log_path="./log/execution_engine.log",
        fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    trade_date_val: date | None = None
    if args.trade_date:
        trade_date_val = date.fromisoformat(args.trade_date)

    config = ExecutionConfig(
        broker_mode=args.broker_mode,
        dry_run=args.dry_run,
        entry_order_type=args.entry_order_type,
        limit_price_buffer_bps=args.limit_price_buffer_bps,
        profit_taker_pct=args.profit_taker_pct,
        trailing_stop_pct=args.trailing_stop_pct,
        max_order_retries=args.max_order_retries,
        poll_interval_seconds=args.poll_interval_seconds,
        fill_timeout_seconds=args.fill_timeout_seconds,
        cancel_timeout_seconds=args.cancel_timeout_seconds,
        allow_outside_rth=args.allow_outside_rth,
        max_slippage_bps=args.max_slippage_bps,
        execution_batch_size=args.execution_batch_size,
        inter_order_delay_ms=args.inter_order_delay_ms,
        account_type=args.account_type,
        pdt_rule=args.pdt_rule,
        swing_only=args.swing_only,
        account_id=args.account,
    )

    repo = ExecutionRepository()
    client = AlpacaTradingClient(broker_mode=config.broker_mode, account_id=args.account)
    broker = BrokerAdapter(client, config)
    oco = OcoManager(broker, repo)
    executor = ProductionExecutor(config, repo, broker, oco)

    started_at = datetime.now()
    metrics = executor.execute_run(risk_run_id=args.risk_run_id, trade_date=trade_date_val)
    finished_at = datetime.now()
    summary = build_execution_run_summary(
        metrics,
        started_at=started_at,
        finished_at=finished_at,
        execution_mode="cli",
        broker_mode=config.broker_mode,
        account_id=args.account,
        account_type=config.account_type,
        effective_pdt_rule=config.effective_pdt_rule,
        swing_only=config.swing_only,
        dry_run=config.dry_run,
        allow_outside_rth=config.allow_outside_rth,
    )
    try:
        persist_run_business_summary(
            summary=summary,
            step_key="execution",
            run_kind="step",
            status=str(summary.get("status", "") or "") or None,
            summary_run_id=str(summary.get("run_id", "") or "") or None,
            entity_run_id=str(summary.get("run_id", "") or "") or None,
            parent_summary_run_id=args.risk_run_id,
            account_id=args.account,
            trade_date=summary.get("trade_date"),
            started_at=summary.get("started_at"),
            finished_at=summary.get("finished_at"),
        )
    except Exception:
        logging.getLogger(__name__).debug("Persistance run_business_summaries indisponible pour execution cli.", exc_info=True)
    emit_run_summary(summary)
    logging.getLogger(__name__).info("Execution metrics: %s", metrics)


if __name__ == "__main__":
    main()
