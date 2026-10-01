"""Daily D7 research matching is prospective, immutable and outcome-blind."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from service.market import cn_dragon_tiger_daily_15d10 as daily
from service.market.cn_dragon_tiger_schedule_15d6 import load_calendar


CALENDAR = Path("config/research_cn/sprint15d6_cn_calendar_2026.yaml").resolve()
NOW = datetime(2026, 10, 8, 1, 30, tzinfo=UTC)  # 09:30 Shanghai


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "batch.yaml"
    path.write_text(yaml.safe_dump({daily.BATCH_NAME: {
        "enabled": True, "status": "RESEARCH_ONLY", "calendar": str(CALENDAR),
        "protocol": "protocol.yaml", "snapshot_root": "snapshots",
        "oracle_output_root": "oracle", "output_root": "matching",
    }}), encoding="utf-8")
    return path


def _published(tmp_path: Path) -> str:
    folder = tmp_path / "oracle" / "2026-10-08"
    folder.mkdir(parents=True)
    data = b"candidate-export"
    (folder / "oracle_top20.parquet").write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    (folder / "report.json").write_text(json.dumps({
        "status": "PROSPECTIVE_RESEARCH_ONLY", "decision_date": "2026-10-08",
        "candidate_export_sha256": digest,
        "score_available_at_utc": "2026-09-30T16:27:50+00:00",
        "export_published_at_utc": "2026-09-30T16:27:51+00:00",
        "decision_cutoff_utc": "2026-10-08T01:15:00+00:00",
        "quality": {"top20": 1},
    }), encoding="utf-8")
    return digest


def test_plan_waits_for_real_open_session_and_cutoff():
    calendar = load_calendar(CALENDAR)
    assert daily.plan(datetime(2026, 10, 1, 1, 30, tzinfo=UTC), calendar)["status"] == "SKIP_CLOSED"
    assert daily.plan(datetime(2026, 10, 8, 1, 14, tzinfo=UTC), calendar)["status"] == "SKIP_BEFORE_CUTOFF"
    assert daily.plan(NOW, calendar) == {"status": "DUE", "session": "2026-10-08"}


def test_dry_run_does_not_match_or_write(monkeypatch, tmp_path):
    config = _config(tmp_path)
    monkeypatch.setattr(daily, "audit", lambda **_kwargs: pytest.fail("matched"))
    result = daily.execute(batch_config=config, now=NOW, dry_run=True)
    assert result["status"] == "DUE"
    assert result["candidate_exists"] is False
    assert not (tmp_path / "matching").exists()


def test_missing_candidate_fails_without_fabricating_output(tmp_path):
    result = daily.execute(batch_config=_config(tmp_path), now=NOW)
    assert result["status"] == "FAILED"
    assert not (tmp_path / "matching" / "2026-10-08").exists()


def test_timely_export_is_matched_once_without_labels(monkeypatch, tmp_path):
    config = _config(tmp_path)
    digest = _published(tmp_path)
    def fake_audit(*, candidates_path, output, now, **_kwargs):
        assert candidates_path == tmp_path / "oracle" / "2026-10-08" / "oracle_top20.parquet"
        assert now == NOW
        output.mkdir(parents=True)
        report = {"candidate_sha256": digest, "status": "INSUFFICIENT_PROSPECTIVE_MATCHED_SAMPLE",
                  "matching": {"candidate_rows": 1, "matched_pairs": 0},
                  "outcomes_loaded": False, "database_modified": False}
        (output / "report.json").write_text(json.dumps(report), encoding="utf-8")
        (output / "outcome_blind_matches.parquet").write_bytes(b"mock-parquet")
        return report
    monkeypatch.setattr(daily, "audit", fake_audit)
    result = daily.execute(batch_config=config, now=NOW)
    assert result["status"] == "COMPLETED_RESEARCH_ONLY"
    assert result["matching_status"] == "INSUFFICIENT_PROSPECTIVE_MATCHED_SAMPLE"
    assert (result["requested_count"], result["received_count"], result["persisted_count"]) == (1, 1, 0)
    monkeypatch.setattr(daily, "audit", lambda **_kwargs: pytest.fail("matched twice"))
    assert daily.execute(batch_config=config, now=NOW)["status"] == "SKIP_ALREADY_MATCHED"


def test_changed_candidate_cannot_reuse_prior_match(tmp_path):
    config = _config(tmp_path)
    _published(tmp_path)
    output = tmp_path / "matching" / "2026-10-08"
    output.mkdir(parents=True)
    (output / "report.json").write_text(json.dumps({"candidate_sha256": "wrong"}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="mismatch"):
        daily.execute(batch_config=config, now=NOW)
