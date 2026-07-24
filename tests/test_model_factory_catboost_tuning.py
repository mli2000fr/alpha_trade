"""Tests unitaires pour les paramètres de tuning CatBoost (Sprint 2026-07-24).

Vérifie que :
- BaselineConfig accepte et valide les nouveaux champs catboost_*
- Le constructeur CatBoostClassifier reçoit bien les paramètres de tuning
- Les valeurs par défaut sont correctes
"""
from __future__ import annotations

import numpy as np
import pytest

from modelFactory.config import BaselineConfig


class TestBaselineConfigCatboostTuning:
    """Validation des nouveaux champs CatBoost dans BaselineConfig."""

    def test_defaults_are_sensible(self) -> None:
        """Les défauts recommandés sont appliqués."""
        cfg = BaselineConfig()
        assert cfg.catboost_l2_leaf_reg == 3.0
        assert cfg.catboost_border_count == 254
        assert cfg.catboost_random_strength == 1.0
        assert cfg.catboost_bagging_temperature == 1.0
        assert cfg.catboost_od_type == "IncToDec"
        assert cfg.catboost_od_wait == 20

    def test_can_set_tuning_values(self) -> None:
        """On peut fixer des valeurs de tuning via le constructeur."""
        cfg = BaselineConfig(
            catboost_l2_leaf_reg=5.0,
            catboost_border_count=128,
            catboost_random_strength=2.0,
            catboost_bagging_temperature=0.5,
            catboost_od_type="Iter",
            catboost_od_wait=40,
        )
        assert cfg.catboost_l2_leaf_reg == 5.0
        assert cfg.catboost_border_count == 128
        assert cfg.catboost_random_strength == 2.0
        assert cfg.catboost_bagging_temperature == 0.5
        assert cfg.catboost_od_type == "Iter"
        assert cfg.catboost_od_wait == 40

    def test_l2_leaf_reg_negative_raises(self) -> None:
        """l2_leaf_reg < 0 est invalide."""
        with pytest.raises(ValueError, match="catboost_l2_leaf_reg"):
            BaselineConfig(catboost_l2_leaf_reg=-1.0)

    def test_border_count_out_of_bounds_raises(self) -> None:
        """border_count doit être dans [1, 255]."""
        with pytest.raises(ValueError, match="catboost_border_count"):
            BaselineConfig(catboost_border_count=0)
        with pytest.raises(ValueError, match="catboost_border_count"):
            BaselineConfig(catboost_border_count=256)

    def test_od_type_invalid_raises(self) -> None:
        """od_type doit être IncToDec ou Iter."""
        with pytest.raises(ValueError, match="catboost_od_type"):
            BaselineConfig(catboost_od_type="Invalid")

    def test_od_wait_negative_raises(self) -> None:
        """od_wait doit être >= 1."""
        with pytest.raises(ValueError, match="catboost_od_wait"):
            BaselineConfig(catboost_od_wait=0)

    def test_frozen_dataclass(self) -> None:
        """BaselineConfig est immutable."""
        cfg = BaselineConfig(catboost_od_wait=40)
        with pytest.raises(Exception):
            cfg.catboost_od_wait = 20  # type: ignore[misc]


class TestCatboostClassifierReceivesTuningParams:
    """Vérifie que les paramètres de tuning sont bien transmis au classifieur."""

    def test_catboost_baseline_passes_tuning_params(self, monkeypatch) -> None:
        """run_catboost_baseline passe les params tuning à CatBoostClassifier."""
        captured_kwargs: dict = {}

        class FakeCatBoostClassifier:
            def __init__(self, **kwargs):
                nonlocal captured_kwargs
                captured_kwargs = kwargs

            def fit(self, X, y, sample_weight=None):
                return self

            def predict_proba(self, X):
                n = len(X)
                p = np.full(n, 0.5)
                return np.column_stack([p, p, p])

        def _fake_import_catboost():
            return FakeCatBoostClassifier

        monkeypatch.setattr(
            "modelFactory.catboost_baseline._import_catboost",
            _fake_import_catboost,
        )

        from modelFactory.config import (
            CalibrationConfig,
            DataConfig,
            TrainingConfig,
            WalkForwardConfig,
        )
        from modelFactory.catboost_baseline import run_catboost_baseline

        import pandas as pd

        n = 120
        x = np.linspace(0, 1, n)
        df = pd.DataFrame({
            "daily_return": x,
            "log_return": x,
            "intraday_range": x,
            "overnight_gap": x,
            "close_to_vwap": x,
            "volume_ratio_20": x,
            "rolling_volatility_20": x + 0.01,
            "rolling_volatility_60": x + 0.02,
            "rolling_mean_return_5": x,
            "rolling_mean_return_20": x,
            "rsi_14": x * 100,
            "atr_14_norm": x + 0.01,
            "is_filled": np.zeros(n),
            "target": ((x > 0.4).astype(int) - 1),
            "future_return": x * 0.05 - 0.025,
        })

        cfg = TrainingConfig(
            data=DataConfig(target_mode="ternary", target_up_threshold=0.03, target_down_threshold=-0.03),
            calibration=CalibrationConfig(method="none"),
            walk_forward=WalkForwardConfig(enabled=False),
            baseline=BaselineConfig(
                enabled=True,
                enable_catboost=True,
                catboost_l2_leaf_reg=5.0,
                catboost_border_count=128,
                catboost_random_strength=2.0,
                catboost_bagging_temperature=0.5,
                catboost_od_type="Iter",
                catboost_od_wait=40,
            ),
        )

        run_catboost_baseline(df, cfg)

        assert captured_kwargs["l2_leaf_reg"] == 5.0
        assert captured_kwargs["border_count"] == 128
        assert captured_kwargs["random_strength"] == 2.0
        assert captured_kwargs["bagging_temperature"] == 0.5
        assert captured_kwargs["od_type"] == "Iter"
        assert captured_kwargs["od_wait"] == 40
        assert captured_kwargs["auto_class_weights"] == "Balanced"
