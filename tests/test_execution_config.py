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
# Sprint S2 / A-006 — PDT rule auto sur compte margin avec drawdown
# ---------------------------------------------------------------------------

class TestPDTRuleMarginDrawdown:
    """[A-006] Vérifie que applies_pdt_limit() bloque le 4e day-trade quand
    l'equity chute sous 25 000 $ sur un compte margin avec pdt_rule='auto'."""

    def test_pdt_auto_margin_equity_above_threshold_no_block(self) -> None:
        """Equity > 25k$ → PDT non appliqué (compte en sécurité)."""
        cfg = ExecutionConfig(account_type="margin", pdt_rule="auto")
        assert cfg.applies_pdt_limit(30_000.0) is False

    def test_pdt_auto_margin_equity_below_threshold_blocks(self) -> None:
        """Equity < 25k$ → PDT appliqué automatiquement."""
        cfg = ExecutionConfig(account_type="margin", pdt_rule="auto")
        assert cfg.applies_pdt_limit(24_999.99) is True

    def test_pdt_auto_margin_equity_at_threshold_no_block(self) -> None:
        """Equity = 25k$ exactement → PDT non bloquant (limite exclusive)."""
        cfg = ExecutionConfig(account_type="margin", pdt_rule="auto")
        # applies_pdt_limit: equity < threshold (strict)
        assert cfg.applies_pdt_limit(25_000.0) is False

    def test_pdt_off_margin_never_blocks(self) -> None:
        """pdt_rule='off' sur margin → jamais de blocage PDT, même sous 25k$."""
        cfg = ExecutionConfig(account_type="margin", pdt_rule="off")
        assert cfg.applies_pdt_limit(10_000.0) is False

    def test_pdt_cash_account_never_blocks(self) -> None:
        """Sur compte cash, effective_pdt_rule='off' quelle que soit la config."""
        cfg = ExecutionConfig(account_type="cash", pdt_rule="auto")
        assert cfg.effective_pdt_rule == "off"
        assert cfg.applies_pdt_limit(5_000.0) is False


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


