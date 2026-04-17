"""Circuit breaker — coupe les allocations si drawdown/perte excessive."""
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
            return True
        return False
