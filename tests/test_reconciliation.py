"""Tests for execution_engine.reconciliation."""
from __future__ import annotations

from datetime import date

from execution_engine.models import ExecutionTarget
from execution_engine.reconciliation import reconcile_targets_vs_broker


def _target(sym: str, shares: int) -> ExecutionTarget:
    return ExecutionTarget(
        risk_run_id="r1", trade_date=date(2026, 4, 18), symbol=sym,
        target_shares=shares, entry_price=100.0, target_weight=0.05,
        sector=None, conviction_score=None, sizing_method=None, kelly_fraction=None,
    )


class TestReconciliation:
    def test_exact_match(self) -> None:
        targets = [_target("AAPL", 100)]
        positions = [{"symbol": "AAPL", "qty": 100}]
        diffs = reconcile_targets_vs_broker(targets, positions)
        assert len(diffs) == 1
        assert diffs[0].action == "none"

    def test_missing_broker_buy_more(self) -> None:
        targets = [_target("AAPL", 100)]
        diffs = reconcile_targets_vs_broker(targets, [])
        assert diffs[0].action == "buy_more"

    def test_excess_sell_excess(self) -> None:
        targets = [_target("AAPL", 50)]
        positions = [{"symbol": "AAPL", "qty": 100}]
        diffs = reconcile_targets_vs_broker(targets, positions)
        assert diffs[0].action == "sell_excess"

    def test_unexpected_investigate(self) -> None:
        positions = [{"symbol": "TSLA", "qty": 50}]
        diffs = reconcile_targets_vs_broker([], positions)
        assert diffs[0].action == "investigate"

    def test_tolerance(self) -> None:
        targets = [_target("AAPL", 100)]
        positions = [{"symbol": "AAPL", "qty": 102}]
        diffs = reconcile_targets_vs_broker(targets, positions, tolerance=5)
        assert diffs[0].action == "none"

    def test_empty_targets(self) -> None:
        diffs = reconcile_targets_vs_broker([], [])
        assert diffs == []
