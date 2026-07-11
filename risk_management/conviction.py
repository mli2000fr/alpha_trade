"""Calcul du conviction score unifié V2.

.. deprecated:: Phase 5.1.b
    Utiliser :func:`core.conviction.fuse` (typed via
    :class:`core.conviction.ConvictionWeights`). Ce module reste un wrapper
    rétrocompat qui émet un ``DeprecationWarning``.
"""
from __future__ import annotations

import warnings


def compute_conviction(
    score_used: float = 0.0,
    predicted_proba: float | None = None,
    score_weight: float = 0.0,
    prediction_weight: float = 1.0,
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
    from core.conviction import compute_conviction as compute_ml_conviction

    return compute_ml_conviction(
        score_used,
        predicted_proba,
        score_weight,
        prediction_weight,
    )

