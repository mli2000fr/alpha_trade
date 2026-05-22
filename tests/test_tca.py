"""Tests for execution_engine.tca."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
import pandas as pd
from execution_engine.models import ExecutionFill
from execution_engine.tca import (
    bucket_slippage_bps,
    build_tca_aggregate_frame,
    build_tca_summary,
    compute_implementation_shortfall,
    compute_slippage_bps,
)


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


def test_bucket_slippage_bps_uses_absolute_ranges() -> None:
    assert bucket_slippage_bps(-5.0) == "0-10 bps"
    assert bucket_slippage_bps(12.0) == "10-25 bps"
    assert bucket_slippage_bps(35.0) == "25-50 bps"
    assert bucket_slippage_bps(88.0) == "> 50 bps"


def test_build_tca_aggregate_frame_groups_by_month_and_bucket() -> None:
    fills = pd.DataFrame(
        {
            "account_id": ["acct-1", "acct-1", "acct-1"],
            "exec_run_id": ["exec-1", "exec-1", "exec-2"],
            "symbol": ["AAPL", "MSFT", "AAPL"],
            "filled_qty": [10.0, 5.0, 8.0],
            "avg_fill_price": [100.0, 200.0, 110.0],
            "fill_timestamp": pd.to_datetime([
                "2026-05-05T10:00:00Z",
                "2026-05-06T10:00:00Z",
                "2026-06-01T10:00:00Z",
            ]),
            "slippage_bps": [8.0, 22.0, 60.0],
            "implementation_shortfall": [1.0, 2.5, 6.0],
        }
    )

    monthly = build_tca_aggregate_frame(fills, group_by=("account_id", "month"))
    by_bucket = build_tca_aggregate_frame(fills, group_by=("account_id", "slippage_bucket"))

    assert monthly["month"].tolist() == ["2026-06", "2026-05"]
    may_row = monthly[monthly["month"] == "2026-05"].iloc[0]
    assert may_row["fill_count"] == 2
    assert may_row["total_notional"] == pytest.approx(2000.0)
    assert may_row["total_implementation_shortfall"] == pytest.approx(3.5)

    assert set(by_bucket["slippage_bucket"].tolist()) == {"0-10 bps", "10-25 bps", "> 50 bps"}

