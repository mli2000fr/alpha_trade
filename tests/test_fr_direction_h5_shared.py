import numpy as np
import pandas as pd
import pytest

from modelFactory.fr_direction_h5_shared import (
    causal_oracle_history,
    choose_champion,
    load_config,
    probability_score,
    support_for,
    ternary_target,
    verdict,
)
from modelFactory.fr_oracle_h5_pilot import feature_matrix
from service.fr.universe_contract_6a import ROOT


def cfg():
    return load_config(ROOT / "config/research_fr/direction_h5_shared_v1.yaml")


def test_unknown_target_not_middle_and_relative_deciles():
    s = pd.Series([1, 2, 5, 9, 10, pd.NA], dtype="Int64")
    target = ternary_target(s)
    assert target.iloc[:5].tolist() == [0, 1, 1, 1, 2]
    assert pd.isna(target.iloc[5])
    with pytest.raises(ValueError, match="Invalid"):
        ternary_target(pd.Series([0, 11]))


def test_fixed_branch_latest_causal_fit_not_champion():
    pred = pd.DataFrame(
        {
            "decision_session_date": ["2024-01-31"] * 2,
            "research_uid": ["u"] * 2,
            "fold": [4, 5],
            "phase": ["test", "validation"],
            "score_trees": [0.1, 0.8],
            "score_logistic": [0.99, 0.01],
        }
    )
    folds = [
        {"fold": 4, "champion": "logistic", "dates": {"validation_start": "2023-08-01"}},
        {"fold": 5, "champion": "logistic", "dates": {"validation_start": "2024-01-30"}},
    ]
    out = causal_oracle_history(pred, folds, cfg())
    assert len(out) == 1
    assert out.iloc[0].oracle_fold == 5
    assert out.iloc[0].oracle_score == 0.8
    pd.testing.assert_frame_equal(out, causal_oracle_history(pred.iloc[::-1], folds, cfg()))


def test_future_oracle_model_rejected():
    pred = pd.DataFrame(
        {
            "decision_session_date": ["2024-01-29"],
            "research_uid": ["u"],
            "fold": [5],
            "phase": ["validation"],
            "score_trees": [0.8],
        }
    )
    with pytest.raises(ValueError, match="not available"):
        causal_oracle_history(pred, [{"fold": 5, "dates": {"validation_start": "2024-01-30"}}], cfg())


def test_duplicate_source_phase_rejected():
    pred = pd.DataFrame(
        {
            "decision_session_date": ["2024-01-31"] * 2,
            "research_uid": ["u"] * 2,
            "fold": [5] * 2,
            "phase": ["validation"] * 2,
            "score_trees": [0.8] * 2,
        }
    )
    with pytest.raises(ValueError, match="duplicate"):
        causal_oracle_history(pred, [{"fold": 5, "dates": {"validation_start": "2024-01-30"}}], cfg())


def test_support_does_not_relax_small_train():
    f = pd.DataFrame({"decision_session_date": ["2024-01-01"] * 300, "decile": [1] * 100 + [5] * 100 + [10] * 100})
    support = support_for(f, "train", 0, cfg())
    assert support["state"] == "BLOCKED_DIRECTION_SUPPORT"
    assert "OOF_TRAIN_DATES_BELOW_126" in support["reasons"]


def test_validation_only_selection_and_tie_priority():
    assert choose_champion({"logistic": {"tail_auc": 0.6}, "trees": {"tail_auc": 0.6}}) == "logistic"
    assert choose_champion({"logistic": {"tail_auc": 0.5}, "trees": {"tail_auc": 0.6}}) == "trees"


def test_probability_class_order():
    class Model:
        classes_ = np.array([0, 1, 2])

        def predict_proba(self, features):
            return np.array([[0.2, 0.3, 0.5]])

    model = Model()
    probs, score = probability_score(model, pd.DataFrame({"x": [1]}))
    assert score[0] == pytest.approx(0.3)
    assert probs.sum() == 1
    model.classes_ = np.array([2, 1, 0])
    with pytest.raises(ValueError, match="order"):
        probability_score(model, pd.DataFrame({"x": [1]}))


def test_one_fold_cannot_claim_confirmation():
    metrics = {"tail_auc": 0.9, "means": {"ic": 0.5, "spread": 0.1}}
    plan = {
        "status": "COMPLETED_LIMITED_RESEARCH",
        "champion": "logistic",
        "test": {"logistic": metrics, "return_20": {"tail_auc": 0.5}},
    }
    assert verdict([plan], cfg())["verdict"] == "LIMITED_PILOT_INSUFFICIENT_OOS_FOLDS"
    assert verdict([{"status": "BLOCKED_DIRECTION_SUPPORT"}], cfg())["verdict"] == "BLOCKED_DIRECTION_SUPPORT"
    assert verdict([plan, plan], cfg())["verdict"] == "PILOT_SIGNAL_REQUIRES_CONFIRMATION"


def test_feature_contract_excludes_labels_and_symbol():
    from modelFactory.fr_feature_profile_freeze import FEATURES

    f = pd.DataFrame({c: [1.0] for c in FEATURES})
    f["future_return"], f["decile"], f["research_uid"] = 0.99, 10, "u"
    x = feature_matrix(f)
    assert list(x.columns) == list(FEATURES)
    assert "future_return" not in x and "decile" not in x and "research_uid" not in x


def test_directional_label_purge_at_validation_boundary():
    from modelFactory.fr_labels_review import phase_mask

    f = pd.DataFrame(
        {
            "decision_session_date": ["2023-12-27", "2023-12-28"],
            "label_available_session_date": ["2024-01-29", "2024-01-30"],
            "path_state": ["VALID", "VALID"],
        }
    )
    fold = {"train_start": "2019-01-31", "train_end": "2023-12-28", "validation_start": "2024-01-30"}
    assert phase_mask(f, fold, "train", "2025-12-31").tolist() == [True, False]
