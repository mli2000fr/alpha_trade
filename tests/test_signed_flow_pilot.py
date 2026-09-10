from __future__ import annotations

import pandas as pd

from modelFactory.directional_data_research.signed_flow_pilot import (
    evaluate_direction, select_events, signed_flow_features,
)


def test_select_events_uses_only_oof_eligible_rows() -> None:
    gate = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-07-02"]),
        "symbol": ["AA", "BB", "CC"],
        "directional_oracle_eligible": [True, False, True],
        "directional_oracle_oof_available": [True, True, True],
    })
    selected = select_events(gate, start_date="2024-01-01", end_date="2024-12-31", count=10)
    assert set(selected["symbol"]) == {"AA", "CC"}
    assert "future_return" not in selected.columns


def test_signed_flow_features_classifies_against_prevailing_mid() -> None:
    base = 1_700_000_000_000_000_000
    quotes = pd.DataFrame({
        "sip_timestamp": [base, base + 2_000_000_000],
        "bid_price": [99.0, 100.0], "ask_price": [101.0, 102.0],
        "bid_size": [100, 200], "ask_size": [100, 100],
    })
    trades = pd.DataFrame({
        "sip_timestamp": [base + 1_000_000_000, base + 3_000_000_000],
        "price": [101.0, 100.0], "size": [10, 5],
    })
    result = signed_flow_features(trades, quotes)
    assert result["feature_status"] == "complete"
    assert result["quote_match_rate"] == 1.0
    assert result["signed_volume_ratio"] == (10 - 5) / 15


def test_evaluate_direction_uses_fixed_orientation_across_semesters() -> None:
    dates = pd.to_datetime(["2023-01-02", "2023-01-03", "2023-07-03", "2023-07-04"])
    features = pd.DataFrame({
        "date": dates, "symbol": ["A", "B", "C", "D"],
        "feature_status": "complete",
        "signed_volume_ratio": [-0.8, 0.8, -0.7, 0.7],
        "signed_dollar_ratio": [-0.8, 0.8, -0.7, 0.7],
        "mean_quote_size_imbalance": [-0.5, 0.5, -0.4, 0.4],
    })
    labels = pd.DataFrame({
        "date": dates, "symbol": ["A", "B", "C", "D"],
        "future_return": [-0.1, 0.1, -0.1, 0.1],
        "abs_future_return": [0.1] * 4, "oracle_extreme10": [1] * 4,
    })
    report = evaluate_direction(features, labels)
    assert report["features"]["signed_volume_ratio"]["oriented_auc"] == 1.0
    assert report["features"]["signed_volume_ratio"]["positive_semester_ratio"] == 1.0
