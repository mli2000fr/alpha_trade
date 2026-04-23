"""modelFactory/catboost_baseline.py — Challenger tabulaire CatBoost pour comparaison au LSTM."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from modelFactory.config import TrainingConfig
from modelFactory.tabular_baseline import run_tabular_baseline

LOGGER = logging.getLogger(__name__)


def _import_catboost() -> Any:
	from catboost import CatBoostClassifier  # type: ignore[import-not-found]

	return CatBoostClassifier


def run_catboost_baseline(
	prepared_df: pd.DataFrame,
	cfg: TrainingConfig,
	*,
	artifact_dir: Path | None = None,
) -> dict[str, Any]:
	if not cfg.baseline.enable_catboost:
		return {}

	try:
		CatBoostClassifier = _import_catboost()
	except ImportError:
		LOGGER.warning("CatBoost indisponible: baseline ignorée")
		return {"status": "unavailable", "model_name": "catboost", "reason": "catboost_not_installed"}

	return run_tabular_baseline(
		prepared_df,
		cfg,
		model_name="catboost",
		model_builder=lambda: CatBoostClassifier(
			depth=cfg.baseline.catboost_depth,
			iterations=cfg.baseline.catboost_iterations,
			learning_rate=cfg.baseline.catboost_learning_rate,
			random_seed=cfg.baseline.random_state,
			loss_function="Logloss",
			verbose=False,
		),
		artifact_dir=artifact_dir,
	)


