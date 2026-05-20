"""Tests unitaires — KellySizer V2."""
from __future__ import annotations

import pytest

from risk_management.config import RiskConfig
from risk_management.kelly import KellySizer
from risk_management.models import PriceInfo


def _kelly_cfg(**overrides) -> RiskConfig:  # type: ignore[no-untyped-def]
    defaults = {
        "account_equity": 100_000,
        "risk_per_trade_pct": 0.01,
        "atr_stop_multiple": 2.0,
        "max_positions": 10,
        "max_position_weight": 0.10,
        "min_position_notional": 500.0,
        "enable_kelly_sizing": True,
        "assumed_payoff_ratio": 1.5,
        "kelly_fraction_multiplier": 0.25,
        "min_effective_probability": 0.52,
        "default_win_rate": 0.55,
        "prediction_confidence_weight": 0.60,
        "historical_win_rate_weight": 0.40,
    }
    defaults.update(overrides)
    return RiskConfig(**defaults)


@pytest.mark.unit
def test_kelly_positive_with_atr() -> None:
    cfg = _kelly_cfg()
    sizer = KellySizer(cfg)
    pi = PriceInfo("AAPL", 150.0, 5.0)
    result = sizer.compute(pi, predicted_proba=0.70, historical_win_rate=0.58)
    assert result.method == "kelly_atr"
    assert result.proposed_shares >= 1


@pytest.mark.unit
def test_kelly_positive_without_atr() -> None:
    cfg = _kelly_cfg()
    sizer = KellySizer(cfg)
    pi = PriceInfo("AAPL", 150.0, None)
    result = sizer.compute(pi, predicted_proba=0.70, historical_win_rate=0.58)
    assert result.method == "kelly_only"
    assert result.proposed_shares >= 1


@pytest.mark.unit
def test_kelly_negative_fallback_atr() -> None:
    cfg = _kelly_cfg(min_effective_probability=0.52)
    sizer = KellySizer(cfg)
    pi = PriceInfo("AAPL", 150.0, 5.0)
    # p_eff ~0.40 → below min_effective_probability → fallback to V1 ATR
    result = sizer.compute(pi, predicted_proba=0.35, historical_win_rate=0.35)
    assert result.method == "atr"


@pytest.mark.unit
def test_kelly_disabled_uses_v1_sizer() -> None:
    from risk_management.position_sizer import PositionSizer
    cfg = _kelly_cfg(enable_kelly_sizing=False)
    # Use PositionSizer directly (KellySizer not created when disabled)
    sizer = PositionSizer(cfg)
    pi = PriceInfo("AAPL", 150.0, 5.0)
    result = sizer.compute(pi)
    assert result.method in ("atr", "equal_weight")


@pytest.mark.unit
def test_kelly_capped_by_max_position_weight() -> None:
    # Very high kelly_fraction_multiplier to force clipping
    cfg = _kelly_cfg(kelly_fraction_multiplier=1.0, max_position_weight=0.05)
    sizer = KellySizer(cfg)
    pi = PriceInfo("AAPL", 10.0, 0.5)
    result = sizer.compute(pi, predicted_proba=0.90, historical_win_rate=0.80)
    # max notional = 100000 * 0.05 = 5000, shares = 5000/10 = 500
    assert result.proposed_shares <= 500
    assert result.proposed_shares >= 1


@pytest.mark.unit
def test_kelly_min_notional_rejection() -> None:
    cfg = _kelly_cfg(min_position_notional=50_000.0, kelly_fraction_multiplier=0.01)
    sizer = KellySizer(cfg)
    pi = PriceInfo("AAPL", 150.0, 5.0)
    result = sizer.compute(pi, predicted_proba=0.55, historical_win_rate=0.55)
    assert result.proposed_shares == 0
    assert result.method == "rejected_notional"


@pytest.mark.unit
def test_fallback_equal_weight_when_no_data() -> None:
    cfg = _kelly_cfg()
    sizer = KellySizer(cfg)
    pi = PriceInfo("XYZ", 50.0, None)
    # default_win_rate=0.55 for both → p_eff=0.55 >= 0.52
    # Kelly = 0.55 - 0.45/1.5 = 0.55 - 0.30 = 0.25 → frac = 0.25*0.25 = 0.0625
    # notional = 100000*0.0625 = 6250 → shares = 125 → kelly_only
    result = sizer.compute(pi, predicted_proba=None, historical_win_rate=None)
    assert result.method == "kelly_only"
    assert result.proposed_shares >= 1


@pytest.mark.unit
def test_kelly_atr_cap_uses_risk_multiplier() -> None:
    cfg = _kelly_cfg(risk_multiplier=0.5, max_position_weight=0.5)
    sizer = KellySizer(cfg)
    pi = PriceInfo("AAPL", 100.0, 2.0)

    result = sizer.compute(pi, predicted_proba=0.90, historical_win_rate=0.80)

    # Kelly très favorable, mais cap ATR piloté par risk_multiplier :
    # budget = 100_000 * 1% * 0.5 = 500 ; risk/share = 2*2 = 4 ; cap = 125.
    assert result.method == "kelly_atr"
    assert result.proposed_shares == 125


@pytest.mark.unit
def test_kelly_uses_effective_min_notional_for_rejection() -> None:
    cfg = _kelly_cfg(
        account_equity=2_000.0,
        min_position_notional=10.0,
        enforce_min_notional=500.0,
    )
    sizer = KellySizer(cfg)
    pi = PriceInfo("AAPL", 100.0, None)

    result = sizer.compute(pi, predicted_proba=0.55, historical_win_rate=0.55)

    assert result.proposed_shares == 0
    assert result.method == "rejected_notional_below_enforced"


