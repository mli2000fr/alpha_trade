from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from modelFactory.config import DataConfig, GlobalModelConfig, ModelConfig, TrainingConfig
from modelFactory.global_model import train_global_model


class _FakeEngine:
	"""Engine SQLAlchemy stub minimal pour les tests train_global_model.

	S10.4 — remplace `engine=object()` qui ne supportait ni `.connect()`
	(load_universe_latest_bar_date) ni les opérations ORM aval.
	"""

	def connect(self):
		import contextlib

		@contextlib.contextmanager
		def _ctx():
			yield self

		return _ctx()

	def execute(self, *args, **kwargs):
		class _Result:
			def scalar(self_inner):
				return None

			def fetchall(self_inner):
				return []

		return _Result()

	def begin(self):
		return self.connect()


class PickleableFakeGlobalEstimator:
	def fit(self, X, y):
		return self

	def predict_proba(self, X):
		values = np.asarray(X.iloc[:, 0], dtype=float)
		p = np.clip(0.5 + 0.1 * np.tanh(values), 0.05, 0.95)
		return np.column_stack([1.0 - p, p])


def _bars(symbol: str, base: float, n: int = 260) -> pd.DataFrame:
	steps = np.arange(n, dtype=float)
	close = pd.Series(base + 5.0 * np.sin(steps * 0.25) + 0.03 * steps, dtype=float)
	return pd.DataFrame(
		{
			"symbol": [symbol] * n,
			"date": pd.date_range("2020-01-01", periods=n, freq="D"),
			"open": close * 0.99,
			"high": close * 1.01,
			"low": close * 0.98,
			"close": close,
			"volume": np.linspace(1_000_000, 1_200_000, n),
			"adj_close": close,
			"vwap": close,
			"daily_return": 0.0,
			"is_filled": 0,
		}
	)


def test_train_global_model_returns_metrics_and_artifacts(monkeypatch, tmp_path: Path) -> None:
	universe = pd.concat([_bars("AAPL", 100.0), _bars("MSFT", 120.0), _bars("NVDA", 150.0)], ignore_index=True)
	benchmark = _bars("SPY", 90.0)

	monkeypatch.setattr("modelFactory.global_model.load_universe_bars", lambda engine, symbols, **kwargs: universe.copy())
	monkeypatch.setattr("modelFactory.global_model.load_benchmark_bars", lambda engine, benchmark_symbol, **kwargs: benchmark.copy())
	monkeypatch.setattr(
		"modelFactory.global_model.load_universe_latest_bar_date",
		lambda engine, symbols, **kwargs: pd.Timestamp("2020-09-15"),
	)
	monkeypatch.setattr(
		"modelFactory.global_model._import_lightgbm",
		lambda: type("FakeLGB", (), {"LGBMClassifier": staticmethod(lambda **kwargs: PickleableFakeGlobalEstimator())})(),
	)

	cfg = TrainingConfig(
		data=DataConfig(feature_set="v1", benchmark_symbol="SPY", min_history_days=80),
		model=ModelConfig(max_epochs=1),
		global_model=GlobalModelConfig(enabled=True, model_name="lightgbm", artifact_symbol="__GLOBAL__"),
		artifacts_dir=tmp_path,
		accelerator="cpu",
	)

	result = train_global_model(["AAPL", "MSFT", "NVDA"], cfg, artifacts_dir=tmp_path, engine=_FakeEngine())

	assert result["status"] == "completed", result
	assert result["backend_model_name"] == "lightgbm"
	assert "AAPL" in result["by_symbol"]
	assert (tmp_path / "__GLOBAL__" / "global_model.pkl").exists()
	with open(tmp_path / "__GLOBAL__" / "config.json", encoding="utf-8") as fh:
		config_data = json.load(fh)
	assert config_data["architecture_selected"] == "global_model"
	assert config_data["feature_contract"]["feature_columns"] == result["feature_columns"]
	assert config_data["reproducibility"]["resolved_seed"] == result["seed"]
	assert result["feature_contract"]["feature_fingerprint"] == result["feature_fingerprint"]





