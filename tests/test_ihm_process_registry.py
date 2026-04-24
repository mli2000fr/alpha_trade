from __future__ import annotations

import sys
import time
from pathlib import Path

import ihm.services.process_registry as registry
from ihm.services.pipeline_runner import PipelineLaunchOptions, PipelineStepDefinition



def _configure_tmp_storage(monkeypatch, tmp_path: Path) -> None:
    runs_dir = tmp_path / "ihm_pipeline_runs"
    history_index = runs_dir / "history_index.json"
    monkeypatch.setattr(registry, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(registry, "HISTORY_INDEX_PATH", history_index)
    registry._ACTIVE_RUNS.clear()
    registry._ACTIVE_WORKFLOWS.clear()


def _wait_for_final_snapshot(run_id: str, *, attempts: int = 80, delay: float = 0.05) -> dict[str, object] | None:
    snapshot = None
    for _ in range(attempts):
        snapshot = registry.poll_pipeline_run(run_id)
        if snapshot and snapshot.get("status") not in {"starting", "running"}:
            return snapshot
        time.sleep(delay)
    return snapshot



def test_background_run_completes_and_persists_logs(monkeypatch, tmp_path: Path) -> None:
    _configure_tmp_storage(monkeypatch, tmp_path)

    command = [
        sys.executable,
        "-c",
        (
            "import sys, time; "
            "print('hello-stdout', flush=True); "
            "sys.stderr.write('hello-stderr\\n'); sys.stderr.flush(); "
            "time.sleep(0.2); "
            "print('done', flush=True)"
        ),
    ]
    monkeypatch.setattr(registry, "build_pipeline_command", lambda step_key, options: command)

    record = registry.start_pipeline_run("fake_step", "Fake Step", PipelineLaunchOptions())

    snapshot = _wait_for_final_snapshot(record.run_id, attempts=40)

    assert snapshot is not None
    assert snapshot["status"] == "completed"
    assert "hello-stdout" in registry.read_pipeline_logs(record.run_id, "stdout")
    assert "hello-stderr" in registry.read_pipeline_logs(record.run_id, "stderr")
    assert "[stdout]" in registry.read_pipeline_logs(record.run_id, "all")

    history = registry.load_pipeline_history()
    assert any(item["run_id"] == record.run_id for item in history)


def test_background_run_captures_structured_run_summary(monkeypatch, tmp_path: Path) -> None:
    _configure_tmp_storage(monkeypatch, tmp_path)

    command = [
        sys.executable,
        "-c",
        (
            "import json; "
            "print('before', flush=True); "
            "print('::alpha_trade_run_summary::' + json.dumps({'targeted_symbols': 3, 'successful_symbols': 2, 'history_status_counts': {'ready': 2, 'provider_error': 1}}), flush=True); "
            "print('after', flush=True)"
        ),
    ]
    monkeypatch.setattr(registry, "build_pipeline_command", lambda step_key, options: command)

    record = registry.start_pipeline_run("fake_summary_step", "Fake Summary Step", PipelineLaunchOptions())
    snapshot = _wait_for_final_snapshot(record.run_id, attempts=40)

    assert snapshot is not None
    assert snapshot["status"] == "completed"
    assert snapshot["run_summary"] == {
        "targeted_symbols": 3,
        "successful_symbols": 2,
        "history_status_counts": {"ready": 2, "provider_error": 1},
    }
    logs = registry.read_pipeline_logs(record.run_id, "stdout")
    assert "before" in logs
    assert "after" in logs
    assert registry.RUN_SUMMARY_PREFIX not in logs



def test_background_run_can_be_stopped(monkeypatch, tmp_path: Path) -> None:
    _configure_tmp_storage(monkeypatch, tmp_path)

    command = [
        sys.executable,
        "-c",
        (
            "import time; "
            "print('started', flush=True); "
            "time.sleep(10)"
        ),
    ]
    monkeypatch.setattr(registry, "build_pipeline_command", lambda step_key, options: command)

    record = registry.start_pipeline_run("long_step", "Long Step", PipelineLaunchOptions())
    time.sleep(0.2)
    assert registry.stop_pipeline_run(record.run_id) is True

    snapshot = _wait_for_final_snapshot(record.run_id, attempts=60)

    assert snapshot is not None
    assert snapshot["status"] == "stopped"
    assert registry.get_pipeline_run_record(record.run_id) is not None
    assert registry.build_log_download_name(record.run_id, "all").endswith("_all.log")


def test_pipeline_workflow_runs_steps_in_order_and_aggregates_logs(monkeypatch, tmp_path: Path) -> None:
    _configure_tmp_storage(monkeypatch, tmp_path)

    steps = (
        PipelineStepDefinition("step_1", "1", "Step 1", "", "", "—"),
        PipelineStepDefinition("step_2", "2", "Step 2", "", "", "step_1"),
        PipelineStepDefinition("step_3", "3", "Step 3", "", "", "step_2"),
    )
    monkeypatch.setattr(registry, "get_pipeline_steps", lambda: steps)
    monkeypatch.setattr(
        registry,
        "build_pipeline_command",
        lambda step_key, options: [
            sys.executable,
            "-c",
            "import sys; print(f'out:{sys.argv[1]}', flush=True); sys.stderr.write(f'err:{sys.argv[1]}\\n'); sys.stderr.flush()",
            step_key,
        ],
    )

    record = registry.start_pipeline_workflow(PipelineLaunchOptions())
    snapshot = _wait_for_final_snapshot(record.run_id, attempts=120)

    assert snapshot is not None
    assert snapshot["status"] == "completed"
    assert snapshot["run_kind"] == "workflow"
    assert snapshot["workflow_completed_steps"] == 3
    assert snapshot["workflow_total_steps"] == 3
    child_run_ids = snapshot["workflow_child_run_ids"]
    assert isinstance(child_run_ids, list)
    assert child_run_ids
    assert len(child_run_ids) == 3

    logs = registry.read_pipeline_logs(record.run_id, "all")
    assert "Démarrage du workflow complet" in logs
    assert "step_1" in logs
    assert "step_2" in logs
    assert "step_3" in logs


def test_pipeline_workflow_stops_on_failed_step(monkeypatch, tmp_path: Path) -> None:
    _configure_tmp_storage(monkeypatch, tmp_path)

    steps = (
        PipelineStepDefinition("step_ok", "1", "Step OK", "", "", "—"),
        PipelineStepDefinition("step_fail", "2", "Step Fail", "", "", "step_ok"),
        PipelineStepDefinition("step_skip", "3", "Step Skip", "", "", "step_fail"),
    )
    monkeypatch.setattr(registry, "get_pipeline_steps", lambda: steps)

    def _command(step_key: str, options: PipelineLaunchOptions) -> list[str]:
        if step_key == "step_fail":
            return [
                sys.executable,
                "-c",
                "import sys; sys.stderr.write('boom\\n'); sys.stderr.flush(); raise SystemExit(1)",
            ]
        return [sys.executable, "-c", f"print('ok:{step_key}', flush=True)"]

    monkeypatch.setattr(registry, "build_pipeline_command", _command)

    record = registry.start_pipeline_workflow(PipelineLaunchOptions())
    snapshot = _wait_for_final_snapshot(record.run_id, attempts=120)

    assert snapshot is not None
    assert snapshot["status"] == "failed"
    assert snapshot["workflow_completed_steps"] == 1
    child_run_ids = snapshot["workflow_child_run_ids"]
    assert isinstance(child_run_ids, list)
    assert len(child_run_ids) == 2

    logs = registry.read_pipeline_logs(record.run_id, "all")
    assert "boom" in logs
    assert "step_skip" not in logs


def test_pipeline_workflow_can_be_stopped(monkeypatch, tmp_path: Path) -> None:
    _configure_tmp_storage(monkeypatch, tmp_path)

    steps = (
        PipelineStepDefinition("slow_step", "1", "Slow Step", "", "", "—"),
        PipelineStepDefinition("never_reached", "2", "Never Reached", "", "", "slow_step"),
    )
    monkeypatch.setattr(registry, "get_pipeline_steps", lambda: steps)
    monkeypatch.setattr(
        registry,
        "build_pipeline_command",
        lambda step_key, options: [
            sys.executable,
            "-c",
            "import time; print('started', flush=True); time.sleep(10)",
        ],
    )

    record = registry.start_pipeline_workflow(PipelineLaunchOptions())
    time.sleep(0.3)
    assert registry.stop_pipeline_run(record.run_id) is True

    snapshot = _wait_for_final_snapshot(record.run_id, attempts=120)

    assert snapshot is not None
    assert snapshot["status"] == "stopped"
    assert snapshot["workflow_completed_steps"] == 0


