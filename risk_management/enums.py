"""Référentiel canonique des valeurs sérialisées du module `risk_management`.

Les valeurs restent volontairement identiques aux chaînes historiques déjà
persistées en base et consommées par l'IHM/backtesting.
"""
from __future__ import annotations

from enum import StrEnum


class Decision(StrEnum):
    ACCEPTED = "ACCEPTED"
    REDUCED = "REDUCED"
    REJECTED = "REJECTED"


class SizingMethod(StrEnum):
    UNKNOWN = "unknown"
    ATR = "atr"
    KELLY_ATR = "kelly_atr"
    KELLY_ONLY = "kelly_only"
    REJECTED_INVALID_PRICE = "rejected_invalid_price"
    REJECTED_ATR_MISSING = "rejected_atr_missing"
    REJECTED_NOTIONAL = "rejected_notional"
    REJECTED_NOTIONAL_BELOW_ENFORCED = "rejected_notional_below_enforced"
    REJECTED_ZERO_SHARES = "rejected_zero_shares"


class DecisionReasonCode(StrEnum):
    OK = "ok"
    UNKNOWN = "unknown"
    MISSING_PRICE = "missing_price"
    CORRELATION_FILTER = "correlation_filter"
    CIRCUIT_BREAKER_ACTIVE = "circuit_breaker_active"
    CONSTRAINT_UNKNOWN = "constraint_unknown"
    CONSTRAINT_MAX_POSITIONS = "constraint_max_positions"
    CONSTRAINT_MAX_TICKERS_PER_SECTOR = "constraint_max_tickers_per_sector"
    CONSTRAINT_MAX_GROSS_EXPOSURE = "constraint_max_gross_exposure"
    CONSTRAINT_MAX_POSITION_WEIGHT = "constraint_max_position_weight"
    CONSTRAINT_MAX_SECTOR_WEIGHT = "constraint_max_sector_weight"
    CONSTRAINT_MIN_POSITION_NOTIONAL = "constraint_min_position_notional"
    REJECTED_INVALID_PRICE = SizingMethod.REJECTED_INVALID_PRICE
    REJECTED_ATR_MISSING = SizingMethod.REJECTED_ATR_MISSING
    REJECTED_NOTIONAL = SizingMethod.REJECTED_NOTIONAL
    REJECTED_NOTIONAL_BELOW_ENFORCED = SizingMethod.REJECTED_NOTIONAL_BELOW_ENFORCED
    REJECTED_ZERO_SHARES = SizingMethod.REJECTED_ZERO_SHARES
    # Factor risk model (Priorité 3)
    FACTOR_CONSTRAINT_VIOLATION = "factor_constraint_violation"
    FACTOR_CORRELATION_FILTER = "factor_correlation_filter"
    # Liquidité dynamique (LiquiditeDynamique.md P1)
    CONSTRAINT_MAX_POSITION_PCT_OF_ADV = "constraint_max_position_pct_of_adv"


__all__ = [
    "Decision",
    "DecisionReasonCode",
    "SizingMethod",
]

