from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from modelFactory.fr_labels import load_config, make_fold_plan, path_label, rank_labels


def source():
    sessions = pd.bdate_range("2025-01-01", periods=30).strftime("%Y-%m-%d").tolist()
    bars = {d: {"open": 100, "close": 110, "high": 112, "low": 98, "volume": 1000} for d in sessions}
    proof = {d: {"research_j1_eligible": True, "isin": "FR_TEST"} for d in sessions}
    return sessions, bars, proof


def test_entry_open_exit_h_offset_and_publication():
    sessions, bars, proof = source()
    result = path_label(sessions[0], 5, sessions, bars, proof, "FR_TEST", sessions[-1])
    assert result["future_return"] == pytest.approx(0.1)
    assert result["exit_session_date"] == sessions[5]
    assert result["label_available_session_date"] == sessions[6]
    assert result["path_state"] == "VALID"


def test_immature_exit_present_publication_not_yet_available():
    sessions, bars, proof = source()
    result = path_label(sessions[0], 5, sessions, bars, proof, "FR_TEST", sessions[5])
    assert result["path_state"] == "IMMATURE"
    assert np.isnan(result["future_return"])


@pytest.mark.parametrize("reason", ["hole", "quarantine", "identity", "zero_volume", "invalid_price"])
def test_path_censored_not_bridged(reason):
    sessions, bars, proof = source()
    if reason == "hole":
        bars.pop(sessions[2])
    elif reason == "quarantine":
        proof[sessions[2]]["research_j1_eligible"] = False
    elif reason == "identity":
        proof[sessions[2]]["isin"] = "OTHER"
    elif reason == "zero_volume":
        bars[sessions[2]]["volume"] = 0
    else:
        bars[sessions[2]]["high"] = 90
    result = path_label(sessions[0], 5, sessions, bars, proof, "FR_TEST", sessions[-1])
    assert result["path_state"] == "CENSORED"
    assert np.isnan(result["future_return"])


def cross_section(values):
    return pd.DataFrame(
        {
            "decision_session_date": "2025-01-02",
            "horizon": 5,
            "path_state": "VALID",
            "future_return": values,
            "absolute_terminal_return": np.abs(values),
        }
    )


def test_deciles_d1_down_d10_up_and_amplitude_both_sides():
    frame = rank_labels(cross_section(np.linspace(-0.2, 0.2, 20)))
    assert frame["decile"].tolist() == list(np.repeat(np.arange(1, 11), 2))
    assert frame["oracle_extreme"].eq(1).sum() == 4
    assert frame.iloc[0]["oracle_extreme"] == 1 and frame.iloc[-1]["oracle_extreme"] == 1


def test_ties_no_arbitrary_symbol_breaking():
    frame = rank_labels(cross_section([0.0] * 20))
    assert frame["decile"].isna().all()
    assert frame["oracle_extreme"].isna().all()
    assert frame["oracle_state"].eq("TIE_BOUNDARY").all()


def test_cross_section_minimum_and_censor_coverage():
    frame = cross_section(np.arange(25) / 100)
    frame.loc[:4, "path_state"] = "CENSORED"
    ranked = rank_labels(frame)
    assert ranked["cross_section_state"].eq("QUALIFIED").all()
    assert ranked.loc[:4, "decile"].isna().all()
    frame.loc[5, "path_state"] = "CENSORED"
    assert rank_labels(frame)["decile"].isna().all()


def test_future_after_exit_has_no_effect():
    sessions, bars, proof = source()
    before = path_label(sessions[0], 5, sessions, bars, proof, "FR_TEST", sessions[-1])
    bars[sessions[10]]["close"] = 200
    after = path_label(sessions[0], 5, sessions, bars, proof, "FR_TEST", sessions[-1])
    assert before == after


def test_folds_end_before_confirmation_and_embargo():
    cfg = load_config(Path(__file__).resolve().parents[1] / "config/labels_fr/fr_labels_v1.yaml")
    sessions = pd.bdate_range("2019-01-01", "2026-06-30").strftime("%Y-%m-%d").tolist()
    plan = make_fold_plan(sessions, cfg)
    assert plan
    for fold in plan:
        assert sessions.index(fold["validation_start"]) - sessions.index(fold["train_end"]) == 22
        assert fold["test_end"] < "2026-01-01"
