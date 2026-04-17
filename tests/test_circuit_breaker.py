"""Tests unitaires — CircuitBreaker."""
from __future__ import annotations

from risk_management.circuit_breaker import CircuitBreaker, PnLSnapshot
from risk_management.config import RiskConfig


def _cfg() -> RiskConfig:
    return RiskConfig(max_portfolio_drawdown_pct=0.15, max_daily_loss_pct=0.05)


def test_no_pnl_not_active() -> None:
    cb = CircuitBreaker(_cfg())
    assert cb.is_active() is False


def test_drawdown_triggers() -> None:
    pnl = PnLSnapshot(portfolio_high_watermark=100_000, portfolio_current_value=84_000)
    cb = CircuitBreaker(_cfg(), pnl)
    assert cb.is_active() is True  # 16% > 15%


def test_drawdown_below_threshold() -> None:
    pnl = PnLSnapshot(portfolio_high_watermark=100_000, portfolio_current_value=90_000)
    cb = CircuitBreaker(_cfg(), pnl)
    assert cb.is_active() is False  # 10% < 15%


def test_daily_loss_triggers() -> None:
    pnl = PnLSnapshot(daily_pnl=-5_500)
    cb = CircuitBreaker(_cfg(), pnl)
    assert cb.is_active() is True  # 5.5% > 5%


def test_daily_loss_below_threshold() -> None:
    pnl = PnLSnapshot(daily_pnl=-3_000)
    cb = CircuitBreaker(_cfg(), pnl)
    assert cb.is_active() is False
