"""Tests unitaires pour selector/regime_scoring.py."""

from __future__ import annotations

import pytest
import pandas as pd
import numpy as np

from selector.regime_scoring import (
    NORMAL_WEIGHTS,
    CAPITAL_PRESERVATION_WEIGHTS,
    DEFENSIVE_FILTER_OVERLAYS,
    MomentumRotationState,
    apply_regime_filters,
    apply_regime_weights,
    evaluate_momentum_rotation,
    get_regime_weights,
)


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def sample_df() -> pd.DataFrame:
    """DataFrame représentatif de candidats post-merge selector."""
    return pd.DataFrame({
        "symbol": ["AAPL", "TSLA", "JNJ", "WMT", "XOM"],
        "sector": ["Tech", "Auto", "Health", "Staples", "Energy"],
        "trend_score": [0.85, 0.92, 0.30, 0.45, 0.55],
        "vcp_score": [0.70, 0.65, 0.40, 0.50, 0.60],
        "total_score": [88.0, 75.0, 62.0, 70.0, 68.0],
        "relative_strength_index": [72.0, 85.0, 48.0, 55.0, 60.0],
        "beta_126": [1.15, 2.10, 0.55, 0.40, 1.05],
        "market_cap": [3.0e12, 600e9, 450e9, 420e9, 480e9],
        "volatility_ratio": [0.80, 1.50, 0.45, 0.50, 0.90],
        "atr_pct_20": [0.025, 0.075, 0.018, 0.022, 0.035],
        "spread_bps": [4.0, 12.0, 6.0, 5.0, 10.0],
    })


class MockSnapshot:
    """Mock minimal pour MarketRegimeSnapshot."""
    def __init__(self, mode: str = "normal"):
        self.mode = mode


# ── get_regime_weights ──────────────────────────────────────────────

class TestGetRegimeWeights:
    def test_normal_mode_returns_normal_weights(self):
        snap = MockSnapshot("normal")
        w = get_regime_weights(snap)
        assert w == NORMAL_WEIGHTS

    def test_capital_preservation_returns_defensive_weights(self):
        snap = MockSnapshot("capital_preservation")
        w = get_regime_weights(snap)
        assert w == CAPITAL_PRESERVATION_WEIGHTS

    def test_close_only_returns_defensive_weights(self):
        snap = MockSnapshot("close_only")
        w = get_regime_weights(snap)
        assert w == CAPITAL_PRESERVATION_WEIGHTS

    def test_none_snapshot_returns_normal_weights(self):
        w = get_regime_weights(None)
        assert w == NORMAL_WEIGHTS

    def test_rotation_overrides_normal(self):
        snap = MockSnapshot("normal")
        rot = MomentumRotationState(lookback_weeks=2, threshold=-0.01)
        # Feed losing returns
        for _ in range(10):
            rot.record(-0.01)  # -1% per day
        w = get_regime_weights(snap, rotation_state=rot)
        assert w == CAPITAL_PRESERVATION_WEIGHTS

    def test_rotation_no_override_when_winning(self):
        snap = MockSnapshot("normal")
        rot = MomentumRotationState(lookback_weeks=2, threshold=-0.01)
        for _ in range(10):
            rot.record(+0.01)  # +1% per day
        w = get_regime_weights(snap, rotation_state=rot)
        assert w == NORMAL_WEIGHTS


# ── apply_regime_filters ────────────────────────────────────────────

class TestApplyRegimeFilters:
    def test_normal_mode_no_filter(self, sample_df):
        snap = MockSnapshot("normal")
        result = apply_regime_filters(sample_df.copy(), snap)
        assert len(result) == len(sample_df)

    def test_defensive_mode_filters_high_beta(self, sample_df):
        snap = MockSnapshot("capital_preservation")
        result = apply_regime_filters(sample_df.copy(), snap)
        # TSLA (beta=2.1) doit être filtré
        assert "TSLA" not in result["symbol"].values
        assert len(result) < len(sample_df)

    def test_defensive_mode_filters_high_atr(self, sample_df):
        snap = MockSnapshot("capital_preservation")
        result = apply_regime_filters(sample_df.copy(), snap)
        # TSLA (atr_pct_20=0.075 > 0.06) doit être filtré
        assert "TSLA" not in result["symbol"].values

    def test_none_snapshot_no_filter(self, sample_df):
        result = apply_regime_filters(sample_df.copy(), None)
        assert len(result) == len(sample_df)

    def test_empty_df(self):
        result = apply_regime_filters(pd.DataFrame(), MockSnapshot("capital_preservation"))
        assert result.empty


# ── apply_regime_weights ────────────────────────────────────────────

class TestApplyRegimeWeights:
    def test_normal_mode_is_noop(self, sample_df):
        snap = MockSnapshot("normal")
        df_in = sample_df.copy()
        result = apply_regime_weights(df_in, snap)
        # En mode normal, le DataFrame est retourné tel quel
        assert len(result) == len(sample_df)
        # Pas de colonnes défensives ajoutées
        assert "defensive_beta_component" not in result.columns
        # Les colonnes originales sont préservées
        assert "symbol" in result.columns
        assert "trend_score" in result.columns

    def test_defensive_mode_adds_components(self, sample_df):
        snap = MockSnapshot("capital_preservation")
        # Ajouter les colonnes normalisées qui seraient normalement produites par merge_scores
        df = sample_df.copy()
        from selector.factors import winsorize_and_normalize
        df["normalized_total_score"] = winsorize_and_normalize(df["total_score"])
        df["normalized_rsi"] = winsorize_and_normalize(df["relative_strength_index"])
        result = apply_regime_weights(df, snap)
        assert "defensive_beta_component" in result.columns
        assert "defensive_size_component" in result.columns
        assert "defensive_low_vol_component" in result.columns
        assert "final_score" in result.columns
        # TSLA filtré (high beta + high ATR)
        assert len(result) < len(sample_df)

    def test_defensive_weights_sum_to_one(self):
        total = sum(CAPITAL_PRESERVATION_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}"

    def test_normal_weights_sum_to_one(self):
        total = sum(NORMAL_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}"

    def test_empty_df(self):
        result = apply_regime_weights(pd.DataFrame(), MockSnapshot("capital_preservation"))
        assert result.empty

    def test_defensive_prefers_low_beta(self, sample_df):
        snap = MockSnapshot("capital_preservation")
        df = sample_df.copy()
        from selector.factors import winsorize_and_normalize
        df["normalized_total_score"] = winsorize_and_normalize(df["total_score"])
        df["normalized_rsi"] = winsorize_and_normalize(df["relative_strength_index"])
        result = apply_regime_weights(df, snap)
        # JNJ (beta=0.55) et WMT (beta=0.40) devraient avoir un bon score défensif
        tsla_rows = result[result["symbol"] == "TSLA"]
        # TSLA a dû être filtré
        assert tsla_rows.empty
        # JNJ a un bon score défensif
        jnj_row = result[result["symbol"] == "JNJ"]
        if not jnj_row.empty:
            assert jnj_row["defensive_beta_component"].iloc[0] > 0


# ── MomentumRotationState ───────────────────────────────────────────

class TestMomentumRotationState:
    def test_initial_state_not_ready(self):
        rot = MomentumRotationState()
        assert not rot.is_ready()
        assert not rot.should_rotate()
        assert rot.cumulative_return() is None

    def test_ready_after_one_week(self):
        rot = MomentumRotationState(lookback_weeks=2)
        for _ in range(5):
            rot.record(0.001)
        assert rot.is_ready()

    def test_rotate_when_losing(self):
        rot = MomentumRotationState(lookback_weeks=2, threshold=-0.03)
        for _ in range(10):
            rot.record(-0.008)  # -0.8% per day → ~-8% cumulé
        assert rot.should_rotate()

    def test_no_rotate_when_winning(self):
        rot = MomentumRotationState(lookback_weeks=2, threshold=-0.03)
        for _ in range(10):
            rot.record(+0.005)  # +0.5% per day
        assert not rot.should_rotate()

    def test_reset_clears_history(self):
        rot = MomentumRotationState()
        for _ in range(10):
            rot.record(-0.01)
        assert rot.is_ready()
        rot.reset()
        assert not rot.is_ready()
        assert rot.cumulative_return() is None

    def test_window_size_respected(self):
        rot = MomentumRotationState(lookback_weeks=2)
        # 20 jours de returns
        for i in range(20):
            rot.record(0.01 if i < 10 else -0.01)
        # La fenêtre (2*5=10 jours) ne garde que les 10 derniers
        cum = rot.cumulative_return()
        # Les 10 derniers jours sont tous à -1%, donc cumulé ≈ -9.5%
        assert cum is not None
        assert cum < -0.05  # au moins -5%

    def test_lookback_weeks_minimum_one(self):
        rot = MomentumRotationState(lookback_weeks=0)
        assert rot._lookback == 1


# ── evaluate_momentum_rotation ──────────────────────────────────────

class TestEvaluateMomentumRotation:
    def test_defensive_snapshot_always_true(self):
        snap = MockSnapshot("capital_preservation")
        assert evaluate_momentum_rotation(None, snap) is True

    def test_normal_snapshot_without_rotation_is_false(self):
        snap = MockSnapshot("normal")
        assert evaluate_momentum_rotation(None, snap) is False

    def test_normal_snapshot_with_losing_rotation_is_true(self):
        snap = MockSnapshot("normal")
        rot = MomentumRotationState(lookback_weeks=2, threshold=-0.01)
        for _ in range(10):
            rot.record(-0.01)
        assert evaluate_momentum_rotation(rot, snap) is True

    def test_normal_snapshot_with_winning_rotation_is_false(self):
        snap = MockSnapshot("normal")
        rot = MomentumRotationState(lookback_weeks=2, threshold=-0.01)
        for _ in range(10):
            rot.record(+0.01)
        assert evaluate_momentum_rotation(rot, snap) is False

    def test_rotation_not_ready_returns_false(self):
        snap = MockSnapshot("normal")
        rot = MomentumRotationState()
        rot.record(-0.05)  # 1 seul jour
        assert evaluate_momentum_rotation(rot, snap) is False


# ── Constantes ──────────────────────────────────────────────────────

class TestConstants:
    def test_defensive_filters_have_expected_keys(self):
        assert "max_beta_126" in DEFENSIVE_FILTER_OVERLAYS
        assert "max_spread_bps" in DEFENSIVE_FILTER_OVERLAYS
        assert "min_market_cap" in DEFENSIVE_FILTER_OVERLAYS
        assert "max_atr_pct_20" in DEFENSIVE_FILTER_OVERLAYS
        assert DEFENSIVE_FILTER_OVERLAYS["max_beta_126"] == 1.2
        assert DEFENSIVE_FILTER_OVERLAYS["min_market_cap"] == 2_000_000_000.0
