from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modelFactory import first_touch_directional as first
from modelFactory.path_aware_directional import LONG_NET_RETURN_COL, SHORT_NET_RETURN_COL


def _bars(kind: str = "flat") -> pd.DataFrame:
    dates = pd.date_range("2024-01-02", periods=50, freq="B")
    frame = pd.DataFrame({
        "date": dates, "symbol": "AAA", "open": 100.0,
        "high": 101.0, "low": 99.0, "close": 100.0,
    })
    # Signal index 20, entrée index 21, première séance observable index 22.
    if kind == "up":
        frame.loc[22, "high"] = 107.0
    elif kind == "down":
        frame.loc[22, "low"] = 93.0
    elif kind == "ambiguous":
        frame.loc[22, ["high", "low"]] = [107.0, 93.0]
    return frame


def _signal(panel: pd.DataFrame) -> pd.Series:
    return panel.loc[panel["date"].eq(pd.Timestamp("2024-01-30"))].iloc[0]


def test_first_touch_config_contract() -> None:
    config = first.FirstTouchConfig()
    assert config.barrier_atr_mult == pytest.approx(3.0)
    assert config.barrier_max_pct == pytest.approx(0.07)
    assert config.max_sessions == 20
    assert config.entry_delay_sessions == 1
    assert config.primary_margin == pytest.approx(0.10)


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("up", first.UP_FIRST),
        ("down", first.DOWN_FIRST),
        ("ambiguous", first.AMBIGUOUS),
        ("flat", first.NO_TOUCH),
    ],
)
def test_build_first_touch_panel_has_four_explicit_outcomes(kind: str, expected: int) -> None:
    panel = first.build_first_touch_panel(
        _bars(kind), first.FirstTouchConfig(max_sessions=5)
    )
    signal = _signal(panel)
    assert signal[first.TARGET_COL] == expected
    assert signal[first.TARGET_NAME_COL] == first.CLASS_NAMES[expected]
    if expected == first.NO_TOUCH:
        assert pd.isna(signal[first.TOUCH_SESSIONS_COL])
    else:
        assert signal[first.TOUCH_SESSIONS_COL] == 1


def test_first_touch_uses_signal_close_atr_and_filters_next_open_gap() -> None:
    bars = _bars("up")
    bars.loc[21, "open"] = 110.0
    panel = first.build_first_touch_panel(
        bars, first.FirstTouchConfig(max_sessions=5, max_entry_gap_pct=0.03)
    )
    signal = _signal(panel)
    assert signal["first_touch_entry_gap_abs"] == pytest.approx(0.10)
    assert not bool(signal["first_touch_entry_gap_eligible"])
    assert pd.isna(signal[first.TARGET_COL])


def test_first_touch_does_not_label_a_right_censored_horizon_as_no_touch() -> None:
    panel = first.build_first_touch_panel(
        _bars("flat"), first.FirstTouchConfig(max_sessions=20)
    )
    tail_signal = panel.iloc[-10]
    assert pd.isna(tail_signal[first.TARGET_COL])
    assert tail_signal[first.TARGET_NAME_COL] is None


def _policy_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.to_datetime(["2024-01-02"] * 4),
        "symbol": ["UP", "DOWN", "AMB", "NONE"],
        first.TARGET_COL: [first.UP_FIRST, first.DOWN_FIRST, first.AMBIGUOUS, first.NO_TOUCH],
        first.P_NO_TOUCH_COL: [0.05, 0.05, 0.05, 0.70],
        first.P_DOWN_COL: [0.10, 0.75, 0.20, 0.10],
        first.P_UP_COL: [0.80, 0.10, 0.20, 0.10],
        first.P_AMBIGUOUS_COL: [0.05, 0.10, 0.55, 0.10],
        first.PREDICTED_CLASS_COL: [first.UP_FIRST, first.DOWN_FIRST, first.AMBIGUOUS, first.NO_TOUCH],
        LONG_NET_RETURN_COL: [0.05, -0.05, -0.01, 0.0],
        SHORT_NET_RETURN_COL: [-0.05, 0.05, -0.01, 0.0],
    })


def test_policy_abstains_on_ambiguous_and_no_touch_winners() -> None:
    policy = first.apply_first_touch_policy(_policy_frame(), margin=0.10)
    assert policy[first.DECISION_COL].tolist() == ["LONG", "SHORT", "ABSTAIN", "ABSTAIN"]
    assert policy[first.CHOSEN_RETURN_COL].dropna().tolist() == pytest.approx([0.05, 0.05])


def test_policy_respects_up_down_probability_margin() -> None:
    frame = _policy_frame().iloc[[0]].copy()
    frame[first.P_UP_COL] = 0.41
    frame[first.P_DOWN_COL] = 0.36
    policy = first.apply_first_touch_policy(frame, margin=0.10)
    assert policy.iloc[0][first.DECISION_COL] == "ABSTAIN"


def test_evaluate_first_touch_oos_perfect_predictions() -> None:
    frame = pd.concat([_policy_frame()] * 20, ignore_index=True)
    frame["date"] = pd.date_range("2024-01-02", periods=len(frame), freq="B")
    metrics = first.evaluate_first_touch_oos(frame)
    primary = metrics["policies"][f"{first.PRIMARY_MARGIN:.2f}"]
    assert metrics["accuracy"] == pytest.approx(1.0)
    assert metrics["balanced_accuracy"] == pytest.approx(1.0)
    assert metrics["macro_f1"] == pytest.approx(1.0)
    assert metrics["directional_auc_up_vs_down"] == pytest.approx(1.0)
    assert primary["coverage"] == pytest.approx(0.5)
    assert primary["decision_precision"] == pytest.approx(1.0)
    assert primary["mean_net_return"] == pytest.approx(0.05)


def test_invalid_first_touch_config_is_rejected() -> None:
    with pytest.raises(ValueError):
        first.FirstTouchConfig(barrier_atr_mult=0)
    with pytest.raises(ValueError):
        first.FirstTouchConfig(entry_delay_sessions=0)
