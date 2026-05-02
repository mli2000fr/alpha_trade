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


def test_start_managed_run_supports_non_pipeline_commands(monkeypatch, tmp_path: Path) -> None:
    _configure_tmp_storage(monkeypatch, tmp_path)

    record = registry.start_managed_run(
        step_key="watcher_local_service",
        step_label="Watcher local",
        command=[sys.executable, "-c", "print('watcher-local-ok', flush=True)"],
        account_id="acct-1",
    )

    snapshot = _wait_for_final_snapshot(record.run_id, attempts=40)

    assert snapshot is not None
    assert snapshot["status"] == "completed"
    assert snapshot["step_key"] == "watcher_local_service"
    assert "watcher-local-ok" in registry.read_pipeline_logs(record.run_id, "stdout")



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
    monkeypatch.setattr(registry, "get_pipeline_workflow_steps", lambda **kwargs: steps)
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


def test_pipeline_workflow_aggregates_child_run_summaries(monkeypatch, tmp_path: Path) -> None:
    _configure_tmp_storage(monkeypatch, tmp_path)

    steps = (
        PipelineStepDefinition("step_import", "1", "Import", "", "", "—"),
        PipelineStepDefinition("step_sanitize", "2", "Sanitize", "", "", "step_import"),
    )
    monkeypatch.setattr(registry, "get_pipeline_workflow_steps", lambda **kwargs: steps)

    def _command(step_key: str, options: PipelineLaunchOptions) -> list[str]:
        if step_key == "step_import":
            payload = (
                "import json; "
                "print('::alpha_trade_run_summary::' + json.dumps({'targeted_symbols': 3, 'successful_symbols': 2, 'history_status_counts': {'ready': 2, 'provider_error': 1}}), flush=True)"
            )
        else:
            payload = (
                "import json; "
                "print('::alpha_trade_run_summary::' + json.dumps({'targeted_symbols': 3, 'successful_symbols': 3, 'status_breakdown': {'success': 3, 'failed': 0}}), flush=True)"
            )
        return [sys.executable, "-c", payload]

    monkeypatch.setattr(registry, "build_pipeline_command", _command)

    record = registry.start_pipeline_workflow(PipelineLaunchOptions())
    snapshot = _wait_for_final_snapshot(record.run_id, attempts=120)

    assert snapshot is not None
    assert snapshot["status"] == "completed"
    raw_run_summary = snapshot.get("run_summary")
    assert isinstance(raw_run_summary, dict)
    run_summary = raw_run_summary
    assert run_summary["workflow_steps_with_summary"] == 2
    assert run_summary["targeted_symbols"] == 6
    assert run_summary["successful_symbols"] == 5
    assert run_summary["history_status_counts"] == {"ready": 2, "provider_error": 1}
    assert run_summary["status_breakdown"] == {"success": 3, "failed": 0}
    assert len(run_summary["workflow_step_summaries"]) == 2


def test_pipeline_workflow_stops_on_failed_step(monkeypatch, tmp_path: Path) -> None:
    _configure_tmp_storage(monkeypatch, tmp_path)

    steps = (
        PipelineStepDefinition("step_ok", "1", "Step OK", "", "", "—"),
        PipelineStepDefinition("step_fail", "2", "Step Fail", "", "", "step_ok"),
        PipelineStepDefinition("step_skip", "3", "Step Skip", "", "", "step_fail"),
    )
    monkeypatch.setattr(registry, "get_pipeline_workflow_steps", lambda **kwargs: steps)

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
    monkeypatch.setattr(registry, "get_pipeline_workflow_steps", lambda **kwargs: steps)
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


def test_pipeline_workflow_exposes_current_child_run_id_while_running(monkeypatch, tmp_path: Path) -> None:
    _configure_tmp_storage(monkeypatch, tmp_path)

    steps = (
        PipelineStepDefinition("slow_step", "1", "Slow Step", "", "", "—"),
        PipelineStepDefinition("never_reached", "2", "Never Reached", "", "", "slow_step"),
    )
    monkeypatch.setattr(registry, "get_pipeline_workflow_steps", lambda **kwargs: steps)
    monkeypatch.setattr(
        registry,
        "build_pipeline_command",
        lambda step_key, options: [
            sys.executable,
            "-c",
            "import time; print('started', flush=True); time.sleep(1)",
        ],
    )

    record = registry.start_pipeline_workflow(PipelineLaunchOptions())

    running_snapshot = None
    for _ in range(40):
        snapshot = registry.poll_pipeline_run(record.run_id)
        if snapshot and snapshot.get("workflow_current_child_run_id"):
            running_snapshot = snapshot
            break
        time.sleep(0.05)

    assert running_snapshot is not None
    assert running_snapshot["status"] in {"starting", "running"}
    assert isinstance(running_snapshot["workflow_current_child_run_id"], str)
    assert running_snapshot["workflow_current_child_run_id"] in running_snapshot["workflow_child_run_ids"]

    final_snapshot = _wait_for_final_snapshot(record.run_id, attempts=120)
    assert final_snapshot is not None
    assert final_snapshot["status"] == "completed"
    assert final_snapshot["workflow_current_child_run_id"] is None


def test_pipeline_workflow_skips_ml_train_when_not_requested(monkeypatch, tmp_path: Path) -> None:
    _configure_tmp_storage(monkeypatch, tmp_path)

    steps = (
        PipelineStepDefinition("step_1", "1", "Step 1", "", "", "—"),
        PipelineStepDefinition("ml_train", "9", "ML Train", "", "", "step_1"),
        PipelineStepDefinition("step_10", "10", "Step 10", "", "", "ml_train"),
    )
    monkeypatch.setattr(
        registry,
        "get_pipeline_workflow_steps",
        lambda **kwargs: tuple(step for step in steps if kwargs.get("include_ml_train", True) or step.key != "ml_train"),
    )
    monkeypatch.setattr(
        registry,
        "build_pipeline_command",
        lambda step_key, options: [sys.executable, "-c", f"print('{step_key}', flush=True)"],
    )

    record = registry.start_pipeline_workflow(PipelineLaunchOptions(), include_ml_train=False)
    snapshot = _wait_for_final_snapshot(record.run_id, attempts=120)

    assert snapshot is not None
    assert snapshot["status"] == "completed"
    assert snapshot["workflow_total_steps"] == 2
    assert snapshot["command"] == ["step_1", "step_10"]
    assert "1 → 12" in str(snapshot["step_label"])
    assert "sans étape 9" in str(snapshot["step_label"])
    logs = registry.read_pipeline_logs(record.run_id, "all")
    assert "step_1" in logs
    assert "step_10" in logs
    assert "ml_train" not in logs


def test_pipeline_workflow_includes_ml_train_when_requested(monkeypatch, tmp_path: Path) -> None:
    _configure_tmp_storage(monkeypatch, tmp_path)

    steps = (
        PipelineStepDefinition("step_1", "1", "Step 1", "", "", "—"),
        PipelineStepDefinition("ml_train", "9", "ML Train", "", "", "step_1"),
        PipelineStepDefinition("step_10", "10", "Step 10", "", "", "ml_train"),
    )
    monkeypatch.setattr(registry, "get_pipeline_workflow_steps", lambda **kwargs: steps)
    monkeypatch.setattr(
        registry,
        "build_pipeline_command",
        lambda step_key, options: [sys.executable, "-c", f"print('{step_key}', flush=True)"],
    )

    record = registry.start_pipeline_workflow(PipelineLaunchOptions(), include_ml_train=True)
    snapshot = _wait_for_final_snapshot(record.run_id, attempts=120)

    assert snapshot is not None
    assert snapshot["status"] == "completed"
    assert snapshot["workflow_total_steps"] == 3
    assert snapshot["command"] == ["step_1", "ml_train", "step_10"]
    assert "1 → 12" in str(snapshot["step_label"])
    assert "avec étape 9" in str(snapshot["step_label"])
    logs = registry.read_pipeline_logs(record.run_id, "all")
    assert "ml_train" in logs


def test_pipeline_workflow_can_start_at_step_3_and_append_corporate_actions(monkeypatch, tmp_path: Path) -> None:
    _configure_tmp_storage(monkeypatch, tmp_path)

    steps = (
        PipelineStepDefinition("step_1", "1", "Step 1", "", "", "—"),
        PipelineStepDefinition("step_2", "2", "Step 2", "", "", "step_1"),
        PipelineStepDefinition("step_3", "3", "Step 3", "", "", "step_2"),
        PipelineStepDefinition("ml_train", "9", "ML Train", "", "", "step_3"),
        PipelineStepDefinition("step_12", "12", "Step 12", "", "", "ml_train"),
        PipelineStepDefinition("corporate_actions_sync", "13", "CA Sync", "", "", "step_12"),
        PipelineStepDefinition("corporate_actions_apply", "14", "CA Apply", "", "", "corporate_actions_sync"),
    )
    monkeypatch.setattr(registry, "get_pipeline_workflow_steps", lambda **kwargs: tuple(
        step
        for step in steps
        if step.key in (
            ["step_3", "ml_train", "step_12", "corporate_actions_sync", "corporate_actions_apply"]
            if kwargs.get("start_step") == "3"
            else ["step_1", "step_2", "step_3", "ml_train", "step_12", "corporate_actions_sync", "corporate_actions_apply"]
        )
        and (kwargs.get("include_ml_train", True) or step.key != "ml_train")
        and (
            step.key not in {"corporate_actions_sync", "corporate_actions_apply"}
            or kwargs.get("include_corporate_actions_sync", False)
            or kwargs.get("include_corporate_actions_apply", False)
        )
        and (step.key != "corporate_actions_apply" or kwargs.get("include_corporate_actions_apply", False))
    ))
    monkeypatch.setattr(
        registry,
        "build_pipeline_command",
        lambda step_key, options: [sys.executable, "-c", f"print('{step_key}', flush=True)"],
    )

    record = registry.start_pipeline_workflow(
        PipelineLaunchOptions(),
        start_step="3",
        include_ml_train=True,
        include_corporate_actions_sync=False,
        include_corporate_actions_apply=True,
    )
    snapshot = _wait_for_final_snapshot(record.run_id, attempts=120)

    assert snapshot is not None
    assert snapshot["status"] == "completed"
    assert snapshot["workflow_total_steps"] == 5
    assert snapshot["command"] == ["step_3", "ml_train", "step_12", "corporate_actions_sync", "corporate_actions_apply"]
    assert "3 → 12 + 13 → 14" in str(snapshot["step_label"])
    logs = registry.read_pipeline_logs(record.run_id, "all")
    assert "1. Step 1" not in logs
    assert "2. Step 2" not in logs
    assert "corporate_actions_sync" in logs
    assert "corporate_actions_apply" in logs


def test_should_override_failed_status_for_ml_train_windows_post_success_crash() -> None:
    record = registry.PipelineRunRecord(
        run_id="run-1",
        step_key="ml_train",
        step_label="9. ML Train (Model Factory)",
        command=["python", "-m", "modelFactory", "--mode", "train"],
        command_display="python -m modelFactory --mode train",
        account_id="default",
        status="running",
        executed_at="2026-05-01T00:51:18",
        run_summary={
            "mode": "train",
            "symbols_total": 21,
            "symbols_completed": 21,
            "symbols_skipped": 0,
            "symbols_failed": 0,
        },
    )

    assert registry._should_override_failed_status(record, 3221226505) is True


def test_should_not_override_failed_status_when_ml_summary_reports_failures() -> None:
    record = registry.PipelineRunRecord(
        run_id="run-2",
        step_key="ml_train",
        step_label="9. ML Train (Model Factory)",
        command=["python", "-m", "modelFactory", "--mode", "train"],
        command_display="python -m modelFactory --mode train",
        account_id="default",
        status="running",
        executed_at="2026-05-01T00:51:18",
        run_summary={
            "mode": "train",
            "symbols_total": 21,
            "symbols_completed": 20,
            "symbols_skipped": 0,
            "symbols_failed": 1,
        },
    )

    assert registry._should_override_failed_status(record, 3221226505) is False


def test_should_override_failed_status_for_ml_train_from_text_summary_logs(tmp_path: Path) -> None:
    stdout_path = tmp_path / "stdout.log"
    stdout_path.write_text(
        "\n".join(
            [
                "2026-05-01 00:53:53,660 modelFactory.orchestrator INFO run_training_batch finished completed=21 skipped=0 failed=0",
                "",
                "============================================================",
                "  Model Factory — Training Summary",
                "  Completed: 21  Skipped: 0  Failed: 0",
                "============================================================",
            ]
        ),
        encoding="utf-8",
    )
    record = registry.PipelineRunRecord(
        run_id="run-3",
        step_key="ml_train",
        step_label="9. ML Train (Model Factory)",
        command=["python", "-m", "modelFactory", "--mode", "train"],
        command_display="python -m modelFactory --mode train",
        account_id="default",
        status="running",
        executed_at="2026-05-01T00:51:18",
        stdout_path=str(stdout_path),
    )

    assert registry._should_override_failed_status(record, 3221226505) is True


def test_should_not_override_failed_status_for_ml_train_from_text_summary_logs_when_failed(tmp_path: Path) -> None:
    stdout_path = tmp_path / "stdout.log"
    stdout_path.write_text(
        "\n".join(
            [
                "2026-05-01 00:53:53,660 modelFactory.orchestrator INFO run_training_batch finished completed=20 skipped=0 failed=1",
                "",
                "============================================================",
                "  Model Factory — Training Summary",
                "  Completed: 20  Skipped: 0  Failed: 1",
                "============================================================",
            ]
        ),
        encoding="utf-8",
    )
    record = registry.PipelineRunRecord(
        run_id="run-4",
        step_key="ml_train",
        step_label="9. ML Train (Model Factory)",
        command=["python", "-m", "modelFactory", "--mode", "train"],
        command_display="python -m modelFactory --mode train",
        account_id="default",
        status="running",
        executed_at="2026-05-01T00:51:18",
        stdout_path=str(stdout_path),
    )

    assert registry._should_override_failed_status(record, 3221226505) is False


