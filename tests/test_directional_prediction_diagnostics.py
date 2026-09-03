from __future__ import annotations

import pandas as pd
import pytest

from ihm.services.directional_prediction_diagnostics import (
    attach_forward_returns,
    evaluate_directional_top_decile,
    oracle_top_fraction,
)


def test_attach_forward_returns_uses_trading_sessions_and_spy_excess() -> None:
    dates = pd.to_datetime(["2024-01-05", "2024-01-08", "2024-01-09", "2024-01-10"])
    bars = pd.DataFrame({
        "symbol": ["AAA"] * 4 + ["SPY"] * 4,
        "date": list(dates) * 2,
        "adj_close": [100.0, 101.0, 102.0, 110.0, 100.0, 100.5, 101.0, 102.0],
    })
    predictions = pd.DataFrame({"symbol": ["AAA"], "prediction_date": [dates[0]]})

    result = attach_forward_returns(predictions, bars, horizon=3)

    assert result.iloc[0]["future_return"] == pytest.approx(0.10)
    assert result.iloc[0]["benchmark_future_return"] == pytest.approx(0.02)
    assert result.iloc[0]["excess_future_return"] == pytest.approx(0.08)


def test_top_decile_is_selected_per_date_and_short_return_is_signed() -> None:
    rows = []
    for date in pd.to_datetime(["2024-01-02", "2024-01-03"]):
        for index in range(10):
            rows.append({
                "prediction_date": date,
                "symbol": f"S{index:02d}",
                "proba_short": index / 10.0,
                "future_return": -0.05 if index == 9 else 0.01,
                "excess_future_return": -0.04 if index == 9 else 0.0,
            })

    result = evaluate_directional_top_decile(pd.DataFrame(rows), side="short")

    assert result["picks"]["symbol"].tolist() == ["S09", "S09"]
    assert result["metrics"]["n_picks"] == 2
    assert result["metrics"]["hit_rate"] == pytest.approx(1.0)
    assert result["metrics"]["extreme_hit_rate"] == pytest.approx(1.0)
    assert result["metrics"]["mean_signed_return"] == pytest.approx(0.05)


def test_oracle_top_fraction_is_daily_and_deterministic() -> None:
    frame = pd.DataFrame({
        "prediction_date": pd.to_datetime(["2024-01-02"] * 5),
        "symbol": ["E", "D", "C", "B", "A"],
        "proba_extreme": [0.1, 0.2, 0.3, 0.4, 0.5],
    })
    selected = oracle_top_fraction(frame, 0.20)
    # Parité avec la cascade : rank(pct=True) >= 0.80.
    assert selected["symbol"].tolist() == ["B", "A"]


def test_oracle_precomputed_pool_is_not_reranked_on_directional_intersection() -> None:
    frame = pd.DataFrame({
        "prediction_date": pd.to_datetime(["2024-01-02"] * 2),
        "symbol": ["A", "B"],
        "proba_extreme": [0.9, 0.8],
        "oracle_top_pool": [False, True],
    })

    selected = oracle_top_fraction(frame, 0.20)

    assert selected["symbol"].tolist() == ["B"]


def test_unmatured_top_candidate_is_not_replaced_by_a_lower_probability() -> None:
    frame = pd.DataFrame({
        "prediction_date": pd.to_datetime(["2024-01-02"] * 10),
        "symbol": [f"S{index:02d}" for index in range(10)],
        "proba_long": [index / 10.0 for index in range(10)],
        "future_return": [0.01] * 9 + [None],
    })

    result = evaluate_directional_top_decile(frame, side="long")

    assert result["selected"]["symbol"].tolist() == ["S09"]
    assert result["picks"].empty
    assert result["metrics"]["n_selected"] == 1
    assert result["metrics"]["n_picks"] == 0
