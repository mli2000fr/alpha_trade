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

    snapshot = ops_supervision.build_ops_supervision_snapshot(
        account_id="acct-1",
        now=datetime.fromisoformat("2026-04-26T10:00:30"),
    )

    assert snapshot["metrics"]["services_monitored"] == 1
    assert snapshot["metrics"]["active_runs"] == 1
    assert isinstance(snapshot["service_health"], pd.DataFrame)
    assert isinstance(snapshot["latest_runs"], pd.DataFrame)
    assert isinstance(snapshot["active_runs"], pd.DataFrame)


