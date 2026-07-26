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


# ── Approche 2 — Stacking : include_global_stacking ──

def test_get_feature_columns_global_stacking_adds_column() -> None:
    cols = features.get_feature_columns(
        include_cross_sectional=True, include_global_stacking=True,
    )
    assert "global_rank" in cols
    assert "ret_20_rank" in cols
    assert "sector_ret_20" in cols


def test_get_feature_columns_global_stacking_requires_cross_sectional() -> None:
    cols = features.get_feature_columns(include_global_stacking=True)
    assert "global_rank" not in cols


def test_get_feature_columns_global_stacking_default_off() -> None:
    cols = features.get_feature_columns(include_cross_sectional=True)
    assert "global_rank" not in cols


def test_fingerprint_differs_with_global_stacking() -> None:
    """Le fingerprint change quand include_global_stacking passe de False à True."""
    fp_off = features.fingerprint(
        include_cross_sectional=True, include_global_stacking=False,
    )
    fp_on = features.fingerprint(
        include_cross_sectional=True, include_global_stacking=True,
    )
    assert fp_off != fp_on
    assert len(fp_off) == 16
    assert len(fp_on) == 16


def test_fingerprint_stable_global_stacking() -> None:
    """Le fingerprint est stable (déterministe) pour include_global_stacking=True."""
    fp1 = features.fingerprint(
        feature_set="expert", include_cross_sectional=True, include_global_stacking=True,
    )
    fp2 = features.fingerprint(
        feature_set="expert", include_cross_sectional=True, include_global_stacking=True,
    )
    assert fp1 == fp2


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


# ─────────────────────────────────────────────────────────────────────
# Sprint 2026-07-26 — Régime macro + interactions global_rank
# ─────────────────────────────────────────────────────────────────────

def test_macro_regime_features_in_columns():
    """Vérifie que SPY_SMA_200_slope et VIX_zscore sont dans get_feature_columns
    quand include_macro_regime=True."""
    cols = features.get_feature_columns(
        feature_set="expert", include_macro_regime=True,
    )
    assert "SPY_SMA_200_slope" in cols
    assert "VIX_zscore" in cols


def test_macro_regime_features_absent_when_disabled():
    """Sans include_macro_regime, les colonnes ne doivent pas apparaître."""
    cols = features.get_feature_columns(feature_set="expert")
    assert "SPY_SMA_200_slope" not in cols
    assert "VIX_zscore" not in cols


def test_compute_features_macro_regime_from_benchmark():
    """compute_features avec benchmark SPY + include_macro_regime produit
    SPY_SMA_200_slope (pente SMA200) et VIX_zscore (fallback 0 sans VIX chargé)."""
    n = 300
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    close = pd.Series(100.0 + np.arange(n) * 0.5, dtype=float)

    bars = pd.DataFrame({
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
    })
    benchmark = pd.DataFrame({
        "symbol": ["SPY"] * n,
        "date": dates,
        "open": close * 0.5,
        "high": close * 0.51,
        "low": close * 0.49,
        "close": close * 1.5,  # tendance haussière
        "volume": np.linspace(5_000_000, 6_000_000, n),
        "adj_close": close * 1.5,
        "vwap": close * 1.5,
        "daily_return": 0.0,
        "is_filled": 0,
    })

    result = features.compute_features(
        bars, benchmark_df=benchmark,
        feature_set="expert", include_macro_regime=True,
    )
    assert "SPY_SMA_200_slope" in result.columns
    assert "VIX_zscore" in result.columns
    # En tendance haussière stable, la pente SMA200 doit être > 0
    non_null = result["SPY_SMA_200_slope"].dropna()
    assert len(non_null) > 0
    assert (non_null > 0).all(), f"SPY_SMA_200_slope should be positive in uptrend, got min={non_null.min()}"


# ─────────────────────────────────────────────────────────────────────
# Rank interaction features (Action 5)
# ─────────────────────────────────────────────────────────────────────

def test_rank_interaction_features_in_columns():
    """rank_x_* doivent apparaître dans get_feature_columns
    quand include_cross_sectional=True ET include_global_stacking=True."""
    cols = features.get_feature_columns(
        feature_set="expert",
        include_cross_sectional=True,
        include_global_stacking=True,
    )
    for f in features.RANK_INTERACTION_FEATURES:
        assert f in cols, f"{f} missing from feature columns"


def test_rank_interaction_features_absent_without_stacking():
    """Sans include_global_stacking, pas de rank_x_*."""
    cols = features.get_feature_columns(
        feature_set="expert",
        include_cross_sectional=True,
        include_global_stacking=False,
    )
    for f in features.RANK_INTERACTION_FEATURES:
        assert f not in cols, f"{f} should not appear without stacking"


def test_compute_rank_interactions_basic():
    """compute_rank_interactions calcule bien global_rank × feature source."""
    df = pd.DataFrame({
        "global_rank": [0.5, 0.9, 0.1, 0.0, 1.0],
        "rsi_14": [50.0, 70.0, 30.0, 40.0, 60.0],
        "momentum_20": [0.02, -0.01, 0.05, 0.0, 0.10],
        "momentum_60": [0.10, 0.05, -0.02, 0.0, 0.20],
        "rolling_volatility_20": [0.15, 0.20, 0.10, 0.25, 0.05],
        "sma20_distance": [0.01, 0.03, -0.02, 0.0, 0.05],
    })
    result = features.compute_rank_interactions(df)

    assert result["rank_x_rsi_14"].tolist() == [25.0, 63.0, 3.0, 0.0, 60.0]
    # Floating-point: 0.5*0.02, 0.9*(-0.01), 0.1*0.05, 0.0*0, 1.0*0.10
    assert abs(result.loc[0, "rank_x_momentum_20"] - 0.01) < 1e-12
    assert abs(result.loc[1, "rank_x_momentum_20"] - (-0.009)) < 1e-12
    assert abs(result.loc[2, "rank_x_momentum_20"] - 0.005) < 1e-12
    assert result.loc[3, "rank_x_momentum_20"] == 0.0
    assert result.loc[4, "rank_x_momentum_20"] == 0.10
    assert result["rank_x_sma20_distance"].tolist() == [0.005, 0.027, -0.002, 0.0, 0.05]


def test_compute_rank_interactions_fallback_no_global_rank():
    """Sans colonne global_rank, compute_rank_interactions remplit 0.0."""
    df = pd.DataFrame({"rsi_14": [50.0, 70.0], "momentum_20": [0.02, -0.01]})
    result = features.compute_rank_interactions(df)
    for col in features.RANK_INTERACTION_FEATURES:
        assert col in result.columns
        assert (result[col] == 0.0).all(), f"{col} should be 0.0 without global_rank"


def test_compute_rank_interactions_fallback_missing_source():
    """Si une feature source manque, la colonne rank_x correspondante vaut 0.0."""
    df = pd.DataFrame({
        "global_rank": [0.5, 0.9],
        "rsi_14": [50.0, 70.0],
        # momentum_20, momentum_60, etc. absents
    })
    result = features.compute_rank_interactions(df)
    # rsi_14 est présent → rank_x_rsi_14 doit être calculé
    assert (result["rank_x_rsi_14"] != 0.0).any()
    # momentum_20 est absent → fallback 0.0
    assert (result["rank_x_momentum_20"] == 0.0).all()
    assert (result["rank_x_volatility_20"] == 0.0).all()


def test_compute_rank_interactions_handles_nan():
    """global_rank NaN → fill 0.5 ; source NaN → fill 0.0."""
    df = pd.DataFrame({
        "global_rank": [np.nan, 0.8],
        "rsi_14": [50.0, np.nan],
        "momentum_20": [0.02, 0.05],
    })
    result = features.compute_rank_interactions(df)
    # ligne 0: global_rank NaN → 0.5, rsi=50 → 25.0
    assert abs(result.loc[0, "rank_x_rsi_14"] - 25.0) < 1e-9
    # ligne 1: rsi NaN → 0.0 source → rank = 0
    assert abs(result.loc[1, "rank_x_rsi_14"] - 0.0) < 1e-9
    assert result.loc[0, "rank_x_momentum_20"] == 0.01  # 0.5*0.02


# ─────────────────────────────────────────────────────────────────────
# Config defaults (Actions 2-4 — régularisation)
# ─────────────────────────────────────────────────────────────────────

def test_baseline_config_defaults_regularized():
    """Vérifie que les nouveaux défauts de régularisation sont bien appliqués."""
    from modelFactory.config import BaselineConfig
    cfg = BaselineConfig()
    assert cfg.max_depth == 4
    assert cfg.lgbm_num_leaves == 15
    assert cfg.lgbm_min_child_samples == 30
    assert cfg.lgbm_subsample == 0.8
    assert cfg.lgbm_colsample_bytree == 0.7
    assert cfg.lgbm_reg_alpha == 0.1
    assert cfg.lgbm_reg_lambda == 0.1
    assert cfg.catboost_depth == 4


def test_data_config_include_macro_regime_default():
    """include_macro_regime_features est False par défaut."""
    from modelFactory.config import DataConfig
    cfg = DataConfig()
    assert cfg.include_macro_regime_features is False

