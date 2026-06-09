from datetime import date

import pytest

from execution_engine import reconciliation
from execution_engine.models import ExecutionPosition, ExecutionTarget, ReconciliationStatus


def _target(symbol: str = "AAPL", shares: float = 100, entry_price: float = 150.0) -> ExecutionTarget:
    return ExecutionTarget(
        risk_run_id="risk-1",
        trade_date=date(2026, 4, 26),
        symbol=symbol,
        target_shares=shares,
        entry_price=entry_price,
        target_weight=0.05,
        sector="Tech",
        conviction_score=0.8,
        sizing_method="atr",
        kelly_fraction=0.1,
    )


def test_reconciliation_importable():
    assert hasattr(reconciliation, "__doc__")


def test_reconcile_execution_state_marks_open_order_gap_as_manual_review() -> None:
    results = reconciliation.reconcile_execution_state(
        exec_run_id="exec-1",
        account_id="acct-1",
        targets=[_target()],
        broker_positions=[{"symbol": "AAPL", "qty": 80}],
        internal_positions=[ExecutionPosition(account_id="acct-1", symbol="AAPL", net_qty=80)],
        open_order_state=[{"symbol": "AAPL", "open_request_buy_qty": 20.0, "open_request_sell_qty": 0.0, "open_broker_buy_qty": 20.0, "open_broker_sell_qty": 0.0}],
        protection_state=[{"symbol": "AAPL", "protection_qty": 80.0}],
        tolerance=0,
        buying_power_available=100_000.0,
    )

    assert results[0].action == "buy_more"
    assert results[0].reconciliation_status == ReconciliationStatus.MANUAL_REVIEW
    assert results[0].reason_code == "open_orders_in_flight"


def test_reconcile_execution_state_blocks_missing_protection() -> None:
    results = reconciliation.reconcile_execution_state(
        exec_run_id="exec-1",
        account_id="acct-1",
        targets=[_target()],
        broker_positions=[{"symbol": "AAPL", "qty": 100}],
        internal_positions=[ExecutionPosition(account_id="acct-1", symbol="AAPL", net_qty=100)],
        open_order_state=[],
        protection_state=[],
        tolerance=0,
        buying_power_available=100_000.0,
    )

    assert results[0].action == "none"
    assert results[0].reconciliation_status == ReconciliationStatus.BLOCKED
    assert results[0].reason_code == "missing_protection"


def test_reconcile_execution_state_marks_external_symbol_for_manual_review() -> None:
    results = reconciliation.reconcile_execution_state(
        exec_run_id="exec-1",
        account_id="acct-1",
        targets=[_target(symbol="AAPL")],
        broker_positions=[{"symbol": "MSFT", "qty": 12}],
        internal_positions=[ExecutionPosition(account_id="acct-1", symbol="MSFT", net_qty=12)],
        open_order_state=[],
        protection_state=[{"symbol": "MSFT", "protection_qty": 12.0}],
        tolerance=0,
        buying_power_available=100_000.0,
    )

    msft = next(result for result in results if result.symbol == "MSFT")
    assert msft.action == "investigate"
    assert msft.reconciliation_status == ReconciliationStatus.MANUAL_REVIEW


def test_reconcile_execution_state_blocks_insufficient_buying_power() -> None:
    results = reconciliation.reconcile_execution_state(
        exec_run_id="exec-1",
        account_id="acct-1",
        targets=[_target(entry_price=150.0)],
        broker_positions=[{"symbol": "AAPL", "qty": 80}],
        internal_positions=[ExecutionPosition(account_id="acct-1", symbol="AAPL", net_qty=80)],
        open_order_state=[],
        protection_state=[{"symbol": "AAPL", "protection_qty": 80.0}],
        tolerance=0,
        buying_power_available=1_000.0,
    )

    assert results[0].action == "buy_more"
    assert results[0].reconciliation_status == ReconciliationStatus.BLOCKED
    assert results[0].reason_code == "insufficient_buying_power"


def test_reconcile_execution_state_marks_clear_shortfall_as_safe_auto() -> None:
    results = reconciliation.reconcile_execution_state(
        exec_run_id="exec-1",
        account_id="acct-1",
        targets=[_target(entry_price=150.0)],
        broker_positions=[{"symbol": "AAPL", "qty": 80}],
        internal_positions=[ExecutionPosition(account_id="acct-1", symbol="AAPL", net_qty=80)],
        open_order_state=[],
        protection_state=[{"symbol": "AAPL", "protection_qty": 80.0}],
        tolerance=0,
        buying_power_available=10_000.0,
    )

    assert results[0].action == "buy_more"
    assert results[0].reconciliation_status == ReconciliationStatus.SAFE_AUTO
    assert results[0].reason_code is None


def test_reconcile_execution_state_marks_sell_excess_with_internal_mismatch() -> None:
    results = reconciliation.reconcile_execution_state(
        exec_run_id="exec-2",
        account_id="acct-1",
        targets=[_target(entry_price=150.0)],
        broker_positions=[{"symbol": " aapl ", "qty": 120}],
        internal_positions=[ExecutionPosition(account_id="acct-1", symbol="AAPL", net_qty=80)],
        open_order_state=[],
        protection_state=[{"symbol": "AAPL", "protection_qty": 120.0}],
        tolerance=0,
        buying_power_available=100_000.0,
    )

    assert results[0].symbol == "AAPL"
    assert results[0].action == "sell_excess"
    assert results[0].reconciliation_status == ReconciliationStatus.MANUAL_REVIEW
    assert results[0].reason_code == "internal_position_mismatch"


def test_reconcile_targets_vs_broker_returns_legacy_diff_projection() -> None:
    diffs = reconciliation.reconcile_targets_vs_broker(
        targets=[_target(symbol="AAPL", shares=10, entry_price=100.0)],
        broker_positions=[{"symbol": "AAPL", "qty": 8}],
        tolerance=0,
    )

    assert len(diffs) == 1
    assert diffs[0].symbol == "AAPL"
    assert diffs[0].target_qty == 10
    assert diffs[0].broker_qty == 8.0
    assert diffs[0].delta == -2.0
    assert diffs[0].action == "buy_more"


def test_reconcile_execution_state_respects_fractional_tolerance() -> None:
    results = reconciliation.reconcile_execution_state(
        exec_run_id="exec-frac-1",
        account_id="acct-1",
        targets=[_target(shares=0.333333333)],
        broker_positions=[{"symbol": "AAPL", "qty": 0.333333334}],
        internal_positions=[ExecutionPosition(account_id="acct-1", symbol="AAPL", net_qty=0.333333334)],
        open_order_state=[],
        protection_state=[{"symbol": "AAPL", "protection_qty": 0.333333334}],
        tolerance=1e-6,
        buying_power_available=100_000.0,
    )

    assert results[0].action == "none"
    assert results[0].reconciliation_status == ReconciliationStatus.SAFE_AUTO
    assert results[0].reason_code is None


def test_reconcile_execution_state_flags_fractional_shortfall_above_tolerance() -> None:
    results = reconciliation.reconcile_execution_state(
        exec_run_id="exec-frac-2",
        account_id="acct-1",
        targets=[_target(shares=0.75)],
        broker_positions=[{"symbol": "AAPL", "qty": 0.25}],
        internal_positions=[ExecutionPosition(account_id="acct-1", symbol="AAPL", net_qty=0.25)],
        open_order_state=[],
        protection_state=[{"symbol": "AAPL", "protection_qty": 0.25}],
        tolerance=1e-6,
        buying_power_available=100_000.0,
    )

    assert results[0].action == "buy_more"
    assert results[0].position_delta == pytest.approx(-0.5)
    assert results[0].reconciliation_status == ReconciliationStatus.SAFE_AUTO


def test_reconcile_targets_vs_broker_keeps_fractional_target_qty() -> None:
    diffs = reconciliation.reconcile_targets_vs_broker(
        targets=[_target(symbol="AAPL", shares=0.5, entry_price=100.0)],
        broker_positions=[{"symbol": "AAPL", "qty": 0.25}],
        tolerance=1e-6,
    )

    assert len(diffs) == 1
    assert diffs[0].target_qty == pytest.approx(0.5)
    assert diffs[0].broker_qty == pytest.approx(0.25)
    assert diffs[0].delta == pytest.approx(-0.25)


