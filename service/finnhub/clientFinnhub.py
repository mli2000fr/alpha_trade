import logging
import os
import time
from typing import Any, Iterable, Optional, cast

import requests

DEFAULT_TIMEOUT_SECONDS = 10
MAX_TIMEOUT_RETRIES = 10
TIMEOUT_BACKOFF_SECONDS = 10
MAX_RATE_LIMIT_RETRIES = 3
RATE_LIMIT_BACKOFF_SECONDS = 60
MIN_REQUEST_INTERVAL_SECONDS = 1.1
FINNHUB_PROFILE_ENDPOINT = "https://finnhub.io/api/v1/stock/profile2"

LOGGER = logging.getLogger(__name__)


def get_finnhub_token() -> str:
    """Récupère le token Finnhub depuis les variables d'environnement."""
    api_key = os.getenv("FINNHUB_API_KEY") or os.getenv("CLE_FINNHUB")
    if not api_key:
        raise RuntimeError(
            "FINNHUB_API_KEY ou CLE_FINNHUB non défini dans les variables d'environnement système."
        )
    return api_key


def _normalize_symbol(symbol: str) -> str:
    normalized = (symbol or "").strip().upper()
    if not normalized:
        raise ValueError("symbol ne peut pas être vide.")
    return normalized


def _build_params(symbol: str) -> dict[str, str]:
    return {
        "symbol": _normalize_symbol(symbol),
        "token": get_finnhub_token(),
    }


def fetch_company_profile(symbol: str, session: Optional[requests.Session] = None) -> dict[str, Any]:
    """Récupère le profil société Finnhub pour un symbole."""
    owned_session = session is None
    client = session or requests.Session()
    params = _build_params(symbol)
    result: Optional[dict[str, Any]] = None

    timeout_attempts = 0
    rate_limit_attempts = 0

    try:
        while True:
            try:
                response = client.get(
                    FINNHUB_PROFILE_ENDPOINT,
                    params=params,
                    timeout=DEFAULT_TIMEOUT_SECONDS,
                )

                if response.status_code == 429:
                    rate_limit_attempts += 1
                    LOGGER.warning(
                        "Finnhub rate limit | symbol=%s tentative=%s/%s",
                        params["symbol"],
                        rate_limit_attempts,
                        MAX_RATE_LIMIT_RETRIES,
                    )
                    if rate_limit_attempts >= MAX_RATE_LIMIT_RETRIES:
                        raise RuntimeError(
                            f"Finnhub rate limit atteint pour {params['symbol']} après {MAX_RATE_LIMIT_RETRIES} tentatives."
                        )
                    time.sleep(RATE_LIMIT_BACKOFF_SECONDS)
                    continue

                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise RuntimeError(f"Réponse Finnhub invalide pour {params['symbol']}.")

                LOGGER.info(
                    "Finnhub profile | symbol=%s country=%s exchange=%s industry=%s",
                    params["symbol"],
                    data.get("country"),
                    data.get("exchange"),
                    data.get("finnhubIndustry"),
                )
                result = cast(dict[str, Any], data)
                break
            except requests.exceptions.Timeout:
                timeout_attempts += 1
                LOGGER.warning(
                    "Timeout Finnhub | symbol=%s tentative=%s/%s",
                    params["symbol"],
                    timeout_attempts,
                    MAX_TIMEOUT_RETRIES,
                )
                if timeout_attempts >= MAX_TIMEOUT_RETRIES:
                    raise RuntimeError(
                        f"Abandon après {MAX_TIMEOUT_RETRIES} timeouts Finnhub pour {params['symbol']}."
                    )
                time.sleep(TIMEOUT_BACKOFF_SECONDS)
    finally:
        if owned_session:
            client.close()

    if result is None:
        raise RuntimeError(f"Réponse Finnhub indisponible pour {params['symbol']}.")
    return result


def fetch_symbol_sector(symbol: str, session: Optional[requests.Session] = None) -> Optional[str]:
    """Récupère le secteur Finnhub (`finnhubIndustry`) d'un symbole."""
    profile = fetch_company_profile(symbol, session=session)
    sector = profile.get("finnhubIndustry")
    if not sector:
        LOGGER.warning("Secteur Finnhub absent pour %s.", _normalize_symbol(symbol))
        return None
    return str(sector)


def fetch_symbol_sector_record(symbol: str, session: Optional[requests.Session] = None) -> dict[str, Any]:
    """Retourne un enregistrement normalisé contenant le secteur d'un symbole."""
    normalized_symbol = _normalize_symbol(symbol)
    profile = fetch_company_profile(normalized_symbol, session=session)
    sector = profile.get("finnhubIndustry")
    return {
        "symbol": normalized_symbol,
        "sector": str(sector) if sector else None,
        "source": "Finnhub",
        "raw_profile": profile,
    }


def fetch_multiple_symbol_sector_records(
    symbols: Iterable[str],
    sleep_seconds: float = MIN_REQUEST_INTERVAL_SECONDS,
    session: Optional[requests.Session] = None,
) -> list[dict[str, Any]]:
    """Récupère les secteurs Finnhub pour plusieurs symboles en respectant le rate limiting."""
    if sleep_seconds < 0:
        raise ValueError("sleep_seconds doit être supérieur ou égal à 0.")

    symbol_list = list(symbols)
    owned_session = session is None
    client = session or requests.Session()
    records: list[dict[str, Any]] = []

    try:
        for index, symbol in enumerate(symbol_list, start=1):
            try:
                records.append(fetch_symbol_sector_record(symbol, session=client))
            except Exception:
                LOGGER.exception("Erreur Finnhub sur le symbole %s.", symbol)

            if index < len(symbol_list):
                time.sleep(sleep_seconds)

        return records
    finally:
        if owned_session:
            client.close()

