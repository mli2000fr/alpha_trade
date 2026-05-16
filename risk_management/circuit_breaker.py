"""Circuit breaker — coupe les allocations si drawdown/perte excessive.

Sprint S3 / A-013 : ``is_active()`` émet désormais une notification email
(best-effort, silencieuse si le notificateur n'est pas configuré) quand un
circuit breaker se déclenche. La dépendance vers ``ihm.services.email_notifier``
est lazily importée pour éviter de polluer les imports du moteur risk.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from risk_management.config import RiskConfig

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class PnLSnapshot:
    """Snapshot PnL injecté de l'extérieur (ou valeurs par défaut)."""
    portfolio_high_watermark: float | None = None
    portfolio_current_value: float | None = None
    daily_pnl: float | None = None


def _try_send_alert(event: str, payload: dict) -> None:
    """Tente d'envoyer une notification email — silencieux si désactivé."""
    try:
        from ihm.services.email_notifier import send_notification
        send_notification(event=event, payload=payload)
    except Exception:  # noqa: BLE001 — alerting best-effort, ne bloque jamais le trading
        LOGGER.debug("Notification email circuit_breaker indisponible.", exc_info=True)


class CircuitBreaker:
    """Évalue si le trading doit être suspendu."""

    def __init__(self, config: RiskConfig, pnl: PnLSnapshot | None = None) -> None:
        self._cfg = config
        self._pnl = pnl or PnLSnapshot()

    def is_active(self) -> bool:
        """Retourne True si un circuit breaker est déclenché."""
        if self._check_drawdown():
            return True
        if self._check_daily_loss():
            return True
        return False

    # ------------------------------------------------------------------
    def _check_drawdown(self) -> bool:
        hwm = self._pnl.portfolio_high_watermark
        cur = self._pnl.portfolio_current_value
        if hwm is None or cur is None or hwm <= 0:
            return False
        dd = (hwm - cur) / hwm
        if dd >= self._cfg.max_portfolio_drawdown_pct:
            LOGGER.warning("Circuit breaker drawdown: %.2f%% >= seuil %.2f%%", dd * 100, self._cfg.max_portfolio_drawdown_pct * 100)
            # Sprint S3 / A-013 — alerte email best-effort.
            _try_send_alert(
                event="circuit_breaker_fired",
                payload={
                    "trigger": "drawdown",
                    "drawdown_pct": round(dd * 100, 2),
                    "threshold_pct": round(self._cfg.max_portfolio_drawdown_pct * 100, 2),
                    "portfolio_high_watermark": hwm,
                    "portfolio_current_value": cur,
                },
            )
            return True
        return False

    def _check_daily_loss(self) -> bool:
        daily = self._pnl.daily_pnl
        if daily is None:
            return False
        equity = self._cfg.account_equity
        if equity <= 0:
            return False
        loss_pct = abs(min(daily, 0.0)) / equity
        if loss_pct >= self._cfg.max_daily_loss_pct:
            LOGGER.warning("Circuit breaker daily loss: %.2f%% >= seuil %.2f%%", loss_pct * 100, self._cfg.max_daily_loss_pct * 100)
            # Sprint S3 / A-013 — alerte email best-effort.
            _try_send_alert(
                event="circuit_breaker_fired",
                payload={
                    "trigger": "daily_loss",
                    "daily_loss_pct": round(loss_pct * 100, 2),
                    "threshold_pct": round(self._cfg.max_daily_loss_pct * 100, 2),
                    "daily_pnl": daily,
                    "account_equity": equity,
                },
            )
            return True
        return False
