"""Adaptateur EODHD ``Financial News Feed`` aligné sur le contrat Alpaca/Finnhub.

Expose ``iter_news_pages`` avec la même signature que
:func:`service.alpaca.clientNewsAlpaca.iter_news_pages` afin de pouvoir
être branché tel quel dans :mod:`event_sentiment.ingestion`.

Spécificités EODHD :

* Endpoint : ``GET https://eodhd.com/api/news`` (paramètres : ``s=AAPL.US``
  ou ``t=<tag>``, ``from``/``to`` au format ``YYYY-MM-DD``, ``limit``,
  ``offset``, ``api_token``, ``fmt=json``).
* La pagination est par ``offset`` (pas de cursor) — encapsulée derrière
  un ``next_token`` synthétique sérialisé : ``str(offset_suivant)``. On
  arrête dès qu'une page est plus courte que ``limit``.
* La fenêtre est exprimée en dates calendaires : on filtre côté client
  pour respecter la fenêtre UTC fine demandée.
* EODHD ne fournit pas d'identifiant article stable : on construit un
  hash déterministe sur ``url|date|title|symbole_interrogé`` (cf.
  pattern ``_stable_article_id`` de Finnhub) afin de préserver
  l'unicité ``(ingestion_source, dedupe_hash)`` de ``news_raw``.
* Les requêtes acceptent indifféremment un symbole projet ``AAPL`` ou déjà
  natif provider ``AAPL.US``. Pour l'appel HTTP, on conserve le format
  provider natif ; pour le downstream `event_sentiment`, on normalise quand
  même vers le symbole projet canonique ``AAPL`` afin de rester compatible
  avec `stock_scores`, `stock_metadata` et `news_ticker_map`.
* Les champs ``tags`` et ``sentiment`` (déjà calculé côté provider)
  sont **conservés tels quels** dans ``raw_provider_payload`` (donc
  recopiés dans ``news_raw.raw_payload``). FinBERT reste la source de
  vérité pour ``news_sentiment`` ; le sentiment EODHD est purement
  audit-only à ce stade.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

import requests
import dateutil.parser

from service._http_retry import RetryPolicy, request_with_retry
from service._telemetry import bump as _telemetry_bump
from service.eodhd.accounts import EodhdAccountRegistry, EodhdAuthError
from service.eodhd.symbols import from_eodhd, to_eodhd

LOGGER = logging.getLogger(__name__)

EODHD_NEWS_ENDPOINT_PATH = "/news"
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_BACKOFF_SECONDS = 1.0
TELEMETRY_CLIENT = "eodhd"

# Quota tracker volontairement non utilisé ici : l'endpoint ``/news`` est
# facturé séparément côté plan All-In-One et n'a pas le même profil que
# les EOD bars / splits / dividends. On laisse le tracker hors path news
# pour ne pas couper les appels EOD si jamais le quota saute côté news.


class EodhdNewsFetchError(RuntimeError):
    """Erreur technique lors d'un fetch EODHD news."""


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _fmt_date(value: datetime) -> str:
    return _to_utc(value).strftime("%Y-%m-%d")


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
        raise EodhdNewsFetchError(str(exc)) from exc


def _get_base_url() -> str:
    try:
        return EodhdAccountRegistry.get().resolve().base_url.rstrip("/")
    except EodhdAuthError:
        return "https://eodhd.com/api"


def _stable_article_id(symbol: str, raw: dict[str, Any]) -> str:
    """Identifiant déterministe — EODHD n'expose pas d'``id`` stable."""
    try:
        stable_symbol = to_eodhd(str(symbol or "").strip().upper())
    except ValueError:
        stable_symbol = str(symbol or "").strip().upper()
    parts = "|".join(
        [
            stable_symbol,
            str(raw.get("link") or raw.get("url") or ""),
            str(raw.get("title") or raw.get("headline") or ""),
            str(raw.get("date") or ""),
        ]
    )
    return hashlib.sha1(parts.encode("utf-8")).hexdigest()[:24]


def _to_project_symbol(symbol: str) -> str:
    raw = str(symbol or "").strip().upper()
    if not raw:
        return ""
    try:
        project_symbol, _exchange = from_eodhd(raw)
        return project_symbol
    except ValueError:
        return raw


def _normalize_symbol_list(symbol_query: str, raw_symbols: Any) -> list[str]:
    """Convertit ``symbols`` EODHD (``AAPL.US``, ``IONQ.US``…) en symboles projet.

    Garantit que le symbole interrogé est présent (EODHD peut renvoyer
    une liste vide ou ne pas inclure le symbole demandé).
    """
    project_symbols: list[str] = []
    seen: set[str] = set()

    def _add(sym: str) -> None:
        sym = sym.strip().upper()
        if not sym or sym in seen:
            return
        seen.add(sym)
        project_symbols.append(sym)

    if isinstance(raw_symbols, list):
        for entry in raw_symbols:
            if not entry:
                continue
            text = str(entry).strip()
            if not text:
                continue
            try:
                project, _ = from_eodhd(text)
            except ValueError:
                project = text.upper()
            _add(project)

    # Garantit la présence du symbole interrogé en tête, au format projet
    # canonique (ex. ``AAPL.US`` -> ``AAPL``).
    query_symbol = _to_project_symbol(symbol_query)
    if query_symbol and query_symbol not in seen:
        project_symbols.insert(0, query_symbol)
        seen.add(query_symbol)
    return project_symbols


def _normalize_payload(symbol: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Convertit un article EODHD en payload compatible
    :func:`event_sentiment.ingestion.NewsIngestionService._normalize_article`.
    """
    article_id = _stable_article_id(symbol, raw)
    published_at_raw = raw.get("date") or raw.get("published_at")
    headline = str(raw.get("title") or raw.get("headline") or "").strip()
    content = str(raw.get("content") or raw.get("body") or "").strip() or None
    url = str(raw.get("link") or raw.get("url") or "").strip() or None
    project_symbols = _normalize_symbol_list(symbol, raw.get("symbols"))

    return {
        "id": article_id,
        "created_at": str(published_at_raw) if published_at_raw else None,
        "headline": headline,
        # EODHD n'expose pas de ``summary`` distinct du ``content`` ; le
        # scoring FinBERT retombe donc sur ``content`` quand ``summary`` est
        # absent.
        "summary": None,
        "content": content,
        "source": str(raw.get("source") or "eodhd").strip() or "eodhd",
        "url": url,
        "symbols": project_symbols,
        # Le payload EODHD complet (tags, sentiment provider, etc.) est
        # conservé tel quel pour audit downstream via ``news_raw.raw_payload``.
        "raw_provider_payload": raw,
    }


def _parse_published_ts(raw_date: Any) -> datetime | None:
    if raw_date is None or raw_date == "":
        return None
    try:
        ts = dateutil.parser.isoparse(str(raw_date))
    except (ValueError, TypeError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def fetch_news_page(
    start_utc: datetime,
    end_utc: datetime,
    symbols: Optional[list[str]] = None,
    limit: int = 50,
    offset: int = 0,
    session: Optional[requests.Session] = None,
) -> tuple[list[dict[str, Any]], Optional[str]]:
    """Récupère **une** page EODHD pour le 1er symbole de ``symbols``.

    Retourne ``(articles, next_token)`` où ``next_token = str(offset_suivant)``
    ou ``None`` quand la pagination est épuisée (page courte).

    Notes :
    * EODHD ``/news`` accepte un seul ``s=`` à la fois (ou un ``t=`` tag).
      Pour rester aligné avec le contrat ``iter_news_pages`` du pipeline
      (qui appelle systématiquement avec ``symbols=[symbol]``), on traite
      uniquement le 1er symbole de la liste.
    """
    if not symbols:
        return [], None
    request_symbol = (symbols[0] or "").strip().upper()
    if not request_symbol:
        return [], None

    eodhd_symbol = to_eodhd(request_symbol)
    start = _to_utc(start_utc)
    end = _to_utc(end_utc)
    base_url = _get_base_url()
    url = f"{base_url}{EODHD_NEWS_ENDPOINT_PATH}"
    params: dict[str, Any] = {
        "api_token": _get_token(),
        "s": eodhd_symbol,
        "from": _fmt_date(start),
        "to": _fmt_date(end),
        "limit": int(max(1, limit)),
        "offset": int(max(0, offset)),
        "fmt": "json",
    }

    owned_session = session is None
    client = session or requests.Session()
    _telemetry_bump(TELEMETRY_CLIENT, "requests_total")
    try:
        response = request_with_retry(
            client,
            "GET",
            url,
            params=params,
            policy=_retry_policy(),
        )
        data = response.json()
        _telemetry_bump(TELEMETRY_CLIENT, "success_total")
    except requests.exceptions.HTTPError as exc:
        status_raw = getattr(exc.response, "status_code", None)
        status = int(status_raw) if isinstance(status_raw, int) else None
        if status == 429:
            _telemetry_bump(TELEMETRY_CLIENT, "429_total")
        elif status and 500 <= status < 600:
            _telemetry_bump(TELEMETRY_CLIENT, "5xx_total")
        elif status in (401, 403):
            _telemetry_bump(TELEMETRY_CLIENT, "auth_error_total")
        raise EodhdNewsFetchError(
            f"EODHD HTTP {status} sur /news symbol={eodhd_symbol}: {exc}"
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise EodhdNewsFetchError(
            f"EODHD erreur réseau /news symbol={eodhd_symbol}: {exc}"
        ) from exc
    finally:
        if owned_session:
            client.close()

    if not isinstance(data, list):
        # Certaines variantes wrappent dans ``{\"data\": [...]}``.
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            data = data["data"]
        else:
            data = []

    page_size = len(data)
    collected: list[dict[str, Any]] = []
    for raw in data:
        if not isinstance(raw, dict):
            continue
        published = _parse_published_ts(raw.get("date"))
        if published is not None and (published < start or published > end):
            continue
        collected.append(_normalize_payload(request_symbol, raw))

    # Pagination par offset : tant que la page brute fait ``limit`` items
    # on suppose qu'il y a peut-être une page suivante. Sinon on s'arrête.
    next_token: Optional[str] = None
    if page_size >= int(params["limit"]):
        next_token = str(int(params["offset"]) + page_size)

    LOGGER.info(
        "EODHD news page | symbol=%s from=%s to=%s offset=%s raw=%s kept=%s next=%s",
        eodhd_symbol,
        params["from"],
        params["to"],
        params["offset"],
        page_size,
        len(collected),
        next_token,
    )
    return collected, next_token


def iter_news_pages(
    start_utc: datetime,
    end_utc: datetime,
    symbols: Optional[list[str]] = None,
    limit: int = 50,
    page_token: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> Iterator[tuple[list[dict[str, Any]], Optional[str]]]:
    """Itérateur compatible avec :func:`service.alpaca.clientNewsAlpaca.iter_news_pages`.

    Encapsule la pagination par ``offset`` derrière un ``next_token``
    sérialisé. Émet une page par appel REST jusqu'à épuisement.
    """
    if not symbols:
        yield [], None
        return

    try:
        offset = int(page_token) if page_token else 0
    except (TypeError, ValueError):
        offset = 0

    while True:
        articles, next_token = fetch_news_page(
            start_utc=start_utc,
            end_utc=end_utc,
            symbols=symbols,
            limit=limit,
            offset=offset,
            session=session,
        )
        yield articles, next_token
        if not next_token:
            return
        try:
            offset = int(next_token)
        except (TypeError, ValueError):
            return


__all__ = [
    "EodhdNewsFetchError",
    "EODHD_NEWS_ENDPOINT_PATH",
    "fetch_news_page",
    "iter_news_pages",
]

