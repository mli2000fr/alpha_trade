"""Tests unitaires — risk_management/abstention.py (AbstentionPolicy).

Sprint Maître 8.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from risk_management.abstention import (
    AbstentionDecision,
    AbstentionPolicy,
    evaluate_abstention_veto,
)
from risk_management.edge import DirectionalEdgeEstimate
from risk_management.selection_contract import MLRankedCandidate


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def candidate_long() -> MLRankedCandidate:
    return MLRankedCandidate(
        symbol="AAPL",
        trade_date=date.today(),
        side="long",
        p_long=0.60,
        p_flat=0.25,
        p_short=0.15,
        p_side=0.60,
        model_run_id="run_001",
        policy_version=1,
    )


@pytest.fixture
def candidate_ambiguous() -> MLRankedCandidate:
    """Candidat avec faible marge top-2 (ambigu)."""
    return MLRankedCandidate(
        symbol="MSFT",
        trade_date=date.today(),
        side="long",
        p_long=0.38,
        p_flat=0.35,
        p_short=0.27,
        p_side=0.38,
        model_run_id="run_002",
        policy_version=1,
    )


@pytest.fixture
def candidate_stale() -> MLRankedCandidate:
    """Candidat avec feature_cutoff vieux."""
    from datetime import timedelta
    old = datetime.now() - timedelta(days=3)
    return MLRankedCandidate(
        symbol="GOOGL",
        trade_date=date.today(),
        side="long",
        p_long=0.55,
        p_flat=0.30,
        p_short=0.15,
        p_side=0.55,
        model_run_id="run_003",
        policy_version=1,
        feature_cutoff=old,
        decision_cutoff=datetime.now(),
    )


@pytest.fixture
def good_edge() -> DirectionalEdgeEstimate:
    return DirectionalEdgeEstimate(
        side="long", gross_edge=0.08, cost_pct=0.002, net_edge=0.078,
        hit_rate=0.60, payoff=2.0, sample_size=100, uncertainty=0.03,
    )


@pytest.fixture
def bad_edge_negative() -> DirectionalEdgeEstimate:
    return DirectionalEdgeEstimate(
        side="long", gross_edge=0.01, cost_pct=0.02, net_edge=-0.01,
        hit_rate=0.45, payoff=0.9, sample_size=50, uncertainty=0.08,
    )


@pytest.fixture
def uncertain_edge() -> DirectionalEdgeEstimate:
    return DirectionalEdgeEstimate(
        side="long", gross_edge=0.05, cost_pct=0.002, net_edge=0.048,
        hit_rate=0.52, payoff=1.2, sample_size=15, uncertainty=0.35,
    )


# ── AbstentionDecision ──────────────────────────────────────────────────────


class TestAbstentionDecision:
    def test_go_true(self) -> None:
        d = AbstentionDecision(go=True, reason="all_gates_passed")
        assert d.go is True
        assert d.is_blocked is False

    def test_go_false(self) -> None:
        d = AbstentionDecision(go=False, reason="p_side too low")
        assert d.go is False
        assert d.is_blocked is True


# ── AbstentionPolicy — permissive ───────────────────────────────────────────


class TestAbstentionPolicyPermissive:
    """Politique permissive : edge net > 0 uniquement."""

    def test_go_with_good_edge(self, candidate_long, good_edge) -> None:
        policy = AbstentionPolicy.permissive()
        decision = policy.evaluate(candidate_long, good_edge)
        assert decision.go is True

    def test_no_go_with_negative_edge(self, candidate_long, bad_edge_negative) -> None:
        policy = AbstentionPolicy.permissive()
        decision = policy.evaluate(candidate_long, bad_edge_negative)
        assert decision.go is False
        assert "net_edge" in decision.reason

    def test_no_go_without_edge(self, candidate_long) -> None:
        policy = AbstentionPolicy.permissive()
        decision = policy.evaluate(candidate_long, edge=None)
        assert decision.go is False
        assert "manquant" in decision.reason


# ── AbstentionPolicy — sensible defaults ────────────────────────────────────


class TestAbstentionPolicySensible:
    """Politique avec seuils raisonnables."""

    def test_go_with_everything_good(self, candidate_long, good_edge) -> None:
        policy = AbstentionPolicy.sensible_defaults()
        decision = policy.evaluate(candidate_long, good_edge)
        assert decision.go is True

    def test_no_go_low_p_side(self, candidate_ambiguous, good_edge) -> None:
        """p_side=0.38 < 0.45 → NO-GO."""
        policy = AbstentionPolicy.sensible_defaults()
        decision = policy.evaluate(candidate_ambiguous, good_edge)
        assert decision.go is False
        assert "p_side" in decision.reason

    def test_no_go_low_top2_margin(self, candidate_ambiguous, good_edge) -> None:
        """Marge top-2 trop faible."""
        policy = AbstentionPolicy(min_top2_margin=0.05, require_positive_edge=False)
        decision = policy.evaluate(candidate_ambiguous, good_edge)
        assert decision.go is False
        assert "marge top-2" in decision.reason

    def test_go_with_good_top2_margin(self, candidate_long, good_edge) -> None:
        """Marge top-2 OK (0.60 - 0.25 = 0.35 > 0.05)."""
        policy = AbstentionPolicy(min_top2_margin=0.05, require_positive_edge=False)
        decision = policy.evaluate(candidate_long, good_edge)
        assert decision.go is True

    def test_no_go_high_uncertainty(self, candidate_long, uncertain_edge) -> None:
        """Incertitude 0.35 > 0.20 → NO-GO."""
        policy = AbstentionPolicy.sensible_defaults()
        decision = policy.evaluate(candidate_long, uncertain_edge)
        assert decision.go is False
        assert "incertitude" in decision.reason

    def test_no_go_negative_edge(self, candidate_long, bad_edge_negative) -> None:
        policy = AbstentionPolicy.sensible_defaults()
        decision = policy.evaluate(candidate_long, bad_edge_negative)
        assert decision.go is False


# ── AbstentionPolicy — strict ───────────────────────────────────────────────


class TestAbstentionPolicyStrict:
    def test_no_go_stale_data(self, candidate_stale, good_edge) -> None:
        policy = AbstentionPolicy.strict()
        decision = policy.evaluate(candidate_stale, good_edge)
        assert decision.go is False
        assert "anciennes" in decision.reason

    def test_no_go_missing_feature_cutoff(self, candidate_long, good_edge) -> None:
        policy = AbstentionPolicy.strict()
        decision = policy.evaluate(candidate_long, good_edge)
        # candidate_long has no feature_cutoff
        assert decision.go is False
        assert "feature_cutoff" in decision.reason

    def test_go_with_fresh_data(self, good_edge) -> None:
        """Candidat avec feature_cutoff récent → GO si toutes les autres gates passent."""
        candidate = MLRankedCandidate(
            symbol="AAPL",
            trade_date=date.today(),
            side="long",
            p_long=0.55,
            p_flat=0.30,
            p_short=0.15,
            p_side=0.55,
            model_run_id="run_004",
            policy_version=1,
            feature_cutoff=datetime.now(),
            decision_cutoff=datetime.now(),
        )
        policy = AbstentionPolicy(
            min_p_side=0.50,
            min_top2_margin=0.05,
            max_uncertainty=0.20,
            require_positive_edge=True,
            max_data_age_days=1,
            require_data_availability=True,
        )
        decision = policy.evaluate(candidate, good_edge)
        assert decision.go is True


# ── evaluate_abstention_veto ────────────────────────────────────────────────


class TestEvaluateAbstentionVeto:
    def test_helper_returns_decision(self, candidate_long, good_edge) -> None:
        decision = evaluate_abstention_veto(candidate_long, good_edge)
        assert isinstance(decision, AbstentionDecision)
        assert decision.go is True

    def test_helper_rejects_low_p_side(self, candidate_ambiguous, good_edge) -> None:
        decision = evaluate_abstention_veto(
            candidate_ambiguous, good_edge, min_p_side=0.45,
        )
        assert decision.go is False
        assert "p_side" in decision.reason


# ── AbstentionPolicy — gate_results ─────────────────────────────────────────


class TestAbstentionPolicyGateResults:
    def test_all_gates_passed(self, candidate_long, good_edge) -> None:
        policy = AbstentionPolicy.permissive()
        decision = policy.evaluate(candidate_long, good_edge)
        assert "positive_edge" in decision.gate_results
        assert decision.gate_results["positive_edge"] is True

    def test_gate_failed_in_results(self, candidate_long, bad_edge_negative) -> None:
        policy = AbstentionPolicy.permissive()
        decision = policy.evaluate(candidate_long, bad_edge_negative)
        assert decision.gate_results["positive_edge"] is False

    def test_multiple_gates_in_results(self, candidate_long, good_edge) -> None:
        policy = AbstentionPolicy(min_p_side=0.45, min_top2_margin=0.10, require_positive_edge=True)
        decision = policy.evaluate(candidate_long, good_edge)
        assert "p_side" in decision.gate_results
        assert "top2_margin" in decision.gate_results
        assert "positive_edge" in decision.gate_results


# ── Abstention avec edge absent ─────────────────────────────────────────────


class TestAbstentionWithoutEdge:
    def test_permissive_without_edge_rejects(self, candidate_long) -> None:
        policy = AbstentionPolicy.permissive()
        decision = policy.evaluate(candidate_long, edge=None)
        assert decision.go is False

    def test_sensible_without_edge_rejects(self, candidate_long) -> None:
        policy = AbstentionPolicy.sensible_defaults()
        decision = policy.evaluate(candidate_long, edge=None)
        assert decision.go is False

    def test_edge_optional_when_not_required(self, candidate_long) -> None:
        """Si require_positive_edge=False, l'absence d'edge est OK."""
        policy = AbstentionPolicy(
            min_p_side=0.45, min_top2_margin=0.05, require_positive_edge=False,
        )
        decision = policy.evaluate(candidate_long, edge=None)
        assert decision.go is True
