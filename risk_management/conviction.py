"""Calcul du conviction score unifié V2."""
from __future__ import annotations


def compute_conviction(
    score_used: float,
    predicted_proba: float | None,
    score_weight: float,
    prediction_weight: float,
) -> float:
    """Retourne le conviction score combinant score quant et prédiction ML."""
    if predicted_proba is not None:
        return score_weight * score_used + prediction_weight * predicted_proba
    return score_used

