"""Read-only CN 2026 Oracle export gate."""

from types import SimpleNamespace
from datetime import datetime, timezone

import pandas as pd
import pytest

from service.market import cn_oracle_export_readiness_15d7 as module


class _Result:
    def __init__(self, value):
        self.value = value

    def one(self):
        return self.value

    def scalar_one(self):
        return self.value


class _Connection:
    def __init__(self, populated):
        self.populated = populated

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query):
        sql = str(query)
        if "COUNT(*)" in sql and "stock_bars_daily" in sql:
            return _Result(("2026-09-30", 100) if self.populated else (None, 0))
        if "COUNT(*)" in sql and "market_sessions" in sql:
            return _Result(("2026-09-30", 180) if self.populated else (None, 0))
        if "stock_bars_daily" in sql:
            return _Result("2026-09-30" if self.populated else "2025-12-31")
        return _Result("2026-09-30" if self.populated else "2025-12-31")


class _Engine:
    def __init__(self, populated=False, database="alpha_trade_cn"):
        self.populated = populated
        self.url = SimpleNamespace(database=database)

    def connect(self):
        return _Connection(self.populated)


def _snapshot_mock(monkeypatch):
    monkeypatch.setattr(module, "load_calendar", lambda _path: {})
    monkeypatch.setattr(module, "load_timely_snapshots", lambda _root, _calendar, **_kwargs: (
        {"2026-09-30": {"event_day": "2026-09-29", "cutoff_utc": datetime(2026, 9, 30, 1, 15, tzinfo=timezone.utc)}},
        {"sessions": 1, "source_paths": []},
    ))


def test_missing_database_inputs_fail_closed(monkeypatch, tmp_path):
    _snapshot_mock(monkeypatch)
    report = module.inspect(snapshot_root=tmp_path, calendar_path=tmp_path,
                            oracle_root=tmp_path, engine=_Engine())
    assert report["status"] == "BLOCKED_EXPORT"
    assert "CN_2026_DECISION_CALENDAR_MISSING" in report["reasons"]
    assert "CN_2026_PREDECISION_BARS_MISSING" in report["reasons"]
    assert "NO_VALID_2026_PROSPECTIVE_ORACLE_CANDIDATE_EXPORT" in report["reasons"]
    assert report["database_modified"] is False


def test_validated_candidate_export_is_not_equivalent_to_serving_go(monkeypatch, tmp_path):
    _snapshot_mock(monkeypatch)
    monkeypatch.setattr(module, "load_protocol", lambda _path: {})
    monkeypatch.setattr(module, "load_candidates", lambda *_args: pd.DataFrame({
        "decision_date": ["2026-09-30"] * 2,
        "score_available_at_utc": ["2026-09-29T15:00:00+00:00"] * 2,
        "prior_return_available_at_utc": ["2026-09-29T15:00:00+00:00"] * 2,
    }))
    report = module.inspect(snapshot_root=tmp_path, calendar_path=tmp_path,
                            oracle_root=tmp_path, candidate_export=tmp_path / "candidates.parquet",
                            engine=_Engine(populated=True),
                            now=datetime(2026, 10, 1, tzinfo=timezone.utc))
    assert report["status"] == "INPUTS_PRESENT_REQUIRES_ARTIFACT_AND_PIT_AUDIT"
    assert report["candidate_rows_validated"] == 2
    assert "CN_2026_DECISION_CALENDAR_MISSING" not in report["reasons"]
    assert report["serving_changed"] is False


def test_future_cutoff_preview_validates_export_but_never_claims_matching_ready(monkeypatch, tmp_path):
    monkeypatch.setattr(module, "load_calendar", lambda _path: {})
    monkeypatch.setattr(module, "load_timely_snapshots", lambda _root, _calendar, **_kwargs: (
        {"2026-10-08": {"event_day": "2026-09-30", "cutoff_utc": datetime(2026, 10, 8, 1, 15, tzinfo=timezone.utc)}},
        {"sessions": 1, "future_cutoffs": 1, "source_paths": []},
    ))
    monkeypatch.setattr(module, "load_protocol", lambda _path: {})
    monkeypatch.setattr(module, "load_candidates", lambda *_args: pd.DataFrame({
        "decision_date": ["2026-10-08"],
        "score_available_at_utc": ["2026-09-30T15:00:00+00:00"],
        "prior_return_available_at_utc": ["2026-09-30T15:00:00+00:00"],
    }))
    report = module.inspect(snapshot_root=tmp_path, calendar_path=tmp_path,
                            oracle_root=tmp_path, candidate_export=tmp_path / "candidates.parquet",
                            engine=_Engine(populated=True),
                            now=datetime(2026, 9, 30, 16, 0, tzinfo=timezone.utc))
    assert report["status"] == "WAITING_FOR_DECISION_CUTOFF"
    assert report["candidate_rows_validated"] == 1
    assert report["future_candidate_decisions"] == ["2026-10-08"]
    assert report["serving_changed"] is False


def test_refuses_us_database(monkeypatch, tmp_path):
    _snapshot_mock(monkeypatch)
    with pytest.raises(RuntimeError, match="outside alpha_trade_cn"):
        module.inspect(snapshot_root=tmp_path, calendar_path=tmp_path,
                       oracle_root=tmp_path, engine=_Engine(database="alpha_trade"))
