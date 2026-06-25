"""Kelly sizer combiné ATR — V2."""
from __future__ import annotations

import logging
import math

from risk_management.config import RiskConfig
from risk_management.enums import SizingMethod
from risk_management.models import PriceInfo, SizingResult
from risk_management.position_sizer import PositionSizer

LOGGER = logging.getLogger(__name__)


class KellySizer:
    """Sizing Kelly fractional avec cap ATR et fallback V1."""

    def __init__(self, config: RiskConfig) -> None:
        self._cfg = config
        self._fallback = PositionSizer(config)

    def compute(
        self,
        price_info: PriceInfo,
        predicted_proba: float | None,
        historical_win_rate: float | None,
    ) -> SizingResult:
        """Calcule la taille de position via Kelly + ATR cap."""
        cfg = self._cfg
        symbol = price_info.symbol
        price = price_info.last_close

        if price <= 0:
            return SizingResult(symbol=symbol, proposed_shares=0, method=SizingMethod.REJECTED_INVALID_PRICE)

        # 1. Probabilité effective
        pp = predicted_proba if predicted_proba is not None else cfg.default_win_rate
        wr = historical_win_rate if historical_win_rate is not None else cfg.default_win_rate
        p_eff = cfg.prediction_confidence_weight * pp + cfg.historical_win_rate_weight * wr
        p_eff = max(0.001, min(p_eff, 0.999))

        # 2. Si p_eff trop faible → fallback
        if p_eff < cfg.min_effective_probability:
            LOGGER.info("p_eff=%.4f < seuil pour %s — fallback V1.", p_eff, symbol)
            return self._fallback.compute(price_info)

        # 3. Kelly
        q = 1.0 - p_eff
        b = cfg.assumed_payoff_ratio
        raw_kelly = p_eff - q / b
        fractional_kelly = max(0.0, raw_kelly) * cfg.kelly_fraction_multiplier
        # ── P0 (2026-06-25) : plafond de sécurité Kelly ──
        fractional_kelly = min(fractional_kelly, cfg.max_kelly_fraction)
        fractional_kelly = min(fractional_kelly, cfg.max_position_weight)

        # 4. Si kelly <= 0 → fallback
        if fractional_kelly <= 0:
            LOGGER.info("Kelly <= 0 pour %s — fallback V1.", symbol)
            return self._fallback.compute(price_info)

        # 5. Shares Kelly
        kelly_notional = cfg.account_equity * fractional_kelly
        kelly_shares = math.floor(kelly_notional / price)

        # 6. Cap ATR
        if price_info.atr_20 is not None and price_info.atr_20 > 0:
            risk_budget = cfg.account_equity * cfg.risk_per_trade_pct * max(0.0, cfg.risk_multiplier)
            risk_per_share = price_info.atr_20 * cfg.atr_stop_multiple
            atr_shares_cap = math.floor(risk_budget / risk_per_share)
            proposed = min(kelly_shares, atr_shares_cap)
            method = SizingMethod.KELLY_ATR
        else:
            # 7. Pas d'ATR
            proposed = kelly_shares
            method = SizingMethod.KELLY_ONLY

        proposed = max(proposed, 0)

        # 8. Notional minimum
        min_notional = cfg.effective_min_notional
        if proposed * price < min_notional:
            LOGGER.info("Notional Kelly insuffisant pour %s — rejet.", symbol)
            method_rej = (
                SizingMethod.REJECTED_NOTIONAL_BELOW_ENFORCED
                if cfg.enforce_min_notional is not None
                else SizingMethod.REJECTED_NOTIONAL
            )
            return SizingResult(symbol=symbol, proposed_shares=0, method=method_rej)

        if proposed < 1:
            return SizingResult(symbol=symbol, proposed_shares=0, method=SizingMethod.REJECTED_ZERO_SHARES)

        return SizingResult(symbol=symbol, proposed_shares=proposed, method=method)

