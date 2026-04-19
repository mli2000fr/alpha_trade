"""Implémentation concrète de core.interfaces.RiskChecker."""
from __future__ import annotations

import logging

from risk_management.circuit_breaker import CircuitBreaker, PnLSnapshot
from risk_management.config import RiskConfig
from risk_management.constraints import ConstraintChecker, PortfolioState

LOGGER = logging.getLogger(__name__)


class RiskCheckerImpl:
    """Implémente le Protocol ``RiskChecker`` de core/interfaces.py."""

    def __init__(
        self,
        config: RiskConfig,
        state: PortfolioState | None = None,
        pnl: PnLSnapshot | None = None,
        sector_map: dict[str, str] | None = None,
    ) -> None:
        self._cfg = config
        self._state = state or PortfolioState()
        self._cb = CircuitBreaker(config, pnl)
        self._constraints = ConstraintChecker(config)
        self._sector_map: dict[str, str] = sector_map or {}

    # --- Protocol RiskChecker -------------------------------------------
    def check_position_size(self, symbol: str, proposed_shares: float, price: float) -> float:
        """Retourne le nombre de parts autorisé (<= proposed_shares)."""
        if self._cb.is_active():
            LOGGER.warning("Circuit breaker actif — position rejetee pour %s.", symbol)
            return 0.0
        sector = self._sector_map.get(symbol, "UNKNOWN")
        approved, reason = self._constraints.check(
            symbol=symbol,
            sector=sector,
            proposed_shares=int(proposed_shares),
            price=price,
            state=self._state,
        )
        if approved < proposed_shares and reason != "OK":
            LOGGER.info("Position reduite pour %s: %s -> %s (%s)", symbol, int(proposed_shares), approved, reason)
        return float(approved)

    def is_circuit_breaker_active(self) -> bool:
        return self._cb.is_active()

    # --- helpers pour portfolio_builder ----------------------------------
    def accept(self, symbol: str, sector: str, shares: int, price: float) -> None:
        """Enregistre une position acceptée dans l'état courant."""
        notional = shares * price
        self._state.position_count += 1
        self._state.total_notional += notional
        assert self._state.sector_notional is not None
        self._state.sector_notional[sector] = self._state.sector_notional.get(sector, 0.0) + notional
