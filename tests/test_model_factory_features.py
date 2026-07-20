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


def test_compute_features_expert_adds_trend_relative_strength_and_regime() -> None:
    n = 260
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    close = pd.Series(np.linspace(100.0, 150.0, n), dtype=float)
    benchmark_close = pd.Series(np.linspace(90.0, 120.0, n), dtype=float)

    bars = pd.DataFrame(
        {
            "symbol": ["AAPL"] * n,
            "date": dates,
            "open": close * 0.99,
            "high": close * 1.01,
            "low": close * 0.98,
            "close": close,
            "volume": np.linspace(1_000_000, 1_100_000, n),
            "adj_close": close,
            "vwap": close,
            "daily_return": 0.0,
            "is_filled": 0,
        }
    )
    benchmark = pd.DataFrame(
        {
            "symbol": ["SPY"] * n,
            "date": dates,
            "open": benchmark_close * 0.99,
            "high": benchmark_close * 1.01,
            "low": benchmark_close * 0.98,
            "close": benchmark_close,
            "volume": np.linspace(2_000_000, 2_200_000, n),
            "adj_close": benchmark_close,
            "vwap": benchmark_close,
            "daily_return": 0.0,
            "is_filled": 0,
        }
    )

    result = features.compute_features(bars, benchmark_df=benchmark, feature_set="expert")

    for col in ["sma20_distance", "relative_strength_20", "market_volatility_20", "regime_bull_market"]:
        assert col in result.columns
    assert not result[["sma20_distance", "relative_strength_20", "market_volatility_20"]].isna().any().any()


def test_get_feature_columns_can_include_cross_sectional_features() -> None:
    cols = features.get_feature_columns(include_sentiment=False, feature_set="expert", include_cross_sectional=True)

    assert "relative_strength_20" in cols
    assert "ret_20_rank" in cols


def test_get_feature_columns_can_include_screener_scores() -> None:
    cols = features.get_feature_columns(include_screener_scores=True)

    assert "selector_trend_score" in cols
    assert "selector_mode_sector_neutralized" in cols


def test_get_feature_columns_can_include_sector_features() -> None:
    """Sector features are included automatically with cross-sectional features."""
    cols = features.get_feature_columns(include_cross_sectional=True)

    assert "sector_ret_20" in cols
    assert "sector_ret_60" in cols
    assert "sector_vol_20" in cols
    assert "sector_relative_strength_20" in cols
    assert "sector_dollar_volume_20" in cols
    assert "sector_symbol_count" in cols
    assert "stock_vs_sector_ret_20" in cols
    assert "stock_vs_sector_ret_60" in cols


def test_get_feature_columns_sector_features_default_off() -> None:
    """By default (no cross-sectional), sector features should NOT be included."""
    cols = features.get_feature_columns()
    assert "sector_ret_20" not in cols
    assert "sector_vol_20" not in cols


def test_get_feature_columns_cross_sectional_includes_sector() -> None:
    """Cross-sectional now includes both percentile ranks AND sector features."""
    cols = features.get_feature_columns(include_cross_sectional=True)
    assert "ret_20_rank" in cols  # cross-sectional percentile
    assert "sector_ret_20" in cols  # sector feature
    # Both should be present without conflict
    assert len(cols) == len(set(cols))  # no duplicates


def test_compute_features_merges_selector_context_pit_safely() -> None:
    n = 90
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    close = pd.Series(100.0 + np.arange(n), dtype=float)
    bars = pd.DataFrame(
        {
            "symbol": ["AAPL"] * n,
            "date": dates,
            "open": close * 0.99,
            "high": close * 1.01,
            "low": close * 0.98,
            "close": close,
            "volume": np.linspace(1_000_000, 1_100_000, n),
            "adj_close": close,
            "vwap": close,
            "daily_return": 0.0,
            "is_filled": 0,
        }
    )
    selector_df = pd.DataFrame(
        {
            "symbol": ["AAPL", "AAPL"],
            "date": [dates[-2], dates[-1]],
            "trend_score": [0.74, 0.82],
            "selection_rank": [7, 3],
            "earnings_blackout": [0, 1],
            "selector_signal_mode": ["strict", "sector_neutralized"],
        }
    )

    result = features.compute_features(
        bars,
        selector_df=selector_df,
        include_screener_scores=True,
    )

    assert not result.empty
    last_row = result.iloc[-1]
    assert last_row["selector_trend_score"] == 0.82
    assert last_row["selector_selection_rank"] == 3.0
    assert last_row["selector_earnings_blackout"] == 1.0
    assert last_row["selector_mode_sector_neutralized"] == 1.0


