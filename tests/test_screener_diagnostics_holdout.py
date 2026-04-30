"""Tests Phase 6.1.d — validation hold-out du diagnostic screener."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from backtesting.screener_diagnostics import (
    export_holdout_validation,
    validate_recommendations_holdout,
)


def _make_daily(scenarios: list[str], dates: list[str], scores: dict[str, list[float]]) -> pd.DataFrame:
    rows = []
    for sc in scenarios:
        for d, val in zip(dates, scores[sc]):
            rows.append({
                "scenario_name": sc,
                "trade_date": d,
                "portfolio_forward_return_20d": val,
            })
    return pd.DataFrame(rows)


def test_validate_recommendations_holdout_basic_stable_top_k() -> None:
    dates = ["2025-01-01", "2025-01-02", "2025-02-01", "2025-02-02"]
    scenarios = ["A", "B", "C"]
    # A domine en train ET en test → stable.
    scores = {
        "A": [0.10, 0.12, 0.11, 0.13],
        "B": [0.05, 0.06, 0.05, 0.07],
        "C": [0.02, 0.01, 0.02, 0.03],
    }
    df = _make_daily(scenarios, dates, scores)
    result, summary = validate_recommendations_holdout(
        df, train_end="2025-01-15", test_end="2025-02-28",
    )
    assert summary["status"] == "ok"
    assert summary["scenarios_evaluated"] == 3
    assert summary["stable_top_k_ratio"] == 1.0  # top-1 stable
    assert result.iloc[0]["scenario_name"] == "A"
    assert "rank_train" in result.columns and "rank_test" in result.columns
    assert "score_delta" in result.columns


def test_validate_recommendations_holdout_detects_unstable_ranking() -> None:
    dates = ["2025-01-01", "2025-01-02", "2025-02-01", "2025-02-02"]
    # A bon en train, mauvais en test ; B inverse.
    scores = {
        "A": [0.20, 0.18, -0.05, -0.10],
        "B": [-0.05, -0.04, 0.18, 0.22],
    }
    df = _make_daily(["A", "B"], dates, scores)
    result, summary = validate_recommendations_holdout(
        df, train_end="2025-01-15", test_end="2025-02-28",
    )
    # Le top-1 change entre train et test.
    assert summary["scenarios_evaluated"] == 2
    a_row = result[result["scenario_name"] == "A"].iloc[0]
    assert a_row["rank_train"] == 1
    assert a_row["rank_test"] == 2
    assert a_row["rank_delta"] > 0


def test_validate_recommendations_holdout_handles_empty_window() -> None:
    df = _make_daily(["A"], ["2025-01-01"], {"A": [0.1]})
    result, summary = validate_recommendations_holdout(
        df, train_end="2024-01-15", test_end="2024-02-28",
    )
    assert result.empty
    assert summary["status"] == "empty_window"


def test_validate_recommendations_holdout_missing_metric_column() -> None:
    df = pd.DataFrame({"scenario_name": ["A"], "trade_date": ["2025-01-01"]})
    result, summary = validate_recommendations_holdout(
        df, train_end="2025-01-15", test_end="2025-02-28",
    )
    assert result.empty
    assert summary["status"] == "missing_metric"


def test_export_holdout_validation_writes_csv_and_json(tmp_path: Path) -> None:
    df = pd.DataFrame([{"scenario_name": "A", "rank_train": 1, "rank_test": 1}])
    summary = {"status": "ok", "stable_top_k_ratio": 1.0}
    paths = export_holdout_validation(df, summary, tmp_path)
    assert paths["holdout_validation_recommendations"].exists()
    assert paths["holdout_summary"].exists()
    payload = json.loads(paths["holdout_summary"].read_text(encoding="utf-8"))
    assert payload["status"] == "ok"

