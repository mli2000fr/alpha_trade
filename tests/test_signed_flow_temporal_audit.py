from __future__ import annotations

import pandas as pd

from modelFactory.directional_data_research.signed_flow_temporal_audit import (
    candidate_features, evaluate, temporal_features,
)


def test_temporal_features_splits_prefixed_windows() -> None:
    close = pd.Timestamp("2025-01-02T21:00:00Z")
    minutes = [25, 10, 2]
    timestamps = [int((close - pd.Timedelta(minutes=value)).value) for value in minutes]
    quotes = pd.DataFrame({
        "sip_timestamp": timestamps, "bid_price": [99.0] * 3, "ask_price": [101.0] * 3,
        "bid_size": [200.0] * 3, "ask_size": [100.0] * 3,
    })
    trades = pd.DataFrame({
        "sip_timestamp": [value + 1_000_000 for value in timestamps],
        "price": [101.0, 99.0, 101.0], "size": [10.0, 10.0, 10.0],
    })
    result = temporal_features(trades, quotes, close.isoformat())
    assert result["feature_status"] == "complete"
    assert result["early_30_15_signed_volume_ratio"] == 1.0
    assert result["middle_15_5_signed_volume_ratio"] == -1.0
    assert result["late_5_0_signed_volume_ratio"] == 1.0
    assert result["late_minus_early_signed_volume_ratio"] == 0.0
    assert result["flow_acceleration_signed_volume_ratio"] == 4.0


def test_evaluate_applies_multiplicity_and_fixed_feature_set() -> None:
    rows = []
    labels = []
    names = candidate_features()
    for semester_index, semester_start in enumerate(("2022-01-03", "2022-07-05")):
        start = pd.Timestamp(semester_start)
        for index in range(100):
            date = start + pd.Timedelta(days=index)
            symbol = f"S{semester_index}_{index}"
            is_long = index % 2
            row = {"date": date, "symbol": symbol, "feature_status": "complete"}
            for name in names:
                row[name] = float(is_long)
            rows.append(row)
            labels.append({
                "date": date, "symbol": symbol,
                "future_return": 0.1 if is_long else -0.1,
                "abs_future_return": 0.1, "oracle_extreme10": 1,
            })
    result = evaluate(pd.DataFrame(rows), pd.DataFrame(labels))
    assert result["tested_feature_count"] == len(names)
    assert result["go_next_stage"] is True
    assert result["features"][names[0]]["gates"]["bonferroni_p_lt_005"] is True
