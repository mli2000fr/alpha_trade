"""Réconciliation analytique et actionnable des états execution/broker."""
from __future__ import annotations

from typing import Any

from common.quantity_utils import QUANTITY_EPSILON, normalize_share_quantity
from execution_engine.models import (
    ExecutionPosition,
    ExecutionReconciliationResult,
    ExecutionTarget,
    ReconcileDiff,
    ReconciliationStatus,
)


def _symbol_key(raw_symbol: str | None) -> str:
    return str(raw_symbol or "").strip().upper()


def _qty(value: Any) -> float:
    return normalize_share_quantity(value)


def _effective_tolerance(tolerance: float | int) -> float:
    return max(normalize_share_quantity(tolerance), QUANTITY_EPSILON)


def reconcile_execution_state(
    *,
    exec_run_id: str,
    account_id: str,
    targets: list[ExecutionTarget],
    broker_positions: list[dict[str, Any]],
    internal_positions: list[ExecutionPosition],
    open_order_state: list[dict[str, Any]] | None = None,
    protection_state: list[dict[str, Any]] | None = None,
    tolerance: float = 0.0,
    buying_power_available: float | None = None,
) -> list[ExecutionReconciliationResult]:
    effective_tolerance = _effective_tolerance(tolerance)
    target_map = {_symbol_key(target.symbol): target for target in targets}
    broker_map = {
        _symbol_key(position.get("symbol")): _qty(position.get("qty"))
        for position in broker_positions
        if _symbol_key(position.get("symbol"))
    }
    internal_map = {
        _symbol_key(position.symbol): _qty(position.net_qty)
        for position in internal_positions
        if _symbol_key(position.symbol) and _symbol_key(position.symbol) != "__FLAT__"
    }
    order_map = {
        _symbol_key(row.get("symbol")): {
            "open_request_buy_qty": _qty(row.get("open_request_buy_qty")),
            "open_request_sell_qty": _qty(row.get("open_request_sell_qty")),
            "open_broker_buy_qty": _qty(row.get("open_broker_buy_qty")),
            "open_broker_sell_qty": _qty(row.get("open_broker_sell_qty")),
        }
        for row in (open_order_state or [])
        if _symbol_key(row.get("symbol"))
    }
    protection_map = {
        _symbol_key(row.get("symbol")): _qty(row.get("protection_qty"))
        for row in (protection_state or [])
        if _symbol_key(row.get("symbol"))
    }

    all_symbols = sorted(set(target_map) | set(broker_map) | set(internal_map) | set(order_map) | set(protection_map))
    results: list[ExecutionReconciliationResult] = []
    for symbol in all_symbols:
        target = target_map.get(symbol)
        target_qty = _qty(target.target_shares) if target is not None else 0.0
        internal_qty = _qty(internal_map.get(symbol, 0.0))
        broker_qty = _qty(broker_map.get(symbol, 0.0))
        delta = normalize_share_quantity(broker_qty - target_qty)
        order_state_for_symbol = order_map.get(symbol, {})
        open_request_buy_qty = _qty(order_state_for_symbol.get("open_request_buy_qty"))
        open_request_sell_qty = _qty(order_state_for_symbol.get("open_request_sell_qty"))
        open_broker_buy_qty = _qty(order_state_for_symbol.get("open_broker_buy_qty"))
        open_broker_sell_qty = _qty(order_state_for_symbol.get("open_broker_sell_qty"))
        protection_qty = _qty(protection_map.get(symbol, 0.0))
        has_open_protection = protection_qty > effective_tolerance

        if abs(delta) <= effective_tolerance:
            action = "none"
        elif symbol not in target_map:
            action = "investigate"
        elif delta > 0:
            action = "sell_excess"
        else:
            action = "buy_more"

        reasons: list[str] = []
        if abs(normalize_share_quantity(broker_qty - internal_qty)) > effective_tolerance:
            reasons.append("internal_position_mismatch")
        if any(
            value > effective_tolerance
            for value in (open_request_buy_qty, open_request_sell_qty, open_broker_buy_qty, open_broker_sell_qty)
        ):
            reasons.append("open_orders_in_flight")
        if broker_qty > effective_tolerance and not has_open_protection:
            reasons.append("missing_protection")

        if action == "buy_more" and buying_power_available is not None:
            reference_price = float(target.entry_price) if target is not None else 0.0
            estimated_notional = abs(delta) * max(reference_price, 0.0)
            if estimated_notional > max(float(buying_power_available), 0.0) + effective_tolerance:
                reasons.append("insufficient_buying_power")

        if action == "investigate":
            status = ReconciliationStatus.MANUAL_REVIEW
        elif "insufficient_buying_power" in reasons or "missing_protection" in reasons:
            status = ReconciliationStatus.BLOCKED
        elif reasons:
            status = ReconciliationStatus.MANUAL_REVIEW
        else:
            status = ReconciliationStatus.SAFE_AUTO

        reason_code = "|".join(reasons) if reasons else None
        results.append(ExecutionReconciliationResult(
            exec_run_id=exec_run_id,
            account_id=account_id,
            symbol=symbol,
            target_qty=target_qty,
            internal_position_qty=internal_qty,
            broker_position_qty=broker_qty,
            position_delta=delta,
            open_request_buy_qty=open_request_buy_qty,
            open_request_sell_qty=open_request_sell_qty,
            open_broker_buy_qty=open_broker_buy_qty,
            open_broker_sell_qty=open_broker_sell_qty,
            has_open_protection=has_open_protection,
            protection_qty=protection_qty,
            action=action,
            reconciliation_status=status,
            reason_code=reason_code,
        ))
    return results


def reconcile_targets_vs_broker(
    targets: list[ExecutionTarget],
    broker_positions: list[dict],
    tolerance: float = 0.0,
) -> list[ReconcileDiff]:
    results = reconcile_execution_state(
        exec_run_id="legacy-reconcile",
        account_id="default",
        targets=targets,
        broker_positions=broker_positions,
        internal_positions=[],
        open_order_state=[],
        protection_state=[],
        tolerance=tolerance,
        buying_power_available=None,
    )
    return [
        ReconcileDiff(
            symbol=result.symbol,
            target_qty=result.target_qty,
            broker_qty=result.broker_position_qty,
            delta=result.position_delta,
            action=result.action,
        )
        for result in results
    ]
