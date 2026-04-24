"""Registre global des pipelines lancés en arrière-plan depuis l'IHM."""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from ihm.services.pipeline_runner import (
    PROJECT_ROOT,
    PipelineLaunchOptions,
    build_pipeline_command,
    build_subprocess_env,
    format_command_for_display,
    get_pipeline_steps,
)

RunStatus = Literal["starting", "running", "completed", "failed", "timeout", "stopped"]
TAIL_MAX_LINES = 400
RUNS_DIR = PROJECT_ROOT / "artifacts" / "ihm_pipeline_runs"
HISTORY_INDEX_PATH = RUNS_DIR / "history_index.json"
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"


@dataclass(frozen=True, slots=True)
class PipelineRunRecord:
    """Métadonnées sérialisables d'un run lancé depuis l'IHM."""

    run_id: str
    step_key: str
    step_label: str
    command: list[str]
    command_display: str
    account_id: str | None
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
    run_kind: Literal["step", "workflow"] = "step"
    parent_run_id: str | None = None
    workflow_total_steps: int = 0
    workflow_completed_steps: int = 0
    workflow_current_step_key: str | None = None
    workflow_current_step_label: str | None = None
    workflow_child_run_ids: list[str] = field(default_factory=list)
    run_summary: dict[str, object] = field(default_factory=dict)

    def to_state(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class _ManagedRun:
    record: PipelineRunRecord
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


@dataclass(slots=True)
class _ManagedWorkflow:
    record: PipelineRunRecord
    thread: threading.Thread
    started_perf: float
    stop_event: threading.Event
    lock: threading.Lock = field(default_factory=threading.Lock)
    stdout_tail: list[str] = field(default_factory=list)
    stderr_tail: list[str] = field(default_factory=list)
    current_child_run_id: str | None = None


_REGISTRY_LOCK = threading.Lock()
_ACTIVE_RUNS: dict[str, _ManagedRun] = {}
_ACTIVE_WORKFLOWS: dict[str, _ManagedWorkflow] = {}


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


def _persist_record(record: PipelineRunRecord) -> None:
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


def _with_updates(record: PipelineRunRecord, **updates: object) -> PipelineRunRecord:
    data = record.to_state()
    data.update(updates)
    return PipelineRunRecord(**data)


def _extract_run_summary(line: str) -> dict[str, object] | None:
    cleaned = line.strip()
    if not cleaned.startswith(RUN_SUMMARY_PREFIX):
        return None
    payload = cleaned[len(RUN_SUMMARY_PREFIX):].strip()
    if not payload:
        return None
    try:
        parsed = json.loads(payload)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def _drain_events(managed: _ManagedRun) -> bool:
    stdout_chunk: list[str] = []
    stderr_chunk: list[str] = []
    latest_summary: dict[str, object] | None = None
    drained = False
    while True:
        try:
            stream_name, line = managed.events.get_nowait()
        except queue.Empty:
            break
        drained = True
        summary = _extract_run_summary(line)
        if summary is not None:
            latest_summary = summary
            continue
        if stream_name == "stdout":
            stdout_chunk.append(line)
            _append_tail(managed.stdout_tail or [], line)
        else:
            stderr_chunk.append(line)
            _append_tail(managed.stderr_tail or [], line)

    if stdout_chunk:
        Path(managed.record.stdout_path).parent.mkdir(parents=True, exist_ok=True)
        with Path(managed.record.stdout_path).open("a", encoding="utf-8") as fh:
            fh.write("".join(stdout_chunk))
        with Path(managed.record.combined_path).open("a", encoding="utf-8") as fh:
            fh.write("".join(f"[stdout] {line}" for line in stdout_chunk))
        managed.record = _with_updates(
            managed.record,
            stdout_lines=managed.record.stdout_lines + len(stdout_chunk),
        )

    if stderr_chunk:
        Path(managed.record.stderr_path).parent.mkdir(parents=True, exist_ok=True)
        with Path(managed.record.stderr_path).open("a", encoding="utf-8") as fh:
            fh.write("".join(stderr_chunk))
        with Path(managed.record.combined_path).open("a", encoding="utf-8") as fh:
            fh.write("".join(f"[stderr] {line}" for line in stderr_chunk))
        managed.record = _with_updates(
            managed.record,
            stderr_lines=managed.record.stderr_lines + len(stderr_chunk),
        )

    if latest_summary is not None:
        managed.record = _with_updates(managed.record, run_summary=latest_summary)

    return drained


def _finalize_if_needed(managed: _ManagedRun) -> PipelineRunRecord:
    elapsed = round(time.perf_counter() - managed.started_perf, 2)
    returncode = managed.process.poll()

    if managed.record.timeout_seconds is not None and elapsed > managed.record.timeout_seconds and returncode is None:
        _kill_process_tree(managed.process)
        managed.timed_out = True
        Path(managed.record.stderr_path).parent.mkdir(parents=True, exist_ok=True)
        timeout_message = "\nTimeout d'exécution dépassé.\n"
        with Path(managed.record.stderr_path).open("a", encoding="utf-8") as fh:
            fh.write(timeout_message)
        with Path(managed.record.combined_path).open("a", encoding="utf-8") as fh:
            fh.write(f"[stderr] {timeout_message}")
        _append_tail(managed.stderr_tail or [], timeout_message)
        managed.record = _with_updates(
            managed.record,
            stderr_lines=managed.record.stderr_lines + 1,
        )
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
    _persist_record(managed.record)
    return managed.record


def _tail_text(lines: list[str]) -> str:
    return "".join(lines)


def _count_lines(text: str) -> int:
    return len(text.splitlines()) if text else 0


def _append_text(path_value: str, content: str) -> None:
    if not content:
        return
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(content)


def _read_new_text(path_value: str, offset: int) -> tuple[str, int]:
    path = Path(path_value)
    if not path.exists():
        return "", offset
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        fh.seek(offset)
        content = fh.read()
        return content, fh.tell()


def _prefix_chunk(content: str, prefix: str) -> str:
    if not content:
        return ""
    return "".join(f"{prefix}{line}" for line in content.splitlines(keepends=True))


def _append_workflow_chunk(managed: _ManagedWorkflow, stream: Literal["stdout", "stderr"], content: str, *, prefix: str) -> None:
    if not content:
        return

    with managed.lock:
        record = managed.record
        line_count = _count_lines(content)
        if stream == "stdout":
            _append_text(record.stdout_path, content)
            _append_text(record.combined_path, _prefix_chunk(content, prefix))
            for line in content.splitlines(keepends=True):
                _append_tail(managed.stdout_tail, line)
            managed.record = _with_updates(record, stdout_lines=record.stdout_lines + line_count)
        else:
            _append_text(record.stderr_path, content)
            _append_text(record.combined_path, _prefix_chunk(content, prefix))
            for line in content.splitlines(keepends=True):
                _append_tail(managed.stderr_tail, line)
            managed.record = _with_updates(record, stderr_lines=record.stderr_lines + line_count)
        _persist_record(managed.record)


def _append_workflow_event(managed: _ManagedWorkflow, message: str, *, is_error: bool = False) -> None:
    content = message if message.endswith("\n") else f"{message}\n"
    _append_workflow_chunk(
        managed,
        "stderr" if is_error else "stdout",
        content,
        prefix="[workflow] ",
    )


def _update_workflow_record(managed: _ManagedWorkflow, **updates: object) -> PipelineRunRecord:
    with managed.lock:
        managed.record = _with_updates(managed.record, **updates)
        _persist_record(managed.record)
        return managed.record


def _finalize_workflow_record(
    managed: _ManagedWorkflow,
    *,
    status: RunStatus,
    returncode: int | None,
    workflow_completed_steps: int,
) -> PipelineRunRecord:
    return _update_workflow_record(
        managed,
        status=status,
        returncode=returncode,
        duration_seconds=round(time.perf_counter() - managed.started_perf, 2),
        finished_at=datetime.now().isoformat(timespec="seconds"),
        workflow_completed_steps=workflow_completed_steps,
        workflow_current_step_key=None,
        workflow_current_step_label=None,
    )


def _sync_child_logs_to_workflow(
    managed: _ManagedWorkflow,
    child_snapshot: dict[str, object] | None,
    *,
    step_label: str,
    offsets: dict[str, int],
) -> None:
    if child_snapshot is None:
        return

    stdout_chunk, offsets["stdout"] = _read_new_text(str(child_snapshot.get("stdout_path", "")), offsets["stdout"])
    stderr_chunk, offsets["stderr"] = _read_new_text(str(child_snapshot.get("stderr_path", "")), offsets["stderr"])
    if stdout_chunk:
        _append_workflow_chunk(managed, "stdout", stdout_chunk, prefix=f"[stdout][{step_label}] ")
    if stderr_chunk:
        _append_workflow_chunk(managed, "stderr", stderr_chunk, prefix=f"[stderr][{step_label}] ")


def _run_pipeline_workflow(
    managed: _ManagedWorkflow,
    options: PipelineLaunchOptions,
    *,
    db_config: dict[str, str | None] | None = None,
    timeout_seconds: int | None = None,
) -> None:
    steps = get_pipeline_steps()
    total_steps = len(steps)

    try:
        _append_workflow_event(managed, f"Démarrage du workflow complet ({total_steps} étapes).")
        _update_workflow_record(managed, status="running", workflow_total_steps=total_steps, workflow_completed_steps=0)

        completed_steps = 0
        child_run_ids: list[str] = []

        for index, step in enumerate(steps, start=1):
            if managed.stop_event.is_set():
                _append_workflow_event(managed, "Workflow arrêté avant le lancement de l'étape suivante.", is_error=True)
                _finalize_workflow_record(managed, status="stopped", returncode=-3, workflow_completed_steps=completed_steps)
                return

            step_label = f"{step.num}. {step.name}"
            _append_workflow_event(managed, f"=== [{index}/{total_steps}] Démarrage {step_label} ===")
            child_record = start_pipeline_run(
                step.key,
                step_label,
                options,
                db_config=db_config,
                timeout_seconds=timeout_seconds,
                parent_run_id=managed.record.run_id,
            )
            child_run_ids.append(child_record.run_id)
            with managed.lock:
                managed.current_child_run_id = child_record.run_id
            _update_workflow_record(
                managed,
                workflow_current_step_key=step.key,
                workflow_current_step_label=step_label,
                workflow_child_run_ids=list(child_run_ids),
                workflow_completed_steps=completed_steps,
            )

            offsets = {"stdout": 0, "stderr": 0}
            child_snapshot: dict[str, object] | None = None

            while True:
                if managed.stop_event.is_set():
                    stop_pipeline_run(child_record.run_id)

                child_snapshot = poll_pipeline_run(child_record.run_id)
                _sync_child_logs_to_workflow(managed, child_snapshot, step_label=step_label, offsets=offsets)

                child_status = str(child_snapshot.get("status", "")) if child_snapshot is not None else "failed"
                _update_workflow_record(
                    managed,
                    status="running",
                    duration_seconds=round(time.perf_counter() - managed.started_perf, 2),
                    workflow_current_step_key=step.key,
                    workflow_current_step_label=step_label,
                    workflow_child_run_ids=list(child_run_ids),
                    workflow_completed_steps=completed_steps,
                )
                if child_status not in {"starting", "running"}:
                    break
                time.sleep(0.2)

            _sync_child_logs_to_workflow(managed, child_snapshot, step_label=step_label, offsets=offsets)
            with managed.lock:
                managed.current_child_run_id = None

            final_child_status = str(child_snapshot.get("status", "failed")) if child_snapshot is not None else "failed"
            final_child_returncode_raw = child_snapshot.get("returncode", -1) if child_snapshot is not None else -1
            final_child_returncode = int(final_child_returncode_raw) if isinstance(final_child_returncode_raw, int) else -1
            if final_child_status != "completed":
                _append_workflow_event(
                    managed,
                    f"Workflow interrompu sur {step_label} — statut `{final_child_status}` (run `{child_record.run_id}`).",
                    is_error=final_child_status in {"failed", "timeout", "stopped"},
                )
                parent_status: RunStatus = "failed"
                if final_child_status == "timeout":
                    parent_status = "timeout"
                elif final_child_status == "stopped" or managed.stop_event.is_set():
                    parent_status = "stopped"
                _finalize_workflow_record(
                    managed,
                    status=parent_status,
                    returncode=final_child_returncode,
                    workflow_completed_steps=completed_steps,
                )
                return

            completed_steps = index
            _update_workflow_record(managed, workflow_completed_steps=completed_steps, workflow_child_run_ids=list(child_run_ids))
            _append_workflow_event(managed, f"=== [{index}/{total_steps}] Terminé {step_label} (run `{child_record.run_id}`) ===")

        _append_workflow_event(managed, "Workflow complet terminé avec succès.")
        _finalize_workflow_record(managed, status="completed", returncode=0, workflow_completed_steps=completed_steps)
    except Exception as exc:
        _append_workflow_event(managed, f"Erreur interne du workflow : {exc}", is_error=True)
        _finalize_workflow_record(managed, status="failed", returncode=-1, workflow_completed_steps=managed.record.workflow_completed_steps)


def _poll_workflow_run(run_id: str, managed: _ManagedWorkflow) -> dict[str, object]:
    with managed.lock:
        record = managed.record
        if record.status in {"starting", "running"}:
            managed.record = _with_updates(record, duration_seconds=round(time.perf_counter() - managed.started_perf, 2))
            record = managed.record
            _persist_record(record)
        snapshot = {
            **record.to_state(),
            "stdout_tail": _tail_text(managed.stdout_tail),
            "stderr_tail": _tail_text(managed.stderr_tail),
            "is_active": record.status in {"starting", "running"},
        }

    if not snapshot["is_active"] and not managed.thread.is_alive():
        with _REGISTRY_LOCK:
            _ACTIVE_WORKFLOWS.pop(run_id, None)
    return snapshot


def _run_dir_for(step_key: str, run_id: str) -> Path:
    return RUNS_DIR / step_key / run_id


def start_pipeline_run(
    step_key: str,
    step_label: str,
    options: PipelineLaunchOptions,
    *,
    db_config: dict[str, str | None] | None = None,
    timeout_seconds: int | None = None,
    parent_run_id: str | None = None,
) -> PipelineRunRecord:
    """Démarre un pipeline en arrière-plan et retourne son enregistrement initial."""
    _ensure_storage()
    command = build_pipeline_command(step_key, options)
    command_display = format_command_for_display(command)
    env = build_subprocess_env(db_config=db_config)

    run_id = f"{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"
    run_dir = _run_dir_for(step_key, run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = run_dir / "stdout.log"
    stderr_path = run_dir / "stderr.log"
    combined_path = run_dir / "combined.log"
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    combined_path.write_text("", encoding="utf-8")

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

    record = PipelineRunRecord(
        run_id=run_id,
        step_key=step_key,
        step_label=step_label,
        command=command,
        command_display=command_display,
        account_id=options.account_id,
        status="running",
        executed_at=datetime.now().isoformat(timespec="seconds"),
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        combined_path=str(combined_path),
        timeout_seconds=timeout_seconds,
        parent_run_id=parent_run_id,
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


def start_pipeline_workflow(
    options: PipelineLaunchOptions,
    *,
    db_config: dict[str, str | None] | None = None,
    timeout_seconds: int | None = None,
) -> PipelineRunRecord:
    """Démarre un workflow séquentiel 1→12 en arrière-plan."""
    if list_active_pipeline_runs():
        raise RuntimeError("Un run pipeline est déjà actif. Attendez sa fin ou arrêtez-le avant de lancer le workflow complet.")

    _ensure_storage()
    run_id = f"{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"
    run_dir = _run_dir_for("pipeline_workflow", run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = run_dir / "stdout.log"
    stderr_path = run_dir / "stderr.log"
    combined_path = run_dir / "combined.log"
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    combined_path.write_text("", encoding="utf-8")

    steps = get_pipeline_steps()
    record = PipelineRunRecord(
        run_id=run_id,
        step_key="pipeline_workflow",
        step_label="Workflow complet 1 → 12",
        command=[step.key for step in steps],
        command_display="Workflow séquentiel Pipeline 1 → 12",
        account_id=options.account_id,
        status="running",
        executed_at=datetime.now().isoformat(timespec="seconds"),
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        combined_path=str(combined_path),
        timeout_seconds=timeout_seconds,
        run_kind="workflow",
        workflow_total_steps=len(steps),
    )

    stop_event = threading.Event()
    managed: _ManagedWorkflow

    def _workflow_target() -> None:
        _run_pipeline_workflow(managed, options, db_config=db_config, timeout_seconds=timeout_seconds)

    thread = threading.Thread(target=_workflow_target, daemon=True, name=f"pipeline-workflow-{run_id}")
    managed = _ManagedWorkflow(
        record=record,
        thread=thread,
        started_perf=time.perf_counter(),
        stop_event=stop_event,
    )

    with _REGISTRY_LOCK:
        _ACTIVE_WORKFLOWS[run_id] = managed
    _persist_record(record)
    thread.start()
    return record


def list_active_pipeline_runs() -> list[dict[str, object]]:
    snapshots: list[dict[str, object]] = []
    for run_id in list(_ACTIVE_RUNS.keys()):
        snapshot = poll_pipeline_run(run_id)
        if snapshot is not None:
            snapshots.append(snapshot)
    for run_id in list(_ACTIVE_WORKFLOWS.keys()):
        snapshot = poll_pipeline_run(run_id)
        if snapshot is not None:
            snapshots.append(snapshot)
    snapshots.sort(key=lambda item: str(item.get("executed_at", "")), reverse=True)
    return snapshots


def poll_pipeline_run(run_id: str) -> dict[str, object] | None:
    """Met à jour un run actif et retourne un snapshot sérialisable."""
    with _REGISTRY_LOCK:
        workflow = _ACTIVE_WORKFLOWS.get(run_id)
        managed = _ACTIVE_RUNS.get(run_id)
    if workflow is not None:
        return _poll_workflow_run(run_id, workflow)
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


def stop_pipeline_run(run_id: str) -> bool:
    """Demande l'arrêt d'un run actif."""
    with _REGISTRY_LOCK:
        managed = _ACTIVE_RUNS.get(run_id)
        workflow = _ACTIVE_WORKFLOWS.get(run_id)
    if workflow is not None:
        with workflow.lock:
            workflow.record = _with_updates(workflow.record, stop_requested=True)
            child_run_id = workflow.current_child_run_id
            record = workflow.record
        _persist_record(record)
        workflow.stop_event.set()
        if child_run_id:
            stop_pipeline_run(child_run_id)
        return True
    if managed is None:
        return False

    managed.record = _with_updates(managed.record, stop_requested=True)
    _kill_process_tree(managed.process)
    _persist_record(_with_updates(managed.record, status="stopped"))
    return True


def load_pipeline_history() -> list[dict[str, object]]:
    """Charge l'historique persistant des runs IHM."""
    history = list(_read_history_index().values())
    history.sort(
        key=lambda item: str(item.get("finished_at") or item.get("executed_at") or ""),
        reverse=True,
    )
    return history


def get_pipeline_run_record(run_id: str) -> dict[str, object] | None:
    active = poll_pipeline_run(run_id)
    if active is not None:
        return active
    return _read_history_index().get(run_id)


def read_pipeline_logs(run_id: str, stream: Literal["stdout", "stderr", "all"] = "all") -> str:
    """Retourne les logs complets d'un run selon le flux demandé."""
    record = get_pipeline_run_record(run_id)
    if record is None:
        return ""

    path_key = {
        "stdout": "stdout_path",
        "stderr": "stderr_path",
        "all": "combined_path",
    }[stream]
    path = Path(str(record.get(path_key, "")))
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def build_log_download_name(run_id: str, stream: Literal["stdout", "stderr", "all"] = "all") -> str:
    record = get_pipeline_run_record(run_id)
    step_key = str(record.get("step_key", "pipeline")) if record else "pipeline"
    return f"{step_key}_{run_id}_{stream}.log"

