from __future__ import annotations

import numpy as np
import pandas as pd
from types import SimpleNamespace

from modelFactory.config import BaselineConfig, CalibrationConfig, DataConfig, TargetOptimizationConfig, TrainingConfig, WalkForwardConfig
from modelFactory.lightgbm_baseline import run_lightgbm_baseline


class FakePickleableLGBMClassifier:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        # Phase 4.2.c — un Booster natif (fake) accessible via .booster_
        self.booster_ = _FakeBooster()

    def fit(self, X, y):
        return self

    def predict_proba(self, X):
        p = np.clip(np.asarray(X["daily_return"], dtype=float), 0.05, 0.95)
        return np.column_stack([1.0 - p, p])


class _FakeBooster:
    def save_model(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# fake LightGBM model (test fixture)\n")


def _prepared_df(n: int = 120) -> pd.DataFrame:
    x = np.linspace(0.0, 1.0, n)
    target = (x > 0.45).astype(float)
    future_return = np.where(target == 1.0, 0.03, -0.01)
    return pd.DataFrame(
        {
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
            "target": target,
            "future_return": future_return,
        }
    )


def test_run_lightgbm_baseline_returns_metrics(monkeypatch) -> None:
    class FakeModel:
        def fit(self, X, y):
            return self

        def predict_proba(self, X):
            p = np.clip(np.asarray(X["daily_return"], dtype=float), 0.05, 0.95)
            return np.column_stack([1.0 - p, p])

    class FakeLGB:
        class LGBMClassifier:
            def __init__(self, **kwargs):
                self.model = FakeModel()

            def fit(self, X, y):
                return self.model.fit(X, y)

            def predict_proba(self, X):
                return self.model.predict_proba(X)

    monkeypatch.setattr("modelFactory.lightgbm_baseline._import_lightgbm", lambda: FakeLGB)

    cfg = TrainingConfig(
        data=DataConfig(),
        calibration=CalibrationConfig(method="none"),
        walk_forward=WalkForwardConfig(),
        baseline=BaselineConfig(enabled=True),
        target_optimization=TargetOptimizationConfig(),
    )

    result = run_lightgbm_baseline(_prepared_df(), cfg)

    assert result["status"] == "completed"
    assert result["model_name"] == "lightgbm"
    assert "bucket_analysis" in result["test"]
    assert "threshold_optimization" in result
    assert "selection_score" in result


def test_run_lightgbm_baseline_can_persist_local_artifacts(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "modelFactory.lightgbm_baseline._import_lightgbm",
        lambda: SimpleNamespace(LGBMClassifier=FakePickleableLGBMClassifier),
    )

    cfg = TrainingConfig(
        data=DataConfig(),
        calibration=CalibrationConfig(method="none"),
        walk_forward=WalkForwardConfig(),
        baseline=BaselineConfig(enabled=True),
        target_optimization=TargetOptimizationConfig(),
    )

    result = run_lightgbm_baseline(_prepared_df(), cfg, artifact_dir=tmp_path)

    assert result["inference_backend"] == "lightgbm_tabular"
    # Phase 4.2.c — format natif (.txt) au lieu de pickle.
    assert result["artifact_paths"]["model_path"].endswith("lightgbm_model.txt")
    assert result["artifact_paths"]["model_format"] == "txt"
    assert (tmp_path / "lightgbm_model.txt").exists()
    assert not (tmp_path / "lightgbm_model.pkl").exists()


