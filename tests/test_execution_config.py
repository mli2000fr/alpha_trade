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


# ---------------------------------------------------------------------------
# Contraintes de compte runtime encore actives
# ---------------------------------------------------------------------------

class TestAccountConstraints:
    def test_cash_account_can_be_configured_for_swing_only(self) -> None:
        cfg = ExecutionConfig(account_type="cash", swing_only=True, cash_settlement_days=1)

        assert cfg.account_type == "cash"
        assert cfg.swing_only is True
        assert cfg.cash_settlement_days == 1

    def test_margin_account_supports_intraday_configuration(self) -> None:
        cfg = ExecutionConfig(account_type="margin", swing_only=False)

        assert cfg.account_type == "margin"
        assert cfg.swing_only is False


# ---------------------------------------------------------------------------
# Sprint S2 / A-017 — fill_timeout_seconds
# ---------------------------------------------------------------------------

class TestFillTimeout:
    """[A-017] Vérifie la valeur par défaut et la configurabilité de fill_timeout."""

    def test_fill_timeout_default_is_180_seconds(self) -> None:
        """fill_timeout_seconds doit être 180s par défaut (paper mode)."""
        cfg = ExecutionConfig()
        assert cfg.fill_timeout_seconds == 180, (
            f"fill_timeout_seconds={cfg.fill_timeout_seconds} — attendu 180s "
            f"(réduit les ordres orphelins lors de gaps d'ouverture volatils)"
        )

    def test_fill_timeout_configurable_for_live(self) -> None:
        """En live, l'opérateur peut configurer 300s via preset."""
        cfg = ExecutionConfig(broker_mode="live", fill_timeout_seconds=300)
        assert cfg.fill_timeout_seconds == 300

    def test_fill_timeout_must_be_positive(self) -> None:
        """fill_timeout_seconds doit être > 0."""
        with pytest.raises(ValueError, match="fill_timeout_seconds"):
            ExecutionConfig(fill_timeout_seconds=0)


