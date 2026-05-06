"""Sprint S13.3 — Le ``MockBroker`` doit être 100 % déterministe."""
from __future__ import annotations

from decimal import Decimal

import pytest

from core.broker_models import OrderRequest
from service.mock_broker import MockBroker


def _run_scenario(seed: int) -> list[str]:
    b = MockBroker(seed=seed)
    ids: list[str] = []
    for sym, qty in (("AAPL", 5), ("MSFT", 3), ("AAPL", 2)):
        snap = b.submit_order(OrderRequest(symbol=sym, qty=Decimal(qty), side="buy"))
        ids.append(snap.order_id)
    return ids


def test_same_seed_produces_same_order_ids():
    assert _run_scenario(42) == _run_scenario(42)


def test_different_seeds_diverge():
    a = _run_scenario(1)
    b = _run_scenario(2)
    # order_id contient le seed → divergent
    assert a != b


def test_cancel_returns_false_when_already_filled():
    b = MockBroker(seed=10)
    snap = b.submit_order(OrderRequest(symbol="X", qty=Decimal("1"), side="buy"))
    assert snap.status == "filled"
    assert b.cancel_order(snap.order_id) is False


def test_cancel_open_order_when_auto_fill_disabled():
    b = MockBroker(seed=10, auto_fill=False)
    snap = b.submit_order(OrderRequest(symbol="X", qty=Decimal("1"), side="buy"))
    assert snap.status == "accepted"
    assert b.cancel_order(snap.order_id) is True
    again = b.get_orders(status="canceled")
    assert any(o.order_id == snap.order_id for o in again)


def test_stream_trades_invoked_on_submit():
    b = MockBroker(seed=10)
    received = []
    with b.stream_trades(received.append):
        b.submit_order(OrderRequest(symbol="Y", qty=Decimal("2"), side="buy"))
    assert len(received) == 1
    assert received[0].symbol == "Y"


def test_get_orders_filters_by_status():
    b = MockBroker(seed=10, auto_fill=False)
    b.submit_order(OrderRequest(symbol="A", qty=Decimal("1"), side="buy"))
    accepted = b.get_orders(status="accepted")
    filled = b.get_orders(status="filled")
    assert len(accepted) == 1 and len(filled) == 0

