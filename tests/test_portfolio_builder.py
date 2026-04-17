"""Tests unitaires — PortfolioBuilder."""
from __future__ import annotations

from risk_management.config import RiskConfig
from risk_management.models import CandidateScore, PriceInfo
from risk_management.portfolio_builder import PortfolioBuilder


def _cfg() -> RiskConfig:
    return RiskConfig(
        account_equity=100_000,
        risk_per_trade_pct=0.01,
        atr_stop_multiple=2.0,
        max_positions=3,
        max_position_weight=0.10,
        max_sector_weight=0.30,
        min_position_notional=500.0,
    )


def _candidates() -> list[CandidateScore]:
    return [
        CandidateScore("AAPL", "Tech", 0.95),
        CandidateScore("MSFT", "Tech", 0.90),
        CandidateScore("XOM", "Energy", 0.85),
        CandidateScore("LOW", "Retail", 0.80),
    ]


def _prices() -> dict[str, PriceInfo]:
    return {
        "AAPL": PriceInfo("AAPL", 150.0, 5.0),
        "MSFT": PriceInfo("MSFT", 300.0, 8.0),
        "XOM": PriceInfo("XOM", 100.0, 3.0),
        "LOW": PriceInfo("LOW", 50.0, 2.0),
    }


def test_build_respects_max_positions() -> None:
    builder = PortfolioBuilder(_cfg())
    entries = builder.build(_candidates(), _prices())
    accepted = [e for e in entries if e.approved_shares > 0]
    assert len(accepted) <= 3


def test_missing_price_rejected() -> None:
    builder = PortfolioBuilder(_cfg())
    cands = [CandidateScore("NOPE", "Tech", 0.99)]
    entries = builder.build(cands, {})
    assert entries[0].decision == "REJECTED"
    assert "prix" in entries[0].decision_reason


def test_accepted_entries_have_positive_weight() -> None:
    builder = PortfolioBuilder(_cfg())
    entries = builder.build(_candidates(), _prices())
    for e in entries:
        if e.decision in ("ACCEPTED", "REDUCED"):
            assert e.target_weight > 0
            assert e.approved_shares >= 1


def test_score_source_is_final_score_sentiment() -> None:
    builder = PortfolioBuilder(_cfg())
    entries = builder.build(_candidates(), _prices())
    for e in entries:
        assert e.score_source == "final_score_sentiment"

