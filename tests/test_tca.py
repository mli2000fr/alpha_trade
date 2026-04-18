"""Tests for execution_engine.tca."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from execution_engine.models import ExecutionFill
from execution_engine.tca import build_tca_summary, compute_implementation_shortfall, compute_slippage_bps


def _fill(fill_price: float = 150.5, decision_price: float = 150.0, qty: float = 100.0) -> ExecutionFill:
    slip = compute_slippage_bps(fill_price, decision_price)
    ishort = compute_implementation_shortfall(fill_price, decision_price, qty)
    return ExecutionFill(
        fill_id="f1", broker_order_id="b1", intent_id="i1", symbol="AAPL",
        filled_qty=qty, avg_fill_price=fill_price,
        fill_timestamp=datetime.now(timezone.utc),
        decision_price=decision_price, slippage_bps=slip, implementation_shortfall=ishort,
    )


class TestSlippage:
    def test_positive(self) -> None:
        assert compute_slippage_bps(150.5, 150.0) == pytest.approx(33.33, abs=0.1)

    def test_negative(self) -> None:
        assert compute_slippage_bps(149.5, 150.0) == pytest.approx(-33.33, abs=0.1)

    def test_zero(self) -> None:
        assert compute_slippage_bps(150.0, 150.0) == 0.0


class TestImplementationShortfall:
    def test_basic(self) -> None:
        assert compute_implementation_shortfall(150.5, 150.0, 100) == pytest.approx(50.0)


class TestTcaSummary:
    def test_counts_alerts(self) -> None:
        fills = [_fill(150.5, 150.0, 100), _fill(150.0, 150.0, 50)]
        summary = build_tca_summary(fills, max_slippage_bps=30)
        assert summary.total_filled == 2
        assert summary.slippage_alerts == 1  # first fill ~33 bps > 30

    def test_empty(self) -> None:
        summary = build_tca_summary([], max_slippage_bps=30)
        assert summary.total_filled == 0
