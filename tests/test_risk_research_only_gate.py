"""Tests du gate research_only (Sprint Maître 0 / Section 17 Point 4).

Vérifie que tout artefact research_only est refusé avant paper ou live.
"""

from __future__ import annotations

import pytest

from risk_management.config import RiskConfig
from risk_management.enums import Decision, DecisionReasonCode
from risk_management.models import (
    DirectionalWinRateInfo,
    PredictionInfo,
    PriceInfo,
    SelectionScore,
)
from risk_management.portfolio_builder import PortfolioBuilder
from risk_management.selection_contract import (
    MLRankedCandidate,
    build_candidate_from_prediction,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _cfg(**overrides) -> RiskConfig:  # type: ignore[no-untyped-def]
    defaults = {
        "account_equity": 100_000,
        "risk_per_trade_pct": 0.01,
        "atr_stop_multiple": 2.0,
        "max_positions": 3,
        "max_position_weight": 0.10,
        "max_sector_weight": 0.30,
        "min_position_notional": 500.0,
        "min_breakout_days": 1,
        "enable_kelly_sizing": False,
    }
    defaults.update(overrides)
    return RiskConfig(**defaults)


def _pred(symbol: str, research_only: bool = False) -> PredictionInfo:
    return PredictionInfo(
        symbol=symbol,
        predicted_proba=0.80,
        predicted_class=1,
        run_id="run-1",
        predicted_side="long",
        proba_long=0.80,
        proba_flat=0.10,
        proba_short=0.10,
        research_only=research_only,
    )


def _price(symbol: str, last_close: float = 150.0, atr: float = 5.0) -> PriceInfo:
    return PriceInfo(symbol, last_close, atr)


# ── PredictionInfo.research_only ─────────────────────────────────────────────

def test_prediction_info_research_only_defaults_false():
    p = PredictionInfo("AAPL", 0.80, 1, "run-1")
    assert p.research_only is False


def test_prediction_info_research_only_true():
    p = PredictionInfo("AAPL", 0.80, 1, "run-1", research_only=True)
    assert p.research_only is True


# ── MLRankedCandidate.research_only propagation ──────────────────────────────

def test_build_candidate_propagates_research_only():
    from datetime import date
    c = build_candidate_from_prediction(
        symbol="AAPL",
        trade_date=date(2026, 7, 13),
        predicted_side="long",
        proba_long=0.8,
        proba_flat=0.1,
        proba_short=0.1,
        proba=0.8,
        model_run_id="run-1",
        research_only=True,
    )
    assert c.research_only is True


def test_build_candidate_defaults_research_only_false():
    from datetime import date
    c = build_candidate_from_prediction(
        symbol="AAPL",
        trade_date=date(2026, 7, 13),
        predicted_side="long",
        proba_long=0.8,
        proba_flat=0.1,
        proba_short=0.1,
        proba=0.8,
        model_run_id="run-1",
    )
    assert c.research_only is False


# ── PortfolioBuilder rejects research_only ───────────────────────────────────

def test_builder_rejects_research_only_prediction():
    """Un symbole avec une prédiction research_only=True est rejeté."""
    builder = PortfolioBuilder(_cfg())
    predictions = {
        "AAPL": _pred("AAPL", research_only=True),
    }
    entries = builder.build(
        [SelectionScore("AAPL", "Tech", 0.95)],
        {"AAPL": _price("AAPL")},
        predictions=predictions,
    )
    assert len(entries) == 1
    assert entries[0].decision == Decision.REJECTED
    assert entries[0].decision_reason_code == DecisionReasonCode.RESEARCH_ONLY_BLOCKED


def test_builder_accepts_non_research_only_prediction():
    """Un symbole normal (research_only=False) n'est PAS rejeté par ce gate."""
    builder = PortfolioBuilder(_cfg())
    predictions = {
        "AAPL": _pred("AAPL", research_only=False),
    }
    entries = builder.build(
        [SelectionScore("AAPL", "Tech", 0.95)],
        {"AAPL": _price("AAPL")},
        predictions=predictions,
    )
    # Doit être accepté (ou rejeté pour une autre raison, pas RESEARCH_ONLY)
    research_rejected = [
        e for e in entries
        if e.decision_reason_code == DecisionReasonCode.RESEARCH_ONLY_BLOCKED
    ]
    assert len(research_rejected) == 0


def test_builder_rejects_only_research_symbols_in_mixed_batch():
    """Dans un batch mixte, seuls les research_only sont rejetés."""
    builder = PortfolioBuilder(_cfg())
    predictions = {
        "AAPL": _pred("AAPL", research_only=True),
        "MSFT": _pred("MSFT", research_only=False),
    }
    entries = builder.build(
        [SelectionScore("AAPL", "Tech", 0.95), SelectionScore("MSFT", "Tech", 0.90)],
        {"AAPL": _price("AAPL"), "MSFT": _price("MSFT", 300.0, 8.0)},
        predictions=predictions,
    )
    aapl_entries = [e for e in entries if e.symbol == "AAPL"]
    msft_entries = [e for e in entries if e.symbol == "MSFT"]
    assert len(aapl_entries) == 1
    assert aapl_entries[0].decision_reason_code == DecisionReasonCode.RESEARCH_ONLY_BLOCKED
    # MSFT ne doit PAS être research_only rejeté
    assert all(
        e.decision_reason_code != DecisionReasonCode.RESEARCH_ONLY_BLOCKED
        for e in msft_entries
    )


def test_builder_no_predictions_no_research_rejection():
    """Sans predictions, le gate research_only ne bloque rien."""
    builder = PortfolioBuilder(_cfg())
    entries = builder.build(
        [SelectionScore("AAPL", "Tech", 0.95)],
        {"AAPL": _price("AAPL")},
    )
    research_rejected = [
        e for e in entries
        if e.decision_reason_code == DecisionReasonCode.RESEARCH_ONLY_BLOCKED
    ]
    assert len(research_rejected) == 0


# ── DecisionReasonCode ───────────────────────────────────────────────────────

def test_research_only_blocked_reason_code_exists():
    assert DecisionReasonCode.RESEARCH_ONLY_BLOCKED == "research_only_blocked"


# ── Pre-live checklist gate connectivity smoke ───────────────────────────────

def test_pre_live_checklist_includes_research_gate():
    """Le gate S00_RESEARCH existe dans la checklist canonique."""
    from risk_management.pre_live_checklist import build_pre_live_checklist

    checklist = build_pre_live_checklist()
    research_gates = [g for g in checklist.gates if g.gate_id == "S00_RESEARCH"]
    assert len(research_gates) == 1
    assert "research" in research_gates[0].name.lower()
