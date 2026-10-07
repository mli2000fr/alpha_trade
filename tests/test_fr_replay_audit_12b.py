import json

import pandas as pd
import pytest

from modelFactory.fr_fold7_rebuild import sha
from modelFactory.fr_portfolio_replay_12b import audit


def make_evidence(tmp_path):
    preflight, qualification, output = [tmp_path / name for name in ("pre", "qual", "out")]
    for p in (preflight, qualification, output):
        p.mkdir()
    frame = pd.DataFrame([{"fold": 6, "research_uid": "A", "decision_session_date": "2024-09-02"}])
    frame.to_parquet(preflight / "decision_candidates_scored.parquet")
    (preflight / "report.json").write_text(json.dumps({"causal_research_rescoring": {
        "scores_sha256": sha(preflight / "decision_candidates_scored.parquet")}}))
    (qualification / "report.json").write_text(json.dumps({"candidate_paths": 1,
        "preflight_report_sha256": sha(preflight / "report.json")}))
    paths = frame.rename(columns={"decision_session_date": "entry_session"})
    paths["economic_return_ready"] = False
    paths["provider_state"] = "BLOCKED_PRICE_PATH"
    paths.to_parquet(qualification / "holding_path_qualification.parquet")
    return preflight, qualification, output


def test_audit_preserves_bad_paths_without_performance(tmp_path):
    pre, qual, out = make_evidence(tmp_path)
    report = audit(pre, qual, out)
    assert report["net_pnl"] is None and report["executed_orders"] == 0
    assert report["candidate_paths"] == 1 and report["qualified_paths"] == 0
    assert len(pd.read_parquet(out / "execution_evidence_requests.parquet")) == 1
    assert report["future_path_filtering"] is False


def test_audit_rejects_wrong_candidate_identity(tmp_path):
    pre, qual, out = make_evidence(tmp_path)
    paths = pd.read_parquet(qual / "holding_path_qualification.parquet")
    paths["research_uid"] = "OTHER"
    paths.to_parquet(qual / "holding_path_qualification.parquet")
    with pytest.raises(ValueError, match="divergents"):
        audit(pre, qual, out)
