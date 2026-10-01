"""Sprint 18-D : port OMS complet, doubles inertes et replay fail-closed."""

from __future__ import annotations

from dataclasses import replace

import pytest

from execution_engine.broker_doubles_18d import (
    MockBrokerAdapter,
    ReplayBrokerAdapter,
    ReplayMismatch,
)
from execution_engine.broker_router import ExecutionBrokerPort
from execution_engine.models import IntentRole, OrderIntent, OrderStatus


def _intent(name: str, *, role: str = IntentRole.ENTRY,
            side: str = "buy", qty: float = 100) -> OrderIntent:
    return OrderIntent(
        intent_id=name, risk_run_id="risk", exec_run_id="exec",
        symbol="AAPL", side=side, qty=qty, order_type="limit",
        limit_price=10, trail_percent=None, broker_mode="paper",
        parent_intent_id=None, intent_role=role,
        idempotency_key=name, decision_price=10,
    )


def test_mock_implements_full_port_without_network_or_automatic_fill() -> None:
    broker = MockBrokerAdapter(account={"equity": "10000", "cash": "9000"},
                               positions={"AAPL": {"symbol": "AAPL", "qty": "100"}},
                               prices={"AAPL": 10.25})
    assert isinstance(broker, ExecutionBrokerPort)
    order = broker.submit_intent(_intent("entry"))
    assert order.status == OrderStatus.SUBMITTED and order.filled_qty == 0
    assert broker.poll_order_status(order.broker_order_id, "entry") == order
    assert broker.get_account_equity() == 10000
    assert broker.get_latest_market_price("AAPL") == 10.25
    assert broker.get_position("AAPL") == {"symbol": "AAPL", "qty": "100"}
    raw = broker.list_recent_orders(status="open")
    assert broker.broker_order_from_api(raw[0], intent_id="entry").status == OrderStatus.SUBMITTED
    assert broker.cancel_all_open_orders(dry_run=True)[0].error == "dry_run"
    assert broker.poll_order_status(order.broker_order_id).status == OrderStatus.SUBMITTED
    assert broker.cancel_broker_order(order.broker_order_id)
    assert broker.poll_order_status(order.broker_order_id).status == OrderStatus.CANCELED
    assert broker.cancel_broker_order(order.broker_order_id) is False
    with pytest.raises(ReplayMismatch, match="déjà soumise"):
        broker.submit_intent(_intent("entry"))


def test_mock_oco_is_explicit_and_cancels_sibling_on_injected_fill() -> None:
    broker = MockBrokerAdapter()
    parent = _intent("parent")
    tp, stop = broker.submit_oco_protection(
        parent, _intent("tp", role=IntentRole.TAKE_PROFIT, side="sell"),
        _intent("stop", role=IntentRole.INITIAL_STOP, side="sell"),
    )
    assert tp.status == stop.status == OrderStatus.SUBMITTED
    broker.set_order_status(tp.broker_order_id, OrderStatus.FILLED,
                            filled_qty=100, avg_fill_price=11)
    assert broker.poll_order_status(stop.broker_order_id).status == OrderStatus.CANCELED
    with pytest.raises(ReplayMismatch, match="terminal"):
        broker.set_order_status(stop.broker_order_id, OrderStatus.FILLED,
                                filled_qty=100, avg_fill_price=9)


def test_replay_only_accepts_recorded_actions_and_observations() -> None:
    intent = _intent("entry")
    seed = MockBrokerAdapter()
    submitted = seed.submit_intent(intent)
    filled = replace(submitted, status=OrderStatus.FILLED,
                     filled_qty=100, avg_fill_price=10.1)
    replay = ReplayBrokerAdapter(
        submissions={intent.intent_id: submitted},
        polls={submitted.broker_order_id: (filled,)},
    )
    assert isinstance(replay, ExecutionBrokerPort)
    assert replay.submit_intent(intent) == submitted
    assert replay.poll_order_status(submitted.broker_order_id, "entry") == filled
    with pytest.raises(ReplayMismatch, match="épuisée"):
        replay.poll_order_status(submitted.broker_order_id, "entry")
    with pytest.raises(ReplayMismatch, match="absente"):
        replay.submit_intent(_intent("unrecorded"))
    with pytest.raises(ReplayMismatch, match="Annulation absente"):
        replay.cancel_broker_order(submitted.broker_order_id)
    with pytest.raises(ReplayMismatch, match="bande de polling"):
        replay.set_order_status(submitted.broker_order_id, OrderStatus.FILLED,
                                filled_qty=100, avg_fill_price=10.1)


def test_replay_rejects_foreign_order_identity() -> None:
    intent = _intent("entry")
    submitted = MockBrokerAdapter().submit_intent(intent)
    replay = ReplayBrokerAdapter(
        submissions={"entry": submitted},
        polls={submitted.broker_order_id: (replace(submitted, symbol="MSFT"),)},
    )
    replay.submit_intent(intent)
    with pytest.raises(ReplayMismatch, match="étrangère"):
        replay.poll_order_status(submitted.broker_order_id)
