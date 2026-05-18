"""modelFactory/tabular_baseline.py — Helpers communs aux challengers tabulaires."""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from modelFactory.calibration import PlattCalibrator
from modelFactory.config import TrainingConfig
from modelFactory.dataset import chrono_split
from modelFactory.evaluation import compute_threshold_metrics, optimize_decision_threshold
from modelFactory.features import get_feature_columns


def tabular_split(
	df: pd.DataFrame,
	*,
	train_ratio: float,
	val_ratio: float,
	forecast_horizon: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
	if "target" not in df.columns:
		raise ValueError("La baseline tabulaire attend une colonne 'target'.")
	clean = df.loc[df["target"].notna()].reset_index(drop=True)
	split = chrono_split(
		clean,
		train_ratio,
		val_ratio,
		forecast_horizon=forecast_horizon,
		date_column="date" if "date" in clean.columns else None,
	)
	return split.train, split.val, split.test


def binary_auc(labels: np.ndarray, scores: np.ndarray) -> float | None:
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


def expected_calibration_error(labels: np.ndarray, proba: np.ndarray, n_bins: int = 10) -> float:
	edges = np.linspace(0.0, 1.0, n_bins + 1)
	ece = 0.0
	for i in range(n_bins):
		left, right = edges[i], edges[i + 1]
		mask = (proba >= left) & (proba <= right) if i == n_bins - 1 else (proba >= left) & (proba < right)
		if not np.any(mask):
			continue
		ece += mask.mean() * abs(float(labels[mask].mean()) - float(proba[mask].mean()))
	return float(ece)


def compute_tabular_metrics(
	labels: np.ndarray,
	proba: np.ndarray,
	future_returns: np.ndarray,
	decision_threshold: float,
) -> dict[str, Any]:
	labels = np.asarray(labels, dtype=np.int64)
	proba = np.asarray(proba, dtype=np.float64)
	threshold_metrics = compute_threshold_metrics(
		proba,
		labels,
		np.asarray(future_returns, dtype=np.float64),
		decision_threshold=decision_threshold,
		n_buckets=5,
	)
	pred = (proba >= decision_threshold).astype(np.int64)
	return {
		"directional_accuracy": float((pred == labels).mean()),
		"precision": float(threshold_metrics["precision_long"]),
		"recall": float(threshold_metrics["recall_long"]),
		"auc": binary_auc(labels, proba),
		"brier_score": float(np.mean((proba - labels) ** 2)),
		"ece": expected_calibration_error(labels, proba),
		"action_rate": float(threshold_metrics["coverage_at_threshold"]),
		**threshold_metrics,
	}


def fit_tabular_calibrator(
	val_raw_proba: np.ndarray,
	labels: np.ndarray,
	cfg: TrainingConfig,
) -> PlattCalibrator | None:
	if cfg.calibration.method != "platt":
		return None
	labels = np.asarray(labels, dtype=np.int64)
	if len(labels) < cfg.calibration.min_samples:
		return None
	if len(np.unique(labels)) < 2:
		return None
	eps = 1e-6
	margins = np.log(np.clip(val_raw_proba, eps, 1 - eps) / np.clip(1 - val_raw_proba, eps, 1 - eps))
	return PlattCalibrator(max_iter=cfg.calibration.max_iter).fit(margins, labels)


def apply_tabular_calibration(raw_proba: np.ndarray, calibrator: PlattCalibrator | None) -> np.ndarray:
	if calibrator is None or not calibrator.fitted:
		return np.asarray(raw_proba, dtype=np.float64)
	eps = 1e-6
	margins = np.log(np.clip(raw_proba, eps, 1 - eps) / np.clip(1 - raw_proba, eps, 1 - eps))
	return calibrator.predict_proba(margins)


def run_tabular_baseline(
	prepared_df: pd.DataFrame,
	cfg: TrainingConfig,
	*,
	model_name: str,
	model_builder: Callable[[], Any],
	artifact_dir: Path | None = None,
	save_callback: Callable[[Any, Path], None] | None = None,
	model_extension: str = ".pkl",
) -> dict[str, Any]:
	feature_columns = get_feature_columns(
		include_sentiment=cfg.data.include_sentiment_features,
		feature_set=cfg.data.feature_set,
		include_cross_sectional=cfg.data.enable_cross_sectional_features,
	)
	train_df, val_df, test_df = tabular_split(
		prepared_df,
		train_ratio=cfg.data.train_ratio,
		val_ratio=cfg.data.val_ratio,
		forecast_horizon=cfg.data.forecast_horizon,
	)
	if train_df.empty or val_df.empty or test_df.empty:
		return {"status": "skipped", "model_name": model_name, "reason": "insufficient_rows_after_split"}

	model = model_builder()
	model.fit(train_df[feature_columns], train_df["target"].astype(int))

	val_raw = model.predict_proba(val_df[feature_columns])[:, 1]
	calibrator = fit_tabular_calibrator(val_raw, val_df["target"].astype(int).to_numpy(), cfg)
	val_proba = apply_tabular_calibration(val_raw, calibrator)

	if cfg.threshold_optimization.enabled:
		threshold_summary = optimize_decision_threshold(
			val_proba,
			val_df["target"].astype(int).to_numpy(),
			val_df["future_return"].to_numpy(),
			candidate_thresholds=cfg.threshold_optimization.candidate_decision_thresholds,
			default_threshold=cfg.data.decision_threshold,
			min_action_rate=cfg.threshold_optimization.min_action_rate,
			max_action_rate=cfg.threshold_optimization.max_action_rate,
			min_precision_long=cfg.threshold_optimization.min_precision_long,
			n_buckets=5,
		)
		selected_threshold = float(threshold_summary["selected_threshold"])
	else:
		selected_threshold = float(cfg.data.decision_threshold)
		threshold_summary = {
			"enabled": False,
			"selection_status": "disabled",
			"selected_threshold": selected_threshold,
			"candidates": [],
		}

	test_raw = model.predict_proba(test_df[feature_columns])[:, 1]
	test_proba = apply_tabular_calibration(test_raw, calibrator)
	val_metrics = compute_tabular_metrics(
		val_df["target"].astype(int).to_numpy(),
		val_proba,
		val_df["future_return"].to_numpy(),
		selected_threshold,
	)
	test_metrics = compute_tabular_metrics(
		test_df["target"].astype(int).to_numpy(),
		test_proba,
		test_df["future_return"].to_numpy(),
		selected_threshold,
	)
	selection_score = float(
		test_metrics.get("threshold_business_score")
		or test_metrics.get("auc")
		or val_metrics.get("threshold_business_score")
		or 0.0
	)
	result = {
		"status": "completed",
		"model_name": model_name,
		"feature_columns": feature_columns,
		"val": val_metrics,
		"test": test_metrics,
		"calibration_method": calibrator.method if calibrator is not None and calibrator.fitted else "none",
		"threshold_optimization": threshold_summary,
		"selected_decision_threshold": selected_threshold,
		"inference_backend": f"{model_name}_tabular",
		"selection_score": selection_score,
	}
	if artifact_dir is not None:
		artifact_dir.mkdir(parents=True, exist_ok=True)
		# Phase 4.2.c — format natif si callback fourni, sinon pickle (rétrocompat).
		model_path = artifact_dir / f"{model_name}_model{model_extension}"
		if save_callback is not None:
			save_callback(model, model_path)
		else:
			with open(model_path, "wb") as fh:
				pickle.dump(model, fh)
		calibrator_path: str | None = None
		if calibrator is not None and calibrator.fitted:
			cal_path = artifact_dir / f"{model_name}_calibrator.pkl"
			with open(cal_path, "wb") as fh:
				pickle.dump(calibrator.state_dict(), fh)
			calibrator_path = str(cal_path)
		result["artifact_paths"] = {
			"model_path": str(model_path),
			"calibrator_path": calibrator_path,
			"model_format": model_extension.lstrip("."),
		}
	return result


