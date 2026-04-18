"""Fonctions utilitaires d'audit pour execution_engine."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from execution_engine.models import (
    BrokerOrder,
    ExecutionEvent,
    ExecutionFill,
    OrderIntent,
    OrderStatus,
)


def build_run_id() -> str:
    return uuid.uuid4().hex[:16]


def make_event(
    exec_run_id: str,
    event_type: str,
    message: str,
    *,
    symbol: str | None = None,
    broker_order_id: str | None = None,
    intent_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> ExecutionEvent:
    return ExecutionEvent(
        event_id=uuid.uuid4().hex[:16],
        exec_run_id=exec_run_id,
        symbol=symbol,
        event_type=event_type,
        message=message[:255],
        broker_order_id=broker_order_id,
        intent_id=intent_id,
        payload_json=json.dumps(payload) if payload else None,
        created_at=datetime.now(timezone.utc),
    )


def order_intent_to_db_dict(intent: OrderIntent, exec_run_id: str, status: str = OrderStatus.NEW) -> dict[str, Any]:
    return {
        "exec_run_id": exec_run_id,
        "risk_run_id": intent.risk_run_id,
        "symbol": intent.symbol,
        "intent_id": intent.intent_id,
        "parent_intent_id": intent.parent_intent_id,
        "intent_role": intent.intent_role,
        "idempotency_key": intent.idempotency_key,
        "broker_mode": intent.broker_mode,
        "broker_order_id": None,
        "client_order_id": intent.idempotency_key,
        "side": intent.side,
        "qty": intent.qty,
        "filled_qty": 0.0,
        "avg_fill_price": None,
        "order_type": intent.order_type,
        "limit_price": intent.limit_price,
        "stop_price": None,
        "trail_percent": intent.trail_percent,
        "decision_price": intent.decision_price,
        "status": status,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


def broker_order_to_db_dict(order: BrokerOrder, exec_run_id: str) -> dict[str, Any]:
    return {
        "exec_run_id": exec_run_id,
        "broker_order_id": order.broker_order_id,
        "client_order_id": order.client_order_id,
        "intent_id": order.intent_id,
        "symbol": order.symbol,
        "side": order.side,
        "qty": order.qty,
        "filled_qty": order.filled_qty,
        "avg_fill_price": order.avg_fill_price,
        "status": order.status,
        "order_type": order.order_type,
        "limit_price": order.limit_price,
        "stop_price": order.stop_price,
        "trail_percent": order.trail_percent,
        "updated_at": datetime.now(timezone.utc),
    }


def fill_to_db_dict(fill: ExecutionFill, exec_run_id: str) -> dict[str, Any]:
    return {
        "exec_run_id": exec_run_id,
        "fill_id": fill.fill_id,
        "broker_order_id": fill.broker_order_id,
        "intent_id": fill.intent_id,
        "symbol": fill.symbol,
        "filled_qty": fill.filled_qty,
        "avg_fill_price": fill.avg_fill_price,
        "fill_timestamp": fill.fill_timestamp,
        "decision_price": fill.decision_price,
        "slippage_bps": fill.slippage_bps,
        "implementation_shortfall": fill.implementation_shortfall,
    }


def event_to_db_dict(event: ExecutionEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "exec_run_id": event.exec_run_id,
        "symbol": event.symbol,
        "event_type": event.event_type,
        "message": event.message,
        "broker_order_id": event.broker_order_id,
        "intent_id": event.intent_id,
        "payload_json": event.payload_json,
        "created_at": event.created_at or datetime.now(timezone.utc),
    }

