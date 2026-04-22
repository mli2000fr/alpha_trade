"""modelFactory/evaluation.py — Évaluation avancée et analyses business."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


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
        return {"n_buckets": n_buckets, "buckets": []}

    future_ret = np.asarray(future_returns, dtype=np.float64).reshape(-1) if future_returns is not None else None
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

    return {
        "n_buckets": n_buckets,
        "monotonic_hit_rate": monotonic_hit_rate,
        "buckets": buckets,
    }


def align_sequence_rows(df: pd.DataFrame, seq_len: int) -> pd.DataFrame:
    """Aligne les lignes du DataFrame avec les séquences construites pour le modèle."""
    if "target" not in df.columns:
        raise ValueError("align_sequence_rows requiert une colonne 'target'.")
    aligned = df.iloc[seq_len:].copy()
    return aligned.loc[aligned["target"].notna()].reset_index(drop=True)

