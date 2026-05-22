"""Agrégations métier pour l'écran IHM de supervision ops."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from ihm.components.status_badges import classify_heartbeat_freshness, heartbeat_badge, run_status_badge
from ihm.services.pipeline_runner import PROJECT_ROOT
from ihm.services.process_registry import list_active_pipeline_runs
from ihm.services.queries import get_ops_latest_critical_summaries, get_ops_service_summaries
from ihm.services.run_summary import build_run_summary_caption, get_run_summary
from ihm.services.windows_watcher_bridge import get_windows_watcher_status, list_windows_watcher_log_sources
from ihm.services.watcher_runtime import WATCHER_ONCE_STEP_KEY, WATCHER_SERVICE_STEP_KEY, build_windows_integration_rows, list_watcher_run_history

SERVICE_LABELS: dict[str, str] = {
    "execution_protection_watch_service": "Watcher protections",
}

CRITICAL_RUN_SCOPES: tuple[tuple[str, str, str | None], ...] = (
    ("Workflow pipeline", "pipeline_workflow", "workflow"),
    ("Risk management", "risk_management", None),
    ("Execution broker", "execution", None),
    ("Watcher protections", "execution_protection_watch", None),
    ("Corporate Actions", "corporate_actions_run", None),
)

_FAILED_STATUSES = {"FAILED", "ERROR", "TIMEOUT", "STOPPED"}
_RUNNING_STATUSES = {"RUNNING", "STARTING"}
_WATCHER_RUN_TYPE_LABELS = {
    WATCHER_ONCE_STEP_KEY: "once",
    WATCHER_SERVICE_STEP_KEY: "service local IHM",
}
COVERAGE_ARTIFACT_PATH = PROJECT_ROOT / "coverage.json"


def _status_upper(value: object) -> str:
    return str(value or "").strip().upper()


def _severity_rank(level: str) -> int:
    return {"error": 0, "warn": 1, "ok": 2, "info": 3}.get(level, 4)


def _iter_records(records: pd.DataFrame | Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    if isinstance(records, pd.DataFrame):
        return [dict(row) for row in records.to_dict(orient="records")]
    return [dict(row) for row in records]


def build_service_health_dataframe(
    records: pd.DataFrame | Iterable[Mapping[str, object]],
    *,
    now: datetime | None = None,
) -> pd.DataFrame:
    latest_by_scope: dict[tuple[str, str], dict[str, object]] = {}
    for record in _iter_records(records):
        step_key = str(record.get("step_key", "") or "")
        summary = get_run_summary(record)
        service_scope = str(summary.get("service_scope", record.get("entity_run_id", "")) or record.get("summary_run_id", "") or "global")
        dedupe_key = (step_key, service_scope)
        if dedupe_key not in latest_by_scope:
            latest_by_scope[dedupe_key] = record

    rows: list[dict[str, object]] = []
    for record in latest_by_scope.values():
        step_key = str(record.get("step_key", "") or "")
        summary = get_run_summary(record)
        status = str(record.get("status", summary.get("status", "UNKNOWN")) or "UNKNOWN")
        last_heartbeat_at = str(summary.get("last_heartbeat_at", "") or "").strip() or None
        interval_seconds = summary.get("heartbeat_interval_seconds")
        heartbeat_level, heartbeat_label, heartbeat_age_seconds = classify_heartbeat_freshness(
            last_heartbeat_at,
            interval_seconds,
            service_status=status,
            now=now,
        )
        rows.append(
            {
                "service": SERVICE_LABELS.get(step_key, step_key or "service"),
                "scope": str(summary.get("service_scope", record.get("entity_run_id", "—")) or "—"),
                "status": status,
                "status_badge": run_status_badge(status),
                "heartbeat": heartbeat_badge(last_heartbeat_at, interval_seconds, service_status=status, now=now),
                "heartbeat_level": heartbeat_level,
                "heartbeat_label": heartbeat_label,
                "heartbeat_age_seconds": heartbeat_age_seconds,
                "last_heartbeat_at": last_heartbeat_at or "—",
                "last_cycle_at": str(summary.get("last_cycle_at", "—") or "—"),
                "last_cycle_watched_items": int(summary.get("last_cycle_watched_items", 0) or 0),
                "last_cycle_transitioned_items": int(summary.get("last_cycle_transitioned_items", 0) or 0),
                "iterations": int(summary.get("iterations", 0) or 0),
                "summary_run_id": str(record.get("summary_run_id", "") or ""),
                "entity_run_id": str(record.get("entity_run_id", "") or ""),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(
        by=["heartbeat_level", "service", "scope"],
        key=lambda col: col.map(_severity_rank) if col.name == "heartbeat_level" else col,
        ascending=[True, True, True],
    ).reset_index(drop=True)


def build_latest_runs_dataframe(records: pd.DataFrame | Iterable[Mapping[str, object]]) -> pd.DataFrame:
    record_list = _iter_records(records)
    rows: list[dict[str, object]] = []
    for scope_label, step_key, run_kind in CRITICAL_RUN_SCOPES:
        matched_record: dict[str, object] | None = None
        for record in record_list:
            if str(record.get("step_key", "") or "") != step_key:
                continue
            if run_kind is not None and str(record.get("run_kind", "") or "") != run_kind:
                continue
            matched_record = record
            break
        if matched_record is None:
            continue
        status = str(matched_record.get("status", "UNKNOWN") or "UNKNOWN")
        rows.append(
            {
                "scope": scope_label,
                "step_key": step_key,
                "status": status,
                "status_badge": run_status_badge(status),
                "run_id": str(
                    matched_record.get("entity_run_id")
                    or matched_record.get("source_run_id")
                    or matched_record.get("summary_run_id")
                    or "—"
                ),
                "trade_date": matched_record.get("trade_date") or "—",
                "summary": build_run_summary_caption(matched_record),
            }
        )
    return pd.DataFrame(rows)


def build_active_runs_dataframe(
    active_runs: Iterable[Mapping[str, object]],
    *,
    account_id: str | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for record in active_runs:
        if account_id and str(record.get("account_id", "") or "") not in {"", account_id}:
            continue
        rows.append(
            {
                "run_id": str(record.get("run_id", "") or ""),
                "step_key": str(record.get("step_key", "") or ""),
                "run_kind": str(record.get("run_kind", "step") or "step"),
                "status": str(record.get("status", "") or ""),
                "status_badge": run_status_badge(record.get("status")),
                "account_id": str(record.get("account_id", "") or ""),
                "parent_run_id": str(record.get("parent_run_id", "") or "") or "—",
                "workflow_correlation_id": str(record.get("workflow_correlation_id", "") or "") or "—",
                "executed_at": str(record.get("executed_at", "") or ""),
                "duration_seconds": float(record.get("duration_seconds", 0.0) or 0.0),
                "is_active": bool(record.get("is_active", False)),
            }
        )
    return pd.DataFrame(rows)


def build_run_lineage_dataframe(active_runs_df: pd.DataFrame) -> pd.DataFrame:
    if active_runs_df.empty:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    for row in active_runs_df.to_dict(orient="records"):
        run_kind = str(row.get("run_kind", "step") or "step")
        parent_run_id = str(row.get("parent_run_id", "—") or "—")
        if run_kind == "workflow":
            lineage_role = "workflow parent"
        elif parent_run_id != "—":
            lineage_role = "child run"
        else:
            lineage_role = "standalone step"
        rows.append(
            {
                "workflow_correlation_id": str(row.get("workflow_correlation_id", "—") or "—"),
                "lineage_role": lineage_role,
                "run_id": str(row.get("run_id", "") or ""),
                "parent_run_id": parent_run_id,
                "step_key": str(row.get("step_key", "") or ""),
                "status_badge": str(row.get("status_badge", "") or ""),
                "account_id": str(row.get("account_id", "") or "") or "global",
            }
        )

    df = pd.DataFrame(rows)
    return df.sort_values(
        by=["workflow_correlation_id", "lineage_role", "run_id"],
        ascending=[True, True, False],
    ).reset_index(drop=True)


def build_coverage_artifact_health(payload: Mapping[str, object] | None) -> dict[str, object]:
    if not payload:
        return {
            "status": "missing",
            "message": "Aucun artefact coverage.json détecté.",
            "files_count": 0,
            "executed_files": 0,
            "num_statements": 0,
            "covered_lines": 0,
            "percent_covered": None,
            "branch_coverage": False,
        }

    meta = payload.get("meta") if isinstance(payload.get("meta"), Mapping) else {}
    totals = payload.get("totals") if isinstance(payload.get("totals"), Mapping) else {}
    files = payload.get("files") if isinstance(payload.get("files"), Mapping) else {}

    if not totals or not files:
        return {
            "status": "invalid",
            "message": "Artefact coverage.json incomplet ou invalide.",
            "files_count": 0,
            "executed_files": 0,
            "num_statements": 0,
            "covered_lines": 0,
            "percent_covered": None,
            "branch_coverage": False,
        }

    files_count = sum(1 for value in files.values() if isinstance(value, Mapping))
    executed_files = sum(
        1
        for value in files.values()
        if isinstance(value, Mapping) and value.get("executed_lines")
    )
    num_statements = int(totals.get("num_statements", 0) or 0)
    covered_lines = int(totals.get("covered_lines", 0) or 0)
    percent_covered = totals.get("percent_covered")
    branch_coverage = bool(meta.get("branch_coverage", False) or "covered_branches" in totals or "num_branches" in totals)

    if files_count <= 0 or executed_files <= 0 or num_statements <= 0:
        status = "incomplete"
        message = "Artefact coverage présent mais partiel : la suite complète n'a probablement pas été exécutée."
    elif not branch_coverage:
        status = "incomplete"
        message = "Artefact coverage sans branch coverage : relancez la suite avec --cov-branch."
    else:
        status = "complete"
        message = "Artefact coverage exploitable pour l'exploitation incident."

    return {
        "status": status,
        "message": message,
        "files_count": files_count,
        "executed_files": executed_files,
        "num_statements": num_statements,
        "covered_lines": covered_lines,
        "percent_covered": percent_covered,
        "branch_coverage": branch_coverage,
    }


def load_coverage_artifact_health(coverage_path: Path | None = None) -> dict[str, object]:
    path = coverage_path or COVERAGE_ARTIFACT_PATH
    if not path.exists():
        payload: Mapping[str, object] | None = None
    else:
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            payload = loaded if isinstance(loaded, Mapping) else None
        except Exception:
            payload = None
    summary = build_coverage_artifact_health(payload)
    summary["path"] = str(path)
    return summary


def build_watcher_history_dataframe(records: Iterable[Mapping[str, object]]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for record in records:
        step_key = str(record.get("step_key", "") or "")
        if step_key not in _WATCHER_RUN_TYPE_LABELS:
            continue
        status = str(record.get("status", "") or "")
        rows.append(
            {
                "run_id": str(record.get("run_id", "") or ""),
                "type": _WATCHER_RUN_TYPE_LABELS.get(step_key, step_key),
                "status": status,
                "status_badge": run_status_badge(status),
                "account_id": str(record.get("account_id", "") or "") or "global",
                "executed_at": str(record.get("executed_at", "") or ""),
                "finished_at": str(record.get("finished_at", "") or "") or "—",
                "duration_seconds": float(record.get("duration_seconds", 0.0) or 0.0),
                "stdout_lines": int(record.get("stdout_lines", 0) or 0),
                "stderr_lines": int(record.get("stderr_lines", 0) or 0),
                "summary": build_run_summary_caption(record),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(by=["executed_at", "run_id"], ascending=[False, False]).reset_index(drop=True)


def build_windows_integration_dataframe(*, account_id: str | None = None) -> pd.DataFrame:
    return pd.DataFrame(build_windows_integration_rows(account_id=account_id))


def build_windows_runtime_dataframe(payload: Mapping[str, object] | None) -> pd.DataFrame:
    if not payload:
        return pd.DataFrame()

    bridge_available = bool(payload.get("bridge_available", False))
    bridge_mode = str(payload.get("bridge_mode", "read_only") or "read_only")
    rows: list[dict[str, object]] = []

    task = payload.get("task")
    if isinstance(task, Mapping):
        rows.append(
            {
                "runtime": "Task Scheduler",
                "name": str(task.get("name", "") or ""),
                "exists": bool(task.get("exists", False)),
                "status": str(task.get("state", "unknown") or "unknown"),
                "enabled": task.get("enabled"),
                "last_run": str(task.get("lastRunTime", "") or "—"),
                "next_run": str(task.get("nextRunTime", "") or "—"),
                "detail": str(task.get("lastTaskResult", "") or "—"),
                "stdout_path": str(task.get("stdoutPath", "") or "—"),
                "stderr_path": str(task.get("stderrPath", "") or "—"),
                "bridge_available": bridge_available,
                "bridge_mode": bridge_mode,
            }
        )

    service = payload.get("service")
    if isinstance(service, Mapping):
        rows.append(
            {
                "runtime": "NSSM / Service Windows",
                "name": str(service.get("name", "") or ""),
                "exists": bool(service.get("exists", False)),
                "status": str(service.get("status", "unknown") or "unknown"),
                "enabled": str(service.get("startType", "") or "—"),
                "last_run": "—",
                "next_run": "—",
                "detail": str(service.get("displayName", "") or service.get("error", "") or "—"),
                "stdout_path": str(service.get("stdoutPath", "") or "—"),
                "stderr_path": str(service.get("stderrPath", "") or "—"),
                "bridge_available": bridge_available,
                "bridge_mode": bridge_mode,
            }
        )

    return pd.DataFrame(rows)


def build_windows_log_sources_dataframe(payload: Mapping[str, object] | None) -> pd.DataFrame:
    rows = list_windows_watcher_log_sources(dict(payload or {}))
    return pd.DataFrame(rows)


def build_windows_bridge_dataframe(payload: Mapping[str, object] | None) -> pd.DataFrame:
    if not payload:
        return pd.DataFrame()

    bridge = payload.get("bridge")
    bridge_payload = dict(bridge) if isinstance(bridge, Mapping) else {}
    allowlist_value = bridge_payload.get("allowlist", [])
    if isinstance(allowlist_value, list):
        allowlist_text = ", ".join(str(item) for item in allowlist_value if item)
    else:
        allowlist_text = str(allowlist_value or "")
    return pd.DataFrame(
        [
            {
                "bridge_available": bool(payload.get("bridge_available", False)),
                "bridge_mode": str(payload.get("bridge_mode", bridge_payload.get("mode", "read_only")) or "read_only"),
                "script_key": str(payload.get("script_key", "status") or "status"),
                "script": str(bridge_payload.get("script", "—") or "—"),
                "allowlist": allowlist_text or "—",
                "reason": str(payload.get("reason", "") or "—"),
            }
        ]
    )


def build_ops_alerts(
    service_health_df: pd.DataFrame,
    latest_runs_df: pd.DataFrame,
    active_runs_df: pd.DataFrame,
) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []

    if service_health_df.empty:
        alerts.append({
            "severity": "warn",
            "message": "Aucun résumé de santé de service disponible pour le watcher protections.",
        })
    else:
        for row in service_health_df.to_dict(orient="records"):
            heartbeat_level = str(row.get("heartbeat_level", "") or "")
            if heartbeat_level == "error":
                alerts.append({
                    "severity": "error",
                    "message": f"Service {row.get('service')} scope={row.get('scope')} en état {row.get('heartbeat_label')}.",
                })
            elif heartbeat_level == "warn":
                alerts.append({
                    "severity": "warn",
                    "message": f"Service {row.get('service')} scope={row.get('scope')} à surveiller (heartbeat).",
                })

    for row in latest_runs_df.to_dict(orient="records"):
        status = _status_upper(row.get("status"))
        if status in _FAILED_STATUSES:
            alerts.append({
                "severity": "error",
                "message": f"Dernier run {row.get('scope')} en échec : {row.get('status_badge')}.",
            })
        elif status in _RUNNING_STATUSES:
            alerts.append({
                "severity": "info",
                "message": f"Run {row.get('scope')} actuellement en cours : {row.get('status_badge')}.",
            })

    if not active_runs_df.empty:
        alerts.append({
            "severity": "info",
            "message": f"{len(active_runs_df)} run(s) IHM encore actif(s).",
        })

    severity_order = {"error": 0, "warn": 1, "info": 2}
    alerts.sort(key=lambda item: severity_order.get(item["severity"], 9))
    return alerts


def build_watcher_control_state(
    service_health_df: pd.DataFrame,
    active_runs_df: pd.DataFrame,
) -> dict[str, object]:
    service_rows = service_health_df.to_dict(orient="records") if not service_health_df.empty else []
    active_rows = active_runs_df.to_dict(orient="records") if not active_runs_df.empty else []

    watcher_rows = [row for row in service_rows if str(row.get("service", "") or "") == "Watcher protections"]
    local_service_run = next(
        (row for row in active_rows if str(row.get("step_key", "") or "") == WATCHER_SERVICE_STEP_KEY and bool(row.get("is_active", False))),
        None,
    )
    local_once_run = next(
        (row for row in active_rows if str(row.get("step_key", "") or "") == WATCHER_ONCE_STEP_KEY and bool(row.get("is_active", False))),
        None,
    )
    fresh_watcher_row = next((row for row in watcher_rows if str(row.get("heartbeat_level", "") or "") == "ok"), None)
    external_fresh_service_detected = fresh_watcher_row is not None and local_service_run is None

    guardrail_messages: list[str] = []
    if external_fresh_service_detected:
        guardrail_messages.append(
            "Un heartbeat watcher frais est déjà détecté sans process local IHM actif : l'IHM suppose qu'un service Windows packagé tourne déjà et bloque par défaut les démarrages locaux."
        )
    if local_once_run is not None:
        guardrail_messages.append(
            f"Un run watcher once local est déjà actif (`{local_once_run.get('run_id', '')}`). Attendez sa fin avant de démarrer ou redémarrer un service local."
        )

    return {
        "local_service_active": local_service_run is not None,
        "local_service_run_id": str((local_service_run or {}).get("run_id", "") or ""),
        "local_once_active": local_once_run is not None,
        "local_once_run_id": str((local_once_run or {}).get("run_id", "") or ""),
        "fresh_service_detected": fresh_watcher_row is not None,
        "external_fresh_service_detected": external_fresh_service_detected,
        "fresh_service_scope": str((fresh_watcher_row or {}).get("scope", "") or ""),
        "guardrail_messages": guardrail_messages,
    }


def build_ops_supervision_snapshot(
    *,
    account_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    service_records = get_ops_service_summaries(account_id=account_id, limit=20)
    latest_run_records = get_ops_latest_critical_summaries(account_id=account_id, limit=50)
    active_runs = list_active_pipeline_runs()
    watcher_history = list_watcher_run_history(account_id=account_id, limit=50)
    windows_status = get_windows_watcher_status()

    service_health_df = build_service_health_dataframe(service_records, now=now)
    latest_runs_df = build_latest_runs_dataframe(latest_run_records)
    active_runs_df = build_active_runs_dataframe(active_runs, account_id=account_id)
    watcher_history_df = build_watcher_history_dataframe(watcher_history)
    watcher_windows_integration_df = build_windows_integration_dataframe(account_id=account_id)
    watcher_windows_runtime_df = build_windows_runtime_dataframe(windows_status)
    watcher_windows_log_sources_df = build_windows_log_sources_dataframe(windows_status)
    watcher_windows_bridge_df = build_windows_bridge_dataframe(windows_status)
    run_lineage_df = build_run_lineage_dataframe(active_runs_df)
    coverage_artifact = load_coverage_artifact_health()
    alerts = build_ops_alerts(service_health_df, latest_runs_df, active_runs_df)
    watcher_control_state = build_watcher_control_state(service_health_df, active_runs_df)

    metrics = {
        "services_monitored": int(len(service_health_df.index)),
        "services_stale": int((service_health_df.get("heartbeat_level") == "error").sum()) if not service_health_df.empty else 0,
        "services_warn": int((service_health_df.get("heartbeat_level") == "warn").sum()) if not service_health_df.empty else 0,
        "critical_alerts": sum(1 for alert in alerts if alert["severity"] == "error"),
        "active_runs": int(len(active_runs_df.index)),
        "watcher_history_runs": int(len(watcher_history_df.index)),
        "windows_log_sources": int(len(watcher_windows_log_sources_df.index)),
        "coverage_complete": int(str(coverage_artifact.get("status") or "") == "complete"),
    }

    return {
        "metrics": metrics,
        "alerts": alerts,
        "service_health": service_health_df,
        "latest_runs": latest_runs_df,
        "active_runs": active_runs_df,
        "run_lineage": run_lineage_df,
        "watcher_control": watcher_control_state,
        "watcher_history": watcher_history_df,
        "watcher_windows_integration": watcher_windows_integration_df,
        "watcher_windows_status": dict(windows_status),
        "watcher_windows_runtime": watcher_windows_runtime_df,
        "watcher_windows_log_sources": watcher_windows_log_sources_df,
        "watcher_windows_bridge": watcher_windows_bridge_df,
        "coverage_artifact": coverage_artifact,
    }

