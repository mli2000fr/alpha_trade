from __future__ import annotations

import pandas as pd
import pytest

from selector.strict_filter_profiles import STRICT_SWING_CASH_FILTERS, StrictFilterProfile


def test_strict_filter_profile_validates_positive_thresholds() -> None:
    with pytest.raises(ValueError, match="min_close"):
        StrictFilterProfile("bad", min_close=0.0, min_avg_dollar_volume_20d=30_000_000.0, max_volatility_ratio=0.9)


def test_strict_filter_profile_exports_scanner_and_backtest_keys() -> None:
    expected_optional = {
        "min_relative_strength_index": 100.0,
        "min_high_52w_proximity": 0.75,
        "min_weekly_trend_score": 1.0,
        "min_atr_pct_20": 0.015,
        "max_atr_pct_20": 0.06,
        "min_market_cap": 2_000_000_000.0,
        "min_beta_126": 0.8,
        "max_spread_bps": 40.0,
        "earnings_blackout_days": 3,
    }
    assert STRICT_SWING_CASH_FILTERS.to_backtest_filter_dict() == {
        "min_close": 10.0,
        "min_avg_dollar_volume_20d": 30_000_000.0,
        "max_volatility_ratio": 0.9,
        "require_above_ma200": True,
        **expected_optional,
    }
    assert STRICT_SWING_CASH_FILTERS.to_scanner_config_kwargs() == {
        "min_close": 10.0,
        "liquidity_threshold": 30_000_000.0,
        "max_volatility_ratio": 0.9,
        "require_above_ma200": True,
        **expected_optional,
    }


def test_strict_filter_profile_applies_shared_thresholds_to_frame() -> None:
    base_columns = {
        "relative_strength_index": 110.0,
        "high_52w": 14.0,
        "weekly_trend_score": 1.0,
        "atr_pct_20": 0.03,
        "ma200": 5.0,
        "market_cap": 5_000_000_000.0,
        "beta_126": 1.2,
        "spread_bps": 10.0,
        "earnings_blackout": 0,
    }
    rows = [
        {"symbol": "PASS", "latest_close": 12.0, "avg_dollar_volume_20d": 35_000_000.0,
         "volatility_ratio": 0.7, **base_columns},
        {"symbol": "LOWP", "latest_close": 9.5, "avg_dollar_volume_20d": 35_000_000.0,
         "volatility_ratio": 0.7, **base_columns},
        {"symbol": "SPIKE", "latest_close": 15.0, "avg_dollar_volume_20d": 35_000_000.0,
         "volatility_ratio": 1.05, **base_columns},
    ]
    frame = pd.DataFrame(rows)

    filtered = STRICT_SWING_CASH_FILTERS.apply_to_frame(frame)

    assert list(filtered["symbol"]) == ["PASS"]

