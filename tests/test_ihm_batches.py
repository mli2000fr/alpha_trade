from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from ihm.services import batch_management as batches


def _spec(name: str = "daily_bars_sync", **overrides: object) -> batches.BatchSpec:
    values = {
        "name": name, "priority": "P0", "description": "Collecte test",
        "activation_requirement": "", "unlock_steps": (), "tables": ("table_a",),
        "enabled": True, "status": "ACTIVE", "provider": "provider", "timezone": "Europe/Paris",
        "run_hours": ("1", "13"), "run_minutes": ("5",), "run_days": ("1", "4"),
        "symbols_file": "config/univers.txt", "universe_scope": "", "log_file": "log/test.txt",
        "task_name": batches.task_name_for_batch(name), "raw_config": {},
    }
    values.update(overrides)
    return batches.BatchSpec(**values)


def test_load_catalogue_sorts_priorities_and_reads_metadata(tmp_path: Path) -> None:
    config = {
        "late": {
            "priority": "P4", "description": "Late", "tables": "x,y", "enabled": False,
            "activation_requirement": "Choose provider",
            "unlock_steps": ["Choose", "Implement", "Validate"],
        },
        "urgent": {"priority": "P0", "description": "Urgent", "tables": "z", "run_hours": "2"},
    }
    path = tmp_path / "batch.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    specs = batches.load_batch_specs(str(path))
    assert [item.name for item in specs] == ["urgent", "late"]
    assert specs[0].tables == ("z",)
    assert specs[1].tables == ("x", "y")
    assert specs[1].activation_requirement == "Choose provider"
    assert specs[1].unlock_steps == ("Choose", "Implement", "Validate")
    assert not specs[1].runnable


def test_catalogue_exposes_research_notice(tmp_path: Path) -> None:
    path = tmp_path / "batch.yaml"
    path.write_text(yaml.safe_dump({
        "analyst": {"enabled": True, "research_notice": "Yahoo pour la recherche."}
    }), encoding="utf-8")
    spec = batches.load_batch_specs(str(path))[0]
    assert spec.research_notice == "Yahoo pour la recherche."


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
    uninstall = batches.build_uninstall_command(generic)
    assert "uninstall_scheduled_batch_task.ps1" in " ".join(uninstall)
    assert uninstall[-2:] == ["-TaskName", "AlphaTrade-DailyBarsSync"]


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


def test_uninstall_batch_executes_exact_non_shell_command(monkeypatch) -> None:
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="removed", stderr="")

    monkeypatch.setattr(batches.subprocess, "run", fake_run)
    result = batches.uninstall_batch(_spec())
    assert result.ok
    assert captured["command"][-2:] == ["-TaskName", "AlphaTrade-DailyBarsSync"]
    assert "shell" not in captured


def test_bulk_install_and_uninstall_continue_after_one_failure(monkeypatch) -> None:
    specs = [_spec("one"), _spec("two")]

    def fake_install(spec, *, run_as):
        if spec.name == "one":
            raise RuntimeError("boom")
        return batches.CommandResult(True, 0, "ok", "")

    monkeypatch.setattr(batches, "install_batch", fake_install)
    installed = batches.install_all_batches(specs, run_as="System")
    assert not installed["one"].ok
    assert installed["two"].ok

    monkeypatch.setattr(
        batches, "uninstall_batch",
        lambda spec: batches.CommandResult(True, 0, spec.name, ""),
    )
    removed = batches.uninstall_all_batches(specs)
    assert list(removed) == ["one", "two"]
    assert all(result.ok for result in removed.values())


@pytest.mark.e2e
def test_batch_page_renders_without_external_dependencies(monkeypatch) -> None:
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    from ihm.pages import batches as page

    monkeypatch.setattr(
        page,
        "load_batch_specs",
        lambda: (
            _spec(),
            _spec(
                "pending_provider", enabled=False, status="PENDING_PROVIDER",
                activation_requirement="Choisir un fournisseur PIT.",
            ),
        ),
    )
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
    metric_labels = {metric.label for metric in at.metric}
    assert "Exécutables (batch.yaml)" in metric_labels
    assert "Installés mais dormants" in metric_labels
    assert any("Choisir un fournisseur PIT." in error.value for error in at.error)
    button_labels = {button.label for button in at.button}
    assert "♻️ Installer / réinstaller tous" in button_labels
    assert "🗑️ Désinstaller tous les batchs" in button_labels
