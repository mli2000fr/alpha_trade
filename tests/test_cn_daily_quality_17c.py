"""Calendar, source ownership, read-only quality gates and failure evidence."""

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
import yaml

from service.market import cn_daily_quality_17c as quality
from service.market.cn_dragon_tiger_schedule_15d6 import load_calendar

CALENDAR = Path("config/research_cn/sprint15d6_cn_calendar_2026.yaml").resolve()
NOW = datetime(2026, 9, 30, 15, 35, tzinfo=UTC)  # 23:35 Shanghai


def _evidence() -> dict:
    oracle = {"decision_date": "2026-10-08", "previous_session": "2026-09-30",
              "score_available_at_utc": "2026-09-30T11:10:00+00:00",
              "export_published_at_utc": "2026-09-30T11:11:00+00:00",
              "candidate_export_sha256": "next", "quality": {"top20": 2}}
    current = {"decision_date": "2026-09-30",
               "export_published_at_utc": "2026-09-29T11:10:00+00:00",
               "candidate_export_sha256": "current"}
    return {
        "session": "2026-09-30", "next_session": "2026-10-08",
        "audit_at_utc": NOW.isoformat(), "manifest_symbols": 4,
        "chunk_expected": 2, "chunk_recorded": 2, "chunk_completed": 2,
        "chunk_failed": 0, "chunk_manifest_verified": True,
        "d9_run": {"status": "COMPLETED_RESEARCH_ONLY", "completed_chunks": 2},
        "market_session": {"session_status": "open", "close_at_utc": "2026-09-30T07:00:00"},
        "bars": {"bars": 8, "unique_instruments": 8, "invalid_ohlc": 0,
                 "suspended_with_volume": 0, "missing_lineage": 0,
                 "future_lineage": 0, "preclose_lineage": 0},
        "equity_bars": 4,
        "index_symbols": list(quality.INDEX_SYMBOLS),
        "limits": {"count_rows": 4, "unknown": 0},
        "staging": {"daily": {"symbols": 4}, "index_daily": {"symbols": 4},
                    "adj_factor": {"symbols": 1}},
        "factor_matches": 1, "oracle": oracle, "oracle_error": None,
        "current_oracle": current, "current_oracle_error": None,
        "d6_before": {"counts": {"events": 2}},
        "d6_after": {"counts": {"events": 3}},
        "d10": {"status": "INSUFFICIENT_PROSPECTIVE_MATCHED_SAMPLE", "outcomes_loaded": False,
                "database_modified": False, "candidate_sha256": "current"},
        "d10_run": {"status": "COMPLETED_RESEARCH_ONLY", "d7_report_sha256": "reporthash",
                    "d7_pairs_sha256": "pairshash"},
        "d10_report_sha256": "reporthash", "d10_pairs_sha256": "pairshash",
    }


def _configs(tmp_path: Path) -> tuple[Path, Path]:
    batch = tmp_path / "batch_cn.yaml"
    research = tmp_path / "batch.yaml"
    batch.write_text(yaml.safe_dump({
        quality.BATCH_NAME: {"enabled": True, "status": "ACTIVE", "market_code": "CN_A",
            "database_alias": "cn_primary", "calendar": str(CALENDAR),
            "output_root": str(tmp_path / "reports"), "minimum_bar_coverage_ratio": 0.995},
        "cn_daily_market_data_sync": {"enabled": False},
    }), encoding="utf-8")
    research.write_text(yaml.safe_dump({"cn_oracle_prospective_daily": {
        "enabled": True, "status": "RESEARCH_ONLY"}}), encoding="utf-8")
    return batch, research


def test_plan_skips_holiday_and_checks_next_verified_open_session():
    calendar = load_calendar(CALENDAR)
    assert quality.plan(datetime(2026, 10, 1, 11, 35, tzinfo=UTC), calendar)["status"] == "SKIP_CLOSED"
    assert quality.plan(datetime(2026, 9, 30, 10, 0, tzinfo=UTC), calendar)["status"] == "SKIP_BEFORE_WINDOW"
    assert quality.plan(datetime(2026, 9, 30, 11, 35, tzinfo=UTC), calendar)["status"] == "SKIP_BEFORE_WINDOW"
    planned = quality.plan(NOW, calendar)
    assert (planned["previous_session"], planned["next_session"]) == ("2026-09-29", "2026-10-08")


@pytest.mark.parametrize("paris_day", ["2026-02-06", "2026-07-10", "2026-10-09"])
def test_paris_evening_audits_same_friday_cn_session(paris_day):
    now = datetime.fromisoformat(paris_day + "T20:30:00").replace(tzinfo=ZoneInfo("Europe/Paris"))
    planned = quality.plan(now, load_calendar(CALENDAR), audit_previous_day_before_open=True)
    assert planned["status"] == "DUE"
    assert planned["session"] == paris_day
    assert planned["next_session"] > paris_day
    assert quality.plan(now, load_calendar(CALENDAR))["status"] == "SKIP_CLOSED"


def test_overnight_window_never_substitutes_stale_session_or_current_open_day():
    calendar = load_calendar(CALENDAR)
    # Oct 2 in Shanghai: previous civil day is the holiday, not Sep 30.
    holiday = datetime(2026, 10, 1, 20, 30, tzinfo=ZoneInfo("Europe/Paris"))
    planned = quality.plan(holiday, calendar, audit_previous_day_before_open=True)
    assert planned == {"status": "SKIP_CLOSED", "session": "2026-10-01"}
    # At/after decision cutoff the current CN session is not closed yet.
    cutoff = datetime(2026, 10, 9, 9, 15, tzinfo=quality.SHANGHAI)
    planned = quality.plan(cutoff, calendar, audit_previous_day_before_open=True)
    assert planned == {"status": "SKIP_BEFORE_WINDOW", "session": "2026-10-09"}


def test_execute_reads_overnight_option_without_connecting_to_database(tmp_path):
    batch, research = _configs(tmp_path)
    config = yaml.safe_load(batch.read_text(encoding="utf-8"))
    config[quality.BATCH_NAME]["audit_previous_day_before_open"] = True
    batch.write_text(yaml.safe_dump(config), encoding="utf-8")
    now = datetime(2026, 10, 9, 20, 30, tzinfo=ZoneInfo("Europe/Paris"))
    report = quality.execute(batch_config=batch, research_config=research, now=now, dry_run=True)
    assert report["status"] == "DUE"
    assert report["session"] == "2026-10-09"
    assert report["database_modified"] is False


def test_every_gate_passes_on_complete_pit_evidence():
    assert all(check["status"] == "PASS" for check in quality.evaluate(_evidence()))


@pytest.mark.parametrize("change,expected", [
    (lambda e: e["bars"].update(future_lineage=1), "future_lineage"),
    (lambda e: e.update(factor_matches=0), "factors_promoted"),
    (lambda e: e.update(chunk_completed=1), "chunks_complete"),
    (lambda e: e.update(d9_run=None), "d9_owner_completed"),
    (lambda e: e.update(d10=None), "d10_outcome_blind_match"),
    (lambda e: e["oracle"].update(export_published_at_utc="2026-10-01T00:00:00+00:00"), "oracle_next_decision"),
])
def test_critical_failure_cannot_be_hidden(change, expected):
    evidence = copy.deepcopy(_evidence())
    change(evidence)
    failures = {check["name"] for check in quality.evaluate(evidence) if check["status"] == "CRITICAL"}
    assert expected in failures


def test_interrupted_chunks_fail_then_resume_without_rewriting_quality_history():
    evidence = _evidence()
    evidence["chunk_completed"] = 1
    evidence["chunk_failed"] = 1
    assert "chunks_complete" in {check["name"] for check in quality.evaluate(evidence)
                                 if check["status"] == "CRITICAL"}
    evidence["chunk_completed"] = 2
    evidence["chunk_failed"] = 0
    assert all(check["status"] == "PASS" for check in quality.evaluate(evidence))


def test_holiday_and_dry_run_never_open_database(monkeypatch, tmp_path):
    batch, research = _configs(tmp_path)
    monkeypatch.setattr(quality, "get_market_engine", lambda *_args, **_kwargs: pytest.fail("DB opened"))
    assert quality.execute(batch_config=batch, research_config=research,
                           now=datetime(2026, 10, 1, 11, 35, tzinfo=UTC))["status"] == "SKIP_CLOSED"
    assert quality.execute(batch_config=batch, research_config=research,
                           now=NOW, dry_run=True)["status"] == "DUE"
    assert not (tmp_path / "reports").exists()


def test_duplicate_collector_is_rejected_before_database(monkeypatch, tmp_path):
    batch, research = _configs(tmp_path)
    config = yaml.safe_load(batch.read_text(encoding="utf-8"))
    config["cn_daily_market_data_sync"]["enabled"] = True
    batch.write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.setattr(quality, "get_market_engine", lambda *_args, **_kwargs: pytest.fail("DB opened"))
    with pytest.raises(RuntimeError, match="duplicate canonical collector"):
        quality.execute(batch_config=batch, research_config=research, now=NOW)


def test_quality_accepts_d9_only_in_cn_catalog_and_rejects_duplicate(tmp_path):
    batch, research = _configs(tmp_path)
    config = yaml.safe_load(batch.read_text(encoding="utf-8"))
    legacy = yaml.safe_load(research.read_text(encoding="utf-8"))
    config["cn_oracle_prospective_daily"] = {
        **legacy["cn_oracle_prospective_daily"],
        "market_code": "CN_A", "database_alias": "cn_primary",
    }
    research.write_text("{}", encoding="utf-8")
    batch.write_text(yaml.safe_dump(config), encoding="utf-8")
    assert quality.execute(batch_config=batch, research_config=research,
                           now=NOW, dry_run=True)["status"] == "DUE"
    research.write_text(yaml.safe_dump(legacy), encoding="utf-8")
    with pytest.raises(RuntimeError, match="duplicated"):
        quality.execute(batch_config=batch, research_config=research, now=NOW, dry_run=True)


def test_critical_failure_writes_report_and_keeps_database_read_only(monkeypatch, tmp_path):
    batch, research = _configs(tmp_path)
    engine = SimpleNamespace(dispose=lambda: None)
    monkeypatch.setattr(quality, "get_market_engine", lambda *_args, **_kwargs: engine)
    evidence = _evidence()
    evidence["chunk_completed"] = 1
    monkeypatch.setattr(quality, "read_evidence", lambda *_args, **_kwargs: evidence)
    result = quality.execute(batch_config=batch, research_config=research, now=NOW)
    assert result["status"] == "FAILED" and result["failed_count"] == 1
    assert result["database_modified"] is False
    written = json.loads(Path(result["report_path"]).read_text(encoding="utf-8"))
    assert written["checks"] and written["status"] == "FAILED"
    assert (written["market_code"], written["database_alias"]) == ("CN_A", "cn_primary")


def test_source_read_failure_preserves_error_and_alert_counts(monkeypatch, tmp_path):
    batch, research = _configs(tmp_path)
    monkeypatch.setattr(quality, "get_market_engine", lambda *_args, **_kwargs:
                        SimpleNamespace(dispose=lambda: None))
    def broken_source(*_args, **_kwargs):
        raise TimeoutError("BaoStock source state unavailable")
    monkeypatch.setattr(quality, "read_evidence", broken_source)
    report = quality.execute(batch_config=batch, research_config=research, now=NOW)
    assert report["status"] == "FAILED" and report["failed_count"] == 1
    assert "TimeoutError" in report["error_message"]
    assert report["database_modified"] is False


def test_future_run_report_is_not_used_as_past_evidence(tmp_path):
    folder = tmp_path / "runs"
    folder.mkdir()
    (folder / "run-20261001.json").write_text(json.dumps({
        "session": "2026-09-30", "finished_at_utc": "2026-10-01T00:00:00+00:00",
        "status": "COMPLETED_RESEARCH_ONLY"}), encoding="utf-8")
    assert quality._latest_run(folder, "2026-09-30", now=NOW) is None


def test_late_d6_snapshot_is_not_accepted_as_pit_evidence(tmp_path):
    folder = tmp_path / "2026-09-30"
    folder.mkdir()
    (folder / "snapshot-1.json").write_text(json.dumps({
        "observed_at_utc": "2026-10-08T01:16:00+00:00",
        "counts": {"events": 10},
        "collection_context": {"phase": "before_open", "next_open_session": "2026-10-08",
                               "decision_cutoff_shanghai": "2026-10-08T09:15:00+08:00"},
    }), encoding="utf-8")
    assert quality._snapshot(folder, "before_open", next_session="2026-10-08",
                             now=datetime(2026, 10, 8, 2, 0, tzinfo=UTC)) is None
