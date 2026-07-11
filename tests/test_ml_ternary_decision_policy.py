"""Tests pour la politique de décision ternaire (Sprint Maître 0)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from core.ternary_decision_policy import (
    DEFAULT_TERNARY_POLICY,
    TernaryDecision,
    TernaryDecisionPolicy,
    decide_from_array,
    decide_ternary_side,
)


# ── Construction de la policy ────────────────────────────────────────────────

def test_policy_default_construction() -> None:
    policy = TernaryDecisionPolicy()
    assert policy.threshold_long == 0.45
    assert policy.threshold_short == 0.45
    assert policy.top2_margin == 0.05
    assert policy.version == 1


def test_policy_rejects_invalid_thresholds() -> None:
    with pytest.raises(ValueError, match="threshold_long"):
        TernaryDecisionPolicy(threshold_long=0.0)
    with pytest.raises(ValueError, match="threshold_long"):
        TernaryDecisionPolicy(threshold_long=1.0)
    with pytest.raises(ValueError, match="threshold_short"):
        TernaryDecisionPolicy(threshold_short=-0.1)
    with pytest.raises(ValueError, match="threshold_short"):
        TernaryDecisionPolicy(threshold_short=1.5)
    with pytest.raises(ValueError, match="top2_margin"):
        TernaryDecisionPolicy(top2_margin=-0.01)
    with pytest.raises(ValueError, match="top2_margin"):
        TernaryDecisionPolicy(top2_margin=1.0)
    with pytest.raises(ValueError, match="version"):
        TernaryDecisionPolicy(version=0)


def test_policy_roundtrip_dict() -> None:
    policy = TernaryDecisionPolicy(
        threshold_long=0.40,
        threshold_short=0.40,
        top2_margin=0.08,
        version=3,
    )
    d = policy.to_dict()
    restored = TernaryDecisionPolicy.from_dict(d)
    assert restored.threshold_long == 0.40
    assert restored.threshold_short == 0.40
    assert restored.top2_margin == 0.08
    assert restored.version == 3


def test_policy_is_immutable() -> None:
    policy = TernaryDecisionPolicy()
    with pytest.raises(Exception):  # frozen dataclass
        policy.threshold_long = 0.5  # type: ignore[misc]


# ── Décision : cas nominaux ──────────────────────────────────────────────────

def test_clear_long_signal() -> None:
    decision = decide_ternary_side(0.10, 0.20, 0.70)
    assert decision.side == "long"
    assert decision.p_side == 0.70
    assert decision.reason == "p_long_dominant"


def test_clear_short_signal() -> None:
    decision = decide_ternary_side(0.65, 0.25, 0.10)
    assert decision.side == "short"
    assert decision.p_side == 0.65
    assert decision.reason == "p_short_dominant"


def test_flat_when_below_threshold() -> None:
    # p_long est la meilleure mais sous le seuil
    decision = decide_ternary_side(0.30, 0.40, 0.30)
    assert decision.side == "flat"
    assert "below_threshold" in decision.reason or "flat" in decision.reason


def test_flat_when_margin_too_small() -> None:
    policy = TernaryDecisionPolicy(threshold_long=0.45, threshold_short=0.45, top2_margin=0.10)
    # p_long > threshold mais margin < top2_margin
    decision = decide_ternary_side(0.10, 0.40, 0.50, policy=policy)
    assert decision.side == "flat"
    assert decision.reason == "flat_by_margin"


def test_long_with_custom_threshold() -> None:
    policy = TernaryDecisionPolicy(threshold_long=0.35, threshold_short=0.45, top2_margin=0.05)
    # p_long=0.50 est la meilleure, >= threshold, margin vs 2e (0.30) >= 0.05
    decision = decide_ternary_side(0.10, 0.30, 0.60, policy=policy)
    assert decision.side == "long"
    assert decision.reason == "p_long_dominant"


def test_short_with_custom_threshold() -> None:
    policy = TernaryDecisionPolicy(threshold_long=0.45, threshold_short=0.35, top2_margin=0.05)
    # p_short=0.55 est la meilleure, >= threshold, margin vs 2e (0.30) >= 0.05
    decision = decide_ternary_side(0.55, 0.30, 0.15, policy=policy)
    assert decision.side == "short"
    assert decision.reason == "p_short_dominant"


def test_flat_dominant() -> None:
    decision = decide_ternary_side(0.10, 0.80, 0.10)
    assert decision.side == "flat"
    # flat dominant a le plus de proba
    assert decision.reason in ("flat_dominant", "flat_default")


# ── Égalités et tie-break ────────────────────────────────────────────────────

def test_tiebreak_long_beats_short() -> None:
    """En cas d'égalité long==short au-dessus du threshold, avec top2_margin=0, long gagne."""
    policy = TernaryDecisionPolicy(threshold_long=0.40, threshold_short=0.40, top2_margin=0.0)
    decision = decide_ternary_side(0.40, 0.20, 0.40, policy=policy)
    # margin = 0, top2_margin = 0 → margin OK. Tiebreak: long > short.
    assert decision.side == "long"
    assert decision.reason == "p_long_dominant"


def test_tiebreak_long_beats_short_when_margin_satisfied() -> None:
    """Même avec tiebreak, si p_long >= threshold et top2_margin=0, long gagne."""
    policy = TernaryDecisionPolicy(threshold_long=0.40, threshold_short=0.40, top2_margin=0.0)
    decision = decide_ternary_side(0.40, 0.20, 0.40, policy=policy)
    # top2_margin=0, long==short=0.40>=threshold → tiebreak long
    assert decision.side == "long"
    assert decision.reason == "p_long_dominant"


def test_three_way_tie() -> None:
    """Égalité à trois : flat par défaut car la meilleure est flat après tiebreak? Non, long > short > flat."""
    policy = TernaryDecisionPolicy(threshold_long=0.3, threshold_short=0.3, top2_margin=0.0)
    decision = decide_ternary_side(1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0, policy=policy)
    # Tiebreak: long > short > flat, best=long, second=short, margin=0
    assert decision.side == "long"


# ── Probabilités invalides ───────────────────────────────────────────────────

def test_rejects_nan() -> None:
    with pytest.raises(ValueError, match="non_finite"):
        decide_ternary_side(float("nan"), 0.5, 0.5)


def test_rejects_inf() -> None:
    with pytest.raises(ValueError, match="non_finite"):
        decide_ternary_side(0.0, float("inf"), 0.0)


def test_rejects_out_of_bounds() -> None:
    with pytest.raises(ValueError, match="out_of_bounds"):
        decide_ternary_side(1.5, 0.0, 0.0)
    with pytest.raises(ValueError, match="out_of_bounds"):
        decide_ternary_side(-0.1, 0.6, 0.5)


def test_rejects_sum_not_one() -> None:
    with pytest.raises(ValueError, match="sum_not_one"):
        decide_ternary_side(0.5, 0.5, 0.5)


def test_accepts_sum_close_to_one() -> None:
    """Une somme proche de 1 dans la tolérance est acceptée."""
    decision = decide_ternary_side(0.333, 0.333, 0.334)
    assert decision.side in {"long", "flat", "short"}


# ── Décision déterministe ────────────────────────────────────────────────────

def test_same_probs_same_side() -> None:
    """Mêmes probabilités => même side, toujours."""
    for _ in range(10):
        d1 = decide_ternary_side(0.15, 0.25, 0.60)
        d2 = decide_ternary_side(0.15, 0.25, 0.60)
        assert d1.side == d2.side == "long"
        assert d1.p_side == d2.p_side
        assert d1.reason == d2.reason


# ── decide_from_array ────────────────────────────────────────────────────────

def test_decide_from_array_3() -> None:
    arr = np.array([0.10, 0.20, 0.70])
    decision = decide_from_array(arr)
    assert decision.side == "long"


def test_decide_from_array_1x3() -> None:
    arr = np.array([[0.65, 0.25, 0.10]])
    decision = decide_from_array(arr)
    assert decision.side == "short"


def test_decide_from_array_rejects_wrong_shape() -> None:
    with pytest.raises(ValueError, match="3 éléments"):
        decide_from_array(np.array([0.5, 0.5]))


# ── TernaryDecision immutable ─────────────────────────────────────────────────

def test_ternary_decision_rejects_invalid_side() -> None:
    with pytest.raises(ValueError, match="side"):
        TernaryDecision(side="buy", p_side=0.5, reason="test")  # type: ignore[arg-type]


def test_ternary_decision_rejects_invalid_p_side() -> None:
    with pytest.raises(ValueError, match="p_side"):
        TernaryDecision(side="long", p_side=1.5, reason="test")


# ── Default policy ───────────────────────────────────────────────────────────

def test_default_policy_exists() -> None:
    assert DEFAULT_TERNARY_POLICY.version == 1
    assert DEFAULT_TERNARY_POLICY.threshold_long == 0.45
