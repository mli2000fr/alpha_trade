"""modelFactory/tabular_baseline.py — Helpers communs aux challengers tabulaires."""
from __future__ import annotations

import json
import logging
import pickle
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from modelFactory.calibration import PlattCalibrator, TemperatureScaler, VectorScaler
from modelFactory.config import ReproducibilityConfig, TrainingConfig
from modelFactory.dataset import chrono_split
from modelFactory.directional_conditioning import (
	ORACLE_ELIGIBLE_COLUMN,
	eligible_target_mask,
	filter_eligible_target_rows,
)
from modelFactory.evaluation import (
    check_model_collapse,
    compute_multiclass_metrics,
    compute_threshold_metrics,
    optimize_decision_threshold,
)
from modelFactory.features import build_feature_contract
from modelFactory.features import get_feature_columns
from modelFactory.reproducibility import apply_reproducibility, derive_seed

LOGGER = logging.getLogger(__name__)
from core.ternary_decision_policy import TernaryDecisionPolicy, decide_ternary_side_batch


def tabular_split(
	df: pd.DataFrame,
	*,
	train_ratio: float,
	val_ratio: float,
	forecast_horizon: int = 0,
	embargo_rows: int = 0,
	by_dates: bool = False,
	embargo_dates: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
	if "target" not in df.columns:
		raise ValueError("La baseline tabulaire attend une colonne 'target'.")
	if ORACLE_ELIGIBLE_COLUMN in df.columns:
		# Conserver les frontières temporelles du calendrier complet, puis borner
		# seulement les observations du modèle au TOP20 Oracle OOF.
		if by_dates and "date" in df.columns:
			from modelFactory.dataset import chrono_split_by_dates
			split = chrono_split_by_dates(
				df.reset_index(drop=True),
				train_ratio=train_ratio,
				val_ratio=val_ratio,
				forecast_horizon=forecast_horizon,
				embargo_dates=embargo_dates,
			)
		else:
			split = chrono_split(
				df.reset_index(drop=True), train_ratio, val_ratio,
				forecast_horizon=forecast_horizon, embargo_rows=embargo_rows,
			)
		return tuple(filter_eligible_target_rows(part) for part in (split.train, split.val, split.test))
	clean = df.loc[df["target"].notna()].reset_index(drop=True)
	if by_dates and "date" in clean.columns:
		from modelFactory.dataset import chrono_split_by_dates
		split = chrono_split_by_dates(
			clean,
			train_ratio=train_ratio,
			val_ratio=val_ratio,
			forecast_horizon=forecast_horizon,
			embargo_dates=embargo_dates,
			date_column="date",
		)
	else:
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
	brier = float(np.mean((proba - labels) ** 2))
	result: dict[str, Any] = {
		"loss": brier,  # Brier score = MSE des probas (compatible colonne loss)
		"directional_accuracy": float((pred == labels).mean()),
		"precision": float(threshold_metrics["precision_long"]),
		"recall": float(threshold_metrics["recall_long"]),
		"auc": binary_auc(labels, proba),
		"brier_score": brier,
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
			# ⚠️ Ne pas inclure f1_weighted ni l'ancien f1_macro (issus de compute_multiclass_metrics)
			# dans le calcul du f1_macro legacy — seul f1_short, f1_flat, f1_long sont pertinents.
			_f1_class_keys = {"f1_short", "f1_flat", "f1_long"}
			f1_vals = [v for k, v in result.items() if k in _f1_class_keys and v is not None]
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
) -> PlattCalibrator | TemperatureScaler | VectorScaler | None:
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
) -> VectorScaler | None:
	"""Fit un VectorScaler pour la calibration ternaire (Sprint Maître 2).

	Remplace TemperatureScaler : le VectorScaler ajoute des biais par classe
	qui corrigent la sur/sous-prédiction systématique (ex. LightGBM qui
	sur-predit le Short de +7.7pp). Le TemperatureScaler (1 paramètre T)
	ne peut pas corriger un biais de distribution entre classes.

	Fonctionne sur les pseudo-logits obtenus par inverse-softmax (log).
	"""
	labels = np.asarray(labels, dtype=np.int64)
	proba = np.asarray(raw_proba_all, dtype=np.float64)
	if proba.ndim != 2 or proba.shape[1] < 3:
		return None
	if len(labels) < cfg.calibration.min_samples:
		return None
	if len(np.unique(labels)) < 2:
		return None
	# Convertir probas en pseudo-logits pour le calibrateur
	eps = 1e-8
	clipped = np.clip(proba, eps, 1 - eps)
	# Normaliser
	clipped = clipped / clipped.sum(axis=1, keepdims=True)
	logits = np.log(clipped)
	return VectorScaler(max_iter=cfg.calibration.max_iter).fit(logits, labels)


def apply_tabular_calibration(
	raw_proba: np.ndarray,
	calibrator: PlattCalibrator | TemperatureScaler | VectorScaler | None,
	*,
	target_mode: str = "binary",
) -> np.ndarray:
	"""Applique le calibrateur selon le mode cible (Sprint Maître 2)."""
	if calibrator is None or not calibrator.fitted:
		return np.asarray(raw_proba, dtype=np.float64)
	if target_mode == "ternary" and isinstance(calibrator, (TemperatureScaler, VectorScaler)):
		from modelFactory.calibration import probabilities_to_pseudo_logits

		return calibrator.predict_proba(probabilities_to_pseudo_logits(raw_proba))
	if isinstance(calibrator, PlattCalibrator):
		eps = 1e-6
		raw = np.asarray(raw_proba, dtype=np.float64)
		if raw.ndim == 2 and raw.shape[1] >= 2:
			raw = raw[:, 1] if raw.shape[1] == 2 else raw[:, 2]
		raw = raw.reshape(-1)
		margins = np.log(np.clip(raw, eps, 1 - eps) / np.clip(1 - raw, eps, 1 - eps))
		return calibrator.predict_proba(margins)
	return np.asarray(raw_proba, dtype=np.float64)


# ── Regression metrics helper ────────────────────────────────────────────

def _compute_regression_metrics(
	pred: np.ndarray,
	target: np.ndarray,
	future_return: np.ndarray,
	*,
	bias_correction: float = 0.0,
) -> dict[str, Any]:
	"""Calcule les métriques de régression pour un modèle per-symbol.

	Inclut le F1 macro binarisé (signe) pour comparabilité avec le mode ternaire.

	**Sprint 2026-08-03 — Alignement sector-neutre** :
	La ``directional_accuracy`` et le ``F1`` sont calculés par rapport à la
	**target neutralisée** (``target``) — celle que le modèle a appris à prédire.
	Compare le signe de la prédiction au signe de la target neutralisée,
	PAS au ``future_return`` brut. Le ``future_return`` brut reste utilisé
	uniquement pour l'IC (coefficient d'information vs rendements réels).

	Args:
		pred: Prédictions continues du modèle [n_samples]
		target: Target de régression NEUTRALISÉE (vol-scalé winsorizé) [n_samples]
		future_return: Rendement futur BRUT [n_samples] — pour IC uniquement
		bias_correction: Correction de biais appliquée AVANT binarisation.
		    pred_corrected = pred - bias_correction.
		    Le signe de pred_corrected détermine long (>0) / short (<0).

	Returns:
		dict avec mse, mae, correlation, directional_accuracy, ic, f1_macro, etc.
	"""
	valid = np.isfinite(pred) & np.isfinite(target)
	if valid.sum() < 2:
		return {"loss": 0.0, "mse": 0.0, "mae": 0.0, "correlation": 0.0, "directional_accuracy": 0.0, "n_samples": int(valid.sum()),
		        "f1_macro": 0.0, "f1_short": 0.0, "f1_flat": 0.0, "f1_long": 0.0,
		        "true_short_pct": 0.0, "true_flat_pct": 0.0, "true_long_pct": 0.0,
		        "pred_short_pct": 0.0, "pred_flat_pct": 0.0, "pred_long_pct": 0.0,
		        "ic": 0.0, "bias_correction": 0.0}

	p = pred[valid]
	t = target[valid]          # neutralisée — ce que le modèle apprend
	f = future_return[valid]   # brute — réalité économique

	residuals = p - t
	mse = float(np.mean(residuals ** 2))
	mae = float(np.mean(np.abs(residuals)))

	# Pearson correlation avec la target neutralisée
	corr = float(np.corrcoef(p, t)[0, 1]) if len(p) > 2 else 0.0

	# ── Bias correction ──
	p_corrected = p - bias_correction

	# ── Directional accuracy : sign(pred) == sign(target neutralisée) ──
	# C'est la métrique alignée avec ce que le modèle apprend.
	# On mesure : "le modèle a-t-il correctement prédit la sur/sous-performance
	# relative au secteur ?" et NON "le prix a-t-il monté ou baissé ?"
	dir_acc = float(np.mean(np.sign(p_corrected) == np.sign(t))) if len(p) > 0 else 0.0

	# ── IC (Information Coefficient) : corrélation prédiction vs rendement BRUT ──
	# L'IC reste sur le future_return brut car il mesure la capacité
	# à générer du PnL réel (utile pour le backtesting).
	ic = float(np.corrcoef(p, f)[0, 1]) if len(p) > 2 and np.isfinite(f).sum() >= 2 else 0.0

	# ── F1 macro binarisé — sur target NEUTRALISÉE ──
	# Cohérent avec dir_acc : on évalue la capacité de ranking intra-secteur.
	pred_side = np.select([p_corrected > 0, p_corrected < 0], [1, -1], default=0).astype(int)
	true_side = np.select([t > 0, t < 0], [1, -1], default=0).astype(int)

	pred_shifted = pred_side + 1  # {-1,0,1} → {0,1,2}
	true_shifted = true_side + 1

	f1_per_class: dict[str, float] = {}
	for cls_idx, cls_name in enumerate(["short", "flat", "long"]):
		tp = int(((pred_shifted == cls_idx) & (true_shifted == cls_idx)).sum())
		fp = int(((pred_shifted == cls_idx) & (true_shifted != cls_idx)).sum())
		fn = int(((pred_shifted != cls_idx) & (true_shifted == cls_idx)).sum())
		prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
		rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
		f1_per_class[f"f1_{cls_name}"] = float(2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0)

	f1_values = [v for v in f1_per_class.values() if v is not None]
	f1_macro = float(np.mean(f1_values)) if f1_values else 0.0

	return {
		"loss": mse,  # compatibilité avec insert_metrics (colonne loss = MSE pour regression)
		"mse": mse,
		"mae": mae,
		"rmse": float(np.sqrt(mse)),
		"correlation": corr,
		"directional_accuracy": dir_acc,
		"ic": ic,
		"n_samples": int(valid.sum()),
		"pred_mean": float(np.mean(p)),
		"pred_std": float(np.std(p)),
		"target_mean": float(np.mean(t)),
		"target_std": float(np.std(t)),
		"f1_macro": f1_macro,
		**f1_per_class,
		"true_short_pct": float((true_shifted == 0).mean() * 100),
		"true_flat_pct": float((true_shifted == 1).mean() * 100),
		"true_long_pct": float((true_shifted == 2).mean() * 100),
		"pred_short_pct": float((pred_shifted == 0).mean() * 100),
		"pred_flat_pct": float((pred_shifted == 1).mean() * 100),
		"pred_long_pct": float((pred_shifted == 2).mean() * 100),
		"bias_correction": float(bias_correction),
	}


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
	by_dates: bool = False,
	embargo_dates: int = 0,
	symbol_tag: str = "",
	forecast_horizon_override: int | None = None,
	feature_columns_override: list[str] | None = None,
) -> dict[str, Any]:
	# ── Purge dynamique par horizon (Sprint 2026-08-03) ──
	_purge_horizon = forecast_horizon_override if forecast_horizon_override is not None else cfg.data.forecast_horizon
	# ── Feature columns : utiliser l'override si fourni (P0-3 fix) ──
	if feature_columns_override is not None:
		feature_columns = list(feature_columns_override)
	else:
		feature_columns = get_feature_columns(
			include_sentiment=cfg.data.include_sentiment_features,
			feature_set=cfg.data.feature_set,
			include_cross_sectional=cfg.data.enable_cross_sectional_features,
			include_screener_scores=cfg.data.include_screener_scores,
			include_short_score=cfg.data.include_short_score_features,
			include_macro_vix=cfg.data.include_macro_vix_features,
			include_macro_vxn=cfg.data.include_macro_vxn_features,
			include_macro_vix3m=cfg.data.include_macro_vix3m_features,
			include_macro_move=cfg.data.include_macro_move_features,
			include_global_stacking=cfg.global_model.stacking_enabled,
			include_fundamentals=cfg.data.include_fundamentals_features,
			include_factors=cfg.data.include_factors_features,
			include_macro_regime=cfg.data.include_macro_regime_features,
			include_volume_features=(cfg.data.include_volume_features and cfg.data.feature_whitelist_enabled),
			feature_whitelist_enabled=cfg.data.feature_whitelist_enabled,
			feature_whitelist=cfg.data.feature_whitelist,
		)
	train_df, val_df, test_df = tabular_split(
		prepared_df,
		train_ratio=cfg.data.train_ratio,
		val_ratio=cfg.data.val_ratio,
		forecast_horizon=_purge_horizon,
		by_dates=by_dates,
		embargo_dates=embargo_dates,
	)
	if train_df.empty or val_df.empty or test_df.empty:
		return {"status": "skipped", "model_name": model_name, "reason": "insufficient_rows_after_split"}

	# ── Standardize regression target on train stats (anti-leakage) ──
	if cfg.data.target_mode == "regression":
		from modelFactory.features import standardize_regression_target
		# ── Winsorize using train quantiles (anti-leakage P1-1, 2026-08-04) ──
		# Avant : build_target() winsorisait sur l'historique complet → fuite.
		# Après : on re-winsorise avec les quantiles du train SEULEMENT.
		train_target = train_df["target"]
		valid = train_target.notna()
		if valid.sum() >= 2:
			_lo = float(train_target.loc[valid].quantile(0.01))
			_hi = float(train_target.loc[valid].quantile(0.99))
			for _part in (train_df, val_df, test_df):
				_part["target"] = _part["target"].clip(_lo, _hi)
		# Compute stats on train only, apply to all splits
		train_target = train_df["target"]
		valid = train_target.notna()
		if valid.sum() >= 2:
			t_mean = float(train_target.loc[valid].mean())
			t_std = float(train_target.loc[valid].std())
			if t_std > 1e-9:
				for _part in (train_df, val_df, test_df):
					_part["target"] = (_part["target"] - t_mean) / t_std
			else:
				for _part in (train_df, val_df, test_df):
					_part["target"] = _part["target"] - t_mean

	_symbol_tag = symbol_tag or "__BATCH__"
	if not symbol_tag and "symbol" in prepared_df.columns and not prepared_df["symbol"].empty:
		_symbol_tag = str(prepared_df["symbol"].iloc[0])
	resolved_seed = derive_seed(cfg.reproducibility.seed, "tabular_baseline", model_name, _symbol_tag)
	apply_reproducibility(
		ReproducibilityConfig(seed=resolved_seed, deterministic=cfg.reproducibility.deterministic),
		context=f"tabular_baseline:{model_name}:{_symbol_tag}",
	)
	model = model_builder(resolved_seed)
	is_ternary = cfg.data.target_mode == "ternary"
	is_regression = cfg.data.target_mode == "regression"

	if is_regression:
		# ── Regression : target continue ─────────────────────────────
		train_targets = train_df["target"].astype(float)
		# Vérifier qu'il y a de la variance
		if train_targets.std() < 1e-9:
			return {"status": "skipped", "model_name": model_name, "reason": "zero_variance_target"}

		_sample_weights: "np.ndarray | None" = None
		if "date" in train_df.columns:
			_train_dates = pd.to_datetime(train_df["date"])
			_max_date = _train_dates.max()
			_days_diff = (_max_date - _train_dates).dt.days
			_sample_weights = np.exp(-_days_diff.values.astype(np.float64) / 365.0)

		model.fit(train_df[feature_columns], train_targets, sample_weight=_sample_weights)

		# Prédictions continues
		val_pred = model.predict(val_df[feature_columns])
		test_pred = model.predict(test_df[feature_columns])

		# Métriques régression
		val_future = val_df["future_return"].to_numpy()
		test_future = test_df["future_return"].to_numpy()

		# ── Bias correction : recalibre le seuil long/short ──
		# La target sector-neutre est centrée sur 0 par construction,
		# mais le modèle peut avoir un biais systématique.
		# On calcule la médiane des prédictions sur la validation
		# pour recentrer le seuil de décision.
		bias_correction = float(np.median(val_pred))
		LOGGER.info(
			"tabular_baseline regression bias_correction=%.6f model=%s",
			bias_correction, model_name,
		)

		val_metrics = _compute_regression_metrics(val_pred, val_df["target"].to_numpy(), val_future, bias_correction=bias_correction)
		test_metrics = _compute_regression_metrics(test_pred, test_df["target"].to_numpy(), test_future, bias_correction=bias_correction)

		selected_threshold = float(cfg.data.decision_threshold)
		calibrator = None
		val_proba = val_pred  # utilisé pour décision binaire simple
		test_proba = test_pred
		cal_labels = (val_future > 0).astype(int)
		threshold_summary = {"enabled": False, "selection_status": "regression_mode", "selected_threshold": selected_threshold, "candidates": []}
		selection_score = float(val_metrics.get("directional_accuracy", 0.0))
	else:
		# ── Classification (binaire / ternaire) ──────────────────────
		train_targets = train_df["target"].astype(int)
		# LightGBM/CatBoost exigent des labels consecutifs a partir de 0.
		# On decale {-1,0,+1} -> {0,1,2} pour le mode ternaire.
		if is_ternary:
			train_targets = train_targets + 1  # shift: -1->0, 0->1, +1->2
		unique_classes = train_targets.unique()
		if len(unique_classes) < 2:
			return {"status": "skipped", "model_name": model_name, "reason": f"single_class_target_{unique_classes[0]}"}

		# Sample weighting par récence (Cause 3 — changement de régime)
		# Donne plus de poids aux données récentes (demi-vie = 1 an).
		_sample_weights: "np.ndarray | None" = None
		if "date" in train_df.columns:
			_train_dates = pd.to_datetime(train_df["date"])
			_max_date = _train_dates.max()
			_days_diff = (_max_date - _train_dates).dt.days
			_sample_weights = np.exp(-_days_diff.values.astype(np.float64) / 365.0)
			LOGGER.info(
				"tabular_baseline sample_weight model=%s rows=%d half_life=365d "
				"weight_min=%.3f weight_max=%.3f weight_mean=%.3f",
				model_name,
				len(_sample_weights),
				float(_sample_weights.min()),
				float(_sample_weights.max()),
				float(_sample_weights.mean()),
			)

		model.fit(train_df[feature_columns], train_targets, sample_weight=_sample_weights)

	is_ternary = cfg.data.target_mode == "ternary"
	if not is_regression:
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
		include_screener_scores=cfg.data.include_screener_scores,
		include_short_score=cfg.data.include_short_score_features,
		include_macro_vix=cfg.data.include_macro_vix_features,
		include_macro_vxn=cfg.data.include_macro_vxn_features,
		include_macro_vix3m=cfg.data.include_macro_vix3m_features,
		include_macro_move=cfg.data.include_macro_move_features,
		include_global_stacking=cfg.global_model.stacking_enabled,
		include_fundamentals=cfg.data.include_fundamentals_features,
		include_factors=cfg.data.include_factors_features,
		include_macro_regime=cfg.data.include_macro_regime_features,
		include_score_components=cfg.data.include_score_components,
		include_volume_features=(cfg.data.include_volume_features and cfg.data.feature_whitelist_enabled),
		feature_whitelist_enabled=cfg.data.feature_whitelist_enabled,
		feature_whitelist=cfg.data.feature_whitelist,
		feature_columns=feature_columns,
		scaler_feature_names=feature_columns,
	)
	result = {
		"status": "completed",
		"model_name": model_name,
		"seed": int(resolved_seed),
		"feature_columns": feature_columns,
		"feature_contract": feature_contract,
		"feature_fingerprint": feature_contract.get("feature_fingerprint"),
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


# ---------------------------------------------------------------------------
# Walk-forward tabulaire (Sprint Maître 1 Ter)
# ---------------------------------------------------------------------------

def run_tabular_walk_forward(
	prepared_df: pd.DataFrame,
	cfg: TrainingConfig,
	*,
	model_name: str,
	model_builder: Callable[[int], Any],
	ternary_policy: "TernaryDecisionPolicy | None" = None,
	by_dates: bool = False,
	symbol_tag: str = "",
	forecast_horizon_override: int | None = None,
	feature_columns_override: list[str] | None = None,
) -> dict[str, Any]:
	"""Évalue un modèle tabulaire en walk-forward (mêmes splits que le LSTM)."""
	from modelFactory.dataset import generate_walk_forward_splits, generate_walk_forward_splits_by_dates
	from modelFactory.features import get_feature_columns as _get_fc

	if not cfg.walk_forward.enabled:
		return {}

	# ── Purge dynamique par horizon (Sprint 2026-08-03) ──
	_purge_horizon = forecast_horizon_override if forecast_horizon_override is not None else cfg.data.forecast_horizon

	if by_dates:
		splits = generate_walk_forward_splits_by_dates(
			prepared_df,
			min_train_dates=cfg.walk_forward.min_train_size,
			val_dates=cfg.walk_forward.val_size,
			test_dates=cfg.walk_forward.test_size,
			step_dates=cfg.walk_forward.step_size,
			max_splits=cfg.walk_forward.max_splits,
			forecast_horizon=_purge_horizon,
		)
	else:
		splits = generate_walk_forward_splits(
			prepared_df,
			min_train_size=cfg.walk_forward.min_train_size,
			val_size=cfg.walk_forward.val_size,
			test_size=cfg.walk_forward.test_size,
			step_size=cfg.walk_forward.step_size,
			max_splits=cfg.walk_forward.max_splits,
			forecast_horizon=_purge_horizon,
		)
	if not splits:
		return {"status": "skipped", "reason": "no_valid_split"}

	is_ternary = cfg.data.target_mode == "ternary"
	is_regression = cfg.data.target_mode == "regression"
	# ── Feature columns : utiliser l'override si fourni (P0-3 fix) ──
	if feature_columns_override is not None:
		feature_cols = list(feature_columns_override)
	else:
		feature_cols = _get_fc(
			include_sentiment=cfg.data.include_sentiment_features,
			feature_set=cfg.data.feature_set,
			include_cross_sectional=cfg.data.enable_cross_sectional_features,
			include_screener_scores=cfg.data.include_screener_scores,
			include_short_score=cfg.data.include_short_score_features,
			include_macro_vix=cfg.data.include_macro_vix_features,
			include_macro_vxn=cfg.data.include_macro_vxn_features,
			include_macro_vix3m=cfg.data.include_macro_vix3m_features,
			include_macro_move=cfg.data.include_macro_move_features,
			include_global_stacking=cfg.global_model.stacking_enabled,
			include_fundamentals=cfg.data.include_fundamentals_features,
			include_factors=cfg.data.include_factors_features,
			include_macro_regime=cfg.data.include_macro_regime_features,
		)

	_symbol_tag = symbol_tag or "__BATCH__"
	if not symbol_tag and "symbol" in prepared_df.columns and not prepared_df["symbol"].empty:
		_symbol_tag = str(prepared_df["symbol"].iloc[0])

	_has_global_rank = "global_rank" in feature_cols
	LOGGER.info(
		"tabular_wf start symbol=%s model=%s splits=%d prepared_rows=%d "
		"feature_cols=%d stacking=%s global_pred=%s",
		_symbol_tag, model_name, len(splits), len(prepared_df),
		len(feature_cols), cfg.global_model.stacking_enabled, _has_global_rank,
	)

	fold_metrics: list[dict[str, Any]] = []
	wf_seed = derive_seed(cfg.reproducibility.seed, "tabular_walk_forward", model_name, _symbol_tag)

	for split in splits:
		split_seed = derive_seed(wf_seed, split.split_index)
		apply_reproducibility(
			ReproducibilityConfig(seed=split_seed, deterministic=cfg.reproducibility.deterministic),
			context=f"tabular_wf:{model_name}:{_symbol_tag}:split_{split.split_index}",
		)
		model = model_builder(split_seed)
		if is_regression:
			# ── Winsorize + Standardize target on this fold's train stats (anti-leakage) ──
			_train_df_r = split.train.copy()
			_test_df_r = split.test.copy()
			_train_valid_r = eligible_target_mask(_train_df_r)
			if _train_valid_r.sum() >= 2:
				# Winsorize using this fold's train quantiles (P1-1 fix)
				_lo = float(_train_df_r.loc[_train_valid_r, "target"].quantile(0.01))
				_hi = float(_train_df_r.loc[_train_valid_r, "target"].quantile(0.99))
				_train_df_r["target"] = _train_df_r["target"].clip(_lo, _hi)
				_test_df_r["target"] = _test_df_r["target"].clip(_lo, _hi)
				# Standardize
				_t_mean = float(_train_df_r.loc[_train_valid_r, "target"].mean())
				_t_std = float(_train_df_r.loc[_train_valid_r, "target"].std())
				if _t_std > 1e-9:
					_train_df_r["target"] = (_train_df_r["target"] - _t_mean) / _t_std
					_test_df_r["target"] = (_test_df_r["target"] - _t_mean) / _t_std
				else:
					_train_df_r["target"] = _train_df_r["target"] - _t_mean
					_test_df_r["target"] = _test_df_r["target"] - _t_mean
			# ── Regression : target continue ──
			# Filter NaN rows AFTER standardization (NaN targets persist from shift(-h))
			_train_valid_mask = eligible_target_mask(_train_df_r)
			_train_df_r = _train_df_r.loc[_train_valid_mask]
			if _train_df_r.empty:
				continue
			train_targets = _train_df_r["target"].astype(float)
			if train_targets.std() < 1e-9:
				continue
			_wf_sample_weights: "np.ndarray | None" = None
			if "date" in _train_df_r.columns:
				_wf_train_dates = pd.to_datetime(_train_df_r["date"])
				_wf_max_date = _wf_train_dates.max()
				_wf_days_diff = (_wf_max_date - _wf_train_dates).dt.days
				_wf_sample_weights = np.exp(-_wf_days_diff.values.astype(np.float64) / 365.0)
			model.fit(_train_df_r[feature_cols], train_targets, sample_weight=_wf_sample_weights)
			# ── Bias correction from train set (WF fold) ──
			_train_pred = model.predict(_train_df_r[feature_cols])
			_wf_bias = float(np.median(_train_pred))
			_test_valid_r = eligible_target_mask(_test_df_r)
			_test_df_r = _test_df_r.loc[_test_valid_r]
			if _test_df_r.empty:
				continue
			test_pred = model.predict(_test_df_r[feature_cols])
			test_pred_corrected = test_pred - _wf_bias
			test_target = _test_df_r["target"].astype(float).to_numpy()
			test_future = _test_df_r["future_return"].to_numpy() if "future_return" in _test_df_r.columns else None
			valid = np.isfinite(test_pred_corrected) & np.isfinite(test_target)
			n = int(valid.sum())
			fold_m: dict[str, Any] = {"split_index": split.split_index, "train_rows": len(_train_df_r), "test_rows": len(_test_df_r), "n_valid": n,
			                          "f1_macro": 0.0, "f1_short": 0.0, "f1_flat": 0.0, "f1_long": 0.0,
			                          "true_short_pct": 0.0, "true_flat_pct": 0.0, "true_long_pct": 0.0,
			                          "pred_short_pct": 0.0, "pred_flat_pct": 0.0, "pred_long_pct": 0.0,
			                          "bias_correction": float(_wf_bias)}
			if n >= 2:
				p, t = test_pred_corrected[valid], test_target[valid]
				f = test_future[valid] if test_future is not None else None
				fold_m["mse"] = float(np.mean((test_pred[valid] - t) ** 2))  # MSE on raw pred
				fold_m["mae"] = float(np.mean(np.abs(test_pred[valid] - t)))
				fold_m["directional_accuracy"] = float(np.mean(np.sign(p) == np.sign(t)))
				if f is not None:
					fold_m["ic"] = float(np.corrcoef(p, f)[0, 1]) if np.isfinite(f).sum() >= 2 else None
				# ── F1 macro binarisé — sur target NEUTRALISÉE ──
				# Cohérent avec l'entraînement sector-neutre :
				# on mesure la capacité de ranking intra-secteur, pas le rendement absolu.
				_f_f1 = t
				pred_side = np.select([p > 0, p < 0], [1, -1], default=0).astype(int)
				true_side = np.select([_f_f1 > 0, _f_f1 < 0], [1, -1], default=0).astype(int)
				pred_shifted = pred_side + 1
				true_shifted = true_side + 1
				f1_vals: dict[str, float] = {}
				for cls_idx, cls_name in enumerate(["short", "flat", "long"]):
					tp = int(((pred_shifted == cls_idx) & (true_shifted == cls_idx)).sum())
					fp = int(((pred_shifted == cls_idx) & (true_shifted != cls_idx)).sum())
					fn = int(((pred_shifted != cls_idx) & (true_shifted == cls_idx)).sum())
					_prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
					_rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
					f1_vals[f"f1_{cls_name}"] = float(2 * _prec * _rec / (_prec + _rec) if (_prec + _rec) > 0 else 0.0)
				fold_m.update(f1_vals)
				_f1_list = [v for v in f1_vals.values() if v is not None]
				fold_m["f1_macro"] = float(np.mean(_f1_list)) if _f1_list else 0.0
				fold_m["true_short_pct"] = float((true_shifted == 0).mean() * 100)
				fold_m["true_flat_pct"] = float((true_shifted == 1).mean() * 100)
				fold_m["true_long_pct"] = float((true_shifted == 2).mean() * 100)
				fold_m["pred_short_pct"] = float((pred_shifted == 0).mean() * 100)
				fold_m["pred_flat_pct"] = float((pred_shifted == 1).mean() * 100)
				fold_m["pred_long_pct"] = float((pred_shifted == 2).mean() * 100)
			if "date" in _train_df_r.columns:
				fold_m["train_start_date"] = str(_train_df_r["date"].min().date())
				fold_m["train_end_date"] = str(_train_df_r["date"].max().date())
			if "date" in _test_df_r.columns:
				fold_m["test_start_date"] = str(_test_df_r["date"].min().date())
				fold_m["test_end_date"] = str(_test_df_r["date"].max().date())
			fold_metrics.append(fold_m)
		else:
			# ── Filtrer les lignes avec target valide (évite NaN du shift) ──
			_train_valid = eligible_target_mask(split.train)
			_train_df = split.train.loc[_train_valid]
			train_targets = _train_df["target"].astype(int)
			if is_ternary:
				train_targets = train_targets + 1
			unique_train = train_targets.unique()
			if len(unique_train) < 2:
				continue

			# Sample weighting par récence pour le split WF
			_wf_sample_weights: "np.ndarray | None" = None
			if "date" in _train_df.columns:
				_wf_train_dates = pd.to_datetime(_train_df["date"])
				_wf_max_date = _wf_train_dates.max()
				_wf_days_diff = (_wf_max_date - _wf_train_dates).dt.days
				_wf_sample_weights = np.exp(-_wf_days_diff.values.astype(np.float64) / 365.0)

			model.fit(_train_df[feature_cols], train_targets, sample_weight=_wf_sample_weights)

			# ── Filtrer les lignes test avec target valide ──
			_test_valid = eligible_target_mask(split.test)
			_test_df = split.test.loc[_test_valid]
			if _test_df.empty:
				continue
			raw_proba_all = model.predict_proba(_test_df[feature_cols])
			test_targets = _test_df["target"].astype(int)
			test_labels = test_targets.to_numpy()
			if is_ternary:
				test_labels_shifted = test_labels + 1
				n_classes_proba = raw_proba_all.shape[1]
				if n_classes_proba >= 3:
					preds = decide_ternary_side_batch(
						raw_proba_all[:, :3],
						policy=ternary_policy if ternary_policy is not None else TernaryDecisionPolicy(),
					)
					proba_3 = raw_proba_all[:, :3]
				else:
					# Moins de 3 classes → fallback: reconstruire une matrice (N,3)
					model_classes = getattr(model, "classes_", None)
					if model_classes is not None:
						# model_classes ex: [-1, 1] → shifted: [0, 2]
						shifted_classes = np.array([int(c) + 1 for c in model_classes])
					else:
						# fallback: supposer classes 0..n_classes_proba-1
						shifted_classes = np.arange(n_classes_proba)
					proba_3 = np.zeros((len(raw_proba_all), 3), dtype=np.float64)
					for col_idx, shifted_cls in enumerate(shifted_classes):
						if 0 <= shifted_cls < 3:
							proba_3[:, shifted_cls] = raw_proba_all[:, col_idx]
					# Normaliser pour que les probas somment à 1
					_row_sums = proba_3.sum(axis=1)
					_valid = _row_sums > 0
					proba_3[_valid] = proba_3[_valid] / _row_sums[_valid, np.newaxis]
					proba_3[~_valid] = 1.0 / 3.0
					preds = decide_ternary_side_batch(
						proba_3,
						policy=ternary_policy if ternary_policy is not None else TernaryDecisionPolicy(),
					)
				n = len(preds)
				fold_m: dict[str, Any] = {
					"split_index": split.split_index,
				"train_rows": len(_train_df),
				"test_rows": len(_test_df),
					"loss": 0.0, "directional_accuracy": 0.0,
					"f1_macro": 0.0,
					"f1_short": 0.0, "f1_flat": 0.0, "f1_long": 0.0,
					"true_short_pct": 0.0, "true_flat_pct": 0.0, "true_long_pct": 0.0,
					"pred_short_pct": 0.0, "pred_flat_pct": 0.0, "pred_long_pct": 0.0,
				}
				if n > 0:
					# Directional accuracy : % de classes correctes (3 classes)
					fold_m["directional_accuracy"] = float((preds == test_labels_shifted).mean())
					# Brier score (MSE des probas vs one-hot) comme loss
					_one_hot = np.zeros((n, 3), dtype=np.float64)
					_one_hot[np.arange(n), test_labels_shifted] = 1.0
					fold_m["loss"] = float(np.mean((proba_3 - _one_hot) ** 2))
					for cls_idx, cls_name in enumerate(["short", "flat", "long"]):
						tp = int(((preds == cls_idx) & (test_labels_shifted == cls_idx)).sum())
						fp = int(((preds == cls_idx) & (test_labels_shifted != cls_idx)).sum())
						fn = int(((preds != cls_idx) & (test_labels_shifted == cls_idx)).sum())
						prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
						rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
						fold_m[f"f1_{cls_name}"] = float(2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0)
						fold_m[f"true_{cls_name}_pct"] = float((test_labels_shifted == cls_idx).mean() * 100)
						fold_m[f"pred_{cls_name}_pct"] = float((preds == cls_idx).mean() * 100)
					f1_vals = [fold_m[f"f1_{c}"] for c in ["short", "flat", "long"]]
					fold_m["f1_macro"] = float(np.mean(f1_vals)) if f1_vals else 0.0
				# Ajouter les dates du fold
				if "date" in _train_df.columns:
					fold_m["train_start_date"] = str(_train_df["date"].min().date())
					fold_m["train_end_date"] = str(_train_df["date"].max().date())
				if "date" in _test_df.columns:
					fold_m["test_start_date"] = str(_test_df["date"].min().date())
					fold_m["test_end_date"] = str(_test_df["date"].max().date())
				fold_metrics.append(fold_m)
			else:
				# Binaire
				test_proba = raw_proba_all[:, -1]
				acc = float((test_proba >= 0.5).astype(int) == test_labels).mean()
				fold_metrics.append({
					"split_index": split.split_index,
					"train_rows": len(_train_df),
					"test_rows": len(_test_df),
					"accuracy": acc,
				})

	if not fold_metrics:
		return {"status": "skipped", "reason": "all_folds_empty"}

	# ── Agrégation ──
	if is_regression:
		_keys = ["mse", "mae", "directional_accuracy", "ic",
		         "f1_macro", "f1_short", "f1_flat", "f1_long",
		         "true_short_pct", "true_flat_pct", "true_long_pct",
		         "pred_short_pct", "pred_flat_pct", "pred_long_pct"]
	else:
		_keys = ["loss", "directional_accuracy",
		         "f1_macro", "f1_short", "f1_flat", "f1_long",
				"true_short_pct", "true_flat_pct", "true_long_pct",
				"pred_short_pct", "pred_flat_pct", "pred_long_pct"]
	mean_metrics: dict[str, float | None] = {}
	for key in _keys:
		vals = [m[key] for m in fold_metrics if m.get(key) is not None]
		mean_metrics[key] = float(np.mean(vals)) if vals else None

	return {
		"status": "completed",
		"n_splits": len(fold_metrics),
		"mean": mean_metrics,
		"splits": fold_metrics,
	}
