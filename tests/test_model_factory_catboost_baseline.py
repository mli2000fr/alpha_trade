from __future__ import annotations

import numpy as np
import pandas as pd

from modelFactory.catboost_baseline import run_catboost_baseline
from modelFactory.config import BaselineConfig, CalibrationConfig, DataConfig, TargetOptimizationConfig, TrainingConfig, WalkForwardConfig


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


def test_run_catboost_baseline_returns_unavailable_when_package_missing(monkeypatch) -> None:
	def _raise_import_error():
		raise ImportError("catboost missing")

	monkeypatch.setattr("modelFactory.catboost_baseline._import_catboost", _raise_import_error)

	cfg = TrainingConfig(
		data=DataConfig(),
		calibration=CalibrationConfig(method="none"),
		walk_forward=WalkForwardConfig(),
		baseline=BaselineConfig(enabled=True, enable_catboost=True),
		target_optimization=TargetOptimizationConfig(),
	)

	result = run_catboost_baseline(_prepared_df(), cfg)

	assert result["status"] == "unavailable"
	assert result["model_name"] == "catboost"


def test_run_catboost_baseline_returns_metrics(monkeypatch) -> None:
	class FakeModel:
		def fit(self, X, y):
			return self

		def predict_proba(self, X):
			p = np.clip(np.asarray(X["daily_return"], dtype=float), 0.05, 0.95)
			return np.column_stack([1.0 - p, p])

	monkeypatch.setattr("modelFactory.catboost_baseline._import_catboost", lambda: lambda **kwargs: FakeModel())

	cfg = TrainingConfig(
		data=DataConfig(),
		calibration=CalibrationConfig(method="none"),
		walk_forward=WalkForwardConfig(),
		baseline=BaselineConfig(enabled=True, enable_catboost=True),
		target_optimization=TargetOptimizationConfig(),
	)

	result = run_catboost_baseline(_prepared_df(), cfg)

	assert result["status"] == "completed"
	assert result["model_name"] == "catboost"
	assert "bucket_analysis" in result["test"]
	assert "threshold_optimization" in result
	assert "selection_score" in result


