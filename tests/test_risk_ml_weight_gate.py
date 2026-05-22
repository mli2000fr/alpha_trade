from __future__ import annotations

from risk_management.config import RiskConfig
from risk_management.ml_gate import MlGateState, apply_ml_gate_to_risk_config


def test_apply_ml_gate_to_risk_config_forces_quant_only_when_disabled() -> None:
    config = RiskConfig(
        account_equity=25_000.0,
        score_weight=0.40,
        prediction_weight=0.60,
    )

    updated = apply_ml_gate_to_risk_config(
        config,
        MlGateState(enabled=False, reason="drift_policy_kill_switch", action="kill_switch_ml"),
    )

    assert updated.score_weight == 1.0
    assert updated.prediction_weight == 0.0


def test_apply_ml_gate_to_risk_config_keeps_weights_when_enabled() -> None:
    config = RiskConfig(
        account_equity=25_000.0,
        score_weight=0.45,
        prediction_weight=0.55,
    )

    updated = apply_ml_gate_to_risk_config(
        config,
        MlGateState(enabled=True, reason="drift_policy_enabled", action="allow"),
    )

    assert updated.score_weight == 0.45
    assert updated.prediction_weight == 0.55

