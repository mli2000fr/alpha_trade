from __future__ import annotations

import pandas as pd
import pytest

from risk_management.config import RiskConfig
from risk_management.live_pipeline_guards import (
    apply_vol_target_to_risk_config,
    evaluate_ml_coverage_gate,
    evaluate_vol_target,
)


def test_evaluate_ml_coverage_gate_blocks_when_threshold_is_not_met() -> None:
    decision = evaluate_ml_coverage_gate(
        candidate_count=10,
        prediction_count=7,
        min_coverage_ratio=0.80,
        regime_allows_new_entries=True,
        ml_gate_enabled=True,
    )

    assert decision.enabled is True
    assert decision.allowed is False
    assert decision.coverage_ratio == pytest.approx(0.70)
    assert decision.required_ratio == pytest.approx(0.80)
    assert decision.reason == "coverage_below_threshold"



def test_evaluate_ml_coverage_gate_is_skipped_when_regime_blocks_entries() -> None:
    decision = evaluate_ml_coverage_gate(
        candidate_count=10,
        prediction_count=0,
        min_coverage_ratio=0.80,
        regime_allows_new_entries=False,
        ml_gate_enabled=True,
    )

    assert decision.enabled is True
    assert decision.allowed is True
    assert decision.reason == "skipped_by_regime"



def test_apply_vol_target_to_risk_config_scales_risk_and_exposure() -> None:
    returns = pd.Series([0.02, -0.02] * 30, dtype=float)
    decision = evaluate_vol_target(
        returns,
        target_annual_vol=0.12,
        lookback_days=60,
        benchmark_symbol="SPY",
    )
    config = RiskConfig(account_equity=100_000.0, risk_multiplier=1.0, max_gross_exposure=1.0)

    updated = apply_vol_target_to_risk_config(config, decision)

    assert decision.enabled is True
    assert decision.applied is True
    assert 0.0 < decision.scaler < 1.0
    assert updated.risk_multiplier == pytest.approx(decision.scaler)
    assert updated.max_gross_exposure == pytest.approx(decision.scaler)

