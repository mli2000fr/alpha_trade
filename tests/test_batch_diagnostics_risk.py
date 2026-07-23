"""Tests unitaires pour risk_management/batch_diagnostics.py.

Couvre :
- ``boost_candidate_scores`` : boost p_side/p_long/p_short AVANT sizing
- ``apply_batch_diagnostics_to_entries`` : exclusion uniquement
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from modelFactory.batch_diagnostics import (
    RANK_TYPE_BOTTOM,
    RANK_TYPE_TOP,
    RANK_TYPE_ZERO_SHORT,
    BatchFilters,
)
from risk_management.batch_diagnostics import (
    apply_batch_diagnostics_to_entries,
    boost_candidate_scores,
)
from risk_management.models import PortfolioEntry


# ── Helpers ────────────────────────────────────────────────────────

def _entry(
    symbol: str = "AAPL",
    side: str = "buy",
    approved_shares: float = 100.0,
    target_notional: float = 15_000.0,
    target_weight: float = 0.05,
) -> PortfolioEntry:
    return PortfolioEntry(
        symbol=symbol,
        sector="Tech",
        entry_price=150.0,
        score_used=0.8,
        score_source="ml",
        atr_20=5.0,
        proposed_shares=approved_shares,
        approved_shares=approved_shares,
        target_notional=target_notional,
        target_weight=target_weight,
        decision="ACCEPTED",  # type: ignore[arg-type]
        decision_reason="ok",
        side=side,
    )


class _FakeCandidate:
    """Simule un MLRankedCandidate pour les tests de boost_candidate_scores."""

    def __init__(
        self,
        symbol: str,
        side: str = "long",
        p_side: float = 0.6,
        p_long: float = 0.5,
        p_short: float = 0.2,
    ):
        self.symbol = symbol
        self.side = side
        self.p_side = p_side
        self.p_long = p_long
        self.p_short = p_short


def _mock_filters(monkeypatch, **kwargs) -> MagicMock:
    """Mock get_batch_filters pour les tests Risk."""
    filters = BatchFilters(
        batch_id="test-batch",
        batch_started_at=None,
        prefer=kwargs.get("prefer", frozenset({"AAPL", "MSFT"})),
        exclude_long=kwargs.get("exclude_long", frozenset({"TSLA"})),
        exclude_short=kwargs.get("exclude_short", frozenset({"GME"})),
        all_diagnostics=kwargs.get("all_diagnostics", pd.DataFrame({
            "symbol": ["AAPL", "MSFT"],
            "rank_type": [RANK_TYPE_TOP, RANK_TYPE_TOP],
            "rank_position": [1, 2],
        })),
        batch_comment=kwargs.get("batch_comment"),
    )
    monkeypatch.setattr(
        "risk_management.batch_diagnostics.get_batch_filters",
        lambda engine, **kw: filters,
    )
    monkeypatch.setattr(
        "risk_management.batch_diagnostics._load_config_defaults",
        lambda: {"prefer_sizing_multiplier": 1.5, "prefer_top_n": 10},
    )
    return MagicMock()


# ── Tests boost_candidate_scores ────────────────────────────────────

class TestBoostCandidateScores:

    def test_boosts_p_side_for_prefer(self, monkeypatch):
        engine = _mock_filters(monkeypatch)
        candidates = [
            _FakeCandidate("AAPL", side="long", p_side=0.5, p_long=0.4),
            _FakeCandidate("GOOG", side="long", p_side=0.6, p_long=0.5),
        ]
        boosted, batch_id = boost_candidate_scores(candidates, engine)
        assert boosted == 1
        assert batch_id == "test-batch"
        assert candidates[0].p_side == pytest.approx(0.75)  # 0.5 × 1.5
        assert candidates[1].p_side == 0.6  # inchangé

    def test_boosts_p_long_for_long_candidate(self, monkeypatch):
        engine = _mock_filters(monkeypatch)
        candidates = [_FakeCandidate("AAPL", side="long", p_side=0.5, p_long=0.4)]
        boost_candidate_scores(candidates, engine)
        assert candidates[0].p_long == pytest.approx(0.6)  # 0.4 × 1.5

    def test_boosts_p_short_for_short_candidate(self, monkeypatch):
        engine = _mock_filters(monkeypatch)
        candidates = [_FakeCandidate("AAPL", side="short", p_side=0.5, p_short=0.3)]
        boost_candidate_scores(candidates, engine)
        assert candidates[0].p_short == pytest.approx(0.45)  # 0.3 × 1.5

    def test_clips_at_one(self, monkeypatch):
        engine = _mock_filters(monkeypatch)
        candidates = [_FakeCandidate("AAPL", side="long", p_side=0.9, p_long=0.8)]
        boost_candidate_scores(candidates, engine)
        assert candidates[0].p_side == 1.0
        assert candidates[0].p_long == 1.0

    def test_no_boost_when_prefer_empty(self, monkeypatch):
        engine = _mock_filters(monkeypatch, prefer=frozenset())
        candidates = [_FakeCandidate("AAPL", side="long", p_side=0.5)]
        boosted, _ = boost_candidate_scores(candidates, engine)
        assert boosted == 0

    def test_no_boost_empty_candidates(self, monkeypatch):
        engine = _mock_filters(monkeypatch)
        boosted, batch_id = boost_candidate_scores([], engine)
        assert boosted == 0
        assert batch_id is None

    def test_no_boost_when_no_batch(self, monkeypatch):
        monkeypatch.setattr(
            "risk_management.batch_diagnostics.get_batch_filters",
            lambda engine, **kw: BatchFilters(
                batch_id="", batch_started_at=None,
                prefer=frozenset(), exclude_long=frozenset(),
                exclude_short=frozenset(), all_diagnostics=pd.DataFrame(),
            ),
        )
        engine = MagicMock()
        candidates = [_FakeCandidate("AAPL")]
        boosted, batch_id = boost_candidate_scores(candidates, engine)
        assert boosted == 0
        assert batch_id is None


# ── Tests apply_batch_diagnostics_to_entries (exclusion only) ───────

class TestApplyBatchDiagnosticsToEntries:

    def test_excludes_long_entry(self, monkeypatch):
        engine = _mock_filters(monkeypatch)
        entries = [
            _entry("AAPL", side="buy"),
            _entry("TSLA", side="buy"),
            _entry("MSFT", side="buy"),
        ]
        result, excluded, batch_id = apply_batch_diagnostics_to_entries(entries, engine)
        assert len(result) == 2
        assert excluded == 1
        assert batch_id == "test-batch"
        assert {e.symbol for e in result} == {"AAPL", "MSFT"}

    def test_excludes_short_entry(self, monkeypatch):
        engine = _mock_filters(monkeypatch)
        entries = [_entry("AAPL", side="sell"), _entry("GME", side="sell")]
        result, excluded, _ = apply_batch_diagnostics_to_entries(entries, engine)
        assert len(result) == 1
        assert excluded == 1
        assert result[0].symbol == "AAPL"

    def test_no_exclusion_when_no_batch(self, monkeypatch):
        monkeypatch.setattr(
            "risk_management.batch_diagnostics.get_batch_filters",
            lambda engine, **kw: BatchFilters(
                batch_id="", batch_started_at=None,
                prefer=frozenset(), exclude_long=frozenset({"TSLA"}),
                exclude_short=frozenset(), all_diagnostics=pd.DataFrame(),
            ),
        )
        engine = MagicMock()
        entries = [_entry("TSLA", side="buy")]
        result, excluded, batch_id = apply_batch_diagnostics_to_entries(entries, engine)
        assert len(result) == 1
        assert excluded == 0
        assert batch_id is None

    def test_empty_entries_unchanged(self, monkeypatch):
        engine = _mock_filters(monkeypatch)
        result, excluded, _ = apply_batch_diagnostics_to_entries([], engine)
        assert result == []
        assert excluded == 0

    def test_boost_no_longer_applied(self, monkeypatch):
        """Vérifie que le boost N'EST PLUS fait dans cette fonction."""
        engine = _mock_filters(monkeypatch, prefer=frozenset({"AAPL"}))
        entries = [_entry("AAPL", side="buy", approved_shares=100.0, target_notional=15_000.0)]
        result, excluded, _ = apply_batch_diagnostics_to_entries(entries, engine)
        assert excluded == 0
        assert result[0].approved_shares == 100.0  # INCHANGÉ
        assert result[0].target_notional == 15_000.0  # INCHANGÉ

    def test_side_case_insensitive(self, monkeypatch):
        engine = _mock_filters(monkeypatch)
        entries = [
            _entry("TSLA", side="LONG"),
            _entry("GME", side="SELL"),
            _entry("AAPL", side="buy"),
        ]
        result, excluded, _ = apply_batch_diagnostics_to_entries(entries, engine)
        assert excluded == 2
        assert len(result) == 1
        assert result[0].symbol == "AAPL"
