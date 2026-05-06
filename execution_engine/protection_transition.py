"""Sprint S7 - Dynamic trailing transition (post-fill watcher).

Free function extracted from :class:`execution_engine.executor.ProductionExecutor`.
``ProductionExecutor._maybe_activate_dynamic_trailing`` becomes a thin
delegation to keep its public signature stable.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from execution_engine.audit import make_event
from execution_engine.models import BrokerOrder, EventType, ExecutionEvent, OrderIntent
from execution_engine.order_intents import (
    build_trailing_stop_intent,
    resolve_trailing_activation_price,
)

if TYPE_CHECKING:  # pragma: no cover
    from execution_engine.executor import ProductionExecutor

LOGGER = logging.getLogger(__name__)


def maybe_activate_dynamic_trailing(
    executor: "ProductionExecutor",
    parent: OrderIntent,
    fill_qty: float,
    fill_price: float,
    exec_run_id: str,
    *,
    target: Any | None,
    initial_stop_intent: OrderIntent | None,
    initial_stop_order: BrokerOrder | None,
    metrics: dict[str, int],
) -> list[ExecutionEvent]:
    cfg = executor._cfg
    broker = executor._broker
    events: list[ExecutionEvent] = []
    if (
        not cfg.enable_dynamic_trailing_transition
        or cfg.protection_transition_timeout_seconds <= 0
        or target is None
        or initial_stop_intent is None
        or initial_stop_order is None
    ):
        return events

    trigger_price, trigger_mode = resolve_trailing_activation_price(fill_price, cfg, target)
    if trigger_price is None:
        return events

    deadline = time.monotonic() + cfg.protection_transition_timeout_seconds
    while time.monotonic() <= deadline:
        market_price = broker.get_latest_market_price(parent.symbol)
        metrics["dynamic_trailing_trigger_checks"] = (
            metrics.get("dynamic_trailing_trigger_checks", 0) + 1
        )
        if market_price is not None and market_price >= trigger_price:
            events.append(
                make_event(
                    exec_run_id,
                    EventType.PROTECTION_TRIGGER_HIT,
                    f"Trigger trailing atteint pour {parent.symbol} a {market_price:.2f}",
                    symbol=parent.symbol,
                    intent_id=parent.intent_id,
                    broker_order_id=initial_stop_order.broker_order_id,
                    payload={
                        "market_price": round(float(market_price), 4),
                        "trigger_price": trigger_price,
                        "trigger_mode": trigger_mode,
                        "initial_stop_order_id": initial_stop_order.broker_order_id,
                    },
                )
            )
            canceled, canceled_order = executor._cancel_child_for_transition(
                initial_stop_intent, initial_stop_order, exec_run_id
            )
            if not canceled:
                metrics["dynamic_trailing_cancel_failures"] = (
                    metrics.get("dynamic_trailing_cancel_failures", 0) + 1
                )
                events.append(
                    make_event(
                        exec_run_id,
                        EventType.PROTECTION_TRANSITION_FAILED,
                        f"Impossible d'annuler le stop initial pour {parent.symbol}",
                        symbol=parent.symbol,
                        intent_id=initial_stop_intent.intent_id,
                        broker_order_id=canceled_order.broker_order_id,
                        payload={
                            "trigger_price": trigger_price,
                            "market_price": round(float(market_price), 4),
                            "trigger_mode": trigger_mode,
                            "stop_status": canceled_order.status,
                        },
                    )
                )
                return events

            trailing_intent = build_trailing_stop_intent(
                parent, fill_qty, fill_price, cfg, target=target
            )
            try:
                trailing_order = broker.submit_intent(trailing_intent)
                executor._persist_child_order_state(trailing_intent, trailing_order)
                metrics["child_trailing_stop_orders_submitted"] = (
                    metrics.get("child_trailing_stop_orders_submitted", 0) + 1
                )
                metrics["dynamic_trailing_activations"] = (
                    metrics.get("dynamic_trailing_activations", 0) + 1
                )
                events.append(
                    make_event(
                        exec_run_id,
                        EventType.PROTECTION_TRANSITION_COMPLETED,
                        f"Stop initial promu en trailing pour {parent.symbol}",
                        symbol=parent.symbol,
                        intent_id=trailing_intent.intent_id,
                        broker_order_id=trailing_order.broker_order_id,
                        payload={
                            "trigger_price": trigger_price,
                            "market_price": round(float(market_price), 4),
                            "trigger_mode": trigger_mode,
                            "initial_stop_order_id": initial_stop_order.broker_order_id,
                            "trailing_stop_order_id": trailing_order.broker_order_id,
                            "trailing_stop_percent": trailing_intent.trail_percent,
                        },
                    )
                )
            except Exception as exc:
                metrics["child_order_submit_failures"] = (
                    metrics.get("child_order_submit_failures", 0) + 1
                )
                events.append(
                    make_event(
                        exec_run_id,
                        EventType.PROTECTION_TRANSITION_FAILED,
                        f"Echec soumission trailing dynamique pour {parent.symbol}: {str(exc)[:120]}",
                        symbol=parent.symbol,
                        intent_id=initial_stop_intent.intent_id,
                        payload={
                            "trigger_price": trigger_price,
                            "market_price": round(float(market_price), 4),
                            "trigger_mode": trigger_mode,
                        },
                    )
                )
            return events

        if time.monotonic() >= deadline:
            break
        time.sleep(cfg.protection_transition_poll_interval_seconds)

    metrics["dynamic_trailing_timeouts"] = metrics.get("dynamic_trailing_timeouts", 0) + 1
    events.append(
        make_event(
            exec_run_id,
            EventType.PROTECTION_TRANSITION_FAILED,
            f"Trigger trailing non atteint dans la fenetre pour {parent.symbol}",
            symbol=parent.symbol,
            intent_id=initial_stop_intent.intent_id,
            broker_order_id=initial_stop_order.broker_order_id,
            payload={
                "trigger_price": trigger_price,
                "trigger_mode": trigger_mode,
                "timeout_seconds": cfg.protection_transition_timeout_seconds,
            },
        )
    )
    return events


__all__ = ["maybe_activate_dynamic_trailing"]

