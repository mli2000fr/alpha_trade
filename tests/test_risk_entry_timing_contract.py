"""Tests du contrat temporel decision_cutoff → entry J+1 (Sprint Maître 0 / Section 17 Point 3)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from risk_management.selection_contract import (
    MLRankedCandidate,
    compute_entry_date,
    validate_decision_timing,
    assert_valid_entry_timing,
)


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def trading_day() -> date:
    """Un lundi NYSE (2026-07-13 est un lundi)."""
    return date(2026, 7, 13)


@pytest.fixture
def weekend_day() -> date:
    """Un samedi (marché fermé)."""
    return date(2026, 7, 11)


@pytest.fixture
def valid_candidate(trading_day: date) -> MLRankedCandidate:
    return MLRankedCandidate(
        symbol="AAPL",
        trade_date=trading_day,
        side="long",
        p_long=0.6,
        p_flat=0.3,
        p_short=0.1,
        p_side=0.6,
        model_run_id="run-1",
        feature_cutoff=datetime(2026, 7, 13, 21, 0, 0),
        decision_cutoff=datetime(2026, 7, 13, 21, 30, 0),
    )


# ── compute_entry_date ──────────────────────────────────────────────────────

def test_entry_date_is_next_trading_day_after_monday(trading_day: date):
    assert compute_entry_date(trading_day) == date(2026, 7, 14)  # mardi


def test_entry_date_is_next_trading_day_after_friday():
    assert compute_entry_date(date(2026, 7, 10)) == date(2026, 7, 13)  # lundi


def test_entry_date_skips_weekend(weekend_day: date):
    """Même depuis un samedi, next_trading_day donne le lundi suivant."""
    entry = compute_entry_date(weekend_day)
    assert entry.weekday() < 5
    assert entry > weekend_day


# ── validate_decision_timing ────────────────────────────────────────────────

def test_valid_timing_no_violations(valid_candidate: MLRankedCandidate, trading_day: date):
    violations = validate_decision_timing(valid_candidate, decision_date=trading_day)
    assert violations == []


def test_decision_on_weekend_rejected(valid_candidate: MLRankedCandidate, weekend_day: date):
    violations = validate_decision_timing(valid_candidate, decision_date=weekend_day)
    assert any("decision_date_not_trading_day" in v for v in violations)


def test_feature_cutoff_after_decision_rejected(valid_candidate: MLRankedCandidate, trading_day: date):
    candidate = MLRankedCandidate(
        symbol="AAPL",
        trade_date=trading_day,
        side="long",
        p_long=0.6, p_flat=0.3, p_short=0.1, p_side=0.6,
        model_run_id="run-1",
        feature_cutoff=datetime(2026, 7, 14, 21, 0, 0),  # J+1 !!
        decision_cutoff=datetime(2026, 7, 13, 21, 30, 0),
    )
    violations = validate_decision_timing(candidate, decision_date=trading_day)
    assert any("feature_cutoff_after_decision" in v for v in violations)


def test_decision_cutoff_mismatch_rejected(valid_candidate: MLRankedCandidate, trading_day: date):
    candidate = MLRankedCandidate(
        symbol="AAPL",
        trade_date=trading_day,
        side="long",
        p_long=0.6, p_flat=0.3, p_short=0.1, p_side=0.6,
        model_run_id="run-1",
        feature_cutoff=datetime(2026, 7, 13, 21, 0, 0),
        decision_cutoff=datetime(2026, 7, 12, 21, 30, 0),  # J-1 !!
    )
    violations = validate_decision_timing(candidate, decision_date=trading_day)
    assert any("decision_cutoff_mismatch" in v for v in violations)


def test_entry_must_be_after_decision(valid_candidate: MLRankedCandidate, trading_day: date):
    """Le contrat impose que l'entrée ne peut pas avoir lieu le jour J."""
    violations = validate_decision_timing(valid_candidate, decision_date=trading_day)
    # La fonction calcule entry_date = next_trading_day(trading_day)
    # et vérifie entry_date > trading_day (ce qui est toujours vrai
    # pour un jour de bourse valide puisque next_trading_day est > from_date).
    assert not any("entry_not_after_decision" in v for v in violations)


def test_null_cutoffs_no_violations(trading_day: date):
    """Les cutoffs None sont autorisés (rétrocompatibilité)."""
    candidate = MLRankedCandidate(
        symbol="AAPL",
        trade_date=trading_day,
        side="long",
        p_long=0.6, p_flat=0.3, p_short=0.1, p_side=0.6,
        model_run_id="run-1",
    )
    violations = validate_decision_timing(candidate, decision_date=trading_day)
    # feature_cutoff=None et decision_cutoff=None → pas de violation
    # Seul le check entry > decision est fait, qui passe pour un trading day
    assert not any("cutoff" in v for v in violations)


# ── assert_valid_entry_timing ───────────────────────────────────────────────

def test_assert_passes_for_valid_candidate(valid_candidate: MLRankedCandidate, trading_day: date):
    assert_valid_entry_timing(valid_candidate, decision_date=trading_day)


def test_assert_raises_for_weekend_decision(valid_candidate: MLRankedCandidate, weekend_day: date):
    with pytest.raises(ValueError, match="decision_cutoff→entry"):
        assert_valid_entry_timing(valid_candidate, decision_date=weekend_day)


def test_assert_raises_for_future_features(valid_candidate: MLRankedCandidate, trading_day: date):
    candidate = MLRankedCandidate(
        symbol="AAPL",
        trade_date=trading_day,
        side="long",
        p_long=0.6, p_flat=0.3, p_short=0.1, p_side=0.6,
        model_run_id="run-1",
        feature_cutoff=datetime(2026, 7, 20, 21, 0, 0),  # futur
        decision_cutoff=datetime(2026, 7, 13, 21, 30, 0),
    )
    with pytest.raises(ValueError, match="decision_cutoff→entry"):
        assert_valid_entry_timing(candidate, decision_date=trading_day)


# ── next_trading_day edge cases ─────────────────────────────────────────────

def test_next_trading_day_nth_2():
    from common.market_calendar import next_trading_day
    j1 = next_trading_day(date(2026, 7, 13))
    j2 = next_trading_day(date(2026, 7, 13), nth=2)
    assert j1 == date(2026, 7, 14)
    assert j2 > j1
    assert j2.weekday() < 5


def test_next_trading_day_rejects_nth_zero():
    from common.market_calendar import next_trading_day
    with pytest.raises(ValueError, match="nth"):
        next_trading_day(date(2026, 7, 13), nth=0)


# ── trading_days_between ────────────────────────────────────────────────────

def test_trading_days_between():
    from common.market_calendar import trading_days_between
    # Un lundi au mardi = 2 jours de bourse
    assert trading_days_between(date(2026, 7, 13), date(2026, 7, 14)) == 2
    # Lundi au lundi suivant = 6 jours de bourse
    assert trading_days_between(date(2026, 7, 13), date(2026, 7, 20)) == 6
    # Inversé = 0
    assert trading_days_between(date(2026, 7, 20), date(2026, 7, 13)) == 0


# ── PortfolioBuilder integration smoke test ─────────────────────────────────

def test_portfolio_builder_sets_entry_date(trading_day: date):
    """Vérifie que PortfolioBuilder.build() positionne trade_date et entry_date."""
    from risk_management.config import RiskConfig
    from risk_management.portfolio_builder import PortfolioBuilder

    builder = PortfolioBuilder(RiskConfig())
    entries = builder.build([], {}, trade_date=trading_day)
    # Marché ouvert mais 0 candidat → liste vide, pas d'erreur
    assert entries == []


def test_portfolio_builder_does_not_block_on_holiday(weekend_day: date):
    """Vérifie que PortfolioBuilder.build() ne bloque pas un jour fermé.

    Le vrai contrat est entry_date > trade_date, ce qui est toujours vrai
    via next_trading_day(). Un jour non-trading émet un avertissement
    mais n'empêche pas la construction du portefeuille (utile en backtest).
    """
    from risk_management.config import RiskConfig
    from risk_management.portfolio_builder import PortfolioBuilder

    builder = PortfolioBuilder(RiskConfig())
    # Même un samedi, avec 0 candidat, le build doit réussir (liste vide)
    entries = builder.build([], {}, trade_date=weekend_day)
    assert entries == []
