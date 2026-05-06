"""Sprint S4 (A-021) — tests pour modelFactory/drift_policy.py."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from modelFactory.drift_monitor import DriftReport, compute_drift
from modelFactory.drift_policy import (
    DEFAULT_KILL_STATUSES,
    MLPolicyDecision,
    apply_kill_switch,
    evaluate_drift_gate,
    persist_kill_switch_event,
    summary_fields,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def baseline_predictions() -> np.ndarray:
    rng = np.random.default_rng(0)
    return rng.uniform(0.30, 0.70, size=500)


@pytest.fixture
def today_alert() -> np.ndarray:
    """Distribution franchement déplacée → status ALERT (PSI ≥ 0.25)."""
    rng = np.random.default_rng(1)
    return rng.uniform(0.85, 0.99, size=200)


@pytest.fixture
def today_ok() -> np.ndarray:
    """Distribution proche de la baseline → status OK."""
    rng = np.random.default_rng(2)
    return rng.uniform(0.30, 0.70, size=200)


# ---------------------------------------------------------------------------
# evaluate_drift_gate
# ---------------------------------------------------------------------------

def test_gate_disabled_on_alert(baseline_predictions, today_alert):
    report = compute_drift(today_alert, baseline_predictions, model_id="m-alert")
    assert report.status == "ALERT"
    decision = evaluate_drift_gate(report)
    assert decision.gate == "disabled"
    assert decision.action == "kill_switch_ml"
    assert decision.drift_status == "ALERT"
    assert decision.model_id == "m-alert"
    assert "ALERT" in decision.reason


def test_gate_enabled_on_ok(baseline_predictions, today_ok):
    report = compute_drift(today_ok, baseline_predictions, model_id="m-ok")
    assert report.status == "OK"
    decision = evaluate_drift_gate(report)
    assert decision.gate == "enabled"
    assert decision.action == "allow"


def test_gate_none_report_returns_allow():
    decision = evaluate_drift_gate(None)
    assert decision.action == "allow"
    assert decision.gate == "enabled"
    assert decision.drift_status == "n/a"
    assert decision.reason == "no_drift_report_available"


def test_warn_does_not_kill_by_default():
    report = DriftReport(
        model_id="m-warn", n_samples=200, n_baseline=500,
        ks_stat=0.1, ks_pvalue=0.03, psi=0.15, status="WARN", notes=[],
    )
    decision = evaluate_drift_gate(report)
    assert decision.gate == "enabled"
    assert decision.action == "allow"


def test_warn_can_be_killed_when_grace_off():
    report = DriftReport(
        model_id="m-warn", n_samples=200, n_baseline=500,
        ks_stat=0.1, ks_pvalue=0.03, psi=0.15, status="WARN", notes=[],
    )
    decision = evaluate_drift_gate(report, kill_on=("WARN", "ALERT"), warn_grace=False)
    assert decision.action == "kill_switch_ml"


def test_sample_size_too_small_does_not_kill():
    report = DriftReport(
        model_id="m-small", n_samples=2, n_baseline=10,
        ks_stat=None, ks_pvalue=None, psi=None,
        status="OK", notes=["sample_size_too_small"],
    )
    decision = evaluate_drift_gate(report)
    assert decision.action == "allow"
    assert decision.reason == "sample_size_too_small"


# ---------------------------------------------------------------------------
# apply_kill_switch
# ---------------------------------------------------------------------------

def test_apply_kill_switch_neutralizes_predictions():
    df = pd.DataFrame({
        "symbol": ["AAPL", "MSFT"],
        "predicted_proba": [0.91, 0.93],
        "raw_proba": [0.91, 0.93],
    })
    decision = MLPolicyDecision(
        model_id="x", drift_status="ALERT", gate="disabled",
        action="kill_switch_ml", reason="test",
        ks_pvalue=0.001, psi=0.4, n_samples=10, n_baseline=100,
        computed_at="2026-05-06T00:00:00+00:00",
    )
    out = apply_kill_switch(decision, df)
    assert out["ml_disabled"].all()
    assert out["predicted_proba"].isna().all()
    assert out["raw_proba"].isna().all()


def test_apply_kill_switch_pass_through_when_allow():
    df = pd.DataFrame({"symbol": ["AAPL"], "predicted_proba": [0.6]})
    decision = MLPolicyDecision(
        model_id="x", drift_status="OK", gate="enabled",
        action="allow", reason="ok", ks_pvalue=0.5, psi=0.05,
        n_samples=200, n_baseline=500, computed_at="t",
    )
    out = apply_kill_switch(decision, df)
    assert (out["ml_disabled"] == False).all()  # noqa: E712
    assert out["predicted_proba"].iloc[0] == 0.6


# ---------------------------------------------------------------------------
# summary_fields
# ---------------------------------------------------------------------------

def test_summary_fields_with_kill_switch():
    decision = MLPolicyDecision(
        model_id="x", drift_status="ALERT", gate="disabled",
        action="kill_switch_ml", reason="boom",
        ks_pvalue=0.001, psi=0.4, n_samples=10, n_baseline=100,
        computed_at="t",
    )
    fields = summary_fields(decision)
    assert fields["ml_drift_status"] == "ALERT"
    assert fields["ml_kill_switch_active"] is True
    assert fields["ml_kill_switch_reason"] == "boom"
    assert fields["ml_drift_ks_pvalue"] == 0.001
    assert fields["ml_drift_psi"] == 0.4


def test_summary_fields_when_no_decision():
    fields = summary_fields(None)
    assert fields["ml_kill_switch_active"] is False
    assert fields["ml_drift_status"] == "n/a"
    assert fields["ml_kill_switch_reason"] is None


# ---------------------------------------------------------------------------
# persist_kill_switch_event
# ---------------------------------------------------------------------------

def test_persist_kill_switch_event_payload(tmp_path):
    sqlalchemy = pytest.importorskip("sqlalchemy")
    engine = sqlalchemy.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(sqlalchemy.text(
            """
            CREATE TABLE ml_drift_runs (
                run_id TEXT PRIMARY KEY,
                computed_at TIMESTAMP,
                model_id TEXT,
                ks_stat REAL,
                ks_pvalue REAL,
                psi REAL,
                n_samples INTEGER,
                n_baseline INTEGER,
                status TEXT,
                payload TEXT,
                schema_version INTEGER
            )
            """
        ))
    decision = MLPolicyDecision(
        model_id="m-1", drift_status="ALERT", gate="disabled",
        action="kill_switch_ml", reason="r",
        ks_pvalue=0.001, psi=0.4, n_samples=10, n_baseline=100,
        computed_at="t",
    )
    persist_kill_switch_event(decision, engine=engine)
    with engine.connect() as conn:
        row = conn.execute(sqlalchemy.text("SELECT status, payload FROM ml_drift_runs")).fetchone()
    assert row is not None
    status, payload_json = row
    assert status == "ALERT"
    payload = json.loads(payload_json)
    assert payload["gate_action"] == "kill_switch_ml"
    assert payload["decision"]["model_id"] == "m-1"


def test_default_kill_statuses():
    assert "ALERT" in DEFAULT_KILL_STATUSES

