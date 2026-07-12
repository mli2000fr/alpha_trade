from __future__ import annotations

import numpy as np
import pandas as pd

from modelFactory.evaluation import (
    align_sequence_rows,
    bucket_analysis,
    compute_threshold_metrics,
    optimize_decision_threshold,
)


def test_bucket_analysis_returns_expected_bucket_count() -> None:
    result = bucket_analysis(
        np.array([0.1, 0.2, 0.7, 0.9]),
        np.array([0, 0, 1, 1]),
        np.array([-0.01, 0.0, 0.02, 0.03]),
        n_buckets=2,
    )

    assert result["n_buckets"] == 2
    assert len(result["buckets"]) == 2
    assert result["buckets"][0]["count"] == 2
    assert result["top_bucket_hit_rate"] == 1.0
    assert result["top_minus_bottom_bucket_hit_rate"] == 1.0


def test_compute_threshold_metrics_returns_action_metrics() -> None:
    result = compute_threshold_metrics(
        np.array([0.2, 0.6, 0.8, 0.9]),
        np.array([0, 0, 1, 1]),
        np.array([-0.01, -0.02, 0.03, 0.05]),
        decision_threshold=0.75,
    )

    assert result["coverage_at_threshold"] == 0.5
    assert result["precision_long"] == 1.0
    assert result["avg_future_return_on_actions"] == 0.04
    assert result["threshold_business_score"] > 0.0


def test_optimize_decision_threshold_selects_best_valid_candidate() -> None:
    summary = optimize_decision_threshold(
        np.array([0.2, 0.4, 0.6, 0.8, 0.9]),
        np.array([0, 0, 0, 1, 1]),
        np.array([-0.03, -0.02, -0.01, 0.02, 0.03]),
        candidate_thresholds=(0.50, 0.75, 0.85),
        default_threshold=0.50,
        min_action_rate=0.20,
        max_action_rate=0.80,
        min_precision_long=0.50,
    )

    assert summary["selection_status"] == "selected"
    assert summary["selected_threshold"] == 0.75
    assert len(summary["candidates"]) == 3


def test_optimize_decision_threshold_falls_back_to_default_when_constraints_fail() -> None:
    summary = optimize_decision_threshold(
        np.array([0.2, 0.4, 0.6, 0.8]),
        np.array([0, 0, 1, 1]),
        np.array([-0.02, -0.01, 0.02, 0.03]),
        candidate_thresholds=(0.70, 0.80),
        default_threshold=0.60,
        min_action_rate=0.80,
        max_action_rate=0.90,
        min_precision_long=0.90,
    )

    assert summary["selection_status"] == "fallback_default_threshold"
    assert summary["selected_threshold"] == 0.60


def test_align_sequence_rows_matches_sequence_end_rows_and_drops_non_finite_targets() -> None:
    df = pd.DataFrame(
        {
            "target": [1.0, 0.0, 1.0, np.nan, 0.0],
            "future_return": [0.1, -0.1, 0.2, np.nan, -0.05],
        }
    )

    aligned = align_sequence_rows(df, seq_len=2)

    assert len(aligned) == 3
    assert aligned["target"].tolist() == [0.0, 1.0, 0.0]
