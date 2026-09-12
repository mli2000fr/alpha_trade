from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from ihm.services import batch_management as batches


def _spec(name: str = "daily_bars_sync", **overrides: object) -> batches.BatchSpec:
    values = {
        "name": name, "priority": "P0", "description": "Collecte test", "tables": ("table_a",),
        "enabled": True, "status": "ACTIVE", "provider": "provider", "timezone": "Europe/Paris",
        "run_hours": ("1", "13"), "run_minutes": ("5",), "run_days": ("1", "4"),
        "symbols_file": "config/univers.txt", "log_file": "log/test.txt",
        "task_name": batches.task_name_for_batch(name), "raw_config": {},
    }
    values.update(overrides)
    return batches.BatchSpec(**values)


def test_load_catalogue_sorts_priorities_and_reads_metadata(tmp_path: Path) -> None:
    config = {
        "late": {"priority": "P4", "description": "Late", "tables": "x,y", "enabled": False},
        "urgent": {"priority": "P0", "description": "Urgent", "tables": "z", "run_hours": "2"},
    }
    path = tmp_path / "batch.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    specs = batches.load_batch_specs(str(path))
    assert [item.name for item in specs] == ["urgent", "late"]
    assert specs[0].tables == ("z",)
    assert specs[1].tables == ("x", "y")
    assert not specs[1].runnable


def test_schedule_and_task_names_cover_legacy_and_generic() -> None:
    assert batches.task_name_for_batch("earnings_calendar_sync") == "AlphaTrade-EarningsCalendarSync"
    assert batches.task_name_for_batch("daily_bars_sync") == "AlphaTrade-DailyBarsSync"
    assert batches.format_schedule(_spec()) == "lun, jeu · 01:05, 13:05 · Europe/Paris"


def test_commands_use_force_for_immediate_runs() -> None:
    generic = _spec()
    assert "install_forward_pit_task.ps1" in " ".join(batches.build_install_command(generic))
    assert "-BatchName daily_bars_sync" in batches.format_command(batches.build_install_command(generic))
    assert batches.build_run_command(generic)[-1] == "-Force"
    earnings = _spec("earnings_calendar_sync")
    assert batches.build_run_command(earnings)[-1] == "-Force"
    market = _spec("market_cap_sync")
    assert batches.build_run_command(market)[-1] == "-IgnoreRunDays"


def test_pending_batch_cannot_run() -> None:
    assert not _spec(enabled=False).runnable
    assert not _spec(status="PENDING_PROVIDER").runnable


def test_start_batch_is_async_and_suppresses_duplicate_notification(monkeypatch) -> None:
    captured = {}

    def fake_start(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(run_id="run-1")

    monkeypatch.setattr(batches, "start_managed_run", fake_start)
    record = batches.start_batch(_spec(), db_config={"host": "localhost"})
    assert record.run_id == "run-1"
    assert captured["step_key"] == "batch:daily_bars_sync"
    assert captured["notify_on_finish"] is False
    assert captured["timeout_seconds"] is None


def test_task_scheduler_json_is_normalized(monkeypatch) -> None:
    payload = [{"task_name": "AlphaTrade-DailyBarsSync", "state": "Ready", "enabled": True}]
    monkeypatch.setattr(batches.sys, "platform", "win32")
    monkeypatch.setattr(
        batches.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""),
    )
    states, error = batches.query_windows_task_states()
    assert error is None
    assert states["AlphaTrade-DailyBarsSync"]["state"] == "Ready"


@pytest.mark.e2e
def test_batch_page_renders_without_external_dependencies(monkeypatch) -> None:
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    from ihm.pages import batches as page

    monkeypatch.setattr(page, "load_batch_specs", lambda: (_spec(),))
    monkeypatch.setattr(page, "_task_states", lambda: ({}, None))
    monkeypatch.setattr(page, "_latest_collection_runs", lambda: ({}, None))
    monkeypatch.setattr(page, "list_active_batch_runs", lambda *args: [])
    monkeypatch.setattr(page, "load_pipeline_history", lambda: [])
    monkeypatch.setattr(page, "read_batch_log_tail", lambda spec: "")

    def runner() -> None:
        from ihm.pages import batches as batch_page
        batch_page.render()

    at = AppTest.from_function(runner).run(timeout=15)
    assert not at.exception
    assert any("Batchs planifiés" in title.value for title in at.title)
