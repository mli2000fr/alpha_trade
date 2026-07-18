"""modelFactory/tabular_baseline.py — Helpers communs aux challengers tabulaires."""
from __future__ import annotations

import json
import pickle
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from modelFactory.calibration import PlattCalibrator, TemperatureScaler
from modelFactory.config import ReproducibilityConfig, TrainingConfig
from modelFactory.dataset import chrono_split
from modelFactory.evaluation import (
    check_model_collapse,
    compute_multiclass_metrics,
    compute_threshold_metrics,
    optimize_decision_threshold,
)
from modelFactory.features import build_feature_contract
from modelFactory.features import fingerprint as compute_feature_fingerprint
from modelFactory.features import get_feature_columns
from modelFactory.reproducibility import apply_reproducibility, derive_seed
from core.ternary_decision_policy import TernaryDecisionPolicy, decide_ternary_side_batch


def tabular_split(
	df: pd.DataFrame,
	*,
	train_ratio: float,
	val_ratio: float,
	forecast_horizon: int = 0,
	embargo_rows: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
	if "target" not in df.columns:
		raise ValueError("La baseline tabulaire attend une colonne 'target'.")
	clean = df.loc[df["target"].notna()].reset_index(drop=True)
	split = chrono_split(
		clean,
		train_ratio,
		val_ratio,
		forecast_horizon=forecast_horizon,
		embargo_rows=embargo_rows,
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
	*,
	raw_proba_all: np.ndarray | None = None,
	target_raw: np.ndarray | None = None,
	is_ternary: bool = False,
	ternary_policy: "TernaryDecisionPolicy | None" = None,
) -> dict[str, Any]:
	"""Métriques tabulaires complètes (Sprint Maître 1 : multiclasses ajouté)."""
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
	result: dict[str, Any] = {
		"directional_accuracy": float((pred == labels).mean()),
		"precision": float(threshold_metrics["precision_long"]),
		"recall": float(threshold_metrics["recall_long"]),
		"auc": binary_auc(labels, proba),
		"brier_score": float(np.mean((proba - labels) ** 2)),
		"ece": expected_calibration_error(labels, proba),
		"action_rate": float(threshold_metrics["coverage_at_threshold"]),
		"n_observations": len(labels),
		**threshold_metrics,
	}

	# ── F1 ternaire + métriques multiclasses (Sprint Maître 1) ──
	if is_ternary and raw_proba_all is not None and target_raw is not None:
		probs_all = np.asarray(raw_proba_all, dtype=np.float64)
		targets = np.asarray(target_raw, dtype=np.int64)  # {-1, 0, 1}

		if probs_all.ndim == 2 and probs_all.shape[1] >= 3 and len(targets) == probs_all.shape[0]:
			# ── Sprint Maître 0 : décision via la policy partagée ─
			_pol = ternary_policy if ternary_policy is not None else TernaryDecisionPolicy()
			preds_multi = decide_ternary_side_batch(probs_all[:, :3], policy=_pol)  # {0=short, 1=flat, 2=long}
			labels_shifted = targets + 1  # {-1,0,1} -> {0,1,2}

			# ── Sprint Maître 1 : métriques multiclasses complètes ─
			multiclass_metrics = compute_multiclass_metrics(
				y_true=labels_shifted,
				y_proba=probs_all[:, :3],
				class_names=("short", "flat", "long"),
			)
			result.update(multiclass_metrics)

			# Per-class F1 (legacy + redondance sécurisée)
			for cls_idx, cls_name in enumerate(["short", "flat", "long"]):
				tp = int(((preds_multi == cls_idx) & (labels_shifted == cls_idx)).sum())
				fp = int(((preds_multi == cls_idx) & (labels_shifted != cls_idx)).sum())
				fn = int(((preds_multi != cls_idx) & (labels_shifted == cls_idx)).sum())
				prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
				rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
				result[f"f1_{cls_name}"] = float(2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0)
			f1_vals = [v for k, v in result.items() if k.startswith("f1_") and v is not None]
			result["f1_macro"] = float(np.mean(f1_vals)) if f1_vals else 0.0

			# ── Distribution true / pred (compatible LSTM) ──
			n = len(labels_shifted)
			for cls_idx, cls_name in enumerate(["short", "flat", "long"]):
				result[f"true_{cls_name}_pct"] = float((labels_shifted == cls_idx).mean() * 100) if n > 0 else 0.0
				result[f"pred_{cls_name}_pct"] = float((preds_multi == cls_idx).mean() * 100) if n > 0 else 0.0

			# ── Sprint Maître 1 : détection de collapse ─
			collapsed, collapse_reason = check_model_collapse(probs_all[:, :3])
			result["collapsed"] = collapsed
			result["collapse_reason"] = collapse_reason

	return result


def fit_tabular_calibrator(
	val_raw_proba: np.ndarray,
	labels: np.ndarray,
	cfg: TrainingConfig,
	*,
	target_mode: str = "binary",
) -> PlattCalibrator | TemperatureScaler | None:
	"""Fit un calibrateur selon le mode cible.

	Sprint Maître 1 :
	- ``binary`` → :class:`PlattCalibrator` (binaire).
	- ``ternary`` → :class:`TemperatureScaler` (multiclasse).
	"""
	if cfg.calibration.method == "none":
		return None
	if target_mode == "ternary":
		return _fit_ternary_calibrator(val_raw_proba, labels, cfg)
	# Binaire : Platt
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


def _fit_ternary_calibrator(
	raw_proba_all: np.ndarray,
	labels: np.ndarray,
	cfg: TrainingConfig,
) -> TemperatureScaler | None:
	"""Fit un TemperatureScaler pour la calibration ternaire (Sprint Maître 1).

	Le TemperatureScaler opère sur les logits. On utilise les probabilités
	brutes comme pseudo-logits via inverse-softmax (log).
	"""
	labels = np.asarray(labels, dtype=np.int64)
	proba = np.asarray(raw_proba_all, dtype=np.float64)
	if proba.ndim != 2 or proba.shape[1] < 3:
		return None
	if len(labels) < cfg.calibration.min_samples:
		return None
	if len(np.unique(labels)) < 2:
		return None
	# Convertir probas en pseudo-logits pour TemperatureScaler
	eps = 1e-8
	clipped = np.clip(proba, eps, 1 - eps)
	# Normaliser
	clipped = clipped / clipped.sum(axis=1, keepdims=True)
	logits = np.log(clipped)
	return TemperatureScaler(max_iter=cfg.calibration.max_iter).fit(logits, labels)


def apply_tabular_calibration(
	raw_proba: np.ndarray,
	calibrator: PlattCalibrator | TemperatureScaler | None,
	*,
	target_mode: str = "binary",
) -> np.ndarray:
	"""Applique le calibrateur selon le mode cible (Sprint Maître 1)."""
	if calibrator is None or not calibrator.fitted:
		return np.asarray(raw_proba, dtype=np.float64)
	if target_mode == "ternary" and isinstance(calibrator, TemperatureScaler):
		return calibrator.predict_proba(raw_proba)
	if isinstance(calibrator, PlattCalibrator):
		eps = 1e-6
		raw = np.asarray(raw_proba, dtype=np.float64)
		if raw.ndim == 2 and raw.shape[1] >= 2:
			raw = raw[:, 1] if raw.shape[1] == 2 else raw[:, 2]
		raw = raw.reshape(-1)
		margins = np.log(np.clip(raw, eps, 1 - eps) / np.clip(1 - raw, eps, 1 - eps))
		return calibrator.predict_proba(margins)
	return np.asarray(raw_proba, dtype=np.float64)


def run_tabular_baseline(
	prepared_df: pd.DataFrame,
	cfg: TrainingConfig,
	*,
	model_name: str,
	model_builder: Callable[[int], Any],
	artifact_dir: Path | None = None,
	save_callback: Callable[[Any, Path], None] | None = None,
	model_extension: str = ".pkl",
	ternary_policy: "TernaryDecisionPolicy | None" = None,
) -> dict[str, Any]:
	feature_columns = get_feature_columns(
		include_sentiment=cfg.data.include_sentiment_features,
		feature_set=cfg.data.feature_set,
		include_cross_sectional=cfg.data.enable_cross_sectional_features,
		include_selector_context=cfg.data.include_selector_context_features,
		include_short_score=cfg.data.include_short_score_features,
	)
	train_df, val_df, test_df = tabular_split(
		prepared_df,
		train_ratio=cfg.data.train_ratio,
		val_ratio=cfg.data.val_ratio,
		forecast_horizon=cfg.data.forecast_horizon,
	)
	if train_df.empty or val_df.empty or test_df.empty:
		return {"status": "skipped", "model_name": model_name, "reason": "insufficient_rows_after_split"}

	symbol_tag = "__BATCH__"
	if "symbol" in prepared_df.columns and not prepared_df["symbol"].empty:
		symbol_tag = str(prepared_df["symbol"].iloc[0])
	resolved_seed = derive_seed(cfg.reproducibility.seed, "tabular_baseline", model_name, symbol_tag)
	apply_reproducibility(
		ReproducibilityConfig(seed=resolved_seed, deterministic=cfg.reproducibility.deterministic),
		context=f"tabular_baseline:{model_name}:{symbol_tag}",
	)
	model = model_builder(resolved_seed)
	is_ternary = cfg.data.target_mode == "ternary"
	train_targets = train_df["target"].astype(int)
	# LightGBM/CatBoost exigent des labels consecutifs a partir de 0.
	# On decale {-1,0,+1} -> {0,1,2} pour le mode ternaire.
	if is_ternary:
		train_targets = train_targets + 1  # shift: -1->0, 0->1, +1->2
	unique_classes = train_targets.unique()
	if len(unique_classes) < 2:
		return {"status": "skipped", "model_name": model_name, "reason": f"single_class_target_{unique_classes[0]}"}
	model.fit(train_df[feature_columns], train_targets)

	is_ternary = cfg.data.target_mode == "ternary"
	# Determine which predict_proba column holds the long probability.
	# For ternary with all 3 classes present: 3 cols -> col 2=long.
	# For binary or ternary with missing classes: use last column.
	raw_proba_all = model.predict_proba(val_df[feature_columns])
	num_proba_cols = raw_proba_all.shape[1]
	if is_ternary and num_proba_cols >= 3:
		long_col = 2  # full ternary: [short, flat, long]
	else:
		long_col = num_proba_cols - 1  # fallback: last column

	val_raw = raw_proba_all[:, long_col]
	target_mode = cfg.data.target_mode

	# ── Sprint Maître 1 : calibration multiclasse ─────────────────────
	# Toujours calculer cal_labels (binarisé long=1) pour le threshold optimizer
	cal_labels = (val_df["target"].astype(int) == 1).astype(int).to_numpy() if is_ternary else val_df["target"].astype(int).to_numpy()

	if is_ternary and num_proba_cols >= 3:
		# Ternaire : TemperatureScaler sur les 3 probas
		val_labels_ternary = (val_df["target"].astype(int) + 1).to_numpy()  # shift -1,0,1 -> 0,1,2
		calibrator = fit_tabular_calibrator(
			raw_proba_all[:, :3], val_labels_ternary, cfg, target_mode="ternary",
		)
		# Appliquer calibration ternaire
		calibrated_all = apply_tabular_calibration(
			raw_proba_all[:, :3], calibrator, target_mode="ternary",
		)
		val_proba = calibrated_all[:, 2]  # p_long calibrée
	else:
		# Binaire : Platt
		calibrator = fit_tabular_calibrator(val_raw, cal_labels, cfg, target_mode="binary")
		val_proba = apply_tabular_calibration(val_raw, calibrator, target_mode="binary")

	if cfg.threshold_optimization.enabled:
		threshold_summary = optimize_decision_threshold(
			val_proba,
			cal_labels,  # binarisee : 1=long, 0=sinon
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

	test_raw_all = model.predict_proba(test_df[feature_columns])
	num_test_cols = test_raw_all.shape[1]
	test_long_col = 2 if (is_ternary and num_test_cols >= 3) else (num_test_cols - 1)
	test_raw = test_raw_all[:, test_long_col]

	# ── Sprint Maître 1 : calibration test ────────────────────────────
	if is_ternary and num_test_cols >= 3:
		calibrated_test_all = apply_tabular_calibration(
			test_raw_all[:, :3], calibrator, target_mode="ternary",
		)
		test_proba = calibrated_test_all[:, 2]
	else:
		test_proba = apply_tabular_calibration(test_raw, calibrator, target_mode="binary")

	# Pour les métriques, on binarise aussi la target test
	test_labels = (test_df["target"].astype(int) == 1).astype(int).to_numpy() if is_ternary else test_df["target"].astype(int).to_numpy()
	val_labels = (val_df["target"].astype(int) == 1).astype(int).to_numpy() if is_ternary else val_df["target"].astype(int).to_numpy()

	val_metrics = compute_tabular_metrics(
		val_labels,
		val_proba,
		val_df["future_return"].to_numpy(),
		selected_threshold,
		raw_proba_all=raw_proba_all if is_ternary else None,
		target_raw=val_df["target"].astype(int).to_numpy() if is_ternary else None,
		is_ternary=is_ternary,
		ternary_policy=ternary_policy,
	)
	test_metrics = compute_tabular_metrics(
		test_labels,
		test_proba,
		test_df["future_return"].to_numpy(),
		selected_threshold,
		raw_proba_all=test_raw_all if is_ternary else None,
		target_raw=test_df["target"].astype(int).to_numpy() if is_ternary else None,
		is_ternary=is_ternary,
		ternary_policy=ternary_policy,
	)
	# ── Sprint Maître 1 : selection_score depuis val uniquement ──────
	selection_score = float(
		val_metrics.get("threshold_business_score")
		or val_metrics.get("auc")
		or val_metrics.get("auc_macro")
		or 0.0
	)
	feature_contract = build_feature_contract(
		include_sentiment=cfg.data.include_sentiment_features,
		feature_set=cfg.data.feature_set,
		include_cross_sectional=cfg.data.enable_cross_sectional_features,
		include_selector_context=cfg.data.include_selector_context_features,
		include_short_score=cfg.data.include_short_score_features,
		feature_columns=feature_columns,
		scaler_feature_names=feature_columns,
	)
	result = {
		"status": "completed",
		"model_name": model_name,
		"seed": int(resolved_seed),
		"feature_columns": feature_columns,
		"feature_contract": feature_contract,
		"feature_fingerprint": compute_feature_fingerprint(
			include_sentiment=cfg.data.include_sentiment_features,
			feature_set=cfg.data.feature_set,
			include_cross_sectional=cfg.data.enable_cross_sectional_features,
			include_selector_context=cfg.data.include_selector_context_features,
			include_short_score=cfg.data.include_short_score_features,
			feature_columns=feature_columns,
		),
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


def save_baseline_artifact(
	result: dict[str, Any],
	*,
	artifact_dir: Path,
	period_start: date | str,
	period_end: date | str,
	universe_run_id: str = "",
	code_version: str = "",
	data_fingerprint: str,
	config_fingerprint: str,
	symbol_tag: str = "__BATCH__",
) -> Path:
	"""Produit et sauvegarde un artefact baseline JSON standalone (Sprint 0 tâche 5).

	L'artefact contient : période, univers, seed, version de code,
	fingerprints de données/configuration, et métriques par side.
	"""
	from core.ternary_decision_policy import DEFAULT_TERNARY_POLICY

	if not data_fingerprint:
		raise ValueError("data_fingerprint is required for a baseline artifact.")
	if not config_fingerprint:
		raise ValueError("config_fingerprint is required for a baseline artifact.")

	artifact_dir = Path(artifact_dir)
	artifact_dir.mkdir(parents=True, exist_ok=True)

	val: dict[str, Any] = result.get("val", {})
	test: dict[str, Any] = result.get("test", {})

	baseline = {
		"baseline_version": 1,
		"generated_at": datetime.now(timezone.utc).isoformat(),
		"period": {
			"start": str(period_start),
			"end": str(period_end),
		},
		"universe": {
			"run_id": universe_run_id,
		},
		"model": {
			"name": result.get("model_name", "unknown"),
			"inference_backend": result.get("inference_backend", ""),
			"seed": result.get("seed"),
			"calibration_method": result.get("calibration_method", "none"),
			"decision_threshold": result.get("selected_decision_threshold"),
		},
		"policy": {
			"version": DEFAULT_TERNARY_POLICY.version,
			"threshold_long": DEFAULT_TERNARY_POLICY.threshold_long,
			"threshold_short": DEFAULT_TERNARY_POLICY.threshold_short,
			"top2_margin": DEFAULT_TERNARY_POLICY.top2_margin,
		},
		"code": {
			"version": code_version,
		},
		"fingerprints": {
			"features": result.get("feature_fingerprint", ""),
			"data": data_fingerprint,
			"configuration": config_fingerprint,
		},
		"metrics": {
			"val": {
				"n_observations": val.get("n_observations"),
				"accuracy": val.get("accuracy"),
				"f1_macro": val.get("f1_macro"),
				"f1_weighted": val.get("f1_weighted"),
				"f1_long": val.get("f1_long"),
				"f1_short": val.get("f1_short"),
				"f1_flat": val.get("f1_flat"),
				"balanced_accuracy": val.get("balanced_accuracy"),
				"action_rate": val.get("action_rate"),
				"pred_fraction_long": val.get("pred_fraction_long"),
				"pred_fraction_short": val.get("pred_fraction_short"),
				"pred_fraction_flat": val.get("pred_fraction_flat"),
				"brier_multiclass": val.get("brier_multiclass"),
				"log_loss": val.get("log_loss"),
				"selection_score": result.get("selection_score"),
			},
			"test": {
				"n_observations": test.get("n_observations"),
				"accuracy": test.get("accuracy"),
				"f1_macro": test.get("f1_macro"),
				"f1_weighted": test.get("f1_weighted"),
				"f1_long": test.get("f1_long"),
				"f1_short": test.get("f1_short"),
				"f1_flat": test.get("f1_flat"),
				"balanced_accuracy": test.get("balanced_accuracy"),
				"action_rate": test.get("action_rate"),
				"pred_fraction_long": test.get("pred_fraction_long"),
				"pred_fraction_short": test.get("pred_fraction_short"),
				"pred_fraction_flat": test.get("pred_fraction_flat"),
				"brier_multiclass": test.get("brier_multiclass"),
				"log_loss": test.get("log_loss"),
			},
		},
		"collapsed": {
			"val": val.get("collapsed", False),
			"test": test.get("collapsed", False),
		},
	}

	path = artifact_dir / f"baseline_{symbol_tag}_{result.get('model_name','unknown')}.json"
	with open(path, "w", encoding="utf-8") as fh:
		json.dump(baseline, fh, indent=2, ensure_ascii=False, default=str)

	return path

