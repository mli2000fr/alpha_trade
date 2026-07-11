"""modelFactory/evaluation.py — Évaluation avancée et analyses business.

Sprint Maître 1 — ajouts :
- Métriques multiclasses : one-vs-rest AUC, Brier multiclasse, log-loss,
  balanced accuracy, macro-F1, weighted-F1.
- Validation des probabilités (finies, somme = 1, bornes).
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


# ── Sprint Maître 1 : métriques multiclasses ─────────────────────────────────

def _validate_proba_array(proba: np.ndarray, *, tol: float = 1e-6) -> str | None:
    """Valide un tableau de probabilités [N, C]. Retourne None si OK."""
    if proba.ndim != 2:
        return f"expected_2d_got_{proba.ndim}d"
    if not np.isfinite(proba).all():
        return "non_finite_values"
    if (proba < 0).any() or (proba > 1).any():
        return "out_of_bounds"
    sums = proba.sum(axis=1)
    if (np.abs(sums - 1.0) > tol).any():
        return f"sum_not_one_max_dev={float(np.abs(sums - 1.0).max()):.8f}"
    return None


def multiclass_auc_one_vs_rest(
    y_true: np.ndarray,
    y_proba: np.ndarray,
) -> dict[str, float | None]:
    """Calcule l'AUC one-vs-rest pour chaque classe.

    Parameters
    ----------
    y_true : np.ndarray [N]
        Labels entiers (0, 1, 2, ...).
    y_proba : np.ndarray [N, C]
        Probabilités par classe.

    Returns
    -------
    dict avec clés ``auc_class_0``, ``auc_class_1``, ..., ``auc_macro``.
    Chaque AUC est bornée dans [0, 1] ; None si classe absente.
    """
    from modelFactory.tabular_baseline import binary_auc

    y_true = np.asarray(y_true, dtype=np.int64)
    y_proba = np.asarray(y_proba, dtype=np.float64)
    error = _validate_proba_array(y_proba)
    if error is not None:
        return {"auc_macro": None, "error": error}

    n_classes = y_proba.shape[1]
    aucs: dict[str, float | None] = {}
    valid_aucs: list[float] = []
    for c in range(n_classes):
        binary_labels = (y_true == c).astype(np.int64)
        if binary_labels.sum() == 0 or (binary_labels == 1).sum() == len(binary_labels):
            aucs[f"auc_class_{c}"] = None
            continue
        auc_val = binary_auc(binary_labels, y_proba[:, c])
        if auc_val is not None:
            if auc_val < 0.0 or auc_val > 1.0:
                auc_val = None  # AUC hors bornes → invalide
            else:
                valid_aucs.append(auc_val)
        aucs[f"auc_class_{c}"] = auc_val
    aucs["auc_macro"] = float(np.mean(valid_aucs)) if valid_aucs else None
    return aucs


def multiclass_brier_score(
    y_true: np.ndarray,
    y_proba: np.ndarray,
) -> float | None:
    """Brier score multiclasses : moyenne sur les classes du Brier one-vs-rest.

    .. math::
        BS = \\frac{1}{C} \\sum_{c=1}^{C} \\frac{1}{N} \\sum_{i=1}^{N} (p_{ic} - y_{ic})^2
    """
    y_true = np.asarray(y_true, dtype=np.int64)
    y_proba = np.asarray(y_proba, dtype=np.float64)
    error = _validate_proba_array(y_proba)
    if error is not None:
        return None
    n_classes = y_proba.shape[1]
    briers: list[float] = []
    for c in range(n_classes):
        binary_labels = (y_true == c).astype(np.float64)
        briers.append(float(np.mean((y_proba[:, c] - binary_labels) ** 2)))
    return float(np.mean(briers)) if briers else None


def multiclass_log_loss(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    *, eps: float = 1e-15,
) -> float | None:
    """Log-loss multiclasses.

    .. math::
        LL = -\\frac{1}{N} \\sum_{i=1}^{N} \\log(p_{i, y_i})
    """
    y_true = np.asarray(y_true, dtype=np.int64)
    y_proba = np.asarray(y_proba, dtype=np.float64)
    error = _validate_proba_array(y_proba)
    if error is not None:
        return None
    n_samples = len(y_true)
    if n_samples == 0:
        return None
    clipped = np.clip(y_proba, eps, 1 - eps)
    # Normaliser après clipping
    clipped = clipped / clipped.sum(axis=1, keepdims=True)
    log_probs = np.log(clipped[np.arange(n_samples), y_true])
    return float(-np.mean(log_probs))


def multiclass_balanced_accuracy(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> float | None:
    """Balanced accuracy multiclasses : moyenne des recalls par classe."""
    y_true = np.asarray(y_true, dtype=np.int64)
    y_pred = np.asarray(y_pred, dtype=np.int64)
    classes = np.unique(np.concatenate([y_true, y_pred]))
    if len(classes) < 2:
        return None
    recalls: list[float] = []
    for c in classes:
        mask_true = y_true == c
        if mask_true.sum() == 0:
            continue
        tp = int((y_pred[mask_true] == c).sum())
        recalls.append(tp / int(mask_true.sum()))
    return float(np.mean(recalls)) if recalls else None


def compute_multiclass_metrics(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    *,
    class_names: tuple[str, ...] = ("short", "flat", "long"),
) -> dict[str, Any]:
    """Calcule l'ensemble complet des métriques multiclasses.

    Parameters
    ----------
    y_true : np.ndarray [N]
        Labels entiers (0 = short, 1 = flat, 2 = long par défaut).
    y_proba : np.ndarray [N, C]
        Probabilités calibrées par classe.
    class_names : tuple[str, ...]
        Noms des classes dans l'ordre.

    Returns
    -------
    dict avec métriques par classe + agrégées.
    """
    y_true = np.asarray(y_true, dtype=np.int64)
    y_proba = np.asarray(y_proba, dtype=np.float64)

    result: dict[str, Any] = {}

    # Validation
    error = _validate_proba_array(y_proba)
    result["proba_valid"] = error is None
    if error is not None:
        result["proba_error"] = error
        return result

    n_classes = y_proba.shape[1]
    if len(class_names) != n_classes:
        class_names = tuple(f"class_{i}" for i in range(n_classes))

    # Prédictions (via argmax — la policy du Sprint 0 s'applique via decide_ternary_side_batch)
    y_pred = np.argmax(y_proba, axis=1).astype(np.int64)

    # AUC one-vs-rest
    auc_results = multiclass_auc_one_vs_rest(y_true, y_proba)
    result.update(auc_results)

    # Brier multiclasse
    result["brier_multiclass"] = multiclass_brier_score(y_true, y_proba)

    # Log-loss
    result["log_loss"] = multiclass_log_loss(y_true, y_proba)

    # Balanced accuracy
    result["balanced_accuracy"] = multiclass_balanced_accuracy(y_true, y_pred)

    # Per-class metrics
    for c in range(n_classes):
        name = class_names[c] if c < len(class_names) else f"class_{c}"
        mask_true = y_true == c
        mask_pred = y_pred == c
        tp = int((mask_true & mask_pred).sum())
        fp = int(((~mask_true) & mask_pred).sum())
        fn = int((mask_true & (~mask_pred)).sum())
        tn = int(((~mask_true) & (~mask_pred)).sum())

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

        result[f"precision_{name}"] = float(prec)
        result[f"recall_{name}"] = float(rec)
        result[f"f1_{name}"] = float(f1)
        result[f"support_{name}"] = int(mask_true.sum())

    # Macro / weighted F1
    f1_vals = [result[f"f1_{name}"] for name in class_names[:n_classes]]
    supports = [result[f"support_{name}"] for name in class_names[:n_classes]]
    result["f1_macro"] = float(np.mean(f1_vals)) if f1_vals else 0.0
    total_support = sum(supports)
    result["f1_weighted"] = (
        float(sum(f1 * s for f1, s in zip(f1_vals, supports)) / total_support)
        if total_support > 0 else 0.0
    )

    # Accuracy globale
    result["accuracy"] = float((y_true == y_pred).mean())

    # Distribution des classes prédites (pour détection de collapse)
    for c in range(n_classes):
        name = class_names[c] if c < len(class_names) else f"class_{c}"
        result[f"pred_fraction_{name}"] = float(mask_pred.mean())

    # Action rate (non-flat si flat est la classe 1)
    if n_classes == 3:
        result["action_rate"] = float((y_pred != 1).mean())

    return result


def check_model_collapse(
    y_proba: np.ndarray,
    *,
    min_action_rate: float = 0.01,
    min_class_fraction: float = 0.005,
    max_single_class_fraction: float = 0.99,
) -> tuple[bool, str | None]:
    """Détecte si un modèle est collapsed (prédit quasi toujours la même classe).

    Parameters
    ----------
    y_proba : np.ndarray [N, C]
        Probabilités.
    min_action_rate : float
        Taux d'action minimum (non-flat) pour les modèles ternaires.
    min_class_fraction : float
        Fraction minimum de prédictions pour chaque classe.
    max_single_class_fraction : float
        Fraction maximum acceptable pour une seule classe.

    Returns
    -------
    (is_collapsed, reason)
    """
    y_proba = np.asarray(y_proba, dtype=np.float64)
    if y_proba.ndim != 2 or y_proba.shape[1] < 2:
        return True, "invalid_proba_shape"
    if not np.isfinite(y_proba).all():
        return True, "non_finite_proba"

    y_pred = np.argmax(y_proba, axis=1)
    n = len(y_pred)
    if n < 10:
        return True, f"insufficient_samples_{n}"

    n_classes = y_proba.shape[1]
    class_counts = np.bincount(y_pred, minlength=n_classes)
    class_fractions = class_counts / n

    # Une classe domine trop
    if class_fractions.max() >= max_single_class_fraction:
        dominant = int(np.argmax(class_fractions))
        return True, f"single_class_dominant_{dominant}_{class_fractions[dominant]:.3f}"

    # Une classe quasi absente
    for c in range(n_classes):
        if class_fractions[c] < min_class_fraction:
            return True, f"class_{c}_near_absent_{class_fractions[c]:.4f}"

    # Pour ternaire : vérifier action_rate
    if n_classes == 3:
        action_rate = float((y_pred != 1).mean())
        if action_rate < min_action_rate:
            return True, f"action_rate_too_low_{action_rate:.4f}"

    return False, None


def compute_business_score(
    *,
    precision_long: float,
    coverage_at_threshold: float,
    avg_future_return_on_actions: float | None = None,
    hit_rate_on_actions: float | None = None,
) -> float:
    """Score métier simple pour classer les seuils de décision.

    Favorise d'abord la précision des signaux et une couverture non nulle,
    puis ajoute un bonus si les rendements futurs conditionnels sont positifs.
    """
    score = float(precision_long) * float(coverage_at_threshold)
    if avg_future_return_on_actions is not None:
        score += max(float(avg_future_return_on_actions), 0.0)
    if hit_rate_on_actions is not None:
        score += 0.10 * float(hit_rate_on_actions)
    return float(score)


def bucket_analysis(
    probabilities: np.ndarray,
    labels: np.ndarray,
    future_returns: np.ndarray | None = None,
    *,
    n_buckets: int = 5,
) -> dict[str, Any]:
    """Analyse les probabilités par bucket de conviction."""
    probs = np.asarray(probabilities, dtype=np.float64).reshape(-1)
    y = np.asarray(labels, dtype=np.float64).reshape(-1)
    if len(probs) == 0:
        return {
            "n_buckets": n_buckets,
            "base_rate": None,
            "monotonic_hit_rate": True,
            "top_bucket_hit_rate": None,
            "top_bucket_avg_future_return": None,
            "top_minus_bottom_bucket_hit_rate": None,
            "top_minus_bottom_bucket_return": None,
            "buckets": [],
        }

    future_ret = np.asarray(future_returns, dtype=np.float64).reshape(-1) if future_returns is not None else None
    base_rate = float(y.mean()) if len(y) else None
    order = np.argsort(probs)
    bucket_edges = np.array_split(order, n_buckets)
    buckets: list[dict[str, Any]] = []
    for bucket_id, idx in enumerate(bucket_edges, start=1):
        if len(idx) == 0:
            continue
        bucket_probs = probs[idx]
        bucket_labels = y[idx]
        row: dict[str, Any] = {
            "bucket": bucket_id,
            "count": int(len(idx)),
            "proba_min": float(bucket_probs.min()),
            "proba_max": float(bucket_probs.max()),
            "proba_mean": float(bucket_probs.mean()),
            "hit_rate": float(bucket_labels.mean()),
            "lift_vs_base_rate": (float(bucket_labels.mean()) / base_rate) if base_rate not in (None, 0.0) else None,
        }
        if future_ret is not None and len(future_ret) == len(probs):
            bucket_returns = future_ret[idx]
            row["avg_future_return"] = float(bucket_returns.mean())
            row["median_future_return"] = float(np.median(bucket_returns))
        buckets.append(row)

    monotonic_hit_rate = all(
        buckets[i]["hit_rate"] <= buckets[i + 1]["hit_rate"]
        for i in range(len(buckets) - 1)
    ) if len(buckets) > 1 else True

    bottom_bucket = buckets[0] if buckets else None
    top_bucket = buckets[-1] if buckets else None

    return {
        "n_buckets": n_buckets,
        "base_rate": base_rate,
        "monotonic_hit_rate": monotonic_hit_rate,
        "top_bucket_hit_rate": top_bucket.get("hit_rate") if top_bucket else None,
        "top_bucket_avg_future_return": top_bucket.get("avg_future_return") if top_bucket else None,
        "top_minus_bottom_bucket_hit_rate": (
            float(top_bucket["hit_rate"] - bottom_bucket["hit_rate"])
            if top_bucket is not None and bottom_bucket is not None
            else None
        ),
        "top_minus_bottom_bucket_return": (
            float((top_bucket.get("avg_future_return") or 0.0) - (bottom_bucket.get("avg_future_return") or 0.0))
            if top_bucket is not None and bottom_bucket is not None
            and "avg_future_return" in top_bucket and "avg_future_return" in bottom_bucket
            else None
        ),
        "buckets": buckets,
    }


def compute_threshold_metrics(
    probabilities: np.ndarray,
    labels: np.ndarray,
    future_returns: np.ndarray | None,
    *,
    decision_threshold: float,
    n_buckets: int = 5,
) -> dict[str, Any]:
    """Calcule les métriques business conditionnelles au seuil de décision.

    Pour les probabilités multi-classes (shape [N, C] avec C > 1), la colonne
    correspondant à la classe "long" (indice 2 ou dernière colonne) est extraite
    automatiquement.
    """
    probs_raw = np.asarray(probabilities, dtype=np.float64)
    if probs_raw.ndim == 2 and probs_raw.shape[1] > 1:
        # Multi-classes → extraire la colonne "long" (classe positive)
        long_col = min(2, probs_raw.shape[1] - 1)
        probs = probs_raw[:, long_col].reshape(-1)
    else:
        probs = probs_raw.reshape(-1)
    y = np.asarray(labels, dtype=np.int64).reshape(-1)
    future_ret = np.asarray(future_returns, dtype=np.float64).reshape(-1) if future_returns is not None else None

    action_mask = probs >= float(decision_threshold)
    coverage = float(action_mask.mean()) if len(probs) else 0.0
    selected_labels = y[action_mask]
    selected_returns = future_ret[action_mask] if future_ret is not None and len(future_ret) == len(probs) else None

    precision_long = float(selected_labels.mean()) if len(selected_labels) else 0.0
    positives = int((y == 1).sum())
    tp = int(((action_mask.astype(np.int64) == 1) & (y == 1)).sum())
    recall_long = float(tp / positives) if positives else 0.0

    avg_return = float(selected_returns.mean()) if selected_returns is not None and len(selected_returns) else None
    median_return = float(np.median(selected_returns)) if selected_returns is not None and len(selected_returns) else None
    hit_rate = float((selected_returns > 0.0).mean()) if selected_returns is not None and len(selected_returns) else None

    payoff_ratio: float | None = None
    if selected_returns is not None and len(selected_returns):
        pos_returns = selected_returns[selected_returns > 0.0]
        neg_returns = selected_returns[selected_returns < 0.0]
        if len(pos_returns) and len(neg_returns):
            payoff_ratio = float(pos_returns.mean() / abs(neg_returns.mean())) if abs(float(neg_returns.mean())) > 1e-12 else None

    bucket_stats = bucket_analysis(probs, y, future_ret, n_buckets=n_buckets)
    business_score = compute_business_score(
        precision_long=precision_long,
        coverage_at_threshold=coverage,
        avg_future_return_on_actions=avg_return,
        hit_rate_on_actions=hit_rate,
    )
    return {
        "decision_threshold": float(decision_threshold),
        "coverage_at_threshold": coverage,
        "precision_long": precision_long,
        "recall_long": recall_long,
        "avg_future_return_on_actions": avg_return,
        "median_future_return_on_actions": median_return,
        "hit_rate_on_actions": hit_rate,
        "payoff_ratio": payoff_ratio,
        "top_bucket_hit_rate": bucket_stats.get("top_bucket_hit_rate"),
        "top_bucket_avg_future_return": bucket_stats.get("top_bucket_avg_future_return"),
        "top_minus_bottom_bucket_hit_rate": bucket_stats.get("top_minus_bottom_bucket_hit_rate"),
        "top_minus_bottom_bucket_return": bucket_stats.get("top_minus_bottom_bucket_return"),
        "bucket_analysis": bucket_stats,
        "threshold_business_score": business_score,
    }


def optimize_decision_threshold(
    probabilities: np.ndarray,
    labels: np.ndarray,
    future_returns: np.ndarray | None,
    *,
    candidate_thresholds: tuple[float, ...] | list[float],
    default_threshold: float,
    min_action_rate: float,
    max_action_rate: float,
    min_precision_long: float,
    n_buckets: int = 5,
) -> dict[str, Any]:
    """Sélectionne le meilleur seuil de décision sur validation."""
    candidates: list[dict[str, Any]] = []
    valid_candidates: list[dict[str, Any]] = []

    for threshold in candidate_thresholds:
        metrics = compute_threshold_metrics(
            probabilities,
            labels,
            future_returns,
            decision_threshold=float(threshold),
            n_buckets=n_buckets,
        )
        failures: list[str] = []
        coverage = float(metrics["coverage_at_threshold"])
        precision_long = float(metrics["precision_long"])
        if coverage < min_action_rate:
            failures.append("min_action_rate")
        if coverage > max_action_rate:
            failures.append("max_action_rate")
        if precision_long < min_precision_long:
            failures.append("min_precision_long")

        row = {
            **metrics,
            "passes_constraints": len(failures) == 0,
            "constraint_failures": failures,
        }
        candidates.append(row)
        if row["passes_constraints"]:
            valid_candidates.append(row)

    if valid_candidates:
        selected = max(
            valid_candidates,
            key=lambda m: (
                float(m["threshold_business_score"]),
                float(m["precision_long"]),
                float(m["coverage_at_threshold"]),
                -float(m["decision_threshold"]),
            ),
        )
        status = "selected"
    else:
        selected = compute_threshold_metrics(
            probabilities,
            labels,
            future_returns,
            decision_threshold=float(default_threshold),
            n_buckets=n_buckets,
        )
        status = "fallback_default_threshold"

    return {
        "enabled": True,
        "selection_status": status,
        "selected_threshold": float(selected["decision_threshold"]),
        "selected_business_score": float(selected["threshold_business_score"]),
        "constraints": {
            "min_action_rate": float(min_action_rate),
            "max_action_rate": float(max_action_rate),
            "min_precision_long": float(min_precision_long),
        },
        "selected_metrics": selected,
        "candidates": candidates,
    }


def align_sequence_rows(df: pd.DataFrame, seq_len: int) -> pd.DataFrame:
    """Aligne les lignes du DataFrame avec les séquences construites pour le modèle."""
    if "target" not in df.columns:
        raise ValueError("align_sequence_rows requiert une colonne 'target'.")
    aligned = df.iloc[seq_len:].copy()
    return aligned.loc[aligned["target"].notna()].reset_index(drop=True)

