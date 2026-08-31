"""Tests unitaires pour les paramètres de tuning LightGBM (Sprint 2026-07-24).

Vérifie que :
- BaselineConfig accepte et valide les nouveaux champs lgbm_*
- Le constructeur LGBMClassifier reçoit bien les paramètres de tuning
- Les valeurs par défaut sont sans effet (compatibilité)
"""
from __future__ import annotations

import numpy as np
import pytest

from modelFactory.config import BaselineConfig


class TestBaselineConfigLgbmTuning:
    """Validation des nouveaux champs LightGBM dans BaselineConfig."""

    def test_defaults_are_backward_compatible(self) -> None:
        """Les défauts de régularisation restent explicitement verrouillés."""
        cfg = BaselineConfig()
        assert cfg.lgbm_reg_alpha == 0.1
        assert cfg.lgbm_reg_lambda == 0.1
        assert cfg.lgbm_min_child_samples == 150
        assert cfg.lgbm_subsample == 0.8
        assert cfg.lgbm_colsample_bytree == 0.7

    def test_can_set_tuning_values(self) -> None:
        """On peut fixer des valeurs de tuning via le constructeur."""
        cfg = BaselineConfig(
            lgbm_reg_alpha=0.1,
            lgbm_reg_lambda=0.5,
            lgbm_min_child_samples=50,
            lgbm_subsample=0.8,
            lgbm_colsample_bytree=0.7,
        )
        assert cfg.lgbm_reg_alpha == 0.1
        assert cfg.lgbm_reg_lambda == 0.5
        assert cfg.lgbm_min_child_samples == 50
        assert cfg.lgbm_subsample == 0.8
        assert cfg.lgbm_colsample_bytree == 0.7

    def test_reg_alpha_negative_raises(self) -> None:
        """reg_alpha < 0 est invalide."""
        with pytest.raises(ValueError, match="lgbm_reg_alpha"):
            BaselineConfig(lgbm_reg_alpha=-0.1)

    def test_subsample_out_of_bounds_raises(self) -> None:
        """subsample doit être dans ]0, 1]."""
        with pytest.raises(ValueError, match="lgbm_subsample"):
            BaselineConfig(lgbm_subsample=0.0)
        with pytest.raises(ValueError, match="lgbm_subsample"):
            BaselineConfig(lgbm_subsample=1.1)

    def test_frozen_dataclass(self) -> None:
        """BaselineConfig est immutable."""
        cfg = BaselineConfig(lgbm_reg_alpha=0.1)
        with pytest.raises(Exception):  # FrozenInstanceError ou équivalent
            cfg.lgbm_reg_alpha = 0.2  # type: ignore[misc]


class TestLgbmClassifierReceivesTuningParams:
    """Vérifie que les paramètres de tuning sont bien transmis au classifieur."""

    def test_lightgbm_baseline_passes_tuning_params(self, monkeypatch) -> None:
        """run_lightgbm_baseline passe les params tuning à LGBMClassifier."""
        captured_kwargs: dict = {}

        class FakeLGB:
            class LGBMClassifier:
                def __init__(self, **kwargs):
                    nonlocal captured_kwargs
                    captured_kwargs = kwargs

                def fit(self, X, y, sample_weight=None):
                    return self

                def predict_proba(self, X):
                    n = len(X)
                    p = np.full(n, 0.5)
                    return np.column_stack([p, p, p])  # 3 classes ternaire

        monkeypatch.setattr("modelFactory.lightgbm_baseline._import_lightgbm", lambda: FakeLGB)

        from modelFactory.config import (
            CalibrationConfig,
            DataConfig,
            TrainingConfig,
            WalkForwardConfig,
        )
        from modelFactory.lightgbm_baseline import run_lightgbm_baseline

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
            "target": ((x > 0.4).astype(int) - 1),  # ternary: -1, 0, 1
            "future_return": x * 0.05 - 0.025,
        })

        cfg = TrainingConfig(
            data=DataConfig(target_mode="ternary", target_up_threshold=0.03, target_down_threshold=-0.03),
            calibration=CalibrationConfig(method="none"),
            walk_forward=WalkForwardConfig(enabled=False),
            baseline=BaselineConfig(
                enabled=True,
                model_name="lightgbm",
                lgbm_reg_alpha=0.1,
                lgbm_reg_lambda=0.5,
                lgbm_min_child_samples=50,
                lgbm_subsample=0.8,
                lgbm_colsample_bytree=0.7,
            ),
        )

        run_lightgbm_baseline(df, cfg)

        assert captured_kwargs["reg_alpha"] == 0.1
        assert captured_kwargs["reg_lambda"] == 0.5
        assert captured_kwargs["min_child_samples"] == 50
        assert captured_kwargs["subsample"] == 0.8
        assert captured_kwargs["colsample_bytree"] == 0.7
        assert captured_kwargs["class_weight"] == "balanced"
