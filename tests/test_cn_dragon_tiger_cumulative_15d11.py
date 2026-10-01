"""Cumulative D7 evidence must remain prospective and outcome-blind."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from service.market import cn_dragon_tiger_cumulative_15d11 as cumulative


PROTOCOL = Path("config/research_cn/sprint15d7_dragon_tiger_protocol.yaml").resolve()
NOW = datetime(2026, 10, 8, 2, 0, tzinfo=UTC)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _oracle(tmp_path: Path) -> tuple[Path, str]:
    folder = tmp_path / "oracle" / "2026-10-08"
    folder.mkdir(parents=True)
    export = folder / "oracle_top20.parquet"
    export.write_bytes(b"frozen-candidates")
    digest = _digest(export)
    (folder / "report.json").write_text(json.dumps({
        "status": "PROSPECTIVE_RESEARCH_ONLY", "decision_date": "2026-10-08",
        "candidate_export_sha256": digest,
        "score_available_at_utc": "2026-09-30T16:27:50+00:00",
        "export_published_at_utc": "2026-09-30T16:27:51+00:00",
        "decision_cutoff_utc": "2026-10-08T01:15:00+00:00",
        "quality": {"top20": 1},
    }), encoding="utf-8")
    return export, digest


def _d10(tmp_path: Path, export: Path, digest: str) -> Path:
    folder = tmp_path / "daily" / "2026-10-08"
    folder.mkdir(parents=True)
    pairs = pd.DataFrame([{
        "decision_date": "2026-10-08", "exposed_exchange": "SSE", "exposed_code": "600519",
        "control_exchange": "SSE", "control_code": "600000",
        "exposed_score_rank": 0.8, "control_score_rank": 0.79,
        "exposed_prior_return_5d": 0.02, "control_prior_return_5d": 0.018,
    }])
    pairs_path = folder / "outcome_blind_matches.parquet"
    pairs.to_parquet(pairs_path, index=False)
    report_path = folder / "report.json"
    report_path.write_text(json.dumps({
        "protocol_sha256": _digest(PROTOCOL), "candidate_sha256": digest,
        "candidate_path": str(export), "outcomes_loaded": False,
        "training_performed": False, "database_modified": False, "serving_changed": False,
        "matching": {"open_sessions": 1, "candidate_rows": 1, "exposed_candidates": 1,
                     "matched_exposed": 1, "matched_pairs": 1},
    }), encoding="utf-8")
    ledger_root = tmp_path / "daily" / "runs"
    ledger_root.mkdir()
    (ledger_root / "run-20261008T013000Z-test.json").write_text(json.dumps({
        "status": "COMPLETED_RESEARCH_ONLY", "session": "2026-10-08",
        "d7_report_sha256": _digest(report_path), "d7_pairs_sha256": _digest(pairs_path),
        "candidate_sha256": digest,
    }), encoding="utf-8")
    return folder


def test_before_cutoff_does_not_claim_available_oracle(tmp_path):
    _oracle(tmp_path)
    result = cumulative.inspect(daily_root=tmp_path / "daily", oracle_root=tmp_path / "oracle",
                                protocol_path=PROTOCOL,
                                now=datetime(2026, 10, 8, 1, 0, tzinfo=UTC))
    assert result["status"] == "WAITING_FOR_FIRST_PROSPECTIVE_MATCH"
    assert result["eligible_oracle_decisions"] == []
    assert result["outcomes_loaded"] is False


def test_missing_daily_match_is_explicit_gap(tmp_path):
    _oracle(tmp_path)
    result = cumulative.inspect(daily_root=tmp_path / "daily", oracle_root=tmp_path / "oracle",
                                protocol_path=PROTOCOL, now=NOW)
    assert result["status"] == "INCOMPLETE_PROSPECTIVE_JOURNAL"
    assert result["missing_daily_matches"] == ["2026-10-08"]
    assert result["gate_checks"]["journal_complete"] is False


def test_valid_one_day_remains_insufficient_and_outcome_blind(tmp_path):
    export, digest = _oracle(tmp_path)
    _d10(tmp_path, export, digest)
    result = cumulative.inspect(daily_root=tmp_path / "daily", oracle_root=tmp_path / "oracle",
                                protocol_path=PROTOCOL, now=NOW)
    assert result["status"] == "INSUFFICIENT_PROSPECTIVE_MATCHED_SAMPLE"
    assert (result["decision_sessions"], result["exposed_candidates"], result["matched_pairs"]) == (1, 1, 1)
    assert result["calendar_quarters"] == ["2026Q4"]
    assert result["outcomes_loaded"] is False
    assert result["training_performed"] is False


def test_tampered_pair_file_is_rejected(tmp_path):
    export, digest = _oracle(tmp_path)
    folder = _d10(tmp_path, export, digest)
    (folder / "outcome_blind_matches.parquet").write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="ledger mismatch"):
        cumulative.inspect(daily_root=tmp_path / "daily", oracle_root=tmp_path / "oracle",
                           protocol_path=PROTOCOL, now=NOW)


def test_future_label_in_pair_file_is_rejected(tmp_path):
    export, digest = _oracle(tmp_path)
    folder = _d10(tmp_path, export, digest)
    path = folder / "outcome_blind_matches.parquet"
    frame = pd.read_parquet(path)
    frame["future_return"] = 0.1
    frame.to_parquet(path, index=False)
    ledger = tmp_path / "daily" / "runs" / "run-20261008T013000Z-test.json"
    payload = json.loads(ledger.read_text(encoding="utf-8"))
    payload["d7_pairs_sha256"] = _digest(path)
    ledger.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Future outcome"):
        cumulative.inspect(daily_root=tmp_path / "daily", oracle_root=tmp_path / "oracle",
                           protocol_path=PROTOCOL, now=NOW)
