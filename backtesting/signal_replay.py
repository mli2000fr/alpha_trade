"""
backtesting/signal_replay.py
==============================
Reconstruit les signaux de trading jour par jour à partir des scores,
du sentiment et des prédictions ML, en réutilisant la logique de conviction
du module ``core.conviction``.

Refactor Phase A (refactor/backtesting/audit_plan.md) :
- A2 : ``fuse()`` vectorisé (suppression du ``df.apply`` ligne par ligne).
- A3 : cascade de fallback factorisée via ``_pick_score_column`` +
       ``SCORE_FALLBACK_PRIORITY`` (au lieu de 4 branches dupliquées).
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

import numpy as np
import pandas as pd

from core.conviction import ConvictionWeights

LOGGER = logging.getLogger(__name__)

# Ordre de priorité des colonnes de score (du plus riche au plus brut).
SCORE_FALLBACK_PRIORITY: tuple[str, ...] = (
    "final_score_walk_forward",
    "final_score_sentiment",
    "final_score",
)


def _pick_score_column(
    df: pd.DataFrame,
    preferred: str | None,
    fallback_priority: Iterable[str] = SCORE_FALLBACK_PRIORITY,
) -> tuple[pd.Series, pd.Series]:
    """Construit ``(score, score_source)`` à partir d'une cascade de colonnes.

    Prend d'abord ``preferred`` si fourni et présent, puis comble les NaN
    restants avec les colonnes du ``fallback_priority`` dans l'ordre.
    """
    columns_in_order: list[str] = []
    if preferred and preferred in df.columns:
        columns_in_order.append(preferred)
    for col in fallback_priority:
        if col in df.columns and col not in columns_in_order:
            columns_in_order.append(col)

    if not columns_in_order:
        raise ValueError(
            "scores_df doit contenir au moins une colonne parmi "
            f"{list(fallback_priority)} (ou ``preferred`` valide)."
        )

    score = pd.Series(np.nan, index=df.index, dtype=float)
    source = pd.Series(pd.NA, index=df.index, dtype="object")
    for col in columns_in_order:
        col_series = pd.to_numeric(df[col], errors="coerce")
        missing_mask = score.isna() & col_series.notna()
        if not missing_mask.any():
            continue
        score = score.where(~missing_mask, col_series)
        source = source.where(~missing_mask, col)
    return score, source


def _vectorized_fuse(
    scores: pd.Series,
    predicted_proba: pd.Series,
    weights: ConvictionWeights,
) -> pd.Series:
    """Variante vectorisée de ``core.conviction.fuse``.

    - ``predicted_proba`` NaN sur une ligne → conviction = score brut.
    - sinon → ``score_weight * score + prediction_weight * proba``.
    NaN dans ``score`` → 0.0 (cohérent avec l'ancien call-site).
    """
    score_arr = scores.fillna(0.0).to_numpy(dtype=float)
    proba_arr = predicted_proba.to_numpy(dtype=float)
    has_proba = ~np.isnan(proba_arr)
    fused = np.where(
        has_proba,
        weights.score_weight * score_arr + weights.prediction_weight * np.nan_to_num(proba_arr),
        score_arr,
    )
    # Clip de securite [0, 1] — coherent avec core.conviction.compute_conviction
    fused = np.clip(fused, 0.0, 1.0)
    return pd.Series(fused, index=scores.index, name="conviction")


def replay_signals(
    scores_df: pd.DataFrame,
    predictions_df: Optional[pd.DataFrame],
    *,
    score_column: str | None = None,
    score_weight: float = 0.40,
    prediction_weight: float = 0.60,
    max_positions: int = 20,
) -> pd.DataFrame:
    """Reconstruit les signaux de conviction quotidiens.

    Returns
    -------
    DataFrame : trade_date, symbol, score, score_source, sector,
                predicted_proba, conviction, rank, selected.
    """
    base_columns = ["symbol", "trade_date"]
    optional_columns = [
        score_column,
        *SCORE_FALLBACK_PRIORITY,
        "sector",
        "score_source",
    ]
    keep_columns = list(base_columns)
    for col in optional_columns:
        if col is None:
            continue
        if col in scores_df.columns and col not in keep_columns:
            keep_columns.append(col)

    df = scores_df[keep_columns].copy()
    score, source = _pick_score_column(df, preferred=score_column)
    df["score"] = score.values
    # Lorsqu'une colonne de score explicite est demandée (--score-column),
    # la source résolue prend priorité sur un éventuel score_source préexistant
    # (ex. label "final_score_walk_forward" posé par l'overlay walk-forward).
    if "score_source" in df.columns and score_column is None:
        existing_source = df["score_source"]
        df["score_source"] = existing_source.where(existing_source.notna(), source.values)
    else:
        df["score_source"] = source.values

    if "sector" not in df.columns:
        df["sector"] = None

    df = df[["symbol", "trade_date", "score", "score_source", "sector"]].copy()

    if predictions_df is not None and len(predictions_df) > 0:
        preds = predictions_df[["symbol", "trade_date", "predicted_proba"]].copy()
        df = df.merge(preds, on=["symbol", "trade_date"], how="left")
    else:
        df["predicted_proba"] = np.nan

    weights = ConvictionWeights(
        score_weight=score_weight,
        prediction_weight=prediction_weight,
    )
    df["conviction"] = _vectorized_fuse(df["score"], df["predicted_proba"], weights)
    df["conviction_source"] = np.where(
        df["predicted_proba"].notna(),
        "core.conviction:score_plus_prediction",
        "core.conviction:score_only",
    )

    df["rank"] = df.groupby("trade_date")["conviction"].rank(ascending=False, method="first")
    df["selected"] = df["rank"] <= max_positions

    LOGGER.info(
        "Signaux reconstruits : %d jours, %d entrées sélectionnées",
        df["trade_date"].nunique(),
        int(df["selected"].sum()),
    )
    return df

