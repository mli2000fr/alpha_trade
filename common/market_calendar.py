"""Calendrier de marché US (NYSE) — extrait de ``common/utils.py`` (Phase 2.1).

S'appuie sur ``pandas_market_calendars`` pour précision complète (MLK, Good
Friday, Thanksgiving…). Fallback weekday-only si la dépendance est absente.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from functools import lru_cache
from typing import Optional

LOGGER = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_nyse_calendar():
    try:
        import pandas_market_calendars as mcal  # noqa: PLC0415
        return mcal.get_calendar("NYSE")
    except Exception:
        LOGGER.warning(
            "pandas_market_calendars indisponible: fallback weekday-only active. "
            "Jours feries US (MLK, Good Friday, Thanksgiving...) non couverts."
        )
        return None


def is_trading_day(d: date) -> bool:
    """True si le marché NYSE est ouvert ce jour."""
    cal = _get_nyse_calendar()
    if cal is None:
        return d.weekday() < 5
    return not cal.schedule(start_date=d, end_date=d).empty


def is_us_market_holiday(d: date) -> bool:
    """Compatibilité ascendante : True si le marché est FERMÉ ce jour."""
    return not is_trading_day(d)


def getLastDateMarche(ref_date: Optional[date] = None) -> date:
    """Retourne la dernière date où le marché US était ouvert."""
    if ref_date is None:
        ref_date = date.today()
    d = ref_date
    while True:
        d -= timedelta(days=1)
        if is_trading_day(d):
            return d


__all__ = [
    "getLastDateMarche",
    "is_trading_day",
    "is_us_market_holiday",
]

