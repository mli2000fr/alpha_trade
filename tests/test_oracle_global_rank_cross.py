from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from modelFactory.oracle_global_rank_cross import (
    E11Config,
    build_cross_events,
    evaluate,
    load_oof_inputs,
    summarize_experiment,
)


def _inputs(days: int = 80, symbols: int = 20) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2022-01-03", periods=days + 25)
    oracle_rows, rank_rows, bar_rows = [], [], []
    for symbol_index in range(symbols):
        symbol = f"S{symbol_index:02d}"
        # Le prix futur est strictement croissant avec le rang afin de rendre
        # le contrat de test lisible et deterministe.
        daily_step = (symbol_index - (symbols - 1) / 2) / 10_000
        for day, date in enumerate(dates):
            price = 100.0 * (1.0 + daily_step) ** day
            bar_rows.append({
                "date": date, "symbol": symbol, "open": price,
                "close": price, "adj_close": price,
            })
            if day < days:
                oracle_rows.append({
                    "date": date,
                    "symbol": symbol,
                    "directional_oracle_fold_start": dates[(day // 20) * 20],
                    "directional_oracle_proba_extreme": 0.9,
                    "directional_oracle_eligible": True,
                    "directional_oracle_oof_available": True,
                })
                rank_rows.append({
                    "date": date, "symbol": symbol,
                    "global_rank_20": (symbol_index + 1) / symbols,
                })
    return pd.DataFrame(oracle_rows), pd.DataFrame(rank_rows), pd.DataFrame(bar_rows)


def test_cross_uses_only_oracle_eligible_oof_rows() -> None:
    oracle, ranking, bars = _inputs(days=2)
    oracle.loc[0, "directional_oracle_eligible"] = False
    oracle.loc[1, "directional_oracle_oof_available"] = False
    events, coverage = build_cross_events(oracle, ranking, bars, E11Config(bootstrap_samples=10))
    assert len(events) == len(oracle) - 2
    assert coverage["oracle_top20_events"] == len(oracle) - 2


def test_cross_reranks_global_rank_inside_oracle_pool() -> None:
    oracle, ranking, bars = _inputs(days=2)
    events, _ = build_cross_events(oracle, ranking, bars, E11Config(bootstrap_samples=10))
    assert events.groupby("date")["side"].apply(lambda x: x.eq("LONG").sum()).eq(4).all()
    assert events.groupby("date")["side"].apply(lambda x: x.eq("SHORT").sum()).eq(4).all()
    assert events.groupby("date")["side"].apply(lambda x: x.eq("ABSTAIN").sum()).eq(12).all()


def test_returns_follow_j1_to_j21_adjusted_open_clock() -> None:
    oracle, ranking, bars = _inputs(days=1)
    events, _ = build_cross_events(oracle, ranking, bars, E11Config(bootstrap_samples=10))
    row = events[events["symbol"].eq("S19")].iloc[0]
    expected = row["terminal_exit_open"] / row["immediate_entry_open"] - 1.0
    assert row["future_return_h20"] == pytest.approx(expected)
    assert row["terminal_date"] == row["date"] + pd.offsets.BDay(21)


def test_positive_synthetic_rank_produces_positive_ic_and_lifts() -> None:
    oracle, ranking, bars = _inputs()
    config = E11Config(minimum_events_per_side=10, bootstrap_samples=50)
    events, coverage = build_cross_events(oracle, ranking, bars, config)
    metrics, daily, folds, semesters = summarize_experiment(events, coverage, config)
    assert metrics["daily_ic"] > 0.99
    assert metrics["daily_long_lift_vs_oracle"] > 0
    assert metrics["daily_short_lift_vs_oracle"] > 0
    assert metrics["daily_long_short_net"] > 0
    assert not daily.empty and not folds.empty and not semesters.empty


def test_verdict_remains_research_only() -> None:
    metrics = {
        "join_coverage": 1.0,
        "long_events": 1_000,
        "short_events": 1_000,
        "daily_ic": 0.03,
        "positive_fold_ic_ratio": 1.0,
        "positive_semester_ic_ratio": 1.0,
        "daily_long_short_net": 0.01,
        "daily_long_short_net_ci95_low": 0.001,
        "daily_long_net": 0.01,
        "daily_long_lift_vs_oracle": 0.005,
        "daily_long_lift_vs_oracle_ci95_low": 0.001,
        "positive_fold_long_lift_ratio": 1.0,
        "positive_semester_long_lift_ratio": 1.0,
        "daily_short_net": 0.01,
        "daily_short_lift_vs_oracle": 0.005,
        "daily_short_lift_vs_oracle_ci95_low": 0.001,
        "positive_fold_short_lift_ratio": 1.0,
        "positive_semester_short_lift_ratio": 1.0,
    }
    result = evaluate(metrics, E11Config())
    assert set(result["verdicts"].values()) == {"GO_RESEARCH"}
    assert result["promotion_authorized"] is False


def test_loader_refuses_serving_or_database_exports(tmp_path: Path) -> None:
    oracle_path = tmp_path / "oracle.parquet"
    rank_path = tmp_path / "rank_from_database.parquet"
    pd.DataFrame({"x": [1]}).to_parquet(oracle_path)
    pd.DataFrame({"x": [1]}).to_parquet(rank_path)
    with pytest.raises(ValueError, match="_oracle_oof_gate"):
        load_oof_inputs(oracle_path, rank_path)


def test_duplicate_global_rank_keys_are_rejected() -> None:
    oracle, ranking, bars = _inputs(days=1)
    ranking = pd.concat([ranking, ranking.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="Doublons"):
        build_cross_events(oracle, ranking, bars, E11Config(bootstrap_samples=10))


def test_config_is_frozen_to_h20() -> None:
    with pytest.raises(ValueError, match="H20"):
        E11Config(horizon=10)


def test_invalid_rank_values_are_excluded() -> None:
    oracle, ranking, bars = _inputs(days=1)
    ranking.loc[0, "global_rank_20"] = np.inf
    events, _ = build_cross_events(oracle, ranking, bars, E11Config(bootstrap_samples=10))
    assert len(events) == len(oracle) - 1
