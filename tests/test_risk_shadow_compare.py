"""Tests Phase 7.7 — shadow compare offline (audit_global §7.7)."""
from __future__ import annotations

import pandas as pd

from risk_management.shadow_compare import compare_runs


def test_shadow_compare_basic_drift() -> None:
    live = pd.DataFrame(
        [
            {"symbol": "AAPL", "qty": 100, "price": 200.0, "conviction": 0.7},
            {"symbol": "MSFT", "qty": 50, "price": 380.0, "conviction": 0.6},
        ]
    )
    sim = pd.DataFrame(
        [
            {"symbol": "AAPL", "qty": 110, "price": 198.0, "conviction": 0.65},
            {"symbol": "GOOG", "qty": 30, "price": 150.0, "conviction": 0.55},
        ]
    )
    report = compare_runs(live, sim, live_run_id="run-live", simulated_run_id="run-sim")
    assert report.symbols_only_in_live == ["MSFT"]
    assert report.symbols_only_in_sim == ["GOOG"]
    # Drift qty AAPL = (100 - 110) / 110 ≈ -0.0909
    assert report.avg_qty_drift_pct is not None
    assert abs(report.avg_qty_drift_pct + 10 / 110) < 1e-6
    # Drift price AAPL = (200 - 198) / 198 ≈ +0.0101
    assert report.avg_price_drift_pct is not None
    assert report.avg_price_drift_pct > 0
    # Drift conviction = 0.7 - 0.65 = 0.05
    assert report.avg_conviction_drift is not None
    assert abs(report.avg_conviction_drift - 0.05) < 1e-6


def test_shadow_compare_empty_inputs() -> None:
    report = compare_runs(
        pd.DataFrame(columns=["symbol", "qty", "price", "conviction"]),
        pd.DataFrame(columns=["symbol", "qty", "price", "conviction"]),
        live_run_id="L",
        simulated_run_id="S",
    )
    assert report.symbols_only_in_live == []
    assert report.symbols_only_in_sim == []
    assert report.avg_qty_drift_pct is None


def test_shadow_compare_payload_schema() -> None:
    live = pd.DataFrame([{"symbol": "X", "qty": 10, "price": 1.0, "conviction": 0.5}])
    report = compare_runs(live, live, live_run_id="A", simulated_run_id="B")
    payload = report.to_payload()
    assert payload["schema_version"] == 1
    # Self-compare → drifts nuls
    assert payload["avg_qty_drift_pct"] == 0.0

