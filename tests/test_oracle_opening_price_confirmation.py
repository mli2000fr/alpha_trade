from __future__ import annotations

import numpy as np
import pandas as pd

from modelFactory.oracle_opening_price_confirmation import (
    E20BConfig,
    attach_price_only_features,
    build_price_only_features,
    decide,
    evaluate_rules,
    load_price_features,
)


def _rows() -> pd.DataFrame:
    minutes = [570, 571, 572, 573, 574, 584, 599, 629]
    closes = np.asarray([100, 100.1, 100.2, 100.3, 100.5, 101, 102, 103])
    return pd.DataFrame({
        "session_date": pd.Timestamp("2026-09-14"), "symbol": "AAA",
        "minute_of_day": minutes,
        "bar_timestamp": pd.date_range("2026-09-14 13:30", periods=len(minutes), freq="min"),
        "open": np.r_[100, closes[:-1]], "high": closes + 0.2,
        "low": closes - 0.2, "close": closes,
        "minute_volume": 1, "trade_count": 1, "vwap": closes,
    })


def test_price_only_features_need_no_volume_columns() -> None:
    rows = _rows().drop(columns=["minute_volume", "trade_count", "vwap"])
    result = build_price_only_features(rows, E20BConfig()).iloc[0]
    assert result["opening_price"] == 100
    assert np.isclose(result["return_5m"], 0.005)
    assert np.isclose(result["return_30m"], 0.02)
    assert np.isclose(result["return_60m"], 0.03)
    assert bool(result["eligible_30m"])


def test_later_prices_cannot_change_earlier_checkpoint() -> None:
    baseline = build_price_only_features(_rows(), E20BConfig()).iloc[0]
    changed = _rows()
    changed.loc[changed["minute_of_day"].gt(574), ["open", "high", "low", "close"]] *= 2
    altered = build_price_only_features(changed, E20BConfig()).iloc[0]
    assert altered["return_5m"] == baseline["return_5m"]
    assert altered["range_5m"] == baseline["range_5m"]


def test_stale_checkpoint_is_rejected() -> None:
    sparse = _rows()[_rows()["minute_of_day"].le(584)]
    result = build_price_only_features(sparse, E20BConfig()).iloc[0]
    assert bool(result["eligible_15m"])
    assert not bool(result["eligible_30m"])
    assert np.isnan(result["return_30m"])


def test_rules_map_signal_to_next_session_and_abstain() -> None:
    events = pd.DataFrame({
        "date": pd.to_datetime(["2026-09-11", "2026-09-14", "2026-09-15"]),
        "symbol": "AAA", "future_return": [0.10, -0.10, 0.05],
        "oracle_decile": [10, 1, 10], "directional_oracle_fold_start": "fold1",
    })
    features = pd.DataFrame({
        "session_date": pd.to_datetime(["2026-09-14", "2026-09-15"]),
        "symbol": "AAA",
        **{f"return_{minute}m": [0.01, 0.001] for minute in (5, 15, 30, 60)},
    })
    joined = attach_price_only_features(events, features)
    config = E20BConfig(bootstrap_samples=10, minimum_events=1, minimum_dates=1)
    summary, _, _ = evaluate_rules(joined, config)
    primary = summary[
        (summary["checkpoint_minutes"] == 30)
        & np.isclose(summary["threshold"], 0.005)
    ].iloc[0]
    assert primary["observed_events"] == 2
    assert primary["selected_events"] == 1
    assert primary["direction_accuracy"] == 1


def test_decision_never_promotes_to_production() -> None:
    config = E20BConfig(
        minimum_events=1, minimum_dates=1, minimum_coverage=0.5,
        minimum_selected_events=1, minimum_tail_events=1,
        minimum_selection_rate=0.1,
        minimum_direction_accuracy=0.5, minimum_tail_accuracy=0.5,
    )
    summary = pd.DataFrame([{
        "policy": "primary", "checkpoint_minutes": 30, "threshold": 0.005,
        "observed_events": 10, "observed_dates": 2, "price_coverage": 1,
        "selected_events": 10, "tail_events": 5, "selection_rate": 1,
        "direction_accuracy": 0.7, "tail_direction_accuracy": 0.7,
        "daily_mean_ci95_low": 0.01, "positive_fold_ratio": 1,
        "positive_semester_ratio": 1,
    }])
    decision = decide(summary, config)
    assert decision["verdict"] == "GO_RESEARCH_VOLUME_ABLATION"
    assert decision["promotion_authorized"] is False


def test_consolidated_backfill_has_priority_over_partitions(tmp_path) -> None:
    pd.DataFrame({"symbol": ["AAA"]}).to_parquet(
        tmp_path / "price_only_features.parquet", index=False,
    )
    assert load_price_features(tmp_path)["symbol"].tolist() == ["AAA"]
