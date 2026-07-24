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
	ternary_policy: "TernaryDecisionPolicy | None" = None,
) -> dict[str, Any]:
	if not cfg.baseline.enable_catboost:
		return {}

	try:
		CatBoostClassifier = _import_catboost()
	except ImportError:
		LOGGER.warning("CatBoost indisponible: baseline ignorée")
		return {"status": "unavailable", "model_name": "catboost", "reason": "catboost_not_installed"}

	artifact_scope = artifact_dir.name if artifact_dir is not None else "__BENCHMARK__"
	catboost_run_root = (Path(cfg.catboost_artifacts_dir) / artifact_scope).resolve()
	catboost_run_root.mkdir(parents=True, exist_ok=True)

	return run_tabular_baseline(
		prepared_df,
		cfg,
		model_name="catboost",
		model_builder=lambda resolved_seed: CatBoostClassifier(
			depth=cfg.baseline.catboost_depth,
			iterations=cfg.baseline.catboost_iterations,
			learning_rate=cfg.baseline.catboost_learning_rate,
			random_seed=resolved_seed,
			loss_function="MultiClass" if cfg.data.target_mode == "ternary" else "Logloss",
			verbose=False,
			train_dir=str(catboost_run_root / f"seed_{resolved_seed}"),
			allow_writing_files=True,
			auto_class_weights="Balanced",
		),
		artifact_dir=artifact_dir,
		# Phase 4.2.c — format natif CatBoost (.cbm). Plus de pickle.
		save_callback=lambda model, path: model.save_model(str(path)),
		model_extension=".cbm",
		ternary_policy=ternary_policy,
	)


