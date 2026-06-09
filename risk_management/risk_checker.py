"""Implémentation concrète de core.interfaces.RiskChecker."""
from __future__ import annotations

import logging

from common.quantity_utils import format_share_quantity
from risk_management.circuit_breaker import CircuitBreaker, PnLSnapshot
from risk_management.config import RiskConfig
from risk_management.constraints import ConstraintChecker, PortfolioState
from risk_management.enums import DecisionReasonCode

LOGGER = logging.getLogger(__name__)


class RiskCheckerImpl:
    """Implémente le Protocol ``RiskChecker`` de core/interfaces.py."""

    def __init__(
        self,
        config: RiskConfig,
        state: PortfolioState | None = None,
        pnl: PnLSnapshot | None = None,
        sector_map: dict[str, str] | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self._cfg = config
        self._state = state or PortfolioState()
        self._cb = circuit_breaker or CircuitBreaker(config, pnl)
        self._constraints = ConstraintChecker(config)
        self._sector_map: dict[str, str] = sector_map or {}
        self._last_decision_reason = "OK"
        self._last_decision_reason_code = DecisionReasonCode.OK

    # --- Protocol RiskChecker -------------------------------------------
    def check_position_size(self, symbol: str, proposed_shares: float, price: float) -> float:
        """Retourne le nombre de parts autorisé (<= proposed_shares)."""
        if self._cb.is_active():
            LOGGER.warning("Circuit breaker actif — position rejetee pour %s.", symbol)
            self._last_decision_reason = "circuit breaker actif"
            self._last_decision_reason_code = DecisionReasonCode.CIRCUIT_BREAKER_ACTIVE
            return 0.0
        sector = self._sector_map.get(symbol, "UNKNOWN")
        approved, reason = self._constraints.check(
            symbol=symbol,
            sector=sector,
            proposed_shares=proposed_shares,
            price=price,
            state=self._state,
        )
        self._last_decision_reason = reason
        self._last_decision_reason_code = self._constraints.reason_to_code(reason)
        if approved < proposed_shares and reason != "OK":
            LOGGER.info(
                "Position reduite pour %s: %s -> %s (%s)",
                symbol,
                format_share_quantity(proposed_shares),
                format_share_quantity(approved),
                reason,
            )
        else:
            LOGGER.info(
                "Position approved pour %s: %s -> %s ---------------",
                symbol,
                format_share_quantity(proposed_shares),
                format_share_quantity(approved),
            )
        return float(approved)

    def is_circuit_breaker_active(self) -> bool:
        return self._cb.is_active()

    def get_last_decision_reason(self) -> str:
        return self._last_decision_reason

    def get_last_decision_reason_code(self) -> DecisionReasonCode:
        return self._last_decision_reason_code

    # --- helpers pour portfolio_builder ----------------------------------
    def accept(self, symbol: str, sector: str, shares: float, price: float) -> None:
        """Enregistre une position acceptée dans l'état courant."""
        notional = shares * price
        self._state.position_count += 1
        self._state.total_notional += notional
        assert self._state.sector_notional is not None
        self._state.sector_notional[sector] = self._state.sector_notional.get(sector, 0.0) + notional
        assert self._state.sector_ticker_count is not None
        self._state.sector_ticker_count[sector] = self._state.sector_ticker_count.get(sector, 0) + 1
