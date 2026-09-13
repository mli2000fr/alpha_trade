from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from modelFactory.directional_alpha_attribution import (
    DEFAULT_PROTOCOL,
    _sector_neutral_leg,
    build_attribution_cohorts,
    build_ex_ante_context,
    classify_attribution,
    load_locked_protocol,
)


def _protocol() -> dict:
    return load_locked_protocol(DEFAULT_PROTOCOL)


def _bars(symbols: tuple[str, ...], periods: int = 430) -> pd.DataFrame:
    dates = pd.bdate_range("2019-01-02", periods=periods)
    rows = []
    for symbol_index, symbol in enumerate(symbols):
        returns = 0.0002 + symbol_index * 0.00005 + 0.001 * np.sin(np.arange(periods) / 17)
        prices = 50 * np.cumprod(1 + returns)
        for day, price in zip(dates, prices, strict=True):
            rows.append({"symbol": symbol, "date": day, "close": price, "adj_close": price})
    return pd.DataFrame(rows)


def test_protocol_is_locked_and_cannot_authorize_live() -> None:
    protocol = _protocol()
    assert protocol["oracle_used"] is False
    assert protocol["validation_class"] == "post_discovery_attribution_not_oos"
    assert not protocol["decision_policy"]["production_promotion_authorized"]
    assert not protocol["decision_policy"]["regime_filter_activation_authorized"]


def test_changed_protocol_is_rejected(tmp_path: Path) -> None:
    protocol = _protocol()
    protocol["beta"]["lookback_sessions"] = 63
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(protocol), encoding="utf-8")
    with pytest.raises(ValueError, match="changé après verrouillage"):
        load_locked_protocol(changed)


def test_ex_ante_beta_does_not_change_when_future_prices_change() -> None:
    protocol = _protocol()
    bars = _bars(("AAA", "BBB"))
    benchmark = _bars(("SPY",))
    date_j = pd.Timestamp(bars["date"].sort_values().unique()[300])
    first, _ = build_ex_ante_context(bars, benchmark, protocol)
    changed = bars.copy()
    changed.loc[changed["date"] > date_j, "close"] *= 2
    changed.loc[changed["date"] > date_j, "adj_close"] *= 2
    second, _ = build_ex_ante_context(changed, benchmark, protocol)
    left = first[first["date"].eq(date_j)].sort_values("symbol")["beta_ex_ante"]
    right = second[second["date"].eq(date_j)].sort_values("symbol")["beta_ex_ante"]
    np.testing.assert_allclose(left, right, equal_nan=True)


def test_sector_neutral_leg_preserves_universe_sector_weights() -> None:
    protocol = _protocol()
    rows = []
    for sector, size, base_return in (("A", 20, 0.02), ("B", 80, 0.10)):
        for index in range(size):
            rows.append({
                "symbol": f"{sector}{index}", "sector": sector,
                "score_residual_momentum_120_10": float(index),
                "future_return_h120": base_return + index / 10_000,
                "beta_ex_ante": 1.0,
            })
    result = _sector_neutral_leg(pd.DataFrame(rows), protocol)
    assert result is not None
    selected_return, beta, universe_return, selected_count = result
    assert beta == pytest.approx(1.0)
    assert selected_count == 20
    assert selected_return > universe_return


def test_attribution_cohort_contains_beta_and_sector_neutral_returns() -> None:
    protocol = _protocol()
    rows = []
    for index in range(100):
        score = -1 + 2 * index / 99
        stock_return = 0.02 + score * 0.05
        rows.append({
            "date": pd.Timestamp("2024-01-02"), "symbol": f"S{index:03d}",
            "sector": "A" if index < 50 else "B", "market_eligible": True,
            "score_residual_momentum_120_10": score,
            "future_return_h120": stock_return,
            "future_excess_h120": stock_return - 0.01,
            "beta_ex_ante": 1.2, "market_regime": "bull_calm",
        })
    cohorts = build_attribution_cohorts(pd.DataFrame(rows), protocol)
    assert len(cohorts) == 1
    assert cohorts.loc[0, "selected_symbols"] == 20
    assert cohorts.loc[0, "raw_portfolio_beta"] == pytest.approx(1.2)
    assert cohorts.loc[0, "raw_excess_vs_universe"] > 0
    assert cohorts.loc[0, "combined_beta_sector_net"] > 0


def _classification_frame(middle_value: float = 0.02) -> pd.DataFrame:
    dates = list(pd.date_range("2018-07-01", "2020-12-01", periods=30))
    dates += list(pd.date_range("2021-01-01", "2022-12-01", periods=30))
    dates += list(pd.date_range("2023-01-01", "2025-12-01", periods=30))
    rows = []
    for day in dates:
        value = middle_value if 2021 <= day.year <= 2022 else 0.02
        rows.append({
            "date": day, "market_regime": "bull_calm",
            "raw_long_net": value + 0.03,
            "raw_excess_vs_universe": value,
            "raw_excess_vs_spy": value,
            "beta_hedged_net": value,
            "sector_neutral_long_net": value + 0.02,
            "sector_neutral_excess_vs_universe": value,
            "combined_beta_sector_net": value,
            "raw_portfolio_beta": 1.0, "sector_neutral_beta": 1.0,
            "market_component": 0.01, "raw_specific_component": value,
        })
    return pd.DataFrame(rows)


def test_structural_classification_requires_all_time_blocks() -> None:
    result = classify_attribution(_classification_frame(), _protocol())
    assert result["verdict"] == "STRUCTURAL_SELECTION_CANDIDATE"
    assert result["all_time_blocks_combined_positive"]

