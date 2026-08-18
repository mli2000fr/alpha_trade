"""Tests unitaires Oracle S5 — combinaison + calibration (fonctions pures)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modelFactory.oracle.combine import (
    calibrate_p_top,
    combine_scores,
    isotonic_regression,
)


class TestCombineScores:
    def test_baseline_is_rank(self):
        r = combine_scores(np.array([0.9, 0.1]), np.array([0.5, 0.5]), method="baseline")
        np.testing.assert_allclose(r, [0.9, 0.1])

    def test_mult(self):
        r = combine_scores(np.array([0.9, 0.1]), np.array([0.5, 0.2]), method="mult")
        np.testing.assert_allclose(r, [0.45, 0.02])

    def test_weighted_alpha_one_is_rank(self):
        r = combine_scores(np.array([0.9, 0.1]), np.array([0.5, 0.2]), method="weighted", alpha=1.0)
        np.testing.assert_allclose(r, [0.9, 0.1])

    def test_weighted_alpha_zero_is_ptop(self):
        r = combine_scores(np.array([0.9, 0.1]), np.array([0.5, 0.2]), method="weighted", alpha=0.0)
        np.testing.assert_allclose(r, [0.5, 0.2])

    def test_unknown_method_raises(self):
        with pytest.raises(ValueError):
            combine_scores(np.array([0.9]), np.array([0.5]), method="nope")


class TestIsotonicRegression:
    def test_monotone_input_unchanged(self):
        x = np.array([0.1, 0.3, 0.5, 0.8])
        y = np.array([0.0, 0.2, 0.6, 1.0])
        xs, fitted = isotonic_regression(x, y)
        np.testing.assert_allclose(fitted, y)

    def test_violations_are_pooled(self):
        # y décroissant → isotonique doit aplanir en moyenne constante
        x = np.array([0.1, 0.2, 0.3])
        y = np.array([1.0, 0.0, 0.5])
        xs, fitted = isotonic_regression(x, y)
        # moyenne globale = 0.5
        np.testing.assert_allclose(fitted, [0.5, 0.5, 0.5])

    def test_output_is_non_decreasing(self):
        rng = np.random.default_rng(0)
        x = rng.uniform(0, 1, 50)
        y = rng.uniform(0, 1, 50)
        xs, fitted = isotonic_regression(x, y)
        assert (np.diff(fitted) >= -1e-12).all()


class TestCalibratePTop:
    def test_identity(self):
        df = pd.DataFrame({"date": pd.to_datetime(["2025-01-02"] * 3), "proba_top": [0.2, 0.5, 0.9]})
        out = calibrate_p_top(df, method="identity")
        np.testing.assert_allclose(out.to_numpy(), [0.2, 0.5, 0.9])

    def test_rank_is_per_date_percentile(self):
        df = pd.DataFrame({
            "date": pd.to_datetime(["2025-01-02"] * 3 + ["2025-01-03"] * 3),
            "proba_top": [0.1, 0.5, 0.9, 0.1, 0.5, 0.9],
        })
        out = calibrate_p_top(df, method="rank")
        np.testing.assert_allclose(out.to_numpy(), [1/3, 2/3, 1.0, 1/3, 2/3, 1.0])

    def test_isotonic_requires_fit(self):
        df = pd.DataFrame({"date": pd.to_datetime(["2025-01-02"]), "proba_top": [0.5]})
        with pytest.raises(ValueError):
            calibrate_p_top(df, method="isotonic")
