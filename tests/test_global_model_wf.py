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
    def test_column_name(self) -> None:
        assert GLOBAL_PRED_FEATURE_COLUMNS == ["global_pred_long"]

    def test_is_list_of_strings(self) -> None:
        for col in GLOBAL_PRED_FEATURE_COLUMNS:
            assert isinstance(col, str)
            assert len(col) > 0


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
