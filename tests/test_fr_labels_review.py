import pandas as pd
import pytest

from modelFactory.fr_labels_review import choose_cases, fold_support, join_panels, phase_mask


def fold():
    return {
        "fold": 0,
        "train_start": "2025-01-02",
        "train_end": "2025-01-02",
        "validation_start": "2025-01-03",
        "validation_end": "2025-01-03",
        "test_start": "2025-01-06",
        "test_end": "2025-01-06",
    }


def config():
    return {
        "development_end": "2025-12-31",
        "min_cross_section": 20,
        "min_session_coverage": 0.8,
        "min_usable_sessions": 40,
        "extreme_cases_per_side_horizon_semester": 2,
    }


def test_maturity_strict_at_split_boundary():
    frame = pd.DataFrame(
        {
            "decision_session_date": ["2025-01-02"] * 3,
            "label_available_session_date": ["2025-01-02", "2025-01-03", None],
            "path_state": ["VALID", "VALID", "IMMATURE"],
        }
    )
    assert phase_mask(frame, fold(), "train", "2025-12-31").tolist() == [True, False, False]


def test_test_target_cannot_reach_confirmation():
    frame = pd.DataFrame(
        {
            "decision_session_date": ["2025-01-06"],
            "label_available_session_date": ["2026-01-02"],
            "path_state": ["VALID"],
        }
    )
    assert not phase_mask(frame, fold(), "test", "2025-12-31").any()


def panels():
    keys = {"decision_session_date": ["2025-01-02"], "research_uid": ["a"]}
    price = pd.DataFrame(
        {
            **keys,
            "profile_row_ready": [True],
            "decision_at": ["2025-01-02T08:00:00Z"],
            "max_input_available_at": ["2025-01-02T08:00:00Z"],
        }
    )
    benchmark = price.assign(common_row_ready=True)
    labels = pd.DataFrame({**keys, "horizon": [5]})
    return labels, price, benchmark


def test_join_one_candidate_many_horizons():
    labels, price, benchmark = panels()
    labels = pd.concat([labels, labels.assign(horizon=10)])
    assert len(join_panels(labels, price, benchmark)) == 2


@pytest.mark.parametrize("problem", ["duplicate", "missing", "future", "subset"])
def test_invalid_support_join(problem):
    labels, price, benchmark = panels()
    if problem == "duplicate":
        labels = pd.concat([labels, labels])
    elif problem == "missing":
        benchmark["research_uid"] = "other"
    elif problem == "future":
        benchmark["max_input_available_at"] = "2025-01-03T08:00:00Z"
    else:
        price["profile_row_ready"] = False
    with pytest.raises(ValueError):
        join_panels(labels, price, benchmark)


def test_extreme_case_selection_keeps_confirmation_blind():
    frame = pd.DataFrame(
        {
            "decision_session_date": ["2025-01-02", "2026-01-02"],
            "label_available_session_date": ["2025-02-01", "2026-02-01"],
            "research_uid": ["a", "a"],
            "provider_symbol": ["A", "A"],
            "horizon": [5, 5],
            "future_return": [0.1, 9.0],
            "path_state": ["VALID", "VALID"],
            "provider_status_current": ["active", "active"],
        }
    )
    selected = choose_cases(frame, config())
    assert selected["decision_session_date"].tolist() == ["2025-01-02"]


def test_labels_restrict_cross_section_after_feature_mask():
    frame = pd.DataFrame(
        {
            "decision_session_date": ["2025-01-02"] * 20,
            "label_available_session_date": ["2025-01-02"] * 20,
            "path_state": "VALID",
            "horizon": 5,
            "profile_row_ready": True,
            "common_row_ready": [True] * 19 + [False],
            "oracle_extreme": [0, 1] * 10,
            "decile": [1, 10] * 10,
            "research_uid": [str(i) for i in range(20)],
            "provider_status_current": "active",
        }
    )
    result = fold_support(frame, [fold()], ["2025-01-02", "2025-01-03", "2025-01-06"], config())
    price = next(x for x in result if x["profile"] == "price_only" and x["phase"] == "train")
    common = next(x for x in result if x["profile"] == "common_price_benchmark" and x["phase"] == "train")
    assert price["oracle_rows"] == 20
    assert common["oracle_rows"] == 0
