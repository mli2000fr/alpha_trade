"""Registre des runs backtesting lancés en arrière-plan depuis l'IHM."""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
import uuid
from dataclasses import replace
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, cast

from ihm.services.backtesting_runner import (
    BackfillScoresHistoryOptions,
    BacktestRunOptions,
    BacktestingCommandKind,
    CalibrateSentimentWeightsOptions,
    DiagnoseScreenerOptions,
    PROJECT_ROOT,
    RecommendScreenerOptions,
    WalkForwardSentimentOptions,
    build_backtesting_command,
    build_subprocess_env,
    format_command_for_display,
)
from ihm.services.db import validate_db_connection_config
from ihm.services.screener_recommendations import build_screener_artifact_summary, get_screener_artifacts_dir

RunStatus = Literal["starting", "running", "completed", "failed", "timeout", "stopped"]
TAIL_MAX_LINES = 400
RUNS_DIR = PROJECT_ROOT / "artifacts" / "ihm_backtesting_runs"
HISTORY_INDEX_PATH = RUNS_DIR / "history_index.json"
DB_REQUIRED_RUN_KINDS = frozenset({
    "run",
    "backfill-scores-history",
    "diagnose-screener",
    "calibrate-sentiment-weights",
    "calibrate-conviction-weights",
    "walk-forward-sentiment",
})


@dataclass(frozen=True, slots=True)
class BacktestingRunRecord:
    run_id: str
    run_kind: BacktestingCommandKind
    run_label: str
    command: list[str]
    command_display: str
    status: RunStatus
    executed_at: str
    finished_at: str | None = None
    returncode: int | None = None
    duration_seconds: float = 0.0
    stdout_path: str = ""
    stderr_path: str = ""
    combined_path: str = ""
    stdout_lines: int = 0
    stderr_lines: int = 0
    timeout_seconds: int | None = None
    stop_requested: bool = False
    screener_artifacts_dir: str | None = None
    screener_artifact_summary: dict[str, object] | None = None

    def to_state(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class _ManagedRun:
    record: BacktestingRunRecord
    process: subprocess.Popen[str]
    events: queue.Queue[tuple[str, str]]
    stdout_thread: threading.Thread
    stderr_thread: threading.Thread
    started_perf: float
    timed_out: bool = False
    stdout_tail: list[str] | None = None
    stderr_tail: list[str] | None = None
    # Sprint S2 / A-014 — verrou pipeline associé au run, libéré à la fin.
    pipeline_lock: object | None = None

    def __post_init__(self) -> None:
        if self.stdout_tail is None:
            self.stdout_tail = []
        if self.stderr_tail is None:
            self.stderr_tail = []


_REGISTRY_LOCK = threading.Lock()
_ACTIVE_RUNS: dict[str, _ManagedRun] = {}


def _ensure_storage() -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    if not HISTORY_INDEX_PATH.exists():
        HISTORY_INDEX_PATH.write_text("{}", encoding="utf-8")


def _append_tail(target: list[str], line: str) -> None:
    target.append(line)
    if len(target) > TAIL_MAX_LINES:
        del target[: len(target) - TAIL_MAX_LINES]


def _read_history_index() -> dict[str, dict[str, object]]:
    _ensure_storage()
    try:
        return json.loads(HISTORY_INDEX_PATH.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {}


def _write_history_index(payload: dict[str, dict[str, object]]) -> None:
    _ensure_storage()
    HISTORY_INDEX_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _persist_record(record: BacktestingRunRecord) -> None:
    with _REGISTRY_LOCK:
        index = _read_history_index()
        index[record.run_id] = record.to_state()
        _write_history_index(index)


def _reader(stream: subprocess.PIPE | None, stream_name: str, events: queue.Queue[tuple[str, str]]) -> None:  # type: ignore[type-arg]
    if stream is None:
        return
    try:
        for line in iter(stream.readline, ""):
            events.put((stream_name, line))
    finally:
        stream.close()


def _creation_flags() -> int:
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return 0


def _kill_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
    else:
        process.kill()


def _kill_process_tree_by_pid(pid: int) -> None:
    pid_int = int(pid)
    if pid_int <= 0:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid_int), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
    else:
        try:
            os.kill(pid_int, 9)
        except ProcessLookupError:
            return


def _parse_iso_datetime(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _compute_elapsed_seconds(executed_at: object) -> float:
    started_at = _parse_iso_datetime(executed_at)
    if started_at is None:
        return 0.0
    return round(max((datetime.now() - started_at).total_seconds(), 0.0), 2)


def _find_backtesting_run_dir(run_id: str, run_kind: str | None = None) -> Path | None:
    candidate_kinds: list[str] = []
    if run_kind:
        candidate_kinds.append(str(run_kind))

    for entry in RUNS_DIR.iterdir() if RUNS_DIR.exists() else []:
        if entry.is_dir() and entry.name not in candidate_kinds:
            candidate_kinds.append(entry.name)

    for kind in candidate_kinds:
        candidate = _run_dir_for(cast(BacktestingCommandKind, kind), run_id)
        if candidate.exists():
            return candidate
    return None


def _find_active_backtesting_lock(run_id: str | None = None) -> dict[str, object] | None:
    from ihm.services.pipeline_lock import list_active_locks as _list_active_locks

    for payload in _list_active_locks():
        if str(payload.get("scope") or "") != "backtesting":
            continue
        if run_id is not None and str(payload.get("run_id") or "") != str(run_id):
            continue
        return payload
    return None


def _build_recovered_snapshot_from_lock(payload: dict[str, object]) -> dict[str, object]:
    run_id = str(payload.get("run_id") or "")
    history_record = _read_history_index().get(run_id, {})
    run_kind = str(history_record.get("run_kind") or "run")
    run_dir = _find_backtesting_run_dir(run_id, run_kind=run_kind)

    stdout_path = str(history_record.get("stdout_path") or "")
    stderr_path = str(history_record.get("stderr_path") or "")
    combined_path = str(history_record.get("combined_path") or "")
    if run_dir is not None:
        if not stdout_path:
            stdout_path = str(run_dir / "stdout.log")
        if not stderr_path:
            stderr_path = str(run_dir / "stderr.log")
        if not combined_path:
            combined_path = str(run_dir / "combined.log")

    executed_at = str(
        history_record.get("executed_at")
        or payload.get("acquired_at")
        or datetime.now().isoformat(timespec="seconds")
    )
    snapshot: dict[str, object] = {
        **history_record,
        "run_id": run_id,
        "run_kind": run_kind,
        "run_label": str(history_record.get("run_label") or f"Backtest récupéré ({run_kind})"),
        "status": "running",
        "executed_at": executed_at,
        "finished_at": None,
        "returncode": None,
        "duration_seconds": _compute_elapsed_seconds(executed_at),
        "stdout_path": stdout_path,
        "stderr_path": stderr_path,
        "combined_path": combined_path,
        "stdout_tail": _read_text_tail(Path(stdout_path), TAIL_MAX_LINES) if stdout_path else "",
        "stderr_tail": _read_text_tail(Path(stderr_path), TAIL_MAX_LINES) if stderr_path else "",
        "is_active": True,
        "recovered_from_lock": True,
        "lock_pid": int(str(payload.get("pid") or 0)),
    }
    return snapshot


def _with_updates(record: BacktestingRunRecord, **updates: object) -> BacktestingRunRecord:
    data = record.to_state()
    data.update(updates)
    return BacktestingRunRecord(**data)


def _drain_events(managed: _ManagedRun) -> bool:
    stdout_chunk: list[str] = []
    stderr_chunk: list[str] = []
    drained = False
    while True:
        try:
            stream_name, line = managed.events.get_nowait()
        except queue.Empty:
            break
        drained = True
        if stream_name == "stdout":
            stdout_chunk.append(line)
            _append_tail(managed.stdout_tail or [], line)
        else:
            stderr_chunk.append(line)
            _append_tail(managed.stderr_tail or [], line)

    if stdout_chunk:
        with Path(managed.record.stdout_path).open("a", encoding="utf-8") as fh:
            fh.write("".join(stdout_chunk))
        with Path(managed.record.combined_path).open("a", encoding="utf-8") as fh:
            fh.write("".join(f"[stdout] {line}" for line in stdout_chunk))
        managed.record = _with_updates(managed.record, stdout_lines=managed.record.stdout_lines + len(stdout_chunk))

    if stderr_chunk:
        with Path(managed.record.stderr_path).open("a", encoding="utf-8") as fh:
            fh.write("".join(stderr_chunk))
        with Path(managed.record.combined_path).open("a", encoding="utf-8") as fh:
            fh.write("".join(f"[stderr] {line}" for line in stderr_chunk))
        managed.record = _with_updates(managed.record, stderr_lines=managed.record.stderr_lines + len(stderr_chunk))

    return drained


def _finalize_if_needed(managed: _ManagedRun) -> BacktestingRunRecord:
    elapsed = round(time.perf_counter() - managed.started_perf, 2)
    returncode = managed.process.poll()

    if managed.record.timeout_seconds is not None and elapsed > managed.record.timeout_seconds and returncode is None:
        _kill_process_tree(managed.process)
        managed.timed_out = True
        timeout_message = "\nTimeout d'exécution dépassé.\n"
        with Path(managed.record.stderr_path).open("a", encoding="utf-8") as fh:
            fh.write(timeout_message)
        with Path(managed.record.combined_path).open("a", encoding="utf-8") as fh:
            fh.write(f"[stderr] {timeout_message}")
        _append_tail(managed.stderr_tail or [], timeout_message)
        managed.record = _with_updates(managed.record, stderr_lines=managed.record.stderr_lines + 1)
        returncode = -2

    _drain_events(managed)
    returncode = managed.process.poll() if returncode is None else returncode

    if returncode is None:
        managed.record = _with_updates(managed.record, status="running", duration_seconds=elapsed)
        return managed.record

    managed.stdout_thread.join(timeout=0.2)
    managed.stderr_thread.join(timeout=0.2)
    _drain_events(managed)

    if managed.timed_out:
        status: RunStatus = "timeout"
        final_code = -2
    elif managed.record.stop_requested:
        status = "stopped"
        final_code = -3 if returncode == 0 else returncode
    else:
        status = "completed" if returncode == 0 else "failed"
        final_code = returncode

    managed.record = _with_updates(
        managed.record,
        status=status,
        returncode=final_code,
        duration_seconds=round(time.perf_counter() - managed.started_perf, 2),
        finished_at=datetime.now().isoformat(timespec="seconds"),
    )
    if managed.record.run_kind in {"diagnose-screener", "recommend-screener"} and managed.record.screener_artifacts_dir:
        managed.record = _with_updates(
            managed.record,
            screener_artifact_summary=build_screener_artifact_summary(managed.record.screener_artifacts_dir),
        )
    _persist_record(managed.record)
    # Sprint S2 / A-014 — libération du verrou cross-process en fin de run.
    if managed.pipeline_lock is not None:
        try:
            from ihm.services.pipeline_lock import release_lock as _release_lock

            _release_lock(managed.pipeline_lock)  # type: ignore[arg-type]
        finally:
            managed.pipeline_lock = None
    return managed.record


def _tail_text(lines: list[str]) -> str:
    return "".join(lines)


def _read_text_tail(path: Path, max_lines: int) -> str:
    if max_lines <= 0 or not path.exists() or not path.is_file():
        return ""
    with path.open("rb") as fh:
        fh.seek(0, os.SEEK_END)
        position = fh.tell()
        chunk_size = 8192
        chunks: list[bytes] = []
        newline_count = 0
        while position > 0 and newline_count <= max_lines:
            read_size = min(chunk_size, position)
            position -= read_size
            fh.seek(position)
            chunk = fh.read(read_size)
            chunks.append(chunk)
            newline_count += chunk.count(b"\n")
    text = b"".join(reversed(chunks)).decode("utf-8", errors="replace")
    lines = text.splitlines()
    return "\n".join(lines[-max_lines:])


def _run_dir_for(run_kind: BacktestingCommandKind, run_id: str) -> Path:
    return RUNS_DIR / run_kind / run_id


def _resolve_screener_artifacts_dir(
    run_kind: BacktestingCommandKind,
    options: BacktestRunOptions | BackfillScoresHistoryOptions | DiagnoseScreenerOptions | RecommendScreenerOptions,
) -> str | None:
    if run_kind == "diagnose-screener" and isinstance(options, DiagnoseScreenerOptions):
        return str(get_screener_artifacts_dir(options.output_dir))
    if run_kind == "recommend-screener" and isinstance(options, RecommendScreenerOptions):
        if options.output_dir:
            return str(get_screener_artifacts_dir(options.output_dir))
        if options.summary_csv:
            return str(get_screener_artifacts_dir(Path(options.summary_csv).parent))
        return str(get_screener_artifacts_dir(options.input_dir))
    return None


def _ensure_db_ready_for_run(
    run_kind: BacktestingCommandKind,
    db_config: dict[str, str | None] | None,
) -> None:
    if run_kind not in DB_REQUIRED_RUN_KINDS or not db_config:
        return
    error = validate_db_connection_config(db_config)
    if error:
        raise RuntimeError(f"Pré-vérification DB échouée pour `{run_kind}` : {error}")


def list_active_backtesting_runs_by_kind(run_kind: BacktestingCommandKind) -> list[dict[str, object]]:
    """Retourne les runs actifs pour un type de commande donné."""
    return [run for run in list_active_backtesting_runs() if str(run.get("run_kind", "")) == run_kind]


def start_backtesting_run(
    run_kind: BacktestingCommandKind,
    run_label: str,
    options: BacktestRunOptions
    | BackfillScoresHistoryOptions
    | DiagnoseScreenerOptions
    | RecommendScreenerOptions
    | CalibrateSentimentWeightsOptions
    | WalkForwardSentimentOptions,
    *,
    db_config: dict[str, str | None] | None = None,
    timeout_seconds: int | None = None,
) -> BacktestingRunRecord:
    """Démarre un run backtesting en arrière-plan et retourne son enregistrement initial."""
    _ensure_storage()
    active_same_kind = list_active_backtesting_runs_by_kind(run_kind)
    if active_same_kind:
        active_run_id = str(active_same_kind[0].get("run_id", ""))
        raise RuntimeError(
            f"Un run `{run_kind}` est déjà en cours ({active_run_id}). Attendez sa fin ou arrêtez-le avant de relancer."
        )
    _ensure_db_ready_for_run(run_kind, db_config)

    # Sprint S2 / A-014 — exclusion mutuelle avec les workflows pipeline.
    from ihm.services.pipeline_lock import (
        PipelineLockBusy,
        acquire_lock as _acquire_lock,
        rebind_lock_pid as _rebind_lock_pid,
    )

    run_id = f"{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"
    try:
        backtest_lock = _acquire_lock("backtesting", owner=f"backtesting:{run_kind}", run_id=run_id)
    except PipelineLockBusy as exc:
        raise RuntimeError(
            f"Verrou pipeline actif : {exc}. "
            "Attendez la fin du workflow pipeline avant de lancer un backtesting."
        ) from exc
    env = build_subprocess_env(db_config=db_config)

    run_dir = _run_dir_for(run_kind, run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = run_dir / "artifacts"
    stdout_path = run_dir / "stdout.log"
    stderr_path = run_dir / "stderr.log"
    combined_path = run_dir / "combined.log"
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    combined_path.write_text("", encoding="utf-8")

    if run_kind == "run" and isinstance(options, BacktestRunOptions):
        options = replace(options, output_dir=str(artifacts_dir))

    command = build_backtesting_command(run_kind, options)
    command_display = format_command_for_display(command)
    screener_artifacts_dir = _resolve_screener_artifacts_dir(run_kind, options)

    try:
        process = subprocess.Popen(
            command,
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=_creation_flags(),
        )
        backtest_lock = _rebind_lock_pid(backtest_lock, pid=process.pid)
    except Exception:
        try:
            from ihm.services.pipeline_lock import release_lock as _release_lock

            _release_lock(backtest_lock)  # type: ignore[arg-type]
        except Exception:
            pass
        raise

    events: queue.Queue[tuple[str, str]] = queue.Queue()
    stdout_thread = threading.Thread(target=_reader, args=(process.stdout, "stdout", events), daemon=True)
    stderr_thread = threading.Thread(target=_reader, args=(process.stderr, "stderr", events), daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    record = BacktestingRunRecord(
        run_id=run_id,
        run_kind=run_kind,
        run_label=run_label,
        command=command,
        command_display=command_display,
        status="running",
        executed_at=datetime.now().isoformat(timespec="seconds"),
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        combined_path=str(combined_path),
        timeout_seconds=timeout_seconds,
        screener_artifacts_dir=screener_artifacts_dir,
    )
    managed = _ManagedRun(
        record=record,
        process=process,
        events=events,
        stdout_thread=stdout_thread,
        stderr_thread=stderr_thread,
        started_perf=time.perf_counter(),
        pipeline_lock=backtest_lock,
    )

    with _REGISTRY_LOCK:
        _ACTIVE_RUNS[run_id] = managed
    _persist_record(record)
    return record


def list_active_backtesting_runs() -> list[dict[str, object]]:
    snapshots: list[dict[str, object]] = []
    for run_id in list(_ACTIVE_RUNS.keys()):
        snapshot = poll_backtesting_run(run_id)
        if snapshot is not None:
            snapshots.append(snapshot)

    recovered_lock = _find_active_backtesting_lock()
    if recovered_lock is not None:
        recovered_run_id = str(recovered_lock.get("run_id") or "")
        if recovered_run_id and all(str(item.get("run_id") or "") != recovered_run_id for item in snapshots):
            snapshots.append(_build_recovered_snapshot_from_lock(recovered_lock))

    snapshots.sort(key=lambda item: str(item.get("executed_at", "")), reverse=True)
    return snapshots


def poll_backtesting_run(run_id: str) -> dict[str, object] | None:
    with _REGISTRY_LOCK:
        managed = _ACTIVE_RUNS.get(run_id)
    if managed is None:
        active_lock = _find_active_backtesting_lock(run_id)
        if active_lock is not None:
            return _build_recovered_snapshot_from_lock(active_lock)
        history = _read_history_index()
        return history.get(run_id)

    record = _finalize_if_needed(managed)
    snapshot = {
        **record.to_state(),
        "stdout_tail": _tail_text(managed.stdout_tail or []),
        "stderr_tail": _tail_text(managed.stderr_tail or []),
        "is_active": record.status in {"starting", "running"},
    }
    if record.status not in {"starting", "running"}:
        with _REGISTRY_LOCK:
            _ACTIVE_RUNS.pop(run_id, None)
    else:
        _persist_record(record)
    return snapshot


def stop_backtesting_run(run_id: str) -> bool:
    with _REGISTRY_LOCK:
        managed = _ACTIVE_RUNS.get(run_id)
    if managed is None:
        active_lock = _find_active_backtesting_lock(run_id)
        if active_lock is None:
            return False

        pid = int(str(active_lock.get("pid") or 0))
        try:
            _kill_process_tree_by_pid(pid)
        finally:
            from ihm.services.pipeline_lock import LockHandle, _lock_path, release_lock as _release_lock

            _release_lock(
                LockHandle(
                    scope="backtesting",
                    owner=str(active_lock.get("owner") or "backtesting:recovered"),
                    run_id=run_id,
                    pid=pid,
                    path=_lock_path("backtesting"),
                )
            )

        history = _read_history_index()
        record = history.get(run_id)
        if record is not None:
            record["status"] = "stopped"
            record["stop_requested"] = True
            record["returncode"] = -3
            record["finished_at"] = datetime.now().isoformat(timespec="seconds")
            record["duration_seconds"] = _compute_elapsed_seconds(record.get("executed_at"))
            history[run_id] = record
            _write_history_index(history)
        return True

    managed.record = _with_updates(managed.record, stop_requested=True)
    _kill_process_tree(managed.process)
    _persist_record(_with_updates(managed.record, status="stopped"))
    return True


def load_backtesting_history() -> list[dict[str, object]]:
    history = list(_read_history_index().values())
    history.sort(key=lambda item: str(item.get("finished_at") or item.get("executed_at") or ""), reverse=True)
    return history


def get_backtesting_run_record(run_id: str) -> dict[str, object] | None:
    active = poll_backtesting_run(run_id)
    if active is not None:
        return active
    return _read_history_index().get(run_id)


def _resolve_backtesting_log_path(
    record: dict[str, object] | None,
    stream: Literal["stdout", "stderr", "all"] = "all",
) -> Path | None:
    if not isinstance(record, dict):
        return None
    path_key = {
        "stdout": "stdout_path",
        "stderr": "stderr_path",
        "all": "combined_path",
    }[stream]
    raw_path = str(record.get(path_key) or "").strip()
    if not raw_path:
        return None
    return Path(raw_path)


def backtesting_log_available(run_id: str, stream: Literal["stdout", "stderr", "all"] = "all") -> bool:
    """Indique si le fichier de log demandé existe encore pour ce run."""
    path = _resolve_backtesting_log_path(get_backtesting_run_record(run_id), stream)
    return bool(path is not None and path.exists())


def read_backtesting_logs(
    run_id: str,
    stream: Literal["stdout", "stderr", "all"] = "all",
    *,
    tail_lines: int | None = None,
) -> str:
    path = _resolve_backtesting_log_path(get_backtesting_run_record(run_id), stream)
    if path is None or not path.exists():
        return ""
    if isinstance(tail_lines, int) and tail_lines > 0:
        return _read_text_tail(path, tail_lines)
    return path.read_text(encoding="utf-8", errors="replace")


def build_backtesting_log_download_name(run_id: str, stream: Literal["stdout", "stderr", "all"] = "all") -> str:
    record = get_backtesting_run_record(run_id)
    run_kind = str(record.get("run_kind", "backtesting")) if record else "backtesting"
    return f"{run_kind}_{run_id}_{stream}.log"

