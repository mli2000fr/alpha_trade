from __future__ import annotations

import pandas as pd

from modelFactory.config import TrainingConfig, WalkForwardConfig
from modelFactory.dataset import generate_walk_forward_splits
from modelFactory.trainer import _aggregate_walk_forward_metrics, _run_walk_forward_validation


def test_aggregate_walk_forward_metrics_returns_means_and_split_count() -> None:
    metrics = [
        {
            "auc": 0.61,
            "threshold_business_score": 0.55,
            "decision_threshold": 0.60,
            "directional_accuracy": 0.58,
            "precision": 0.57,
            "recall": 0.56,
        },
        {
            "auc": 0.65,
            "threshold_business_score": 0.59,
            "decision_threshold": 0.62,
            "directional_accuracy": 0.60,
            "precision": 0.58,
            "recall": 0.57,
        },
    ]

    aggregated = _aggregate_walk_forward_metrics(metrics)

    assert aggregated["n_splits"] == 2
    assert aggregated["mean"]["auc"] == 0.63
    assert aggregated["mean"]["decision_threshold"] == 0.61
    assert aggregated["std"]["auc"] is not None


def test_generate_walk_forward_splits_for_ml_pipeline_shape() -> None:
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=40, freq="D"), "x": range(40)})

    splits = generate_walk_forward_splits(
        df,
        min_train_size=20,
        val_size=6,
        test_size=6,
        step_size=4,
        max_splits=2,
        forecast_horizon=1,
    )

    assert len(splits) == 2
    assert len(splits[0].train) == 19
    assert len(splits[0].val) == 5
    assert len(splits[0].test) == 6


def test_run_walk_forward_validation_returns_empty_when_disabled() -> None:
    cfg = TrainingConfig(walk_forward=WalkForwardConfig(enabled=False))
    prepared_df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=30, freq="D")})

    result = _run_walk_forward_validation("AAPL", prepared_df, cfg)

    assert result == {}

