import logging
import time
from collections.abc import Iterator
from datetime import datetime, time as dt_time, timedelta, timezone
from typing import Any, Literal, Optional

import dateutil.parser
import requests

from service._http_retry import RetryPolicy, request_with_retry
from service._telemetry import bump as _telemetry_bump

DEFAULT_HISTORY_YEARS = 11
DEFAULT_TIMEOUT_SECONDS = 10
MAX_TIMEOUT_RETRIES = 10
TIMEOUT_BACKOFF_SECONDS = 5
PAUSE_CALL_BAR = 0.2
PAUSE_CALL_QUOTE = 0.0
HISTORICAL_QUOTES_LOG_EVERY_PAGES = 10
ALPACA_ASSETS_ENDPOINT = "https://paper-api.alpaca.markets/v2/assets"
ALPACA_BARS_ENDPOINT_TEMPLATE = "https://data.alpaca.markets/v2/stocks/{symbol}/bars"
ALPACA_QUOTES_ENDPOINT_TEMPLATE = "https://data.alpaca.markets/v2/stocks/{symbol}/quotes"
ALPACA_LATEST_QUOTES_ENDPOINT = "https://data.alpaca.markets/v2/stocks/quotes/latest"

#: Politique de retry partagée par tous les call-sites Alpaca data v2.
#: Construite à la volée via :func:`_alpaca_retry_policy()` afin de respecter
#: un éventuel monkeypatch de ``MAX_TIMEOUT_RETRIES`` dans les tests.
def _alpaca_retry_policy() -> RetryPolicy:
    return RetryPolicy(
        max_attempts=MAX_TIMEOUT_RETRIES,
        base_delay_seconds=float(TIMEOUT_BACKOFF_SECONDS),
        max_delay_seconds=60.0,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    )

#: Feeds supportés par l'API Alpaca data v2.
#: ``iex`` = feed gratuit (~2-3% du volume consolidé US — biais documenté
#: dans ``doc/dataIntegrityEngine.md`` et ``audit_global.md``).
#: ``sip`` = feed consolidé payant.
AlpacaFeed = Literal["iex", "sip"]
DEFAULT_FEED: AlpacaFeed = "iex"
_VALID_FEEDS: frozenset[str] = frozenset({"iex", "sip"})

LOGGER = logging.getLogger(__name__)


class AlpacaBarsFetchError(RuntimeError):
    """Erreur technique lors d'un chargement de bars Alpaca.

    Distincte d'un vrai "aucune donnée disponible" provider (ex: HTTP 404).
    """


def get_alpaca_credentials(account_id: Optional[str] = None) -> tuple[str, str]:
    """Récupère les credentials Alpaca depuis le registre multi-comptes.

    Si *account_id* est ``None``, utilise le premier compte configuré
    (rétrocompatibilité avec les variables ``ALPACA_API_KEY`` / ``ALPACA_SECRET_KEY``).
    """
    from service.alpaca.accounts import AccountRegistry
    return AccountRegistry.get().get_credentials(account_id)


def _build_headers(account_id: Optional[str] = None) -> dict[str, str]:
    api_key, secret_key = get_alpaca_credentials(account_id)
    return {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key,
    }


def _normalize_start_date(start_date: Optional[str]) -> str:
    if not start_date:
        return _default_start_date()

    try:
        start_dt = dateutil.parser.isoparse(start_date)
    except (TypeError, ValueError):
        return start_date

    return start_dt.strftime("%Y-%m-%d")


def _default_start_date() -> str:
    default_start = datetime.now(timezone.utc) - timedelta(days=365 * DEFAULT_HISTORY_YEARS)
    return default_start.strftime("%Y-%m-%d")


def _filter_bars_after_start_date(bars: list[dict[str, Any]], start_date: Optional[str]) -> list[dict[str, Any]]:
    if not start_date:
        return bars

    try:
        start_dt = dateutil.parser.isoparse(start_date)
    except (TypeError, ValueError):
        return bars

    return [bar for bar in bars if dateutil.parser.isoparse(bar["t"]) > start_dt]


def _normalize_quotes_window_boundary(value: str, *, end_of_day: bool) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        return cleaned
    try:
        parsed = dateutil.parser.isoparse(cleaned)
    except (TypeError, ValueError):
        return cleaned

    if len(cleaned) <= 10:
        parsed = datetime.combine(
            parsed.date(),
            dt_time.max if end_of_day else dt_time.min,
            tzinfo=timezone.utc,
        )
    elif parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _should_log_page_progress(page_index: int, *, has_next_page: bool) -> bool:
    return page_index == 1 or not has_next_page or page_index % HISTORICAL_QUOTES_LOG_EVERY_PAGES == 0


def fetch_alpaca_assets(session: Optional[requests.Session] = None, account_id: Optional[str] = None) -> list[dict[str, Any]]:
    owned_session = session is None
    client = session or requests.Session()
    _telemetry_bump("alpaca", "requests_total")
    try:
        response = request_with_retry(
            client, "GET", ALPACA_ASSETS_ENDPOINT,
            headers=_build_headers(account_id),
            policy=_alpaca_retry_policy(),
        )
        _telemetry_bump("alpaca", "success_total")
        return response.json()
    finally:
        if owned_session:
            client.close()


def fetch_bars(
    symbol: str,
    timeframe: str,
    start_date: Optional[str] = None,
    session: Optional[requests.Session] = None,
    account_id: Optional[str] = None,
    feed: AlpacaFeed = DEFAULT_FEED,
) -> list[dict[str, Any]]:
    time.sleep(PAUSE_CALL_BAR)
    """Récupère les bars Alpaca pour un symbole et gère la pagination et les timeouts.

    ``feed`` est validé contre :data:`_VALID_FEEDS`. La valeur par défaut
    (``"iex"``) reflète l'offre Alpaca gratuite consommée par le projet ;
    tout autre choix doit être explicite et est tracé dans les logs
    (audit_service.md, audit_dataIntegrityEngine.md).
    """
    if feed not in _VALID_FEEDS:
        raise ValueError(
            f"feed='{feed}' invalide pour Alpaca data v2. "
            f"Valeurs acceptées : {sorted(_VALID_FEEDS)}."
        )
    if feed != DEFAULT_FEED:
        LOGGER.info(
            "Alpaca bars | feed override actif: feed=%s (défaut=%s) symbol=%s",
            feed, DEFAULT_FEED, symbol,
        )
    owned_session = session is None
    client = session or requests.Session()
    endpoint = ALPACA_BARS_ENDPOINT_TEMPLATE.format(symbol=symbol)
    params: dict[str, Any] = {
        "timeframe": timeframe,
        # adjustment=split : série canonique du projet pour le swing trading actions.
        # Les splits sont neutralisés, mais les dividendes ne réécrivent pas le passé.
        "adjustment": "split",
        # feed explicite (Phase 1 refactor) : par défaut IEX (offre Alpaca gratuite).
        "feed": feed,
        # RTH uniquement (09:30–16:00 EST) : exclure les données pre/post-market.
        # "extended_hours": "false",
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

            try:
                _telemetry_bump("alpaca", "requests_total")
                response = request_with_retry(
                    client, "GET", endpoint,
                    headers=_build_headers(account_id),
                    params=params,
                    policy=_alpaca_retry_policy(),
                )
                data = response.json()
                bars = data.get("bars") or []
                bars = _filter_bars_after_start_date(bars, start_date)
                all_bars.extend(bars)
                next_token = data.get("next_page_token")
                _telemetry_bump("alpaca", "success_total")
                LOGGER.info(
                    "Alpaca bars | symbol=%s start=%s next_token=%s count=%s",
                    symbol, params["start"], next_token, len(bars),
                )
            except requests.exceptions.HTTPError as exc:
                if getattr(exc.response, "status_code", None) == 404:
                    LOGGER.warning("Alpaca retourne 404 pour %s : aucun bar disponible.", symbol)
                    return all_bars
                _telemetry_bump("alpaca", "5xx_total")
                raise AlpacaBarsFetchError(
                    f"HTTP error Alpaca pour {symbol}: {exc}"
                ) from exc
            except requests.exceptions.Timeout as exc:
                _telemetry_bump("alpaca", "timeout_total")
                LOGGER.error(
                    "Abandon apres %s timeouts pour %s | partial_bars=%s",
                    MAX_TIMEOUT_RETRIES, symbol, len(all_bars),
                )
                raise AlpacaBarsFetchError(
                    f"Timeout Alpaca epuise pour {symbol} apres {MAX_TIMEOUT_RETRIES} tentatives."
                ) from exc
            except requests.exceptions.RequestException as exc:
                _telemetry_bump("alpaca", "timeout_total")
                raise AlpacaBarsFetchError(
                    f"Erreur reseau Alpaca pour {symbol}: {exc}"
                ) from exc

            if not next_token:
                return all_bars
    finally:
        if owned_session:
            client.close()


def fetch_latest_quotes(
    symbols: list[str],
    session: Optional[requests.Session] = None,
    account_id: Optional[str] = None,
) -> dict[str, dict[str, Any]]:
    """Récupère les dernières quotes Alpaca pour une liste de symboles."""
    if not symbols:
        return {}

    normalized_symbols = []
    for symbol in symbols:
        cleaned = (symbol or "").strip().upper()
        if cleaned and cleaned not in normalized_symbols:
            normalized_symbols.append(cleaned)
    if not normalized_symbols:
        return {}

    owned_session = session is None
    client = session or requests.Session()
    _telemetry_bump("alpaca", "requests_total")
    try:
        response = request_with_retry(
            client, "GET", ALPACA_LATEST_QUOTES_ENDPOINT,
            headers=_build_headers(account_id),
            params={"symbols": ",".join(normalized_symbols)},
            policy=_alpaca_retry_policy(),
        )
        payload = response.json()
        quotes = payload.get("quotes") or {}
        if not isinstance(quotes, dict):
            raise RuntimeError("Réponse latest quotes Alpaca invalide.")
        _telemetry_bump("alpaca", "success_total")
        return {str(symbol): quote for symbol, quote in quotes.items() if isinstance(quote, dict)}
    finally:
        if owned_session:
            client.close()


def fetch_latest_historical_quote_in_window(
    symbol: str,
    *,
    start: str,
    end: str,
    session: Optional[requests.Session] = None,
    account_id: Optional[str] = None,
    feed: AlpacaFeed = DEFAULT_FEED,
) -> dict[str, Any] | None:
    """Retourne la quote historique la plus récente d'une fenêtre donnée.

    Utilise `sort=desc` et `limit=1` pour minimiser les données transférées.
    """
    cleaned_symbol = str(symbol or "").strip().upper()
    if not cleaned_symbol:
        return None
    if feed not in _VALID_FEEDS:
        raise ValueError(
            f"feed='{feed}' invalide pour Alpaca data v2. "
            f"Valeurs acceptées : {sorted(_VALID_FEEDS)}."
        )

    owned_session = session is None
    client = session or requests.Session()
    endpoint = ALPACA_QUOTES_ENDPOINT_TEMPLATE.format(symbol=cleaned_symbol)
    params: dict[str, Any] = {
        "start": _normalize_quotes_window_boundary(start, end_of_day=False),
        "end": _normalize_quotes_window_boundary(end, end_of_day=True),
        "limit": 1,
        "sort": "desc",
        "feed": feed,
    }
    try:
        time.sleep(PAUSE_CALL_QUOTE)
        _telemetry_bump("alpaca", "requests_total")
        response = request_with_retry(
            client,
            "GET",
            endpoint,
            headers=_build_headers(account_id),
            params=params,
            policy=_alpaca_retry_policy(),
        )
        payload = response.json()
        quotes = payload.get("quotes") or []
        if not isinstance(quotes, list):
            raise RuntimeError("Réponse quotes historiques Alpaca invalide.")
        _telemetry_bump("alpaca", "success_total")
        for quote in quotes:
            if isinstance(quote, dict):
                return quote
        return None
    except requests.exceptions.HTTPError as exc:
        if getattr(exc.response, "status_code", None) == 404:
            LOGGER.warning("Alpaca retourne 404 pour %s : aucune quote historique disponible.", cleaned_symbol)
            return None
        _telemetry_bump("alpaca", "5xx_total")
        raise RuntimeError(f"HTTP error Alpaca quote historique fenetre pour {cleaned_symbol}: {exc}") from exc
    except requests.exceptions.Timeout as exc:
        _telemetry_bump("alpaca", "timeout_total")
        raise RuntimeError(
            f"Timeout Alpaca quote historique fenetre epuise pour {cleaned_symbol} apres {MAX_TIMEOUT_RETRIES} tentatives."
        ) from exc
    except requests.exceptions.RequestException as exc:
        _telemetry_bump("alpaca", "timeout_total")
        raise RuntimeError(f"Erreur reseau Alpaca quote historique fenetre pour {cleaned_symbol}: {exc}") from exc
    finally:
        if owned_session:
            client.close()


def fetch_historical_quotes(
    symbol: str,
    *,
    start: str,
    end: str,
    limit: int = 10_000,
    session: Optional[requests.Session] = None,
    account_id: Optional[str] = None,
    feed: AlpacaFeed = DEFAULT_FEED,
) -> list[dict[str, Any]]:
    """Récupère toutes les pages de quotes historiques Alpaca pour un symbole."""
    all_quotes: list[dict[str, Any]] = []
    for page in iter_historical_quotes_pages(
        symbol,
        start=start,
        end=end,
        limit=limit,
        session=session,
        account_id=account_id,
        feed=feed,
    ):
        quotes = page.get("quotes") or []
        if isinstance(quotes, list):
            all_quotes.extend(quote for quote in quotes if isinstance(quote, dict))
    return all_quotes


def iter_historical_quotes_pages(
    symbol: str,
    *,
    start: str,
    end: str,
    limit: int = 10000,
    session: Optional[requests.Session] = None,
    account_id: Optional[str] = None,
    feed: AlpacaFeed = DEFAULT_FEED,
) -> Iterator[dict[str, Any]]:
    """Itère les pages de quotes historiques Alpaca d'un symbole sur une période."""
    cleaned_symbol = str(symbol or "").strip().upper()
    if not cleaned_symbol:
        return
    if feed not in _VALID_FEEDS:
        raise ValueError(
            f"feed='{feed}' invalide pour Alpaca data v2. "
            f"Valeurs acceptées : {sorted(_VALID_FEEDS)}."
        )

    owned_session = session is None
    client = session or requests.Session()
    endpoint = ALPACA_QUOTES_ENDPOINT_TEMPLATE.format(symbol=cleaned_symbol)
    params: dict[str, Any] = {
        "start": _normalize_quotes_window_boundary(start, end_of_day=False),
        "end": _normalize_quotes_window_boundary(end, end_of_day=True),
        "limit": int(limit),
        "sort": "asc",
        "feed": feed,
    }
    next_token: Optional[str] = None
    page_index = 0
    total_quotes = 0

    try:
        while True:
            if next_token:
                params["page_token"] = next_token
            else:
                params.pop("page_token", None)

            try:
                time.sleep(PAUSE_CALL_QUOTE)
                _telemetry_bump("alpaca", "requests_total")
                response = request_with_retry(
                    client,
                    "GET",
                    endpoint,
                    headers=_build_headers(account_id),
                    params=params,
                    policy=_alpaca_retry_policy(),
                )
                payload = response.json()
                quotes = payload.get("quotes") or []
                if not isinstance(quotes, list):
                    raise RuntimeError("Réponse quotes historiques Alpaca invalide.")
                normalized_quotes = [quote for quote in quotes if isinstance(quote, dict)]
                next_token = payload.get("next_page_token")
                page_index += 1
                total_quotes += len(normalized_quotes)
                last_quote_timestamp = None
                if normalized_quotes:
                    last_quote_timestamp = normalized_quotes[-1].get("t")
                _telemetry_bump("alpaca", "success_total")
                if _should_log_page_progress(page_index, has_next_page=bool(next_token)):
                    LOGGER.info(
                        "Alpaca historical quotes | symbol=%s page=%s start=%s end=%s page_count=%s total_count=%s has_next=%s last_quote_ts=%s",
                        cleaned_symbol,
                        page_index,
                        params["start"],
                        params["end"],
                        len(normalized_quotes),
                        total_quotes,
                        bool(next_token),
                        last_quote_timestamp,
                    )
                yield {
                    "symbol": cleaned_symbol,
                    "quotes": normalized_quotes,
                    "page": page_index,
                    "page_count": len(normalized_quotes),
                    "total_count": total_quotes,
                    "has_next": bool(next_token),
                    "start": params["start"],
                    "end": params["end"],
                    "last_quote_timestamp": last_quote_timestamp,
                }
            except requests.exceptions.HTTPError as exc:
                if getattr(exc.response, "status_code", None) == 404:
                    LOGGER.warning("Alpaca retourne 404 pour %s : aucune quote historique disponible.", cleaned_symbol)
                    return
                _telemetry_bump("alpaca", "5xx_total")
                raise RuntimeError(f"HTTP error Alpaca quotes historiques pour {cleaned_symbol}: {exc}") from exc
            except requests.exceptions.Timeout as exc:
                _telemetry_bump("alpaca", "timeout_total")
                raise RuntimeError(
                    f"Timeout Alpaca quotes historiques epuise pour {cleaned_symbol} apres {MAX_TIMEOUT_RETRIES} tentatives."
                ) from exc
            except requests.exceptions.RequestException as exc:
                _telemetry_bump("alpaca", "timeout_total")
                raise RuntimeError(f"Erreur reseau Alpaca quotes historiques pour {cleaned_symbol}: {exc}") from exc

            if not next_token:
                return
    finally:
        if owned_session:
            client.close()


