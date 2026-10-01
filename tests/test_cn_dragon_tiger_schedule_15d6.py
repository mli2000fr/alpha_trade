from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from service.market.cn_dragon_tiger_schedule_15d6 import (
    adjacent_open, execute, is_open, load_calendar, plan,
)

ROOT = Path(__file__).resolve().parents[1]
CALENDAR = ROOT / "config/research_cn/sprint15d6_cn_calendar_2026.yaml"


def _cfg(hour: str, *, enabled: bool = True) -> dict:
    return {"enabled": enabled, "status": "RESEARCH_ONLY",
            "run_hours": hour, "run_minutes": "30"}


def test_official_2026_calendar_and_year_boundary_fail_closed() -> None:
    calendar = load_calendar(CALENDAR)
    assert is_open(date(2026, 9, 30), calendar)
    assert not is_open(date(2026, 10, 1), calendar)
    assert not is_open(date(2026, 10, 7), calendar)
    assert is_open(date(2026, 10, 8), calendar)
    assert adjacent_open(date(2026, 9, 30), calendar, 1) == date(2026, 10, 8)
    assert adjacent_open(date(2026, 10, 8), calendar, -1) == date(2026, 9, 30)
    with pytest.raises(RuntimeError, match="No verified"):
        is_open(date(2027, 1, 4), calendar)


def test_two_windows_target_correct_sessions_and_cutoff() -> None:
    calendar = load_calendar(CALENDAR)
    before = plan("cn_dragon_tiger_before_open", _cfg("8"), calendar,
                  datetime(2026, 9, 30, 0, 30, tzinfo=timezone.utc))
    assert before["status"] == "DUE"
    assert before["target_session"] == "2026-09-29"
    assert before["next_open_session"] == "2026-09-30"
    assert before["decision_cutoff_shanghai"].endswith("09:15:00+08:00")
    after = plan("cn_dragon_tiger_after_close", _cfg("17"), calendar,
                 datetime(2026, 9, 30, 9, 30, tzinfo=timezone.utc))
    assert after["target_session"] == "2026-09-30"
    assert after["next_open_session"] == "2026-10-08"
    assert plan("cn_dragon_tiger_before_open", _cfg("8"), calendar,
                datetime(2026, 10, 1, 0, 30, tzinfo=timezone.utc))["status"] == "SKIP_CLOSED"


def test_disabled_and_manual_timing_never_create_early_observation() -> None:
    calendar = load_calendar(CALENDAR)
    assert plan("cn_dragon_tiger_after_close", _cfg("17", enabled=False), calendar,
                datetime(2026, 9, 30, 9, 30, tzinfo=timezone.utc))["status"] == "SKIP_DISABLED"
    assert plan("cn_dragon_tiger_after_close", _cfg("17"), calendar,
                datetime(2026, 9, 30, 6, 0, tzinfo=timezone.utc),
                force=True)["status"] == "SKIP_BEFORE_MARKET_CLOSE"
    assert plan("cn_dragon_tiger_before_open", _cfg("8"), calendar,
                datetime(2026, 9, 30, 2, 0, tzinfo=timezone.utc),
                force=True)["status"] == "SKIP_AFTER_DECISION_CUTOFF"


def test_due_run_writes_file_ledger_and_skips_duplicate(monkeypatch, tmp_path: Path) -> None:
    from service.market import cn_dragon_tiger_schedule_15d6 as mod
    import yaml

    batch = tmp_path / "batch.yaml"
    batch.write_text(yaml.safe_dump({
        "cn_dragon_tiger_after_close": {
            **_cfg("17"), "output_root": "research"
        }
    }), encoding="utf-8")
    calls = []

    def fake_collect(day, root, *, collection_context):
        calls.append(day)
        folder = root / day.isoformat()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "snapshot-20260930T093000000000Z-unit.json"
        path.write_text(json.dumps({
            "schema": "cn_dragon_tiger_observation_v1",
            "trade_date": day.isoformat(),
            "observed_at_utc": "2026-09-30T09:30:00+00:00",
            "counts": {"events": 5, "first_seen": 5,
                       "removed_since_last": 0, "changed_payload_since_last": 0},
            "collection_context": collection_context,
            "events": [{"code": f"60000{i}"} for i in range(5)],
        }), encoding="utf-8")
        return path

    monkeypatch.setattr(mod, "collect", fake_collect)
    now = datetime(2026, 9, 30, 9, 30, tzinfo=timezone.utc)
    probe = execute("cn_dragon_tiger_after_close", batch, CALENDAR,
                    now=now, probe=True)
    assert probe["status"] == "DUE"
    assert calls == []
    first = execute("cn_dragon_tiger_after_close", batch, CALENDAR, now=now)
    assert first["status"] == "COMPLETED_RESEARCH_ONLY"
    assert first["observed_before_decision_cutoff"] is True
    assert Path(first["report_path"]).exists()
    second = execute("cn_dragon_tiger_after_close", batch, CALENDAR, now=now)
    assert second["status"] == "SKIP_ALREADY_CAPTURED"
    assert execute("cn_dragon_tiger_after_close", batch, CALENDAR,
                   now=now, probe=True)["status"] == "SKIP_ALREADY_CAPTURED"
    assert calls == [date(2026, 9, 30)]
