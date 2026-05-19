"""Tests des helpers selector consommant ``MarketRegimeSnapshot`` (Axe E)."""
from __future__ import annotations

from datetime import date

import pandas as pd

from selector.regime_filters import (
    apply_buyback_blackout_to_candidates,
    apply_earnings_shield_to_candidates,
    apply_full_regime_to_candidates,
    apply_yield_filter_to_candidates,
)
from service.market.models import MarketRegimeSnapshot


def _df():
    return pd.DataFrame({
        "symbol": ["AAPL", "MSFT", "GOOG", "JPM"],
        "sector": ["Technology", "Technology", "Tech", "Financials"],
        "score": [1.0, 0.8, 0.6, 0.4],
    })


def test_earnings_shield_strict_block_removes_rows():
    snap = MarketRegimeSnapshot(
        trade_date=date(2025, 5, 1),
        earnings_shielded_symbols={"AAPL": "strict_block", "MSFT": "strict_block"},
    )
    out = apply_earnings_shield_to_candidates(_df(), snap)
    assert set(out["symbol"]) == {"GOOG", "JPM"}


def test_earnings_shield_negative_score_overrides_score():
    snap = MarketRegimeSnapshot(
        trade_date=date(2025, 5, 1),
        earnings_shielded_symbols={"AAPL": "negative_score"},
        earnings_negative_score_value=-1.0,
    )
    out = apply_earnings_shield_to_candidates(_df(), snap)
    aapl = out.loc[out["symbol"] == "AAPL"].iloc[0]
    assert aapl["score"] == -1.0


def test_earnings_shield_normalizes_snapshot_symbol_case():
    snap = MarketRegimeSnapshot(
        trade_date=date(2025, 5, 1),
        earnings_shielded_symbols={" aapl ": "strict_block"},
    )
    out = apply_earnings_shield_to_candidates(_df(), snap)
    assert "AAPL" not in set(out["symbol"])


def test_buyback_blackout_multiplies_score():
    snap = MarketRegimeSnapshot(
        trade_date=date(2025, 5, 1),
        buyback_blackout_symbols={"AAPL": 0.7},
    )
    out = apply_buyback_blackout_to_candidates(_df(), snap)
    assert out.loc[out["symbol"] == "AAPL", "score"].iloc[0] == 0.7


def test_yield_filter_excludes_blocked_sectors():
    snap = MarketRegimeSnapshot(
        trade_date=date(2025, 5, 1),
        blocked_sectors=("Technology", "Tech"),
    )
    out = apply_yield_filter_to_candidates(_df(), snap)
    assert set(out["symbol"]) == {"JPM"}


def test_yield_filter_normalizes_sector_case_and_whitespace():
    snap = MarketRegimeSnapshot(
        trade_date=date(2025, 5, 1),
        blocked_sectors=(" technology ", "TECH"),
    )
    out = apply_yield_filter_to_candidates(_df(), snap)
    assert set(out["symbol"]) == {"JPM"}


def test_buyback_blackout_is_noop_when_symbol_column_missing():
    snap = MarketRegimeSnapshot(
        trade_date=date(2025, 5, 1),
        buyback_blackout_symbols={"AAPL": 0.7},
    )
    df = pd.DataFrame({"ticker": ["AAPL"], "score": [1.0]})
    out = apply_buyback_blackout_to_candidates(df, snap)
    pd.testing.assert_frame_equal(out, df)


def test_full_regime_pipeline_combines_all_filters():
    snap = MarketRegimeSnapshot(
        trade_date=date(2025, 5, 1),
        blocked_sectors=("Technology",),
        earnings_shielded_symbols={"GOOG": "strict_block"},
        buyback_blackout_symbols={"JPM": 0.5},
    )
    out = apply_full_regime_to_candidates(_df(), snap)
    # Technology -> AAPL/MSFT exclus ; GOOG bloqué earnings ; JPM blackout 0.5
    assert set(out["symbol"]) == {"JPM"}
    assert out.loc[out["symbol"] == "JPM", "score"].iloc[0] == 0.4 * 0.5


def test_filters_passthrough_when_snapshot_none():
    df = _df()
    out = apply_full_regime_to_candidates(df, None)
    pd.testing.assert_frame_equal(out, df)

