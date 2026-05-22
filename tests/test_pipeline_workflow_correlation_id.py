from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

import ihm.services.process_registry as registry
from ihm.services import pipeline_lock
from ihm.services.pipeline_runner import PipelineLaunchOptions, PipelineStepDefinition


@pytest.fixture(autouse=True)
def _reset_process_registry_state(tmp_path: Path):
    locks_dir = tmp_path / ".locks"
    locks_dir.mkdir(parents=True, exist_ok=True)
    pipeline_lock.set_locks_dir_for_tests(locks_dir)
    registry._ACTIVE_RUNS.clear()
    registry._ACTIVE_WORKFLOWS.clear()
    yield
    for run_id in list(registry._ACTIVE_RUNS.keys()):
        try:
            registry.stop_pipeline_run(run_id)
        except Exception:
            pass
    registry._ACTIVE_RUNS.clear()
    registry._ACTIVE_WORKFLOWS.clear()
    pipeline_lock.set_locks_dir_for_tests(None)


def _configure_tmp_storage(monkeypatch, tmp_path: Path) -> None:
    runs_dir = tmp_path / "ihm_pipeline_runs"
    history_index = runs_dir / "history_index.json"
    monkeypatch.setattr(registry, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(registry, "HISTORY_INDEX_PATH", history_index)
    registry._ACTIVE_RUNS.clear()
    registry._ACTIVE_WORKFLOWS.clear()


def _wait_for_final_snapshot(run_id: str, *, attempts: int = 120, delay: float = 0.05) -> dict[str, object] | None:
    snapshot = None
    for _ in range(attempts):
        snapshot = registry.poll_pipeline_run(run_id)
        if snapshot and snapshot.get("status") not in {"scheduled", "starting", "running"}:
            return snapshot
        time.sleep(delay)
    return snapshot


def test_pipeline_workflow_propagates_workflow_correlation_id(monkeypatch, tmp_path: Path) -> None:
    _configure_tmp_storage(monkeypatch, tmp_path)

    steps = (
        PipelineStepDefinition("step_1", "1", "Step 1", "", "", "—"),
        PipelineStepDefinition("step_2", "2", "Step 2", "", "", "step_1"),
    )
    monkeypatch.setattr(registry, "get_pipeline_workflow_steps", lambda **kwargs: steps)
    monkeypatch.setattr(
        registry,
        "build_pipeline_command",
        lambda step_key, options: [sys.executable, "-c", f"print('{step_key}', flush=True)"],
    )

    workflow_record = registry.start_pipeline_workflow(PipelineLaunchOptions())
    snapshot = _wait_for_final_snapshot(workflow_record.run_id)

    assert snapshot is not None
    assert snapshot["status"] == "completed"
    assert snapshot["workflow_correlation_id"] == workflow_record.run_id

    child_run_ids = snapshot["workflow_child_run_ids"]
    assert isinstance(child_run_ids, list)
    assert len(child_run_ids) == 2

    for child_run_id in child_run_ids:
        child_record = registry.get_pipeline_run_record(str(child_run_id))
        assert child_record is not None
        assert child_record["parent_run_id"] == workflow_record.run_id
        assert child_record["workflow_correlation_id"] == workflow_record.run_id

