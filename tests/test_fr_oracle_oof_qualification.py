import pandas as pd
import pytest

from modelFactory.fr_oracle_oof_qualification import complete_folds, potential_history, rolling_folds


def test_rolling_preserves_embargo_and_evaluation():
    fold = {
        "fold": 0,
        "train_start": "2020-01-01",
        "train_end": "2020-01-04",
        "validation_start": "2020-01-07",
        "test_start": "2020-01-09",
    }
    result = rolling_folds([fold], [f"2020-01-0{i}" for i in range(1, 8)], 2)[0]
    assert result == {**fold, "train_start": "2020-01-03"}
    assert fold["train_start"] == "2020-01-01"


@pytest.mark.parametrize("sessions,window", [(["b", "a"], 1), (["a", "a"], 1), (["a"], 2), (["a"], 0)])
def test_bad_rolling_inputs(sessions, window):
    with pytest.raises(ValueError):
        rolling_folds([{"train_start": "a", "train_end": "b"}], sessions, window)


def test_complete_requires_three_unique_phases():
    rows = [{"fold": 0, "phase": p, "state": "GO_DATA_SUPPORT_ONLY"} for p in ("train", "validation", "test")]
    assert complete_folds(rows) == [0]
    assert complete_folds(rows[:-1]) == []
    assert complete_folds(rows + [rows[0]]) == []
    rows[0]["state"] = "BLOCKED_DATA_SUPPORT"
    assert complete_folds(rows) == []


def test_potential_history_is_not_oracle_top20_and_deduplicates():
    frame = pd.DataFrame(
        {
            "decision_session_date": ["2025-01-02"] * 20,
            "research_uid": range(20),
            "label_available_session_date": "2025-01-03",
            "path_state": "VALID",
            "profile_row_ready": True,
            "oracle_extreme": 0,
        }
    )
    fold = {
        "fold": 0,
        "validation_start": "2025-01-02",
        "validation_end": "2025-01-02",
        "test_start": "2025-01-03",
        "test_end": "2025-01-03",
    }
    cfg = {"development_end": "2025-12-31", "min_cross_section": 20}
    # Validation maturité stricte : label disponible au test_start exclu.
    assert potential_history(frame, [fold], [0], cfg).empty
    frame["label_available_session_date"] = "2025-01-02"
    result = potential_history(frame, [fold, fold], [0], cfg)
    assert result.candidate_rows.tolist() == [20]
    assert potential_history(frame.iloc[:19], [fold], [0], cfg).empty
