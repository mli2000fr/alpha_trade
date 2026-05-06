"""Phase C / S14.3 — Property-based tests sur CircuitBreaker."""
from __future__ import annotations

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from risk_management.circuit_breaker import CircuitBreaker, PnLSnapshot
from risk_management.config import RiskConfig


@settings(max_examples=200, deadline=None)
@given(
    equity=st.floats(min_value=10_000, max_value=1_000_000),
    hwm=st.floats(min_value=10_000, max_value=10_000_000),
    cur=st.floats(min_value=1, max_value=10_000_000),
    max_dd=st.floats(min_value=0.05, max_value=0.5),
)
def test_drawdown_trip_iff_dd_above_threshold(equity, hwm, cur, max_dd):
    cfg = RiskConfig(account_equity=equity, max_portfolio_drawdown_pct=max_dd)
    cb = CircuitBreaker(cfg, PnLSnapshot(portfolio_high_watermark=hwm,
                                          portfolio_current_value=cur))
    dd = (hwm - cur) / hwm if hwm > 0 else 0
    if dd >= max_dd:
        assert cb.is_active() is True
    # Le contraire n'est pas garanti (daily loss peut tripper aussi)


@settings(max_examples=200, deadline=None)
@given(
    equity=st.floats(min_value=10_000, max_value=1_000_000),
    daily=st.floats(min_value=-100_000, max_value=100_000),
    max_loss=st.floats(min_value=0.01, max_value=0.2),
)
def test_daily_loss_only_negative_pnl_can_trip(equity, daily, max_loss):
    cfg = RiskConfig(account_equity=equity, max_daily_loss_pct=max_loss)
    cb = CircuitBreaker(cfg, PnLSnapshot(daily_pnl=daily))
    if daily >= 0:
        assert cb.is_active() is False  # gain ne peut jamais tripper


def test_no_data_no_trip():
    cb = CircuitBreaker(RiskConfig())
    assert cb.is_active() is False

