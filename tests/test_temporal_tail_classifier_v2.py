from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from modelFactory import temporal_tail_classifier_v2 as temporal


def test_config_freezes_windows_and_feature_budget(tmp_path: Path) -> None:
    payload = json.loads(Path("config/research/temporal_d1d10_v2.json").read_text())
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = temporal.load_config(path)
    assert loaded["windows"] == [3, 5, 10]
    assert 20 <= len(loaded["base_features"]) <= 30


def test_temporal_features_are_symbol_local_and_causal() -> None:
    rows = []
    for symbol, offset in (("A", 0.0), ("B", 100.0)):
        for index, date in enumerate(pd.bdate_range("2024-01-01", periods=8)):
            rows.append({"symbol": symbol, "date": date, "x": offset + index})
    frame = pd.DataFrame(rows)
    derived, groups = temporal.add_temporal_features(
        frame, ["x"], 3,
        positive_fraction_features={"x"}, acceleration_features={"x"},
    )
    a = derived[derived["symbol"].eq("A")].reset_index(drop=True)
    b = derived[derived["symbol"].eq("B")].reset_index(drop=True)
    assert a.loc[3, "x__delta_3"] == 3
    assert b.loc[3, "x__delta_3"] == 3
    assert np.isnan(a.loc[2, "x__slope_3"])
    assert a.loc[3, "x__slope_3"] == pytest.approx(1.0)
    assert a.loc[3, "x__positive_fraction_3"] == 1
    assert "x__acceleration_3" in groups["shape"]


def test_future_mutation_does_not_change_past_features() -> None:
    frame = pd.DataFrame({
        "symbol": ["A"] * 8,
        "date": pd.bdate_range("2024-01-01", periods=8),
        "x": np.arange(8, dtype=float),
    })
    original, _ = temporal.add_temporal_features(
        frame, ["x"], 3, positive_fraction_features={"x"}, acceleration_features={"x"}
    )
    mutated = frame.copy()
    mutated.loc[7, "x"] = 9999
    changed, _ = temporal.add_temporal_features(
        mutated, ["x"], 3, positive_fraction_features={"x"}, acceleration_features={"x"}
    )
    columns = [name for name in original if "__" in name]
    pd.testing.assert_frame_equal(original.loc[:6, columns], changed.loc[:6, columns])


def test_walk_forward_is_expanding_and_test_is_disjoint() -> None:
    dates = pd.Series(pd.bdate_range("2020-01-01", periods=900))
    folds = temporal.make_folds(
        dates,
        {"min_train_sessions": 504, "test_sessions": 126,
         "step_sessions": 126, "max_splits": 12},
    )
    assert len(folds) == 3
    assert folds[0].test_start == dates.iloc[504]
    assert folds[0].test_end < folds[1].test_start


def test_same_date_auc_rewards_correct_within_date_order() -> None:
    rows = []
    for date in pd.bdate_range("2024-01-01", periods=4):
        rows.extend([
            {"date": date, temporal.TARGET: 0.0, "tail_polarity_score": 0.1},
            {"date": date, temporal.TARGET: 1.0, "tail_polarity_score": 0.9},
        ])
    auc = temporal._same_date_auc(pd.DataFrame(rows))
    assert auc.mean() == 1.0


def test_label_audit_separates_relative_tail_from_absolute_sign() -> None:
    labels = pd.DataFrame({
        "prediction_date": pd.to_datetime(["2024-01-02"] * 4),
        "oracle_decile": [1, 1, 10, 10],
        "future_return": [0.01, 0.02, 0.03, 0.04],
    })
    audit = temporal.audit_labels(labels)
    assert audit["global"]["p_negative_given_d1"] == 0
    assert audit["global"]["p_positive_given_d10"] == 1
    assert audit["same_absolute_sign_date_rate"] == 1


def test_fit_predict_supports_all_prefixed_models() -> None:
    dates = pd.to_datetime(["2024-01-02"] * 4 + ["2024-01-03"] * 4)
    train = pd.DataFrame({
        "date": dates,
        "x": [-2.0, -1.0, 1.0, 2.0] * 2,
        temporal.TARGET: [0, 0, 1, 1] * 2,
    })
    test = train.iloc[:4].copy()
    configs = {
        "logistic": {"C": 1.0, "max_iter": 100},
        "catboost": {"iterations": 3, "depth": 2, "learning_rate": 0.1},
        "pairlogit": {"iterations": 3, "depth": 2, "learning_rate": 0.1},
    }
    for model in configs:
        score = temporal.fit_predict(
            model, train, test, ["x"], configs[model], seed=42, threads=1
        )
        assert len(score) == len(test)
        assert np.isfinite(score).all()
