"""Tests unitaires — compute_conviction V2."""
from __future__ import annotations

import pytest

from risk_management.conviction import compute_conviction


@pytest.mark.unit
def test_with_prediction() -> None:
    result = compute_conviction(score_used=0.8, predicted_proba=0.7, score_weight=0.4, prediction_weight=0.6)
    assert abs(result - (0.4 * 0.8 + 0.6 * 0.7)) < 1e-9


@pytest.mark.unit
def test_without_prediction_uses_score_only() -> None:
    result = compute_conviction(score_used=0.8, predicted_proba=None, score_weight=0.4, prediction_weight=0.6)
    assert result == 0.8

