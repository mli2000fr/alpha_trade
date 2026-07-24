"""Tests unitaires pour la calibration VectorScaler (Sprint 2026-07-24).

Vérifie que :
- VectorScaler s'initialise et se fit correctement
- La calibration corrige un biais de classe simulé
- Le state_dict / from_state_dict fonctionnent (persistance)
- La rétrocompatibilité avec TemperatureScaler est préservée
"""
from __future__ import annotations

import numpy as np
import pytest

from modelFactory.calibration import (
    TemperatureScaler,
    VectorScaler,
    calibrator_from_state_dict,
)


class TestVectorScaler:
    """Tests unitaires du VectorScaler."""

    def test_init_defaults(self) -> None:
        """Les défauts sont corrects."""
        vs = VectorScaler()
        assert vs.temperature == 1.0
        assert vs.biases is None
        assert not vs.fitted
        assert vs.method == "vector"

    def test_fit_preserves_order_on_unbiased_data(self) -> None:
        """Sur des données sans biais, les biais restent proches de 0 (pas de correction)."""
        rng = np.random.RandomState(42)
        logits = rng.randn(200, 3).astype(np.float32) * 2.0
        # Labels selon la classe dominante (pas de biais)
        labels = np.argmax(logits, axis=1).astype(np.int64)

        vs = VectorScaler(max_iter=50).fit(logits, labels)
        assert vs.fitted
        # La température peut varier (optimisation de confiance), mais les biais
        # doivent être proches de 0 car il n'y a pas de biais de classe.
        assert vs.biases is not None
        assert np.allclose(vs.biases, 0.0, atol=0.5)

    def test_fit_corrects_class_bias(self) -> None:
        """Le VectorScaler corrige un biais simulé vers la classe 0 (short)."""
        rng = np.random.RandomState(123)
        n = 300
        # Logits avec biais constant vers classe 0
        logits = np.zeros((n, 3), dtype=np.float32)
        logits[:, 0] = 2.0  # short favorisé
        logits[:, 1] = rng.randn(n) * 0.5
        logits[:, 2] = rng.randn(n) * 0.5
        # Labels réels : équilibrés entre les 3 classes
        labels = np.array([0] * 100 + [1] * 100 + [2] * 100, dtype=np.int64)
        rng.shuffle(labels)

        vs = VectorScaler(max_iter=100).fit(logits, labels)
        assert vs.fitted
        assert vs.biases is not None
        # Le biais de la classe 0 doit être négatif (correction de la sur-prédiction)
        assert vs.biases[0] < vs.biases[1]
        assert vs.biases[0] < vs.biases[2]

    def test_predict_proba_sums_to_one(self) -> None:
        """Les probabilités calibrées somment à 1."""
        rng = np.random.RandomState(99)
        logits = rng.randn(50, 3).astype(np.float32)
        labels = np.argmax(logits, axis=1).astype(np.int64)

        vs = VectorScaler(max_iter=50).fit(logits, labels)
        proba = vs.predict_proba(logits)

        assert proba.shape == (50, 3)
        assert np.all(proba >= 0)
        assert np.all(proba <= 1)
        np.testing.assert_allclose(proba.sum(axis=1), 1.0, atol=1e-6)

    def test_predict_proba_on_unfitted_raises_no_error(self) -> None:
        """predict_proba sur un VectorScaler non fitté retourne le softmax brut."""
        vs = VectorScaler()
        logits = np.array([[1.0, 0.0, -1.0]], dtype=np.float32)
        proba = vs.predict_proba(logits)
        assert proba.shape == (1, 3)
        np.testing.assert_allclose(proba.sum(), 1.0, atol=1e-6)

    def test_state_dict_roundtrip(self) -> None:
        """Le state_dict permet de sérialiser/désérialiser."""
        rng = np.random.RandomState(42)
        logits = rng.randn(100, 3).astype(np.float32)
        labels = np.argmax(logits, axis=1).astype(np.int64)

        vs = VectorScaler(max_iter=50).fit(logits, labels)
        state = vs.state_dict()

        assert state["method"] == "vector"
        assert "temperature" in state
        assert "biases" in state
        assert state["fitted"] is True

        vs2 = VectorScaler.from_state_dict(state)
        assert vs2.temperature == vs.temperature
        assert vs2.fitted == vs.fitted
        np.testing.assert_allclose(vs2.biases, vs.biases)

        # Les prédictions doivent être identiques
        np.testing.assert_allclose(
            vs.predict_proba(logits),
            vs2.predict_proba(logits),
            atol=1e-6,
        )

    def test_calibrator_from_state_dict_supports_vector(self) -> None:
        """calibrator_from_state_dict reconnaît la méthode 'vector'."""
        state = {"method": "vector", "temperature": 1.5, "biases": [0.1, -0.2, 0.1], "fitted": True, "max_iter": 100}
        cal = calibrator_from_state_dict(state)
        assert isinstance(cal, VectorScaler)
        assert cal.temperature == 1.5
        assert cal.fitted is True

    def test_fit_single_class_returns_unfitted(self) -> None:
        """Avec une seule classe dans les labels, le fit ne fait rien."""
        logits = np.random.randn(50, 3).astype(np.float32)
        labels = np.zeros(50, dtype=np.int64)  # une seule classe
        vs = VectorScaler().fit(logits, labels)
        assert not vs.fitted

    def test_temperature_scaler_still_works(self) -> None:
        """Régression : TemperatureScaler fonctionne toujours."""
        logits = np.random.randn(80, 3).astype(np.float32)
        labels = np.argmax(logits, axis=1).astype(np.int64)
        ts = TemperatureScaler(max_iter=50).fit(logits, labels)
        assert ts.fitted
        proba = ts.predict_proba(logits)
        np.testing.assert_allclose(proba.sum(axis=1), 1.0, atol=1e-6)
