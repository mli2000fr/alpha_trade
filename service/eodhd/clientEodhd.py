"""Client HTTP EODHD — endpoints utilisés par Alpha Trade.

Plan §5.2.

Endpoints couverts :
- ``GET /eod-bulk-last-day/{exchange}``    (cost = 100)
- ``GET /eod/{ticker}.{exchange}``         (cost = 1)
- ``GET /splits/{ticker}.{exchange}``      (cost = 1)
- ``GET /div/{ticker}.{exchange}``         (cost = 1)

Toutes les réponses sont retournées en ``list[dict]`` (la structure native
EODHD ; les normalisations OHLCV split-only sont faites par
``service.eodhd.adapters``).
"""
from __future__ import annotations

import logging
from typing import Any, Literal, Optional, Sequence

import requests

from service._http_retry import RetryPolicy, request_with_retry
from service._telemetry import bump as _telemetry_bump
from service.eodhd.accounts import EodhdAccountRegistry, EodhdAuthError
from service.eodhd.quota import (
    EodhdQuotaExceeded,
    EodhdQuotaTracker,
    get_default_tracker,
)
from service.eodhd.symbols import to_eodhd

LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_BACKOFF_SECONDS = 1.0
TELEMETRY_CLIENT = "eodhd"

PeriodLiteral = Literal["d", "w", "m"]


class EodhdBarsFetchError(RuntimeError):
    """Erreur technique lors d'un fetch EODHD."""


def _retry_policy() -> RetryPolicy:
    return RetryPolicy(
        max_attempts=DEFAULT_MAX_ATTEMPTS,
        base_delay_seconds=DEFAULT_BACKOFF_SECONDS,
        max_delay_seconds=30.0,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    )


def _get_token() -> str:
    try:
        return EodhdAccountRegistry.get().get_token()
    except EodhdAuthError as exc:
        raise EodhdBarsFetchError(str(exc)) from exc


def _get_base_url() -> str:
    try:
        return EodhdAccountRegistry.get().resolve().base_url.rstrip("/")
    except EodhdAuthError:
        return "https://eodhd.com/api"


def _build_session(session: Optional[requests.Session]) -> requests.Session:
    return session if session is not None else requests.Session()


def _do_request(
    *,
    endpoint: str,
    url: str,
    params: dict[str, Any],
    session: Optional[requests.Session],
    tracker: EodhdQuotaTracker,
) -> Any:
    """Effectue un GET avec gestion quota + telemetry + retry."""
    tracker.reserve(endpoint)
    sess = _build_session(session)
    _telemetry_bump(TELEMETRY_CLIENT, "requests_total")
    try:
        response = request_with_retry(sess, "GET", url, params=params, policy=_retry_policy())
    except requests.exceptions.Timeout as exc:
        _telemetry_bump(TELEMETRY_CLIENT, "timeout_total")
        tracker.record_failure(endpoint, count_call=False)
        raise EodhdBarsFetchError(f"timeout EODHD ({endpoint}): {exc}") from exc
    except requests.exceptions.HTTPError as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status == 401 or status == 403:
            _telemetry_bump(TELEMETRY_CLIENT, "auth_error_total")
        elif status == 429:
            _telemetry_bump(TELEMETRY_CLIENT, "429_total")
        elif status and status >= 500:
            _telemetry_bump(TELEMETRY_CLIENT, "5xx_total")
        tracker.record_failure(endpoint, count_call=True)
        raise EodhdBarsFetchError(f"HTTP {status} sur {endpoint}: {exc}") from exc
    except requests.exceptions.RequestException as exc:
        tracker.record_failure(endpoint, count_call=False)
        raise EodhdBarsFetchError(f"erreur réseau EODHD ({endpoint}): {exc}") from exc

    tracker.record_success(endpoint)
    _telemetry_bump(TELEMETRY_CLIENT, "success_total")
    try:
        return response.json()
    except ValueError as exc:
        raise EodhdBarsFetchError(f"payload non-JSON sur {endpoint}: {exc}") from exc


# ---------------------------------------------------------------------------
# Endpoints publics
# ---------------------------------------------------------------------------


def fetch_eod_bulk(
    *,
    date: Optional[str] = None,
    exchange: str = "US",
    symbols: Optional[Sequence[str]] = None,
    fmt: str = "json",
    session: Optional[requests.Session] = None,
    tracker: Optional[EodhdQuotaTracker] = None,
) -> list[dict]:
    """Bulk last-day pour un exchange entier (~7 000 symboles US).

    1 appel = 100 calls de quota. ``date`` optionnel (par défaut J-1 côté EODHD).
    ``symbols`` permet de filtrer côté API (paramètre ``symbols=A,B,C``) — utile
    en debug, n'économise PAS le coût (toujours facturé 100).
    """
    base_url = _get_base_url()
    params: dict[str, Any] = {
        "api_token": _get_token(),
        "fmt": fmt,
    }
    if date:
        params["date"] = date
    if symbols:
        params["symbols"] = ",".join(s.strip().upper() for s in symbols if s)
    payload = _do_request(
        endpoint="bulk",
        url=f"{base_url}/eod-bulk-last-day/{exchange.upper()}",
        params=params,
        session=session,
        tracker=tracker or get_default_tracker(),
    )
    if not isinstance(payload, list):
        raise EodhdBarsFetchError(f"bulk payload inattendu (type={type(payload).__name__})")
    return payload


def fetch_eod(
    symbol: str,
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
    period: PeriodLiteral = "d",
    fmt: str = "json",
    session: Optional[requests.Session] = None,
    tracker: Optional[EodhdQuotaTracker] = None,
) -> list[dict]:
    """Historique pour un symbole projet (mappé automatiquement vers ``X.US``).

    1 appel = 1 call. ``start`` / ``end`` au format ISO ``YYYY-MM-DD``.
    """
    eodhd_symbol = to_eodhd(symbol)
    base_url = _get_base_url()
    params: dict[str, Any] = {
        "api_token": _get_token(),
        "fmt": fmt,
        "period": period,
    }
    if start:
        params["from"] = start
    if end:
        params["to"] = end
    payload = _do_request(
        endpoint="eod",
        url=f"{base_url}/eod/{eodhd_symbol}",
        params=params,
        session=session,
        tracker=tracker or get_default_tracker(),
    )
    if not isinstance(payload, list):
        raise EodhdBarsFetchError(f"eod payload inattendu pour {symbol}")
    return payload


def fetch_splits(
    symbol: str,
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
    fmt: str = "json",
    session: Optional[requests.Session] = None,
    tracker: Optional[EodhdQuotaTracker] = None,
) -> list[dict]:
    """Splits pour un symbole projet — 1 call.

    Format attendu : ``[{"date": "YYYY-MM-DD", "split": "N/M"}, ...]``.
    """
    eodhd_symbol = to_eodhd(symbol)
    base_url = _get_base_url()
    params: dict[str, Any] = {
        "api_token": _get_token(),
        "fmt": fmt,
    }
    if start:
        params["from"] = start
    if end:
        params["to"] = end
    payload = _do_request(
        endpoint="splits",
        url=f"{base_url}/splits/{eodhd_symbol}",
        params=params,
        session=session,
        tracker=tracker or get_default_tracker(),
    )
    if not isinstance(payload, list):
        raise EodhdBarsFetchError(f"splits payload inattendu pour {symbol}")
    return payload


def fetch_dividends(
    symbol: str,
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
    fmt: str = "json",
    session: Optional[requests.Session] = None,
    tracker: Optional[EodhdQuotaTracker] = None,
) -> list[dict]:
    """Dividendes pour un symbole projet — 1 call.

    Format attendu : ``[{"date": "YYYY-MM-DD", "value": 0.24, ...}, ...]``.
    """
    eodhd_symbol = to_eodhd(symbol)
    base_url = _get_base_url()
    params: dict[str, Any] = {
        "api_token": _get_token(),
        "fmt": fmt,
    }
    if start:
        params["from"] = start
    if end:
        params["to"] = end
    payload = _do_request(
        endpoint="dividends",
        url=f"{base_url}/div/{eodhd_symbol}",
        params=params,
        session=session,
        tracker=tracker or get_default_tracker(),
    )
    if not isinstance(payload, list):
        raise EodhdBarsFetchError(f"dividends payload inattendu pour {symbol}")
    return payload


__all__ = [
    "DEFAULT_BACKOFF_SECONDS",
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_TIMEOUT_SECONDS",
    "EodhdBarsFetchError",
    "PeriodLiteral",
    "TELEMETRY_CLIENT",
    "fetch_dividends",
    "fetch_eod",
    "fetch_eod_bulk",
    "fetch_splits",
]

