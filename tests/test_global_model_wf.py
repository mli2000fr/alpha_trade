"""tests/test_global_model_wf.py — Tests unitaires pour le Global Model Walk-Forward (Approche 2)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from modelFactory.config import GlobalModelConfig
from modelFactory.cross_sectional import GLOBAL_PRED_FEATURE_COLUMNS
from modelFactory.global_model import (
    _aggregate_wf_per_symbol_metrics,
    _compute_by_symbol_metrics,
)


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _make_mock_proba(y_true: np.ndarray, noise: float = 0.05) -> np.ndarray:
    """Génère des probas réalistes à partir de labels binaires."""
    rng = np.random.default_rng(42)
    proba = (y_true.astype(np.float64) * 0.6 + 0.2) + rng.normal(0, noise, len(y_true))
    return np.clip(proba, 0.01, 0.99)


def _make_mock_test_df(n_symbols: int = 3, n_dates: int = 60) -> pd.DataFrame:
    """Construit un DataFrame poolé minimal pour les tests."""
    rng = np.random.default_rng(123)
    frames: list[pd.DataFrame] = []
    symbols = [f"STOCK_{i}" for i in range(n_symbols)]
    for sym in symbols:
        dates = pd.date_range("2022-01-01", periods=n_dates, freq="B")
        n = len(dates)
        y = rng.integers(0, 2, size=n)
        future_ret = rng.normal(0.001, 0.02, size=n)
        frames.append(pd.DataFrame({
            "symbol": [sym] * n,
            "date": dates,
            "target": y.astype(int),
            "future_return": future_ret,
        }))
    return pd.concat(frames, ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────
# GlobalModelConfig
# ─────────────────────────────────────────────────────────────────────

class TestGlobalModelConfig:
    def test_defaults_stacking_disabled(self) -> None:
        cfg = GlobalModelConfig()
        assert cfg.enabled is False
        assert cfg.stacking_enabled is False
        assert cfg.challenger_enabled is False
        assert cfg.use_cross_sectional_features is True

    def test_flags_independent(self) -> None:
        """FLAG B et C sont indépendants l'un de l'autre."""
        cfg = GlobalModelConfig(enabled=True, stacking_enabled=True, challenger_enabled=False)
        assert cfg.stacking_enabled is True
        assert cfg.challenger_enabled is False

        cfg2 = GlobalModelConfig(enabled=True, stacking_enabled=False, challenger_enabled=True)
        assert cfg2.stacking_enabled is False
        assert cfg2.challenger_enabled is True

    def test_immutable(self) -> None:
        cfg = GlobalModelConfig()
        with pytest.raises(Exception):
            cfg.stacking_enabled = True  # type: ignore[misc]

    def test_validation_model_name(self) -> None:
        with pytest.raises(ValueError, match="global_model.model_name"):
            GlobalModelConfig(model_name="xgboost")

    def test_validation_artifact_symbol_empty(self) -> None:
        with pytest.raises(ValueError, match="artifact_symbol"):
            GlobalModelConfig(artifact_symbol="")


# ─────────────────────────────────────────────────────────────────────
# GLOBAL_PRED_FEATURE_COLUMNS
# ─────────────────────────────────────────────────────────────────────

class TestGlobalPredFeatureColumns:
    def test_ternary_columns_present(self) -> None:
        """Approche 2 ternaire : 3 probas (short, flat, long)."""
        assert len(GLOBAL_PRED_FEATURE_COLUMNS) == 3
        assert "global_pred_short" in GLOBAL_PRED_FEATURE_COLUMNS
        assert "global_pred_flat" in GLOBAL_PRED_FEATURE_COLUMNS
        assert "global_pred_long" in GLOBAL_PRED_FEATURE_COLUMNS

    def test_is_list_of_strings(self) -> None:
        for col in GLOBAL_PRED_FEATURE_COLUMNS:
            assert isinstance(col, str)
            assert len(col) > 0

    def test_order_short_flat_long(self) -> None:
        """L'ordre doit être [short, flat, long] pour correspondre aux colonnes 0,1,2 de predict_proba."""
        assert GLOBAL_PRED_FEATURE_COLUMNS[0] == "global_pred_short"
        assert GLOBAL_PRED_FEATURE_COLUMNS[1] == "global_pred_flat"
        assert GLOBAL_PRED_FEATURE_COLUMNS[2] == "global_pred_long"


# ─────────────────────────────────────────────────────────────────────
# _compute_by_symbol_metrics
# ─────────────────────────────────────────────────────────────────────

class TestComputeBySymbolMetrics:
    def test_partition_name_test(self) -> None:
        df = _make_mock_test_df(n_symbols=2)
        proba = _make_mock_proba(df["target"].to_numpy())
        result = _compute_by_symbol_metrics(df, proba, decision_threshold=0.5, partition_name="test")

        assert len(result) == 2
        for sym in ("STOCK_0", "STOCK_1"):
            assert sym in result
            assert result[sym]["status"] == "completed"
            assert "test" in result[sym]
            assert result[sym]["test"] is not None
            assert "selection_score" in result[sym]

    def test_partition_name_val(self) -> None:
        df = _make_mock_test_df(n_symbols=3)
        proba = _make_mock_proba(df["target"].to_numpy())
        result = _compute_by_symbol_metrics(df, proba, decision_threshold=0.5, partition_name="val")

        assert len(result) == 3
        for sym, entry in result.items():
            assert "val" in entry
            assert "test" not in entry  # on n'a pas mis test

    def test_empty_dataframe(self) -> None:
        df = pd.DataFrame(columns=["symbol", "date", "target", "future_return"])
        proba = np.array([])
        result = _compute_by_symbol_metrics(df, proba, decision_threshold=0.5)
        assert result == {}


# ─────────────────────────────────────────────────────────────────────
# _aggregate_wf_per_symbol_metrics
# ─────────────────────────────────────────────────────────────────────

class TestAggregateWfPerSymbolMetrics:
    def test_aggregates_multiple_folds(self) -> None:
        """3 splits WF pour 2 symboles → agrégation mean/std correcte."""
        fold_metrics: dict[str, list[dict[str, Any]]] = {
            "AAPL": [
                {"val": {"f1_macro": 0.60, "auc": 0.65}},
                {"val": {"f1_macro": 0.64, "auc": 0.68}},
                {"val": {"f1_macro": 0.62, "auc": 0.66}},
            ],
            "MSFT": [
                {"val": {"f1_macro": 0.55, "auc": 0.60}},
                {"val": {"f1_macro": 0.57, "auc": 0.62}},
            ],
        }
        result = _aggregate_wf_per_symbol_metrics(fold_metrics)

        assert "AAPL" in result
        assert "MSFT" in result

        aapl = result["AAPL"]
        assert aapl["status"] == "completed"
        assert aapl["model_name"] == "global_model"
        assert "walk_forward" in aapl
        wf = aapl["walk_forward"]
        assert wf["n_splits"] == 3
        assert wf["mean"]["f1_macro"] == pytest.approx(0.62, abs=0.01)
        assert wf["mean"]["auc"] == pytest.approx(0.6633, abs=0.01)

        msft = result["MSFT"]
        assert msft["walk_forward"]["n_splits"] == 2
        assert msft["walk_forward"]["mean"]["f1_macro"] == pytest.approx(0.56, abs=0.01)

    def test_selection_score_falls_back_to_auc(self) -> None:
        """Si f1_macro est absent, fallback sur threshold_business_score puis auc."""
        fold_metrics = {
            "AAPL": [
                {"val": {"auc": 0.70, "threshold_business_score": 0.55}},
            ],
        }
        result = _aggregate_wf_per_symbol_metrics(fold_metrics)
        aapl = result["AAPL"]
        # Pas de f1_macro → fallback threshold_business_score
        assert aapl["selection_score"] == pytest.approx(0.55, abs=0.01)

    def test_empty_input(self) -> None:
        result = _aggregate_wf_per_symbol_metrics({})
        assert result == {}

    def test_std_computation(self) -> None:
        fold_metrics = {
            "AAPL": [
                {"val": {"f1_macro": 0.50}},
                {"val": {"f1_macro": 0.70}},
            ],
        }
        result = _aggregate_wf_per_symbol_metrics(fold_metrics)
        aapl = result["AAPL"]
        assert aapl["walk_forward"]["std"]["f1_macro"] == pytest.approx(0.10, abs=0.01)
        assert aapl["walk_forward"]["mean"]["f1_macro"] == pytest.approx(0.60, abs=0.01)


# ─────────────────────────────────────────────────────────────────────
# _get_global_feature_columns — régime features
# ─────────────────────────────────────────────────────────────────────

class TestGlobalModelRegimeFeatures:
    def test_regime_columns_included(self) -> None:
        """Le Global Model doit inclure les flags de régime pour les splits conditionnels."""
        from modelFactory.global_model import _get_global_feature_columns
        from modelFactory.config import TrainingConfig
        from dataclasses import replace

        cfg = TrainingConfig()
        cfg = replace(cfg,
            data=replace(cfg.data, enable_cross_sectional_features=True),
            global_model=replace(cfg.global_model, use_cross_sectional_features=True),
        )
        cols = _get_global_feature_columns(cfg)
        assert "regime_bull_market" in cols
        assert "regime_risk_off" in cols

    def test_regime_columns_at_end(self) -> None:
        """Les colonnes régime sont ajoutées en dernier, après les autres features."""
        from modelFactory.global_model import _get_global_feature_columns
        from modelFactory.config import TrainingConfig
        from dataclasses import replace

        cfg = TrainingConfig()
        cfg = replace(cfg,
            data=replace(cfg.data, enable_cross_sectional_features=True),
            global_model=replace(cfg.global_model, use_cross_sectional_features=True),
        )
        cols = _get_global_feature_columns(cfg)
        assert cols[-2] == "regime_bull_market"
        assert cols[-1] == "regime_risk_off"

    def test_regime_included_even_without_cross_sectional(self) -> None:
        """Même sans cross-sectional activé, les colonnes régime sont incluses."""
        from modelFactory.global_model import _get_global_feature_columns
        from modelFactory.config import TrainingConfig

        cfg = TrainingConfig()
        cols = _get_global_feature_columns(cfg)
        assert "regime_bull_market" in cols
        assert "regime_risk_off" in cols


# ─────────────────────────────────────────────────────────────────────
# Sample weighting par récence (Global Model)
# ─────────────────────────────────────────────────────────────────────

class TestGlobalModelSampleWeight:
    def test_weight_formula_half_life(self) -> None:
        """Demi-vie = 365 jours : un point à t-365 pèse 1/e ≈ 0.368."""
        days_diff = np.array([0, 365, 730], dtype=np.float64)
        weights = np.exp(-days_diff / 365.0)
        assert weights[0] == pytest.approx(1.0, abs=0.001)
        assert weights[1] == pytest.approx(1.0 / np.e, abs=0.001)
        assert weights[2] == pytest.approx(1.0 / (np.e * np.e), abs=0.001)

    def test_weight_monotonic_decay(self) -> None:
        """Plus la date est ancienne, plus le poids est faible."""
        days_diff = np.array([0, 30, 180, 365, 730], dtype=np.float64)
        weights = np.exp(-days_diff / 365.0)
        for i in range(len(weights) - 1):
            assert weights[i] > weights[i + 1], (
                f"weight[{i}]={weights[i]:.4f} <= weight[{i+1}]={weights[i+1]:.4f}"
            )

    def test_weight_range(self) -> None:
        """Les poids sont toujours dans [0, 1]."""
        days_diff = np.array([0, 1, 100, 500, 1000, 2000], dtype=np.float64)
        weights = np.exp(-days_diff / 365.0)
        assert np.all(weights >= 0.0)
        assert np.all(weights <= 1.0)
        assert weights[0] == pytest.approx(1.0, abs=0.001)


# ─────────────────────────────────────────────────────────────────────
# Stacking ternaire — 3 probas extraites
# ─────────────────────────────────────────────────────────────────────

class TestGlobalModelTernaryStacking:
    def test_ternary_proba_extraction_order(self) -> None:
        """Simule predict_proba ternaire et vérifie l'extraction short/flat/long."""
        raw_proba = np.array([
            [0.10, 0.30, 0.60],  # confiant long
            [0.70, 0.20, 0.10],  # confiant short
            [0.25, 0.50, 0.25],  # confiant flat
        ], dtype=np.float64)

        is_ternary = True
        num_val_cols = 3

        if is_ternary and num_val_cols >= 3:
            proba_short = raw_proba[:, 0]
            proba_flat = raw_proba[:, 1]
            proba_long = raw_proba[:, 2]
        else:
            proba_long = raw_proba[:, -1]
            proba_short = 1.0 - proba_long
            proba_flat = np.float64(0.0)

        np.testing.assert_array_almost_equal(proba_short, [0.10, 0.70, 0.25])
        np.testing.assert_array_almost_equal(proba_flat, [0.30, 0.20, 0.50])
        np.testing.assert_array_almost_equal(proba_long, [0.60, 0.10, 0.25])

    def test_binary_fallback_produces_three_columns(self) -> None:
        """Fallback binaire : short=1-p, flat=0, long=p."""
        raw_proba = np.array([[0.30], [0.70], [0.50]], dtype=np.float64)
        is_ternary = False
        num_val_cols = 1

        if is_ternary and num_val_cols >= 3:
            proba_short = raw_proba[:, 0]
            proba_flat = raw_proba[:, 1]
            proba_long = raw_proba[:, 2]
        else:
            proba_long = raw_proba[:, -1]
            proba_short = 1.0 - proba_long
            proba_flat = np.float64(0.0)

        np.testing.assert_array_almost_equal(proba_short, [0.70, 0.30, 0.50])
        np.testing.assert_array_almost_equal(proba_flat, [0.0, 0.0, 0.0])
        np.testing.assert_array_almost_equal(proba_long, [0.30, 0.70, 0.50])

    def test_probas_sum_to_one_in_ternary(self) -> None:
        """En ternaire, P(short) + P(flat) + P(long) ≈ 1."""
        rng = np.random.default_rng(42)
        raw = rng.random((100, 3))
        raw = raw / raw.sum(axis=1, keepdims=True)

        proba_short = raw[:, 0]
        proba_flat = raw[:, 1]
        proba_long = raw[:, 2]

        total = proba_short + proba_flat + proba_long
        np.testing.assert_array_almost_equal(total, np.ones(100), decimal=5)


# ─────────────────────────────────────────────────────────────────────
# train_global_model_wf — tests d'intégration légère (sans DB)
# ─────────────────────────────────────────────────────────────────────

class TestTrainGlobalModelWf:
    """Tests qui vérifient la logique sans base de données (monkeypatch)."""

    def test_skips_when_disabled(self) -> None:
        from modelFactory.global_model import train_global_model_wf
        from modelFactory.config import TrainingConfig

        cfg = TrainingConfig()
        # Global model désactivé par défaut
        result = train_global_model_wf([], cfg, artifacts_dir=Path("."), engine=None)
        assert result["status"] == "skipped"
        assert result["reason"] == "disabled"

    def test_skips_when_insufficient_symbols(self, monkeypatch) -> None:
        """Avec 1 seul symbole, le global model n'a pas de sens."""
        from modelFactory.global_model import train_global_model_wf
        from modelFactory.config import TrainingConfig, GlobalModelConfig

        # Monkeypatch pour éviter l'appel DB même si enabled=True
        monkeypatch.setattr(
            "modelFactory.global_model.load_universe_latest_bar_date",
            lambda *a, **kw: None,
        )
        monkeypatch.setattr(
            "modelFactory.global_model.load_universe_bars",
            lambda *a, **kw: pd.DataFrame(),
        )

        cfg = TrainingConfig(global_model=GlobalModelConfig(enabled=True))
        result = train_global_model_wf(["AAPL"], cfg, artifacts_dir=Path("."), engine="mock")
        assert result["status"] == "skipped"
        assert result["reason"] == "insufficient_symbols"
