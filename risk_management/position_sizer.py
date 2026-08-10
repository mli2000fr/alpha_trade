"""Calcul de la taille de position (ATR-based strict)."""
from __future__ import annotations

import logging
import math

from common.quantity_utils import QUANTITY_EPSILON, format_share_quantity, normalize_share_quantity
from risk_management.config import RiskConfig
from risk_management.enums import SizingMethod
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
            return SizingResult(symbol=symbol, proposed_shares=0, method=SizingMethod.REJECTED_INVALID_PRICE)

        # --- ATR-based sizing strict ---
        if price_info.atr_20 is None or price_info.atr_20 <= 0:
            LOGGER.info("ATR indisponible pour %s — rejet explicite.", symbol)
            return SizingResult(symbol=symbol, proposed_shares=0, method=SizingMethod.REJECTED_ATR_MISSING)

        risk_budget = self._cfg.account_equity * self._cfg.risk_per_trade_pct * max(0.0, self._cfg.risk_multiplier)
        risk_per_share = price_info.atr_20 * self._cfg.atr_stop_multiple_for()
        if risk_per_share <= 0:
            return SizingResult(symbol=symbol, proposed_shares=0, method=SizingMethod.REJECTED_ATR_MISSING)
        raw_shares = risk_budget / risk_per_share
        if self._cfg.allow_fractional_shares:
            shares = normalize_share_quantity(max(raw_shares, 0.0))
        else:
            shares = float(math.floor(raw_shares))
        method = SizingMethod.ATR

        shares = max(shares, 0.0)

        # notional minimum (utilise le seuil `enforce_min_notional` du régime si défini)
        min_notional = self._cfg.effective_min_notional
        if shares * price < min_notional:
            method_rej = (
                SizingMethod.REJECTED_NOTIONAL_BELOW_ENFORCED
                if self._cfg.enforce_min_notional is not None
                else SizingMethod.REJECTED_NOTIONAL
            )
            LOGGER.info(
                "Notional insuffisant pour %s — rejet (shares=%s price=%.2f notional=%.2f min=%.2f).",
                symbol, format_share_quantity(shares), price, shares * price, min_notional,
            )
            return SizingResult(symbol=symbol, proposed_shares=0, method=method_rej)

        minimum_viable_shares = QUANTITY_EPSILON if self._cfg.allow_fractional_shares else 1.0
        if shares < minimum_viable_shares:
            LOGGER.info("Quantité insuffisante pour %s — rejet (shares=%s).", symbol, format_share_quantity(shares))
            return SizingResult(symbol=symbol, proposed_shares=0, method=SizingMethod.REJECTED_ZERO_SHARES)

        return SizingResult(symbol=symbol, proposed_shares=shares, method=method)
