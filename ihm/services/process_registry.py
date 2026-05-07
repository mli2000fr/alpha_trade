"""Registre global des pipelines lancés en arrière-plan depuis l'IHM.

Phase 6.2 (refactor) :
- ``atexit`` hook : tue les processus enfants encore actifs si Streamlit est
  arrêté brutalement (Ctrl-C, fermeture du terminal).
- Rotation des artefacts : les runs plus vieux que
  ``IHM_RUNS_RETENTION_DAYS`` (défaut 30 jours) sont purgés au démarrage.
- Audit shell quoting : ``subprocess.Popen`` est invoqué sur ``list[str]``
  sans ``shell=True`` ; aucune interpolation shell n'a lieu.
"""
from __future__ import annotations

import atexit
import json
import logging
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal, cast

from ihm.components.status_badges import classify_heartbeat_freshness

LOGGER = logging.getLogger(__name__)

# Phase 6.2 — rétention configurable via env (défaut 30 jours).
RUNS_RETENTION_ENV = "IHM_RUNS_RETENTION_DAYS"
DEFAULT_RUNS_RETENTION_DAYS = 30

from ihm.services.pipeline_runner import (
    PROJECT_ROOT,
    PipelineLaunchOptions,
    PipelineStepDefinition,
    WorkflowStartStep,
    build_pipeline_command,
    build_subprocess_env,
    format_command_for_display,
    get_pipeline_workflow_steps,
)
from ihm.services.run_summary import aggregate_workflow_run_summary
from database.run_business_summaries import persist_pipeline_run_record_summary

RunStatus = Literal["scheduled", "starting", "running", "completed", "failed", "timeout", "stopped"]
TAIL_MAX_LINES = 400
RUNS_DIR = PROJECT_ROOT / "artifacts" / "ihm_pipeline_runs"
HISTORY_INDEX_PATH = RUNS_DIR / "history_index.json"
RUN_RECORD_FILENAME = "record.json"
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"
WINDOWS_POST_SUCCESS_CRASH_CODES = {3221226505}
ML_TRAIN_SUMMARY_RE = re.compile(r"Completed:\s*(\d+)\s+Skipped:\s*(\d+)\s+Failed:\s*(\d+)")
ML_TRAIN_ORCHESTRATOR_RE = re.compile(r"run_training_batch finished completed=(\d+) skipped=(\d+) failed=(\d+)")
ML_PREDICT_SUMMARY_RE = re.compile(r"Model Factory — Predictions:\s*(\d+)\s+rows")
RECOVERABLE_RUN_ID_RE = re.compile(r"^\d{8}_\d{6}_[0-9a-f]{8}$")
WORKFLOW_TOTAL_STEPS_RE = re.compile(r"workflow complet(?: [^()]*)? \((\d+) étapes exécutées,")
WORKFLOW_STEP_START_RE = re.compile(r"=== \[(\d+)/(\d+)] Démarrage (.+?) ===")
WORKFLOW_STEP_DONE_RE = re.compile(r"=== \[(\d+)/(\d+)] Terminé (.+?) \(run `([^`]+)`\) ===")
WORKFLOW_INTERRUPTED_RE = re.compile(r"Workflow interrompu sur (.+?) — statut `([^`]+)` \(run `([^`]+)`\)\.")


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
    scheduled_for: str | None = None
    actual_started_at: str | None = None
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
    workflow_current_child_run_id: str | None = None
    workflow_child_run_ids: list[str] = field(default_factory=list)
    run_summary: dict[str, object] = field(default_factory=dict)
    heartbeat_interval_seconds: float | None = None
    last_heartbeat_at: str | None = None
    heartbeat_age_seconds: int | None = None
    watchdog_timeout_seconds: int | None = None
    watchdog_state: str = "unknown"
    watchdog_message: str = ""

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
    started_perf: float | None
    stop_event: threading.Event
    lock: threading.Lock = field(default_factory=threading.Lock)
    stdout_tail: list[str] = field(default_factory=list)
    stderr_tail: list[str] = field(default_factory=list)
    current_child_run_id: str | None = None


_REGISTRY_LOCK = threading.Lock()
_ACTIVE_RUNS: dict[str, _ManagedRun] = {}
_ACTIVE_WORKFLOWS: dict[str, _ManagedWorkflow] = {}


def _resolve_workflow_steps(
    *,
    start_step: WorkflowStartStep,
    include_ml_train: bool,
    include_corporate_actions_sync: bool,
    include_corporate_actions_apply: bool,
    selected_step_keys: tuple[str, ...] | None = None,
) -> tuple[PipelineStepDefinition, ...]:
    return cast(
        tuple[PipelineStepDefinition, ...],
        get_pipeline_workflow_steps(
            start_step=start_step,
            include_ml_train=include_ml_train,
            include_corporate_actions_sync=include_corporate_actions_sync,
            include_corporate_actions_apply=include_corporate_actions_apply,
            selected_step_keys=selected_step_keys,
        ),
    )


def _format_workflow_core_step_ranges(steps: tuple[PipelineStepDefinition, ...]) -> str:
    core_numbers = [int(step.num) for step in steps if step.num.isdigit() and 1 <= int(step.num) <= 12]
    if not core_numbers:
        return "aucune"

    ranges: list[str] = []
    start = end = core_numbers[0]
    for current in core_numbers[1:]:
        if current == end + 1:
            end = current
            continue
        ranges.append(f"{start}" if start == end else f"{start} → {end}")
        start = end = current
    ranges.append(f"{start}" if start == end else f"{start} → {end}")
    return ", ".join(ranges)


def _workflow_scope_label(
    *,
    start_step: WorkflowStartStep,
    include_corporate_actions_sync: bool,
    include_corporate_actions_apply: bool,
    selected_step_keys: tuple[str, ...] | None = None,
    steps: tuple[PipelineStepDefinition, ...] | None = None,
) -> str:
    if selected_step_keys is not None:
        effective_steps = steps or _resolve_workflow_steps(
            start_step=start_step,
            include_ml_train=True,
            include_corporate_actions_sync=include_corporate_actions_sync,
            include_corporate_actions_apply=include_corporate_actions_apply,
            selected_step_keys=selected_step_keys,
        )
        return f"étapes { _format_workflow_core_step_ranges(effective_steps) }"

    scope = f"{start_step} → 12"
    if include_corporate_actions_apply:
        return f"{scope} + 13 → 14"
    if include_corporate_actions_sync:
        return f"{scope} + 13"
    return scope


def _workflow_step_label(
    *,
    start_step: WorkflowStartStep,
    include_ml_train: bool,
    include_corporate_actions_sync: bool,
    include_corporate_actions_apply: bool,
    selected_step_keys: tuple[str, ...] | None = None,
    steps: tuple[PipelineStepDefinition, ...] | None = None,
) -> str:
    if selected_step_keys is not None:
        scope = _workflow_scope_label(
            start_step=start_step,
            include_corporate_actions_sync=include_corporate_actions_sync,
            include_corporate_actions_apply=include_corporate_actions_apply,
            selected_step_keys=selected_step_keys,
            steps=steps,
        )
        return f"Workflow personnalisé — {scope}"

    ml_mode = "avec étape 9 — ML Train" if include_ml_train else "sans étape 9 — ML Train"
    scope = _workflow_scope_label(
        start_step=start_step,
        include_corporate_actions_sync=include_corporate_actions_sync,
        include_corporate_actions_apply=include_corporate_actions_apply,
    )
    return f"Workflow complet {scope} ({ml_mode})"


def _workflow_command_display(
    *,
    start_step: WorkflowStartStep,
    include_ml_train: bool,
    include_corporate_actions_sync: bool,
    include_corporate_actions_apply: bool,
    total_steps: int,
    selected_step_keys: tuple[str, ...] | None = None,
    steps: tuple[PipelineStepDefinition, ...] | None = None,
) -> str:
    if selected_step_keys is not None:
        scope = _workflow_scope_label(
            start_step=start_step,
            include_corporate_actions_sync=include_corporate_actions_sync,
            include_corporate_actions_apply=include_corporate_actions_apply,
            selected_step_keys=selected_step_keys,
            steps=steps,
        )
        return f"Workflow séquentiel Pipeline personnalisé {scope} | {total_steps} étape(s) exécutée(s)"

    ml_mode = "avec ML Train" if include_ml_train else "sans ML Train"
    scope = _workflow_scope_label(
        start_step=start_step,
        include_corporate_actions_sync=include_corporate_actions_sync,
        include_corporate_actions_apply=include_corporate_actions_apply,
    )
    return f"Workflow séquentiel Pipeline {scope} | {ml_mode} | {total_steps} étape(s) exécutée(s)"


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
    _write_record_artifact(record.to_state())


def _record_artifact_path_from_record(record: dict[str, object]) -> Path:
    stdout_path = Path(str(record.get("stdout_path") or "")).resolve() if str(record.get("stdout_path") or "").strip() else None
    if stdout_path is not None and stdout_path.name:
        return stdout_path.parent / RUN_RECORD_FILENAME
    return _run_dir_for(str(record.get("step_key") or "pipeline"), str(record.get("run_id") or "unknown")) / RUN_RECORD_FILENAME


def _write_record_artifact(record: dict[str, object]) -> None:
    try:
        artifact_path = _record_artifact_path_from_record(record)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        LOGGER.debug("Persist record artifact failed for run_id=%s", record.get("run_id"), exc_info=True)


def _load_record_artifact(run_dir: Path) -> dict[str, object] | None:
    artifact_path = run_dir / RUN_RECORD_FILENAME
    if not artifact_path.exists():
        return None
    try:
        parsed = json.loads(artifact_path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _parse_run_id_datetime(run_id: str, fallback_path: Path | None = None) -> str:
    cleaned = str(run_id or "").strip()
    if RECOVERABLE_RUN_ID_RE.match(cleaned):
        try:
            return datetime.strptime(cleaned[:15], "%Y%m%d_%H%M%S").isoformat(timespec="seconds")
        except ValueError:
            pass
    if fallback_path is not None:
        try:
            return datetime.fromtimestamp(fallback_path.stat().st_mtime).isoformat(timespec="seconds")
        except OSError:
            pass
    return datetime.now().isoformat(timespec="seconds")


def _file_line_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def _safe_read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _infer_finished_at(run_dir: Path) -> str | None:
    timestamps: list[float] = []
    for file_name in ("stdout.log", "stderr.log", "combined.log", RUN_RECORD_FILENAME):
        candidate = run_dir / file_name
        if not candidate.exists():
            continue
        try:
            timestamps.append(candidate.stat().st_mtime)
        except OSError:
            continue
    if not timestamps:
        return None
    return datetime.fromtimestamp(max(timestamps)).isoformat(timespec="seconds")


def _recover_workflow_run_from_directory(run_dir: Path) -> tuple[dict[str, object] | None, dict[str, dict[str, object]]]:
    artifact = _load_record_artifact(run_dir)
    if artifact is not None:
        return artifact, {}

    run_id = run_dir.name.strip()
    if not RECOVERABLE_RUN_ID_RE.match(run_id):
        return None, {}

    combined_path = run_dir / "combined.log"
    stdout_path = run_dir / "stdout.log"
    stderr_path = run_dir / "stderr.log"
    combined_text = _safe_read_text(combined_path)

    child_hints: dict[str, dict[str, object]] = {}
    child_run_ids: list[str] = []
    workflow_completed_steps = 0
    workflow_total_steps = 0
    current_step_label: str | None = None
    current_child_run_id: str | None = None
    interrupted_status: str | None = None

    total_steps_match = WORKFLOW_TOTAL_STEPS_RE.search(combined_text)
    if total_steps_match is not None:
        workflow_total_steps = int(total_steps_match.group(1))

    for line in combined_text.splitlines():
        step_start_match = WORKFLOW_STEP_START_RE.search(line)
        if step_start_match is not None:
            workflow_total_steps = max(workflow_total_steps, int(step_start_match.group(2)))
            current_step_label = step_start_match.group(3)

        step_done_match = WORKFLOW_STEP_DONE_RE.search(line)
        if step_done_match is not None:
            workflow_completed_steps = max(workflow_completed_steps, int(step_done_match.group(1)))
            workflow_total_steps = max(workflow_total_steps, int(step_done_match.group(2)))
            current_step_label = step_done_match.group(3)
            child_run_id = step_done_match.group(4)
            if child_run_id not in child_run_ids:
                child_run_ids.append(child_run_id)
            child_hints[child_run_id] = {
                "parent_run_id": run_id,
                "step_label": step_done_match.group(3),
                "status": "completed",
            }
            continue

        interrupted_match = WORKFLOW_INTERRUPTED_RE.search(line)
        if interrupted_match is not None:
            current_step_label = interrupted_match.group(1)
            interrupted_status = interrupted_match.group(2)
            interrupted_child_run_id = interrupted_match.group(3)
            current_child_run_id = interrupted_child_run_id
            if interrupted_child_run_id not in child_run_ids:
                child_run_ids.append(interrupted_child_run_id)
            child_hints[interrupted_child_run_id] = {
                    "parent_run_id": run_id,
                    "step_label": interrupted_match.group(1),
                    "status": interrupted_status,
                }

    status: str = "stopped"
    if "Workflow complet terminé avec succès." in combined_text:
        status = "completed"
        current_step_label = None
        current_child_run_id = None
    elif interrupted_status in {"failed", "timeout", "stopped"}:
        status = interrupted_status
    elif "Erreur interne du workflow" in combined_text:
        status = "failed"

    recovered = {
        "run_id": run_id,
        "step_key": "pipeline_workflow",
        "step_label": "Workflow complet",
        "command": [],
        "command_display": "",
        "account_id": None,
        "status": status,
        "executed_at": _parse_run_id_datetime(run_id, run_dir),
        "actual_started_at": None if status == "scheduled" else _parse_run_id_datetime(run_id, run_dir),
        "finished_at": None if status in {"scheduled", "starting", "running"} else _infer_finished_at(run_dir),
        "returncode": None,
        "duration_seconds": 0.0,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "combined_path": str(combined_path),
        "stdout_lines": _file_line_count(stdout_path),
        "stderr_lines": _file_line_count(stderr_path),
        "timeout_seconds": None,
        "stop_requested": status == "stopped",
        "run_kind": "workflow",
        "parent_run_id": None,
        "workflow_total_steps": workflow_total_steps,
        "workflow_completed_steps": workflow_completed_steps,
        "workflow_current_step_key": None,
        "workflow_current_step_label": current_step_label if status in {"scheduled", "starting", "running", "failed", "timeout", "stopped"} else None,
        "workflow_current_child_run_id": current_child_run_id if status in {"scheduled", "starting", "running", "failed", "timeout", "stopped"} else None,
        "workflow_child_run_ids": child_run_ids,
        "run_summary": {},
    }
    return recovered, child_hints


def _recover_step_run_from_directory(
    step_key: str,
    run_dir: Path,
    *,
    child_hints: dict[str, dict[str, object]],
) -> dict[str, object] | None:
    artifact = _load_record_artifact(run_dir)
    if artifact is not None:
        return artifact

    run_id = run_dir.name.strip()
    if not RECOVERABLE_RUN_ID_RE.match(run_id):
        return None

    hint = child_hints.get(run_id, {})
    stdout_path = run_dir / "stdout.log"
    stderr_path = run_dir / "stderr.log"
    combined_path = run_dir / "combined.log"
    stderr_lines = _file_line_count(stderr_path)
    inferred_status = str(hint.get("status") or "").strip() or ("failed" if stderr_lines > 0 else "completed")

    return {
        "run_id": run_id,
        "step_key": step_key,
        "step_label": str(hint.get("step_label") or step_key),
        "command": [],
        "command_display": "",
        "account_id": None,
        "status": inferred_status,
        "executed_at": _parse_run_id_datetime(run_id, run_dir),
        "actual_started_at": _parse_run_id_datetime(run_id, run_dir),
        "finished_at": None if inferred_status in {"starting", "running"} else _infer_finished_at(run_dir),
        "returncode": None,
        "duration_seconds": 0.0,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "combined_path": str(combined_path),
        "stdout_lines": _file_line_count(stdout_path),
        "stderr_lines": stderr_lines,
        "timeout_seconds": None,
        "stop_requested": inferred_status == "stopped",
        "run_kind": "step",
        "parent_run_id": str(hint.get("parent_run_id") or "") or None,
        "workflow_total_steps": 0,
        "workflow_completed_steps": 0,
        "workflow_current_step_key": None,
        "workflow_current_step_label": None,
        "workflow_current_child_run_id": None,
        "workflow_child_run_ids": [],
        "run_summary": {},
    }


def _recover_history_index_entries(existing_index: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    if not RUNS_DIR.exists():
        return {}

    recovered: dict[str, dict[str, object]] = {}
    child_hints: dict[str, dict[str, object]] = {}
    known_run_ids = set(existing_index)

    workflow_dir = RUNS_DIR / "pipeline_workflow"
    if workflow_dir.exists() and workflow_dir.is_dir():
        for run_dir in sorted((candidate for candidate in workflow_dir.iterdir() if candidate.is_dir()), reverse=True):
            workflow_record, workflow_child_hints = _recover_workflow_run_from_directory(run_dir)
            child_hints.update(workflow_child_hints)
            if workflow_record is None:
                continue
            run_id = str(workflow_record.get("run_id") or "").strip()
            if run_id and run_id not in known_run_ids:
                recovered[run_id] = workflow_record
                known_run_ids.add(run_id)

    for step_dir in sorted((candidate for candidate in RUNS_DIR.iterdir() if candidate.is_dir() and candidate.name != "pipeline_workflow"), reverse=True):
        for run_dir in sorted((candidate for candidate in step_dir.iterdir() if candidate.is_dir()), reverse=True):
            run_id = run_dir.name.strip()
            if run_id in known_run_ids:
                continue
            recovered_record = _recover_step_run_from_directory(step_dir.name, run_dir, child_hints=child_hints)
            if recovered_record is None:
                continue
            recovered[run_id] = recovered_record
            known_run_ids.add(run_id)

    return recovered


def _normalize_inactive_scheduled_workflow_record(
    record: dict[str, object],
    *,
    active_workflow_run_ids: set[str],
) -> tuple[dict[str, object], bool]:
    run_id = str(record.get("run_id") or "").strip()
    if not run_id or run_id in active_workflow_run_ids:
        return record, False
    if str(record.get("run_kind") or "") != "workflow":
        return record, False
    if str(record.get("status") or "") != "scheduled":
        return record, False

    normalized = dict(record)
    normalized["status"] = "stopped"
    normalized["stop_requested"] = True
    normalized["workflow_current_step_key"] = None
    normalized["workflow_current_step_label"] = None
    normalized["workflow_current_child_run_id"] = None
    normalized["finished_at"] = str(record.get("finished_at") or datetime.now().isoformat(timespec="seconds"))
    normalized["watchdog_state"] = "inactive"
    normalized["watchdog_message"] = (
        "Workflow planifié non repris après arrêt/redémarrage de l'IHM — relancez-le ou replanifiez un nouveau départ différé."
    )
    return normalized, True


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


def _summary_int(summary: dict[str, object], key: str) -> int:
    value = summary.get(key, 0)
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _summary_float(summary: dict[str, object], key: str) -> float | None:
    value = summary.get(key)
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _derive_watchdog_payload(record: PipelineRunRecord) -> dict[str, object]:
    summary = record.run_summary if isinstance(record.run_summary, dict) else {}
    heartbeat_interval_seconds = _summary_float(summary, "heartbeat_interval_seconds")
    watchdog_timeout_seconds = _summary_int(summary, "watchdog_timeout_seconds") or None
    last_heartbeat_at = str(summary.get("last_heartbeat_at") or "").strip() or None
    if record.status not in {"starting", "running"}:
        return {
            "heartbeat_interval_seconds": heartbeat_interval_seconds,
            "last_heartbeat_at": last_heartbeat_at,
            "heartbeat_age_seconds": None,
            "watchdog_timeout_seconds": watchdog_timeout_seconds,
            "watchdog_state": "inactive",
            "watchdog_message": "Watchdog inactif (run terminé).",
            "should_timeout": False,
        }
    if heartbeat_interval_seconds is None or heartbeat_interval_seconds <= 0:
        return {
            "heartbeat_interval_seconds": heartbeat_interval_seconds,
            "last_heartbeat_at": last_heartbeat_at,
            "heartbeat_age_seconds": None,
            "watchdog_timeout_seconds": watchdog_timeout_seconds,
            "watchdog_state": "disabled",
            "watchdog_message": "Aucun heartbeat structuré reçu — surveillance limitée aux logs/processus.",
            "should_timeout": False,
        }

    level, label, age_seconds = classify_heartbeat_freshness(
        last_heartbeat_at,
        heartbeat_interval_seconds,
        service_status=record.status,
    )
    if level == "ok":
        state = "alive"
        message = "Heartbeat frais — job vivant, même si les logs restent silencieux entre deux phases."
    elif level == "warn":
        state = "watch"
        message = "Heartbeat à surveiller — progression lente ou phase longue en cours."
    else:
        state = "stalled"
        message = "Heartbeat stale — le run semble réellement figé ou bloqué."
    should_timeout = bool(
        watchdog_timeout_seconds
        and age_seconds is not None
        and age_seconds >= watchdog_timeout_seconds
        and level != "ok"
    )
    return {
        "heartbeat_interval_seconds": heartbeat_interval_seconds,
        "last_heartbeat_at": last_heartbeat_at,
        "heartbeat_age_seconds": age_seconds,
        "watchdog_timeout_seconds": watchdog_timeout_seconds,
        "watchdog_state": state,
        "watchdog_message": message,
        "should_timeout": should_timeout,
    }


def _apply_watchdog_payload(record: PipelineRunRecord) -> PipelineRunRecord:
    payload = _derive_watchdog_payload(record)
    updates = {key: value for key, value in payload.items() if key != "should_timeout"}
    return _with_updates(record, **updates)


def _infer_ml_run_summary_from_logs(record: PipelineRunRecord) -> dict[str, object] | None:
    stdout_path = Path(record.stdout_path)
    if not stdout_path.exists():
        return None

    try:
        stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    if record.step_key == "ml_train":
        matches = ML_TRAIN_SUMMARY_RE.findall(stdout_text)
        if matches:
            completed, skipped, failed = (int(value) for value in matches[-1])
            total = completed + skipped + failed
            if total > 0:
                return {
                    "mode": "train",
                    "symbols_total": total,
                    "symbols_completed": completed,
                    "symbols_skipped": skipped,
                    "symbols_failed": failed,
                    "summary_source": "log_fallback_training_summary",
                }

        matches = ML_TRAIN_ORCHESTRATOR_RE.findall(stdout_text)
        if matches:
            completed, skipped, failed = (int(value) for value in matches[-1])
            total = completed + skipped + failed
            if total > 0:
                return {
                    "mode": "train",
                    "symbols_total": total,
                    "symbols_completed": completed,
                    "symbols_skipped": skipped,
                    "symbols_failed": failed,
                    "summary_source": "log_fallback_orchestrator",
                }

    if record.step_key == "ml_predict":
        matches = ML_PREDICT_SUMMARY_RE.findall(stdout_text)
        if matches:
            completed = int(matches[-1])
            if completed > 0:
                return {
                    "mode": "predict",
                    "symbols_total": completed,
                    "symbols_completed": completed,
                    "symbols_skipped": 0,
                    "symbols_failed": 0,
                    "summary_source": "log_fallback_predictions_summary",
                }

    return None


def _override_failed_status_run_summary(record: PipelineRunRecord, returncode: int | None) -> dict[str, object] | None:
    if returncode not in WINDOWS_POST_SUCCESS_CRASH_CODES:
        return None
    if record.step_key not in {"ml_train", "ml_predict"}:
        return None
    summary = dict(record.run_summary) if isinstance(record.run_summary, dict) else {}
    if not summary:
        inferred_summary = _infer_ml_run_summary_from_logs(record)
        if inferred_summary is None:
            return None
        summary = inferred_summary

    mode = str(summary.get("mode", "")).strip().lower()
    total = _summary_int(summary, "symbols_total")
    completed = _summary_int(summary, "symbols_completed")
    skipped = _summary_int(summary, "symbols_skipped")
    failed = _summary_int(summary, "symbols_failed")

    if mode == "train":
        return summary if total > 0 and failed == 0 and total == (completed + skipped) else None

    if mode == "predict":
        return summary if total > 0 and failed == 0 and total == (completed + skipped) else None

    return None


def _should_override_failed_status(record: PipelineRunRecord, returncode: int | None) -> bool:
    return _override_failed_status_run_summary(record, returncode) is not None


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
        merged_summary = dict(managed.record.run_summary) if isinstance(managed.record.run_summary, dict) else {}
        merged_summary.update(latest_summary)
        managed.record = _with_updates(managed.record, run_summary=merged_summary)
        managed.record = _apply_watchdog_payload(managed.record)

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
    managed.record = _apply_watchdog_payload(managed.record)
    watchdog_payload = _derive_watchdog_payload(managed.record)
    if returncode is None and watchdog_payload.get("should_timeout"):
        _kill_process_tree(managed.process)
        managed.timed_out = True
        Path(managed.record.stderr_path).parent.mkdir(parents=True, exist_ok=True)
        timeout_message = "\nWatchdog heartbeat timeout dépassé : le run n'émet plus de heartbeat structuré.\n"
        with Path(managed.record.stderr_path).open("a", encoding="utf-8") as fh:
            fh.write(timeout_message)
        with Path(managed.record.combined_path).open("a", encoding="utf-8") as fh:
            fh.write(f"[stderr] {timeout_message}")
        _append_tail(managed.stderr_tail or [], timeout_message)
        managed.record = _with_updates(
            managed.record,
            stderr_lines=managed.record.stderr_lines + 1,
            watchdog_state="timed_out",
            watchdog_message="Watchdog heartbeat timeout dépassé — run arrêté automatiquement.",
        )
        returncode = -2
    returncode = managed.process.poll() if returncode is None else returncode

    if returncode is None:
        managed.record = _with_updates(managed.record, status="running", duration_seconds=elapsed)
        return managed.record

    managed.stdout_thread.join(timeout=0.2)
    managed.stderr_thread.join(timeout=0.2)
    _drain_events(managed)
    managed.record = _apply_watchdog_payload(managed.record)

    if managed.timed_out:
        status: RunStatus = "timeout"
        final_code = -2
    elif managed.record.stop_requested:
        status = "stopped"
        final_code = -3 if returncode == 0 else returncode
    else:
        status = "completed" if returncode == 0 else "failed"
        final_code = returncode

    override_summary = _override_failed_status_run_summary(managed.record, final_code) if status == "failed" else None
    if override_summary is not None:
        normalized_summary = dict(override_summary)
        normalized_summary.setdefault("process_returncode_original", final_code)
        normalized_summary.setdefault("completion_override", "windows_post_success_crash")
        managed.record = _with_updates(managed.record, run_summary=normalized_summary)
        status = "completed"
        final_code = 0

    managed.record = _with_updates(
        managed.record,
        status=status,
        returncode=final_code,
        duration_seconds=round(time.perf_counter() - managed.started_perf, 2),
        finished_at=datetime.now().isoformat(timespec="seconds"),
        watchdog_state="timed_out" if managed.timed_out else managed.record.watchdog_state,
        watchdog_message=(
            "Watchdog heartbeat timeout dépassé — run arrêté automatiquement."
            if managed.timed_out
            else managed.record.watchdog_message
        ),
    )
    try:
        persist_pipeline_run_record_summary(managed.record.to_state())
    except Exception:
        pass
    _persist_record(managed.record)
    return managed.record


def _tail_text(lines: list[str]) -> str:
    return "".join(lines)


def _workflow_elapsed_seconds(managed: _ManagedWorkflow) -> float:
    started_perf = managed.started_perf
    if started_perf is None:
        return 0.0
    return round(time.perf_counter() - started_perf, 2)


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
    record = _update_workflow_record(
        managed,
        status=status,
        returncode=returncode,
        duration_seconds=_workflow_elapsed_seconds(managed),
        finished_at=datetime.now().isoformat(timespec="seconds"),
        workflow_completed_steps=workflow_completed_steps,
        workflow_current_step_key=None,
        workflow_current_step_label=None,
        workflow_current_child_run_id=None,
    )
    try:
        persist_pipeline_run_record_summary(record.to_state())
    except Exception:
        pass
    return record


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
    start_step: WorkflowStartStep = "1",
    include_ml_train: bool = True,
    include_corporate_actions_sync: bool = False,
    include_corporate_actions_apply: bool = False,
    selected_step_keys: tuple[str, ...] | None = None,
) -> None:
    steps = cast(
        tuple[PipelineStepDefinition, ...],
        _resolve_workflow_steps(
            start_step=start_step,
            include_ml_train=include_ml_train,
            include_corporate_actions_sync=include_corporate_actions_sync,
            include_corporate_actions_apply=include_corporate_actions_apply,
            selected_step_keys=selected_step_keys,
        ),
    )
    total_steps = len(steps)

    # Freeze le trade_date au démarrage du workflow pour garantir que toutes les
    # étapes (5 → 11+) partagent la même date logique, même si l'exécution
    # déborde sur le lendemain (ex : workflow lancé à 22h, étape 11 atteinte
    # après minuit). Sans ce gel, chaque sous-étape ré-évalue date.today() à
    # son démarrage, créant des incohérences (cf. PIT fallback dans risk_management).
    from dataclasses import replace as _dc_replace
    from datetime import date as _date

    if not (options.trade_date or "").strip():
        frozen_trade_date = _date.today().isoformat()
        options = _dc_replace(options, trade_date=frozen_trade_date)
        _append_workflow_event(
            managed,
            f"trade_date du workflow figé à {frozen_trade_date} (toutes les étapes utiliseront cette date).",
        )

    try:
        workflow_mode = _workflow_scope_label(
            start_step=start_step,
            include_corporate_actions_sync=include_corporate_actions_sync,
            include_corporate_actions_apply=include_corporate_actions_apply,
            selected_step_keys=selected_step_keys,
            steps=steps,
        )
        if selected_step_keys is not None:
            _append_workflow_event(
                managed,
                f"Démarrage du workflow personnalisé ({total_steps} étapes exécutées, {workflow_mode}).",
            )
        else:
            ml_mode = "avec étape 9 — ML Train" if include_ml_train else "sans étape 9 — ML Train"
            _append_workflow_event(
                managed,
                f"Démarrage du workflow complet {workflow_mode} ({total_steps} étapes exécutées, {ml_mode}).",
            )
        _update_workflow_record(managed, status="running", workflow_total_steps=total_steps, workflow_completed_steps=0)

        completed_steps = 0
        child_run_ids: list[str] = []
        child_runs_with_summary: dict[str, dict[str, object]] = {}

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
                workflow_current_child_run_id=child_record.run_id,
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
                if child_snapshot is not None and isinstance(child_snapshot.get("run_summary"), dict) and child_snapshot.get("run_summary"):
                    child_runs_with_summary[child_record.run_id] = dict(child_snapshot)
                aggregated_summary = aggregate_workflow_run_summary(child_runs_with_summary.values())

                child_status = str(child_snapshot.get("status", "")) if child_snapshot is not None else "failed"
                _update_workflow_record(
                    managed,
                    status="running",
                    duration_seconds=_workflow_elapsed_seconds(managed),
                    workflow_current_step_key=step.key,
                    workflow_current_step_label=step_label,
                    workflow_current_child_run_id=child_record.run_id,
                    workflow_child_run_ids=list(child_run_ids),
                    workflow_completed_steps=completed_steps,
                    run_summary=aggregated_summary,
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
            _update_workflow_record(
                managed,
                workflow_completed_steps=completed_steps,
                workflow_current_child_run_id=None,
                workflow_child_run_ids=list(child_run_ids),
            )
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
            managed.record = _with_updates(record, duration_seconds=_workflow_elapsed_seconds(managed))
            record = managed.record
            _persist_record(record)
        elif record.status == "scheduled" and record.duration_seconds != 0.0:
            managed.record = _with_updates(record, duration_seconds=0.0)
            record = managed.record
            _persist_record(record)
        snapshot = {
            **record.to_state(),
            "stdout_tail": _tail_text(managed.stdout_tail),
            "stderr_tail": _tail_text(managed.stderr_tail),
            "is_active": record.status in {"scheduled", "starting", "running"},
        }

    if not snapshot["is_active"] and not managed.thread.is_alive():
        with _REGISTRY_LOCK:
            _ACTIVE_WORKFLOWS.pop(run_id, None)
    return snapshot


def _run_dir_for(step_key: str, run_id: str) -> Path:
    return RUNS_DIR / step_key / run_id


def start_managed_run(
    *,
    step_key: str,
    step_label: str,
    command: list[str],
    account_id: str | None = None,
    db_config: dict[str, str | None] | None = None,
    timeout_seconds: int | None = None,
    parent_run_id: str | None = None,
) -> PipelineRunRecord:
    """Démarre un sous-processus arbitraire piloté par le registre IHM."""
    _ensure_storage()
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
    created_at = datetime.now().isoformat(timespec="seconds")

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
        account_id=account_id,
        status="running",
        executed_at=created_at,
        actual_started_at=created_at,
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
    from dataclasses import replace as _dc_replace
    from datetime import date as _date

    # Freeze trade_date au lancement si non défini, pour éviter qu'un sous-process
    # appelle date.today() après minuit alors que les étapes amont ont stamped
    # une date différente. Idempotent : si un workflow parent a déjà figé la
    # date, ce bloc est no-op.
    if not (options.trade_date or "").strip():
        options = _dc_replace(options, trade_date=_date.today().isoformat())

    # Si l'option "Forcer trade_date sur le snapshot le plus récent" est cochée
    # (défaut IHM), on remplace trade_date par le MAX(snapshot_date) <= trade_date
    # avec is_candidate=1 dans stock_scores_history. Permet de continuer un
    # workflow démarré la veille même après réouverture de la session Streamlit
    # (qui a réinitialisé trade_date à date.today()).
    if getattr(options, "force_trade_date_to_latest_snapshot", False) and (options.trade_date or "").strip():
        try:
            from ihm.services.queries import resolve_latest_candidate_snapshot_date

            resolved = resolve_latest_candidate_snapshot_date(options.trade_date)
            if resolved is not None and resolved.isoformat() != options.trade_date:
                LOGGER.info(
                    "start_pipeline_run | trade_date forcé sur snapshot le plus récent : %s -> %s (step=%s)",
                    options.trade_date,
                    resolved.isoformat(),
                    step_key,
                )
                options = _dc_replace(options, trade_date=resolved.isoformat())
        except Exception:
            LOGGER.warning(
                "start_pipeline_run | echec resolution snapshot PIT pour trade_date=%s ; valeur conservée.",
                options.trade_date,
                exc_info=True,
            )

    command = build_pipeline_command(step_key, options)
    return start_managed_run(
        step_key=step_key,
        step_label=step_label,
        command=command,
        account_id=options.account_id,
        db_config=db_config,
        timeout_seconds=timeout_seconds,
        parent_run_id=parent_run_id,
    )


def start_pipeline_workflow(
    options: PipelineLaunchOptions,
    *,
    db_config: dict[str, str | None] | None = None,
    timeout_seconds: int | None = None,
    start_step: WorkflowStartStep = "1",
    include_ml_train: bool = True,
    include_corporate_actions_sync: bool = False,
    include_corporate_actions_apply: bool = False,
    selected_step_keys: tuple[str, ...] | None = None,
    scheduled_for: datetime | None = None,
) -> PipelineRunRecord:
    """Démarre un workflow séquentiel complet en arrière-plan."""
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
    created_at = datetime.now().isoformat(timespec="seconds")

    include_sync = include_corporate_actions_sync or include_corporate_actions_apply
    steps = cast(
        tuple[PipelineStepDefinition, ...],
        _resolve_workflow_steps(
            start_step=start_step,
            include_ml_train=include_ml_train,
            include_corporate_actions_sync=include_sync,
            include_corporate_actions_apply=include_corporate_actions_apply,
            selected_step_keys=selected_step_keys,
        ),
    )
    workflow_label = _workflow_step_label(
        start_step=start_step,
        include_ml_train=include_ml_train,
        include_corporate_actions_sync=include_sync,
        include_corporate_actions_apply=include_corporate_actions_apply,
        selected_step_keys=selected_step_keys,
        steps=steps,
    )
    record = PipelineRunRecord(
        run_id=run_id,
        step_key="pipeline_workflow",
        step_label=workflow_label,
        command=[step.key for step in steps],
        command_display=_workflow_command_display(
            start_step=start_step,
            include_ml_train=include_ml_train,
            include_corporate_actions_sync=include_sync,
            include_corporate_actions_apply=include_corporate_actions_apply,
            total_steps=len(steps),
            selected_step_keys=selected_step_keys,
            steps=steps,
        ),
        account_id=options.account_id,
        status="scheduled" if scheduled_for is not None else "running",
        executed_at=created_at,
        scheduled_for=scheduled_for.isoformat(timespec="seconds") if scheduled_for is not None else None,
        actual_started_at=None if scheduled_for is not None else created_at,
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
        from ihm.services.pipeline_lock import (
            PipelineLockBusy,
            acquire_lock as _acquire_lock,
            release_lock as _release_lock,
        )

        workflow_lock = None

        try:
            if scheduled_for is not None:
                while not stop_event.is_set():
                    remaining_seconds = (scheduled_for - datetime.now()).total_seconds()
                    if remaining_seconds <= 0:
                        break
                    time.sleep(min(remaining_seconds, 1.0))
                if stop_event.is_set():
                    _append_workflow_event(managed, "Workflow planifié annulé avant son démarrage.", is_error=True)
                    _finalize_workflow_record(managed, status="stopped", returncode=-3, workflow_completed_steps=0)
                    return
                _append_workflow_event(managed, f"Démarrage différé atteint ({scheduled_for.isoformat(timespec='seconds')}) — tentative de lancement du workflow.")
                managed.started_perf = time.perf_counter()
                _update_workflow_record(
                    managed,
                    status="starting",
                    actual_started_at=datetime.now().isoformat(timespec="seconds"),
                    duration_seconds=0.0,
                )

            # Sprint S2 / A-014.1 — re-vérification du stop juste avant
            # l'acquisition du verrou (évite d'acquérir/libérer pour rien et
            # supprime la fenêtre de course entre la fin du sleep planifié et
            # l'acquisition du lock).
            if stop_event.is_set():
                _append_workflow_event(managed, "Workflow arrêté avant l'acquisition du verrou pipeline.", is_error=True)
                _finalize_workflow_record(managed, status="stopped", returncode=-3, workflow_completed_steps=0)
                return

            try:
                workflow_lock = _acquire_lock("pipeline", owner="pipeline_workflow", run_id=run_id)
            except PipelineLockBusy as exc:
                _append_workflow_event(
                    managed,
                    f"Impossible de démarrer le workflow planifié : verrou pipeline actif ({exc}).",
                    is_error=True,
                )
                _finalize_workflow_record(managed, status="failed", returncode=-2, workflow_completed_steps=0)
                return
            except Exception as exc:  # pragma: no cover — défense en profondeur
                _append_workflow_event(
                    managed,
                    f"Erreur inattendue lors de l'acquisition du verrou pipeline : {exc}.",
                    is_error=True,
                )
                _finalize_workflow_record(managed, status="failed", returncode=-1, workflow_completed_steps=0)
                return

            _run_pipeline_workflow(
                managed,
                options,
                db_config=db_config,
                timeout_seconds=timeout_seconds,
                start_step=start_step,
                include_ml_train=include_ml_train,
                include_corporate_actions_sync=include_sync,
                include_corporate_actions_apply=include_corporate_actions_apply,
                selected_step_keys=selected_step_keys,
            )
        except Exception as exc:  # pragma: no cover — garde-fou ultime
            # Sans cette branche, une exception non gérée tuerait le thread
            # sans finaliser le record, laissant le workflow "starting"/"running"
            # dans ``_ACTIVE_WORKFLOWS`` indéfiniment et bloquant tout nouveau
            # lancement (``list_active_pipeline_runs`` resterait non-vide).
            try:
                _append_workflow_event(managed, f"Erreur fatale du workflow_target : {exc}", is_error=True)
                _finalize_workflow_record(
                    managed,
                    status="failed",
                    returncode=-1,
                    workflow_completed_steps=managed.record.workflow_completed_steps,
                )
            except Exception:
                LOGGER.exception("workflow_target: échec finalisation après exception fatale")
        finally:
            if workflow_lock is not None:
                try:
                    _release_lock(workflow_lock)
                except Exception:
                    LOGGER.exception("workflow_target: échec release_lock pour run_id=%s", run_id)

    thread = threading.Thread(target=_workflow_target, daemon=True, name=f"pipeline-workflow-{run_id}")
    managed = _ManagedWorkflow(
        record=record,
        thread=thread,
        started_perf=None if scheduled_for is not None else time.perf_counter(),
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
    with _REGISTRY_LOCK:
        index = _read_history_index()
        recovered = _recover_history_index_entries(index)
        if recovered:
            index.update(recovered)
        active_workflow_run_ids = set(_ACTIVE_WORKFLOWS.keys())
        normalized_index: dict[str, dict[str, object]] = {}
        mutated = bool(recovered)
        for run_id, payload in index.items():
            normalized_payload, changed = _normalize_inactive_scheduled_workflow_record(
                payload,
                active_workflow_run_ids=active_workflow_run_ids,
            )
            normalized_index[run_id] = normalized_payload
            mutated = mutated or changed
        index = normalized_index
        if mutated:
            _write_history_index(index)
    history = list(index.values())
    history.sort(
        key=lambda item: str(item.get("finished_at") or item.get("executed_at") or ""),
        reverse=True,
    )
    return history


def get_pipeline_run_record(run_id: str) -> dict[str, object] | None:
    active = poll_pipeline_run(run_id)
    if active is not None:
        return active
    with _REGISTRY_LOCK:
        history = _read_history_index()
        payload = history.get(run_id)
        if payload is None:
            return None
        normalized_payload, changed = _normalize_inactive_scheduled_workflow_record(
            payload,
            active_workflow_run_ids=set(_ACTIVE_WORKFLOWS.keys()),
        )
        if changed:
            history[run_id] = normalized_payload
            _write_history_index(history)
        return normalized_payload


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


# ---------------------------------------------------------------------------
# Phase 6.2 — atexit hook + rotation artefacts.
# ---------------------------------------------------------------------------

def _retention_days() -> int:
    raw = os.getenv(RUNS_RETENTION_ENV)
    if not raw:
        return DEFAULT_RUNS_RETENTION_DAYS
    try:
        value = int(raw)
    except (TypeError, ValueError):
        LOGGER.warning("%s='%s' invalide, fallback %d", RUNS_RETENTION_ENV, raw, DEFAULT_RUNS_RETENTION_DAYS)
        return DEFAULT_RUNS_RETENTION_DAYS
    return max(value, 1)


def rotate_pipeline_artifacts(retention_days: int | None = None) -> dict[str, int]:
    """Purge les runs plus vieux que ``retention_days`` jours.

    Retourne ``{"removed_runs": N, "removed_dirs": M, "retention_days": D}``.
    Idempotent : peut être appelé plusieurs fois sans effet de bord.
    """
    days = retention_days if retention_days is not None else _retention_days()
    cutoff = datetime.now() - timedelta(days=days)
    removed_runs = 0
    removed_dirs = 0

    # 1) Purge l'index : on conserve uniquement les runs plus récents.
    with _REGISTRY_LOCK:
        index = _read_history_index()
        keep: dict[str, dict[str, object]] = {}
        for run_id, payload in index.items():
            ts_str = str(payload.get("finished_at") or payload.get("executed_at") or "")
            try:
                ts = datetime.fromisoformat(ts_str) if ts_str else None
            except ValueError:
                ts = None
            if ts is None or ts >= cutoff:
                keep[run_id] = payload
            else:
                removed_runs += 1
        if removed_runs:
            _write_history_index(keep)

    # 2) Purge les répertoires orphelins/anciens dans artifacts/ihm_pipeline_runs/<step>/<run_id>/.
    if RUNS_DIR.exists():
        for step_dir in RUNS_DIR.iterdir():
            if not step_dir.is_dir():
                continue
            for run_dir in step_dir.iterdir():
                if not run_dir.is_dir():
                    continue
                try:
                    mtime = datetime.fromtimestamp(run_dir.stat().st_mtime)
                except OSError:
                    continue
                if mtime < cutoff:
                    try:
                        shutil.rmtree(run_dir, ignore_errors=True)
                        removed_dirs += 1
                    except OSError:
                        LOGGER.exception("rotate_pipeline_artifacts: échec suppression %s", run_dir)

    if removed_runs or removed_dirs:
        LOGGER.info(
            "rotate_pipeline_artifacts | retention_days=%d removed_runs=%d removed_dirs=%d",
            days, removed_runs, removed_dirs,
        )
    return {"removed_runs": removed_runs, "removed_dirs": removed_dirs, "retention_days": days}


def _atexit_kill_all_children() -> None:
    """Hook ``atexit`` : tue les sous-processus encore actifs (Phase 6.2)."""
    try:
        with _REGISTRY_LOCK:
            active = list(_ACTIVE_RUNS.values())
            workflows = list(_ACTIVE_WORKFLOWS.values())
        for managed in active:
            try:
                _kill_process_tree(managed.process)
            except Exception:
                LOGGER.debug("atexit: échec kill run %s", managed.record.run_id, exc_info=True)
        for wf in workflows:
            try:
                wf.stop_event.set()
            except Exception:
                pass
    except Exception:
        # ne JAMAIS lever depuis atexit
        LOGGER.debug("atexit_kill_all_children: erreur ignorée", exc_info=True)


# Activation du hook atexit + rotation au premier import (idempotent grâce aux flags).
_ATEXIT_REGISTERED = False
_ROTATION_RAN = False


def _ensure_lifecycle_hooks() -> None:
    global _ATEXIT_REGISTERED, _ROTATION_RAN
    if not _ATEXIT_REGISTERED:
        atexit.register(_atexit_kill_all_children)
        _ATEXIT_REGISTERED = True
    if not _ROTATION_RAN:
        try:
            rotate_pipeline_artifacts()
        except Exception:
            LOGGER.debug("rotate_pipeline_artifacts initial: erreur ignorée", exc_info=True)
        _ROTATION_RAN = True


_ensure_lifecycle_hooks()


