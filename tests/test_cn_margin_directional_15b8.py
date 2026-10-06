"""Non-regression checks for the locked CN margin directional campaign."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modelFactory.cn_margin_directional_15b8 import (
    bootstrap_delta_auc,
    daily_top,
    date_weights,
    finite_features,
    sample_train,
    score_metrics,
    weighted_auc,
)


def small_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "session_date": pd.to_datetime(["2024-01-02"] * 5 + ["2024-02-01"] * 5),
        "instrument_id": list(range(1, 6)) * 2,
        "target": [1, 0, 0, 1, 0, 0, 1, 0, 1, 0],
        "PRICE_BASELINE": [.9, .8, .7, .6, .5, .1, .2, .3, .4, .5],
        "PRICE_MARGIN_FLOW": [.8, .7, .6, .9, .5, .1, .9, .3, .8, .5],
    })


def test_top20_is_per_date_and_tie_stable():
    frame = small_frame()
    selected = daily_top(frame, "PRICE_MARGIN_FLOW", .2)
    assert selected.groupby("session_date").size().tolist() == [1, 1]
    assert selected["instrument_id"].tolist() == [4, 2]
    assert score_metrics(frame, "PRICE_MARGIN_FLOW", .2)["precision_top20_equal_date"] == 1


def test_equal_date_weight_not_row_weight():
    frame = small_frame().iloc[[0, 1, 5, 6, 7, 8, 9]].copy()
    weights = date_weights(frame)
    assert weights[:2].sum() == pytest.approx(1)
    assert weights[2:].sum() == pytest.approx(1)
    assert np.isfinite(weighted_auc(frame, "PRICE_BASELINE"))


def test_bootstrap_preserves_repeated_month_multiplicity():
    frame = small_frame()
    repeated = pd.concat([frame.iloc[:5].assign(bootstrap_draw=0),
                          frame.iloc[:5].assign(bootstrap_draw=1)], ignore_index=True)
    assert date_weights(repeated).sum() == pytest.approx(2)
    result = bootstrap_delta_auc(frame, variant="PRICE_MARGIN_FLOW", reps=10,
                                 alpha_each=.05 / 12, seed=5)
    assert result["months"] == 2
    assert result["repetitions"] == 10
    assert np.isfinite(result["lower_fwer_bound"])


def test_future_metadata_forbidden_and_missing_not_imputed():
    part = pd.DataFrame({"price": [1., 2.], "margin": [0.1, np.nan]})
    with pytest.raises(ValueError, match="Label"):
        finite_features({"train": part}, ["price", "target_d10"])
    with pytest.raises(ValueError, match="Missing"):
        finite_features({"train": part}, ["price", "margin"])


def test_training_sample_deterministic_and_keeps_same_rows():
    frame = pd.DataFrame({"session_date": pd.date_range("2024-01-01", periods=20),
                          "instrument_id": list(range(20))})
    first = sample_train(frame, 10)
    second = sample_train(frame, 10)
    pd.testing.assert_frame_equal(first, second)
    assert len(first) == 10
    assert set(first.index).issubset(frame.index)
