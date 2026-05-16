"""Tests Phase 7.2 — calibration empirique poids (audit_global §7.2).

Sprint S3 / A-027 : bornes business [0.05, 0.40] sur poids walk-forward calibrés.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from backtesting.weights_calibration import (
    CalibrationResult,
    calibrate_conviction,
    calibrate_sentiment,
    metric_hit_rate,
    metric_information_coefficient,
)


def _make_synth_data(n: int = 100, *, leak: float = 0.7, seed: int = 7):
    rng = np.random.default_rng(seed)
    quant = rng.uniform(0, 1, n)
    proba = rng.uniform(0, 1, n)
    # Forward return corrélé à la prédiction si leak proche de 1.
    fwd = leak * (proba - 0.5) + (1 - leak) * rng.normal(0, 0.05, n)
    return quant, proba, fwd


def test_metric_ic_perfect_correlation() -> None:
    x = np.linspace(0, 1, 50)
    assert metric_information_coefficient(x, x) == pytest.approx(1.0, abs=1e-6)
    assert metric_information_coefficient(x, -x) == pytest.approx(-1.0, abs=1e-6)


def test_metric_hit_rate_basic() -> None:
    preds = np.array([0.6, 0.7, 0.4, 0.8])
    fwd = np.array([0.01, -0.02, 0.03, 0.05])
    # 3 longs (0.6, 0.7, 0.8), 2 winners → 2/3
    assert metric_hit_rate(preds, fwd) == pytest.approx(2 / 3, abs=1e-6)


def test_calibrate_conviction_returns_valid_result() -> None:
    quant, proba, fwd = _make_synth_data(leak=0.9)
    result = calibrate_conviction(
        quant_scores=quant,
        predicted_proba=proba,
        forward_returns=fwd,
        metric_name="ic",
        grid_step=0.1,
        window=(date(2024, 1, 1), date(2024, 6, 30)),
    )
    assert isinstance(result, CalibrationResult)
    assert result.scope == "conviction"
    assert "score_weight" in result.best_weights and "prediction_weight" in result.best_weights
    # Avec leak=0.9 sur la prédiction, le best devrait privilégier la prédiction.
    assert result.best_weights["prediction_weight"] >= result.best_weights["score_weight"]
    assert len(result.candidates) > 0
    payload = result.to_payload()
    assert payload["schema_version"] == 1
    assert payload["window_start"] == "2024-01-01"


def test_calibrate_conviction_validates_inputs() -> None:
    with pytest.raises(ValueError):
        calibrate_conviction(quant_scores=[0.1], predicted_proba=[0.2, 0.3], forward_returns=[0.0])
    with pytest.raises(ValueError):
        calibrate_conviction(
            quant_scores=[0.1, 0.2],
            predicted_proba=[0.1, 0.2],
            forward_returns=[0.0, 0.0],
            metric_name="unknown",
        )
    with pytest.raises(ValueError):
        # < 5 observations valides
        calibrate_conviction(
            quant_scores=[0.1, 0.2],
            predicted_proba=[0.1, 0.2],
            forward_returns=[0.0, 0.0],
        )


def test_calibrate_sentiment_grid_normalisation() -> None:
    rng = np.random.default_rng(3)
    quant = rng.uniform(0, 1, 80)
    sent = rng.uniform(0, 1, 80)
    macro = rng.uniform(0, 1, 80)
    fwd = 0.3 * (sent - 0.5) + 0.1 * rng.normal(0, 0.05, 80)
    result = calibrate_sentiment(
        quant_scores=quant,
        sentiment_signal=sent,
        macro_signal=macro,
        forward_returns=fwd,
        metric_name="ic",
        grid_step=0.2,
    )
    w = result.best_weights
    s = w["quant_weight"] + w["sentiment_weight"] + w["macro_weight"]
    assert abs(s - 1.0) < 1e-3
    assert all(v >= 0.0 for v in w.values())


# ---------------------------------------------------------------------------
# Sprint S3 / A-027 — bornes business sur les poids walk-forward
# ---------------------------------------------------------------------------

def test_validate_walk_forward_weights_clips_above_max() -> None:
    """Poids au-dessus de WEIGHT_MAX doit être clippé avec warning."""
    from backtesting.walk_forward import WalkForwardWeights, validate_walk_forward_weights, WEIGHT_MAX
    w = WalkForwardWeights(sentiment_weight=0.20, macro_weight=0.10, quant_weight=0.80)
    validated = validate_walk_forward_weights(w, strict=False)
    assert validated.quant_weight == pytest.approx(WEIGHT_MAX)
    assert validated.sentiment_weight == pytest.approx(0.20)


def test_validate_walk_forward_weights_clips_below_min() -> None:
    """Poids en dessous de WEIGHT_MIN doit être clippé."""
    from backtesting.walk_forward import WalkForwardWeights, validate_walk_forward_weights, WEIGHT_MIN
    w = WalkForwardWeights(sentiment_weight=0.01, macro_weight=0.10, quant_weight=0.40)
    validated = validate_walk_forward_weights(w, strict=False)
    assert validated.sentiment_weight == pytest.approx(WEIGHT_MIN)


def test_validate_walk_forward_weights_strict_raises() -> None:
    """strict=True doit lever ValueError sur tout dépassement."""
    from backtesting.walk_forward import WalkForwardWeights, validate_walk_forward_weights
    w = WalkForwardWeights(sentiment_weight=0.20, macro_weight=0.10, quant_weight=0.80)
    with pytest.raises(ValueError, match="hors bornes"):
        validate_walk_forward_weights(w, strict=True)


def test_validate_walk_forward_weights_valid_unchanged() -> None:
    """Poids dans les bornes doivent être retournés inchangés."""
    from backtesting.walk_forward import WalkForwardWeights, validate_walk_forward_weights
    w = WalkForwardWeights(sentiment_weight=0.20, macro_weight=0.10, quant_weight=0.35)
    validated = validate_walk_forward_weights(w, strict=True)
    assert validated is w  # Même objet renvoyé si pas de violation


def test_validate_walk_forward_weights_preserves_metadata() -> None:
    """Les métadonnées calibration_run_id etc. sont conservées après clippage."""
    from backtesting.walk_forward import WalkForwardWeights, validate_walk_forward_weights
    w = WalkForwardWeights(
        sentiment_weight=0.20, macro_weight=0.10, quant_weight=0.80,
        calibration_run_id="wf-99", calibration_source="test"
    )
    validated = validate_walk_forward_weights(w, strict=False)
    assert validated.calibration_run_id == "wf-99"
    assert validated.calibration_source == "test"

