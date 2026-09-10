from __future__ import annotations

import pandas as pd
import pytest

from modelFactory.oracle_universe_p0i_evaluate import (
    amplitude_deciles,
    direction_diagnostic,
    prepare_evaluation,
    selection_concentration,
    universe_turnover,
)


def test_prepare_evaluation_replaces_training_labels_and_filters_quality() -> None:
    scores = pd.DataFrame({
        "date": pd.to_datetime(["2026-01-02", "2026-01-02"]),
        "symbol": ["AAA", "BBB"],
        "proba_extreme": [0.9, 0.1],
        "future_return": [None, None],
        "oracle_extreme10": [None, None],
    })
    labels = pd.DataFrame({
        "prediction_date": pd.to_datetime(["2026-01-02", "2026-01-02"]),
        "symbol": ["AAA", "BBB"],
        "future_return": [0.2, -0.1],
        "oracle_extreme10": [1, 0],
        "target_quality_valid": [1, 0],
        "target_quality_reason": [None, "missing_exit_bar"],
    })
    evaluated, coverage = prepare_evaluation(scores, labels)
    assert evaluated["symbol"].tolist() == ["AAA"]
    assert evaluated.iloc[0]["future_return"] == 0.2
    assert coverage["valid_rows"] == 1
    assert coverage["invalid_or_unavailable_rows"] == 1


def test_amplitude_deciles_uses_absolute_not_signed_return() -> None:
    rows = []
    for date in pd.to_datetime(["2026-01-02", "2026-01-05"]):
        for index in range(20):
            score = index / 19
            magnitude = 0.01 + score * 0.20
            rows.append({
                "date": date, "symbol": f"S{index:02d}",
                "proba_extreme": score,
                "future_return": magnitude if index % 2 else -magnitude,
            })
    monotonicity, table = amplitude_deciles(pd.DataFrame(rows))
    assert monotonicity == pytest.approx(1.0)
    assert table.iloc[-1]["mean_abs_return"] > table.iloc[0]["mean_abs_return"]


def test_universe_turnover_and_selection_concentration() -> None:
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2026-01-02"] * 5 + ["2026-01-05"] * 5),
        "symbol": ["A", "B", "C", "D", "E", "A", "B", "C", "D", "F"],
        "proba_extreme": [5, 4, 3, 2, 1, 5, 4, 3, 2, 1],
    })
    turnover = universe_turnover(frame)
    assert turnover["daily_median"] == 5
    assert turnover["mean_daily_jaccard_turnover"] == 1 - 4 / 6
    concentration = selection_concentration(frame, pct=0.20)
    assert concentration["rows"] == 2
    assert concentration["symbols"] == 1
    assert concentration["largest_symbol_share"] == 1.0


def test_direction_diagnostic_uses_only_daily_top_scores() -> None:
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2026-01-02"] * 5),
        "symbol": list("ABCDE"),
        "proba_extreme": [0.9, 0.8, 0.7, 0.6, 0.5],
        "future_return": [-0.20, 0.10, 0.05, 0.02, 0.01],
        "oracle_extreme10": [1, 1, 0, 0, 0],
    })
    result = direction_diagnostic(frame, pct=0.40)
    assert result["rows"] == 2
    assert result["mean_signed_return"] == pytest.approx(-0.05)
    assert result["positive_rate_among_true_extremes"] == pytest.approx(0.5)
