"""Tests unitaires — compute_conviction V2."""
from __future__ import annotations

import pytest

from risk_management.conviction import compute_conviction


@pytest.mark.unit
def test_with_prediction() -> None:
    result = compute_conviction(predicted_proba=0.7)
    assert result == pytest.approx(0.7)


@pytest.mark.unit
def test_compute_conviction_rejects_missing_prediction() -> None:
    with pytest.raises(ValueError, match="probabilité ML long"):
        compute_conviction(score_used=0.8, predicted_proba=None)

