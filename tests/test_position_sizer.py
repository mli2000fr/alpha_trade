"""Tests unitaires — PositionSizer."""
from __future__ import annotations

import pytest

from risk_management.config import RiskConfig
from risk_management.models import PriceInfo
from risk_management.position_sizer import PositionSizer


@pytest.fixture()
def config() -> RiskConfig:
    return RiskConfig(account_equity=100_000, risk_per_trade_pct=0.01, atr_stop_multiple=2.0, max_positions=10)


@pytest.fixture()
def sizer(config: RiskConfig) -> PositionSizer:
    return PositionSizer(config)


def test_atr_based_sizing(sizer: PositionSizer) -> None:
    pi = PriceInfo(symbol="AAPL", last_close=150.0, atr_20=5.0)
    result = sizer.compute(pi)
    # risk_budget = 100000 * 0.01 = 1000 ; risk_per_share = 5*2 = 10 ; shares = 100
    assert result.proposed_shares == 100
    assert result.method == "atr"


def test_equal_weight_fallback(sizer: PositionSizer) -> None:
    pi = PriceInfo(symbol="XYZ", last_close=50.0, atr_20=None)
    result = sizer.compute(pi)
    # weight = 1/10 = 0.10 ; notional = 10000 ; shares = 200
    assert result.proposed_shares == 200
    assert result.method == "equal_weight"


def test_zero_price_rejected(sizer: PositionSizer) -> None:
    pi = PriceInfo(symbol="BAD", last_close=0.0, atr_20=1.0)
    result = sizer.compute(pi)
    assert result.proposed_shares == 0
    assert result.method == "rejected"


def test_negative_price_rejected(sizer: PositionSizer) -> None:
    pi = PriceInfo(symbol="BAD", last_close=-5.0, atr_20=1.0)
    result = sizer.compute(pi)
    assert result.proposed_shares == 0


def test_very_high_atr_yields_few_shares(sizer: PositionSizer) -> None:
    pi = PriceInfo(symbol="VOL", last_close=600.0, atr_20=400.0)
    result = sizer.compute(pi)
    # risk_budget=1000, risk_per_share=800 => 1 share ; notional=600 > min_position_notional
    assert result.proposed_shares == 1


def test_below_min_position_notional_is_rejected(sizer: PositionSizer) -> None:
    pi = PriceInfo(symbol="SMALL", last_close=100.0, atr_20=250.0)

    result = sizer.compute(pi)

    assert result.proposed_shares == 0
    assert result.method == "rejected"

