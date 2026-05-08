"""Adaptateur Finnhub ``company-news`` aligné sur le contrat Alpaca news.

Expose ``iter_news_pages`` avec la même signature que
:func:`service.alpaca.clientNewsAlpaca.iter_news_pages` afin de pouvoir
être branché tel quel dans :mod:`event_sentiment.ingestion`.

Différences de fond avec Alpaca :

* Finnhub ne propose pas de pagination ``next_page_token`` sur
  ``/company-news`` : on émet **une seule page** par symbole et on renvoie
  ``next_token=None``. ``page_token`` est ignoré côté entrée.
* La fenêtre est exprimée en dates (``YYYY-MM-DD``). On filtre ensuite
  côté client pour respecter la fenêtre UTC fine demandée.
* Finnhub n'expose pas le ``content`` complet : on laisse ce champ vide,
  ``_normalize_article`` accepte ``content=None``.
* L'identifiant ``id`` Finnhub est numérique et stable la majorité du
  temps. En fallback on construit un hash déterministe sur des champs
  stables (``url`` / ``headline`` / ``datetime``) pour préserver
  l'unicité ``(ingestion_source, dedupe_hash)`` de ``news_raw``.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

import requests

from service._http_retry import request_with_retry
from service._telemetry import bump as _telemetry_bump
from service.finnhub.clientFinnhub import (
    _FINNHUB_RETRY_POLICY,
    get_finnhub_token,
)

FINNHUB_COMPANY_NEWS_ENDPOINT = "https://finnhub.io/api/v1/company-news"

LOGGER = logging.getLogger(__name__)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _fmt_date(value: datetime) -> str:
    return _to_utc(value).strftime("%Y-%m-%d")


def _stable_article_id(symbol: str, raw: dict[str, Any]) -> str:
    """Identifiant déterministe quand ``id`` Finnhub est manquant / instable."""
    parts = "|".join(
        [
            symbol,
            str(raw.get("url") or ""),
            str(raw.get("headline") or ""),
            str(raw.get("datetime") or ""),
        ]
    )
    return hashlib.sha1(parts.encode("utf-8")).hexdigest()[:24]


def _normalize_payload(symbol: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Convertit un article Finnhub en payload compatible
    :func:`event_sentiment.ingestion.NewsIngestionService._normalize_article`.
    """
    raw_id = raw.get("id")
    if raw_id in (None, "", 0):
        article_id = _stable_article_id(symbol, raw)
    else:
        article_id = str(raw_id)

    epoch = raw.get("datetime")
    try:
        published_at = datetime.fromtimestamp(int(epoch), tz=timezone.utc) if epoch else None
    except (TypeError, ValueError, OSError):
        published_at = None

    related = raw.get("related") or ""
    related_symbols = [s.strip().upper() for s in str(related).split(",") if s and s.strip()]
    if symbol.upper() not in related_symbols:
        # On garantit que le symbole interrogé reste présent (Finnhub peut
        # retourner ``related=""`` ou un sous-ensemble inattendu).
        related_symbols = [symbol.upper(), *related_symbols]

    return {
        "id": article_id,
        "created_at": published_at.isoformat() if published_at else None,
        "headline": str(raw.get("headline") or "").strip(),
        "summary": str(raw.get("summary") or "").strip() or None,
        "content": None,  # Finnhub n'expose pas le full text
        "source": str(raw.get("source") or "finnhub").strip(),
        "url": str(raw.get("url") or "").strip() or None,
        "symbols": related_symbols,
        "raw_provider_payload": raw,
    }


def fetch_news_page(
    start_utc: datetime,
    end_utc: datetime,
    symbols: Optional[list[str]] = None,
    limit: int = 50,
    session: Optional[requests.Session] = None,
) -> tuple[list[dict[str, Any]], None]:
    """Récupère les news Finnhub pour ``symbols`` sur la fenêtre demandée.

    Retourne ``(articles, None)`` (pas de pagination native).
    """
    if not symbols:
        # Finnhub ``company-news`` est obligatoirement par symbole.
        return [], None

    start = _to_utc(start_utc)
    end = _to_utc(end_utc)
    from_date = _fmt_date(start)
    to_date = _fmt_date(end)
    token = get_finnhub_token()

    collected: list[dict[str, Any]] = []
    for symbol in symbols:
        normalized_symbol = (symbol or "").strip().upper()
        if not normalized_symbol:
            continue
        params = {
            "symbol": normalized_symbol,
            "from": from_date,
            "to": to_date,
            "token": token,
        }
        owned_session = session is None
        client = session or requests.Session()
        _telemetry_bump("finnhub", "requests_total")
        try:
            response = request_with_retry(
                client,
                "GET",
                FINNHUB_COMPANY_NEWS_ENDPOINT,
                params=params,
                policy=_FINNHUB_RETRY_POLICY,
            )
            data = response.json()
            _telemetry_bump("finnhub", "success_total")
        except requests.exceptions.HTTPError as exc:
            status = getattr(exc.response, "status_code", None)
            if status == 429:
                _telemetry_bump("finnhub", "429_total")
            elif status and 500 <= status < 600:
                _telemetry_bump("finnhub", "5xx_total")
            raise RuntimeError(
                f"Finnhub HTTP {status} pour company-news symbol={normalized_symbol}: {exc}"
            ) from exc
        finally:
            if owned_session:
                client.close()

        # ``company-news`` renvoie nativement une liste JSON ; on tolère
        # quelques variantes dict observées sur certains tenants.
        if isinstance(data, list):
            items_raw = data
        elif isinstance(data, dict):
            items_raw = []
            for key in ("news", "data", "company_news", "items"):
                if isinstance(data.get(key), list):
                    items_raw = data[key]
                    break
        else:
            items_raw = []

        for raw in items_raw:
            if not isinstance(raw, dict):
                continue
            epoch = raw.get("datetime")
            if epoch is not None:
                try:
                    ts = datetime.fromtimestamp(int(epoch), tz=timezone.utc)
                except (TypeError, ValueError, OSError):
                    continue
                if ts < start or ts > end:
                    continue
            collected.append(_normalize_payload(normalized_symbol, raw))

        if limit and len(collected) >= limit:
            break

    if limit and len(collected) > limit:
        collected = collected[:limit]

    LOGGER.info(
        "Finnhub company-news page | from=%s to=%s symbols=%s count=%s",
        from_date,
        to_date,
        symbols,
        len(collected),
    )
    return collected, None


def iter_news_pages(
    start_utc: datetime,
    end_utc: datetime,
    symbols: Optional[list[str]] = None,
    limit: int = 50,
    page_token: Optional[str] = None,  # pylint: disable=unused-argument
    session: Optional[requests.Session] = None,
) -> Iterator[tuple[list[dict[str, Any]], Optional[str]]]:
    """Itérateur compatible avec :func:`service.alpaca.clientNewsAlpaca.iter_news_pages`.

    Finnhub n'a pas de pagination ``next_page_token`` sur ``company-news`` :
    on émet exactement **une page** puis on s'arrête.
    """
    articles, _ = fetch_news_page(
        start_utc=start_utc,
        end_utc=end_utc,
        symbols=symbols,
        limit=limit,
        session=session,
    )
    yield articles, None



