"""modelFactory/evaluation.py — Évaluation avancée et analyses business."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


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

