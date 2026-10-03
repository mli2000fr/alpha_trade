from copy import deepcopy

import pandas as pd
import pytest
import yaml

from service.fr.economic_preflight_11a import (
    candidate_audit,
    load_protocol,
    readiness_checks,
    score_candidates,
    selection_ledger,
)
from service.fr.universe_contract_6a import ROOT


def cfg():
    return load_protocol(ROOT / "config/research_fr/economic_references_11a_v1.yaml")


def test_unqualified_costs_never_zero_cost_go():
    checks = readiness_checks(0, {"historical_pit_missing": 0, "corporate_action_missing": 0, "economic_return_missing": 0}, cfg()["costs"])
    assert not next(c for c in checks if c["name"] == "commission_spread_slippage_qualified")["passed"]
    assert not next(c for c in checks if c["name"] == "instrument_date_tax_schedule_qualified")["passed"]


def test_future_label_does_not_remove_candidate():
    config = cfg()
    config["folds"] = [6]
    config["min_cross_section"] = 1
    panel = pd.DataFrame({"decision_session_date": ["2024-08-01"] * 2, "research_uid": ["a", "b"],
                          "profile_row_ready": [True, True], "max_input_available_at": ["2024-07-31T08:00:00Z"] * 2,
                          "decision_at": ["2024-08-01T07:00:00Z"] * 2, "oracle_extreme": [1, None],
                          "path_state": ["VALID", "CENSORED"], "offline_qualified": [True, False]})
    predictions = pd.DataFrame({"decision_session_date": ["2024-08-01"], "research_uid": ["a"], "score_trees": [.8], "fold": [6], "phase": ["test"]})
    folds = [{"fold": 6, "dates": {"test_start": "2024-07-29", "test_end": "2025-01-23"}}]
    candidates, report = candidate_audit(panel, predictions, folds, config)
    assert len(candidates) == 2
    assert report[0]["missing_score_rows"] == 1
    assert candidates.loc[candidates.research_uid.eq("b"), "oracle_score_missing"].item()
    with pytest.raises(ValueError, match="dupliquées"):
        candidate_audit(pd.concat([panel, panel]), predictions, folds, config)
    panel.loc[0, "max_input_available_at"] = "2024-08-02T07:00:00Z"
    with pytest.raises(ValueError, match="après décision"):
        candidate_audit(panel, predictions, folds, config)


def test_locked_confirmation_and_portfolio(tmp_path):
    original = cfg()
    for field, value in [("development_end", "2026-06-30"), ("economic_go_allowed", True), ("selection_uses_future_labels", True)]:
        changed = deepcopy(original)
        changed[field] = value
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump(changed), encoding="utf-8")
        with pytest.raises(ValueError):
            load_protocol(path)


def test_unknown_economic_proof_remains_blocked():
    checks = readiness_checks(3, {"historical_pit_missing": 2, "corporate_action_missing": 2, "economic_return_missing": 2}, cfg()["costs"])
    assert not any(c["passed"] for c in checks)


def scored_sample():
    from modelFactory.fr_feature_profile_freeze import FEATURES
    return pd.DataFrame([{**dict.fromkeys(FEATURES, 1.0), "fold": 6, "research_uid": str(i),
                          "provider_symbol": f"S{i}", "decision_session_date": "2024-08-01",
                          "score_trees": .4 if i else float("nan"), "future_return": -999 if i else 999}
                         for i in range(20)])


def test_rescoring_without_fit_and_guard():
    import numpy as np

    class FrozenModel:
        def predict_proba(self, frame):
            assert "future_return" not in frame
            return np.tile([.6, .4], (len(frame), 1))

    panel = scored_sample()
    result = score_candidates(panel, {6: FrozenModel()})
    assert result.score_oracle_research.eq(.4).all()
    assert pd.isna(panel.score_trees.iloc[0])
    panel.loc[1, "score_trees"] = .9
    with pytest.raises(ValueError, match="divergents"):
        score_candidates(panel, {6: FrozenModel()})


def test_intentions_not_fills_and_future_invariant():
    sample = scored_sample()
    sample["score_oracle_research"] = .4
    first = selection_ledger(sample, cfg())
    sample["future_return"] *= -1
    pd.testing.assert_frame_equal(first, selection_ledger(sample, cfg()))
    assert first.groupby("policy").size().to_dict() == {"atr_top20_long": 4, "oracle_top20_long": 4, "uniform_control_long": 20}
    assert first.execution_state.eq("INTENT_NOT_FILL").all()
    assert first.future_label_used.eq(False).all()
