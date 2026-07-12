"""Tests du lineage univers (Section 17 Point 2.2) — universe_run_id et fingerprint."""

from __future__ import annotations

from datetime import date

import pytest

from common.tradable_universe import compute_universe_fingerprint
from risk_management.models import PredictionInfo, SelectionScore
from risk_management.selection_contract import (
    MLRankedCandidate,
    build_candidate_from_prediction,
)


# ── compute_universe_fingerprint ─────────────────────────────────────────────

def test_fingerprint_deterministic_same_inputs():
    fp1 = compute_universe_fingerprint("run-1", ["AAPL", "MSFT", "XOM"])
    fp2 = compute_universe_fingerprint("run-1", ["MSFT", "XOM", "AAPL"])  # ordre différent
    assert fp1 == fp2  # tri interne
    assert len(fp1) == 16


def test_fingerprint_differs_on_different_run_id():
    fp1 = compute_universe_fingerprint("run-1", ["AAPL"])
    fp2 = compute_universe_fingerprint("run-2", ["AAPL"])
    assert fp1 != fp2


def test_fingerprint_differs_on_different_symbols():
    fp1 = compute_universe_fingerprint("run-1", ["AAPL", "MSFT"])
    fp2 = compute_universe_fingerprint("run-1", ["AAPL"])
    assert fp1 != fp2


def test_fingerprint_includes_snapshot_date():
    fp1 = compute_universe_fingerprint("run-1", ["AAPL"], snapshot_date="2026-07-13")
    fp2 = compute_universe_fingerprint("run-1", ["AAPL"], snapshot_date="2026-07-14")
    assert fp1 != fp2


def test_fingerprint_includes_capital_preset():
    fp1 = compute_universe_fingerprint("run-1", ["AAPL"], capital_preset_key="small")
    fp2 = compute_universe_fingerprint("run-1", ["AAPL"], capital_preset_key="large")
    assert fp1 != fp2


def test_fingerprint_empty_symbols():
    fp = compute_universe_fingerprint("run-1", [])
    assert len(fp) == 16
    # Même fingerprint pour liste vide, indépendamment des symboles vides
    assert fp == compute_universe_fingerprint("run-1", ["", "  "])


def test_fingerprint_strips_and_uppercases():
    fp1 = compute_universe_fingerprint("run-1", [" aapl ", "MSFT"])
    fp2 = compute_universe_fingerprint("run-1", ["AAPL", "msft"])
    assert fp1 == fp2


# ── PredictionInfo.universe_run_id ───────────────────────────────────────────

def test_prediction_info_universe_run_id_default_none():
    p = PredictionInfo("AAPL", 0.80, 1, "run-1")
    assert p.universe_run_id is None


def test_prediction_info_universe_run_id_set():
    p = PredictionInfo("AAPL", 0.80, 1, "run-1", universe_run_id="universe-run-42")
    assert p.universe_run_id == "universe-run-42"


# ── SelectionScore.universe_run_id ───────────────────────────────────────────

def test_selection_score_universe_run_id_default_none():
    s = SelectionScore("AAPL", "Tech", 0.95)
    assert s.universe_run_id is None


def test_selection_score_universe_run_id_set():
    s = SelectionScore("AAPL", "Tech", 0.95, universe_run_id="universe-run-42")
    assert s.universe_run_id == "universe-run-42"


# ── MLRankedCandidate.universe_run_id propagation ────────────────────────────

def test_build_candidate_propagates_universe_run_id():
    c = build_candidate_from_prediction(
        symbol="AAPL",
        trade_date=date(2026, 7, 13),
        predicted_side="long",
        proba_long=0.8,
        proba_flat=0.1,
        proba_short=0.1,
        proba=0.8,
        model_run_id="run-1",
        universe_run_id="universe-run-42",
    )
    assert c.universe_run_id == "universe-run-42"


def test_ml_ranked_candidate_universe_run_id_in_to_dict():
    c = MLRankedCandidate(
        symbol="AAPL",
        trade_date=date(2026, 7, 13),
        side="long",
        p_long=0.6, p_flat=0.3, p_short=0.1, p_side=0.6,
        model_run_id="run-1",
        universe_run_id="universe-run-42",
    )
    d = c.to_dict()
    assert d["universe_run_id"] == "universe-run-42"


# ── PortfolioBuilder smoke: universe_run_id passes through ───────────────────

def test_portfolio_builder_accepts_selection_score_with_universe_run_id():
    """Vérifie que le PortfolioBuilder ne crashe pas avec un SelectionScore portant universe_run_id."""
    from datetime import date as _date
    from risk_management.config import RiskConfig
    from risk_management.models import PriceInfo
    from risk_management.portfolio_builder import PortfolioBuilder

    cfg = RiskConfig(
        account_equity=100_000,
        risk_per_trade_pct=0.01,
        atr_stop_multiple=2.0,
        max_positions=3,
        max_position_weight=0.10,
        max_sector_weight=0.30,
        min_position_notional=500.0,
        min_breakout_days=1,
        enable_kelly_sizing=False,
    )
    builder = PortfolioBuilder(cfg)
    cand = SelectionScore("AAPL", "Tech", 0.95, universe_run_id="universe-run-42")
    # Le build ne doit pas crasher ; le nombre d'entrées dépend du sizing
    entries = builder.build(
        [cand],
        {"AAPL": PriceInfo("AAPL", 150.0, 5.0)},
        trade_date=_date(2026, 7, 13),
    )
    assert cand.universe_run_id == "universe-run-42"
    # Au moins une entrée (acceptée ou rejetée) est produite
    assert isinstance(entries, list)
