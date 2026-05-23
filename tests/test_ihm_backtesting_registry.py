from __future__ import annotations

import json
from pathlib import Path

import pytest


class _FakeProcess:
    def __init__(self):
        self.pid = 4242
        self.stdout = None
        self.stderr = None

    def poll(self):
        return 0


class _FakeThread:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def start(self):
        return None

    def join(self, timeout=None):
        return None


def test_recommend_screener_run_persists_structured_artifact_summary(tmp_path: Path, monkeypatch):
    from ihm.services import backtesting_registry, pipeline_lock
    from ihm.services.backtesting_runner import RecommendScreenerOptions

    runs_dir = tmp_path / "ihm_runs"
    output_dir = tmp_path / "screener_out"
    locks_dir = tmp_path / "locks"

    monkeypatch.setattr(backtesting_registry, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(backtesting_registry, "HISTORY_INDEX_PATH", runs_dir / "history_index.json")
    monkeypatch.setattr(backtesting_registry, "_ACTIVE_RUNS", {})
    monkeypatch.setattr(backtesting_registry, "build_subprocess_env", lambda db_config=None: {})
    monkeypatch.setattr(backtesting_registry.subprocess, "Popen", lambda *args, **kwargs: _FakeProcess())
    monkeypatch.setattr(backtesting_registry.threading, "Thread", _FakeThread)
    monkeypatch.setattr(
        backtesting_registry,
        "build_screener_artifact_summary",
        lambda artifacts_dir: {
            "available": True,
            "artifacts_dir": str(artifacts_dir),
            "objective_count": 2,
            "file_count": 4,
        },
    )

    pipeline_lock.set_locks_dir_for_tests(locks_dir)
    try:
        record = backtesting_registry.start_backtesting_run(
            "recommend-screener",
            "Recommandation screener",
            RecommendScreenerOptions(
                input_dir=str(tmp_path / "input"),
                output_dir=str(output_dir),
                target_horizon=10,
            ),
        )

        snapshot = backtesting_registry.poll_backtesting_run(record.run_id)

        assert snapshot is not None
        assert snapshot["status"] == "completed"
        assert snapshot["screener_artifacts_dir"] == str(output_dir)
        assert snapshot["screener_artifact_summary"]["available"] is True
        assert snapshot["screener_artifact_summary"]["artifacts_dir"] == str(output_dir)
    finally:
        pipeline_lock.set_locks_dir_for_tests(None)


def test_backtesting_log_available_checks_existing_file(tmp_path: Path, monkeypatch) -> None:
    from ihm.services import backtesting_registry

    combined_path = tmp_path / "combined.log"
    combined_path.write_text("hello", encoding="utf-8")

    monkeypatch.setattr(
        backtesting_registry,
        "get_backtesting_run_record",
        lambda run_id: {"combined_path": str(combined_path), "stdout_path": "", "stderr_path": ""},
    )

    assert backtesting_registry.backtesting_log_available("run-1", stream="all") is True
    assert backtesting_registry.read_backtesting_logs("run-1", stream="all") == "hello"


def test_read_backtesting_logs_can_return_only_tail_lines(tmp_path: Path, monkeypatch) -> None:
    from ihm.services import backtesting_registry

    combined_path = tmp_path / "combined.log"
    combined_path.write_text("l1\nl2\nl3\nl4\n", encoding="utf-8")

    monkeypatch.setattr(
        backtesting_registry,
        "get_backtesting_run_record",
        lambda run_id: {"combined_path": str(combined_path), "stdout_path": "", "stderr_path": ""},
    )

    assert backtesting_registry.read_backtesting_logs("run-1", stream="all", tail_lines=2) == "l3\nl4"


def test_start_backtesting_run_rebinds_pipeline_lock_to_child_pid(tmp_path: Path, monkeypatch) -> None:
    from ihm.services import backtesting_registry, pipeline_lock
    from ihm.services.backtesting_runner import BacktestRunOptions

    runs_dir = tmp_path / "ihm_runs"
    locks_dir = tmp_path / "locks"

    monkeypatch.setattr(backtesting_registry, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(backtesting_registry, "HISTORY_INDEX_PATH", runs_dir / "history_index.json")
    monkeypatch.setattr(backtesting_registry, "_ACTIVE_RUNS", {})
    monkeypatch.setattr(backtesting_registry, "build_subprocess_env", lambda db_config=None: {})
    monkeypatch.setattr(backtesting_registry.subprocess, "Popen", lambda *args, **kwargs: _FakeProcess())
    monkeypatch.setattr(backtesting_registry.threading, "Thread", _FakeThread)
    pipeline_lock.set_locks_dir_for_tests(locks_dir)

    try:
        record = backtesting_registry.start_backtesting_run(
            "run",
            "Backtesting run",
            BacktestRunOptions(start="2026-01-01"),
        )

        lock_path = locks_dir / "backtesting.lock"
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        assert record.run_id == payload["run_id"]
        assert payload["owner"] == "backtesting:run"
        assert payload["pid"] == 4242
    finally:
        pipeline_lock.set_locks_dir_for_tests(None)


def test_start_backtesting_run_fails_fast_when_db_preflight_fails(tmp_path: Path, monkeypatch) -> None:
    from ihm.services import backtesting_registry
    from ihm.services.backtesting_runner import BacktestRunOptions

    runs_dir = tmp_path / "ihm_runs"

    monkeypatch.setattr(backtesting_registry, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(backtesting_registry, "HISTORY_INDEX_PATH", runs_dir / "history_index.json")
    monkeypatch.setattr(backtesting_registry, "_ACTIVE_RUNS", {})
    monkeypatch.setattr(
        backtesting_registry,
        "validate_db_connection_config",
        lambda db_config: "Accès MySQL refusé pour l'utilisateur `root` sur `localhost/alpha_trade`.",
    )

    popen_called = False

    def _unexpected_popen(*args, **kwargs):
        nonlocal popen_called
        popen_called = True
        raise AssertionError("Popen ne doit pas être appelé si la pré-vérification DB échoue")

    monkeypatch.setattr(backtesting_registry.subprocess, "Popen", _unexpected_popen)

    with pytest.raises(RuntimeError, match="Pré-vérification DB échouée") as exc_info:
        backtesting_registry.start_backtesting_run(
            "run",
            "Backtesting run",
            BacktestRunOptions(start="2026-01-01"),
            db_config={
                "host": "localhost",
                "name": "alpha_trade",
                "user": "root",
                "password": "bad-secret",
                "source": "variables d'environnement",
            },
        )

    assert "Accès MySQL refusé" in str(exc_info.value)
    assert popen_called is False


