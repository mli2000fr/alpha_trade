"""Client HTTP FRED — séries macro minimales pour Alpha Trade.

Usage actuel : récupération des observations daily/weekly nécessaires au 10Y US
(``DGS10`` par défaut) pour la couche `service.market`.
"""
from __future__ import annotations

import os
from typing import Any, Optional, cast

import requests

from service._http_retry import CircuitOpenError, RetryPolicy, request_with_retry

FRED_API_BASE_URL = "https://api.stlouisfed.org/fred"
DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_API_KEY_ENV = "KEY_FRED"


class FredFetchError(RuntimeError):
    """Erreur technique lors d'un fetch FRED."""


def _retry_policy() -> RetryPolicy:
    return RetryPolicy(
        max_attempts=4,
        base_delay_seconds=0.5,
        max_delay_seconds=10.0,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    )


def _resolve_api_key(api_key_env: str = DEFAULT_API_KEY_ENV) -> str:
    api_key = (os.getenv(api_key_env) or "").strip()
    if not api_key:
        raise FredFetchError(f"Variable d'environnement {api_key_env} absente pour FRED.")
    return api_key


def fetch_series_observations(
    series_id: str,
    *,
    start: str | None = None,
    end: str | None = None,
    api_key_env: str = DEFAULT_API_KEY_ENV,
    session: Optional[requests.Session] = None,
    base_url: str = FRED_API_BASE_URL,
) -> list[dict[str, Any]]:
    """Retourne la liste brute des observations FRED pour une série donnée."""
    resolved_series_id = str(series_id or "").strip().upper()
    if not resolved_series_id:
        raise FredFetchError("series_id FRED vide")
    params: dict[str, Any] = {
        "series_id": resolved_series_id,
        "api_key": _resolve_api_key(api_key_env),
        "file_type": "json",
        "sort_order": "asc",
    }
    if start:
        params["observation_start"] = start
    if end:
        params["observation_end"] = end
    url = f"{base_url.rstrip('/')}/series/observations"
    sess = session if session is not None else requests.Session()
    try:
        response = request_with_retry(sess, "GET", url, params=params, policy=_retry_policy())
    except CircuitOpenError as exc:
        raise FredFetchError(f"circuit HTTP FRED ouvert: {exc}") from exc
    except requests.exceptions.HTTPError as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        raise FredFetchError(f"HTTP {status} sur FRED series={resolved_series_id}: {exc}") from exc
    except requests.exceptions.RequestException as exc:
        raise FredFetchError(f"erreur réseau FRED series={resolved_series_id}: {exc}") from exc

    try:
        payload = cast(dict[str, Any], response.json())
    except ValueError as exc:
        raise FredFetchError(f"payload non-JSON FRED series={resolved_series_id}: {exc}") from exc
    observations = payload.get("observations")
    if not isinstance(observations, list):
        raise FredFetchError(f"payload FRED inattendu pour series={resolved_series_id}")
    return [cast(dict[str, Any], row) for row in observations if isinstance(row, dict)]


__all__ = ["FredFetchError", "fetch_series_observations"]

