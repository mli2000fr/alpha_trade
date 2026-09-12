"""Catalogue et pilotage des batchs planifiés depuis l'IHM.

Le module reste indépendant de Streamlit. Les commandes sont toujours des
listes d'arguments (jamais ``shell=True``) et les collectes longues passent par
le registre asynchrone de l'IHM.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from common.config_loader import load_batch_config
from ihm.services.pipeline_runner import PROJECT_ROOT
from ihm.services.process_registry import (
    PipelineRunRecord,
    list_active_pipeline_runs,
    start_managed_run,
)

WINDOWS_SCRIPTS = PROJECT_ROOT / "scripts" / "windows"
OLD_BATCHES = {
    "market_cap_sync": ("AlphaTrade-MarketCapSync", "install_market_cap_sync_task.ps1", "market_cap_sync_launcher.ps1"),
    "earnings_calendar_sync": ("AlphaTrade-EarningsCalendarSync", "install_earnings_calendar_task.ps1", "earnings_calendar_launcher.ps1"),
    "analyst_snapshot_collection": ("AlphaTrade-AnalystSnapshot", "install_analyst_snapshot_task.ps1", "analyst_snapshot_launcher.ps1"),
}
PENDING_STATUSES = {"PENDING_PROVIDER", "PENDING_QUOTA_DECISION", "ENABLE_AFTER_ORACLE_LIVE_SELECTION"}
DAY_LABELS = {
    "0": "dim", "1": "lun", "2": "mar", "3": "mer",
    "4": "jeu", "5": "ven", "6": "sam",
}


@dataclass(frozen=True, slots=True)
class BatchSpec:
    name: str
    priority: str
    description: str
    tables: tuple[str, ...]
    enabled: bool
    status: str
    provider: str
    timezone: str
    run_hours: tuple[str, ...]
    run_minutes: tuple[str, ...]
    run_days: tuple[str, ...]
    symbols_file: str
    log_file: str
    task_name: str
    raw_config: Mapping[str, Any]

    @property
    def runnable(self) -> bool:
        return self.enabled and self.status not in PENDING_STATUSES


@dataclass(frozen=True, slots=True)
class CommandResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str


def _split(value: Any) -> tuple[str, ...]:
    return tuple(part.strip() for part in str(value or "").split(",") if part.strip())


def _default_task_name(batch_name: str) -> str:
    suffix = "".join(part[:1].upper() + part[1:] for part in batch_name.split("_") if part)
    return f"AlphaTrade-{suffix}"


def task_name_for_batch(batch_name: str) -> str:
    legacy = OLD_BATCHES.get(batch_name)
    return legacy[0] if legacy else _default_task_name(batch_name)


def load_batch_specs(path: str | None = None) -> tuple[BatchSpec, ...]:
    config = load_batch_config(path)
    specs: list[BatchSpec] = []
    for name, raw in config.items():
        if not isinstance(raw, dict):
            continue
        status = str(raw.get("status") or ("ACTIVE" if raw.get("enabled", True) else "DISABLED"))
        specs.append(BatchSpec(
            name=str(name),
            priority=str(raw.get("priority") or "—"),
            description=str(raw.get("description") or "Description non renseignée dans batch.yaml."),
            tables=_split(raw.get("tables")),
            enabled=bool(raw.get("enabled", True)),
            status=status,
            provider=str(raw.get("provider") or raw.get("providers") or "interne"),
            timezone=str(raw.get("timezone") or "heure locale Windows"),
            run_hours=_split(raw.get("run_hours")),
            run_minutes=_split(raw.get("run_minutes")),
            run_days=_split(raw.get("run_days")),
            symbols_file=str(raw.get("symbols_file") or ""),
            log_file=str(raw.get("log_file") or f"log/batch/{name}.txt"),
            task_name=task_name_for_batch(str(name)),
            raw_config=dict(raw),
        ))
    order = {f"P{i}": i for i in range(5)}
    return tuple(sorted(specs, key=lambda item: (order.get(item.priority, 99), item.name)))


def format_schedule(spec: BatchSpec) -> str:
    days = ", ".join(DAY_LABELS.get(day, day) for day in spec.run_days) or "tous les jours"
    hours = spec.run_hours or ("—",)
    minutes = spec.run_minutes or ("0",)
    times: list[str] = []
    for index, hour in enumerate(hours):
        minute = minutes[index] if len(minutes) == len(hours) else minutes[0]
        times.append(f"{int(hour):02d}:{int(minute):02d}" if hour.isdigit() and minute.isdigit() else f"{hour}:{minute}")
    return f"{days} · {', '.join(times)} · {spec.timezone}"


def _powershell_prefix() -> list[str]:
    return [shutil.which("powershell.exe") or "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]


def build_install_command(spec: BatchSpec, *, run_as: str = "Interactive") -> list[str]:
    if spec.name in OLD_BATCHES:
        script = OLD_BATCHES[spec.name][1]
        return _powershell_prefix() + [str(WINDOWS_SCRIPTS / script), "-RunAs", run_as]
    return _powershell_prefix() + [
        str(WINDOWS_SCRIPTS / "install_forward_pit_task.ps1"),
        "-BatchName", spec.name, "-TaskName", spec.task_name, "-RunAs", run_as,
    ]


def build_run_command(spec: BatchSpec) -> list[str]:
    if spec.name == "market_cap_sync":
        return _powershell_prefix() + [str(WINDOWS_SCRIPTS / OLD_BATCHES[spec.name][2]), "-IgnoreRunDays"]
    if spec.name == "earnings_calendar_sync":
        return _powershell_prefix() + [str(WINDOWS_SCRIPTS / OLD_BATCHES[spec.name][2]), "-Force"]
    if spec.name == "analyst_snapshot_collection":
        return _powershell_prefix() + [str(WINDOWS_SCRIPTS / OLD_BATCHES[spec.name][2])]
    return _powershell_prefix() + [
        str(WINDOWS_SCRIPTS / "forward_pit_launcher.ps1"),
        "-BatchName", spec.name, "-Force",
    ]


def format_command(command: list[str]) -> str:
    return subprocess.list2cmdline(command)


def install_batch(spec: BatchSpec, *, run_as: str = "Interactive", timeout_seconds: int = 120) -> CommandResult:
    completed = subprocess.run(
        build_install_command(spec, run_as=run_as),
        cwd=str(PROJECT_ROOT), capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout_seconds, check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return CommandResult(completed.returncode == 0, completed.returncode, completed.stdout, completed.stderr)


def start_batch(spec: BatchSpec, *, db_config: dict[str, str | None] | None = None) -> PipelineRunRecord:
    if not spec.runnable:
        raise ValueError(f"Le batch {spec.name} est désactivé ou en attente ({spec.status}).")
    return start_managed_run(
        step_key=f"batch:{spec.name}",
        step_label=f"Batch — {spec.name}",
        command=build_run_command(spec),
        db_config=db_config,
        timeout_seconds=None,
        # Le launcher envoie déjà email + Telegram : pas de second email IHM.
        notify_on_finish=False,
    )


def list_active_batch_runs(batch_name: str | None = None) -> list[dict[str, object]]:
    target = f"batch:{batch_name}" if batch_name else None
    return [
        run for run in list_active_pipeline_runs()
        if (str(run.get("step_key") or "") == target if target else str(run.get("step_key") or "").startswith("batch:"))
    ]


def query_windows_task_states(timeout_seconds: int = 15) -> tuple[dict[str, dict[str, Any]], str | None]:
    if sys.platform != "win32":
        return {}, "Planificateur Windows indisponible sur cette plateforme."
    script = r"""
$rows = @(Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -like 'AlphaTrade-*' } | ForEach-Object {
  $task = $_
  $info = Get-ScheduledTaskInfo -TaskName $task.TaskName -ErrorAction SilentlyContinue
  [PSCustomObject]@{
    task_name = $task.TaskName
    state = [string]$task.State
    enabled = ([string]$task.State -ne 'Disabled')
    last_run_time = if ($info -and $info.LastRunTime.Year -gt 1900) { $info.LastRunTime.ToString('o') } else { $null }
    next_run_time = if ($info -and $info.NextRunTime.Year -gt 1900) { $info.NextRunTime.ToString('o') } else { $null }
    last_result = if ($info) { [int64]$info.LastTaskResult } else { $null }
  }
})
$rows | ConvertTo-Json -Depth 3 -Compress
"""
    try:
        completed = subprocess.run(
            [shutil.which("powershell.exe") or "powershell.exe", "-NoProfile", "-Command", script],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout_seconds, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {}, str(exc)
    if completed.returncode != 0:
        return {}, (completed.stderr or completed.stdout or f"PowerShell rc={completed.returncode}").strip()
    raw = completed.stdout.strip()
    if not raw:
        return {}, None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {}, f"Réponse Task Scheduler illisible : {exc}"
    rows = payload if isinstance(payload, list) else [payload]
    return {str(row["task_name"]): dict(row) for row in rows if isinstance(row, dict) and row.get("task_name")}, None


def read_batch_log_tail(spec: BatchSpec, max_lines: int = 80) -> str:
    path = Path(spec.log_file)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-max_lines:])


__all__ = [
    "BatchSpec", "CommandResult", "build_install_command", "build_run_command",
    "format_command", "format_schedule", "install_batch", "list_active_batch_runs",
    "load_batch_specs", "query_windows_task_states", "read_batch_log_tail",
    "start_batch", "task_name_for_batch",
]
