"""Tests unitaires pour risk_management/batch_diagnostics.py.

Couvre ``apply_batch_diagnostics_to_entries`` qui applique exclusion + boost
sur les ``PortfolioEntry`` dans l'étape 11 (Risk).
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
from risk_management.batch_diagnostics import apply_batch_diagnostics_to_entries
from risk_management.models import PortfolioEntry


# ── Helpers ────────────────────────────────────────────────────────

def _entry(
    symbol: str = "AAPL",
    side: str = "buy",
    approved_shares: float = 100.0,
    target_notional: float = 15_000.0,
    target_weight: float = 0.05,
) -> PortfolioEntry:
    """Construit un PortfolioEntry minimal pour les tests."""
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


def _mock_engine_for_risk(
    monkeypatch,
    filters: BatchFilters | None = None,
) -> MagicMock:
    """Mock l'engine et get_batch_filters pour les tests Risk."""
    if filters is None:
        filters = BatchFilters(
            batch_id="test-batch",
            batch_started_at=None,
            prefer=frozenset({"AAPL", "MSFT"}),
            exclude_long=frozenset({"TSLA"}),
            exclude_short=frozenset({"GME"}),
            all_diagnostics=pd.DataFrame({
                "symbol": ["AAPL", "MSFT", "TSLA", "GME"],
                "rank_type": [RANK_TYPE_TOP, RANK_TYPE_TOP, RANK_TYPE_BOTTOM, RANK_TYPE_ZERO_SHORT],
                "rank_position": [1, 2, 1, None],
            }),
        )

    monkeypatch.setattr(
        "risk_management.batch_diagnostics.get_batch_filters",
        lambda engine, **kwargs: filters,
    )
    monkeypatch.setattr(
        "risk_management.batch_diagnostics._load_config_defaults",
        lambda: {"prefer_sizing_multiplier": 1.2, "prefer_top_n": 10},
    )

    return MagicMock()


# ── Tests ──────────────────────────────────────────────────────────

class TestApplyBatchDiagnosticsToEntries:

    def test_excludes_long_entry(self, monkeypatch):
        engine = _mock_engine_for_risk(monkeypatch)
        entries = [
            _entry("AAPL", side="buy"),
            _entry("TSLA", side="buy"),
            _entry("MSFT", side="buy"),
        ]
        result, excluded, boosted, batch_id = apply_batch_diagnostics_to_entries(
            entries, engine,
        )
        assert len(result) == 2
        assert excluded == 1
        assert boosted == 2  # AAPL et MSFT sont dans prefer
        assert batch_id == "test-batch"
        assert {e.symbol for e in result} == {"AAPL", "MSFT"}

    def test_excludes_short_entry(self, monkeypatch):
        engine = _mock_engine_for_risk(monkeypatch)
        entries = [
            _entry("AAPL", side="sell"),
            _entry("GME", side="sell"),
        ]
        result, excluded, boosted, batch_id = apply_batch_diagnostics_to_entries(
            entries, engine,
        )
        assert len(result) == 1
        assert excluded == 1
        assert result[0].symbol == "AAPL"

    def test_no_exclusion_when_no_batch_id(self, monkeypatch):
        empty_filters = BatchFilters(
            batch_id="", batch_started_at=None,
            prefer=frozenset(), exclude_long=frozenset(),
            exclude_short=frozenset(), all_diagnostics=pd.DataFrame(),
        )
        engine = _mock_engine_for_risk(monkeypatch, filters=empty_filters)
        entries = [_entry("TSLA", side="buy")]
        result, excluded, boosted, batch_id = apply_batch_diagnostics_to_entries(
            entries, engine,
        )
        assert len(result) == 1
        assert excluded == 0
        assert boosted == 0
        assert batch_id is None

    def test_empty_entries_unchanged(self, monkeypatch):
        engine = _mock_engine_for_risk(monkeypatch)
        result, excluded, boosted, batch_id = apply_batch_diagnostics_to_entries(
            [], engine,
        )
        assert result == []
        assert excluded == 0
        assert boosted == 0

    def test_boosts_prefer_approved_shares(self, monkeypatch):
        engine = _mock_engine_for_risk(monkeypatch)
        entries = [_entry("AAPL", side="buy", approved_shares=100.0, target_notional=15_000.0)]
        result, excluded, boosted, _ = apply_batch_diagnostics_to_entries(
            entries, engine, prefer_multiplier=1.5,
        )
        assert excluded == 0
        assert boosted == 1
        assert result[0].approved_shares == 150.0  # 100 × 1.5
        assert result[0].target_notional == 22_500.0  # 15000 × 1.5

    def test_boosts_only_prefer_symbols(self, monkeypatch):
        engine = _mock_engine_for_risk(monkeypatch)
        entries = [
            _entry("AAPL", side="buy", approved_shares=100.0),
            _entry("GOOG", side="buy", approved_shares=50.0),
        ]
        result, excluded, boosted, _ = apply_batch_diagnostics_to_entries(
            entries, engine, prefer_multiplier=2.0,
        )
        assert excluded == 0
        assert boosted == 1  # seul AAPL dans prefer
        aapl = next(e for e in result if e.symbol == "AAPL")
        goog = next(e for e in result if e.symbol == "GOOG")
        assert aapl.approved_shares == 200.0
        assert goog.approved_shares == 50.0  # inchangé

    def test_no_boost_when_multiplier_is_one(self, monkeypatch):
        engine = _mock_engine_for_risk(monkeypatch)
        entries = [_entry("AAPL", side="buy", approved_shares=100.0)]
        result, excluded, boosted, _ = apply_batch_diagnostics_to_entries(
            entries, engine, prefer_multiplier=1.0,
        )
        assert excluded == 0
        assert boosted == 0
        assert result[0].approved_shares == 100.0  # inchangé

    def test_prefer_top_n_respected(self, monkeypatch):
        """Seuls les top N sont boostés."""
        filters = BatchFilters(
            batch_id="test",
            batch_started_at=None,
            prefer=frozenset({"A", "B", "C", "D", "E"}),
            exclude_long=frozenset(),
            exclude_short=frozenset(),
            all_diagnostics=pd.DataFrame({
                "symbol": ["A", "B", "C", "D", "E"],
                "rank_type": [RANK_TYPE_TOP] * 5,
                "rank_position": [1, 2, 3, 4, 5],
            }),
        )
        engine = _mock_engine_for_risk(monkeypatch, filters=filters)

        entries = [
            _entry("A", side="buy", approved_shares=100.0),
            _entry("B", side="buy", approved_shares=100.0),
            _entry("C", side="buy", approved_shares=100.0),
            _entry("D", side="buy", approved_shares=100.0),
            _entry("E", side="buy", approved_shares=100.0),
        ]
        result, excluded, boosted, _ = apply_batch_diagnostics_to_entries(
            entries, engine, prefer_multiplier=2.0, prefer_top_n=2,
        )
        assert excluded == 0
        assert boosted == 2  # seuls A et B
        for e in result:
            if e.symbol in ("A", "B"):
                assert e.approved_shares == 200.0
            else:
                assert e.approved_shares == 100.0

    def test_combined_exclusion_and_boost(self, monkeypatch):
        """Un symbole exclu n'est PAS boosté même s'il est prefer."""
        filters = BatchFilters(
            batch_id="test",
            batch_started_at=None,
            prefer=frozenset({"TSLA", "AAPL"}),
            exclude_long=frozenset({"TSLA"}),
            exclude_short=frozenset(),
            all_diagnostics=pd.DataFrame({
                "symbol": ["TSLA", "AAPL"],
                "rank_type": [RANK_TYPE_TOP, RANK_TYPE_TOP],
                "rank_position": [1, 2],
            }),
        )
        engine = _mock_engine_for_risk(monkeypatch, filters=filters)

        entries = [
            _entry("TSLA", side="buy", approved_shares=100.0),
            _entry("AAPL", side="buy", approved_shares=100.0),
        ]
        result, excluded, boosted, _ = apply_batch_diagnostics_to_entries(
            entries, engine, prefer_multiplier=2.0,
        )
        assert excluded == 1  # TSLA exclu
        assert boosted == 1  # seul AAPL boosté
        assert len(result) == 1
        assert result[0].symbol == "AAPL"
        assert result[0].approved_shares == 200.0

    def test_side_case_insensitive(self, monkeypatch):
        engine = _mock_engine_for_risk(monkeypatch)
        entries = [
            _entry("TSLA", side="LONG"),
            _entry("GME", side="SELL"),
            _entry("AAPL", side="buy"),
        ]
        result, excluded, boosted, _ = apply_batch_diagnostics_to_entries(
            entries, engine,
        )
        assert excluded == 2  # TSLA (exclude_long) + GME (exclude_short)
        assert len(result) == 1
        assert result[0].symbol == "AAPL"

    def test_exception_returns_unchanged(self, monkeypatch):
        """Si get_batch_filters lève une exception, entries inchangées."""
        monkeypatch.setattr(
            "risk_management.batch_diagnostics.get_batch_filters",
            MagicMock(side_effect=RuntimeError("DB down")),
        )
        engine = MagicMock()
        entries = [_entry("AAPL", side="buy")]
        result, excluded, boosted, batch_id = apply_batch_diagnostics_to_entries(
            entries, engine,
        )
        assert len(result) == 1
        assert excluded == 0
        assert boosted == 0
        assert batch_id is None
