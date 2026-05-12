"""Earnings Shield (J-2 / J+2) + Buyback Blackout (J-14).

Lecture best-effort de ``stock_earnings_calendar`` via SQLAlchemy. Si la table
n'est pas accessible (CI sans DB), retourne des mappings vides — fallback
neutre, jamais bloquant.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable, Mapping

from service.market.config import BuybackBlackoutConfig, EarningsShieldConfig

LOGGER = logging.getLogger(__name__)


EarningsLookup = Callable[[date, int, int], dict[str, date]]
"""Signature d'un loader earnings : ``(trade_date, lookback, lookahead) -> {symbol: earnings_date}``."""


@dataclass(frozen=True, slots=True)
class EarningsShieldResult:
    shielded: dict[str, str]              # {symbol: 'strict_block' | 'negative_score'}
    buyback_blackout: dict[str, float]    # {symbol: ml_multiplier}
    negative_score_value: float


def default_db_lookup(trade_date: date, lookback_days: int, lookahead_days: int) -> dict[str, date]:
    """Lecture par défaut depuis ``stock_earnings_calendar`` via SQLAlchemy.

    Retourne ``{}`` en cas d'erreur (table absente, pas de connexion, etc.).
    """
    try:
        from sqlalchemy import text
        from database.connection import get_sqlalchemy_engine

        eng = get_sqlalchemy_engine()
        start = trade_date - timedelta(days=lookback_days)
        end = trade_date + timedelta(days=lookahead_days)
        with eng.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT symbol, report_date FROM stock_earnings_calendar "
                    "WHERE report_date BETWEEN :start AND :end"
                ),
                {"start": start, "end": end},
            ).fetchall()
        out: dict[str, date] = {}
        for row in rows:
            sym = row[0]
            ed = row[1]
            if hasattr(ed, "date"):
                ed = ed.date()
            out[str(sym).upper()] = ed
        return out
    except Exception as exc:  # pragma: no cover - depends on DB availability
        LOGGER.debug("earnings_shield: DB lookup unavailable (%s) — fallback empty.", exc)
        return {}


def compute_earnings_shield(
    trade_date: date,
    *,
    shield_cfg: EarningsShieldConfig,
    blackout_cfg: BuybackBlackoutConfig,
    lookup: EarningsLookup | None = None,
) -> EarningsShieldResult:
    """Calcule les symboles bouclés (J-2/J+2) et les blackouts buyback."""
    if not shield_cfg.enabled and not blackout_cfg.enabled:
        return EarningsShieldResult({}, {}, shield_cfg.negative_score_value)

    lookup = lookup or default_db_lookup
    lookback = max(shield_cfg.days_after, 0)
    lookahead = max(
        shield_cfg.days_before if shield_cfg.enabled else 0,
        blackout_cfg.days_before_earnings if blackout_cfg.enabled else 0,
    )
    upcoming = lookup(trade_date, lookback, lookahead)

    shielded: dict[str, str] = {}
    blackout: dict[str, float] = {}

    for symbol, ed in upcoming.items():
        delta_days = (ed - trade_date).days

        if shield_cfg.enabled:
            in_window = (-shield_cfg.days_after) <= delta_days <= shield_cfg.days_before
            if in_window:
                shielded[symbol] = (
                    "strict_block" if shield_cfg.mode == "strict_block" else "negative_score"
                )
        if blackout_cfg.enabled and 0 <= delta_days <= blackout_cfg.days_before_earnings:
            # plus on s'approche, plus le malus s'applique : on garde un seul multiplicateur
            blackout[symbol] = blackout_cfg.ml_score_multiplier

    return EarningsShieldResult(
        shielded=shielded,
        buyback_blackout=blackout,
        negative_score_value=shield_cfg.negative_score_value,
    )


__all__ = [
    "EarningsLookup",
    "EarningsShieldResult",
    "compute_earnings_shield",
    "default_db_lookup",
]

