"""Calcul de la taille de position (ATR-based strict)."""
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
        """Retourne un *SizingResult* pour le symbole donné.

        Sprint S3 / A-010 : la télémétrie est cruciale pour diagnostiquer
        pourquoi un opérateur (typiquement petit compte) ne reçoit aucun
        ordre. La valeur de ``method`` distingue désormais les causes :
        ``"rejected_invalid_price"``, ``"rejected_atr_missing"``,
        ``"rejected_notional"`` et ``"rejected_zero_shares"`` —
        agrégées dans ``run_summary`` côté CLI.
        """
        symbol = price_info.symbol
        price = price_info.last_close

        if price <= 0:
            LOGGER.warning("Prix <= 0 pour %s — rejet.", symbol)
            return SizingResult(symbol=symbol, proposed_shares=0, method="rejected_invalid_price")

        # --- ATR-based sizing strict ---
        if price_info.atr_20 is None or price_info.atr_20 <= 0:
            LOGGER.info("ATR indisponible pour %s — rejet explicite.", symbol)
            return SizingResult(symbol=symbol, proposed_shares=0, method="rejected_atr_missing")

        risk_budget = self._cfg.account_equity * self._cfg.risk_per_trade_pct * max(0.0, self._cfg.risk_multiplier)
        risk_per_share = price_info.atr_20 * self._cfg.atr_stop_multiple
        if risk_per_share <= 0:
            return SizingResult(symbol=symbol, proposed_shares=0, method="rejected_atr_missing")
        shares = math.floor(risk_budget / risk_per_share)
        method = "atr"

        shares = max(shares, 0)

        # notional minimum (utilise le seuil `enforce_min_notional` du régime si défini)
        min_notional = self._cfg.effective_min_notional
        if shares * price < min_notional:
            method_rej = (
                "rejected_notional_below_enforced"
                if self._cfg.enforce_min_notional is not None
                else "rejected_notional"
            )
            LOGGER.info(
                "Notional insuffisant pour %s — rejet (shares=%d price=%.2f notional=%.2f min=%.2f).",
                symbol, shares, price, shares * price, min_notional,
            )
            return SizingResult(symbol=symbol, proposed_shares=0, method=method_rej)

        # au moins 1 share
        if shares < 1:
            LOGGER.info("Moins de 1 share pour %s — rejet.", symbol)
            return SizingResult(symbol=symbol, proposed_shares=0, method="rejected_zero_shares")

        return SizingResult(symbol=symbol, proposed_shares=shares, method=method)
