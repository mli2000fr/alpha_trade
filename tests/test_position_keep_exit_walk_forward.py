from __future__ import annotations

import numpy as np
import pandas as pd

from modelFactory.position_keep_exit_walk_forward import (
    MODEL_FEATURES,
    WalkForwardConfig,
    build_purged_folds,
    equal_trade_weights,
    fit_predict_models,
    replay_first_exit,
    select_threshold,
    summarize,
)


def _states(days: int = 40) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-02", periods=days)
    rows = []
    for index, _date in enumerate(dates[:-3]):
        trade_id = f"T{index:03d}"
        for age in range(2):
            state_date = dates[index + age]
            rows.append({
                "trade_id": trade_id, "state_date": state_date,
                "entry_date": dates[index], "label_end_date": dates[index + 2],
                "signal_date": dates[index], "symbol": "AAA",
                "label_keep": float(index % 2),
                "target_keep_advantage": 0.01 if index % 2 else -0.01,
                "immediate_exit_net": 0.02 if index % 2 == 0 else 0.0,
                "keep_terminal_net": 0.01,
            })
    return pd.DataFrame(rows)


def test_folds_are_purged_and_trade_disjoint() -> None:
    states = _states(50)
    folds = build_purged_folds(states, WalkForwardConfig(
        min_train_dates=10, val_dates=5, test_dates=5, step_dates=5, max_splits=3,
    ))
    assert len(folds) == 3
    for fold in folds:
        assert fold["train"]["label_end_date"].max() < fold["val_start"]
        assert fold["validation"]["label_end_date"].max() < fold["test_start"]
        assert set(fold["train"].trade_id).isdisjoint(fold["validation"].trade_id)
        assert set(fold["validation"].trade_id).isdisjoint(fold["test"].trade_id)


def test_equal_trade_weights_give_each_trade_equal_mass() -> None:
    frame = pd.DataFrame({"trade_id": ["A", "A", "A", "B"]})
    weights = equal_trade_weights(frame)
    masses = pd.Series(weights).groupby(frame.trade_id).sum()
    assert masses["A"] == masses["B"]


def test_replay_executes_first_exit_only() -> None:
    frame = _states(8)
    scores = np.ones(len(frame))
    scores[frame.index[frame.trade_id.eq("T000")][1]] = 0.1
    replay = replay_first_exit(frame, scores, threshold=0.5)
    first = replay[replay.trade_id.eq("T000")].iloc[0]
    assert bool(first.model_exit)
    assert first.policy_return == frame[frame.trade_id.eq("T000")].iloc[1].immediate_exit_net


def test_threshold_selection_can_keep_no_exit_baseline() -> None:
    frame = _states(12)
    frame["immediate_exit_net"] = frame["keep_terminal_net"] - 0.05
    selected = select_threshold(frame, np.full(len(frame), 0.5), classifier=True)
    assert selected["exit_rate"] == 0.0
    assert np.isneginf(selected["threshold"])


def test_all_three_models_produce_finite_predictions() -> None:
    rng = np.random.default_rng(7)

    def partition(size: int, prefix: str) -> pd.DataFrame:
        frame = pd.DataFrame({name: rng.normal(size=size) for name in MODEL_FEATURES})
        frame["trade_id"] = [f"{prefix}{index}" for index in range(size)]
        frame["label_keep"] = (frame[MODEL_FEATURES[0]] > 0).astype(int)
        frame["target_keep_advantage"] = frame[MODEL_FEATURES[0]] * 0.01
        return frame

    train, validation, test = partition(240, "T"), partition(80, "V"), partition(80, "E")
    predictions = fit_predict_models(train, validation, test, seed=11)
    assert set(predictions) == {"logistic_keep", "lightgbm_keep", "lightgbm_advantage"}
    for payload in predictions.values():
        assert np.isfinite(payload["validation"]).all()
        assert np.isfinite(payload["test"]).all()


def test_summary_serializes_missing_classifier_metrics_as_null() -> None:
    trades = pd.DataFrame({
        "model": ["lightgbm_advantage"], "signal_date": [pd.Timestamp("2024-01-02")],
        "baseline_return": [0.0], "policy_return": [0.01], "delta": [0.01],
        "model_exit": [True],
    })
    folds = pd.DataFrame({
        "model": ["lightgbm_advantage"], "fold": [0], "mean_delta": [0.01],
        "state_auc": [np.nan], "state_brier": [np.nan],
        "state_spearman_advantage": [0.1],
    })
    result = summarize(trades, folds, WalkForwardConfig(bootstrap_samples=10))
    assert result["models"]["lightgbm_advantage"]["mean_state_auc"] is None
