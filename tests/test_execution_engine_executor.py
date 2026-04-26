from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from execution_engine import executor as executor_module
from execution_engine.config import ExecutionConfig
from execution_engine.executor import ProductionExecutor, _AccountConstraintState
from execution_engine.models import BrokerOrder, EventType, OrderIntent, OrderStatus


def _make_parent_intent() -> OrderIntent:
    return OrderIntent(
        intent_id="intent-parent",
        risk_run_id="risk-1",
        exec_run_id="exec-1",
        symbol="AAPL",
        side="buy",
        qty=10.0,
        order_type="market",
        limit_price=None,
        trail_percent=None,
        broker_mode="paper",
        parent_intent_id=None,
        intent_role="entry",
        idempotency_key="idem-parent",
        decision_price=150.0,
    )


def _make_order(*, status: str, filled_qty: float = 10.0, avg_fill_price: float | None = 151.0) -> BrokerOrder:
    now = datetime.now(timezone.utc)
    return BrokerOrder(
        broker_order_id=f"broker-{status.lower()}",
        client_order_id=f"client-{status.lower()}",
        intent_id="intent-parent",
        symbol="AAPL",
        side="buy",
        qty=10.0,
        filled_qty=filled_qty,
        avg_fill_price=avg_fill_price,
        status=status,
        order_type="market",
        limit_price=None,
        stop_price=None,
        trail_percent=None,
        created_at=now,
        updated_at=now,
    )


def _make_executor(config: ExecutionConfig | None = None) -> tuple[ProductionExecutor, MagicMock, MagicMock, MagicMock]:
    cfg = config or ExecutionConfig(dry_run=False, allow_outside_rth=True, inter_order_delay_ms=0, poll_interval_seconds=0.01)
    repo = MagicMock()
    broker = MagicMock()
    broker.get_account_snapshot.return_value = {
        "equity": 100_000.0,
        "cash": 100_000.0,
        "buying_power": 200_000.0,
        "non_marginable_buying_power": 100_000.0,
        "daytrade_count": 0,
    }
    oco = MagicMock()
    return ProductionExecutor(cfg, repo, broker, oco), repo, broker, oco


def test_build_fill_uses_decision_price_when_avg_fill_missing() -> None:
    executor, _, _, _ = _make_executor()
    intent = _make_parent_intent()
    order = _make_order(status=OrderStatus.FILLED, avg_fill_price=None)

    fill = executor._build_fill(order, intent)

    assert fill.avg_fill_price == 150.0
    assert fill.slippage_bps == pytest.approx(0.0)
    assert fill.implementation_shortfall == pytest.approx(0.0)


def test_poll_until_terminal_returns_filled_order_after_retry(monkeypatch) -> None:
    executor, _, broker, _ = _make_executor(ExecutionConfig(dry_run=False, allow_outside_rth=True, fill_timeout_seconds=1, poll_interval_seconds=0.01, inter_order_delay_ms=0))
    broker.poll_order_status.side_effect = [
        _make_order(status=OrderStatus.SUBMITTED, filled_qty=0.0),
        _make_order(status=OrderStatus.FILLED),
    ]
    clock = iter([0.0, 0.1, 0.2])
    monkeypatch.setattr(executor_module.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(executor_module.time, "sleep", lambda _: None)

    result = executor._poll_until_terminal("broker-order", "intent-parent", "exec-1")

    assert result is not None
    assert result.status == OrderStatus.FILLED
    assert broker.poll_order_status.call_count == 2


def test_poll_until_terminal_returns_none_after_timeout(monkeypatch) -> None:
    executor, _, broker, _ = _make_executor(ExecutionConfig(dry_run=False, allow_outside_rth=True, fill_timeout_seconds=1, poll_interval_seconds=0.01, inter_order_delay_ms=0))
    broker.poll_order_status.return_value = _make_order(status=OrderStatus.SUBMITTED, filled_qty=0.0)
    clock = iter([0.0, 0.2, 0.4, 1.5])
    monkeypatch.setattr(executor_module.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(executor_module.time, "sleep", lambda _: None)

    result = executor._poll_until_terminal("broker-order", "intent-parent", "exec-1")

    assert result is None
    assert broker.poll_order_status.call_count == 2


def test_submit_children_submits_take_profit_and_fallback_trailing_without_target_risk() -> None:
    executor, repo, broker, _ = _make_executor()
    parent = _make_parent_intent()
    filled_order = _make_order(status=OrderStatus.FILLED, filled_qty=10.0, avg_fill_price=151.0)
    broker.submit_intent.side_effect = [
        _make_order(status=OrderStatus.SUBMITTED, filled_qty=0.0),
        _make_order(status=OrderStatus.SUBMITTED, filled_qty=0.0),
    ]

    account_state = _AccountConstraintState(
        account_type="margin",
        effective_pdt_rule="off",
        pdt_limited=False,
        swing_only=False,
        equity=100_000.0,
        buying_power_available=200_000.0,
        settled_cash_available=100_000.0,
        daytrade_count=0,
        remaining_day_trade_slots=0,
    )

    events = executor._submit_children(parent, filled_order, exec_run_id="exec-1", account_state=account_state, metrics={"children_deferred": 0})

    assert broker.submit_intent.call_count == 2
    submitted_children = [call.args[0] for call in broker.submit_intent.call_args_list]
    assert submitted_children[0].intent_role == "take_profit"
    assert submitted_children[1].intent_role == "trailing_stop"
    assert repo.upsert_execution_order.call_count == 2
    assert len(events) == 1
    assert events[0].event_type == EventType.CHILDREN_SUBMITTED


def test_submit_children_skips_when_fill_quantity_is_zero() -> None:
    executor, repo, broker, _ = _make_executor()
    parent = _make_parent_intent()
    unfilled_order = _make_order(status=OrderStatus.SUBMITTED, filled_qty=0.0)
    account_state = _AccountConstraintState(
        account_type="margin",
        effective_pdt_rule="off",
        pdt_limited=False,
        swing_only=False,
        equity=100_000.0,
        buying_power_available=200_000.0,
        settled_cash_available=100_000.0,
        daytrade_count=0,
        remaining_day_trade_slots=0,
    )

    events = executor._submit_children(parent, unfilled_order, exec_run_id="exec-1", account_state=account_state, metrics={"children_deferred": 0})

    assert events == []
    broker.submit_intent.assert_not_called()
    repo.upsert_execution_order.assert_not_called()


def test_build_account_constraint_state_uses_simulated_margin_multiplier_in_dry_run() -> None:
    executor, _, _, _ = _make_executor(
        ExecutionConfig(
            dry_run=True,
            allow_outside_rth=True,
            account_type="margin",
            simulated_account_equity=2_000.0,
            simulated_margin_buying_power_multiplier=2.0,
        )
    )

    state = executor._build_account_constraint_state()

    assert state.buying_power_available == 4_000.0
    assert state.settled_cash_available == 2_000.0


def test_should_defer_children_for_swing_only() -> None:
    executor, _, _, _ = _make_executor()
    state = _AccountConstraintState(
        account_type="margin",
        effective_pdt_rule="off",
        pdt_limited=False,
        swing_only=True,
        equity=2_000.0,
        buying_power_available=4_000.0,
        settled_cash_available=2_000.0,
        daytrade_count=0,
        remaining_day_trade_slots=0,
    )

    defer, reason = executor._should_defer_children(state)

    assert defer is True
    assert reason == "swing_only"


