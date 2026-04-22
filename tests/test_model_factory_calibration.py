from __future__ import annotations

import numpy as np

from modelFactory.calibration import PlattCalibrator, margin_from_logits


def test_margin_from_logits_returns_positive_minus_negative() -> None:
    logits = np.array([[0.0, 1.5], [2.0, -1.0]], dtype=np.float32)

    margins = margin_from_logits(logits)

    np.testing.assert_allclose(margins, np.array([1.5, -3.0]))


def test_platt_calibrator_fits_and_predicts_probabilities() -> None:
    margins = np.array([-2.0, -1.0, 1.0, 2.0], dtype=np.float64)
    labels = np.array([0, 0, 1, 1], dtype=np.int64)

    calibrator = PlattCalibrator(max_iter=50).fit(margins, labels)
    proba = calibrator.predict_proba(margins)

    assert calibrator.fitted is True
    assert np.all(proba >= 0.0)
    assert np.all(proba <= 1.0)
    assert proba[0] < proba[-1]
