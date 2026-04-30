"""Tests pour ``core.conviction`` — fusion ternaire (Phase 4.1.a)."""
from __future__ import annotations

import numpy as np
import pytest

from core.conviction import (
    SentimentFusionWeights,
    fuse_sentiment,
)


def _legacy_formula(
    *,
    quant_score: float,
    sentiment_signal_norm: float,
    macro_signal_norm: float,
    quant_weight: float,
    sentiment_weight: float,
    macro_weight: float,
    signal_active: bool,
) -> float:
    """Formule historique copiée depuis ``signal_aggregator.merge`` (l. 926-944)."""
    sent = sentiment_weight * (sentiment_signal_norm if signal_active else 0.5)
    macro = macro_weight * macro_signal_norm
    quant = quant_weight * quant_score
    return float(np.clip(quant + sent + macro, 0.0, 1.0))


@pytest.mark.parametrize(
    "quant, sent, macro, active",
    [
        (0.50, 0.50, 0.50, True),
        (0.80, 0.20, 0.30, True),
        (0.10, 0.90, 0.10, False),
        (0.95, 0.95, 0.95, True),
        (0.00, 0.00, 1.00, False),
    ],
)
def test_fuse_sentiment_matches_legacy_formula(
    quant: float, sent: float, macro: float, active: bool
) -> None:
    weights = SentimentFusionWeights()
    expected = _legacy_formula(
        quant_score=quant,
        sentiment_signal_norm=sent,
        macro_signal_norm=macro,
        quant_weight=weights.quant_weight,
        sentiment_weight=weights.sentiment_weight,
        macro_weight=weights.macro_weight,
        signal_active=active,
    )
    result = fuse_sentiment(
        quant_score=quant,
        sentiment_signal_norm=sent,
        macro_signal_norm=macro,
        weights=weights,
        signal_active=active,
    )
    assert isinstance(result, float)
    assert result == pytest.approx(expected, abs=1e-9)


def test_fuse_sentiment_broadcasts_arrays() -> None:
    quant = np.array([0.1, 0.5, 0.9])
    sent = np.array([0.5, 0.5, 0.5])
    macro = np.array([0.5, 0.5, 0.5])
    active = np.array([True, False, True])
    out = fuse_sentiment(
        quant_score=quant,
        sentiment_signal_norm=sent,
        macro_signal_norm=macro,
        signal_active=active,
    )
    assert isinstance(out, np.ndarray)
    assert out.shape == (3,)
    assert np.all((out >= 0.0) & (out <= 1.0))


def test_fuse_sentiment_clips_to_unit_interval() -> None:
    # quant=2 hors plage : la fusion doit clip à 1.0
    out = fuse_sentiment(
        quant_score=2.0,
        sentiment_signal_norm=1.0,
        macro_signal_norm=1.0,
        signal_active=True,
    )
    assert out == 1.0


def test_sentiment_fusion_weights_validates_sum() -> None:
    with pytest.raises(ValueError, match="somme des poids"):
        SentimentFusionWeights(quant_weight=0.5, sentiment_weight=0.2, macro_weight=0.2)


def test_sentiment_fusion_weights_rejects_negatives() -> None:
    with pytest.raises(ValueError, match="poids négatifs"):
        SentimentFusionWeights(quant_weight=1.1, sentiment_weight=-0.05, macro_weight=-0.05)


def test_sentiment_fusion_weights_defaults() -> None:
    w = SentimentFusionWeights()
    assert w.quant_weight == 0.75
    assert w.sentiment_weight == 0.15
    assert w.macro_weight == 0.10

