"""Formule de fusion de la conviction (quant + ML/sentiment).

Phase 2.1 du refactor (`prompt/refactor/plan.md`).

Centralise la formule **unique** consommée par :
- ``risk_management/portfolio_builder.py`` (sizing live / paper) ;
- ``event_sentiment/signal_aggregator.py`` (fusion sentiment) — Phase 4.1 ;
- ``backtesting/signal_replay.py`` (rejeu cohérent) — Phase 6.1.

Le corps actuel délègue à ``risk_management.conviction`` pour préserver la
compatibilité ascendante (zéro changement runtime). La centralisation
permet aux modules amont d'importer une seule API stable :

    from core.conviction import compute_conviction, ConvictionWeights
"""
from __future__ import annotations

from dataclasses import dataclass

from risk_management.conviction import compute_conviction as _compute_conviction


@dataclass(frozen=True, slots=True)
class ConvictionWeights:
    """Pondérations pour la fusion conviction.

    Convention historique projet (audit_risk_management §pondérations) :
    ``score_weight=0.4``, ``prediction_weight=0.6``. À calibrer
    empiriquement Phase 7 (audit_global Long terme).
    """

    score_weight: float = 0.4
    prediction_weight: float = 0.6

    def __post_init__(self) -> None:
        if self.score_weight < 0 or self.prediction_weight < 0:
            raise ValueError("ConvictionWeights : poids négatifs interdits.")
        if self.score_weight + self.prediction_weight <= 0:
            raise ValueError("ConvictionWeights : somme des poids doit être > 0.")


def compute_conviction(
    score_used: float,
    predicted_proba: float | None,
    score_weight: float,
    prediction_weight: float,
) -> float:
    """Retourne le conviction score combinant score quant et prédiction ML.

    Délègue à :func:`risk_management.conviction.compute_conviction` pour
    préserver le comportement existant. Les nouveaux consommateurs sont
    encouragés à passer par :func:`fuse` qui prend un objet
    :class:`ConvictionWeights` typé.
    """
    return _compute_conviction(score_used, predicted_proba, score_weight, prediction_weight)


def fuse(
    *,
    quant_score: float,
    predicted_proba: float | None,
    weights: ConvictionWeights | None = None,
) -> float:
    """Variante typée recommandée pour les nouveaux call-sites."""
    w = weights or ConvictionWeights()
    return compute_conviction(quant_score, predicted_proba, w.score_weight, w.prediction_weight)


__all__ = ["ConvictionWeights", "compute_conviction", "fuse"]

