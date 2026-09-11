from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from modelFactory.directional_alpha_book_confirmation import (
    DEFAULT_PREREGISTRATION,
    LOCKED_PREREGISTRATION_SHA256,
    build_confirmation_cohorts,
    decide_confirmation,
    load_locked_preregistration,
)


def _protocol() -> dict:
    return load_locked_preregistration(DEFAULT_PREREGISTRATION)


def test_preregistration_is_locked_and_oracle_free() -> None:
    protocol = _protocol()
    assert len(LOCKED_PREREGISTRATION_SHA256) == 64
    assert protocol["oracle_used"] is False
    assert protocol["signal"] == "residual_momentum_120_10"
    assert protocol["horizon_sessions"] == 120
    assert protocol["portfolio"]["side"] == "long_only"
    assert protocol["confirmation_start_date"] == "2026-09-14"


def test_modified_preregistration_is_rejected(tmp_path: Path) -> None:
    protocol = _protocol()
    protocol["portfolio"]["round_trip_cost_bps"] = 5.0
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(protocol), encoding="utf-8")
    with pytest.raises(ValueError, match="changé après verrouillage"):
        load_locked_preregistration(changed)


def test_confirmation_cohorts_ignore_pre_registration_dates_and_use_long_top20() -> None:
    protocol = _protocol()
    rows = []
    for cohort_date in (pd.Timestamp("2026-09-11"), pd.Timestamp("2026-09-14")):
        for index in range(100):
            score = -1.0 + 2.0 * index / 99
            rows.append({
                "date": cohort_date,
                "symbol": f"S{index:03d}",
                "market_eligible": True,
                "score_residual_momentum_120_10": score,
                "future_return_h120": score * 0.10,
                "benchmark_future_return_h120": 0.01,
            })
    cohorts = build_confirmation_cohorts(pd.DataFrame(rows), protocol)
    assert cohorts["date"].tolist() == [pd.Timestamp("2026-09-14")]
    assert cohorts.loc[0, "selected_symbols"] == 20
    assert cohorts.loc[0, "long_return_net"] > 0
    assert cohorts.loc[0, "universe_return_net"] == pytest.approx(-0.0006)


def test_decision_remains_pending_before_minimum_evidence() -> None:
    protocol = _protocol()
    cohorts = pd.DataFrame({
        "date": pd.bdate_range("2026-09-14", periods=10),
        "selected_symbols": 100,
        "long_return_net": 0.10,
        "excess_vs_universe": 0.05,
        "excess_vs_spy": 0.04,
    })
    result = decide_confirmation(cohorts, protocol)
    assert result["verdict"] == "PENDING_DATA"
    assert not result["minimum_evidence_satisfied"]


def test_decision_can_go_only_after_all_locked_gates_pass() -> None:
    protocol = _protocol()
    dates = pd.date_range("2026-09-14", periods=24, freq="40D")
    cohorts = pd.DataFrame({
        "date": dates,
        "selected_symbols": np.full(24, 100),
        "long_return_net": np.linspace(0.08, 0.12, 24),
        "excess_vs_universe": np.linspace(0.035, 0.055, 24),
        "excess_vs_spy": np.linspace(0.025, 0.045, 24),
    })
    result = decide_confirmation(cohorts, protocol)
    assert result["minimum_evidence_satisfied"]
    assert all(result["gates"].values())
    assert result["verdict"] == "GO_RESEARCH_SHADOW_ONLY"


def test_failed_gate_yields_no_go_after_sufficient_evidence() -> None:
    protocol = _protocol()
    dates = pd.date_range("2026-09-14", periods=24, freq="40D")
    cohorts = pd.DataFrame({
        "date": dates,
        "selected_symbols": np.full(24, 100),
        "long_return_net": np.linspace(-0.12, -0.08, 24),
        "excess_vs_universe": np.linspace(-0.055, -0.035, 24),
        "excess_vs_spy": np.linspace(-0.045, -0.025, 24),
    })
    result = decide_confirmation(cohorts, protocol)
    assert result["minimum_evidence_satisfied"]
    assert result["verdict"] == "NO_GO"

