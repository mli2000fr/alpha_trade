"""Métriques légères partagées pour l'évaluation de l'Oracle Extreme.

Ce module est indépendant de l'entraînement afin que l'IHM ne charge pas
PyTorch, LightGBM ou CatBoost pour afficher un diagnostic.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    """AUC (Mann-Whitney) sans dépendance scikit-learn."""
    y = np.asarray(y_true, dtype=float)
    s = np.asarray(y_score, dtype=float)
    mask = np.isfinite(s)
    y, s = y[mask], s[mask]
    pos = y == 1.0
    neg = y == 0.0
    if pos.sum() == 0 or neg.sum() == 0:
        return None
    ranks = pd.Series(s).rank(method="average").to_numpy()
    r_pos = ranks[pos].sum()
    auc = (r_pos - pos.sum() * (pos.sum() + 1) / 2.0) / (pos.sum() * neg.sum())
    return float(auc)


def precision_recall_at_top_pct(
    df: pd.DataFrame,
    score_col: str,
    pct: float = 0.10,
    min_universe: int = 20,
    target_col: str = "oracle_extreme10",
) -> dict[str, float | None]:
    """Précision/rappel cross-sectionnel du TOP pct moyenné par date."""
    rows: list[dict[str, float]] = []
    for _, group in df.groupby("date"):
        group = group.dropna(subset=[score_col, target_col])
        if len(group) < min_universe:
            continue
        n_top = max(1, int(np.ceil(len(group) * pct)))
        top = group.nlargest(n_top, score_col)
        precision = float(top[target_col].mean())
        n_actual = int(group[target_col].sum())
        recall = float(top[target_col].sum() / n_actual) if n_actual > 0 else None
        rows.append({"precision": precision, "recall": recall})
    if not rows:
        return {"precision": None, "recall": None, "n_dates": 0}
    frame = pd.DataFrame(rows)
    return {
        "precision": float(frame["precision"].mean()),
        "recall": float(frame["recall"].mean()),
        "n_dates": int(len(frame)),
    }


def decile_monotonicity(
    df: pd.DataFrame,
    score_col: str,
) -> tuple[float | None, pd.DataFrame]:
    """Déciles cross-sectionnels du score, rendement moyen et Spearman."""
    sub = df.dropna(subset=[score_col, "future_return"]).copy()
    if sub.empty:
        return None, pd.DataFrame()
    sub["_dec"] = (
        np.floor(
            sub.groupby("date")[score_col]
            .rank(pct=True)
            .clip(upper=1 - 1e-9)
            * 10
        )
        .clip(0, 9)
        .astype(int)
        + 1
    )
    stats = sub.groupby("_dec")["future_return"].agg(
        mean="mean", median="median", count="count"
    )
    if len(stats) < 2:
        return None, stats
    x = pd.Series(stats.index, dtype=float).rank().to_numpy()
    y = pd.Series(stats["mean"].to_numpy(dtype=float)).rank().to_numpy()
    corr = np.corrcoef(x, y)[0, 1]
    return float(corr) if np.isfinite(corr) else None, stats
