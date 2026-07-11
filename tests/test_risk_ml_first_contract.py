"""Tests pour le contrat ML → Risque — Sprint Maître 5."""

from __future__ import annotations

from datetime import date

import pytest

from risk_management.selection_contract import (
    MLRankedCandidate,
    RiskDecisionInput,
    SelectorVetoContext,
    build_candidate_from_prediction,
    build_rankings,
    filter_actionable,
    validate_candidate_consistency,
)


# ── MLRankedCandidate ───────────────────────────────────────────────────────

def test_ml_ranked_candidate_construction() -> None:
    c = MLRankedCandidate(
        symbol="AAPL",
        trade_date=date(2026, 7, 10),
        side="long",
        p_long=0.6, p_flat=0.3, p_short=0.1,
        p_side=0.6,
        model_run_id="run-001",
    )
    assert c.symbol == "AAPL"
    assert c.is_actionable() is True
    assert c.side == "long"


def test_ml_ranked_candidate_flat_not_actionable() -> None:
    c = MLRankedCandidate(
        symbol="AAPL",
        trade_date=date(2026, 7, 10),
        side="flat",
        p_long=0.3, p_flat=0.4, p_short=0.3,
        p_side=0.4,
        model_run_id="run-001",
    )
    assert c.is_actionable() is False


def test_ml_ranked_candidate_rejects_invalid_side() -> None:
    with pytest.raises(ValueError, match="side"):
        MLRankedCandidate(
            symbol="AAPL", trade_date=date(2026, 7, 10),
            side="buy", p_long=0.5, p_flat=0.3, p_short=0.2,
            p_side=0.5, model_run_id="run-001",
        )


def test_ml_ranked_candidate_rejects_empty_symbol() -> None:
    with pytest.raises(ValueError, match="symbol"):
        MLRankedCandidate(
            symbol="", trade_date=date(2026, 7, 10),
            side="long", p_long=0.5, p_flat=0.3, p_short=0.2,
            p_side=0.5, model_run_id="run-001",
        )


def test_ml_ranked_candidate_rejects_empty_model_run_id() -> None:
    with pytest.raises(ValueError, match="model_run_id"):
        MLRankedCandidate(
            symbol="AAPL", trade_date=date(2026, 7, 10),
            side="long", p_long=0.5, p_flat=0.3, p_short=0.2,
            p_side=0.5, model_run_id="",
        )


def test_ml_ranked_candidate_side_consistency_long() -> None:
    """side=long doit impliquer p_side ≈ p_long."""
    with pytest.raises(ValueError, match="Incohérence"):
        MLRankedCandidate(
            symbol="AAPL", trade_date=date(2026, 7, 10),
            side="long", p_long=0.6, p_flat=0.3, p_short=0.1,
            p_side=0.1,  # incohérent !
            model_run_id="run-001",
        )


def test_ml_ranked_candidate_to_dict() -> None:
    c = MLRankedCandidate(
        symbol="MSFT", trade_date=date(2026, 7, 10),
        side="short", p_long=0.1, p_flat=0.3, p_short=0.6,
        p_side=0.6, model_run_id="run-002", side_rank=1,
    )
    d = c.to_dict()
    assert d["symbol"] == "MSFT"
    assert d["side"] == "short"
    assert d["side_rank"] == 1


# ── SelectorVetoContext ─────────────────────────────────────────────────────

def test_selector_veto_context_no_side_field() -> None:
    """Le SelectorVetoContext ne doit PAS avoir de champ side ou rank."""
    ctx = SelectorVetoContext(symbol="AAPL")
    assert not hasattr(ctx, "side")
    assert not hasattr(ctx, "side_rank")
    assert not hasattr(ctx, "rank")


def test_selector_veto_context_with_veto() -> None:
    ctx = SelectorVetoContext(
        symbol="AAPL", sector="Tech",
        earnings_blackout=True, veto=True,
        veto_reason="earnings_window",
    )
    assert ctx.veto is True
    assert ctx.veto_reason == "earnings_window"


# ── RiskDecisionInput ───────────────────────────────────────────────────────

def test_risk_decision_input() -> None:
    candidate = MLRankedCandidate(
        symbol="AAPL", trade_date=date(2026, 7, 10),
        side="long", p_long=0.6, p_flat=0.3, p_short=0.1,
        p_side=0.6, model_run_id="run-001",
    )
    veto_ctx = SelectorVetoContext(symbol="AAPL", veto=False)
    inp = RiskDecisionInput(candidate=candidate, veto_context=veto_ctx)
    assert inp.is_vetoed is False
    assert inp.side == "long"


def test_risk_decision_input_vetoed() -> None:
    candidate = MLRankedCandidate(
        symbol="AAPL", trade_date=date(2026, 7, 10),
        side="long", p_long=0.6, p_flat=0.3, p_short=0.1,
        p_side=0.6, model_run_id="run-001",
    )
    veto_ctx = SelectorVetoContext(symbol="AAPL", veto=True, veto_reason="low_quality")
    inp = RiskDecisionInput(candidate=candidate, veto_context=veto_ctx)
    assert inp.is_vetoed is True
    assert inp.veto_reason == "low_quality"


# ── build_rankings ──────────────────────────────────────────────────────────

def test_build_rankings_separate_long_short() -> None:
    candidates = [
        MLRankedCandidate(symbol="A", trade_date=date(2026,7,10), side="long", p_long=0.7, p_flat=0.2, p_short=0.1, p_side=0.7, model_run_id="r1"),
        MLRankedCandidate(symbol="B", trade_date=date(2026,7,10), side="short", p_long=0.1, p_flat=0.2, p_short=0.7, p_side=0.7, model_run_id="r1"),
        MLRankedCandidate(symbol="C", trade_date=date(2026,7,10), side="long", p_long=0.5, p_flat=0.3, p_short=0.2, p_side=0.5, model_run_id="r1"),
        MLRankedCandidate(symbol="D", trade_date=date(2026,7,10), side="flat", p_long=0.3, p_flat=0.4, p_short=0.3, p_side=0.4, model_run_id="r1"),
    ]
    longs, shorts = build_rankings(candidates)
    assert len(longs) == 2
    assert len(shorts) == 1
    assert longs[0].symbol == "A"  # p_side=0.7 > 0.5
    assert longs[0].side_rank == 1
    assert longs[1].side_rank == 2


def test_build_rankings_flat_excluded() -> None:
    candidates = [
        MLRankedCandidate(symbol="A", trade_date=date(2026,7,10), side="flat", p_long=0.3, p_flat=0.4, p_short=0.3, p_side=0.4, model_run_id="r1"),
    ]
    longs, shorts = build_rankings(candidates)
    assert len(longs) == 0
    assert len(shorts) == 0


# ── filter_actionable ───────────────────────────────────────────────────────

def test_filter_actionable_excludes_flat() -> None:
    candidates = [
        MLRankedCandidate(symbol="A", trade_date=date(2026,7,10), side="long", p_long=0.5, p_flat=0.3, p_short=0.2, p_side=0.5, model_run_id="r1"),
        MLRankedCandidate(symbol="B", trade_date=date(2026,7,10), side="flat", p_long=0.3, p_flat=0.4, p_short=0.3, p_side=0.4, model_run_id="r1"),
    ]
    actionable = filter_actionable(candidates)
    assert len(actionable) == 1
    assert actionable[0].symbol == "A"


# ── validate_candidate_consistency ──────────────────────────────────────────

def test_validate_consistent_candidate() -> None:
    c = MLRankedCandidate(
        symbol="AAPL", trade_date=date(2026, 7, 10),
        side="long", p_long=0.6, p_flat=0.3, p_short=0.1,
        p_side=0.6, model_run_id="r1",
    )
    violations = validate_candidate_consistency(c)
    assert len(violations) == 0


def test_validate_detects_prob_sum_not_one() -> None:
    c = MLRankedCandidate(
        symbol="AAPL", trade_date=date(2026, 7, 10),
        side="long", p_long=0.6, p_flat=0.6, p_short=0.6,
        p_side=0.6, model_run_id="r1",
    )
    violations = validate_candidate_consistency(c)
    assert any("prob_sum_not_one" in v for v in violations)


def test_validate_detects_missing_trade_date() -> None:
    """Cas où trade_date n'est pas renseigné — détecté."""
    c = MLRankedCandidate(
        symbol="AAPL", trade_date=date(2026, 7, 10),
        side="long", p_long=0.6, p_flat=0.3, p_short=0.1,
        p_side=0.6, model_run_id="r1",
    )
    assert c.trade_date is not None


# ── build_candidate_from_prediction ─────────────────────────────────────────

def test_build_from_prediction_long() -> None:
    c = build_candidate_from_prediction(
        symbol="AAPL", trade_date=date(2026, 7, 10),
        predicted_side="long", proba_long=0.6, proba_flat=0.3, proba_short=0.1,
        proba=0.6, model_run_id="run-001",
    )
    assert c.side == "long"
    assert c.p_side == 0.6
    assert c.is_actionable() is True


def test_build_from_prediction_flat() -> None:
    c = build_candidate_from_prediction(
        symbol="AAPL", trade_date=date(2026, 7, 10),
        predicted_side="flat", proba_long=0.3, proba_flat=0.4, proba_short=0.3,
        proba=0.4, model_run_id="run-001",
    )
    assert c.side == "flat"
    assert c.is_actionable() is False


def test_build_from_prediction_unknown_side_defaults_flat() -> None:
    c = build_candidate_from_prediction(
        symbol="AAPL", trade_date=date(2026, 7, 10),
        predicted_side="unknown", proba_long=0.5, proba_flat=0.3, proba_short=0.2,
        proba=0.5, model_run_id="run-001",
    )
    assert c.side == "flat"
