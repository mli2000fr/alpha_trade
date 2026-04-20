"""
common/utils.py
Utilitaires partagés pour le calendrier de marché US (NYSE).
Utilise pandas_market_calendars pour une précision complète (MLK, Good Friday, Thanksgiving, etc.).
"""
import logging
import sys
from datetime import date, timedelta
from functools import lru_cache
from typing import Optional
from logging.handlers import RotatingFileHandler
from pathlib import Path
import yaml

LOGGER = logging.getLogger(__name__)
DEFAULT_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s -- %(message)s"


def _configure_utf8_stdio() -> None:
    """Force stdout/stderr en UTF-8 quand le runtime le permet.

    Important sur Windows quand le processus est lancé en arrière-plan ou via des pipes,
    sinon certains caractères Unicode (accents, flèches, emoji) peuvent casser le logging
    ou produire du texte illisible.
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _reset_root_logging_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass


def configure_root_logging(
    *,
    level: int = logging.INFO,
    log_path: str | None = None,
    fmt: str = DEFAULT_LOG_FORMAT,
    datefmt: str | None = None,
    max_bytes: int = 5_000_000,
    backup_count: int = 3,
) -> logging.Logger:
    """Configure le root logger du projet avec sortie stdout et fichier optionnel."""
    _configure_utf8_stdio()
    logger = logging.getLogger()
    logger.setLevel(level)
    _reset_root_logging_handlers(logger)

    formatter = logging.Formatter(fmt, datefmt=datefmt)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(level)
    stdout_handler.setFormatter(formatter)
    stdout_handler._alpha_trade_managed = True  # type: ignore[attr-defined]
    logger.addHandler(stdout_handler)

    if log_path:
        file_handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        file_handler._alpha_trade_managed = True  # type: ignore[attr-defined]
        logger.addHandler(file_handler)

    return logger


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
    Configure le root logger du projet sur stdout et ajoute un RotatingFileHandler.
    Format : %(asctime)s %(levelname)-8s %(name)s -- %(message)s
    """
    return configure_root_logging(
        level=logging.INFO,
        log_path=log_path,
        fmt=DEFAULT_LOG_FORMAT,
        max_bytes=max_bytes,
        backup_count=backup_count,
    )


def load_config(path: str = None) -> dict:
    """Charge la configuration centralisée YAML (config.yaml)."""
    config_path = Path(path) if path else Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
