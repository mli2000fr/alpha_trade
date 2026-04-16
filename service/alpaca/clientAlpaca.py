import logging
import os
import time
from typing import Any, Optional

import dateutil.parser
import requests

DEFAULT_START_DATE = "2010-01-01T00:00:00Z"
DEFAULT_TIMEOUT_SECONDS = 10
MAX_TIMEOUT_RETRIES = 10
TIMEOUT_BACKOFF_SECONDS = 10
ALPACA_ASSETS_ENDPOINT = "https://paper-api.alpaca.markets/v2/assets"
ALPACA_BARS_ENDPOINT_TEMPLATE = "https://data.alpaca.markets/v2/stocks/{symbol}/bars"

LOGGER = logging.getLogger(__name__)


def get_alpaca_credentials() -> tuple[str, str]:
    """Récupère les credentials Alpaca depuis les variables d'environnement."""
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        raise RuntimeError("ALPACA_API_KEY ou ALPACA_SECRET_KEY non définis dans les variables d'environnement système.")
    return api_key, secret_key


def _build_headers() -> dict[str, str]:
    api_key, secret_key = get_alpaca_credentials()
    return {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key,
    }


def _normalize_start_date(start_date: Optional[str]) -> str:
    if not start_date:
        return DEFAULT_START_DATE

    try:
        start_dt = dateutil.parser.isoparse(start_date)
    except (TypeError, ValueError):
        return start_date

    return start_dt.strftime("%Y-%m-%d")


def _filter_bars_after_start_date(bars: list[dict[str, Any]], start_date: Optional[str]) -> list[dict[str, Any]]:
    if not start_date:
        return bars

    try:
        start_dt = dateutil.parser.isoparse(start_date)
    except (TypeError, ValueError):
        return bars

    return [bar for bar in bars if dateutil.parser.isoparse(bar["t"]) > start_dt]


def fetch_alpaca_assets(session: Optional[requests.Session] = None) -> list[dict[str, Any]]:
    owned_session = session is None
    client = session or requests.Session()
    try:
        response = client.get(ALPACA_ASSETS_ENDPOINT, headers=_build_headers(), timeout=DEFAULT_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    finally:
        if owned_session:
            client.close()


def fetch_bars(
    symbol: str,
    timeframe: str,
    start_date: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> list[dict[str, Any]]:
    """Récupère les bars Alpaca pour un symbole et gère la pagination et les timeouts."""
    owned_session = session is None
    client = session or requests.Session()
    endpoint = ALPACA_BARS_ENDPOINT_TEMPLATE.format(symbol=symbol)
    params: dict[str, Any] = {
        "timeframe": timeframe,
        # adjustment=all : Alpaca retourne des prix OHLCV entièrement ajustés
        # (splits + dividendes). En conséquence, close_price = adj_close = prix ajusté.
        # Si le raw close est nécessaire, utiliser adjustment=raw dans un appel séparé.
        "adjustment": "all",
        # RTH uniquement (09:30–16:00 EST) : exclure les données pre/post-market.
        "feed": "sip",
        "extended_hours": "false",
        "limit": 5000,
        "start": _normalize_start_date(start_date),
    }

    all_bars: list[dict[str, Any]] = []
    next_token: Optional[str] = None

    try:
        while True:
            if next_token:
                params["page_token"] = next_token
            else:
                params.pop("page_token", None)

            timeout_attempts = 0
            while True:
                try:
                    response = client.get(
                        endpoint,
                        headers=_build_headers(),
                        params=params,
                        timeout=DEFAULT_TIMEOUT_SECONDS,
                    )
                    response.raise_for_status()
                    data = response.json()
                    bars = data.get("bars") or []
                    bars = _filter_bars_after_start_date(bars, start_date)
                    all_bars.extend(bars)
                    next_token = data.get("next_page_token")
                    LOGGER.info(
                        "Alpaca bars | symbol=%s start=%s next_token=%s count=%s",
                        symbol,
                        params["start"],
                        next_token,
                        len(bars),
                    )
                    break
                except requests.exceptions.Timeout:
                    timeout_attempts += 1
                    LOGGER.warning(
                        "Timeout Alpaca | symbol=%s tentative=%s/%s",
                        symbol,
                        timeout_attempts,
                        MAX_TIMEOUT_RETRIES,
                    )
                    if timeout_attempts >= MAX_TIMEOUT_RETRIES:
                        LOGGER.error("Abandon après %s timeouts pour %s.", MAX_TIMEOUT_RETRIES, symbol)
                        return all_bars
                    time.sleep(TIMEOUT_BACKOFF_SECONDS)
                except requests.exceptions.HTTPError as exc:
                    if getattr(exc.response, "status_code", None) == 404:
                        LOGGER.warning("Alpaca retourne 404 pour %s : aucun bar disponible.", symbol)
                        return all_bars
                    raise

            if not next_token:
                return all_bars
    finally:
        if owned_session:
            client.close()
