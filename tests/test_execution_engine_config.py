import pytest

from execution_engine.config import (
    ExecutionConfig,
    ProtectionWatcherServiceConfig,
    load_trailing_stop_config_from_yaml,
)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"broker_mode": "sandbox"}, "broker_mode"),
        ({"execution_profile": "overnight"}, "execution_profile"),
        ({"submission_window": "intraday"}, "submission_window"),
        ({"account_type": "leveraged"}, "account_type"),
        ({"pdt_rule": "strict"}, "pdt_rule"),
        ({"entry_order_type": "stop"}, "entry_order_type"),
        ({"max_entry_gap_pct": -0.01}, "max_entry_gap_pct"),
        ({"max_entry_gap_pct": 1.0}, "max_entry_gap_pct"),
        ({"profit_taker_pct": 0}, "profit_taker_pct"),
        ({"trailing_stop_pct": 1}, "trailing_stop_pct"),
        ({"trailing_activation_trigger": "unknown"}, "trailing_activation_trigger"),
        ({"trailing_activation_r_multiple": 0}, "trailing_activation_r_multiple"),
        ({"trailing_activation_profit_pct": 1}, "trailing_activation_profit_pct"),
        ({"max_slippage_bps": 600}, "max_slippage_bps"),
        ({"max_order_retries": -1}, "max_order_retries"),
        ({"retry_base_delay_seconds": 0}, "retry_base_delay_seconds"),
        ({"inter_order_delay_ms": -1}, "inter_order_delay_ms"),
        ({"poll_interval_seconds": 0}, "poll_interval_seconds"),
        ({"fill_timeout_seconds": 0}, "fill_timeout_seconds"),
        ({"cancel_timeout_seconds": 0}, "cancel_timeout_seconds"),
        ({"protection_transition_timeout_seconds": -1}, "protection_transition_timeout_seconds"),
        ({"protection_transition_poll_interval_seconds": 0}, "protection_transition_poll_interval_seconds"),
        ({"execution_batch_size": 0}, "execution_batch_size"),
        ({"max_consecutive_failures": 0}, "max_consecutive_failures"),
        ({"pdt_equity_threshold": 0}, "pdt_equity_threshold"),
        ({"max_day_trades": 0}, "max_day_trades"),
        ({"cash_settlement_days": 0}, "cash_settlement_days"),
        ({"simulated_account_equity": 0}, "simulated_account_equity"),
        ({"simulated_margin_buying_power_multiplier": 0.5}, "simulated_margin_buying_power_multiplier"),
        ({"regime_max_positions": 0}, "regime_max_positions"),
        ({"regime_max_position_weight": 0}, "regime_max_position_weight"),
        ({"regime_max_position_weight": 1.1}, "regime_max_position_weight"),
        ({"regime_max_sector_weight": 0}, "regime_max_sector_weight"),
        ({"regime_max_sector_weight": 1.1}, "regime_max_sector_weight"),
        ({"regime_max_gross_exposure": 0}, "regime_max_gross_exposure"),
        ({"regime_max_gross_exposure": 1.1}, "regime_max_gross_exposure"),
    ],
)
def test_execution_config_validates_invalid_values(kwargs, message):
    with pytest.raises(ValueError, match=message):
        ExecutionConfig(**kwargs)


def test_execution_config_is_paper_by_default() -> None:
    cfg = ExecutionConfig()

    assert cfg.is_paper() is True
    assert cfg.is_live() is False


def test_execution_config_is_live_when_requested() -> None:
    cfg = ExecutionConfig(broker_mode="live")

    assert cfg.is_live() is True
    assert cfg.is_paper() is False


def test_execution_config_disables_effective_pdt_for_cash_account() -> None:
    cfg = ExecutionConfig(account_type="cash", pdt_rule="auto")

    assert cfg.effective_pdt_rule == "off"
    assert cfg.applies_pdt_limit(2_000.0) is False


def test_execution_config_defaults_to_overnight_profile() -> None:
    cfg = ExecutionConfig()

    assert cfg.execution_profile == "overnight_cash_swing"
    assert cfg.submission_window == "both"
    assert cfg.is_overnight_profile is True
    assert cfg.resolved_account_id == "default"


def test_execution_config_resolves_explicit_account_id() -> None:
    cfg = ExecutionConfig(account_id="live1", submission_window="pre_open")

    assert cfg.resolved_account_id == "live1"
    assert cfg.submission_window == "pre_open"


def test_execution_config_accepts_optional_regime_guards() -> None:
    cfg = ExecutionConfig(
        regime_max_positions=3,
        regime_max_position_weight=0.20,
        regime_max_sector_weight=0.35,
        regime_max_gross_exposure=0.45,
    )

    assert cfg.regime_max_positions == 3
    assert cfg.regime_max_position_weight == pytest.approx(0.20)
    assert cfg.regime_max_sector_weight == pytest.approx(0.35)
    assert cfg.regime_max_gross_exposure == pytest.approx(0.45)


def test_load_trailing_stop_config_from_yaml_uses_risk_management_section() -> None:
    cfg = load_trailing_stop_config_from_yaml(
        {
            "risk_management": {
                "trailing_stop": {
                    "enabled": True,
                    "mode": "dynamic_atr",
                    "atr_period": 21,
                    "atr_multiplier": 3.0,
                    "fallback_fixed_pct": 6.5,
                    "break_even_after_atr_multiple": 1.5,
                    "eod_check_time_est": "15:45",
                    "apply_to_manual_orphan_buys": False,
                }
            }
        }
    )

    assert cfg.enabled is True
    assert cfg.mode == "dynamic_atr"
    assert cfg.atr_period == 21
    assert cfg.atr_multiplier == pytest.approx(3.0)
    assert cfg.fallback_fixed_pct == pytest.approx(6.5)
    assert cfg.break_even_after_atr_multiple == pytest.approx(1.5)
    assert cfg.eod_check_time_est == "15:45"
    assert cfg.apply_to_manual_orphan_buys is False


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"interval_seconds": 0}, "interval_seconds"),
        ({"idle_interval_seconds": 0}, "idle_interval_seconds"),
        ({"heartbeat_interval_seconds": 0}, "heartbeat_interval_seconds"),
        ({"max_iterations": 0}, "max_iterations"),
        ({"max_consecutive_failures": 0}, "max_consecutive_failures"),
    ],
)
def test_protection_watcher_service_config_validates_invalid_values(kwargs, message):
    with pytest.raises(ValueError, match=message):
        ProtectionWatcherServiceConfig(**kwargs)


