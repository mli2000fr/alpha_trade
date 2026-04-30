from __future__ import annotations

from datetime import datetime

import pandas as pd

from ihm.services import ops_supervision


def _service_record(
    *,
    status: str = "RUNNING",
    scope: str = "acct-1",
    heartbeat: str = "2026-04-26T10:00:00",
    interval: float = 60.0,
) -> dict[str, object]:
    return {
        "step_key": "execution_protection_watch_service",
        "status": status,
        "summary_run_id": "svc-1",
        "entity_run_id": "watcher-service:acct-1",
        "run_summary": {
            "service_scope": scope,
            "last_heartbeat_at": heartbeat,
            "heartbeat_interval_seconds": interval,
            "last_cycle_at": "2026-04-26T10:00:00",
            "last_cycle_watched_items": 2,
            "last_cycle_transitioned_items": 1,
            "iterations": 5,
        },
    }


def test_build_service_health_dataframe_classifies_heartbeat_status() -> None:
    df = ops_supervision.build_service_health_dataframe(
        [
            _service_record(scope="fresh", heartbeat="2026-04-26T10:02:30"),
            _service_record(scope="stale", heartbeat="2026-04-26T09:55:00"),
        ],
        now=datetime.fromisoformat("2026-04-26T10:03:00"),
    )

    assert list(df["scope"]) == ["stale", "fresh"]
    assert list(df["heartbeat_level"]) == ["error", "ok"]
    assert "Heartbeat STALE" in str(df.iloc[0]["heartbeat"])


def test_build_latest_runs_dataframe_maps_critical_scopes() -> None:
    df = ops_supervision.build_latest_runs_dataframe(
        [
            {
                "step_key": "execution",
                "status": "COMPLETED",
                "entity_run_id": "exec-1",
                "summary_run_id": "sum-1",
                "run_summary": {"submitted_orders": 4, "filled_orders": 4},
            },
            {
                "step_key": "risk_management",
                "status": "FAILED",
                "entity_run_id": "risk-1",
                "summary_run_id": "sum-2",
                "run_summary": {"targeted_symbols": 8},
            },
        ]
    )

    assert list(df["scope"]) == ["Risk management", "Execution broker"]
    assert list(df["run_id"]) == ["risk-1", "exec-1"]
    assert "cibles=8" in str(df.iloc[0]["summary"])


def test_build_ops_alerts_combines_services_runs_and_active_processes() -> None:
    service_df = pd.DataFrame(
        [
            {
                "service": "Watcher protections",
                "scope": "acct-1",
                "heartbeat_level": "error",
                "heartbeat_label": "STALE",
            }
        ]
    )
    latest_runs_df = pd.DataFrame(
        [
            {
                "scope": "Execution broker",
                "status": "FAILED",
                "status_badge": "🔴 FAILED",
            }
        ]
    )
    active_runs_df = pd.DataFrame([{"run_id": "wf-1"}])

    alerts = ops_supervision.build_ops_alerts(service_df, latest_runs_df, active_runs_df)

    assert alerts[0]["severity"] == "error"
    assert "Watcher protections" in alerts[0]["message"]
    assert any("Execution broker" in alert["message"] for alert in alerts)
    assert any(alert["severity"] == "info" for alert in alerts)


def test_build_watcher_control_state_detects_external_fresh_service() -> None:
    service_df = ops_supervision.build_service_health_dataframe(
        [_service_record(scope="acct-1", heartbeat="2026-04-26T10:02:45")],
        now=datetime.fromisoformat("2026-04-26T10:03:00"),
    )
    active_runs_df = pd.DataFrame(columns=["run_id", "step_key", "status", "account_id", "executed_at", "duration_seconds", "is_active"])

    state = ops_supervision.build_watcher_control_state(service_df, active_runs_df)

    assert state["fresh_service_detected"] is True
    assert state["external_fresh_service_detected"] is True
    assert state["local_service_active"] is False
    assert state["guardrail_messages"]


def test_build_watcher_control_state_prefers_local_service_when_active() -> None:
    service_df = ops_supervision.build_service_health_dataframe(
        [_service_record(scope="acct-1", heartbeat="2026-04-26T10:02:45")],
        now=datetime.fromisoformat("2026-04-26T10:03:00"),
    )
    active_runs_df = pd.DataFrame(
        [
            {
                "run_id": "watch-local-1",
                "step_key": "execution_protection_watch_service_local",
                "status": "running",
                "account_id": "acct-1",
                "executed_at": "2026-04-26T10:02:00",
                "duration_seconds": 60.0,
                "is_active": True,
            }
        ]
    )

    state = ops_supervision.build_watcher_control_state(service_df, active_runs_df)

    assert state["local_service_active"] is True
    assert state["local_service_run_id"] == "watch-local-1"
    assert state["external_fresh_service_detected"] is False


def test_build_watcher_history_dataframe_formats_runtime_runs() -> None:
    df = ops_supervision.build_watcher_history_dataframe(
        [
            {
                "run_id": "watch-2",
                "step_key": "execution_protection_watch_service_local",
                "status": "running",
                "account_id": "acct-1",
                "executed_at": "2026-04-26T10:03:00",
                "finished_at": None,
                "duration_seconds": 12.0,
                "stdout_lines": 4,
                "stderr_lines": 1,
                "run_summary": {},
            },
            {
                "run_id": "watch-1",
                "step_key": "execution_protection_watch_once",
                "status": "completed",
                "account_id": "acct-1",
                "executed_at": "2026-04-26T10:00:00",
                "finished_at": "2026-04-26T10:00:10",
                "duration_seconds": 10.0,
                "stdout_lines": 2,
                "stderr_lines": 0,
                "run_summary": {"watched_items": 2, "transitioned_items": 1},
            },
        ]
    )

    assert list(df["run_id"]) == ["watch-2", "watch-1"]
    assert list(df["type"]) == ["service local IHM", "once"]
    assert "Surveillés=2" in str(df.iloc[1]["summary"]) or "watched_items=2" in str(df.iloc[1]["summary"])


def test_build_windows_integration_dataframe_exposes_three_modes() -> None:
    df = ops_supervision.build_windows_integration_dataframe(account_id="acct-1")

    assert list(df["mode"]) == ["Task Scheduler", "NSSM", "Lanceur manuel"]
    assert all("acct-1" in command for command in df["command"])


def test_build_windows_runtime_dataframe_formats_task_and_service() -> None:
    df = ops_supervision.build_windows_runtime_dataframe(
        {
            "bridge_available": True,
            "bridge_mode": "read_only",
            "task": {
                "name": "AlphaTrade-ProtectionWatcher",
                "exists": True,
                "state": "Ready",
                "enabled": True,
                "lastRunTime": "2026-04-26T10:00:00",
                "nextRunTime": "2026-04-26T10:05:00",
                "lastTaskResult": "0",
                "stdoutPath": "C:/logs/task_stdout.log",
                "stderrPath": "C:/logs/task_stderr.log",
            },
            "service": {
                "name": "AlphaTradeProtectionWatcher",
                "exists": True,
                "status": "Running",
                "startType": "Auto",
                "displayName": "Alpha Trade Protection Watcher",
                "stdoutPath": "C:/logs/service_stdout.log",
                "stderrPath": "C:/logs/service_stderr.log",
            },
        }
    )

    assert list(df["runtime"]) == ["Task Scheduler", "NSSM / Service Windows"]
    assert list(df["bridge_mode"]) == ["read_only", "read_only"]
    assert list(df["exists"]) == [True, True]


def test_build_windows_log_sources_dataframe_uses_bridge_payload() -> None:
    df = ops_supervision.build_windows_log_sources_dataframe(
        {
            "logSources": [
                {"source": "Task Scheduler stdout", "runtime": "task", "kind": "stdout", "path": "C:/logs/task_stdout.log", "exists": True},
                {"source": "NSSM stderr", "runtime": "service", "kind": "stderr", "path": "C:/logs/service_stderr.log", "exists": False},
            ]
        }
    )

    assert list(df["source"]) == ["Task Scheduler stdout", "NSSM stderr"]
    assert list(df["exists"]) == [True, False]


def test_build_ops_supervision_snapshot_aggregates_metrics(monkeypatch) -> None:
    monkeypatch.setattr(
        ops_supervision,
        "get_ops_service_summaries",
        lambda account_id=None, limit=20: pd.DataFrame([_service_record(scope="acct-1", heartbeat="2026-04-26T10:00:00")]),
    )
    monkeypatch.setattr(
        ops_supervision,
        "get_ops_latest_critical_summaries",
        lambda account_id=None, limit=50: pd.DataFrame(
            [
                {
                    "step_key": "execution",
                    "status": "COMPLETED",
                    "entity_run_id": "exec-1",
                    "summary_run_id": "sum-1",
                    "run_summary": {"submitted_orders": 4, "filled_orders": 4},
                }
            ]
        ),
    )
    monkeypatch.setattr(
        ops_supervision,
        "list_active_pipeline_runs",
        lambda: [{"run_id": "wf-1", "step_key": "pipeline_workflow", "status": "running", "account_id": "acct-1", "executed_at": "2026-04-26T10:00:00", "duration_seconds": 10, "is_active": True}],
    )
    monkeypatch.setattr(
        ops_supervision,
        "list_watcher_run_history",
        lambda account_id=None, limit=50: [
            {
                "run_id": "watch-1",
                "step_key": "execution_protection_watch_once",
                "status": "completed",
                "account_id": "acct-1",
                "executed_at": "2026-04-26T09:59:00",
                "finished_at": "2026-04-26T09:59:15",
                "duration_seconds": 15.0,
                "stdout_lines": 2,
                "stderr_lines": 0,
                "run_summary": {"watched_items": 1},
            }
        ],
    )
    monkeypatch.setattr(
        ops_supervision,
        "get_windows_watcher_status",
        lambda: {
            "bridge_available": True,
            "bridge_mode": "read_only",
            "task": {"name": "AlphaTrade-ProtectionWatcher", "exists": True, "state": "Ready", "stdoutPath": "C:/logs/task_stdout.log", "stderrPath": "C:/logs/task_stderr.log"},
            "service": {"name": "AlphaTradeProtectionWatcher", "exists": True, "status": "Running", "startType": "Auto", "displayName": "Alpha Trade Protection Watcher", "stdoutPath": "C:/logs/service_stdout.log", "stderrPath": "C:/logs/service_stderr.log"},
            "logSources": [
                {"source": "Task Scheduler stdout", "runtime": "task", "kind": "stdout", "path": "C:/logs/task_stdout.log", "exists": True},
            ],
            "bridge": {"script": "get_protection_watcher_status.ps1", "mode": "read_only", "allowlist": ["status", "log_import"]},
        },
    )

    snapshot = ops_supervision.build_ops_supervision_snapshot(
        account_id="acct-1",
        now=datetime.fromisoformat("2026-04-26T10:00:30"),
    )

    assert snapshot["metrics"]["services_monitored"] == 1
    assert snapshot["metrics"]["active_runs"] == 1
    assert isinstance(snapshot["service_health"], pd.DataFrame)
    assert isinstance(snapshot["latest_runs"], pd.DataFrame)
    assert isinstance(snapshot["active_runs"], pd.DataFrame)
    assert isinstance(snapshot["watcher_history"], pd.DataFrame)
    assert isinstance(snapshot["watcher_windows_integration"], pd.DataFrame)
    assert isinstance(snapshot["watcher_windows_runtime"], pd.DataFrame)
    assert isinstance(snapshot["watcher_windows_log_sources"], pd.DataFrame)
    assert isinstance(snapshot["watcher_windows_bridge"], pd.DataFrame)
    assert snapshot["watcher_control"]["fresh_service_detected"] is True


