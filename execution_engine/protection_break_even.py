"""Logique métier pure : break-even auto + EOD review (Axe F du plan).

Ce module fournit deux fonctions pures testables sans broker / DB :

* :func:`should_promote_to_break_even` — vrai si le profit latent dépasse
  ``break_even_after_atr_multiple × ATR × shares``.
* :func:`compute_break_even_stop_price` — retourne le nouveau stop = entry_price.
* :func:`is_eod_review_window` — vrai si l'heure courante (US/Eastern)
  est >= ``eod_check_time_est`` (HH:MM).

L'intégration concrète dans ``execution_engine.protection_watcher`` se limite
à appeler ces helpers + ``broker_adapter.replace_stop_order``.
"""
from __future__ import annotations

from datetime import datetime, time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from execution_engine.config import TrailingStopConfig


def should_promote_to_break_even(
    *,
    avg_fill_price: float,
    current_price: float,
    atr_value: float | None,
    shares: float,
    cfg: "TrailingStopConfig",
) -> bool:
    """True si position en profit > break_even_after_atr_multiple × ATR × shares."""
    if not cfg.enabled or shares <= 0 or avg_fill_price <= 0:
        return False
    if atr_value is None or atr_value <= 0:
        return False
    threshold_per_share = float(cfg.break_even_after_atr_multiple) * float(atr_value)
    profit_per_share = float(current_price) - float(avg_fill_price)
    return profit_per_share >= threshold_per_share


def compute_break_even_stop_price(avg_fill_price: float) -> float:
    """Stop au prix d'entrée moyen (break-even)."""
    return round(float(avg_fill_price), 2)


def _parse_hhmm(s: str) -> time:
    parts = s.split(":")
    if len(parts) != 2:
        raise ValueError(f"format HH:MM attendu, reçu {s!r}")
    return time(hour=int(parts[0]), minute=int(parts[1]))


def is_eod_review_window(
    *,
    now_eastern: datetime,
    cfg: "TrailingStopConfig",
) -> bool:
    """True si ``now_eastern`` >= ``eod_check_time_est`` (HH:MM)."""
    if not cfg.enabled:
        return False
    target = _parse_hhmm(cfg.eod_check_time_est)
    return now_eastern.timetz().replace(tzinfo=None) >= target


__all__ = [
    "should_promote_to_break_even",
    "compute_break_even_stop_price",
    "is_eod_review_window",
]

