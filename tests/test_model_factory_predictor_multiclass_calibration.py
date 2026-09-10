from __future__ import annotations

import numpy as np

from modelFactory.calibration import VectorScaler
from modelFactory.predictor import (
    _apply_optional_calibration,
    _apply_optional_multiclass_calibration,
)
from modelFactory.runtime_status import reset_runtime_status, snapshot_runtime_status


def test_vector_calibrator_never_uses_binary_margin_path() -> None:
    calibrator = VectorScaler(
        temperature=1.2,
        biases=np.array([-0.1, 0.0, 0.1]),
        fitted=True,
    )

    proba, method = _apply_optional_calibration(
        symbol="KBH",
        selected_model="lightgbm",
        calibrator=calibrator,
        margin=np.array([0.42]),
        calibrator_path=None,
        raw_proba=0.60,
    )

    assert proba == 0.60
    assert method == "none"


def test_vector_calibrator_applies_to_all_ternary_probabilities() -> None:
    reset_runtime_status()
    calibrator = VectorScaler(
        temperature=1.2,
        biases=np.array([-0.3, 0.0, 0.3]),
        fitted=True,
    )
    raw = np.array([[0.55, 0.30, 0.15]], dtype=np.float64)

    calibrated, method = _apply_optional_multiclass_calibration(
        symbol="KBH",
        selected_model="lightgbm",
        calibrator=calibrator,
        raw_probabilities=raw,
        calibrator_path=None,
    )

    assert method == "vector"
    assert calibrated.shape == (1, 3)
    np.testing.assert_allclose(calibrated.sum(axis=1), 1.0, atol=1e-6)
    assert not np.allclose(calibrated, raw)
    assert snapshot_runtime_status().get("prediction_calibration_fallback_count", 0) == 0


def test_invalid_multiclass_calibrator_falls_back_to_raw_probabilities() -> None:
    reset_runtime_status()

    class BrokenVector:
        method = "vector"
        fitted = True

        def predict(self, values):
            return np.array([0.1, 0.2, 0.7])  # forme invalide: [3] au lieu de [1, 3]

    raw = np.array([[0.2, 0.3, 0.5]], dtype=np.float64)
    calibrated, method = _apply_optional_multiclass_calibration(
        symbol="KBH",
        selected_model="lightgbm",
        calibrator=BrokenVector(),
        raw_probabilities=raw,
        calibrator_path=None,
    )

    assert method == "none"
    np.testing.assert_allclose(calibrated, raw)
    status = snapshot_runtime_status()
    assert status["prediction_calibration_fallback_count"] == 1
    assert status["last_calibration_fallback_reason"] == (
        "multiclass_calibrator_incompatible:lightgbm"
    )
