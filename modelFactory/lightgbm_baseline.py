"""modelFactory/lightgbm_baseline.py — Baseline tabulaire LightGBM pour comparaison au LSTM."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from modelFactory.config import TrainingConfig
from modelFactory.tabular_baseline import run_tabular_baseline

LOGGER = logging.getLogger(__name__)


def _import_lightgbm() -> Any:
    import lightgbm as lgb  # type: ignore[import-not-found]

    return lgb


def run_lightgbm_baseline(
    prepared_df: pd.DataFrame,
    cfg: TrainingConfig,
    *,
    artifact_dir: Path | None = None,
) -> dict[str, Any]:
    if not cfg.baseline.enabled:
        return {}

    try:
        lgb = _import_lightgbm()
    except ImportError:
        LOGGER.warning("LightGBM indisponible: baseline ignorée")
        return {"status": "unavailable", "model_name": "lightgbm", "reason": "lightgbm_not_installed"}

    return run_tabular_baseline(
        prepared_df,
        cfg,
        model_name="lightgbm",
        model_builder=lambda resolved_seed: lgb.LGBMClassifier(
            objective="binary",
            max_depth=cfg.baseline.max_depth,
            n_estimators=cfg.baseline.n_estimators,
            learning_rate=cfg.baseline.learning_rate,
            random_state=resolved_seed,
        ),
        artifact_dir=artifact_dir,
        # Phase 4.2.c — format natif LightGBM (.txt). Plus de pickle.
        save_callback=lambda model, path: model.booster_.save_model(str(path)),
        model_extension=".txt",
    )

