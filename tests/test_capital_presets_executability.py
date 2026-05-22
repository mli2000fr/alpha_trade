from __future__ import annotations

import pytest

from common.capital_presets import (
    apply_backtest_defaults_from_preset,
    build_capital_preset_executability_summary,
    get_capital_preset_by_key,
)


def test_build_capital_preset_executability_summary_for_small_cash_account() -> None:
    preset = get_capital_preset_by_key("capital_0_5000")

    assert preset is not None
    summary = build_capital_preset_executability_summary(preset, detected_equity=3_500.0)

    assert summary["preset_key"] == "capital_0_5000"
    assert summary["account_type"] == "cash"
    assert summary["pdt_rule"] == "off"
    assert summary["cash_settlement_days"] == 1
    assert summary["min_position_notional"] == pytest.approx(150.0)
    assert summary["ticket_share_of_equity"] == pytest.approx(150.0 / 3_500.0, rel=1e-6)
    assert summary["recommended_commission_bps_stress"] == pytest.approx(12.0)
    assert summary["recommended_slippage_bps_stress"] == pytest.approx(20.0)
    assert summary["ml_gate_policy"] == "quant_only_on_ml_gate_disable"
    assert any("T+1" in warning for warning in summary["warnings"])
    assert any("ticket minimal effectif 150 $" in warning for warning in summary["warnings"])


def test_apply_backtest_defaults_from_preset_prefills_costs_and_settlement() -> None:
    preset = get_capital_preset_by_key("capital_0_5000")

    assert preset is not None
    updated = apply_backtest_defaults_from_preset(
        {
            "max_positions": 20,
            "account_type": "margin",
            "pdt_rule": "auto",
            "swing_only": False,
            "cash_settlement_days": 3,
            "commission_bps": 5.0,
            "slippage_bps": 5.0,
        },
        preset,
        explicit_flags=set(),
    )

    assert updated["max_positions"] == 4
    assert updated["account_type"] == "cash"
    assert updated["pdt_rule"] == "off"
    assert updated["swing_only"] is True
    assert updated["cash_settlement_days"] == 1
    assert updated["commission_bps"] == pytest.approx(12.0)
    assert updated["slippage_bps"] == pytest.approx(20.0)

