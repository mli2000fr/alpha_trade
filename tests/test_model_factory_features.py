from __future__ import annotations

import numpy as np
import pandas as pd

from modelFactory import features

def test_features_importable():
    assert hasattr(features, "__doc__")


def test_build_target_prefers_adjusted_close_when_available() -> None:
    df = pd.DataFrame(
        {
            "close": [200.0, 202.0, 101.0, 102.0],
            "adj_close": [100.0, 101.0, 101.0, 102.0],
        }
    )

    target = features.build_target(df, horizon=1)

    assert target.iloc[0] == 1.0
    assert target.iloc[1] == 0.0
    assert target.iloc[2] == 1.0
    assert pd.isna(target.iloc[3])


def test_compute_features_absorbs_split_with_adjusted_prices() -> None:
    n = 90
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    adj_close = pd.Series(100.0 + np.arange(n), dtype=float)
    factor = pd.Series([0.5] * 45 + [1.0] * (n - 45), dtype=float)
    close = adj_close / factor

    df = pd.DataFrame(
        {
            "symbol": ["AAPL"] * n,
            "date": dates,
            "open": close * 0.99,
            "high": close * 1.01,
            "low": close * 0.98,
            "close": close,
            "volume": np.linspace(1_000_000, 1_100_000, n),
            "adj_close": adj_close,
            "vwap": close,
            "daily_return": 0.0,
            "is_filled": 0,
        }
    )

    result = features.compute_features(df)

    assert not result.empty
    assert result["daily_return"].abs().max() < 0.05


def test_build_target_swing_cash_creates_neutral_zone() -> None:
    df = pd.DataFrame(
        {
            "close": [100.0, 102.0, 101.0, 101.8, 101.7],
            "adj_close": [100.0, 102.0, 101.0, 101.8, 101.7],
        }
    )

    target = features.build_target(
        df,
        horizon=1,
        mode="swing_cash",
        positive_threshold=0.01,
        negative_threshold=-0.01,
    )

    assert target.iloc[0] == 1.0
    assert pd.isna(target.iloc[1])
    assert pd.isna(target.iloc[2])
    assert pd.isna(target.iloc[3])
    assert pd.isna(target.iloc[4])


