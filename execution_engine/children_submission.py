"""Sprint S7 - Children + rebalance order submission helpers.

Free functions extracted from :class:`execution_engine.executor.ProductionExecutor`.
``ProductionExecutor._submit_children`` and ``_submit_rebalance_orders`` become
thin delegations preserving their public signatures.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from execution_engine.account_state import (
    _AccountConstraintState,
    reserve_account_capacity_for_intent,
    should_defer_children,
)
from execution_engine.audit import make_event
from execution_engine.models import (
    BrokerOrder,
    EventType,
    ExecutionEvent,
    IntentRole,
    OrderIntent,
    OrderStatus,
)
from execution_engine.order_intents import (
    build_initial_stop_intent,
    build_rebalance_buy_intent,
    build_rebalance_sell_intent,
    build_take_profit_intent,
    build_trailing_stop_intent,
    resolve_trailing_activation_price,
)
from common.quantity_utils import format_share_quantity, is_effectively_integer_quantity
from service.alpaca.trading_client import BrokerApiError

if TYPE_CHECKING:  # pragma: no cover
    from execution_engine.executor import ProductionExecutor

LOGGER = logging.getLogger(__name__)


def submit_children(
    executor: "ProductionExecutor",
    parent: OrderIntent,
    filled_order: BrokerOrder,
    exec_run_id: str,
    *,
    account_state: _AccountConstraintState,
    metrics: dict[str, int],
    target: Any | None = None,
) -> list[ExecutionEvent]:
    cfg = executor._cfg
    broker = executor._broker
    events: list[ExecutionEvent] = []
    fill_qty = filled_order.filled_qty
    fill_price = filled_order.avg_fill_price or parent.decision_price
    if fill_qty <= 0:
        return events

    protections_allowed, blocked_reason = cfg.can_submit_fractional_protection_orders(
        fill_qty,
        context="children",
    )
    if not protections_allowed:
        metrics["children_skipped_fractional_entry_only_mode"] = (
            metrics.get("children_skipped_fractional_entry_only_mode", 0) + 1
        )
        events.append(
            make_event(
                exec_run_id,
                EventType.CHILDREN_DEFERRED_ACCOUNT_CONSTRAINT,
                (
                    f"Fractional protections skipped for {parent.symbol}: "
                    f"entry-only mode qty={format_share_quantity(fill_qty)}"
                ),
                symbol=parent.symbol,
                intent_id=parent.intent_id,
                payload={
                    "reason": blocked_reason,
                    "fill_qty": fill_qty,
                    "fractional_live_entries_enabled": cfg.fractional_live_entries_enabled,
                    "fractional_live_protections_enabled": cfg.fractional_live_protections_enabled,
                    "fractional_live_mode": cfg.resolved_fractional_live_mode,
                },
            )
        )
        return events

    defer_children, reason = should_defer_children(account_state)
    if defer_children:
        metrics["children_deferred"] += 1
        events.append(
            make_event(
                exec_run_id,
                EventType.CHILDREN_DEFERRED_ACCOUNT_CONSTRAINT,
                f"Children deferred for {parent.symbol} due to {reason}",
                symbol=parent.symbol,
                intent_id=parent.intent_id,
                payload={
                    "reason": reason,
                    "account_type": account_state.account_type,
                    "swing_only": account_state.swing_only,
                    "daytrade_count": account_state.daytrade_count,
                },
            )
        )
        return events

    tp_intent = build_take_profit_intent(parent, fill_qty, fill_price, cfg, target=target)
    stop_intent = build_initial_stop_intent(parent, fill_qty, fill_price, cfg, target=target)
    protection_intent = stop_intent or build_trailing_stop_intent(
        parent, fill_qty, fill_price, cfg, target=target
    )
    submitted_children: list[tuple[OrderIntent, BrokerOrder]] = []
    initial_stop_submitted_intent: OrderIntent | None = None
    initial_stop_submitted_order: BrokerOrder | None = None
    trigger_price, trigger_mode = (
        resolve_trailing_activation_price(fill_price, cfg, target)
        if stop_intent is not None
        else (None, None)
    )

    for child in [tp_intent, protection_intent]:
        try:
            child_order = broker.submit_intent(child)
            executor._persist_child_order_state(child, child_order)
            submitted_children.append((child, child_order))
            if child.intent_role == IntentRole.TAKE_PROFIT:
                metrics["child_take_profit_orders_submitted"] = (
                    metrics.get("child_take_profit_orders_submitted", 0) + 1
                )
            elif child.intent_role == IntentRole.INITIAL_STOP:
                metrics["child_initial_stop_orders_submitted"] = (
                    metrics.get("child_initial_stop_orders_submitted", 0) + 1
                )
                initial_stop_submitted_intent = child
                initial_stop_submitted_order = child_order
            elif child.intent_role == IntentRole.TRAILING_STOP:
                metrics["child_trailing_stop_orders_submitted"] = (
                    metrics.get("child_trailing_stop_orders_submitted", 0) + 1
                )
        except Exception as exc:
            LOGGER.warning("Child submit failed for %s %s: %s", child.symbol, child.intent_role, exc)
            metrics["child_order_submit_failures"] = (
                metrics.get("child_order_submit_failures", 0) + 1
            )
            if child.intent_role == IntentRole.INITIAL_STOP:
                fallback_trailing = build_trailing_stop_intent(
                    parent, fill_qty, fill_price, cfg, target=target
                )
                try:
                    fallback_order = broker.submit_intent(fallback_trailing)
                    executor._persist_child_order_state(fallback_trailing, fallback_order)
                    submitted_children.append((fallback_trailing, fallback_order))
                    metrics["child_trailing_stop_orders_submitted"] = (
                        metrics.get("child_trailing_stop_orders_submitted", 0) + 1
                    )
                except Exception as fallback_exc:
                    LOGGER.warning(
                        "Trailing fallback submit failed for %s after initial stop failure: %s",
                        child.symbol,
                        fallback_exc,
                    )
                    metrics["child_order_submit_failures"] = (
                        metrics.get("child_order_submit_failures", 0) + 1
                    )

    protection_child = next(
        (
            child
            for child, _ in submitted_children
            if child.intent_role in {IntentRole.INITIAL_STOP, IntentRole.TRAILING_STOP}
        ),
        None,
    )
    protection_mode = None
    if protection_child is not None:
        protection_mode = (
            "broker_initial_stop"
            if protection_child.intent_role == IntentRole.INITIAL_STOP
            else "trailing_fallback"
        )
    protection_label = {
        "broker_initial_stop": "STOP",
        "trailing_fallback": "TRAIL",
        None: "PROTECTION_FAILED",
    }[protection_mode]

    events.append(
        make_event(
            exec_run_id,
            EventType.CHILDREN_SUBMITTED,
            f"Bracket children for {parent.symbol}: TP + {protection_label}",
            symbol=parent.symbol,
            intent_id=parent.intent_id,
            payload={
                "take_profit_limit_price": tp_intent.limit_price,
                "initial_stop_price": stop_intent.stop_price if stop_intent is not None else None,
                "trailing_stop_percent": protection_child.trail_percent
                if protection_child and protection_child.intent_role == IntentRole.TRAILING_STOP
                else None,
                "protection_mode": protection_mode,
                "child_order_roles": [child.intent_role for child, _ in submitted_children],
                "dynamic_trailing_trigger_price": trigger_price,
                "dynamic_trailing_trigger_mode": trigger_mode,
                "risk_per_share": getattr(target, "risk_per_share", None),
                "stop_price_initial": getattr(target, "stop_price_initial", None),
                "initial_risk_dollars": getattr(target, "initial_risk_dollars", None),
            },
        )
    )
    return events


def submit_rebalance_orders(
    executor: "ProductionExecutor",
    action_diffs: list,
    exec_run_id: str,
    targets: list,
    metrics: dict[str, int],
    account_state: _AccountConstraintState,
) -> list[ExecutionEvent]:
    """Submit sell_excess / buy_more orders to correct reconciliation diffs.

    'investigate' diffs (broker symbols off-target) are logged but skipped.
    """
    cfg = executor._cfg
    broker = executor._broker
    events: list[ExecutionEvent] = []
    risk_run_id = targets[0].risk_run_id if targets else "unknown"

    for diff in action_diffs:
        if diff.action == "investigate":
            LOGGER.warning(
                "Rebalance SKIP %s (investigate) : %.0f shares broker hors cible - action manuelle requise",
                diff.symbol,
                diff.broker_qty,
            )
            events.append(
                make_event(
                    exec_run_id,
                    EventType.RECONCILE_DIFF,
                    f"INVESTIGATE {diff.symbol}: {diff.broker_qty:.0f} broker, hors cible",
                    symbol=diff.symbol,
                )
            )
            continue

        qty = abs(diff.delta)
        if qty <= 1e-9:
            continue

        if diff.action == "sell_excess":
            intent = build_rebalance_sell_intent(
                exec_run_id=exec_run_id,
                risk_run_id=risk_run_id,
                symbol=diff.symbol,
                qty=qty,
                broker_mode=cfg.broker_mode,
            )
            action_label = (
                f"SELL EXCESS {diff.symbol}: -{format_share_quantity(qty)} shares "
                f"(broker={format_share_quantity(diff.broker_qty)} > cible={format_share_quantity(diff.target_qty)})"
            )
        else:  # buy_more
            intent = build_rebalance_buy_intent(
                exec_run_id=exec_run_id,
                risk_run_id=risk_run_id,
                symbol=diff.symbol,
                qty=qty,
                broker_mode=cfg.broker_mode,
            )
            action_label = (
                f"BUY MORE {diff.symbol}: +{format_share_quantity(qty)} shares "
                f"(broker={format_share_quantity(diff.broker_qty)} < cible={format_share_quantity(diff.target_qty)})"
            )

            if not reserve_account_capacity_for_intent(
                intent, account_state, exec_run_id, events, metrics
            ):
                LOGGER.info("Rebalance buy blocked by account constraints: %s", diff.symbol)
                continue

        LOGGER.info("Rebalance: %s", action_label)

        executor._persist_order_request_state(intent, status=OrderStatus.NEW)

        try:
            order = broker.submit_intent(intent)
            executor._persist_order_request_state(intent, status=order.status)
            executor._persist_broker_order_state(intent, order)
            metrics["rebalance_submitted"] = metrics.get("rebalance_submitted", 0) + 1
            events.append(
                make_event(
                    exec_run_id,
                    EventType.ORDER_SUBMITTED,
                    f"Rebalance submitted: {action_label}",
                    symbol=diff.symbol,
                    broker_order_id=order.broker_order_id,
                    intent_id=intent.intent_id,
                )
            )
            LOGGER.info("Rebalance order submitted: %s -> %s", diff.symbol, order.broker_order_id)
        except BrokerApiError as exc:
            LOGGER.error("Rebalance ordre refuse [%s] %s: %s", exc.status_code, diff.symbol, exc)
            metrics["rebalance_failed"] = metrics.get("rebalance_failed", 0) + 1
            executor._persist_order_request_state(
                intent,
                status=OrderStatus.REJECTED,
                failure_reason=f"[{exc.status_code}] {str(exc)[:200]}",
            )
            events.append(
                make_event(
                    exec_run_id,
                    EventType.ORDER_REJECTED,
                    f"Rebalance rejected [{exc.status_code}] {diff.symbol}: {str(exc)[:200]}",
                    symbol=diff.symbol,
                    intent_id=intent.intent_id,
                )
            )
        except Exception as exc:
            LOGGER.error("Rebalance submit failed %s: %s", diff.symbol, exc)
            metrics["rebalance_failed"] = metrics.get("rebalance_failed", 0) + 1
            executor._persist_order_request_state(
                intent,
                status=OrderStatus.FAILED,
                failure_reason=str(exc)[:200],
            )
            events.append(
                make_event(
                    exec_run_id,
                    EventType.ORDER_REJECTED,
                    f"Rebalance failed {diff.symbol}: {str(exc)[:200]}",
                    symbol=diff.symbol,
                    intent_id=intent.intent_id,
                )
            )

        if cfg.inter_order_delay_ms > 0:
            time.sleep(cfg.inter_order_delay_ms / 1000.0)

    return events


__all__ = ["submit_children", "submit_rebalance_orders"]

