"""Tests pour la calibration multiclasse — Sprint Maître 1."""

from __future__ import annotations

import numpy as np
import pytest

from modelFactory.calibration import (
    PlattCalibrator,
    TemperatureScaler,
    VectorScaler,
    calibrator_from_state_dict,
)
from modelFactory.config import CalibrationConfig, DataConfig, TrainingConfig


def _make_training_cfg(*, target_mode: str = "binary", calibration_method: str = "platt") -> TrainingConfig:
    data_kwargs = {}
    if target_mode == "ternary":
        data_kwargs = {"target_up_threshold": 0.03, "target_down_threshold": -0.03}
    return TrainingConfig(
        data=DataConfig(target_mode=target_mode, **data_kwargs),
        calibration=CalibrationConfig(method=calibration_method, min_samples=2),
    )


# ── TemperatureScaler ───────────────────────────────────────────────────────

def test_temperature_scaler_fit_and_predict() -> None:
    scaler = TemperatureScaler(temperature=2.0)
    logits = np.array([[0.5, 1.0, -0.5], [1.0, 2.0, 0.0], [-0.5, 0.5, 3.0]], dtype=np.float32)
    labels = np.array([1, 0, 2], dtype=np.int64)
    scaler.fit(logits, labels)
    assert scaler.fitted is True
    proba = scaler.predict(logits)
    assert proba.shape == (3, 3)
    assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-5)
    assert (proba >= 0).all() and (proba <= 1).all()


def test_temperature_scaler_softens() -> None:
    """Avec T > 1, l'entropie devrait augmenter (probas plus étalées)."""
    scaler = TemperatureScaler(temperature=5.0)
    logits = np.array([[10.0, 0.0, 0.0]], dtype=np.float32)
    labels = np.array([0], dtype=np.int64)
    scaler.fit(logits, labels)
    proba = scaler.predict(logits)
    # Avec T=5, le softmax devrait être moins extrême que T=1
    proba_t1 = TemperatureScaler(temperature=1.0).predict(logits)
    entropy_t5 = -np.sum(proba * np.log(proba + 1e-15))
    entropy_t1 = -np.sum(proba_t1 * np.log(proba_t1 + 1e-15))
    assert entropy_t5 > entropy_t1  # T plus grand = plus d'entropie


def test_temperature_scaler_roundtrip_state_dict() -> None:
    scaler = TemperatureScaler(temperature=2.5, fitted=True, max_iter=50)
    state = scaler.state_dict()
    restored = TemperatureScaler.from_state_dict(state)
    assert restored.temperature == 2.5
    assert restored.fitted is True
    assert restored.max_iter == 50
    assert restored.method == "temperature"


def test_temperature_scaler_temperature_floor() -> None:
    """Temperature ne doit jamais être <= 0."""
    scaler = TemperatureScaler(temperature=0.001)
    # Même avec une très petite température, predict doit fonctionner
    logits = np.array([[0.5, 1.0, -0.5]], dtype=np.float32)
    proba = scaler.predict(logits)
    assert proba.shape == (1, 3)
    assert np.allclose(proba.sum(), 1.0)


def test_calibrator_from_state_dict_routes_temperature() -> None:
    state = {"method": "temperature", "temperature": 1.5, "fitted": True, "max_iter": 100}
    cal = calibrator_from_state_dict(state)
    assert isinstance(cal, TemperatureScaler)
    assert cal.temperature == 1.5


def test_calibrator_from_state_dict_routes_platt() -> None:
    state = {"method": "platt", "slope": 2.0, "intercept": -0.5, "fitted": True, "max_iter": 100}
    cal = calibrator_from_state_dict(state)
    assert isinstance(cal, PlattCalibrator)
    assert cal.slope == 2.0


def test_calibrator_from_state_dict_returns_none_for_unknown() -> None:
    assert calibrator_from_state_dict(None) is None
    assert calibrator_from_state_dict({"method": "isotonic"}) is None


# ── PlattCalibrator (rétrocompatibilité) ────────────────────────────────────

def test_platt_calibrator_unchanged() -> None:
    cal = PlattCalibrator()
    margins = np.array([-2.0, -1.0, 1.0, 2.0], dtype=np.float32)
    targets = np.array([0, 0, 1, 1], dtype=np.float32)
    cal.fit(margins, targets)
    assert cal.fitted is True
    proba = cal.predict_proba(margins)
    assert proba.shape == (4,)
    assert (proba >= 0).all() and (proba <= 1).all()


# ── Tabular calibration routing (Sprint Maître 1) ───────────────────────────

def test_fit_tabular_calibrator_ternary_uses_vector_scaling() -> None:
    from modelFactory.tabular_baseline import fit_tabular_calibrator

    cfg = _make_training_cfg(target_mode="ternary", calibration_method="platt")
    val_proba = np.array([
        [0.6, 0.3, 0.1],
        [0.1, 0.7, 0.2],
        [0.2, 0.2, 0.6],
        [0.5, 0.3, 0.2],
        [0.1, 0.6, 0.3],
        [0.3, 0.2, 0.5],
    ], dtype=np.float64)
    labels = np.array([0, 1, 2, 0, 1, 2], dtype=np.int64)
    cal = fit_tabular_calibrator(val_proba, labels, cfg, target_mode="ternary")
    assert isinstance(cal, VectorScaler)
    assert cal.fitted is True


def test_fit_tabular_calibrator_binary_uses_platt() -> None:
    from modelFactory.tabular_baseline import fit_tabular_calibrator

    cfg = _make_training_cfg(target_mode="binary", calibration_method="platt")
    val_proba = np.array([0.2, 0.6, 0.8, 0.3, 0.7, 0.4], dtype=np.float64)
    labels = np.array([0, 1, 1, 0, 1, 0], dtype=np.int64)
    cal = fit_tabular_calibrator(val_proba, labels, cfg, target_mode="binary")
    assert isinstance(cal, PlattCalibrator)
    assert cal.fitted is True


def test_fit_tabular_calibrator_returns_none_when_disabled() -> None:
    from modelFactory.tabular_baseline import fit_tabular_calibrator

    cfg = _make_training_cfg(target_mode="ternary", calibration_method="none")
    val_proba = np.array([[0.6, 0.3, 0.1]], dtype=np.float64)
    labels = np.array([0], dtype=np.int64)
    cal = fit_tabular_calibrator(val_proba, labels, cfg, target_mode="ternary")
    assert cal is None


def test_apply_tabular_calibration_ternary() -> None:
    from modelFactory.tabular_baseline import apply_tabular_calibration

    cal = TemperatureScaler(temperature=2.0, fitted=True)
    raw_proba = np.array([[0.6, 0.3, 0.1], [0.1, 0.7, 0.2]], dtype=np.float64)
    calibrated = apply_tabular_calibration(raw_proba, cal, target_mode="ternary")
    assert calibrated.shape == (2, 3)
    assert np.allclose(calibrated.sum(axis=1), 1.0, atol=1e-5)


def test_apply_tabular_calibration_binary() -> None:
    from modelFactory.tabular_baseline import apply_tabular_calibration

    cal = PlattCalibrator(slope=1.0, intercept=0.0, fitted=True)
    raw_proba = np.array([0.2, 0.8, 0.5], dtype=np.float64)
    calibrated = apply_tabular_calibration(raw_proba, cal, target_mode="binary")
    assert calibrated.shape == (3,)
    assert (calibrated >= 0).all() and (calibrated <= 1).all()
