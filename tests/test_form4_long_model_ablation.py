from __future__ import annotations

import numpy as np
import pandas as pd

from modelFactory.directional_data_research.form4_long_model_ablation import (
    FORM4_COLUMNS, evaluate_long_score, prepare_form4_model_features,
    restrict_experiment_period,
)
from modelFactory.shared_directional import LONG_TARGET_COL


def test_prepare_form4_model_features_is_finite_and_detects_exclusive_buy() -> None:
    pool = pd.DataFrame({"date": pd.to_datetime(["2025-01-06", "2025-01-07"]),
                         "symbol": ["AAA", "AAA"]})
    events = pd.DataFrame({
        "symbol": ["AAA"], "available_date": pd.to_datetime(["2025-01-06"]),
        "filing_date": pd.to_datetime(["2025-01-03"]), "transaction_code": ["P"],
        "signed": [1.0], "value": [1_000_000.0], "signed_value": [1_000_000.0],
        "aff_10b5_one": [False], "is_officer": [True], "is_director": [False],
    })
    result = prepare_form4_model_features(pool, events)
    assert list(result.columns[-len(FORM4_COLUMNS):]) == FORM4_COLUMNS
    assert result["form4_exclusive_buy_90d"].eq(1.0).all()
    assert np.isfinite(result[FORM4_COLUMNS].to_numpy()).all()


def test_evaluate_long_score_selects_highest_probability_each_day() -> None:
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2025-01-02"] * 4), "symbol": list("ABCD"),
        "future_return": [0.10, -0.05, 0.01, 0.02],
        LONG_TARGET_COL: [1.0, 0.0, 0.0, 0.0],
        "score": [0.9, 0.1, 0.2, 0.3],
    })
    result = evaluate_long_score(frame, "score", top_fraction=0.25)
    assert result["selected_rows"] == 1
    assert result["top10_precision_long"] == 1.0
    assert result["top10_mean_return"] == 0.10


def test_restrict_experiment_period_removes_feature_warmup_rows() -> None:
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2021-12-31", "2022-01-04", "2025-07-11", "2025-07-14"]),
        "value": [1, 2, 3, 4],
    })
    result = restrict_experiment_period(frame, "2022-01-04", "2025-07-11")
    assert result["value"].tolist() == [2, 3]
