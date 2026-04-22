"""modelFactory/lightgbm_baseline.py — Baseline tabulaire LightGBM pour comparaison au LSTM."""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from modelFactory.calibration import PlattCalibrator
from modelFactory.config import TrainingConfig
from modelFactory.evaluation import bucket_analysis
from modelFactory.features import get_feature_columns

LOGGER = logging.getLogger(__name__)


def _import_lightgbm() -> Any:
    import lightgbm as lgb  # type: ignore[import-not-found]

    return lgb


def _tabular_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if "target" not in df.columns:
        raise ValueError("LightGBM baseline attend une colonne 'target'.")
    clean = df.loc[df["target"].notna()].reset_index(drop=True)
    n = len(clean)
    i_train = int(n * 0.70)
    i_val = i_train + int(n * 0.15)
    return clean.iloc[:i_train].reset_index(drop=True), clean.iloc[i_train:i_val].reset_index(drop=True), clean.iloc[i_val:].reset_index(drop=True)


def _binary_auc(labels: np.ndarray, scores: np.ndarray) -> float | None:
    labels = np.asarray(labels, dtype=np.int64)
    scores = np.asarray(scores, dtype=np.float64)
    n_pos = int((labels == 1).sum())
    n_neg = int((labels == 0).sum())
    if n_pos == 0 or n_neg == 0:
        return None
    order = np.argsort(scores)
    sorted_scores = scores[order]
    ranks = np.empty(len(scores), dtype=np.float64)
    i = 0
    while i < len(sorted_scores):
        j = i
        while j + 1 < len(sorted_scores) and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        avg_rank = (i + j + 2) / 2.0
        ranks[order[i:j + 1]] = avg_rank
        i = j + 1
    sum_pos = ranks[labels == 1].sum()
    return float((sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def _expected_calibration_error(labels: np.ndarray, proba: np.ndarray, n_bins: int = 10) -> float:
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        left, right = edges[i], edges[i + 1]
        mask = (proba >= left) & (proba <= right) if i == n_bins - 1 else (proba >= left) & (proba < right)
        if not np.any(mask):
            continue
        ece += mask.mean() * abs(float(labels[mask].mean()) - float(proba[mask].mean()))
    return float(ece)


def _compute_metrics(labels: np.ndarray, proba: np.ndarray, future_returns: np.ndarray, decision_threshold: float) -> dict[str, Any]:
    pred = (proba >= decision_threshold).astype(np.int64)
    tp = int(((pred == 1) & (labels == 1)).sum())
    fp = int(((pred == 1) & (labels == 0)).sum())
    fn = int(((pred == 0) & (labels == 1)).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return {
        "directional_accuracy": float((pred == labels).mean()),
        "precision": float(precision),
        "recall": float(recall),
        "auc": _binary_auc(labels, proba),
        "brier_score": float(np.mean((proba - labels) ** 2)),
        "ece": _expected_calibration_error(labels, proba),
        "action_rate": float(pred.mean()),
        "bucket_analysis": bucket_analysis(proba, labels, future_returns, n_buckets=5),
    }


def run_lightgbm_baseline(prepared_df: pd.DataFrame, cfg: TrainingConfig) -> dict[str, Any]:
    if not cfg.baseline.enabled:
        return {}

    try:
        lgb = _import_lightgbm()
    except ImportError:
        LOGGER.warning("LightGBM indisponible: baseline ignorée")
        return {"status": "unavailable", "reason": "lightgbm_not_installed"}

    feature_columns = get_feature_columns(
        include_sentiment=cfg.data.include_sentiment_features,
        feature_set=cfg.data.feature_set,
    )
    train_df, val_df, test_df = _tabular_split(prepared_df)
    if train_df.empty or val_df.empty or test_df.empty:
        return {"status": "skipped", "reason": "insufficient_rows_after_split"}

    model = lgb.LGBMClassifier(
        objective="binary",
        max_depth=cfg.baseline.max_depth,
        n_estimators=cfg.baseline.n_estimators,
        learning_rate=cfg.baseline.learning_rate,
        random_state=cfg.baseline.random_state,
    )
    model.fit(train_df[feature_columns], train_df["target"].astype(int))

    val_raw = model.predict_proba(val_df[feature_columns])[:, 1]
    calibrator = None
    if cfg.calibration.method == "platt" and len(np.unique(val_df["target"].astype(int))) > 1 and len(val_df) >= cfg.calibration.min_samples:
        eps = 1e-6
        margins = np.log(np.clip(val_raw, eps, 1 - eps) / np.clip(1 - val_raw, eps, 1 - eps))
        calibrator = PlattCalibrator(max_iter=cfg.calibration.max_iter).fit(margins, val_df["target"].astype(int).to_numpy())

    val_proba = val_raw
    test_raw = model.predict_proba(test_df[feature_columns])[:, 1]
    test_proba = test_raw
    if calibrator is not None and calibrator.fitted:
        eps = 1e-6
        val_margin = np.log(np.clip(val_raw, eps, 1 - eps) / np.clip(1 - val_raw, eps, 1 - eps))
        test_margin = np.log(np.clip(test_raw, eps, 1 - eps) / np.clip(1 - test_raw, eps, 1 - eps))
        val_proba = calibrator.predict_proba(val_margin)
        test_proba = calibrator.predict_proba(test_margin)

    return {
        "status": "completed",
        "model_name": "lightgbm",
        "feature_columns": feature_columns,
        "val": _compute_metrics(val_df["target"].astype(int).to_numpy(), val_proba, val_df["future_return"].to_numpy(), cfg.data.decision_threshold),
        "test": _compute_metrics(test_df["target"].astype(int).to_numpy(), test_proba, test_df["future_return"].to_numpy(), cfg.data.decision_threshold),
        "calibration_method": calibrator.method if calibrator is not None and calibrator.fitted else "none",
    }

