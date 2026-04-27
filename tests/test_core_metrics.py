"""Tests Phase 7.5 — module ``core.metrics`` (audit_global §7.5)."""
from __future__ import annotations

import importlib

import pytest

import core.metrics as metrics


def test_metrics_module_importable() -> None:
    assert hasattr(metrics, "run_summary_total")
    assert hasattr(metrics, "start_metrics_server")
    assert hasattr(metrics, "is_available")


def test_record_run_summary_never_raises() -> None:
    # Ne doit jamais lever quel que soit l'état (avec ou sans prometheus_client).
    metrics.record_run_summary("test_module", "OK")
    metrics.record_run_summary("test_module", "ERROR")


def test_start_metrics_server_no_port_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPHA_TRADE_METRICS_PORT", raising=False)
    importlib.reload(metrics)
    assert metrics.start_metrics_server() is False


def test_start_metrics_server_invalid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_TRADE_METRICS_PORT", "not-a-port")
    importlib.reload(metrics)
    assert metrics.start_metrics_server() is False


@pytest.mark.skipif(not metrics.is_available(), reason="prometheus_client non installé")
def test_metrics_labels_inc_no_raise() -> None:
    metrics.run_summary_total.labels(module="unit", status="OK").inc()
    metrics.watcher_heartbeat_age_seconds.labels(account_id="paper1").set(12.3)
    metrics.ml_drift_status.labels(model_id="lgbm-v1").set(0)

