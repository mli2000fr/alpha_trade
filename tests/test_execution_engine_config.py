import pytest

from execution_engine.config import ExecutionConfig, ProtectionWatcherServiceConfig


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"broker_mode": "sandbox"}, "broker_mode"),
        ({"account_type": "leveraged"}, "account_type"),
        ({"pdt_rule": "strict"}, "pdt_rule"),
        ({"entry_order_type": "stop"}, "entry_order_type"),
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


