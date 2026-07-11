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

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Union

import numpy as np

LOGGER = logging.getLogger(__name__)


if TYPE_CHECKING:
    from numpy.typing import ArrayLike

    Number = Union[float, ArrayLike]
else:  # pragma: no cover - runtime alias
    Number = object


@dataclass(frozen=True, slots=True)
class ConvictionWeights:
    """Ancien paramétrage de fusion, conservé pour les artefacts historiques.

    Le ranking de sélection ML-first ne consomme plus ces poids: sa conviction
    est la probabilité directionnelle du modèle. Le score technique intervient
    uniquement dans un veto post-prédiction.
    """

    score_weight: float = 0.4
    prediction_weight: float = 0.6

    def __post_init__(self) -> None:
        if self.score_weight < 0 or self.prediction_weight < 0:
            raise ValueError("ConvictionWeights : poids négatifs interdits.")
        total = self.score_weight + self.prediction_weight
        if not np.isclose(total, 1.0, atol=1e-6):
            raise ValueError(
                "ConvictionWeights : la somme des poids doit etre ~1.0 "
                f"(actuel : {total:.6f})."
            )
        if total <= 0:
            raise ValueError("ConvictionWeights : somme des poids doit être > 0.")


def compute_conviction(
    score_used: float,
    predicted_proba: float | None,
    score_weight: float,
    prediction_weight: float,
) -> float:
        """Retourne la probabilité ML long, obligatoire pour une sélection.

        ``score_used`` et les poids sont conservés dans la signature pour la
        compatibilité des appels existants, mais n'influencent plus le ranking.
        """
        del score_used, score_weight, prediction_weight
        if predicted_proba is None or not np.isfinite(predicted_proba):
            raise ValueError("Une probabilité ML long finie est obligatoire pour la conviction.")
        return float(np.clip(predicted_proba, 0.0, 1.0))


def compute_conviction_short(
    score_used: float,
    predicted_proba_short: float | None,
    score_weight: float,
    prediction_weight: float,
) -> float:
        """Retourne la probabilité ML short, obligatoire pour une sélection."""
        del score_used, score_weight, prediction_weight
        if predicted_proba_short is None or not np.isfinite(predicted_proba_short):
            raise ValueError("Une probabilité ML short finie est obligatoire pour la conviction.")
        return float(np.clip(predicted_proba_short, 0.0, 1.0))


def fuse(
    *,
    quant_score: float,
    predicted_proba: float | None,
    weights: ConvictionWeights | None = None,
) -> float:
    """Variante typée recommandée pour les nouveaux call-sites."""
    w = weights or ConvictionWeights()
    return compute_conviction(quant_score, predicted_proba, w.score_weight, w.prediction_weight)


def fuse_short(
    *,
    quant_score: float,
    predicted_proba_short: float | None,
    weights: ConvictionWeights | None = None,
) -> float:
    """Variante typée pour les shorts — inverse le score quant."""
    w = weights or ConvictionWeights()
    return compute_conviction_short(quant_score, predicted_proba_short, w.score_weight, w.prediction_weight)


__all__ = [
    "ConvictionWeights",
    "SentimentFusionWeights",
    "compute_conviction",
    "fuse",
    "fuse_short",
    "fuse_sentiment",
]


@dataclass(frozen=True, slots=True)
class SentimentFusionWeights:
    """Pondérations pour la fusion ternaire **quant + sentiment + macro**.

    Convention calibrée empiriquement (diagnostic IC 2024-2025) :
    - macro_weight = 0.00 (IC ≈ 0, t-stat ≈ 0 — aucun pouvoir prédictif)
    - sentiment_weight = 0.00 (IC ≈ 0.01, t-stat ≈ 1.1 — non significatif,
      désactivé par défaut ; laissé explorable dans la grille de calibration)
    - quant_weight = 1.00 (IC ≈ 0.03, t-stat ≈ 2.5 — seul signal significatif)

    La somme doit être proche de 1.0 (tolérance ``1e-4``). Tous les poids doivent être ≥ 0.
    """

    quant_weight: float = 1.00
    sentiment_weight: float = 0.00
    macro_weight: float = 0.00

    def __post_init__(self) -> None:
        if self.quant_weight < 0 or self.sentiment_weight < 0 or self.macro_weight < 0:
            raise ValueError("SentimentFusionWeights : poids négatifs interdits.")
        total = self.quant_weight + self.sentiment_weight + self.macro_weight
        if not np.isclose(total, 1.0, atol=1e-4):
            raise ValueError(
                "SentimentFusionWeights : somme des poids doit être ≈ 1.0 "
                f"(actuel : {total:.4f})."
            )


def fuse_sentiment(
    *,
    quant_score: "Number",
    sentiment_signal_norm: "Number",
    macro_signal_norm: "Number",
    weights: SentimentFusionWeights | None = None,
    signal_active: "Number" = True,
) -> "np.ndarray | float":
    """Fusion ternaire ``final_score_sentiment`` clipée dans ``[0, 1]``.

    Réplique strictement la formule historique de
    ``event_sentiment.signal_aggregator.SentimentSignalAggregator.merge``
    (lignes 926-944) afin d'offrir une API centralisée :

        sent  = sentiment_weight * (sentiment_signal_norm if active else 0.5)
        macro = macro_weight     * macro_signal_norm
        quant = quant_weight     * quant_score
        final = clip(quant + sent + macro, 0.0, 1.0)

    Accepte des scalaires ou des array-like (broadcast NumPy).
    """
    w = weights or SentimentFusionWeights()
    quant_arr = np.asarray(quant_score, dtype=float)
    sentiment_arr = np.asarray(sentiment_signal_norm, dtype=float)
    macro_arr = np.asarray(macro_signal_norm, dtype=float)
    active_arr = np.asarray(signal_active, dtype=bool)

    sent_component = np.where(
        active_arr,
        w.sentiment_weight * sentiment_arr,
        w.sentiment_weight * 0.5,
    )
    macro_component = w.macro_weight * macro_arr
    quant_component = w.quant_weight * quant_arr
    fused = np.clip(quant_component + sent_component + macro_component, 0.0, 1.0)
    if fused.ndim == 0:
        result = float(fused)
        LOGGER.debug(
            "sentiment_fusion | quant=%.4f (w=%.2f) sent=%.4f (w=%.2f) macro=%.4f (w=%.2f) → fused=%.4f",
            float(quant_arr), w.quant_weight,
            float(sentiment_arr), w.sentiment_weight,
            float(macro_arr), w.macro_weight,
            result,
        )
        return result
    LOGGER.debug(
        "sentiment_fusion | batch=%s quant_mean=%.4f sent_mean=%.4f macro_mean=%.4f fused_mean=%.4f",
        fused.size, float(quant_arr.mean()), float(sentiment_arr.mean()),
        float(macro_arr.mean()), float(fused.mean()),
    )
    return fused

