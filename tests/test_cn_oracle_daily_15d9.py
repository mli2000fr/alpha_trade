"""Fail-closed daily CN Oracle journal and no-retroactive-score checks."""

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from service.market import cn_oracle_daily_15d9 as daily
from service.market.cn_dragon_tiger_schedule_15d6 import load_calendar


CALENDAR = Path("config/research_cn/sprint15d6_cn_calendar_2026.yaml")


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "batch.yaml"
    path.write_text(yaml.safe_dump({daily.BATCH_NAME: {
        "enabled": True, "status": "RESEARCH_ONLY", "calendar": str(CALENDAR.resolve()),
        "output_root": str(tmp_path / "journal"),
        "oracle_output_root": str(tmp_path / "oracle"),
        "manifest_root": str(tmp_path / "manifests"),
        "chunks_root": str(tmp_path / "chunks"),
        "collection_root": str(tmp_path / "collection"),
        "seed_manifest": str(tmp_path / "seed.txt"), "chunk_size": 25,
    }}), encoding="utf-8")
    return path


def _now() -> datetime:
    return datetime(2026, 9, 30, 11, 0, tzinfo=UTC)  # 19:00 Shanghai


def test_plan_skips_closed_and_before_close_but_selects_next_open_session():
    calendar = load_calendar(CALENDAR)
    assert daily.plan(datetime(2026, 10, 1, 11, 0, tzinfo=UTC), calendar)["status"] == "SKIP_CLOSED"
    assert daily.plan(datetime(2026, 9, 30, 9, 0, tzinfo=UTC), calendar)["status"] == "SKIP_BEFORE_CLOSE"
    planned = daily.plan(_now(), calendar)
    assert planned["decision"] == "2026-10-08"
    assert planned["cutoff_utc"] == "2026-10-08T01:15:00+00:00"


def test_dry_run_does_not_open_database(monkeypatch, tmp_path):
    config = _config(tmp_path)
    monkeypatch.setattr(daily, "get_market_engine", lambda *_args, **_kwargs: pytest.fail("DB opened"))
    report = daily.execute(batch_config=config, now=_now(), dry_run=True)
    assert report["status"] == "DUE"
    assert not (tmp_path / "journal").exists()


def test_existing_valid_export_is_skipped_without_collection(monkeypatch, tmp_path):
    config = _config(tmp_path)
    folder = tmp_path / "oracle" / "2026-10-08"
    folder.mkdir(parents=True)
    content = b"already-published"
    (folder / "oracle_top20.parquet").write_bytes(content)
    (folder / "report.json").write_text(json.dumps({
        "status": "PROSPECTIVE_RESEARCH_ONLY", "decision_date": "2026-10-08",
        "candidate_export_sha256": hashlib.sha256(content).hexdigest(),
        "score_available_at_utc": "2026-09-30T11:00:00+00:00",
        "export_published_at_utc": "2026-09-30T11:01:00+00:00",
        "decision_cutoff_utc": "2026-10-08T01:15:00+00:00",
        "quality": {"top20": 1},
    }), encoding="utf-8")
    monkeypatch.setattr(daily, "get_market_engine", lambda *_args, **_kwargs: pytest.fail("DB opened"))
    report = daily.execute(batch_config=config, now=_now())
    assert report["status"] == "SKIP_ALREADY_PUBLISHED"
    assert report["existing_candidates"] == 1
    assert report["persisted_count"] == 0


def test_incomplete_collection_never_scores(monkeypatch, tmp_path):
    config = _config(tmp_path)
    class Engine:
        url = SimpleNamespace(database="alpha_trade_cn")
        def dispose(self):
            pass
    monkeypatch.setattr(daily, "get_market_engine", lambda *_args, **_kwargs: Engine())
    def fake_prepare(_engine, *, manifest, chunks_root, **_kwargs):
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text("sh.600519", encoding="utf-8")
        chunks_root.mkdir(parents=True, exist_ok=True)
        (chunks_root / "chunk_0000.txt").write_text("sh.600519", encoding="utf-8")
        (chunks_root / "index.json").write_text(json.dumps({
            "symbol_count": 1, "chunk_count": 1, "chunks": ["chunk_0000.txt"],
        }), encoding="utf-8")
    monkeypatch.setattr(daily, "prepare", fake_prepare)
    monkeypatch.setattr(daily, "run_all", lambda *_args, **_kwargs: {
        "status": "PARTIAL", "completed_chunks": 0, "state": "state.json",
    })
    monkeypatch.setattr(daily, "oracle_check", lambda **_kwargs: pytest.fail("Oracle checked"))
    monkeypatch.setattr(daily, "oracle_run", lambda **_kwargs: pytest.fail("Oracle scored"))
    report = daily.execute(batch_config=config, now=_now())
    assert report["status"] == "FAILED"
    assert report["failed_count"] == 1
    assert report["persisted_count"] == 0


def test_completed_collection_scores_once_and_verifies_export(monkeypatch, tmp_path):
    config = _config(tmp_path)
    class Engine:
        url = SimpleNamespace(database="alpha_trade_cn")
        def dispose(self):
            pass
    monkeypatch.setattr(daily, "get_market_engine", lambda *_args, **_kwargs: Engine())
    def fake_prepare(_engine, *, manifest, chunks_root, **_kwargs):
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text("sh.600519", encoding="utf-8")
        chunks_root.mkdir(parents=True, exist_ok=True)
        (chunks_root / "chunk_0000.txt").write_text("sh.600519", encoding="utf-8")
        (chunks_root / "index.json").write_text(json.dumps({
            "symbol_count": 1, "chunk_count": 1, "chunks": ["chunk_0000.txt"],
        }), encoding="utf-8")
    monkeypatch.setattr(daily, "prepare", fake_prepare)
    monkeypatch.setattr(daily, "run_all", lambda *_args, **_kwargs: {
        "status": "COMPLETED", "completed_chunks": 1, "state": "state.json",
    })
    monkeypatch.setattr(daily, "oracle_check", lambda **_kwargs: {
        "status": "READY_TO_SCORE", "known_bar_rows": 2, "reasons": [],
    })
    def fake_score(*, decision_day):
        folder = tmp_path / "oracle" / decision_day.isoformat()
        folder.mkdir(parents=True)
        content = b"new-oracle-score"
        (folder / "oracle_top20.parquet").write_bytes(content)
        (folder / "report.json").write_text(json.dumps({
            "status": "PROSPECTIVE_RESEARCH_ONLY", "decision_date": decision_day.isoformat(),
            "candidate_export_sha256": hashlib.sha256(content).hexdigest(),
            "candidate_export": str(folder / "oracle_top20.parquet"),
            "score_available_at_utc": "2026-09-30T11:00:00+00:00",
            "export_published_at_utc": "2026-09-30T11:01:00+00:00",
            "decision_cutoff_utc": "2026-10-08T01:15:00+00:00",
            "quality": {"top20": 1},
        }), encoding="utf-8")
        return {"quality": {"top20": 1}}
    monkeypatch.setattr(daily, "oracle_run", fake_score)
    report = daily.execute(batch_config=config, now=_now())
    assert report["status"] == "COMPLETED_RESEARCH_ONLY"
    assert report["completed_chunks"] == 1
    assert (report["requested_count"], report["received_count"], report["persisted_count"]) == (1, 2, 1)
    assert report["failed_count"] == 0
    monkeypatch.setattr(daily, "get_market_engine", lambda *_args, **_kwargs: pytest.fail("DB reopened"))
    again = daily.execute(batch_config=config, now=_now())
    assert again["status"] == "SKIP_ALREADY_PUBLISHED"


def test_invalid_existing_export_fails_closed(monkeypatch, tmp_path):
    config = _config(tmp_path)
    folder = tmp_path / "oracle" / "2026-10-08"
    folder.mkdir(parents=True)
    (folder / "oracle_top20.parquet").write_bytes(b"modified")
    (folder / "report.json").write_text(json.dumps({
        "status": "PROSPECTIVE_RESEARCH_ONLY", "decision_date": "2026-10-08",
        "candidate_export_sha256": "0" * 64,
    }), encoding="utf-8")
    monkeypatch.setattr(daily, "get_market_engine", lambda *_args, **_kwargs: pytest.fail("DB opened"))
    report = daily.execute(batch_config=config, now=_now())
    assert report["status"] == "FAILED"
    assert "invalid" in report["error_message"]


def test_partial_collection_resumes_and_publishes_only_after_completion(monkeypatch, tmp_path):
    config = _config(tmp_path)

    class Engine:
        url = SimpleNamespace(database="alpha_trade_cn")
        def dispose(self):
            pass

    monkeypatch.setattr(daily, "get_market_engine", lambda *_args, **_kwargs: Engine())

    def fake_prepare(_engine, *, manifest, chunks_root, **_kwargs):
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text("sh.600519", encoding="utf-8")
        chunks_root.mkdir(parents=True, exist_ok=True)
        (chunks_root / "chunk_0000.txt").write_text("sh.600519", encoding="utf-8")
        (chunks_root / "index.json").write_text(json.dumps({
            "symbol_count": 1, "chunk_count": 1, "chunks": ["chunk_0000.txt"],
        }), encoding="utf-8")

    monkeypatch.setattr(daily, "prepare", fake_prepare)
    attempts = []

    def fake_collect(*_args, **_kwargs):
        attempts.append(1)
        return {"status": "PARTIAL" if len(attempts) == 1 else "COMPLETED",
                "completed_chunks": 0 if len(attempts) == 1 else 1,
                "state": "state.json"}

    monkeypatch.setattr(daily, "run_all", fake_collect)
    monkeypatch.setattr(daily, "oracle_check", lambda **_kwargs: {
        "status": "READY_TO_SCORE", "known_bar_rows": 2, "reasons": [],
    })

    def fake_score(*, decision_day):
        folder = tmp_path / "oracle" / decision_day.isoformat()
        folder.mkdir(parents=True)
        content = b"published-on-retry"
        (folder / "oracle_top20.parquet").write_bytes(content)
        (folder / "report.json").write_text(json.dumps({
            "status": "PROSPECTIVE_RESEARCH_ONLY",
            "decision_date": decision_day.isoformat(),
            "candidate_export_sha256": hashlib.sha256(content).hexdigest(),
            "candidate_export": str(folder / "oracle_top20.parquet"),
            "score_available_at_utc": "2026-09-30T11:00:00+00:00",
            "export_published_at_utc": "2026-09-30T11:01:00+00:00",
            "decision_cutoff_utc": "2026-10-08T01:15:00+00:00",
            "quality": {"top20": 1},
        }), encoding="utf-8")
        return {"quality": {"top20": 1}}

    score_calls = []
    def guarded_score(*, decision_day):
        score_calls.append(decision_day)
        return fake_score(decision_day=decision_day)
    monkeypatch.setattr(daily, "oracle_run", guarded_score)

    failure = daily.execute(batch_config=config, now=_now())
    assert failure["status"] == "FAILED" and failure["completed_chunks"] == 0
    assert not score_calls and not (tmp_path / "oracle" / "2026-10-08").exists()
    success = daily.execute(batch_config=config, now=_now())
    assert success["status"] == "COMPLETED_RESEARCH_ONLY"
    assert len(attempts) == 2 and len(score_calls) == 1
    assert Path(failure["report_path"]).exists() and Path(success["report_path"]).exists()
    assert failure["report_path"] != success["report_path"]
