"""Calcul du conviction score unifié V2.

.. deprecated:: Phase 5.1.b
    Utiliser :func:`core.conviction.fuse` (typed via
    :class:`core.conviction.ConvictionWeights`). Ce module reste un wrapper
    rétrocompat qui émet un ``DeprecationWarning``.
"""
from __future__ import annotations

import warnings


def compute_conviction(
    score_used: float,
    predicted_proba: float | None,
    score_weight: float,
    prediction_weight: float,
) -> float:
    """Retourne le conviction score combinant score quant et prédiction ML.

    .. deprecated:: Phase 5.1.b
        Préférer ``core.conviction.fuse(quant_score=..., predicted_proba=...,
        weights=ConvictionWeights(...))``.
    """
    warnings.warn(
        "risk_management.conviction.compute_conviction is deprecated; "
        "use core.conviction.fuse instead (Phase 5.1.b).",
        DeprecationWarning,
        stacklevel=2,
    )
    if predicted_proba is not None:
        return score_weight * score_used + prediction_weight * predicted_proba
    return score_used

