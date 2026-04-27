"""Tests Phase 7.4 — drift monitoring ML (audit_global §7.4)."""
from __future__ import annotations

import numpy as np

from modelFactory.drift_monitor import compute_drift


def test_drift_ok_when_distribution_similar() -> None:
    rng = np.random.default_rng(42)
    baseline = rng.uniform(0.3, 0.7, 500)
    today = rng.uniform(0.3, 0.7, 200)
    report = compute_drift(today, baseline, model_id="lgbm-v1")
    assert report.status == "OK"
    assert report.n_samples == 200
    assert report.n_baseline == 500


def test_drift_alert_on_strong_shift() -> None:
    rng = np.random.default_rng(0)
    baseline = rng.uniform(0.1, 0.4, 500)
    today = rng.uniform(0.7, 0.95, 200)  # shift massif
    report = compute_drift(today, baseline, model_id="lgbm-v1")
    assert report.status == "ALERT"
    assert report.psi is not None and report.psi > 0.25


def test_drift_too_small_sample() -> None:
    report = compute_drift([0.1, 0.2], [0.3, 0.4, 0.5], model_id="lgbm-v1")
    assert report.status == "OK"
    assert "sample_size_too_small" in report.notes
    assert report.ks_stat is None


def test_drift_payload_schema() -> None:
    rng = np.random.default_rng(1)
    baseline = rng.uniform(0, 1, 200)
    today = rng.uniform(0, 1, 100)
    report = compute_drift(today, baseline, model_id="lgbm-v1")
    payload = report.to_payload()
    assert payload["schema_version"] == 1
    assert payload["model_id"] == "lgbm-v1"
    assert payload["status"] in {"OK", "WARN", "ALERT"}

