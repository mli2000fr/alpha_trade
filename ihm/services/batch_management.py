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
    "earnings_calendar_sync": ("AlphaTrade-EarningsCalendarSync", "install_earnings_calendar_task.ps1", "earnings_calendar_launcher.ps1"),
    "analyst_snapshot_collection": ("AlphaTrade-AnalystSnapshot", "install_analyst_snapshot_task.ps1", "analyst_snapshot_launcher.ps1"),
}
CN_DRAGON_BATCHES = {"cn_dragon_tiger_after_close", "cn_dragon_tiger_before_open"}
CN_DRAGON_MATCH_BATCHES = {"cn_dragon_tiger_daily_match"}
CN_ORACLE_BATCHES = {"cn_oracle_prospective_daily"}
CN_BACKUP_BATCHES = {"cn_db_backup"}
CN_QUALITY_BATCHES = {"cn_daily_quality_17c"}
CN_OPERATIONAL_BATCHES = CN_BACKUP_BATCHES | CN_QUALITY_BATCHES
CN_RESEARCH_BATCHES = CN_DRAGON_BATCHES | CN_DRAGON_MATCH_BATCHES | CN_ORACLE_BATCHES | CN_OPERATIONAL_BATCHES
PENDING_STATUSES = {
    "PENDING_QUALIFICATION",
    "PENDING_RESTORE_PROOF",
    "PENDING_PROVIDER",
    "PENDING_QUOTA_DECISION",
    "PENDING_FULL_UNIVERSE_CAPACITY",
    "ENABLE_AFTER_ORACLE_LIVE_SELECTION",
    "BLOCKED_FREE_NO_NBBO_SOURCE",
    "BLOCKED_NO_FREE_OFFICIAL_FEED",
}
DAY_LABELS = {
    "0": "dim", "1": "lun", "2": "mar", "3": "mer",
    "4": "jeu", "5": "ven", "6": "sam",
}


@dataclass(frozen=True, slots=True)
class BatchSpec:
    name: str
    priority: str
    description: str
    activation_requirement: str
    unlock_steps: tuple[str, ...]
    tables: tuple[str, ...]
    enabled: bool
    status: str
    provider: str
    timezone: str
    run_hours: tuple[str, ...]
    run_minutes: tuple[str, ...]
    run_days: tuple[str, ...]
    symbols_file: str
    universe_scope: str
    log_file: str
    task_name: str
    raw_config: Mapping[str, Any]
    research_notice: str = ""
    supervision_dependencies: tuple[str, ...] = ()
    execution_notice: str = ""
    catalog_path: str = "batch.yaml"

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


def _string_list(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    text_value = str(value or "").strip()
    return (text_value,) if text_value else ()


def _default_task_name(batch_name: str) -> str:
    suffix = "".join(part[:1].upper() + part[1:] for part in batch_name.split("_") if part)
    return f"AlphaTrade-{suffix}"


def _normalize_windows_task_time(value: Any) -> str | None:
    """Reject Task Scheduler's pre-2000 sentinel used for 'never run'."""
    text_value = str(value or "").strip()
    if not text_value:
        return None
    try:
        year = int(text_value[:4])
    except (TypeError, ValueError):
        return None
    return text_value if year >= 2000 else None


def task_name_for_batch(batch_name: str) -> str:
    legacy = OLD_BATCHES.get(batch_name)
    return legacy[0] if legacy else _default_task_name(batch_name)


def load_batch_specs(path: str | None = None) -> tuple[BatchSpec, ...]:
    config = load_batch_config(path)
    if path and Path(path).name == 'batch_cn.yaml':
        defaults = config.get('defaults') or {}
        config = {name: {**defaults, **section} for name, section in config.items()
                  if name not in ('defaults','schema_version') and isinstance(section,dict)}
        if any(not n.startswith('cn_') or r.get('market_code')!='CN_A' or r.get('database_alias')!='cn_primary'
               for n,r in config.items()):
            raise ValueError('Catalogue CN incompatible')
    if path and Path(path).name == "batch_fr.yaml":
        defaults = config.get("defaults") or {}
        config = {name: {**defaults, **section} for name, section in config.items()
                  if name not in ("defaults", "schema_version") and isinstance(section, dict)}
        for name, section in config.items():
            if not name.startswith("fr_") or section.get("market_code") != "FR_EQ" or section.get("database_alias") != "fr_primary":
                raise ValueError(f"Catalogue FR incompatible : {name}")
        for sibling in ("batch.yaml", "batch_cn.yaml"):
            other_path = Path(path).resolve().parent / sibling
            if other_path.exists():
                duplicates = set(config) & set(load_batch_config(str(other_path)))
                if duplicates:
                    raise ValueError(f"Doublons de catalogue FR / {sibling} : {sorted(duplicates)}")
    catalog_paths = {name: str(Path(path).resolve()) if path else str(PROJECT_ROOT / "batch.yaml")
                     for name in config}
    if path is None:
        # Add only CN jobs supported by this page. Until the controlled cutover,
        # the four research sections remain in batch.yaml; duplicates fail closed.
        cn_config = load_batch_config(str(PROJECT_ROOT / "batch_cn.yaml"))
        for name in CN_RESEARCH_BATCHES & set(cn_config):
            if name in config:
                raise ValueError(f"Duplicate {name} in batch.yaml and batch_cn.yaml")
            config[name] = cn_config[name]
            catalog_paths[name] = str(PROJECT_ROOT / "batch_cn.yaml")
    specs: list[BatchSpec] = []
    for name, raw in config.items():
        if not isinstance(raw, dict):
            continue
        status = str(raw.get("status") or ("ACTIVE" if raw.get("enabled", True) else "DISABLED"))
        specs.append(BatchSpec(
            name=str(name),
            priority=str(raw.get("priority") or "—"),
            description=str(raw.get("description") or "Description non renseignée dans batch.yaml."),
            activation_requirement=str(raw.get("activation_requirement") or ""),
            unlock_steps=_string_list(raw.get("unlock_steps")),
            tables=_split(raw.get("tables")),
            enabled=bool(raw.get("enabled", True)),
            status=status,
            provider=str(raw.get("provider") or raw.get("providers") or "interne"),
            timezone=str(raw.get("timezone") or "heure locale Windows"),
            run_hours=_split(raw.get("run_hours")),
            run_minutes=_split(raw.get("run_minutes")),
            run_days=_split(raw.get("run_days")),
            symbols_file=str(raw.get("symbols_file") or ""),
            universe_scope=str(raw.get("universe_scope") or ""),
            log_file=str(raw.get("log_file") or f"log/batch/{name}.txt"),
            task_name=task_name_for_batch(str(name)),
            raw_config=dict(raw),
            research_notice=str(raw.get("research_notice") or ""),
            supervision_dependencies=_split(raw.get("supervision_dependencies")),
            execution_notice=str(raw.get("execution_notice") or ""),
            catalog_path=catalog_paths[name],
        ))
    order = {f"P{i}": i for i in range(5)}
    return tuple(sorted(specs, key=lambda item: (order.get(item.priority, 99), item.name)))


def load_market_batch_specs(market: str) -> tuple[BatchSpec, ...]:
    """UI market boundary; retain legacy CN sections in their original catalogue."""
    from dataclasses import replace
    if market == 'FR_EQ':
        return load_batch_specs(str(PROJECT_ROOT/'batch_fr.yaml'))
    if market not in ('US_EQ','CN_A'):
        raise ValueError('Périmètre batch inconnu')
    legacy = load_batch_specs(str(PROJECT_ROOT/'batch.yaml'))
    if market == 'US_EQ':
        return tuple(s for s in legacy if not s.name.startswith(('cn_','fr_'))
                     and s.raw_config.get('market_code', 'US_EQ') == 'US_EQ')
    specs = {s.name:s for s in legacy if s.name.startswith('cn_')}
    for spec in load_batch_specs(str(PROJECT_ROOT/'batch_cn.yaml')):
        if spec.name in specs:
            raise ValueError(f'Duplicate {spec.name} in batch.yaml and batch_cn.yaml')
        specs[spec.name]=spec
    for name,spec in list(specs.items()):
        if name not in CN_RESEARCH_BATCHES:
            dormant_status = spec.status if spec.status.startswith(('DISABLED_', 'SUPERSEDED_')) else 'PENDING_QUALIFICATION'
            specs[name] = replace(spec,enabled=False,status=dormant_status,
                activation_requirement=spec.activation_requirement or
                'Famille CN déclarée, sans launcher quotidien raccordé à cette page ; aucun fallback US autorisé.')
    return tuple(sorted(specs.values(),key=lambda s:(s.priority,s.name)))


def supports_batch_execution(spec: BatchSpec) -> bool:
    return not spec.name.startswith('cn_') or spec.name in CN_RESEARCH_BATCHES


def read_fr_inpi_mapping(spec: BatchSpec) -> dict | None:
    if spec.name!='fr_fundamentals_sync': return None
    path=(PROJECT_ROOT/str(spec.raw_config.get('mapping_report_file',''))).resolve()
    expected=(PROJECT_ROOT/'artifacts/fr/operations/fr_fundamentals_sync/mapping/mapping_report.json').resolve()
    if path!=expected: raise ValueError('Rapport mapping INPI hors périmètre FR')
    if not path.exists(): return None
    if path.stat().st_size>4*1024*1024: raise ValueError('Rapport mapping INPI trop volumineux')
    report=json.loads(path.read_text(encoding='utf-8'))
    state_path=path.parent.parent/'collection_state.json'
    if state_path.exists() and state_path.stat().st_size<=8*1024*1024:
        state=json.loads(state_path.read_text(encoding='utf-8'))
        entries=state.get('issuers',{})
        eligible={r['isin']+'-'+r['siren'] for r in report['rows'] if r['status']=='VERIFIED'}
        report['collection_completed_issuers']=sum(bool(e.get('completed_at')) for k,e in entries.items() if k in eligible)
        report['document_exclusions']=[{'ISIN/SIREN':key,'Compte':d.get('id'),'Motif':d.get('reason')}
            for key,entry in entries.items() for d in entry.get('skipped_documents',[])]
    return report


def format_schedule(spec: BatchSpec) -> str:
    days = ", ".join(DAY_LABELS.get(day, day) for day in spec.run_days) or "tous les jours"
    hours = spec.run_hours or ("—",)
    minutes = spec.run_minutes or ("0",)
    times: list[str] = []
    for index, hour in enumerate(hours):
        minute = minutes[index] if len(minutes) == len(hours) else minutes[0]
        times.append(f"{int(hour):02d}:{int(minute):02d}" if hour.isdigit() and minute.isdigit() else f"{hour}:{minute}")
    schedule = f"{days} · {', '.join(times)} · {spec.timezone}"
    if bool(spec.raw_config.get("first_weekday_of_month", False)):
        schedule = f"premier {days} du mois · {', '.join(times)} · {spec.timezone}"
    recovery_hours = _split(spec.raw_config.get("recovery_run_hours"))
    if recovery_hours:
        recovery_minutes = _split(spec.raw_config.get("recovery_run_minutes")) or ("0",)
        recovery_times: list[str] = []
        for index, hour in enumerate(recovery_hours):
            minute = recovery_minutes[index] if len(recovery_minutes) == len(recovery_hours) else recovery_minutes[0]
            recovery_times.append(
                f"{int(hour):02d}:{int(minute):02d}"
                if hour.isdigit() and minute.isdigit()
                else f"{hour}:{minute}"
            )
        schedule += f" · secours conditionnel {', '.join(recovery_times)}"
    return schedule


def format_data_coverage(spec: BatchSpec) -> str:
    """Décrit la reprise réellement garantie, sans extrapoler le fournisseur."""
    explicit = str(spec.raw_config.get("coverage_description") or "").strip()
    if explicit:
        return explicit
    recovery_hours = _split(spec.raw_config.get("recovery_run_hours"))
    if recovery_hours:
        recovery_minutes = _split(spec.raw_config.get("recovery_run_minutes")) or ("0",)
        times: list[str] = []
        for index, hour in enumerate(recovery_hours):
            minute = recovery_minutes[index] if len(recovery_minutes) == len(recovery_hours) else recovery_minutes[0]
            times.append(
                f"{int(hour):02d}:{int(minute):02d}"
                if hour.isdigit() and minute.isdigit()
                else f"{hour}:{minute}"
            )
        return (
            "Snapshot J non reconstructible · second passage conditionnel disponible à "
            f"{', '.join(times)} ({spec.timezone})"
        )

    lookback = spec.raw_config.get("lookback_days")
    if lookback is None:
        lookback = spec.raw_config.get("observation_lookback_days")
    if lookback is not None:
        forward = spec.raw_config.get("forward_days")
        end = f"J+{int(forward)}" if forward is not None and int(forward) > 0 else "J"
        return f"Fenêtre rejouée : J−{int(lookback)} à {end}"

    if not spec.enabled:
        return "Aucune collecte planifiée tant que le batch reste désactivé"
    if spec.name == "pit_data_quality_daily":
        return "Contrôle ponctuel à J · aucune nouvelle donnée collectée"
    if spec.universe_scope == "raw_sec_filings":
        return "Reprise du backlog RAW complet non encore normalisé"
    return "Snapshot J uniquement · aucun rattrapage historique automatique"


def _powershell_prefix() -> list[str]:
    return [shutil.which("powershell.exe") or "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]


def build_install_command(spec: BatchSpec, *, run_as: str = "Interactive") -> list[str]:
    if not supports_batch_execution(spec):
        raise ValueError('Launcher CN non raccordé ; installation US interdite')
    if Path(spec.catalog_path).name == "batch_fr.yaml":
        return _powershell_prefix() + [str(WINDOWS_SCRIPTS / "install_forward_pit_task.ps1"),
            "-BatchName", spec.name, "-TaskName", spec.task_name, "-RunAs", run_as,
            "-BatchConfigPath", spec.catalog_path,
            "-LauncherPath", str(WINDOWS_SCRIPTS / "fr_operational_launcher_15a.ps1")]
    cn_catalog = Path(spec.catalog_path).name == "batch_cn.yaml"
    if spec.name in OLD_BATCHES:
        script = OLD_BATCHES[spec.name][1]
        return _powershell_prefix() + [str(WINDOWS_SCRIPTS / script), "-RunAs", run_as]
    if spec.name in CN_DRAGON_BATCHES:
        command = _powershell_prefix() + [
            str(WINDOWS_SCRIPTS / "install_forward_pit_task.ps1"),
            "-BatchName", spec.name, "-TaskName", spec.task_name, "-RunAs", run_as,
            "-LauncherPath", str(WINDOWS_SCRIPTS / "cn_dragon_tiger_launcher_15d6.ps1"),
        ]
        return command + (["-BatchConfigPath", spec.catalog_path] if cn_catalog else [])
    if spec.name in CN_ORACLE_BATCHES:
        command = _powershell_prefix() + [
            str(WINDOWS_SCRIPTS / "install_forward_pit_task.ps1"),
            "-BatchName", spec.name, "-TaskName", spec.task_name, "-RunAs", run_as,
            "-LauncherPath", str(WINDOWS_SCRIPTS / "cn_oracle_daily_launcher_15d9.ps1"),
        ]
        return command + (["-BatchConfigPath", spec.catalog_path] if cn_catalog else [])
    if spec.name in CN_DRAGON_MATCH_BATCHES:
        command = _powershell_prefix() + [
            str(WINDOWS_SCRIPTS / "install_forward_pit_task.ps1"),
            "-BatchName", spec.name, "-TaskName", spec.task_name, "-RunAs", run_as,
            "-LauncherPath", str(WINDOWS_SCRIPTS / "cn_dragon_tiger_daily_launcher_15d10.ps1"),
        ]
        return command + (["-BatchConfigPath", spec.catalog_path] if cn_catalog else [])
    if spec.name in CN_BACKUP_BATCHES:
        return _powershell_prefix() + [
            str(WINDOWS_SCRIPTS / "install_forward_pit_task.ps1"),
            "-BatchName", spec.name, "-TaskName", spec.task_name, "-RunAs", run_as,
            "-BatchConfigPath", str(PROJECT_ROOT / "batch_cn.yaml"),
            "-LauncherPath", str(WINDOWS_SCRIPTS / "cn_db_backup_launcher_17b.ps1"),
        ]
    if spec.name in CN_QUALITY_BATCHES:
        return _powershell_prefix() + [
            str(WINDOWS_SCRIPTS / "install_forward_pit_task.ps1"),
            "-BatchName", spec.name, "-TaskName", spec.task_name, "-RunAs", run_as,
            "-BatchConfigPath", str(PROJECT_ROOT / "batch_cn.yaml"),
            "-LauncherPath", str(WINDOWS_SCRIPTS / "cn_daily_quality_launcher_17c.ps1"),
        ]
    return _powershell_prefix() + [
        str(WINDOWS_SCRIPTS / "install_forward_pit_task.ps1"),
        "-BatchName", spec.name, "-TaskName", spec.task_name, "-RunAs", run_as,
    ]


def build_run_command(spec: BatchSpec) -> list[str]:
    if not supports_batch_execution(spec):
        raise ValueError('Launcher CN non raccordé ; exécution US interdite')
    if Path(spec.catalog_path).name == "batch_fr.yaml":
        return _powershell_prefix() + [str(WINDOWS_SCRIPTS / "fr_operational_launcher_15a.ps1"),
            "-BatchName", spec.name, "-BatchConfigPath", spec.catalog_path, "-Force"]
    cn_config_arg = (["-BatchConfigPath", spec.catalog_path]
                     if Path(spec.catalog_path).name == "batch_cn.yaml" else [])
    if spec.name in CN_DRAGON_BATCHES:
        return _powershell_prefix() + [
            str(WINDOWS_SCRIPTS / "cn_dragon_tiger_launcher_15d6.ps1"),
            "-BatchName", spec.name, *cn_config_arg, "-Force",
        ]
    if spec.name in CN_ORACLE_BATCHES:
        return _powershell_prefix() + [
            str(WINDOWS_SCRIPTS / "cn_oracle_daily_launcher_15d9.ps1"),
            "-BatchName", spec.name, *cn_config_arg, "-Force",
        ]
    if spec.name in CN_DRAGON_MATCH_BATCHES:
        return _powershell_prefix() + [
            str(WINDOWS_SCRIPTS / "cn_dragon_tiger_daily_launcher_15d10.ps1"),
            "-BatchName", spec.name, *cn_config_arg, "-Force",
        ]
    if spec.name in CN_BACKUP_BATCHES:
        return _powershell_prefix() + [
            str(WINDOWS_SCRIPTS / "cn_db_backup_launcher_17b.ps1"),
            "-BatchName", spec.name, "-Force",
        ]
    if spec.name in CN_QUALITY_BATCHES:
        return _powershell_prefix() + [
            str(WINDOWS_SCRIPTS / "cn_daily_quality_launcher_17c.ps1"),
            "-BatchName", spec.name, "-Force",
        ]
    if spec.name == "earnings_calendar_sync":
        return _powershell_prefix() + [str(WINDOWS_SCRIPTS / OLD_BATCHES[spec.name][2]), "-Force"]
    if spec.name == "analyst_snapshot_collection":
        return _powershell_prefix() + [str(WINDOWS_SCRIPTS / OLD_BATCHES[spec.name][2]), "-Force"]
    return _powershell_prefix() + [
        str(WINDOWS_SCRIPTS / "forward_pit_launcher.ps1"),
        "-BatchName", spec.name, "-Force",
    ]


def build_uninstall_command(spec: BatchSpec) -> list[str]:
    return _powershell_prefix() + [
        str(WINDOWS_SCRIPTS / "uninstall_scheduled_batch_task.ps1"),
        "-TaskName", spec.task_name,
    ]


def format_command(command: list[str]) -> str:
    return subprocess.list2cmdline(command)


def install_batch(spec: BatchSpec, *, run_as: str = "Interactive", timeout_seconds: int = 120) -> CommandResult:
    if Path(spec.catalog_path).name == "batch_fr.yaml" and not spec.runnable:
        return CommandResult(False, -1, "", "Batch FR désactivé ou non qualifié : aucune tâche modifiée.")
    completed = subprocess.run(
        build_install_command(spec, run_as=run_as),
        cwd=str(PROJECT_ROOT), capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout_seconds, check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return CommandResult(completed.returncode == 0, completed.returncode, completed.stdout, completed.stderr)


def uninstall_batch(spec: BatchSpec, *, timeout_seconds: int = 60) -> CommandResult:
    completed = subprocess.run(
        build_uninstall_command(spec),
        cwd=str(PROJECT_ROOT), capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout_seconds, check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return CommandResult(completed.returncode == 0, completed.returncode, completed.stdout, completed.stderr)


def _failed_command_result(exc: Exception) -> CommandResult:
    return CommandResult(False, -1, "", str(exc))


def install_all_batches(
    specs: tuple[BatchSpec, ...] | list[BatchSpec],
    *,
    run_as: str = "Interactive",
) -> dict[str, CommandResult]:
    """Installe uniquement les batchs explicitement actifs dans batch.yaml.

    Le filtrage est volontairement répété ici, même si l'IHM filtre déjà sa
    sélection, afin qu'un autre appelant ne puisse pas réinstaller par erreur
    une tâche dont ``enabled`` vaut ``false``.
    """
    results: dict[str, CommandResult] = {}
    for spec in specs:
        if not spec.enabled:
            continue
        try:
            results[spec.name] = install_batch(spec, run_as=run_as)
        except Exception as exc:
            results[spec.name] = _failed_command_result(exc)
    return results


def uninstall_all_batches(
    specs: tuple[BatchSpec, ...] | list[BatchSpec],
) -> dict[str, CommandResult]:
    results: dict[str, CommandResult] = {}
    for spec in specs:
        try:
            results[spec.name] = uninstall_batch(spec)
        except Exception as exc:
            results[spec.name] = _failed_command_result(exc)
    return results


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
    last_run_time = if ($info -and $info.LastRunTime.Year -ge 2000) { $info.LastRunTime.ToString('o') } else { $null }
    next_run_time = if ($info -and $info.NextRunTime.Year -ge 2000) { $info.NextRunTime.ToString('o') } else { $null }
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
    normalized: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not row.get("task_name"):
            continue
        item = dict(row)
        item["last_run_time"] = _normalize_windows_task_time(item.get("last_run_time"))
        item["next_run_time"] = _normalize_windows_task_time(item.get("next_run_time"))
        normalized[str(item["task_name"])] = item
    return normalized, None


def read_batch_log_tail(spec: BatchSpec, max_lines: int = 80) -> str:
    path = Path(spec.log_file)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-max_lines:])


def latest_cn_dragon_research_run(spec: BatchSpec) -> dict[str, Any] | None:
    """Read CN research status from its file ledger, never the US PIT table."""
    if spec.name not in CN_RESEARCH_BATCHES:
        return None
    root = Path(str(spec.raw_config.get("output_root") or ""))
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    for path in sorted((root / "runs").glob("run-*.json"), reverse=True):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if report.get("batch") != spec.name:
            continue
        status = str(report.get("status") or "UNKNOWN")
        return {
            "batch_name": spec.name, "provider": spec.provider,
            "status": ("COMPLETED" if status == "COMPLETED_RESEARCH_ONLY"
                       else "FAILED" if status.startswith("FAILED") else status),
            "started_at": report.get("started_at_utc"),
            "finished_at": report.get("finished_at_utc"),
            "requested_count": report.get("requested_count"),
            "received_count": report.get("received_count"),
            "persisted_count": report.get("persisted_count"),
            "failed_count": report.get("failed_count"),
            "warning_count": report.get("warning_count"),
            "error_message": report.get("error_message"),
        }
    return None


def read_cn_daily_quality_history(spec: BatchSpec, *, limit: int = 7) -> tuple[dict[str, Any], ...]:
    """Read the newest distinct CN sessions; no database or scheduler mutation."""
    if spec.name != "cn_daily_quality_17c" or limit < 1:
        return ()
    root = Path(str(spec.raw_config.get("output_root") or ""))
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    rows: list[dict[str, Any]] = []
    seen_sessions: set[str] = set()
    for path in sorted((root / "runs").glob("run-*.json"), reverse=True):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(report, dict) or report.get("batch") != spec.name:
            continue
        session = str(report.get("session") or "")
        if not session or session in seen_sessions:
            continue
        seen_sessions.add(session)
        checks = report.get("checks") or []
        alerts = [str(item.get("name")) for item in checks
                  if isinstance(item, dict) and item.get("status") in {"CRITICAL", "WARNING"}]
        rows.append({
            "session": session, "status": str(report.get("status") or "UNKNOWN"),
            "passed": sum(item.get("status") == "PASS" for item in checks
                          if isinstance(item, dict)),
            "critical": report.get("failed_count"), "warnings": report.get("warning_count"),
            "alerts": ", ".join(alerts), "finished_at": report.get("finished_at_utc"),
            "report_path": str(path),
        })
        if len(rows) >= limit:
            break
    return tuple(rows)


__all__ = [
    "BatchSpec", "CommandResult", "build_install_command", "build_run_command", "build_uninstall_command",
    "format_command", "format_schedule", "install_all_batches", "install_batch", "list_active_batch_runs",
    "read_cn_daily_quality_history",
    "load_batch_specs", "query_windows_task_states", "read_batch_log_tail",
    "latest_cn_dragon_research_run",
    "start_batch", "task_name_for_batch", "uninstall_all_batches", "uninstall_batch",
]
