from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from modelFactory.fr_feature_profile_freeze import FEATURES
from modelFactory.fr_oracle_h5_pilot import (
    choose_champion,
    deterministic_score,
    feature_matrix,
    load_config,
    score_metrics,
    select_phase,
    verdict,
)


@pytest.fixture
def cfg():
    return load_config(Path(__file__).resolve().parents[1] / "config/research_fr/oracle_h5_pilot_v1.yaml")


def test_exact_feature_list_and_deterministic_log_transform():
    frame = pd.DataFrame([{**dict.fromkeys(FEATURES, 1.0), "future_return": 999, "oracle_extreme": 1}])
    matrix = feature_matrix(frame)
    assert list(matrix) == list(FEATURES)
    assert matrix["traded_value_mean20_eur"].iloc[0] == pytest.approx(np.log(2))
    assert matrix["return_1"].iloc[0] == 1
    frame.loc[0, "return_1"] = np.nan
    with pytest.raises(ValueError):
        feature_matrix(frame)


def test_top20_ranking_per_day_not_global(cfg):
    frame = pd.DataFrame(
        {
            "decision_session_date": ["2025-01-02"] * 20 + ["2025-01-03"] * 20,
            "research_uid": [str(i) for i in range(20)] * 2,
            "oracle_extreme": ([1] * 4 + [0] * 16) * 2,
        }
    )
    score = np.array(list(range(20, 0, -1)) * 2, dtype=float)
    metrics, days = score_metrics(frame, score, cfg)
    assert days["selected"].tolist() == [4, 4]
    assert metrics["mean_daily_precision"] == 1
    assert metrics["mean_daily_lift"] == 5
    assert metrics["average_precision"] == 1


def test_tie_break_independent_of_input_order(cfg):
    frame = pd.DataFrame(
        {
            "decision_session_date": ["2025-01-02"] * 20,
            "research_uid": [str(i) for i in range(20)],
            "oracle_extreme": [0, 1] * 10,
        }
    )
    first, _ = score_metrics(frame, np.ones(20), cfg)
    shuffled = frame.sample(frac=1, random_state=3)
    second, _ = score_metrics(shuffled, np.ones(20), cfg)
    assert first == second
    assert deterministic_score("2025-01-02", "a", 17) == deterministic_score("2025-01-02", "a", 17)


def test_champion_uses_validation_and_logistic_tie_priority():
    assert choose_champion({"logistic": {"average_precision": 0.2}, "trees": {"average_precision": 0.3}}) == "trees"
    assert choose_champion({"logistic": {"average_precision": 0.3}, "trees": {"average_precision": 0.3}}) == "logistic"


def test_phase_requires_mature_label_and_20_usable_rows(cfg):
    frame = pd.DataFrame(
        {
            "decision_session_date": ["2025-01-02"] * 20,
            "research_uid": [str(i) for i in range(20)],
            "label_available_session_date": ["2025-01-03"] * 20,
            "path_state": "VALID",
            "profile_row_ready": True,
            "oracle_extreme": [0, 1] * 10,
        }
    )
    fold = {"train_start": "2025-01-02", "train_end": "2025-01-02", "validation_start": "2025-01-06"}
    assert len(select_phase(frame, fold, "train", cfg)) == 20
    frame.loc[0, "label_available_session_date"] = "2025-01-06"
    assert select_phase(frame, fold, "train", cfg).empty


def test_invalid_score_rejected(cfg):
    frame = pd.DataFrame({"decision_session_date": ["2025-01-02"], "research_uid": ["a"], "oracle_extreme": [1]})
    with pytest.raises(ValueError):
        score_metrics(frame, np.array([np.nan]), cfg)


def test_pilot_gate_requires_both_mechanical_baselines(cfg):
    tests = {
        "trees": {"mean_daily_precision": 0.4, "average_precision": 0.35, "mean_daily_lift": 1.8},
        "atr": {"mean_daily_precision": 0.3, "average_precision": 0.3},
        "volatility": {"mean_daily_precision": 0.35, "average_precision": 0.32},
    }
    folds = [{"champion": "trees", "test": tests} for _ in range(3)]
    assert verdict(folds, cfg)["verdict"] == "PILOT_SIGNAL_REQUIRES_CONFIRMATION"
    tests["volatility"]["mean_daily_precision"] = 0.45
    assert verdict(folds, cfg)["verdict"] == "NO_GO_INCREMENTAL_PILOT"
