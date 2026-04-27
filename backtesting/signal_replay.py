"""
backtesting/signal_replay.py
==============================
Reconstruit les signaux de trading jour par jour à partir des scores,
du sentiment et des prédictions ML, en réutilisant la logique de conviction
du module risk_management.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

# Phase 6.1.a — fusion conviction unifiée via core.conviction
# (auparavant : risk_management.conviction, désormais déprécié).
from core.conviction import ConvictionWeights, fuse

LOGGER = logging.getLogger(__name__)


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

    Parameters
    ----------
    scores_df : DataFrame
        Colonnes : symbol, trade_date, final_score_sentiment (ou final_score), sector
    predictions_df : DataFrame | None
        Colonnes : symbol, trade_date, predicted_proba
    score_weight, prediction_weight : poids de la conviction
    max_positions : nombre max de candidats retenus par jour

    Returns
    -------
    DataFrame avec colonnes : trade_date, symbol, score, predicted_proba, conviction, rank, selected
    """
    preferred_score_column = score_column if score_column in scores_df.columns else None
    # Utiliser la colonne demandée si fournie, sinon final_score_sentiment puis final_score.
    # Si la colonne primaire contient des trous, fallback ligne par ligne sur final_score.
    candidate_columns = [
        "symbol", "trade_date", preferred_score_column,
        "final_score_walk_forward", "final_score_sentiment", "final_score", "sector", "score_source",
    ]
    base_columns: list[str] = []
    for col in candidate_columns:
        if col is None or col not in scores_df.columns or col in base_columns:
            continue
        base_columns.append(col)
    df = scores_df[base_columns].copy()
    df["score_source"] = df["score_source"] if "score_source" in df.columns else pd.NA
    if preferred_score_column is not None:
        df["score"] = df[preferred_score_column]
        df.loc[df[preferred_score_column].notna(), "score_source"] = preferred_score_column
        if "final_score_sentiment" in df.columns and preferred_score_column != "final_score_sentiment":
            missing_mask = df["score"].isna()
            df.loc[missing_mask, "score"] = df.loc[missing_mask, "final_score_sentiment"]
            df.loc[missing_mask & df["final_score_sentiment"].notna(), "score_source"] = "final_score_sentiment"
        if "final_score" in df.columns:
            missing_mask = df["score"].isna()
            df.loc[missing_mask, "score"] = df.loc[missing_mask, "final_score"]
            df.loc[missing_mask & df["final_score"].notna(), "score_source"] = "final_score"
    elif "final_score_walk_forward" in df.columns:
        df["score"] = df["final_score_walk_forward"]
        df.loc[df["final_score_walk_forward"].notna(), "score_source"] = "final_score_walk_forward"
        if "final_score_sentiment" in df.columns:
            missing_mask = df["score"].isna()
            df.loc[missing_mask, "score"] = df.loc[missing_mask, "final_score_sentiment"]
            df.loc[missing_mask & df["final_score_sentiment"].notna(), "score_source"] = "final_score_sentiment"
        if "final_score" in df.columns:
            missing_mask = df["score"].isna()
            df.loc[missing_mask, "score"] = df.loc[missing_mask, "final_score"]
            df.loc[missing_mask & df["final_score"].notna(), "score_source"] = "final_score"
    elif "final_score_sentiment" in df.columns:
        df["score"] = df["final_score_sentiment"]
        df.loc[df["final_score_sentiment"].notna(), "score_source"] = "final_score_sentiment"
        if "final_score" in df.columns:
            missing_mask = df["score"].isna()
            df.loc[missing_mask, "score"] = df.loc[missing_mask, "final_score"]
            df.loc[missing_mask & df["final_score"].notna(), "score_source"] = "final_score"
    elif "final_score" in df.columns:
        df["score"] = df["final_score"]
        df.loc[df["final_score"].notna(), "score_source"] = "final_score"
    else:
        raise ValueError("scores_df doit contenir final_score_sentiment ou final_score.")

    if "sector" not in df.columns:
        df["sector"] = None

    df = df[["symbol", "trade_date", "score", "score_source", "sector"]].copy()

    # Merger les prédictions ML si disponibles
    if predictions_df is not None and len(predictions_df) > 0:
        preds = predictions_df[["symbol", "trade_date", "predicted_proba"]].copy()
        df = df.merge(preds, on=["symbol", "trade_date"], how="left")
    else:
        df["predicted_proba"] = np.nan

    # Calculer la conviction (Phase 6.1.a — via core.conviction.fuse)
    conviction_weights = ConvictionWeights(
        score_weight=score_weight,
        prediction_weight=prediction_weight,
    )
    df["conviction"] = df.apply(
        lambda r: fuse(
            quant_score=float(r["score"]) if pd.notna(r["score"]) else 0.0,
            predicted_proba=(
                float(r["predicted_proba"]) if pd.notna(r["predicted_proba"]) else None
            ),
            weights=conviction_weights,
        ),
        axis=1,
    )

    # Rank par jour, sélectionner top-N
    df["rank"] = df.groupby("trade_date")["conviction"].rank(ascending=False, method="first")
    df["selected"] = df["rank"] <= max_positions

    LOGGER.info(
        "Signaux reconstruits : %d jours, %d entrées sélectionnées",
        df["trade_date"].nunique(),
        df["selected"].sum(),
    )
    return df

