"""Calcul de la taille de position (ATR-based ou equal-weight fallback)."""
from __future__ import annotations

import logging
import math

from risk_management.config import RiskConfig
from risk_management.models import PriceInfo, SizingResult

LOGGER = logging.getLogger(__name__)


class PositionSizer:
    """Calcule le nombre de parts proposé pour un symbole."""

    def __init__(self, config: RiskConfig) -> None:
        self._cfg = config

    def compute(self, price_info: PriceInfo) -> SizingResult:
        """Retourne un *SizingResult* pour le symbole donné."""
        symbol = price_info.symbol
        price = price_info.last_close

        if price <= 0:
            LOGGER.warning("Prix <= 0 pour %s — rejet.", symbol)
            return SizingResult(symbol=symbol, proposed_shares=0, method="rejected")

        # --- ATR-based sizing ---
        if price_info.atr_20 is not None and price_info.atr_20 > 0:
            risk_budget = self._cfg.account_equity * self._cfg.risk_per_trade_pct
            risk_per_share = price_info.atr_20 * self._cfg.atr_stop_multiple
            shares = math.floor(risk_budget / risk_per_share)
            method = "atr"
        else:
            # equal-weight fallback
            weight = 1.0 / max(self._cfg.max_positions, 1)
            notional = self._cfg.account_equity * weight
            shares = math.floor(notional / price)
            method = "equal_weight"
            LOGGER.info("ATR indisponible pour %s — fallback equal-weight.", symbol)

        shares = max(shares, 0)

        # notional minimum
        if shares * price < self._cfg.min_position_notional:
            if price > 0:
                min_shares = math.ceil(self._cfg.min_position_notional / price)
                if min_shares <= shares or shares == 0:
                    shares = 0
                    LOGGER.info("Notional insuffisant pour %s — rejet.", symbol)
                    return SizingResult(symbol=symbol, proposed_shares=0, method="rejected")

        # au moins 1 share
        if shares < 1:
            LOGGER.info("Moins de 1 share pour %s — rejet.", symbol)
            return SizingResult(symbol=symbol, proposed_shares=0, method="rejected")

        return SizingResult(symbol=symbol, proposed_shares=shares, method=method)
