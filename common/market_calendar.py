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


def nyse_session_dates(start: date, end: date) -> list[date]:
    """Retourne la liste ordonnée des jours ouvrés NYSE dans ``[start, end]``.

    - Source de vérité : ``pandas_market_calendars`` (calendrier NYSE).
    - Fallback : énumération weekday-only si la dépendance est absente, avec un
      log ``WARNING`` (jours fériés US non couverts).
    - Idempotent / pure : aucun effet de bord.
    """
    if end < start:
        return []
    cal = _get_nyse_calendar()
    if cal is not None:
        try:
            schedule = cal.schedule(start_date=start, end_date=end)
        except Exception as exc:  # pragma: no cover - défensif
            LOGGER.warning(
                "pandas_market_calendars schedule a echoue (%s) | fallback weekday-only.",
                exc,
            )
        else:
            return [d.date() if hasattr(d, "date") else d for d in schedule.index.tolist()]
    # Fallback weekday-only.
    LOGGER.warning(
        "Calendrier NYSE en mode fallback weekday-only sur [%s, %s] (jours feries US non filtres).",
        start,
        end,
    )
    out: list[date] = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            out.append(cur)
        cur += timedelta(days=1)
    return out


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
    "nyse_session_dates",
]

