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
    monkeypatch.setattr(backtesting_registry, "list_active_backtesting_runs_by_kind", lambda run_kind: [])
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


def test_list_active_backtesting_runs_recovers_live_locked_run_after_restart(tmp_path: Path, monkeypatch) -> None:
    from ihm.services import backtesting_registry, pipeline_lock

    run_id = "20260614_110349_17710755"
    runs_dir = tmp_path / "ihm_runs"
    run_dir = runs_dir / "run" / run_id
    locks_dir = tmp_path / "locks"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "stdout.log").write_text("stdout line\n", encoding="utf-8")
    (run_dir / "stderr.log").write_text("stderr line\n", encoding="utf-8")
    (run_dir / "combined.log").write_text("combined line\n", encoding="utf-8")

    monkeypatch.setattr(backtesting_registry, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(backtesting_registry, "HISTORY_INDEX_PATH", runs_dir / "history_index.json")
    monkeypatch.setattr(backtesting_registry, "_ACTIVE_RUNS", {})

    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "history_index.json").write_text(
        json.dumps(
            {
                run_id: {
                    "run_id": run_id,
                    "run_kind": "run",
                    "run_label": "Backtest complet",
                    "command": ["python", "-m", "backtesting", "run"],
                    "command_display": "python -m backtesting run",
                    "status": "running",
                    "executed_at": "2026-06-14T11:03:49",
                    "finished_at": None,
                    "returncode": None,
                    "duration_seconds": 0.0,
                    "stdout_path": str(run_dir / "stdout.log"),
                    "stderr_path": str(run_dir / "stderr.log"),
                    "combined_path": str(run_dir / "combined.log"),
                    "stdout_lines": 1,
                    "stderr_lines": 1,
                    "timeout_seconds": None,
                    "stop_requested": False,
                    "screener_artifacts_dir": None,
                    "screener_artifact_summary": None,
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    pipeline_lock.set_locks_dir_for_tests(locks_dir)
    monkeypatch.setattr(pipeline_lock, "_is_pid_alive", lambda pid: pid == 4242)
    try:
        locks_dir.mkdir(parents=True, exist_ok=True)
        (locks_dir / "backtesting.lock").write_text(
            json.dumps(
                {
                    "scope": "backtesting",
                    "owner": "backtesting:run",
                    "run_id": run_id,
                    "pid": 4242,
                    "acquired_at": "2026-06-14T11:03:49",
                    "process_started_at": None,
                }
            ),
            encoding="utf-8",
        )

        snapshots = backtesting_registry.list_active_backtesting_runs()

        assert len(snapshots) == 1
        assert snapshots[0]["run_id"] == run_id
        assert snapshots[0]["status"] == "running"
        assert snapshots[0]["is_active"] is True
        assert snapshots[0]["recovered_from_lock"] is True
        assert snapshots[0]["lock_pid"] == 4242
        assert "stdout line" in snapshots[0]["stdout_tail"]
        assert "stderr line" in snapshots[0]["stderr_tail"]
    finally:
        pipeline_lock.set_locks_dir_for_tests(None)


def test_stop_backtesting_run_can_stop_recovered_locked_run(tmp_path: Path, monkeypatch) -> None:
    from ihm.services import backtesting_registry, pipeline_lock

    run_id = "20260614_110349_17710755"
    runs_dir = tmp_path / "ihm_runs"
    run_dir = runs_dir / "run" / run_id
    locks_dir = tmp_path / "locks"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "stdout.log").write_text("stdout line\n", encoding="utf-8")
    (run_dir / "stderr.log").write_text("stderr line\n", encoding="utf-8")
    (run_dir / "combined.log").write_text("combined line\n", encoding="utf-8")

    monkeypatch.setattr(backtesting_registry, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(backtesting_registry, "HISTORY_INDEX_PATH", runs_dir / "history_index.json")
    monkeypatch.setattr(backtesting_registry, "_ACTIVE_RUNS", {})

    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "history_index.json").write_text(
        json.dumps(
            {
                run_id: {
                    "run_id": run_id,
                    "run_kind": "run",
                    "run_label": "Backtest complet",
                    "command": ["python", "-m", "backtesting", "run"],
                    "command_display": "python -m backtesting run",
                    "status": "running",
                    "executed_at": "2026-06-14T11:03:49",
                    "finished_at": None,
                    "returncode": None,
                    "duration_seconds": 0.0,
                    "stdout_path": str(run_dir / "stdout.log"),
                    "stderr_path": str(run_dir / "stderr.log"),
                    "combined_path": str(run_dir / "combined.log"),
                    "stdout_lines": 1,
                    "stderr_lines": 1,
                    "timeout_seconds": None,
                    "stop_requested": False,
                    "screener_artifacts_dir": None,
                    "screener_artifact_summary": None,
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    killed_pids: list[int] = []
    monkeypatch.setattr(backtesting_registry, "_kill_process_tree_by_pid", lambda pid: killed_pids.append(pid))
    pipeline_lock.set_locks_dir_for_tests(locks_dir)
    monkeypatch.setattr(pipeline_lock, "_is_pid_alive", lambda pid: pid == 4242)
    try:
        locks_dir.mkdir(parents=True, exist_ok=True)
        lock_path = locks_dir / "backtesting.lock"
        lock_path.write_text(
            json.dumps(
                {
                    "scope": "backtesting",
                    "owner": "backtesting:run",
                    "run_id": run_id,
                    "pid": 4242,
                    "acquired_at": "2026-06-14T11:03:49",
                    "process_started_at": None,
                }
            ),
            encoding="utf-8",
        )

        assert backtesting_registry.stop_backtesting_run(run_id) is True
        history = backtesting_registry.get_backtesting_run_record(run_id)

        assert killed_pids == [4242]
        assert not lock_path.exists()
        assert history is not None
        assert history["status"] == "stopped"
        assert history["stop_requested"] is True
        assert history["returncode"] == -3
    finally:
        pipeline_lock.set_locks_dir_for_tests(None)


def test_start_backtesting_run_releases_lock_if_popen_fails(tmp_path: Path, monkeypatch) -> None:
    from ihm.services import backtesting_registry, pipeline_lock
    from ihm.services.backtesting_runner import BacktestRunOptions

    runs_dir = tmp_path / "ihm_runs"
    locks_dir = tmp_path / "locks"

    monkeypatch.setattr(backtesting_registry, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(backtesting_registry, "HISTORY_INDEX_PATH", runs_dir / "history_index.json")
    monkeypatch.setattr(backtesting_registry, "_ACTIVE_RUNS", {})
    monkeypatch.setattr(backtesting_registry, "build_subprocess_env", lambda db_config=None: {})
    monkeypatch.setattr(backtesting_registry.subprocess, "Popen", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    pipeline_lock.set_locks_dir_for_tests(locks_dir)
    try:
        with pytest.raises(RuntimeError, match="boom"):
            backtesting_registry.start_backtesting_run(
                "run",
                "Backtesting run",
                BacktestRunOptions(start="2026-01-01"),
            )

        assert not (locks_dir / "backtesting.lock").exists()
    finally:
        pipeline_lock.set_locks_dir_for_tests(None)




def test_delete_backtesting_runs_except_removes_non_completed_index_and_dir(tmp_path: Path, monkeypatch) -> None:
    from ihm.services import backtesting_registry

    runs_dir = tmp_path / "ihm_runs"
    monkeypatch.setattr(backtesting_registry, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(backtesting_registry, "HISTORY_INDEX_PATH", runs_dir / "history_index.json")
    monkeypatch.setattr(backtesting_registry, "_ACTIVE_RUNS", {})

    def _mk_run(run_id: str, kind: str, status: str) -> None:
        d = runs_dir / kind / run_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "stdout.log").write_text("out\n", encoding="utf-8")
        (d / "artifacts").mkdir(exist_ok=True)
        (d / "artifacts" / "report.json").write_text("{}", encoding="utf-8")

    _mk_run("r_completed", "run", "completed")
    _mk_run("r_failed", "run", "failed")
    _mk_run("r_stopped", "run", "stopped")
    _mk_run("r_backfill", "backfill-scores-history", "failed")

    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "history_index.json").write_text(
        json.dumps(
            {
                "r_completed": {"run_id": "r_completed", "run_kind": "run", "status": "completed"},
                "r_failed": {"run_id": "r_failed", "run_kind": "run", "status": "failed"},
                "r_stopped": {"run_id": "r_stopped", "run_kind": "run", "status": "stopped"},
                "r_backfill": {"run_id": "r_backfill", "run_kind": "backfill-scores-history", "status": "failed"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(backtesting_registry, "list_active_backtesting_runs", lambda: [])

    result = backtesting_registry.delete_backtesting_runs_except(keep_statuses={"completed"}, stop_active=False)

    assert sorted(result["deleted"]) == ["r_backfill", "r_failed", "r_stopped"]
    assert result["kept"] == ["r_completed"]
    assert result["errors"] == []

    remaining = backtesting_registry._read_history_index()
    assert set(remaining) == {"r_completed"}
    assert not (runs_dir / "run" / "r_failed").exists()
    assert not (runs_dir / "run" / "r_stopped").exists()
    assert not (runs_dir / "backfill-scores-history" / "r_backfill").exists()
    assert (runs_dir / "run" / "r_completed").exists()


def test_delete_backtesting_runs_except_counts_statuses(tmp_path: Path, monkeypatch) -> None:
    from ihm.services import backtesting_registry

    runs_dir = tmp_path / "ihm_runs"
    monkeypatch.setattr(backtesting_registry, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(backtesting_registry, "HISTORY_INDEX_PATH", runs_dir / "history_index.json")
    monkeypatch.setattr(backtesting_registry, "_ACTIVE_RUNS", {})

    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "history_index.json").write_text(
        json.dumps(
            {
                "r1": {"run_id": "r1", "run_kind": "run", "status": "completed"},
                "r2": {"run_id": "r2", "run_kind": "run", "status": "completed"},
                "r3": {"run_id": "r3", "run_kind": "run", "status": "failed"},
            }
        ),
        encoding="utf-8",
    )
    for rid in ("r1", "r2", "r3"):
        (runs_dir / "run" / rid).mkdir(parents=True, exist_ok=True)

    counts = backtesting_registry.count_backtesting_runs_by_status()
    assert counts == {"completed": 2, "failed": 1}


def test_delete_backtesting_runs_deletes_only_selected_ids(tmp_path: Path, monkeypatch) -> None:
    from ihm.services import backtesting_registry

    runs_dir = tmp_path / "ihm_runs"
    monkeypatch.setattr(backtesting_registry, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(backtesting_registry, "HISTORY_INDEX_PATH", runs_dir / "history_index.json")
    monkeypatch.setattr(backtesting_registry, "_ACTIVE_RUNS", {})

    for rid, status in (("a", "completed"), ("b", "failed"), ("c", "completed")):
        (runs_dir / "run" / rid).mkdir(parents=True, exist_ok=True)
        (runs_dir / "run" / rid / "stdout.log").write_text("out\n", encoding="utf-8")

    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "history_index.json").write_text(
        json.dumps(
            {
                "a": {"run_id": "a", "run_kind": "run", "status": "completed"},
                "b": {"run_id": "b", "run_kind": "run", "status": "failed"},
                "c": {"run_id": "c", "run_kind": "run", "status": "completed"},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(backtesting_registry, "list_active_backtesting_runs", lambda: [])

    result = backtesting_registry.delete_backtesting_runs(["a", "b"], stop_active=False)

    assert sorted(result["deleted"]) == ["a", "b"]
    assert result["kept"] == []
    assert result["errors"] == []
    remaining = backtesting_registry._read_history_index()
    assert set(remaining) == {"c"}
    assert not (runs_dir / "run" / "a").exists()
    assert not (runs_dir / "run" / "b").exists()
    assert (runs_dir / "run" / "c").exists()


def test_append_to_log_self_heals_deleted_run_directory(tmp_path: Path) -> None:
    """_append_to_log doit recréer le dossier/fichier manquant (auto-réparation).

    Régression : le répertoire d'un run actif peut être supprimé pendant que le
    process tourne encore (purge, reset ML, rétention, suppression manuelle).
    Sans récréation, `_drain_events` plantait toute la page en FileNotFoundError.
    """
    from ihm.services import backtesting_registry

    log_path = tmp_path / "run" / "20260830_082329_bfadd8e6" / "stdout.log"

    # Le fichier (et son dossier parent) n'existe pas → l'append doit auto-réparer
    assert not log_path.exists()
    backtesting_registry._append_to_log(str(log_path), "ligne 1\n")

    assert log_path.exists()
    assert log_path.read_text(encoding="utf-8") == "ligne 1\n"

    # Append successif → contenu conservé, pas d'écrasement
    backtesting_registry._append_to_log(str(log_path), "ligne 2\n")
    assert log_path.read_text(encoding="utf-8") == "ligne 1\nligne 2\n"

    # Chemin vide / texte vide → no-op silencieux
    backtesting_registry._append_to_log("", "x")
    backtesting_registry._append_to_log(str(log_path), "")
    assert log_path.read_text(encoding="utf-8") == "ligne 1\nligne 2\n"


def test_drain_events_survives_deleted_log_files(tmp_path: Path, monkeypatch) -> None:
    """_drain_events ne doit pas planter quand les fichiers de logs ont disparu.

    Reproduit le crash `FileNotFoundError` remonté en prod : le run est actif,
    il a du stdout en attente, mais son répertoire de logs a été supprimé.
    """
    from ihm.services import backtesting_registry
    from ihm.services.backtesting_registry import BacktestingRunRecord, _ManagedRun

    runs_dir = tmp_path / "ihm_runs"
    run_dir = runs_dir / "run" / "20260830_082329_bfadd8e6"

    record = BacktestingRunRecord(
        run_id="20260830_082329_bfadd8e6",
        run_kind="run",
        run_label="Backtest complet",
        command=["python", "-m", "backtesting", "run"],
        command_display="python -m backtesting run",
        status="running",
        executed_at="2026-08-30T08:23:29",
        stdout_path=str(run_dir / "stdout.log"),
        stderr_path=str(run_dir / "stderr.log"),
        combined_path=str(run_dir / "combined.log"),
    )
    events: "queue.Queue[tuple[str, str]]" = __import__("queue").Queue()
    events.put(("stdout", "hello\n"))
    events.put(("stderr", "err\n"))

    managed = _ManagedRun(
        record=record,
        process=_FakeProcess(),
        events=events,
        stdout_thread=_FakeThread(),
        stderr_thread=_FakeThread(),
        started_perf=0.0,
    )

    # Le répertoire du run n'existe PAS (simule la suppression pendant le run)
    assert not run_dir.exists()

    drained = backtesting_registry._drain_events(managed)

    assert drained is True
    # Auto-réparation : les logs ont été recréés et remplis
    assert (run_dir / "stdout.log").read_text(encoding="utf-8") == "hello\n"
    assert (run_dir / "stderr.log").read_text(encoding="utf-8") == "err\n"
    assert "[stdout] hello\n" in (run_dir / "combined.log").read_text(encoding="utf-8")
    assert managed.record.stdout_lines == 1
    assert managed.record.stderr_lines == 1
