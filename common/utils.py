"""
common/utils.py
Utilitaires partagés pour le calendrier de marché US (NYSE).
Utilise pandas_market_calendars pour une précision complète (MLK, Good Friday, Thanksgiving, etc.).
"""
import logging
from datetime import date, timedelta
from functools import lru_cache
from typing import Optional
from logging.handlers import RotatingFileHandler
from pathlib import Path
import yaml

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
            "pandas_market_calendars indisponible: fallback weekday-only active. "
            "Jours feries US (MLK, Good Friday, Thanksgiving…) non couverts."
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


def setup_logging_with_file_handler(log_path: str = "alpha_trade.log", max_bytes: int = 5_000_000, backup_count: int = 3):
    """
    Ajoute un RotatingFileHandler au root logger, en plus du stdout.
    Format : %(asctime)s %(levelname)-8s %(name)s -- %(message)s
    """
    logger = logging.getLogger()
    formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s -- %(message)s")
    file_handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    # Évite les doublons si déjà ajouté
    if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        logger.addHandler(file_handler)


def load_config(path: str = None) -> dict:
    """Charge la configuration centralisée YAML (config.yaml)."""
    config_path = Path(path) if path else Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
