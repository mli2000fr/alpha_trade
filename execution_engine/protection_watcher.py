"""Watcher post-run dédié à la promotion stop initial -> trailing dynamique."""
from __future__ import annotations

import argparse
import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable

from common.utils import configure_root_logging
from database.run_business_summaries import emit_run_summary, persist_run_business_summary
from execution_engine.audit import build_run_id, make_event, order_intent_to_db_dict
from execution_engine.broker_adapter import BrokerAdapter
from execution_engine.config import ExecutionConfig
from execution_engine.db_io import ExecutionRepository
from execution_engine.models import (
    BrokerOrder,
    EventType,
    IntentRole,
    OrderIntent,
    OrderStatus,
    ProtectionWatchItem,
)
from execution_engine.order_intents import build_initial_stop_intent, build_trailing_stop_intent, resolve_trailing_activation_price
from service.alpaca.trading_client import AlpacaTradingClient

LOGGER = logging.getLogger(__name__)


def _build_summary(
    metrics: dict[str, Any],
    *,
    watch_run_id: str,
    started_at: datetime,
    finished_at: datetime,
) -> dict[str, Any]:
    return {
        "run_id": watch_run_id,
        "source_exec_run_id": metrics.get("source_exec_run_id"),
        "trade_date": metrics.get("trade_date"),
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
        "status": metrics.get("status", "COMPLETED"),
        "watched_items": int(metrics.get("watched_items", 0) or 0),
        "triggered_items": int(metrics.get("triggered_items", 0) or 0),
        "transitioned_items": int(metrics.get("transitioned_items", 0) or 0),
        "pending_items": int(metrics.get("pending_items", 0) or 0),
        "terminal_items": int(metrics.get("terminal_items", 0) or 0),
        "skipped_existing_trailing": int(metrics.get("skipped_existing_trailing", 0) or 0),
        "cancel_failed_items": int(metrics.get("cancel_failed_items", 0) or 0),
        "trigger_check_count": int(metrics.get("trigger_check_count", 0) or 0),
        "submit_failed_items": int(metrics.get("submit_failed_items", 0) or 0),
        "broker_mode": metrics.get("broker_mode"),
        "account_id": metrics.get("account_id"),
    }


class ProtectionTransitionWatcher:
    """Surveille après coup les stops initiaux actifs pour les promouvoir en trailing."""

    def __init__(
        self,
        repo: ExecutionRepository,
        broker_factory: Callable[[str, str | None], BrokerAdapter],
        config_factory: Callable[[str, str | None], ExecutionConfig],
    ) -> None:
        self._repo = repo
        self._broker_factory = broker_factory
        self._config_factory = config_factory
        self._broker_cache: dict[tuple[str, str | None], BrokerAdapter] = {}
        self._config_cache: dict[tuple[str, str | None], ExecutionConfig] = {}

    def run(
        self,
        *,
        exec_run_id: str | None = None,
        account_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        started_at = datetime.now()
        items = self._repo.load_pending_protection_watch_items(exec_run_id=exec_run_id, account_id=account_id, limit=limit)
        metrics_by_run: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "status": "COMPLETED",
                "watched_items": 0,
                "triggered_items": 0,
                "transitioned_items": 0,
                "pending_items": 0,
                "terminal_items": 0,
                "skipped_existing_trailing": 0,
                "cancel_failed_items": 0,
                "trigger_check_count": 0,
                "submit_failed_items": 0,
            }
        )

        for item in items:
            run_metrics = metrics_by_run[item.source_exec_run_id]
            run_metrics["source_exec_run_id"] = item.source_exec_run_id
            run_metrics["trade_date"] = item.trade_date.isoformat()
            run_metrics["broker_mode"] = item.broker_mode
            run_metrics["account_id"] = item.account_id
            run_metrics["watched_items"] += 1
            self._process_item(item, run_metrics)

        summaries: list[dict[str, Any]] = []
        finished_at = datetime.now()
        for source_exec_run_id, run_metrics in metrics_by_run.items():
            watch_run_id = f"watch-{build_run_id()}"
            summary = _build_summary(run_metrics, watch_run_id=watch_run_id, started_at=started_at, finished_at=finished_at)
            summaries.append(summary)
            try:
                persist_run_business_summary(
                    summary=summary,
                    step_key="execution_protection_watch",
                    run_kind="step",
                    status=str(summary.get("status", "") or "") or None,
                    summary_run_id=watch_run_id,
                    source_run_id=watch_run_id,
                    entity_run_id=source_exec_run_id,
                    parent_summary_run_id=source_exec_run_id,
                    account_id=run_metrics.get("account_id"),
                    trade_date=summary.get("trade_date"),
                    started_at=summary.get("started_at"),
                    finished_at=summary.get("finished_at"),
                    engine=self._repo.engine,
                )
            except Exception:
                LOGGER.debug("Persistance run_business_summaries indisponible pour le watcher protections.", exc_info=True)
            emit_run_summary(summary)
        return summaries

    def _config_for(self, broker_mode: str, account_id: str | None) -> ExecutionConfig:
        key = (broker_mode, account_id)
        if key not in self._config_cache:
            self._config_cache[key] = self._config_factory(broker_mode, account_id)
        return self._config_cache[key]

    def _broker_for(self, broker_mode: str, account_id: str | None) -> BrokerAdapter:
        key = (broker_mode, account_id)
        if key not in self._broker_cache:
            self._broker_cache[key] = self._broker_factory(broker_mode, account_id)
        return self._broker_cache[key]

    def _persist_event(self, event) -> None:
        try:
            from execution_engine.audit import event_to_db_dict

            self._repo.insert_execution_event(event_to_db_dict(event))
        except Exception:
            LOGGER.debug("Persistance event watcher impossible: %s", event.event_type, exc_info=True)

    def _persist_order_state(self, intent: OrderIntent, order: BrokerOrder, exec_run_id: str) -> None:
        db_dict = order_intent_to_db_dict(intent, exec_run_id, status=order.status)
        db_dict["broker_order_id"] = order.broker_order_id
        db_dict["filled_qty"] = order.filled_qty
        db_dict["avg_fill_price"] = order.avg_fill_price
        try:
            self._repo.upsert_execution_order(db_dict)
        except Exception:
            LOGGER.debug("Persistance ordre watcher impossible pour %s", intent.intent_id, exc_info=True)

    @staticmethod
    def _build_parent_intent(item: ProtectionWatchItem, stop_order: BrokerOrder) -> OrderIntent:
        return OrderIntent(
            intent_id=item.parent_intent_id,
            risk_run_id=item.risk_run_id,
            exec_run_id=item.source_exec_run_id,
            symbol=item.symbol,
            side="buy",
            qty=item.fill_qty,
            order_type="market",
            limit_price=None,
            trail_percent=None,
            broker_mode=item.broker_mode,
            parent_intent_id=None,
            intent_role=IntentRole.ENTRY,
            idempotency_key=f"watch-parent-{item.parent_intent_id}",
            decision_price=item.fill_price,
            stop_price=stop_order.stop_price,
        )

    def _cancel_initial_stop(
        self,
        broker: BrokerAdapter,
        config: ExecutionConfig,
        item: ProtectionWatchItem,
        stop_order: BrokerOrder,
    ) -> tuple[bool, BrokerOrder]:
        if not broker.cancel_broker_order(stop_order.broker_order_id):
            return False, stop_order
        latest_order = stop_order
        deadline = time.monotonic() + config.cancel_timeout_seconds
        while time.monotonic() < deadline:
            latest_order = broker.poll_order_status(stop_order.broker_order_id, item.initial_stop_intent_id)
            if latest_order.status == OrderStatus.CANCELED:
                return True, latest_order
            if latest_order.status in {OrderStatus.FILLED, OrderStatus.REJECTED, OrderStatus.FAILED, OrderStatus.EXPIRED}:
                return False, latest_order
            time.sleep(config.poll_interval_seconds)
        return False, latest_order

    def _process_item(self, item: ProtectionWatchItem, metrics: dict[str, Any]) -> None:
        if not item.initial_stop_broker_order_id:
            metrics["submit_failed_items"] += 1
            return

        config = self._config_for(item.broker_mode, item.account_id)
        broker = self._broker_for(item.broker_mode, item.account_id)
        stop_order = broker.poll_order_status(item.initial_stop_broker_order_id, item.initial_stop_intent_id)
        parent_intent = self._build_parent_intent(item, stop_order)
        stop_intent = build_initial_stop_intent(parent_intent, item.fill_qty, item.fill_price, config, target=item)
        if stop_intent is None:
            metrics["submit_failed_items"] += 1
            return
        self._persist_order_state(stop_intent, stop_order, item.source_exec_run_id)

        if stop_order.status in OrderStatus.TERMINAL:
            metrics["terminal_items"] += 1
            return

        trigger_price, trigger_mode = resolve_trailing_activation_price(item.fill_price, config, item)
        if trigger_price is None:
            metrics["pending_items"] += 1
            return

        market_price = broker.get_latest_market_price(item.symbol)
        metrics["trigger_check_count"] += 1
        if market_price is None or market_price < trigger_price:
            metrics["pending_items"] += 1
            return

        metrics["triggered_items"] += 1
        trigger_event = make_event(
            item.source_exec_run_id,
            EventType.PROTECTION_TRIGGER_HIT,
            f"Trigger trailing atteint pour {item.symbol} à {market_price:.2f}",
            symbol=item.symbol,
            broker_order_id=stop_order.broker_order_id,
            intent_id=item.initial_stop_intent_id,
            payload={
                "market_price": round(float(market_price), 4),
                "trigger_price": trigger_price,
                "trigger_mode": trigger_mode,
            },
        )
        self._persist_event(trigger_event)

        open_children = self._repo.load_open_child_orders(item.parent_intent_id)
        if any(child.intent_id != item.initial_stop_intent_id and child.order_type == "trailing_stop" for child in open_children):
            metrics["skipped_existing_trailing"] += 1
            return

        canceled, canceled_order = self._cancel_initial_stop(broker, config, item, stop_order)
        self._persist_order_state(stop_intent, canceled_order, item.source_exec_run_id)
        if not canceled:
            metrics["cancel_failed_items"] += 1
            self._persist_event(make_event(
                item.source_exec_run_id,
                EventType.PROTECTION_TRANSITION_FAILED,
                f"Impossible d'annuler le stop initial pour {item.symbol}",
                symbol=item.symbol,
                broker_order_id=canceled_order.broker_order_id,
                intent_id=item.initial_stop_intent_id,
                payload={
                    "trigger_price": trigger_price,
                    "trigger_mode": trigger_mode,
                    "stop_status": canceled_order.status,
                },
            ))
            return

        trailing_intent = build_trailing_stop_intent(parent_intent, item.fill_qty, item.fill_price, config, target=item)
        try:
            trailing_order = broker.submit_intent(trailing_intent)
            self._persist_order_state(trailing_intent, trailing_order, item.source_exec_run_id)
        except Exception as exc:
            metrics["submit_failed_items"] += 1
            self._persist_event(make_event(
                item.source_exec_run_id,
                EventType.PROTECTION_TRANSITION_FAILED,
                f"Echec soumission trailing dynamique pour {item.symbol}: {str(exc)[:120]}",
                symbol=item.symbol,
                intent_id=item.initial_stop_intent_id,
                payload={
                    "trigger_price": trigger_price,
                    "trigger_mode": trigger_mode,
                },
            ))
            return

        metrics["transitioned_items"] += 1
        self._persist_event(make_event(
            item.source_exec_run_id,
            EventType.PROTECTION_TRANSITION_COMPLETED,
            f"Stop initial promu en trailing pour {item.symbol}",
            symbol=item.symbol,
            broker_order_id=trailing_order.broker_order_id,
            intent_id=trailing_intent.intent_id,
            payload={
                "trigger_price": trigger_price,
                "trigger_mode": trigger_mode,
                "trailing_stop_percent": trailing_intent.trail_percent,
                "initial_stop_order_id": stop_order.broker_order_id,
                "trailing_stop_order_id": trailing_order.broker_order_id,
            },
        ))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Alpha Trade — Protection Transition Watcher")
    parser.add_argument("--exec-run-id", type=str, default=None)
    parser.add_argument("--account", type=str, default=None)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--broker-mode", type=str, default="paper", choices=["paper", "live"])
    parser.add_argument("--trailing-stop-pct", type=float, default=0.05)
    parser.add_argument("--trailing-activation-trigger", type=str, default="multiple_r", choices=["multiple_r", "profit_pct"])
    parser.add_argument("--trailing-activation-r-multiple", type=float, default=1.0)
    parser.add_argument("--trailing-activation-profit-pct", type=float, default=0.03)
    parser.add_argument("--log-level", type=str, default="INFO")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    configure_root_logging(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        log_path="./log/execution_protection_watcher.log",
        fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    def config_factory(broker_mode: str, account_id: str | None) -> ExecutionConfig:
        return ExecutionConfig(
            broker_mode=broker_mode,
            account_id=account_id,
            trailing_stop_pct=args.trailing_stop_pct,
            trailing_activation_trigger=args.trailing_activation_trigger,
            trailing_activation_r_multiple=args.trailing_activation_r_multiple,
            trailing_activation_profit_pct=args.trailing_activation_profit_pct,
        )

    def broker_factory(broker_mode: str, account_id: str | None) -> BrokerAdapter:
        config = config_factory(broker_mode, account_id)
        client = AlpacaTradingClient(broker_mode=broker_mode, account_id=account_id)
        return BrokerAdapter(client, config)

    repo = ExecutionRepository()
    watcher = ProtectionTransitionWatcher(repo, broker_factory=broker_factory, config_factory=config_factory)
    summaries = watcher.run(exec_run_id=args.exec_run_id, account_id=args.account, limit=args.limit)
    logging.getLogger(__name__).info("Protection watcher summaries: %s", summaries)


if __name__ == "__main__":
    main()

