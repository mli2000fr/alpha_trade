import logging
import time
from datetime import datetime, timezone
from typing import Any, Iterator, Optional, cast

import requests

from service.alpaca.clientAlpaca import DEFAULT_TIMEOUT_SECONDS, get_alpaca_credentials

ALPACA_NEWS_ENDPOINT = "https://data.alpaca.markets/v1beta1/news"
MAX_TIMEOUT_RETRIES = 5
MAX_RATE_LIMIT_RETRIES = 5
TIMEOUT_BACKOFF_SECONDS = 5
RATE_LIMIT_BACKOFF_SECONDS = 20

LOGGER = logging.getLogger(__name__)


def _build_headers() -> dict[str, str]:
    api_key, secret_key = get_alpaca_credentials()
    return {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key,
    }


def _fmt_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_news_page(
    start_utc: datetime,
    end_utc: datetime,
    page_token: Optional[str] = None,
    symbols: Optional[list[str]] = None,
    limit: int = 50,
    session: Optional[requests.Session] = None,
) -> tuple[list[dict[str, Any]], Optional[str]]:
    owned_session = session is None
    client = session or requests.Session()
    params: dict[str, Any] = {
        "start": _fmt_utc(start_utc),
        "end": _fmt_utc(end_utc),
        "limit": limit,
        "sort": "asc",
    }
    if page_token:
        params["page_token"] = page_token
    if symbols:
        params["symbols"] = ",".join(sorted({symbol.strip().upper() for symbol in symbols if symbol}))

    timeout_attempts = 0
    rate_limit_attempts = 0

    try:
        while True:
            try:
                response = client.get(
                    ALPACA_NEWS_ENDPOINT,
                    headers=_build_headers(),
                    params=params,
                    timeout=DEFAULT_TIMEOUT_SECONDS,
                )
                if response.status_code == 429:
                    rate_limit_attempts += 1
                    LOGGER.warning(
                        "Alpaca news rate limit | attempt=%s/%s",
                        rate_limit_attempts,
                        MAX_RATE_LIMIT_RETRIES,
                    )
                    if rate_limit_attempts >= MAX_RATE_LIMIT_RETRIES:
                        raise RuntimeError("Rate limit Alpaca News persistant.")
                    time.sleep(RATE_LIMIT_BACKOFF_SECONDS)
                    continue

                response.raise_for_status()
                payload = cast(dict[str, Any], response.json() or {})
                raw_articles = payload.get("news") or []
                articles = list(raw_articles) if isinstance(raw_articles, list) else []
                raw_next_token = payload.get("next_page_token")
                next_token = str(raw_next_token) if raw_next_token else None
                LOGGER.info(
                    "Alpaca news page | start=%s end=%s count=%s next_token=%s",
                    params["start"],
                    params["end"],
                    len(articles),
                    next_token,
                )
                return articles, next_token
            except requests.exceptions.Timeout:
                timeout_attempts += 1
                LOGGER.warning(
                    "Timeout Alpaca news | attempt=%s/%s",
                    timeout_attempts,
                    MAX_TIMEOUT_RETRIES,
                )
                if timeout_attempts >= MAX_TIMEOUT_RETRIES:
                    raise RuntimeError("Abandon après timeouts Alpaca News.")
                time.sleep(TIMEOUT_BACKOFF_SECONDS)
    finally:
        if owned_session:
            client.close()


def iter_news_pages(
    start_utc: datetime,
    end_utc: datetime,
    symbols: Optional[list[str]] = None,
    limit: int = 50,
    page_token: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> Iterator[tuple[list[dict[str, Any]], Optional[str]]]:
    next_token = page_token
    while True:
        articles, next_token = fetch_news_page(
            start_utc=start_utc,
            end_utc=end_utc,
            page_token=next_token,
            symbols=symbols,
            limit=limit,
            session=session,
        )
        yield articles, next_token
        if not next_token:
            return


