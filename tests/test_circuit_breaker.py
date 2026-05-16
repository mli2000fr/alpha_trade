"""Tests unitaires — CircuitBreaker.

Sprint S3 / A-013 : notification email best-effort sur déclenchement.
"""
from __future__ import annotations

from typing import Any

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


# ---------------------------------------------------------------------------
# Sprint S3 / A-013 — notification email sur déclenchement circuit breaker
# ---------------------------------------------------------------------------

def test_circuit_breaker_drawdown_calls_send_notification(monkeypatch) -> None:
    """Quand un drawdown déclenche le CB, send_notification doit être appelé."""
    import risk_management.circuit_breaker as cb_mod

    calls: list[dict[str, Any]] = []

    def fake_send_notification(event: str, payload: dict | None = None) -> bool:
        calls.append({"event": event, "payload": payload or {}})
        return True

    monkeypatch.setattr(cb_mod, "_try_send_alert", lambda event, payload: calls.append({"event": event, "payload": payload}))

    pnl = PnLSnapshot(portfolio_high_watermark=100_000, portfolio_current_value=84_000)
    cb = CircuitBreaker(_cfg(), pnl)
    assert cb.is_active() is True
    assert len(calls) == 1
    assert calls[0]["event"] == "circuit_breaker_fired"
    assert calls[0]["payload"]["trigger"] == "drawdown"
    assert calls[0]["payload"]["drawdown_pct"] > 15.0


def test_circuit_breaker_daily_loss_calls_send_notification(monkeypatch) -> None:
    """Quand une perte quotidienne déclenche le CB, send_notification doit être appelé."""
    import risk_management.circuit_breaker as cb_mod

    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(cb_mod, "_try_send_alert", lambda event, payload: calls.append({"event": event, "payload": payload}))

    pnl = PnLSnapshot(daily_pnl=-5_500)
    cb = CircuitBreaker(_cfg(), pnl)
    assert cb.is_active() is True
    assert len(calls) == 1
    assert calls[0]["event"] == "circuit_breaker_fired"
    assert calls[0]["payload"]["trigger"] == "daily_loss"


def test_circuit_breaker_no_trigger_no_notification(monkeypatch) -> None:
    """Sans déclenchement, aucune notification ne doit être émise."""
    import risk_management.circuit_breaker as cb_mod

    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(cb_mod, "_try_send_alert", lambda event, payload: calls.append({"event": event}))

    cb = CircuitBreaker(_cfg())
    assert cb.is_active() is False
    assert calls == []

