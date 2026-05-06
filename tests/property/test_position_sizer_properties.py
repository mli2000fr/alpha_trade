"""Phase C / S14.3 — Property-based tests (hypothesis) sur PositionSizer."""
from __future__ import annotations

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from risk_management.config import RiskConfig
from risk_management.models import PriceInfo
from risk_management.position_sizer import PositionSizer


@settings(max_examples=200, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(
    equity=st.floats(min_value=10_000, max_value=10_000_000, allow_nan=False),
    price=st.floats(min_value=0.5, max_value=5_000.0, allow_nan=False),
    atr=st.floats(min_value=0.01, max_value=500.0, allow_nan=False),
    risk_pct=st.floats(min_value=0.001, max_value=0.05, allow_nan=False),
    atr_mult=st.floats(min_value=0.5, max_value=5.0, allow_nan=False),
    min_notional=st.floats(min_value=0.0, max_value=5_000.0, allow_nan=False),
)
def test_position_sizer_invariants(equity, price, atr, risk_pct, atr_mult, min_notional):
    cfg = RiskConfig(
        account_equity=equity,
        risk_per_trade_pct=risk_pct,
        atr_stop_multiple=atr_mult,
        min_position_notional=min_notional,
    )
    sizer = PositionSizer(cfg)
    info = PriceInfo(symbol="X", last_close=price, atr_20=atr)
    res = sizer.compute(info)

    # Inv1 : shares >= 0
    assert res.proposed_shares >= 0
    # Inv2 : si accepté, le risque réel <= budget de risque (à 1 share près)
    if res.proposed_shares > 0:
        risk_budget = equity * risk_pct
        actual_risk = res.proposed_shares * atr * atr_mult
        assert actual_risk <= risk_budget + (atr * atr_mult)
        # Inv3 : si accepté, notional >= min_notional
        assert res.proposed_shares * price >= min_notional
        assert res.method == "atr"
    else:
        assert res.method.startswith("rejected_")


@given(
    price=st.floats(min_value=-100.0, max_value=0.0, allow_nan=False),
    atr=st.floats(min_value=0.01, max_value=10.0, allow_nan=False),
)
def test_invalid_price_always_rejected(price, atr):
    cfg = RiskConfig()
    sizer = PositionSizer(cfg)
    res = sizer.compute(PriceInfo(symbol="X", last_close=price, atr_20=atr))
    assert res.proposed_shares == 0
    assert res.method == "rejected_invalid_price"


@given(
    equity=st.floats(min_value=10_000, max_value=1_000_000, allow_nan=False),
    price=st.floats(min_value=1.0, max_value=500.0, allow_nan=False),
)
def test_missing_atr_always_rejected(equity, price):
    cfg = RiskConfig(account_equity=equity)
    sizer = PositionSizer(cfg)
    res = sizer.compute(PriceInfo(symbol="X", last_close=price, atr_20=None))
    assert res.proposed_shares == 0
    assert res.method == "rejected_atr_missing"

