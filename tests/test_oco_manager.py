"""Tests for execution_engine.oco_manager."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from execution_engine.models import BrokerOrder, EventType, IntentRole, OrderIntent, OrderStatus
from execution_engine.oco_manager import OcoManager


def _intent(role: str = IntentRole.TAKE_PROFIT, parent_id: str = "p1") -> OrderIntent:
    return OrderIntent(
        intent_id="tp1" if role == IntentRole.TAKE_PROFIT else "ts1",
        risk_run_id="r1", exec_run_id="e1", symbol="AAPL", side="sell",
        qty=100, order_type="limit", limit_price=162.0, trail_percent=None,
        broker_mode="paper", parent_intent_id=parent_id, intent_role=role,
        idempotency_key="key1", decision_price=150.0,
    )


def _broker_order(intent_id: str, status: str = OrderStatus.SUBMITTED) -> BrokerOrder:
    return BrokerOrder(
        broker_order_id=f"bo_{intent_id}", client_order_id="c1", intent_id=intent_id,
        symbol="AAPL", side="sell", qty=100, filled_qty=0, avg_fill_price=None,
        status=status, order_type="limit", limit_price=162.0, stop_price=None,
        trail_percent=None, created_at=None, updated_at=None,
    )


class TestOcoManager:
    def test_cancel_sibling_when_tp_filled(self) -> None:
        broker = MagicMock()
        repo = MagicMock()
        repo.load_open_child_orders.return_value = [_broker_order("ts1")]
        broker.cancel_broker_order.return_value = True
        oco = OcoManager(broker, repo)
        events = oco.check_and_cancel_sibling(_intent(IntentRole.TAKE_PROFIT), "e1")
        assert len(events) == 1
        assert events[0].event_type == EventType.OCO_CANCEL_TRIGGERED
        broker.cancel_broker_order.assert_called_once()

    def test_no_cancel_when_no_sibling(self) -> None:
        broker = MagicMock()
        repo = MagicMock()
        repo.load_open_child_orders.return_value = []
        oco = OcoManager(broker, repo)
        events = oco.check_and_cancel_sibling(_intent(), "e1")
        assert events == []

    def test_no_cancel_when_both_open(self) -> None:
        broker = MagicMock()
        repo = MagicMock()
        # Only the filled intent itself is returned (same intent_id), skip
        filled = _intent(IntentRole.TAKE_PROFIT)
        repo.load_open_child_orders.return_value = [_broker_order(filled.intent_id)]
        oco = OcoManager(broker, repo)
        events = oco.check_and_cancel_sibling(filled, "e1")
        assert events == []

    def test_no_cancel_when_no_parent(self) -> None:
        broker = MagicMock()
        repo = MagicMock()
        intent = OrderIntent(
            intent_id="i1", risk_run_id="r1", exec_run_id="e1", symbol="AAPL",
            side="buy", qty=100, order_type="market", limit_price=None,
            trail_percent=None, broker_mode="paper", parent_intent_id=None,
            intent_role=IntentRole.ENTRY, idempotency_key="k1", decision_price=150.0,
        )
        oco = OcoManager(broker, repo)
        events = oco.check_and_cancel_sibling(intent, "e1")
        assert events == []
