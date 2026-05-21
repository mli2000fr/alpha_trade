"""Calendrier de marché US (NYSE) — extrait de ``common/utils.py`` (Phase 2.1).

S'appuie sur ``pandas_market_calendars`` pour précision complète (MLK, Good
Friday, Thanksgiving…). Fallback weekday-only si la dépendance est absente.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time as dt_time, timedelta, timezone
from functools import lru_cache
from typing import Optional
from zoneinfo import ZoneInfo

LOGGER = logging.getLogger(__name__)
MARKET_TZ = ZoneInfo("America/New_York")


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


def get_nyse_session_bounds(session_date: date) -> tuple[datetime, datetime]:
    """Retourne `(market_open_utc, market_close_utc)` pour une séance NYSE.

    - Utilise `pandas_market_calendars` si disponible pour respecter DST et les
      séances écourtées (early close).
    - Fallback : fenêtre RTH standard 09:30–16:00 America/New_York.
    """
    cal = _get_nyse_calendar()
    if cal is not None:
        try:
            schedule = cal.schedule(start_date=session_date, end_date=session_date)
        except Exception as exc:  # pragma: no cover - défensif
            LOGGER.warning(
                "Lecture des bornes NYSE a echoue (%s) pour %s | fallback timezone-aware.",
                exc,
                session_date,
            )
        else:
            if not schedule.empty:
                first_row = schedule.iloc[0]
                market_open = first_row["market_open"]
                market_close = first_row["market_close"]
                if hasattr(market_open, "to_pydatetime"):
                    market_open = market_open.to_pydatetime()
                if hasattr(market_close, "to_pydatetime"):
                    market_close = market_close.to_pydatetime()
                return market_open.astimezone(timezone.utc), market_close.astimezone(timezone.utc)

    market_open_local = datetime.combine(session_date, dt_time(9, 30), tzinfo=MARKET_TZ)
    market_close_local = datetime.combine(session_date, dt_time(16, 0), tzinfo=MARKET_TZ)
    return market_open_local.astimezone(timezone.utc), market_close_local.astimezone(timezone.utc)


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
    "get_nyse_session_bounds",
    "getLastDateMarche",
    "is_trading_day",
    "is_us_market_holiday",
    "nyse_session_dates",
]

