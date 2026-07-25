"""Tests for modelFactory/factor_features.py — CAPM factor exposures."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modelFactory.factor_features import (
    FACTOR_DEFAULTS,
    FACTOR_FEATURE_COLUMNS,
    compute_factor_features,
    fill_factor_defaults,
)


# ── Fixtures ──


def _make_synthetic_bars(n: int = 504, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic daily bars with realistic returns."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    daily_return = rng.normal(0.0005, 0.012, size=n).astype(np.float64)
    return pd.DataFrame({"date": dates, "daily_return": daily_return})


def _make_benchmark(n: int = 504, seed: int = 99) -> pd.DataFrame:
    """Generate synthetic benchmark (SPY-like) returns."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    daily_return = rng.normal(0.0003, 0.010, size=n).astype(np.float64)
    return pd.DataFrame({"date": dates, "daily_return": daily_return})


# ── Tests ──


class TestFactorFeatureColumns:
    def test_columns_are_non_empty(self) -> None:
        assert len(FACTOR_FEATURE_COLUMNS) == 4

    def test_columns_have_expected_names(self) -> None:
        assert FACTOR_FEATURE_COLUMNS == [
            "beta_252", "alpha_252", "r_squared_252", "momentum_252_vs_market",
        ]

    def test_defaults_cover_all_columns(self) -> None:
        for col in FACTOR_FEATURE_COLUMNS:
            assert col in FACTOR_DEFAULTS, f"Missing default for {col}"


class TestComputeFactorFeatures:
    def test_returns_all_factor_columns(self) -> None:
        df = _make_synthetic_bars()
        bench = _make_benchmark()
        result = compute_factor_features(df, benchmark_df=bench)
        for col in FACTOR_FEATURE_COLUMNS:
            assert col in result.columns, f"Missing column {col}"

    def test_no_benchmark_fills_defaults(self) -> None:
        df = _make_synthetic_bars()
        result = compute_factor_features(df, benchmark_df=None)
        assert (result["beta_252"] == 1.0).all()
        assert (result["alpha_252"] == 0.0).all()
        assert (result["r_squared_252"] == 0.0).all()
        assert (result["momentum_252_vs_market"] == 0.0).all()

    def test_empty_benchmark_fills_defaults(self) -> None:
        df = _make_synthetic_bars()
        result = compute_factor_features(df, benchmark_df=pd.DataFrame())
        assert (result["beta_252"] == 1.0).all()
        assert (result["alpha_252"] == 0.0).all()

    def test_beta_near_one_for_identical_returns(self) -> None:
        """If stock = benchmark, beta ≈ 1.0, alpha ≈ 0."""
        n = 600
        rng = np.random.default_rng(123)
        rets = rng.normal(0.0005, 0.010, size=n).astype(np.float64)
        dates = pd.date_range("2019-01-01", periods=n, freq="B")
        df = pd.DataFrame({"date": dates, "daily_return": rets})
        bench = pd.DataFrame({"date": dates, "daily_return": rets.copy()})
        result = compute_factor_features(df, benchmark_df=bench)
        # Last value should converge to ~1.0
        assert 0.9 < result["beta_252"].iloc[-1] < 1.1
        assert -0.01 < result["alpha_252"].iloc[-1] < 0.01

    def test_beta_positive_for_correlated_returns(self) -> None:
        """Stock return = 1.5 * benchmark + noise → beta should be > 0."""
        n = 600
        rng = np.random.default_rng(456)
        dates = pd.date_range("2019-01-01", periods=n, freq="B")
        bench_rets = rng.normal(0.0003, 0.008, size=n).astype(np.float64)
        stock_rets = 1.5 * bench_rets + rng.normal(0, 0.005, size=n).astype(np.float64)
        df = pd.DataFrame({"date": dates, "daily_return": stock_rets})
        bench = pd.DataFrame({"date": dates, "daily_return": bench_rets})
        result = compute_factor_features(df, benchmark_df=bench)
        assert result["beta_252"].iloc[-1] > 0.5
        # R² should be nonzero
        assert result["r_squared_252"].iloc[-1] > 0.0

    def test_r_squared_between_zero_and_one(self) -> None:
        df = _make_synthetic_bars()
        bench = _make_benchmark()
        result = compute_factor_features(df, benchmark_df=bench)
        valid = result["r_squared_252"].iloc[252:]  # skip warm-up
        assert (valid >= 0.0).all()
        assert (valid <= 1.0).all()

    def test_momentum_vs_market_sum_of_returns(self) -> None:
        df = _make_synthetic_bars()
        bench = _make_benchmark()
        result = compute_factor_features(df, benchmark_df=bench)
        # After 252 days, momentum_252_vs_market = sum(stock_rets) - sum(market_rets)
        stock_cum = df["daily_return"].iloc[:252].sum()
        market_cum = bench["daily_return"].iloc[:252].sum()
        assert result["momentum_252_vs_market"].iloc[251] is not None

    def test_short_history_fills_defaults(self) -> None:
        """Less than min_periods (126 days) → defaults."""
        df = _make_synthetic_bars(n=50)
        bench = _make_benchmark(n=50)
        result = compute_factor_features(df, benchmark_df=bench)
        # beta defaults to 1.0 for insufficient history
        assert result["beta_252"].iloc[-1] == 1.0
        assert result["alpha_252"].iloc[-1] == 0.0

    def test_no_inf_nan_in_output(self) -> None:
        df = _make_synthetic_bars()
        bench = _make_benchmark()
        result = compute_factor_features(df, benchmark_df=bench)
        for col in FACTOR_FEATURE_COLUMNS:
            assert not result[col].isna().any(), f"NaN in {col}"
            assert not np.isinf(result[col]).any(), f"Inf in {col}"

    def test_does_not_modify_input(self) -> None:
        df = _make_synthetic_bars()
        original_cols = set(df.columns)
        bench = _make_benchmark()
        _ = compute_factor_features(df, benchmark_df=bench)
        assert set(df.columns) == original_cols  # input unchanged


class TestFillFactorDefaults:
    def test_adds_missing_columns(self) -> None:
        df = pd.DataFrame({"a": [1, 2, 3]})
        result = fill_factor_defaults(df)
        for col in FACTOR_FEATURE_COLUMNS:
            assert col in result.columns
            assert (result[col] == FACTOR_DEFAULTS[col]).all()

    def test_fills_nan_with_defaults(self) -> None:
        df = pd.DataFrame({col: [np.nan, np.nan] for col in FACTOR_FEATURE_COLUMNS})
        result = fill_factor_defaults(df)
        for col in FACTOR_FEATURE_COLUMNS:
            assert not result[col].isna().any()

    def test_replaces_inf(self) -> None:
        df = pd.DataFrame({col: [np.inf, -np.inf] for col in FACTOR_FEATURE_COLUMNS})
        result = fill_factor_defaults(df)
        for col in FACTOR_FEATURE_COLUMNS:
            assert not np.isinf(result[col]).any()

    def test_leaves_valid_values_unchanged(self) -> None:
        df = pd.DataFrame({"beta_252": [1.2, 0.8], "alpha_252": [0.05, -0.02]})
        result = fill_factor_defaults(df)
        assert result["beta_252"].iloc[0] == 1.2
        assert result["alpha_252"].iloc[1] == -0.02


class TestIntegrationWithFeatures:
    """Verify factor features flow through get_feature_columns()."""

    def test_include_factors_adds_columns(self) -> None:
        from modelFactory.features import get_feature_columns
        cols = get_feature_columns(feature_set="expert", include_factors=True)
        for fc in FACTOR_FEATURE_COLUMNS:
            assert fc in cols, f"{fc} not in feature columns"

    def test_without_factors_excludes_columns(self) -> None:
        from modelFactory.features import get_feature_columns
        cols = get_feature_columns(feature_set="expert", include_factors=False)
        for fc in FACTOR_FEATURE_COLUMNS:
            assert fc not in cols, f"{fc} should not be in feature columns"

    def test_fingerprint_changes_with_factors(self) -> None:
        from modelFactory.features import fingerprint
        fp_with = fingerprint(feature_set="expert", include_factors=True)
        fp_without = fingerprint(feature_set="expert", include_factors=False)
        assert fp_with != fp_without

    def test_compute_features_with_factors(self) -> None:
        """End-to-end: compute_features with include_factors=True."""
        from modelFactory.features import compute_features

        n = 600
        rng = np.random.default_rng(42)
        dates = pd.date_range("2020-01-01", periods=n, freq="B")
        df = pd.DataFrame({
            "date": dates,
            "open": 100.0 + rng.normal(0, 2, n).cumsum(),
            "high": 102.0 + rng.normal(0, 2, n).cumsum(),
            "low": 98.0 + rng.normal(0, 2, n).cumsum(),
            "close": 100.0 + rng.normal(0, 2, n).cumsum(),
            "volume": rng.integers(1000000, 10000000, n).astype(float),
            "adj_close": 100.0 + rng.normal(0, 2, n).cumsum(),
            "vwap": 100.0 + rng.normal(0, 2, n).cumsum(),
            "daily_return": rng.normal(0.0005, 0.012, n).astype(float),
            "is_filled": 1,
        })
        bench = pd.DataFrame({
            "date": dates,
            "daily_return": rng.normal(0.0003, 0.010, n).astype(float),
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 1e7,
            "adj_close": 100.0,
            "vwap": 100.0,
            "is_filled": 1,
        })
        result = compute_features(
            df, feature_set="expert", include_factors=True, benchmark_df=bench,
        )
        for fc in FACTOR_FEATURE_COLUMNS:
            assert fc in result.columns, f"{fc} missing from compute_features output"
