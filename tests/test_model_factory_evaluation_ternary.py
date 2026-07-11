"""Tests pour les métriques multiclasses — Sprint Maître 1."""

from __future__ import annotations

import numpy as np
import pytest

from modelFactory.evaluation import (
    check_model_collapse,
    compute_directional_oos_metrics,
    compute_multiclass_metrics,
    multiclass_auc_one_vs_rest,
    multiclass_balanced_accuracy,
    multiclass_brier_score,
    multiclass_log_loss,
    _validate_proba_array,
)


# ── Validation des probabilités ─────────────────────────────────────────────

def test_validate_proba_array_ok() -> None:
    proba = np.array([[0.1, 0.3, 0.6], [0.2, 0.3, 0.5]])
    assert _validate_proba_array(proba) is None


def test_validate_proba_array_rejects_non_finite() -> None:
    proba = np.array([[0.1, np.nan, 0.6]])
    assert _validate_proba_array(proba) == "non_finite_values"


def test_validate_proba_array_rejects_out_of_bounds() -> None:
    proba = np.array([[0.1, -0.1, 1.0]])
    assert _validate_proba_array(proba) == "out_of_bounds"


def test_validate_proba_array_rejects_sum_not_one() -> None:
    proba = np.array([[0.5, 0.5, 0.5]])
    assert "sum_not_one" in (_validate_proba_array(proba) or "")


# ── AUC one-vs-rest ─────────────────────────────────────────────────────────

def test_auc_one_vs_rest_perfect() -> None:
    y_true = np.array([0, 0, 2, 2, 1, 1])
    y_proba = np.array([
        [0.9, 0.05, 0.05],
        [0.85, 0.1, 0.05],
        [0.05, 0.05, 0.9],
        [0.1, 0.05, 0.85],
        [0.05, 0.9, 0.05],
        [0.1, 0.85, 0.05],
    ])
    result = multiclass_auc_one_vs_rest(y_true, y_proba)
    assert result["auc_class_0"] == 1.0
    assert result["auc_class_2"] == 1.0
    assert result["auc_macro"] is not None and result["auc_macro"] >= 0.99


def test_auc_one_vs_rest_bounded() -> None:
    y_true = np.array([0, 1, 2, 0, 1, 2])
    y_proba = np.array([
        [0.5, 0.3, 0.2],
        [0.2, 0.5, 0.3],
        [0.3, 0.3, 0.4],
        [0.6, 0.2, 0.2],
        [0.3, 0.4, 0.3],
        [0.2, 0.3, 0.5],
    ])
    result = multiclass_auc_one_vs_rest(y_true, y_proba)
    for key, val in result.items():
        if key.startswith("auc_class_") and val is not None:
            assert 0.0 <= val <= 1.0, f"{key}={val} hors bornes"
    if result["auc_macro"] is not None:
        assert 0.0 <= result["auc_macro"] <= 1.0


# ── Brier multiclasse ───────────────────────────────────────────────────────

def test_brier_multiclass_perfect() -> None:
    y_true = np.array([0, 1, 2])
    y_proba = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    brier = multiclass_brier_score(y_true, y_proba)
    assert brier is not None and brier < 0.01


def test_brier_multiclass_worst() -> None:
    y_true = np.array([0, 0, 0])
    y_proba = np.array([[0, 0, 1], [0, 0, 1], [0, 0, 1]])
    brier = multiclass_brier_score(y_true, y_proba)
    assert brier is not None and brier > 0.5


# ── Log-loss ────────────────────────────────────────────────────────────────

def test_log_loss_perfect() -> None:
    y_true = np.array([0, 1, 2])
    y_proba = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    ll = multiclass_log_loss(y_true, y_proba)
    assert ll is not None and ll < 1e-10


def test_log_loss_worst() -> None:
    y_true = np.array([0, 0, 0])
    y_proba = np.array([[0, 0, 1], [0, 0, 1], [0, 0, 1]])
    ll = multiclass_log_loss(y_true, y_proba)
    assert ll is not None and ll > 10  # log(eps) ≈ -34, mais après clipping c'est très grand


# ── Balanced accuracy ───────────────────────────────────────────────────────

def test_balanced_accuracy_perfect() -> None:
    y_true = np.array([0, 1, 2, 0, 1, 2])
    y_pred = np.array([0, 1, 2, 0, 1, 2])
    ba = multiclass_balanced_accuracy(y_true, y_pred)
    assert ba == 1.0


def test_balanced_accuracy_zero() -> None:
    y_true = np.array([0, 1, 2, 0, 1, 2])
    y_pred = np.array([2, 2, 2, 2, 2, 2])
    ba = multiclass_balanced_accuracy(y_true, y_pred)
    assert ba is not None and ba < 0.5


# ── compute_multiclass_metrics ──────────────────────────────────────────────

def test_compute_multiclass_metrics_complete() -> None:
    y_true = np.array([0, 0, 1, 1, 2, 2])
    y_proba = np.array([
        [0.8, 0.1, 0.1],
        [0.7, 0.2, 0.1],
        [0.1, 0.8, 0.1],
        [0.2, 0.7, 0.1],
        [0.1, 0.1, 0.8],
        [0.1, 0.2, 0.7],
    ])
    result = compute_multiclass_metrics(y_true, y_proba)
    assert result["proba_valid"] is True
    assert "brier_multiclass" in result
    assert "log_loss" in result
    assert "balanced_accuracy" in result
    assert result["f1_macro"] is not None
    assert result["f1_weighted"] is not None
    assert result["accuracy"] >= 0.5
    assert 0.0 <= result["action_rate"] <= 1.0
    # Per-class metrics
    for name in ("short", "flat", "long"):
        assert f"precision_{name}" in result
        assert f"recall_{name}" in result
        assert f"f1_{name}" in result


def test_compute_multiclass_metrics_rejects_invalid() -> None:
    y_true = np.array([0, 1, 2])
    y_proba = np.array([[0.5, np.nan, 0.5], [0.3, 0.3, 0.4], [0.2, 0.3, 0.5]])
    result = compute_multiclass_metrics(y_true, y_proba)
    assert result["proba_valid"] is False
    assert "proba_error" in result


def test_directional_oos_metrics_use_policy_and_signed_returns() -> None:
    probabilities = np.array([
        [0.70, 0.20, 0.10],  # selected short: -5% long return -> +5% short return
        [0.10, 0.20, 0.70],  # selected long: +4%
        [0.50, 0.43, 0.07],  # selected short: +2% long return -> -2% short return
        [0.40, 0.35, 0.25],  # flat by threshold: ignored
    ])
    future_returns = np.array([-0.05, 0.04, 0.02, 0.10])

    metrics = compute_directional_oos_metrics(probabilities, future_returns)

    assert metrics["long"] == {
        "hit_rate": 1.0,
        "payoff": 0.0,
        "tail_loss": None,
        "trade_count": 1,
    }
    assert metrics["short"]["trade_count"] == 2
    assert metrics["short"]["hit_rate"] == 0.5
    assert metrics["short"]["payoff"] == pytest.approx(2.5)
    assert metrics["short"]["tail_loss"] == pytest.approx(0.02)


# ── Collapse detection ──────────────────────────────────────────────────────

def test_check_collapse_ok() -> None:
    y_proba = np.array([
        [0.5, 0.3, 0.2],
        [0.3, 0.4, 0.3],
        [0.2, 0.3, 0.5],
        [0.4, 0.3, 0.3],
        [0.1, 0.7, 0.2],
        [0.3, 0.2, 0.5],
    ] * 10)  # 60 samples
    collapsed, reason = check_model_collapse(y_proba)
    assert collapsed is False
    assert reason is None


def test_check_collapse_single_class_dominant() -> None:
    # 99% flat, 1% autre → collapse
    y_proba = np.array([[0.1, 0.8, 0.1]] * 99 + [[0.4, 0.3, 0.3]] * 1)
    collapsed, reason = check_model_collapse(y_proba)
    assert collapsed is True
    assert reason is not None
    # Soit "single_class_dominant" soit "class_X_near_absent" — les deux sont valides
    assert "dominant" in reason or "near_absent" in reason or "action_rate" in reason


def test_check_collapse_action_rate_too_low() -> None:
    # 99% flat
    y_proba = np.array([[0.3, 0.4, 0.3]] * 99 + [[0.8, 0.1, 0.1]])
    collapsed, reason = check_model_collapse(y_proba)
    assert collapsed is True


def test_check_collapse_insufficient_samples() -> None:
    y_proba = np.array([[0.5, 0.3, 0.2]])
    collapsed, reason = check_model_collapse(y_proba)
    assert collapsed is True
    assert "insufficient" in (reason or "")


def test_check_collapse_non_finite() -> None:
    y_proba = np.array([[np.nan, 0.5, 0.5]] * 20)
    collapsed, reason = check_model_collapse(y_proba)
    assert collapsed is True
    assert "non_finite" in (reason or "")
