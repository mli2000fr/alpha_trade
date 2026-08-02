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
	from catboost import CatBoostClassifier, CatBoostRegressor  # type: ignore[import-not-found]
	return CatBoostClassifier, CatBoostRegressor


def run_catboost_baseline(
	prepared_df: pd.DataFrame,
	cfg: TrainingConfig,
	*,
	artifact_dir: Path | None = None,
	ternary_policy: "TernaryDecisionPolicy | None" = None,
) -> dict[str, Any]:
	if not cfg.baseline.enable_catboost:
		return {}

	try:
		CatBoostClassifier, CatBoostRegressor = _import_catboost()
	except ImportError:
		LOGGER.warning("CatBoost indisponible: baseline ignorée")
		return {"status": "unavailable", "model_name": "catboost", "reason": "catboost_not_installed"}

	artifact_scope = artifact_dir.name if artifact_dir is not None else "__BENCHMARK__"
	catboost_run_root = (Path(cfg.catboost_artifacts_dir) / artifact_scope).resolve()
	catboost_run_root.mkdir(parents=True, exist_ok=True)

	is_regression = cfg.data.target_mode == "regression"

	if is_regression:
		_CBClass = CatBoostRegressor
		_loss = "RMSE"
		_auto_weights = None
	else:
		_CBClass = CatBoostClassifier
		_loss = "MultiClass" if cfg.data.target_mode == "ternary" else "Logloss"
		_auto_weights = "Balanced"

	return run_tabular_baseline(
		prepared_df,
		cfg,
		model_name="catboost",
		model_builder=lambda resolved_seed: _CBClass(
			depth=cfg.baseline.catboost_depth,
			iterations=cfg.baseline.catboost_iterations,
			learning_rate=cfg.baseline.catboost_learning_rate,
			random_seed=resolved_seed,
			loss_function=_loss,
			verbose=False,
			train_dir=str(catboost_run_root / f"seed_{resolved_seed}"),
			allow_writing_files=True,
			auto_class_weights=_auto_weights,
			l2_leaf_reg=cfg.baseline.catboost_l2_leaf_reg,
			border_count=cfg.baseline.catboost_border_count,
			random_strength=cfg.baseline.catboost_random_strength,
			bagging_temperature=cfg.baseline.catboost_bagging_temperature,
			od_type=cfg.baseline.catboost_od_type,
			od_wait=cfg.baseline.catboost_od_wait,
		),
		artifact_dir=artifact_dir,
		# Phase 4.2.c — format natif CatBoost (.cbm). Plus de pickle.
		save_callback=lambda model, path: model.save_model(str(path)),
		model_extension=".cbm",
		ternary_policy=ternary_policy,
	)


