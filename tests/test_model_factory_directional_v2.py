"""Tests — Per-Symbol Directional v2 : features F1-Core (Trend/Volatility).

Campagne F0/F1/F2/F3a/F3b (2026-08-18). F1 = 7 features directionnelles exclusives.
Règle d'or : F0 (legacy) ne doit pas contenir les features F1.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modelFactory.features import compute_features, get_feature_columns

F1 = [
    "adx_14",
    "atr_ratio_5_20",
    "atr20_pct",
    "ema20_slope_10",
    "ema50_slope_20",
    "distance_ema20",
    "distance_ema50",
]


def _synth_df(n: int = 400, seed: int = 0) -> pd.DataFrame:
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    rng = np.random.default_rng(seed)
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0004, 0.015, n))), index=idx)
    return pd.DataFrame(
        {
            "date": idx,
            "open": close * 0.999,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": pd.Series(rng.integers(100_000, 500_000, n).astype(float), index=idx),
            "adj_close": close,
            "vwap": close,
            "daily_return": close / close.shift(1) - 1.0,
            "is_filled": 1,
        }
    )


def test_f1_features_present_in_expert_set() -> None:
    exp = get_feature_columns(feature_set="expert")
    for f in F1:
        assert f in exp


def test_f1_whitelist_returns_exactly_seven() -> None:
    cols = get_feature_columns(
        feature_set="expert",
        feature_whitelist_enabled=True,
        feature_whitelist=tuple(F1),
    )
    assert cols == F1


def test_f0_legacy_has_no_f1_features() -> None:
    # F0 = v1+short+factors, volume gaté OFF → 18 features, AUCUNE feature F1.
    v1 = get_feature_columns(
        feature_set="v1",
        include_short_score=True,
        include_factors=True,
        include_volume_features=False,
    )
    assert len(v1) == 18
    assert [f for f in F1 if f in v1] == []


def test_f1_features_computed_pit_and_stationary() -> None:
    cf = compute_features(_synth_df(), feature_set="expert")
    for f in F1:
        assert f in cf.columns
        # warmup (NaN) puis valeurs finies → PIT / stationnaire
        assert cf[f].notna().sum() > 100
        assert np.isfinite(cf[f].tail(50)).all()


def test_f1_features_not_computed_for_v1() -> None:
    # En v1 (hors expert), les colonnes F1 ne doivent pas être produites.
    cf = compute_features(_synth_df(), feature_set="v1")
    assert [f for f in F1 if f in cf.columns] == []


# ─────────────────────────────────────────────────────────────
# F2 — Momentum / Price Action / Structure
# F3a — Relative Strength (stock − SPY, stock − secteur)
# F3b — Volume (ratio, z-score, OBV, CMF)
# ─────────────────────────────────────────────────────────────

F2_NEW = [
    "return_2d",
    "return_5d",
    "return_10d",
    "return_20d",
    "range_position_50",
    "distance_high_20",
    "distance_low_20",
    "body_range",
    "close_location_value",
]
F2 = F1 + ["range_position_20"] + F2_NEW  # 17 (cumulatif avec F1)

F3A = [
    "relative_strength_5",
    "relative_strength_20",
    "relative_strength_60",
    "stock_vs_sector_ret_5",
    "stock_vs_sector_ret_20",
    "stock_vs_sector_ret_60",
]  # 6

F3B = ["volume_ratio_20", "volume_zscore_20", "obv_slope_20", "cmf_20"]  # 4


def test_f2_features_present_in_expert_set() -> None:
    exp = get_feature_columns(feature_set="expert")
    for f in F2:
        assert f in exp


def test_f2_whitelist_exact() -> None:
    cols = get_feature_columns(
        feature_set="expert",
        feature_whitelist_enabled=True,
        feature_whitelist=tuple(F2),
    )
    assert cols == F2
    assert len(cols) == 17


def test_f3a_whitelist_exact_with_cross_sectional() -> None:
    cols = get_feature_columns(
        feature_set="expert",
        include_cross_sectional=True,
        feature_whitelist_enabled=True,
        feature_whitelist=tuple(F3A),
    )
    assert cols == F3A
    assert len(cols) == 6


def test_f3b_whitelist_exact_with_volume() -> None:
    cols = get_feature_columns(
        feature_set="expert",
        include_volume_features=True,
        feature_whitelist_enabled=True,
        feature_whitelist=tuple(F3B),
    )
    assert cols == F3B
    assert len(cols) == 4


def test_f2_f3b_features_computed_pit_and_stationary() -> None:
    cf = compute_features(_synth_df(), feature_set="expert")
    for f in F2_NEW + ["volume_zscore_20", "cmf_20"]:
        assert f in cf.columns
        assert cf[f].notna().sum() > 100
        assert np.isfinite(cf[f].tail(50)).all()
    # body_range ∈ [-1,1], close_location_value ∈ [0,1] (range clipé)
    assert cf["close_location_value"].clip(0, 1).equals(cf["close_location_value"])


def test_f3a_relative_strength_5_computed_with_benchmark() -> None:
    bars = _synth_df()
    # Date en ndarray (index RangeIndex) → identique au chargement prod (DB) :
    # sinon `bars["date"]` (Series indexée DatetimeIndex) désaligne le bench.
    idx = bars["date"].to_numpy()
    # Benchmark SPY : drift différent → relative_strength_5 ≠ 0
    bench_close = pd.Series(90 * np.exp(np.cumsum(np.random.default_rng(7).normal(0.0, 0.01, len(bars)))), index=range(len(bars)))
    bench = pd.DataFrame({"date": idx, "close": bench_close.values})
    cf = compute_features(bars, benchmark_df=bench, feature_set="expert")
    assert "relative_strength_5" in cf.columns
    assert cf["relative_strength_5"].notna().sum() > 100
    tail = cf.dropna(subset=["relative_strength_5"]).tail(20)
    expected = tail["momentum_5"] - tail["benchmark_return_5"]
    assert np.allclose(tail["relative_strength_5"], expected, atol=1e-12)


def test_f0_legacy_has_no_f2_f3a_f3b_features() -> None:
    v1 = get_feature_columns(
        feature_set="v1",
        include_short_score=True,
        include_factors=True,
        include_volume_features=False,
    )
    leak = [f for f in F2_NEW + ["stock_vs_sector_ret_5", "relative_strength_5", "volume_zscore_20", "cmf_20"] if f in v1]
    assert leak == []
