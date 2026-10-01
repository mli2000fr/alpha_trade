"""Sprint 17-D preflight is read-only and cannot authorize premature cutover."""

import json
from pathlib import Path

import yaml

from service.market.cn_catalog_preflight_17d import (
    REQUIRED_QUALITY_CHECKS,
    RESEARCH_BATCHES,
    inspect,
)


def _configs(tmp_path: Path) -> tuple[Path, Path, Path]:
    us_path, cn_path, root = tmp_path / "batch.yaml", tmp_path / "batch_cn.yaml", tmp_path / "quality"
    us_path.write_text(yaml.safe_dump({name: {"enabled": True, "status": "RESEARCH_ONLY"}
                                      for name in RESEARCH_BATCHES}), encoding="utf-8")
    cn_path.write_text(yaml.safe_dump({
        "defaults": {"database_alias": "cn_primary"},
        "cn_daily_market_data_sync": {"enabled": False},
        "cn_daily_quality_17c": {"enabled": True, "status": "ACTIVE"},
    }), encoding="utf-8")
    return us_path, cn_path, root


def test_no_real_cycle_blocks_cutover_without_changing_configs(tmp_path):
    us, cn, root = _configs(tmp_path)
    before = us.read_bytes(), cn.read_bytes()
    result = inspect(us_batch_path=us, cn_batch_path=cn, quality_root=root)
    assert result["status"] == "BLOCKED"
    assert result["blockers"] == ["first_real_d6_d9_d10_quality_cycle_missing"]
    assert result["catalog_safe"] is True
    assert result["scheduler_actions_verified"] is False
    assert (us.read_bytes(), cn.read_bytes()) == before
    assert not root.exists()


def test_first_complete_cycle_only_opens_manual_task_check(tmp_path):
    us, cn, root = _configs(tmp_path)
    folder = root / "runs"
    folder.mkdir(parents=True)
    (folder / "run-20261008.json").write_text(json.dumps({
        "session": "2026-10-08", "status": "COMPLETED", "failed_count": 0,
        "warning_count": 0, "finished_at_utc": "2026-10-08T16:00:00+00:00",
        "database_modified": False,
        "checks": [{"name": name, "status": "PASS"} for name in REQUIRED_QUALITY_CHECKS],
        "evidence": {
            "d9_run": {"status": "COMPLETED_RESEARCH_ONLY"},
            "d10_run": {"status": "COMPLETED_RESEARCH_ONLY"},
            "d6_before": {}, "d6_after": {},
        },
    }), encoding="utf-8")
    result = inspect(us_batch_path=us, cn_batch_path=cn, quality_root=root)
    assert result["blockers"] == []
    assert result["status"] == "CONFIG_AND_FIRST_CYCLE_READY_MANUAL_TASK_CHECK_REQUIRED"
    assert result["scheduler_actions_verified"] is False


def test_summary_without_full_quality_checks_cannot_authorize_cutover(tmp_path):
    us, cn, root = _configs(tmp_path)
    folder = root / "runs"
    folder.mkdir(parents=True)
    (folder / "run-20261008.json").write_text(json.dumps({
        "session": "2026-10-08", "status": "COMPLETED", "failed_count": 0,
        "warning_count": 0, "finished_at_utc": "2026-10-08T16:00:00+00:00",
        "database_modified": False, "checks": [{"name": "all", "status": "PASS"}],
        "evidence": {
            "d9_run": {"status": "COMPLETED_RESEARCH_ONLY"},
            "d10_run": {"status": "COMPLETED_RESEARCH_ONLY"},
            "d6_before": {}, "d6_after": {},
        },
    }), encoding="utf-8")
    result = inspect(us_batch_path=us, cn_batch_path=cn, quality_root=root)
    assert "first_real_d6_d9_d10_quality_cycle_missing" in result["blockers"]


def test_failed_cycle_duplicate_sections_and_collector_are_blockers(tmp_path):
    us, cn, root = _configs(tmp_path)
    folder = root / "runs"
    folder.mkdir(parents=True)
    (folder / "run-20261008.json").write_text(json.dumps({
        "session": "2026-10-08", "status": "FAILED", "failed_count": 1,
    }), encoding="utf-8")
    payload = yaml.safe_load(cn.read_text(encoding="utf-8"))
    payload[RESEARCH_BATCHES[0]] = {"enabled": True, "status": "RESEARCH_ONLY"}
    payload["cn_daily_market_data_sync"]["enabled"] = True
    cn.write_text(yaml.safe_dump(payload), encoding="utf-8")
    result = inspect(us_batch_path=us, cn_batch_path=cn, quality_root=root)
    assert f"duplicate_section:{RESEARCH_BATCHES[0]}" in result["blockers"]
    assert "duplicate_canonical_collector" in result["blockers"]
    assert "first_real_d6_d9_d10_quality_cycle_missing" in result["blockers"]


def test_pre_october_quality_is_not_a_prospective_gate(tmp_path):
    us, cn, root = _configs(tmp_path)
    folder = root / "runs"
    folder.mkdir(parents=True)
    (folder / "run-20260930.json").write_text(json.dumps({
        "session": "2026-09-30", "status": "COMPLETED", "failed_count": 0,
    }), encoding="utf-8")
    result = inspect(us_batch_path=us, cn_batch_path=cn, quality_root=root)
    assert result["quality_cycle"] is None
    assert result["status"] == "BLOCKED"
