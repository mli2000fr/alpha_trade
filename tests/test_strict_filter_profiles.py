from __future__ import annotations

import pandas as pd
import pytest

from selector.strict_filter_profiles import STRICT_SWING_CASH_FILTERS, StrictFilterProfile


def test_strict_filter_profile_validates_positive_thresholds() -> None:
    with pytest.raises(ValueError, match="min_close"):
        StrictFilterProfile("bad", min_close=0.0, min_avg_dollar_volume_20d=30_000_000.0, max_volatility_ratio=0.9)


def test_strict_filter_profile_exports_scanner_and_backtest_keys() -> None:
    assert STRICT_SWING_CASH_FILTERS.to_backtest_filter_dict() == {
        "min_close": 10.0,
        "min_avg_dollar_volume_20d": 30_000_000.0,
        "max_volatility_ratio": 0.9,
    }
    assert STRICT_SWING_CASH_FILTERS.to_scanner_config_kwargs() == {
        "min_close": 10.0,
        "liquidity_threshold": 30_000_000.0,
        "max_volatility_ratio": 0.9,
    }


def test_strict_filter_profile_applies_shared_thresholds_to_frame() -> None:
    frame = pd.DataFrame(
        [
            {
                "symbol": "PASS",
                "latest_close": 12.0,
                "avg_dollar_volume_20d": 35_000_000.0,
                "volatility_ratio": 0.7,
            },
            {
                "symbol": "LOWP",
                "latest_close": 9.5,
                "avg_dollar_volume_20d": 35_000_000.0,
                "volatility_ratio": 0.7,
            },
            {
                "symbol": "SPIKE",
                "latest_close": 15.0,
                "avg_dollar_volume_20d": 35_000_000.0,
                "volatility_ratio": 1.05,
            },
        ]
    )

    filtered = STRICT_SWING_CASH_FILTERS.apply_to_frame(frame)

    assert list(filtered["symbol"]) == ["PASS"]

