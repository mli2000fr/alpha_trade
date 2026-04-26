"""Tests for execution_engine.config."""
from __future__ import annotations

import pytest
from execution_engine.config import ExecutionConfig, ProtectionWatcherServiceConfig


class TestExecutionConfig:
    def test_default_values(self) -> None:
        cfg = ExecutionConfig()
        assert cfg.broker_mode == "paper"
        assert cfg.dry_run is False
        assert cfg.entry_order_type == "market"
        assert cfg.profit_taker_pct == 0.08
        assert cfg.trailing_stop_pct == 0.05
        assert cfg.trailing_activation_trigger == "multiple_r"
        assert cfg.protection_transition_timeout_seconds == 0

    def test_valid_paper_mode(self) -> None:
        cfg = ExecutionConfig(broker_mode="paper")
        assert cfg.is_paper()
        assert not cfg.is_live()

    def test_valid_live_mode(self) -> None:
        cfg = ExecutionConfig(broker_mode="live")
        assert cfg.is_live()
        assert not cfg.is_paper()

    def test_invalid_broker_mode(self) -> None:
        with pytest.raises(ValueError, match="broker_mode"):
            ExecutionConfig(broker_mode="sandbox")

    def test_invalid_profit_taker_pct(self) -> None:
        with pytest.raises(ValueError):
            ExecutionConfig(profit_taker_pct=0.0)
        with pytest.raises(ValueError):
            ExecutionConfig(profit_taker_pct=1.0)

    def test_is_paper(self) -> None:
        assert ExecutionConfig(broker_mode="paper").is_paper()

    def test_is_live(self) -> None:
        assert ExecutionConfig(broker_mode="live").is_live()

    def test_protection_watcher_service_config_default_values(self) -> None:
        cfg = ProtectionWatcherServiceConfig()

        assert cfg.interval_seconds == 30.0
        assert cfg.idle_interval_seconds == 120.0
        assert cfg.heartbeat_interval_seconds == 300.0
        assert cfg.max_iterations is None
        assert cfg.stop_when_idle is False
        assert cfg.max_consecutive_failures == 3

