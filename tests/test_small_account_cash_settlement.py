from __future__ import annotations

from common.capital_presets import apply_backtest_defaults_from_preset, get_capital_preset_by_key
from backtesting.trading_constraints import TradingConstraintConfig


def test_micro_account_preset_uses_current_margin_profile() -> None:
    preset = get_capital_preset_by_key("capital_0_2000")

    assert preset is not None
    updated = apply_backtest_defaults_from_preset(
        {
            "account_type": "margin",
            "swing_only": False,
            "cash_settlement_days": 2,
        },
        preset,
        explicit_flags=set(),
    )

    constraints = TradingConstraintConfig(
        account_type=str(updated["account_type"]),
        swing_only=bool(updated["swing_only"]),
        cash_settlement_days=int(updated["cash_settlement_days"]),
    )

    assert constraints.account_type == "margin"
    assert constraints.use_settled_cash_only is False
    assert constraints.cash_settlement_days == 1
    assert constraints.requires_stateful_simulation(2_000.0) is False


def test_margin_preset_keeps_cash_settlement_at_zero() -> None:
    preset = get_capital_preset_by_key("capital_50001_100000")

    assert preset is not None
    updated = apply_backtest_defaults_from_preset(
        {
            "account_type": "cash",
            "swing_only": True,
            "cash_settlement_days": 1,
        },
        preset,
        explicit_flags=set(),
    )

    constraints = TradingConstraintConfig(
        account_type=str(updated["account_type"]),
        swing_only=bool(updated["swing_only"]),
        cash_settlement_days=int(updated["cash_settlement_days"]),
    )

    assert constraints.account_type == "margin"
    assert constraints.use_settled_cash_only is False
    assert constraints.cash_settlement_days == 0

