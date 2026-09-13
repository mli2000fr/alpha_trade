from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modelFactory.directional_alpha_book import (
    PRIMARY_ALPHA,
    E17Config,
    build_gates,
    build_price_alpha_panel,
    evaluate_alpha,
    select_rebalance_dates,
)


def _bars(symbols: tuple[str, ...] = ("AAA", "BBB"), periods: int = 430) -> pd.DataFrame:
    rows = []
    dates = pd.bdate_range("2022-01-03", periods=periods)
    for symbol_index, symbol in enumerate(symbols):
        growth = 1.0005 + symbol_index * 0.0002
        prices = 50.0 * growth ** np.arange(periods)
        for date, price in zip(dates, prices, strict=True):
            rows.append({
                "symbol": symbol, "date": date, "open": price,
                "high": price * 1.01, "low": price * 0.99,
                "close": price, "adj_close": price, "volume": 1_000_000,
                "is_filled": False,
            })
    return pd.DataFrame(rows)


def _instruments(symbols: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame({
        "symbol": list(symbols), "instrument_eligible": True,
        "instrument_reason": "eligible_equity",
    })


def _sectors(symbols: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame({"symbol": list(symbols), "sector": "TECH"})


def test_alpha_panel_is_oracle_independent_and_uses_future_only_for_labels() -> None:
    symbols = ("AAA", "BBB")
    bars = _bars(symbols)
    benchmark = _bars(("SPY",))
    config = E17Config(min_sector_members=2, horizons=(60, 120))
    panel = build_price_alpha_panel(
        bars, benchmark, _instruments(symbols), _sectors(symbols), config
    )
    assert not any("oracle" in column.lower() for column in panel.columns)
    eligible = panel[panel["market_eligible"]]
    assert eligible["momentum_252_21"].notna().any()
    assert eligible[f"score_{PRIMARY_ALPHA}"].notna().any()
    assert eligible["future_return_h60"].notna().any()


def test_future_price_changes_do_not_change_signal_at_j() -> None:
    symbols = ("AAA", "BBB")
    bars = _bars(symbols)
    benchmark = _bars(("SPY",))
    config = E17Config(min_sector_members=2)
    date_j = pd.Timestamp(bars["date"].sort_values().unique()[300])
    first = build_price_alpha_panel(
        bars, benchmark, _instruments(symbols), _sectors(symbols), config
    )
    changed = bars.copy()
    changed.loc[changed["date"] > date_j, ["open", "close", "adj_close"]] *= 3.0
    second = build_price_alpha_panel(
        changed, benchmark, _instruments(symbols), _sectors(symbols), config
    )
    columns = [f"score_{PRIMARY_ALPHA}", "momentum_252_21", "momentum_120_10"]
    left = first[first["date"].eq(date_j)].sort_values("symbol")[columns]
    right = second[second["date"].eq(date_j)].sort_values("symbol")[columns]
    pd.testing.assert_frame_equal(left.reset_index(drop=True), right.reset_index(drop=True))


def test_rebalance_dates_are_deterministic() -> None:
    dates = pd.Series(pd.bdate_range("2024-01-02", periods=45))
    selected = select_rebalance_dates(dates, E17Config(rebalance_sessions=20))
    assert selected == {dates.iloc[0], dates.iloc[20], dates.iloc[40]}


def test_portfolio_evaluation_uses_both_legs_and_costs() -> None:
    dates = pd.bdate_range("2024-01-02", periods=2)
    rows = []
    for date in dates:
        for index in range(100):
            score = -1 + 2 * index / 99
            rows.append({
                "date": date, "symbol": f"S{index:03d}", "market_eligible": True,
                "score_test": score, "future_excess_h60": score * 0.10,
                "future_return_h60": score * 0.10,
            })
    panel = pd.DataFrame(rows)
    result, daily_ic, cohorts = evaluate_alpha(
        panel, "test", 60,
        E17Config(horizons=(60, 120), rebalance_sessions=1, bootstrap_samples=20),
    )
    assert result["daily_ic_mean"] == pytest.approx(1.0)
    assert result["long_mean_net"] > 0
    assert result["short_mean_net"] > 0
    assert result["long_short_mean_net"] > 0
    assert len(daily_ic) == len(dates)
    assert len(cohorts) == len(dates)


def test_gates_are_bound_to_frozen_primary_and_confirmation() -> None:
    good = {
        "daily_ic_mean": 0.03, "daily_ic_ci95_low": 0.01,
        "long_short_mean_net": 0.02, "long_short_ci95_low": 0.005,
        "long_mean_net": 0.02, "short_mean_net": 0.02,
        "positive_semester_ratio": 0.8,
        "positive_pnl_semester_concentration": 0.2,
        "confirmation_long_short_mean_net": 0.01, "cohorts": 100,
    }
    results = {f"{PRIMARY_ALPHA}_h60": good, f"{PRIMARY_ALPHA}_h120": good}
    assert build_gates(results, E17Config())["go_research"]
    results[f"{PRIMARY_ALPHA}_h120"] = {**good, "daily_ic_mean": -0.01}
    assert not build_gates(results, E17Config())["go_research"]
