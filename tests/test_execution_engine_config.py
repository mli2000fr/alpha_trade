import pytest

from execution_engine.config import ExecutionConfig


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"broker_mode": "sandbox"}, "broker_mode"),
        ({"entry_order_type": "stop"}, "entry_order_type"),
        ({"profit_taker_pct": 0}, "profit_taker_pct"),
        ({"trailing_stop_pct": 1}, "trailing_stop_pct"),
        ({"max_slippage_bps": 600}, "max_slippage_bps"),
        ({"max_order_retries": -1}, "max_order_retries"),
        ({"retry_base_delay_seconds": 0}, "retry_base_delay_seconds"),
        ({"inter_order_delay_ms": -1}, "inter_order_delay_ms"),
        ({"poll_interval_seconds": 0}, "poll_interval_seconds"),
        ({"fill_timeout_seconds": 0}, "fill_timeout_seconds"),
        ({"cancel_timeout_seconds": 0}, "cancel_timeout_seconds"),
        ({"execution_batch_size": 0}, "execution_batch_size"),
        ({"max_consecutive_failures": 0}, "max_consecutive_failures"),
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

