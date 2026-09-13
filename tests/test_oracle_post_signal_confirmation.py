from __future__ import annotations

import numpy as np
import pandas as pd

from modelFactory.oracle_post_signal_confirmation import (
    E9Config,
    attach_confirmation_paths,
    build_prequential_decisions,
    evaluate_verdict,
    prepare_price_panel,
    select_threshold,
    summarize_sides,
)


def _bars(symbols=("AAA", "BBB", "SPY"), periods: int = 80) -> pd.DataFrame:
    rows = []
    for symbol_index, symbol in enumerate(symbols):
        for day, current in enumerate(pd.bdate_range("2024-01-02", periods=periods)):
            close = 100 + symbol_index * 10 + day * (1 if symbol != "BBB" else -0.4)
            rows.append({"symbol": symbol, "date": current, "open": close - 0.1,
                         "close": close, "adj_close": close})
    return pd.DataFrame(rows)


def test_price_panel_uses_close_then_next_open_without_lookahead() -> None:
    row = prepare_price_panel(_bars(("AAA",)), (1, 2, 3, 5)).iloc[0]
    assert row["reveal_date_d2"] == pd.Timestamp("2024-01-04")
    assert row["delayed_entry_date_d2"] == pd.Timestamp("2024-01-05")
    assert row["terminal_date"] == pd.Timestamp("2024-01-31")
    assert row["signal_absolute_d2"] == row["reveal_close_d2"] / row["px_close"] - 1


def test_attach_paths_builds_absolute_spy_and_sector_signals() -> None:
    config = E9Config(bootstrap_samples=10)
    prices = prepare_price_panel(_bars(("AAA", "BBB")), config.delays)
    benchmark = prepare_price_panel(_bars(("SPY",)), config.delays)
    dates = pd.bdate_range("2024-01-02", periods=10)
    oracle = pd.DataFrame({"date": np.repeat(dates, 2),
                           "symbol": ["AAA", "BBB"] * len(dates),
                           "mh0": True, "fold_h20": "2024-01-02"})
    events = attach_confirmation_paths(oracle, prices, benchmark,
                                       {"AAA": "X", "BBB": "X"}, config)
    assert np.isfinite(events.iloc[0]["signal_spy_relative_d2"])
    assert np.isfinite(events.iloc[0]["signal_sector_relative_d2"])
    assert events.iloc[0]["delayed_entry_date_d2"] > events.iloc[0]["reveal_date_d2"]


def test_attach_paths_replaces_preexisting_h20_path_columns() -> None:
    config = E9Config(bootstrap_samples=10)
    prices = prepare_price_panel(_bars(("AAA", "BBB")), config.delays)
    benchmark = prepare_price_panel(_bars(("SPY",)), config.delays)
    oracle = pd.DataFrame({"date": [pd.Timestamp("2024-01-02")], "symbol": ["AAA"],
                           "mh0": [True], "fold_h20": ["2024-01-02"],
                           "terminal_exit_open": [-999.0]})
    events = attach_confirmation_paths(oracle, prices, benchmark,
                                       {"AAA": "X", "BBB": "X"}, config)
    assert "terminal_exit_open_x" not in events
    assert events.iloc[0]["terminal_exit_open"] > 0


def test_threshold_is_selected_only_from_supplied_history() -> None:
    config = E9Config(delays=(1,), thresholds=(0.0, 0.01), default_threshold=0.0,
                      minimum_training_events=2, minimum_training_coverage=0.25,
                      primary_delay=1)
    history = pd.DataFrame({"date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]),
                            "signal_absolute_d1": [0.005, -0.005, 0.02, -0.02],
                            "future_unsigned_d1": [-0.01, 0.01, 0.03, -0.03],
                            "delayed_entry_open_d1": 100.0, "terminal_exit_open": 101.0})
    threshold, diagnostics = select_threshold(history, basis="absolute", delay=1, config=config)
    assert threshold == 0.01
    assert len(diagnostics) == 2


def test_threshold_selection_accounts_for_costs() -> None:
    config = E9Config(delays=(1,), thresholds=(0.0,), primary_delay=1,
                      minimum_training_events=1, commission_bps=1.0, slippage_bps=2.0)
    history = pd.DataFrame({"date": [pd.Timestamp("2024-01-02")],
                            "signal_absolute_d1": [0.01], "future_unsigned_d1": [0.02],
                            "delayed_entry_open_d1": [100.0], "terminal_exit_open": [102.0]})
    _, diagnostics = select_threshold(history, basis="absolute", delay=1, config=config)
    assert diagnostics[0]["training_daily_mean"] == 0.02 - config.round_trip_cost


def test_prequential_first_fold_uses_default_and_later_fold_uses_prior_only() -> None:
    config = E9Config(delays=(1,), thresholds=(0.0,), default_threshold=0.0,
                      minimum_training_events=2, primary_delay=1, bootstrap_samples=10)
    rows = []
    for fold, start in (("f1", "2024-01-02"), ("f2", "2024-02-01")):
        for index, current in enumerate(pd.bdate_range(start, periods=3)):
            rows.append({"date": current, "symbol": f"S{index}", "fold_h20": fold,
                         "signal_absolute_d1": 0.01, "signal_spy_relative_d1": 0.01,
                         "signal_sector_relative_d1": 0.01, "future_unsigned_d1": 0.02,
                         "delayed_entry_open_d1": 100.0, "terminal_exit_open": 102.0})
    decisions, thresholds = build_prequential_decisions(pd.DataFrame(rows), config)
    first = thresholds[(thresholds["basis"].eq("absolute")) & thresholds["evaluation_fold"].eq("f1")]
    second = thresholds[(thresholds["basis"].eq("absolute")) & thresholds["evaluation_fold"].eq("f2")]
    assert first.iloc[0]["threshold_source"] == "default_no_history"
    assert second.iloc[0]["threshold_source"] == "prior_oof_folds"
    assert not decisions.empty


def test_verdict_never_authorizes_production() -> None:
    config = E9Config()
    rows = []
    for basis in ("absolute", "spy_relative", "sector_relative"):
        for delay in config.delays:
            rows.append({"policy": f"{basis}_d{delay}", "trades": 1000, "coverage": 0.5,
                         "daily_mean_directional_net": 0.01, "paired_daily_delta_vs_long": 0.01,
                         "paired_daily_delta_ci95_low": 0.001, "positive_fold_ratio": 0.8,
                         "positive_semester_ratio": 0.8})
    verdict = evaluate_verdict(pd.DataFrame(rows), config)
    assert verdict["verdict"] == "GO_RESEARCH_PRIMARY"
    assert verdict["promotion_authorized"] is False


def test_side_summary_exposes_short_underlying_drift() -> None:
    config = E9Config(delays=(1,), primary_delay=1)
    decisions = pd.DataFrame({
        "basis": ["absolute", "absolute"], "delay": [1, 1],
        "direction": ["LONG", "SHORT"],
        "date": pd.to_datetime(["2024-01-02", "2024-01-02"]),
        "directional_net": [0.0194, -0.0206],
        "signal_absolute_d1": [0.01, -0.01],
        "future_unsigned_d1": [0.02, 0.02],
    })
    summary = summarize_sides(decisions, config)
    short = summary[summary["direction"].eq("SHORT")].iloc[0]
    assert short["mean_underlying_future_return"] == 0.02
    assert short["mean_directional_net"] < 0
