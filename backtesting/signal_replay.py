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

from risk_management.conviction import compute_conviction

LOGGER = logging.getLogger(__name__)


def replay_signals(
    scores_df: pd.DataFrame,
    predictions_df: Optional[pd.DataFrame],
    *,
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
    # Utiliser final_score_sentiment si disponible, sinon final_score.
    # Si final_score_sentiment existe mais contient des trous, fallback ligne par ligne sur final_score.
    base_columns = [col for col in ["symbol", "trade_date", "final_score_sentiment", "final_score", "sector"] if col in scores_df.columns]
    df = scores_df[base_columns].copy()
    if "final_score_sentiment" in df.columns:
        df["score"] = df["final_score_sentiment"]
        if "final_score" in df.columns:
            missing_mask = df["score"].isna()
            df.loc[missing_mask, "score"] = df.loc[missing_mask, "final_score"]
    elif "final_score" in df.columns:
        df["score"] = df["final_score"]
    else:
        raise ValueError("scores_df doit contenir final_score_sentiment ou final_score.")

    if "sector" not in df.columns:
        df["sector"] = None

    df = df[["symbol", "trade_date", "score", "sector"]].copy()

    # Merger les prédictions ML si disponibles
    if predictions_df is not None and len(predictions_df) > 0:
        preds = predictions_df[["symbol", "trade_date", "predicted_proba"]].copy()
        df = df.merge(preds, on=["symbol", "trade_date"], how="left")
    else:
        df["predicted_proba"] = np.nan

    # Calculer la conviction
    df["conviction"] = df.apply(
        lambda r: compute_conviction(
            r["score"],
            r["predicted_proba"] if pd.notna(r["predicted_proba"]) else None,
            score_weight,
            prediction_weight,
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

