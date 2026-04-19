from __future__ import annotations

import sys
import time
from pathlib import Path

import ihm.services.process_registry as registry
from ihm.services.pipeline_runner import PipelineLaunchOptions



def _configure_tmp_storage(monkeypatch, tmp_path: Path) -> None:
    runs_dir = tmp_path / "ihm_pipeline_runs"
    history_index = runs_dir / "history_index.json"
    monkeypatch.setattr(registry, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(registry, "HISTORY_INDEX_PATH", history_index)
    registry._ACTIVE_RUNS.clear()



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

    snapshot = None
    for _ in range(40):
        snapshot = registry.poll_pipeline_run(record.run_id)
        if snapshot and snapshot.get("status") not in {"starting", "running"}:
            break
        time.sleep(0.05)

    assert snapshot is not None
    assert snapshot["status"] == "completed"
    assert "hello-stdout" in registry.read_pipeline_logs(record.run_id, "stdout")
    assert "hello-stderr" in registry.read_pipeline_logs(record.run_id, "stderr")
    assert "[stdout]" in registry.read_pipeline_logs(record.run_id, "all")

    history = registry.load_pipeline_history()
    assert any(item["run_id"] == record.run_id for item in history)



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

    snapshot = None
    for _ in range(60):
        snapshot = registry.poll_pipeline_run(record.run_id)
        if snapshot and snapshot.get("status") not in {"starting", "running"}:
            break
        time.sleep(0.05)

    assert snapshot is not None
    assert snapshot["status"] == "stopped"
    assert registry.get_pipeline_run_record(record.run_id) is not None
    assert registry.build_log_download_name(record.run_id, "all").endswith("_all.log")

