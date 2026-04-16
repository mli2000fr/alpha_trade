"""
common/utils.py
Utilitaires partagés pour le calendrier de marché US (NYSE).
Utilise pandas_market_calendars pour une précision complète (MLK, Good Friday, Thanksgiving, etc.).
"""
import logging
from datetime import date, timedelta
from functools import lru_cache
from typing import Optional

LOGGER = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_nyse_calendar():
    """
    Retourne le calendrier NYSE via pandas_market_calendars (mis en cache au niveau du processus).
    En cas d'indisponibilité de la librairie, retourne None et active un fallback weekday-only.
    """
    try:
        import pandas_market_calendars as mcal  # noqa: PLC0415
        return mcal.get_calendar("NYSE")
    except Exception:
        LOGGER.warning(
            "pandas_market_calendars indisponible: fallback weekday-only activé. "
            "Jours fériés US (MLK, Good Friday, Thanksgiving…) non couverts."
        )
        return None


def is_trading_day(d: date) -> bool:
    """Retourne True si le marché NYSE est ouvert ce jour (calendrier complet)."""
    cal = _get_nyse_calendar()
    if cal is None:
        return d.weekday() < 5
    return not cal.schedule(start_date=d, end_date=d).empty


def is_us_market_holiday(d: date) -> bool:
    """
    Compatibilité ascendante : retourne True si le marché est FERMÉ ce jour.
    Couvre maintenant tous les jours fériés NYSE via pandas_market_calendars.
    """
    return not is_trading_day(d)


def getLastDateMarche(ref_date: Optional[date] = None) -> date:
    """
    Retourne la dernière date où le marché US était ouvert.

    :param ref_date: date de référence (datetime.date ou None pour aujourd'hui)
    :return: datetime.date
    """
    if ref_date is None:
        ref_date = date.today()
    d = ref_date
    while True:
        d -= timedelta(days=1)
        if is_trading_day(d):
            return d
