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
from typing import Literal

from ihm.services.backtesting_runner import (
    BackfillScoresHistoryOptions,
    BacktestRunOptions,
    BacktestingCommandKind,
    DiagnoseScreenerOptions,
    PROJECT_ROOT,
    RecommendScreenerOptions,
    build_backtesting_command,
    build_subprocess_env,
    format_command_for_display,
)
from ihm.services.screener_recommendations import build_screener_artifact_summary, get_screener_artifacts_dir

RunStatus = Literal["starting", "running", "completed", "failed", "timeout", "stopped"]
TAIL_MAX_LINES = 400
RUNS_DIR = PROJECT_ROOT / "artifacts" / "ihm_backtesting_runs"
HISTORY_INDEX_PATH = RUNS_DIR / "history_index.json"


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
    return managed.record


def _tail_text(lines: list[str]) -> str:
    return "".join(lines)


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


def list_active_backtesting_runs_by_kind(run_kind: BacktestingCommandKind) -> list[dict[str, object]]:
    """Retourne les runs actifs pour un type de commande donné."""
    return [run for run in list_active_backtesting_runs() if str(run.get("run_kind", "")) == run_kind]


def start_backtesting_run(
    run_kind: BacktestingCommandKind,
    run_label: str,
    options: BacktestRunOptions | BackfillScoresHistoryOptions | DiagnoseScreenerOptions | RecommendScreenerOptions,
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
    env = build_subprocess_env(db_config=db_config)

    run_id = f"{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"
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
    snapshots.sort(key=lambda item: str(item.get("executed_at", "")), reverse=True)
    return snapshots


def poll_backtesting_run(run_id: str) -> dict[str, object] | None:
    with _REGISTRY_LOCK:
        managed = _ACTIVE_RUNS.get(run_id)
    if managed is None:
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
        return False

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


def read_backtesting_logs(run_id: str, stream: Literal["stdout", "stderr", "all"] = "all") -> str:
    record = get_backtesting_run_record(run_id)
    if record is None:
        return ""

    path_key = {"stdout": "stdout_path", "stderr": "stderr_path", "all": "combined_path"}[stream]
    path = Path(str(record.get(path_key, "")))
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def build_backtesting_log_download_name(run_id: str, stream: Literal["stdout", "stderr", "all"] = "all") -> str:
    record = get_backtesting_run_record(run_id)
    run_kind = str(record.get("run_kind", "backtesting")) if record else "backtesting"
    return f"{run_kind}_{run_id}_{stream}.log"

