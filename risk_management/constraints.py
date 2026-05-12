"""Contraintes de risque appliquées lors de la construction du portefeuille."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from risk_management.config import RiskConfig

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class PortfolioState:
    """État courant du portefeuille en construction."""
    total_notional: float = 0.0
    position_count: int = 0
    sector_notional: dict[str, float] | None = None
    sector_ticker_count: dict[str, int] | None = None

    def __post_init__(self) -> None:
        if self.sector_notional is None:
            self.sector_notional = {}
        if self.sector_ticker_count is None:
            self.sector_ticker_count = {}


class ConstraintChecker:
    """Vérifie les contraintes de risque et retourne les shares autorisées."""

    def __init__(self, config: RiskConfig) -> None:
        self._cfg = config

    def check(
        self,
        symbol: str,
        sector: str,
        proposed_shares: int,
        price: float,
        state: PortfolioState,
    ) -> tuple[int, str]:
        """Retourne (approved_shares, reason).  reason == 'OK' si aucune réduction."""
        equity = self._cfg.account_equity

        # max positions (effectif — peut être réduit par le régime)
        if state.position_count >= self._cfg.effective_max_positions:
            return 0, "max_positions atteint"

        # max tickers / secteur (en complément de max_sector_weight)
        if self._cfg.max_tickers_per_sector is not None:
            assert state.sector_ticker_count is not None
            current_n = state.sector_ticker_count.get(sector, 0)
            if current_n >= self._cfg.max_tickers_per_sector:
                return 0, "max_tickers_per_sector atteint"

        notional = proposed_shares * price

        # max gross exposure
        if (state.total_notional + notional) / equity > self._cfg.max_gross_exposure:
            max_notional = equity * self._cfg.max_gross_exposure - state.total_notional
            if max_notional <= 0:
                return 0, "max_gross_exposure atteint"
            proposed_shares = int(max_notional // price)
            notional = proposed_shares * price
            if proposed_shares < 1:
                return 0, "max_gross_exposure atteint"

        # max position weight
        max_pos_notional = equity * self._cfg.max_position_weight
        if notional > max_pos_notional:
            proposed_shares = int(max_pos_notional // price)
            notional = proposed_shares * price
            if proposed_shares < 1:
                return 0, "max_position_weight atteint"

        # max sector weight
        assert state.sector_notional is not None
        current_sector = state.sector_notional.get(sector, 0.0)
        max_sector_notional = equity * self._cfg.max_sector_weight
        if (current_sector + notional) > max_sector_notional:
            remaining = max_sector_notional - current_sector
            if remaining <= 0:
                return 0, "max_sector_weight atteint"
            proposed_shares = int(remaining // price)
            notional = proposed_shares * price
            if proposed_shares < 1:
                return 0, "max_sector_weight atteint"

        # min position notional (effectif — `enforce_min_notional` du régime prioritaire)
        if notional < self._cfg.effective_min_notional:
            return 0, "min_position_notional non atteint"

        return proposed_shares, "OK"
