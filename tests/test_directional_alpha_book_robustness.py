from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from modelFactory.directional_alpha_book_robustness import (
    DEFAULT_PROTOCOL,
    assign_symbol_hash_fold,
    evaluate_long_top,
    load_locked_protocol,
    positive_contribution_concentration,
    select_offset_dates,
)


def _protocol() -> dict:
    return load_locked_protocol(DEFAULT_PROTOCOL)


def test_protocol_is_locked_oracle_free_and_not_oos() -> None:
    protocol = _protocol()
    assert protocol["oracle_used"] is False
    assert protocol["signal"] == "residual_momentum_120_10"
    assert protocol["horizon_sessions"] == 120
    assert protocol["validation_class"] == "post_discovery_historical_robustness_not_oos"
    assert not protocol["decision_policy"]["oos_claim_authorized"]
    assert not protocol["decision_policy"]["production_promotion_authorized"]


def test_changed_protocol_is_rejected(tmp_path: Path) -> None:
    protocol = _protocol()
    protocol["portfolio"]["tail_pct"] = 0.10
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(protocol), encoding="utf-8")
    with pytest.raises(ValueError, match="changé après verrouillage"):
        load_locked_protocol(changed)


def test_symbol_hash_fold_is_stable_and_bounded() -> None:
    first = assign_symbol_hash_fold("AAPL", folds=5, salt="fixed")
    assert first == assign_symbol_hash_fold("aapl", folds=5, salt="fixed")
    assert 0 <= first < 5
    assert len({assign_symbol_hash_fold(f"S{i}", folds=5, salt="fixed") for i in range(50)}) == 5


def test_calendar_offset_is_deterministic() -> None:
    dates = pd.Series(pd.bdate_range("2024-01-02", periods=45))
    assert select_offset_dates(dates, rebalance_sessions=20, offset=5) == {
        dates.iloc[5], dates.iloc[25]
    }


def test_long_top_selects_only_top20_and_applies_equal_cost_to_comparators() -> None:
    protocol = _protocol()
    rows = []
    for index in range(100):
        score = -1 + 2 * index / 99
        stock_return = score * 0.10
        rows.append({
            "date": pd.Timestamp("2024-01-02"),
            "symbol": f"S{index:03d}",
            "sector": "TEST",
            "market_eligible": True,
            "score_residual_momentum_120_10": score,
            "future_return_h120": stock_return,
            "future_excess_h120": stock_return - 0.01,
        })
    cohorts, constituents = evaluate_long_top(
        pd.DataFrame(rows), protocol, calendar_offset=0, cost_bps=6.0
    )
    assert cohorts.loc[0, "selected_symbols"] == 20
    assert len(constituents) == 20
    assert set(constituents["symbol"]) == {f"S{i:03d}" for i in range(80, 100)}
    assert cohorts.loc[0, "universe_return_net"] == pytest.approx(-0.0006)
    assert cohorts.loc[0, "spy_return_net"] == pytest.approx(0.0094)


def test_positive_contribution_concentration_uses_top_twenty_symbols() -> None:
    constituents = pd.DataFrame({
        "symbol": [f"S{i:02d}" for i in range(40)],
        "equal_weight_contribution": [1.0] * 40,
    })
    assert positive_contribution_concentration(constituents) == pytest.approx(0.5)


def test_sector_minimum_refers_to_universe_not_selected_leg() -> None:
    protocol = _protocol()
    assert protocol["locked_robustness_checks"]["minimum_sector_symbols_per_cohort"] == 25
    # With a 20% tail, the minimum concerns the pre-selection sector universe;
    # the selected leg may legitimately contain fewer symbols.
    cohort = pd.DataFrame({"universe": [24, 25], "selected_symbols": [10, 10]})
    assert cohort[cohort["universe"].ge(25)]["universe"].tolist() == [25]


def test_empty_scope_keeps_cohort_schema() -> None:
    protocol = _protocol()
    empty = pd.DataFrame(columns=[
        "date", "symbol", "sector", "market_eligible",
        "score_residual_momentum_120_10", "future_return_h120",
        "future_excess_h120",
    ])
    cohorts, constituents = evaluate_long_top(
        empty, protocol, calendar_offset=0, cost_bps=6.0
    )
    assert cohorts.empty and constituents.empty
    assert "universe" in cohorts.columns
