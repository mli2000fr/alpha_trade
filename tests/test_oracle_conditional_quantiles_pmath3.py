from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from modelFactory.oracle.dataset import GUARD_COL
from modelFactory.oracle_conditional_quantiles_pmath3 import (
    _split, daily_top_fraction, pinball_loss, rearrange_quantiles,
    select_train_rows, summarize, tail_scores,
)


def test_pinball_loss_is_zero_at_perfect_forecast() -> None:
    target = np.array([-0.2, 0.0, 0.3])
    assert pinball_loss(target, target, 0.10) == 0.0
    assert np.isclose(pinball_loss(np.array([1.0]), np.array([0.0]), 0.10), 0.10)
    assert np.isclose(pinball_loss(np.array([-1.0]), np.array([0.0]), 0.10), 0.90)


def test_rearrangement_is_label_free_and_monotone() -> None:
    predictions = np.array([[0.3, 0.1, 0.2], [0.0, 1.0, 2.0]])
    sorted_predictions, crossing = rearrange_quantiles(predictions)
    np.testing.assert_allclose(sorted_predictions[0], [0.1, 0.2, 0.3])
    assert crossing == 0.5
    assert np.all(np.diff(sorted_predictions, axis=1) >= 0)


def test_tail_score_uses_only_frozen_quantiles() -> None:
    quantiles = [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]
    values = np.array([[-0.5, -0.3, -0.1, 0.0, 0.2, 0.5, 0.7]])
    scores = tail_scores(values, quantiles)
    assert np.isclose(scores["tail_midpoint_q10_q90"][0], 0.1)
    assert np.isclose(scores["tail_asymmetry_q10_q50_q90"][0], 0.2)
    assert scores["conditional_median_q50"][0] == 0.0


def test_train_subsample_is_deterministic_and_train_only() -> None:
    frame = pd.DataFrame({"id": range(100)})
    first = select_train_rows(frame, 15, 17)
    second = select_train_rows(frame, 15, 17)
    pd.testing.assert_frame_equal(first, second)
    assert len(first) == 15
    assert first["id"].between(0, 99).all()


def test_daily_selection_uses_each_date_not_global_threshold() -> None:
    frame = pd.DataFrame({
        "date": ["2024-01-01"] * 10 + ["2024-01-02"] * 10,
        "score": list(range(10)) + list(range(100, 110)),
    })
    selected = frame.loc[daily_top_fraction(frame, "score")]
    assert selected.index.tolist() == [9, 19]


def test_fold_split_purges_labels_not_available_at_validation_start() -> None:
    dates = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-02-01"])
    frame = pd.DataFrame({
        "date": dates,
        GUARD_COL: pd.to_datetime(["2020-01-15", "2020-02-15", "2020-02-20"]),
    })
    spec = {"train_dates": dates[:2], "test_dates": dates[2:], "val_start": "2020-02-01"}
    train, test = _split(frame, spec)
    assert train.index.tolist() == [0]
    assert test.index.tolist() == [2]


def test_direction_go_requires_distribution_and_all_direction_gates() -> None:
    gates = {
        "pinball_relative_improvement_min": 0.02,
        "pinball_positive_fold_rate_min": 0.67,
        "outer_quantile_abs_coverage_error_max": 0.03,
        "d1_d10_auc_median_min": 0.53,
        "d1_d10_auc_delta_vs_logistic_min": 0.01,
        "d1_d10_auc_positive_fold_rate_min": 0.67,
        "d1_d10_signed_top_decile_return_lift_min": 0.0025,
    }
    rows = [{
        "pinball_relative_improvement": 0.05,
        "outer_quantile_abs_coverage_error": 0.01,
        "auc_d1_d10": {"tail_midpoint_q10_q90": 0.54, "direct_logistic_score": 0.52},
        "top_decile_mean_return": {"tail_midpoint_q10_q90": 0.02, "direct_logistic_score": 0.01},
    }] * 3
    assert summarize(rows, gates, "tail_midpoint_q10_q90")["direction_verdict"] == "GO_DIRECTION"
    weak = [dict(row, pinball_relative_improvement=-0.01) for row in rows]
    assert summarize(weak, gates, "tail_midpoint_q10_q90")["direction_verdict"] == "NO_GO_DIRECTION"


def test_config_pre_registers_seven_quantiles_and_primary_score() -> None:
    config = json.loads(Path("config/research/pmath3_conditional_quantiles.json").read_text(encoding="utf-8"))
    assert config["quantiles"] == [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]
    assert config["primary_direction_score"] == "tail_midpoint_q10_q90"
    assert config["status"] == "COMPLETED_NO_GO_DISTRIBUTION_NO_GO_DIRECTION"
