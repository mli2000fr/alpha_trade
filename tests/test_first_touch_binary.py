from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modelFactory import first_touch_binary as binary
from modelFactory import first_touch_directional as first
from modelFactory.path_aware_directional import LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL


def test_add_binary_target_excludes_no_touch_and_ambiguous() -> None:
    frame = pd.DataFrame({
        first.TARGET_COL: [
            first.DOWN_FIRST, first.UP_FIRST, first.NO_TOUCH, first.AMBIGUOUS,
        ]
    })
    result = binary.add_binary_target(frame)
    assert result[binary.BINARY_TARGET_COL].iloc[:2].tolist() == [0.0, 1.0]
    assert result[binary.BINARY_TARGET_COL].iloc[2:].isna().all()


class _DummyBinaryModel:
    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        up = np.asarray([0.8, 0.2, 0.7, 0.3], dtype=float)[:len(frame)]
        return np.column_stack([1.0 - up, up])


def test_score_binary_model_emits_comparable_e4_schema() -> None:
    frame = pd.DataFrame({"feature": [1.0, 2.0, 3.0, 4.0]})
    result = binary.score_binary_model(_DummyBinaryModel(), frame, ["feature"], [])
    assert result[first.P_UP_COL].tolist() == pytest.approx([0.8, 0.2, 0.7, 0.3])
    assert (result[first.P_UP_COL] + result[first.P_DOWN_COL]).tolist() == pytest.approx([1] * 4)
    assert result[first.P_NO_TOUCH_COL].eq(0).all()
    assert result[first.P_AMBIGUOUS_COL].eq(0).all()
    assert result[first.PREDICTED_CLASS_COL].tolist() == [
        first.UP_FIRST, first.DOWN_FIRST, first.UP_FIRST, first.DOWN_FIRST,
    ]


def test_binary_policy_keeps_rare_truth_classes_in_oos_denominator() -> None:
    frame = pd.DataFrame({
        "date": pd.date_range("2024-01-02", periods=4, freq="B"),
        "symbol": ["UP", "DOWN", "NONE", "AMB"],
        first.TARGET_COL: [
            first.UP_FIRST, first.DOWN_FIRST, first.NO_TOUCH, first.AMBIGUOUS,
        ],
        first.P_UP_COL: [0.80, 0.20, 0.80, 0.20],
        first.P_DOWN_COL: [0.20, 0.80, 0.20, 0.80],
        first.P_NO_TOUCH_COL: 0.0,
        first.P_AMBIGUOUS_COL: 0.0,
        first.PREDICTED_CLASS_COL: [
            first.UP_FIRST, first.DOWN_FIRST, first.UP_FIRST, first.DOWN_FIRST,
        ],
        LONG_NET_RETURN_COL: [0.05, -0.05, 0.0, 0.0],
        SHORT_NET_RETURN_COL: [-0.05, 0.05, 0.0, 0.0],
    })
    metrics = first.evaluate_first_touch_oos(frame)
    primary = metrics["policies"][f"{first.PRIMARY_MARGIN:.2f}"]
    assert metrics["rows"] == 4
    assert primary["coverage"] == pytest.approx(1.0)
    assert primary["directional_truth_share"] == pytest.approx(0.5)
    assert primary["decision_precision"] == pytest.approx(0.5)


def test_binary_contract_has_no_class_weight_parameter() -> None:
    source = binary._fit_binary.__code__.co_consts
    assert "Balanced" not in source
