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


# ── Section 17 Point 5.2 : to_selection_score adapter ───────────────────────

def test_to_selection_score_long_maps_side_correctly() -> None:
    """MLRankedCandidate(side=long) → SelectionScore(side=buy)."""
    from risk_management.selection_contract import to_selection_score

    c = MLRankedCandidate(
        symbol="AAPL", trade_date=date(2026, 7, 10),
        side="long", p_long=0.7, p_flat=0.2, p_short=0.1,
        p_side=0.7, model_run_id="run-001", side_rank=1,
    )
    ss = to_selection_score(c, sector="Tech", snapshot_date=date(2026, 7, 10))
    assert ss.symbol == "AAPL"
    assert ss.side == "buy"
    assert ss.score_source == "ml_p_side"
    assert ss.score_used == 0.7
    assert ss.selection_rank == 1
    assert ss.calibration_run_id == "run-001"


def test_to_selection_score_short_maps_side_to_sell() -> None:
    """MLRankedCandidate(side=short) → SelectionScore(side=sell)."""
    from risk_management.selection_contract import to_selection_score

    c = MLRankedCandidate(
        symbol="TSLA", trade_date=date(2026, 7, 10),
        side="short", p_long=0.1, p_flat=0.3, p_short=0.6,
        p_side=0.6, model_run_id="run-002", side_rank=2,
    )
    ss = to_selection_score(c, sector="Auto", snapshot_date=date(2026, 7, 10))
    assert ss.side == "sell"
    assert ss.score_source == "ml_p_side"
    assert ss.score_used == 0.6


def test_to_selection_score_preserves_universe_run_id() -> None:
    """L'universe_run_id est transmis au SelectionScore."""
    from risk_management.selection_contract import to_selection_score

    c = MLRankedCandidate(
        symbol="AAPL", trade_date=date(2026, 7, 10),
        side="long", p_long=0.5, p_flat=0.3, p_short=0.2,
        p_side=0.5, model_run_id="run-001",
        universe_run_id="univ-abc-123",
    )
    ss = to_selection_score(c)
    assert ss.universe_run_id == "univ-abc-123"


# ── Section 17 Point 5.4 : validate_payload_completeness ────────────────────

def test_validate_payload_completeness_all_present() -> None:
    """Un payload complet ne génère aucune violation."""
    from risk_management.selection_contract import validate_payload_completeness

    c = MLRankedCandidate(
        symbol="AAPL", trade_date=date(2026, 7, 10),
        side="long", p_long=0.6, p_flat=0.3, p_short=0.1,
        p_side=0.6, model_run_id="run-001", policy_version=2,
        universe_run_id="univ-1", feature_cutoff=date(2026, 7, 10),
        account="paper_trading",
    )
    violations = validate_payload_completeness(c)
    assert len(violations) == 0


def test_validate_payload_completeness_missing_symbol() -> None:
    """Le symbole vide est déjà rejeté par __post_init__ donc
    validate_payload_completeness ne le vérifie pas (non-redondant)."""
    from risk_management.selection_contract import validate_payload_completeness

    # Un candidat valide ne génère pas de violation
    c = MLRankedCandidate(
        symbol="AAPL", trade_date=date(2026, 7, 10),
        side="long", p_long=0.6, p_flat=0.3, p_short=0.1,
        p_side=0.6, model_run_id="run-001",
        universe_run_id="univ-1", feature_cutoff=date(2026, 7, 10),
        account="test",
    )
    violations = validate_payload_completeness(c)
    assert "missing:symbol" not in violations  # __post_init__ handles this


def test_validate_payload_completeness_missing_trade_date() -> None:
    """trade_date=None n'est pas rejeté par __post_init__ mais doit l'être ici."""
    from risk_management.selection_contract import validate_payload_completeness

    # On doit contourner le type checker pour injecter trade_date=None
    # dans un frozen dataclass. object.__setattr__ le permet en __post_init__.
    c = MLRankedCandidate(
        symbol="AAPL", trade_date=date(2026, 7, 10),
        side="long", p_long=0.6, p_flat=0.3, p_short=0.1,
        p_side=0.6, model_run_id="run-001",
        universe_run_id="univ-1", feature_cutoff=date(2026, 7, 10),
        account="test",
    )
    object.__setattr__(c, "trade_date", None)
    violations = validate_payload_completeness(c)
    assert "missing:trade_date" in violations


def test_validate_payload_completeness_missing_universe_run_id() -> None:
    from risk_management.selection_contract import validate_payload_completeness

    c = MLRankedCandidate(
        symbol="AAPL", trade_date=date(2026, 7, 10),
        side="long", p_long=0.6, p_flat=0.3, p_short=0.1,
        p_side=0.6, model_run_id="run-001",
        universe_run_id=None, feature_cutoff=date(2026, 7, 10),
        account="test",
    )
    violations = validate_payload_completeness(c)
    assert "missing:universe_run_id" in violations


def test_validate_payload_completeness_missing_feature_cutoff() -> None:
    from risk_management.selection_contract import validate_payload_completeness

    c = MLRankedCandidate(
        symbol="AAPL", trade_date=date(2026, 7, 10),
        side="long", p_long=0.6, p_flat=0.3, p_short=0.1,
        p_side=0.6, model_run_id="run-001",
        universe_run_id="univ-1", feature_cutoff=None,
        account="test",
    )
    violations = validate_payload_completeness(c)
    assert "missing:feature_cutoff" in violations


def test_validate_payload_completeness_multiple_violations() -> None:
    from risk_management.selection_contract import validate_payload_completeness

    c = MLRankedCandidate(
        symbol="AAPL", trade_date=date(2026, 7, 10),
        side="long", p_long=0.6, p_flat=0.3, p_short=0.1,
        p_side=0.6, model_run_id="run-001",
        universe_run_id=None, feature_cutoff=None,
        account="",
    )
    violations = validate_payload_completeness(c)
    assert "missing:universe_run_id" in violations
    assert "missing:feature_cutoff" in violations
    assert "missing:account" in violations
    assert len(violations) >= 3  # universe_run_id + feature_cutoff + account


def test_validate_payload_completeness_missing_account() -> None:
    """Point 5.4 : account vide/absent → violation."""
    from risk_management.selection_contract import validate_payload_completeness

    c = MLRankedCandidate(
        symbol="AAPL", trade_date=date(2026, 7, 10),
        side="long", p_long=0.6, p_flat=0.3, p_short=0.1,
        p_side=0.6, model_run_id="run-001",
        universe_run_id="univ-1", feature_cutoff=date(2026, 7, 10),
        account="",
    )
    violations = validate_payload_completeness(c)
    assert "missing:account" in violations


# ── Section 17 Point 5.5 : bridge/CLI common fixture parity ─────────────────

# Common fixture: same predictions → same MLRankedCandidate contract
_COMMON_PREDICTIONS_FIXTURE = [
    {"symbol": "AAA", "predicted_side": "long", "proba_long": 0.70, "proba_flat": 0.20, "proba_short": 0.10, "proba": 0.70, "model_run_id": "run-001"},
    {"symbol": "BBB", "predicted_side": "short", "proba_long": 0.10, "proba_flat": 0.15, "proba_short": 0.75, "proba": 0.75, "model_run_id": "run-001"},
    {"symbol": "CCC", "predicted_side": "flat", "proba_long": 0.30, "proba_flat": 0.50, "proba_short": 0.20, "proba": 0.50, "model_run_id": "run-001"},
    {"symbol": "DDD", "predicted_side": "long", "proba_long": 0.55, "proba_flat": 0.30, "proba_short": 0.15, "proba": 0.55, "model_run_id": "run-001"},
]


def test_bridge_cli_parity_same_candidates_from_common_fixture() -> None:
    """Point 5.5 : Le bridge et le CLI produisent le même contrat ML-first
    à partir d'une fixture commune de prédictions."""
    from risk_management.selection_contract import (
        build_candidate_from_prediction,
        build_rankings,
        filter_actionable,
        to_selection_score,
    )

    trade_date = date(2026, 7, 10)

    # ── Chemin commun : factory MLRankedCandidate (utilisé par bridge ET CLI) ──
    candidates: list[MLRankedCandidate] = []
    for pred in _COMMON_PREDICTIONS_FIXTURE:
        c = build_candidate_from_prediction(
            symbol=pred["symbol"],
            trade_date=trade_date,
            predicted_side=pred["predicted_side"],
            proba_long=pred["proba_long"],
            proba_flat=pred["proba_flat"],
            proba_short=pred["proba_short"],
            proba=pred["proba"],
            model_run_id=pred["model_run_id"],
            universe_run_id="univ-common",
            feature_cutoff=trade_date,
        )
        candidates.append(c)

    assert len(candidates) == 4

    # ── Rankings (bridge path) ──
    actionable = filter_actionable(candidates)
    assert len(actionable) == 3  # CCC is flat, excluded

    longs, shorts = build_rankings(actionable)
    assert len(longs) == 2
    assert len(shorts) == 1

    # AAA has p_side=0.70, DDD has p_side=0.55 → AAA rank 1, DDD rank 2
    assert longs[0].symbol == "AAA"
    assert longs[0].side_rank == 1
    assert longs[1].symbol == "DDD"
    assert longs[1].side_rank == 2

    # BBB is the only short
    assert shorts[0].symbol == "BBB"

    # ── Adapter → SelectionScore (legacy boundary) ──
    # Both bridge and CLI use to_selection_score() to cross the legacy boundary
    for candidate in [*longs, *shorts]:
        ss = to_selection_score(candidate, snapshot_date=trade_date)
        assert ss.score_source == "ml_p_side"
        assert ss.score_used == candidate.p_side
        assert ss.selection_rank == candidate.side_rank
        # Side mapping: long→buy, short→sell
        if candidate.side == "long":
            assert ss.side == "buy"
        else:
            assert ss.side == "sell"


def test_bridge_cli_parity_flat_not_in_rankings() -> None:
    """Les flat ne sont jamais dans les rankings, ni dans les SelectionScores."""
    from risk_management.selection_contract import (
        build_candidate_from_prediction,
        build_rankings,
        filter_actionable,
    )

    trade_date = date(2026, 7, 10)
    candidates = [
        build_candidate_from_prediction(
            symbol=sym, trade_date=trade_date,
            predicted_side=side, proba_long=pl, proba_flat=pf, proba_short=ps,
            proba=pside, model_run_id="run-001",
        )
        for sym, side, pl, pf, ps, pside in [
            ("AAA", "flat", 0.3, 0.5, 0.2, 0.5),
            ("BBB", "flat", 0.25, 0.55, 0.2, 0.55),
        ]
    ]
    actionable = filter_actionable(candidates)
    assert len(actionable) == 0

    longs, shorts = build_rankings(candidates)
    assert len(longs) == 0
    assert len(shorts) == 0


def test_bridge_cli_parity_score_source_is_always_ml_p_side() -> None:
    """Point 5.5 : Le score_source est toujours 'ml_p_side' — le ML est l'autorité."""
    from risk_management.selection_contract import (
        build_candidate_from_prediction,
        to_selection_score,
    )

    c = build_candidate_from_prediction(
        symbol="AAPL", trade_date=date(2026, 7, 10),
        predicted_side="long", proba_long=0.8, proba_flat=0.1, proba_short=0.1,
        proba=0.8, model_run_id="run-001",
    )
    ss = to_selection_score(c)
    assert ss.score_source == "ml_p_side", (
        "Le score_source DOIT être 'ml_p_side' — le ML est la seule autorité "
        "sur le score nominal. Aucun rescoring selector n'est permis."
    )
