"""Agrégations métier pour l'écran IHM de supervision ops."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping

import pandas as pd

from ihm.components.status_badges import classify_heartbeat_freshness, heartbeat_badge, run_status_badge
from ihm.services.process_registry import list_active_pipeline_runs
from ihm.services.queries import get_ops_latest_critical_summaries, get_ops_service_summaries
from ihm.services.run_summary import build_run_summary_caption, get_run_summary

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
                "status": str(record.get("status", "") or ""),
                "status_badge": run_status_badge(record.get("status")),
                "account_id": str(record.get("account_id", "") or ""),
                "executed_at": str(record.get("executed_at", "") or ""),
                "duration_seconds": float(record.get("duration_seconds", 0.0) or 0.0),
                "is_active": bool(record.get("is_active", False)),
            }
        )
    return pd.DataFrame(rows)


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


def build_ops_supervision_snapshot(
    *,
    account_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    service_records = get_ops_service_summaries(account_id=account_id, limit=20)
    latest_run_records = get_ops_latest_critical_summaries(account_id=account_id, limit=50)
    active_runs = list_active_pipeline_runs()

    service_health_df = build_service_health_dataframe(service_records, now=now)
    latest_runs_df = build_latest_runs_dataframe(latest_run_records)
    active_runs_df = build_active_runs_dataframe(active_runs, account_id=account_id)
    alerts = build_ops_alerts(service_health_df, latest_runs_df, active_runs_df)

    metrics = {
        "services_monitored": int(len(service_health_df.index)),
        "services_stale": int((service_health_df.get("heartbeat_level") == "error").sum()) if not service_health_df.empty else 0,
        "services_warn": int((service_health_df.get("heartbeat_level") == "warn").sum()) if not service_health_df.empty else 0,
        "critical_alerts": sum(1 for alert in alerts if alert["severity"] == "error"),
        "active_runs": int(len(active_runs_df.index)),
    }

    return {
        "metrics": metrics,
        "alerts": alerts,
        "service_health": service_health_df,
        "latest_runs": latest_runs_df,
        "active_runs": active_runs_df,
    }

