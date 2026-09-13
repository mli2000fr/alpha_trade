from __future__ import annotations

import pandas as pd
import pytest

from modelFactory.oracle_pullback_long import (
    E10Config,
    build_confirmation_events,
    choose_discovery_threshold,
    compare_with_delayed_long,
    evaluate_confirmation,
    select_pullbacks,
)


def _events() -> pd.DataFrame:
    rows = []
    for fold_index, start in enumerate(("2023-01-02", "2023-07-03")):
        for date in pd.bdate_range(start, periods=30):
            for symbol_index in range(4):
                pullback = symbol_index < 2
                rows.append({
                    "date": date,
                    "symbol": f"S{symbol_index}",
                    "fold": f"f{fold_index}",
                    "signal_absolute_d1": -0.01 if pullback else 0.01,
                    "delayed_long_net_d1": 0.03 if pullback else -0.01,
                })
    return pd.DataFrame(rows)


def test_pullback_rule_is_long_only_and_uses_negative_signal() -> None:
    selected = select_pullbacks(_events(), 0.005)
    assert set(selected["symbol"]) == {"S0", "S1"}
    assert selected["signal_absolute_d1"].le(-0.005).all()


def test_discovery_threshold_is_selected_from_discovery_only() -> None:
    config = E10Config(
        threshold_grid=(0.0, 0.005, 0.02), minimum_events=10,
        minimum_coverage=0.1, bootstrap_samples=10,
    )
    threshold, grid = choose_discovery_threshold(_events(), config)
    assert threshold == 0.0
    assert len(grid) == 3


def test_comparison_uses_all_oracle_long_on_selected_dates() -> None:
    config = E10Config(minimum_events=10, bootstrap_samples=10)
    metrics, daily, folds, semesters = compare_with_delayed_long(
        _events(), 0.005, config
    )
    assert metrics["mean_selected_long_net"] == pytest.approx(0.03)
    assert metrics["daily_baseline_long_net"] == pytest.approx(0.01)
    assert metrics["daily_delta"] == pytest.approx(0.02)
    assert not daily.empty and len(folds) == 2 and len(semesters) == 2


def test_confirmation_builder_ranks_top20_and_respects_j1_j2_clock() -> None:
    dates = pd.bdate_range("2024-07-10", periods=30)
    predictions = pd.DataFrame([
        {
            "date": date,
            "symbol": f"S{symbol}",
            "proba_extreme": float(symbol),
            "fold_start": "2024-01-01",
        }
        for date in dates[:3]
        for symbol in range(10)
    ])
    bars = pd.DataFrame([
        {
            "date": date,
            "symbol": f"S{symbol}",
            "open": 100.0 + day,
            "close": 100.0 + day,
            "adj_close": 100.0 + day,
        }
        for day, date in enumerate(dates)
        for symbol in range(10)
    ])
    events = build_confirmation_events(
        predictions, bars, start_date="2024-07-10", end_date="2024-07-12",
        config=E10Config(bootstrap_samples=10),
    )
    assert events.groupby("date")["symbol"].count().eq(3).all()
    row = events.iloc[0]
    assert row["reveal_date_d1"] == row["date"] + pd.offsets.BDay(1)
    assert row["delayed_entry_date_d1"] == row["date"] + pd.offsets.BDay(2)


def test_confirmation_rejects_serving_rows_without_oof_fold() -> None:
    predictions = pd.DataFrame({
        "date": ["2024-07-10"], "symbol": ["AAA"], "proba_extreme": [0.9],
        "fold_start": [None],
    })
    bars = pd.DataFrame({
        "date": pd.bdate_range("2024-07-10", periods=25), "symbol": "AAA",
        "open": 100.0, "close": 100.0, "adj_close": 100.0,
    })
    events = build_confirmation_events(
        predictions, bars, start_date="2024-07-10", end_date="2024-07-10",
        config=E10Config(bootstrap_samples=10),
    )
    assert events.empty


def test_verdict_never_authorizes_production() -> None:
    config = E10Config(minimum_events=10)
    metrics = {
        "trades": 100, "coverage": 0.5, "daily_selected_long_net": 0.01,
        "daily_delta": 0.005, "daily_delta_ci95_low": 0.001,
        "positive_fold_ratio": 0.8, "positive_semester_ratio": 0.8,
        "daily_p05_delta": 0.001,
    }
    result = evaluate_confirmation(metrics, config)
    assert result["verdict"] == "GO_RESEARCH_LIFECYCLE"
    assert result["promotion_authorized"] is False
