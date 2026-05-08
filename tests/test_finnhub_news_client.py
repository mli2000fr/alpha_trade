"""Tests pour l'adaptateur Finnhub ``company-news``.

Couvre :

* la normalisation d'un payload Finnhub vers le format consommé par
  :func:`event_sentiment.ingestion.NewsIngestionService._normalize_article` ;
* le filtrage côté client de la fenêtre UTC fine ;
* l'utilisation d'un identifiant déterministe quand ``id`` est absent.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from service.finnhub import news_client


@pytest.fixture(autouse=True)
def _fake_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(news_client, "get_finnhub_token", lambda: "test-token")
    news_client._reset_company_news_rate_limit_state()


def _patch_request(monkeypatch: pytest.MonkeyPatch, payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remplace ``request_with_retry`` par un fake renvoyant ``payload``."""
    captured: list[dict[str, Any]] = []

    def _fake_request(client, method, url, *, params, policy):  # type: ignore[no-untyped-def]
        captured.append({"url": url, "params": dict(params)})
        return SimpleNamespace(json=lambda: payload)

    monkeypatch.setattr(news_client, "request_with_retry", _fake_request)
    return captured


def test_iter_news_pages_normalises_finnhub_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    epoch = int(datetime(2026, 4, 15, 12, 30, tzinfo=timezone.utc).timestamp())
    raw = [
        {
            "id": 999_111,
            "datetime": epoch,
            "headline": "AAPL hits new high",
            "summary": "Some summary",
            "source": "Reuters",
            "url": "https://example.test/a",
            "related": "AAPL,MSFT",
        }
    ]
    captured = _patch_request(monkeypatch, raw)

    pages = list(
        news_client.iter_news_pages(
            start_utc=datetime(2026, 4, 15, tzinfo=timezone.utc),
            end_utc=datetime(2026, 4, 16, tzinfo=timezone.utc),
            symbols=["aapl"],
        )
    )

    assert len(pages) == 1
    articles, next_token = pages[0]
    assert next_token is None
    assert len(articles) == 1
    article = articles[0]
    # Champs attendus par `_normalize_article`
    assert article["id"] == "999111"
    assert article["headline"] == "AAPL hits new high"
    assert article["summary"] == "Some summary"
    assert article["content"] is None
    assert article["source"] == "Reuters"
    assert article["url"] == "https://example.test/a"
    assert article["symbols"] == ["AAPL", "MSFT"]
    # Timestamp rendu en ISO UTC
    assert article["created_at"].startswith("2026-04-15T12:30:00")
    # Endpoint et paramètres
    assert captured[0]["url"] == news_client.FINNHUB_COMPANY_NEWS_ENDPOINT
    assert captured[0]["params"]["symbol"] == "AAPL"
    assert captured[0]["params"]["from"] == "2026-04-15"
    assert captured[0]["params"]["to"] == "2026-04-16"
    assert captured[0]["params"]["token"] == "test-token"


def test_iter_news_pages_filters_outside_window(monkeypatch: pytest.MonkeyPatch) -> None:
    inside = int(datetime(2026, 4, 15, 12, tzinfo=timezone.utc).timestamp())
    before = int(datetime(2026, 4, 14, 23, tzinfo=timezone.utc).timestamp())
    after = int(datetime(2026, 4, 17, 0, 1, tzinfo=timezone.utc).timestamp())
    raw = [
        {"id": 1, "datetime": before, "headline": "h1", "url": "u1", "related": "AAPL"},
        {"id": 2, "datetime": inside, "headline": "h2", "url": "u2", "related": "AAPL"},
        {"id": 3, "datetime": after, "headline": "h3", "url": "u3", "related": "AAPL"},
    ]
    _patch_request(monkeypatch, raw)

    pages = list(
        news_client.iter_news_pages(
            start_utc=datetime(2026, 4, 15, tzinfo=timezone.utc),
            end_utc=datetime(2026, 4, 16, 23, 59, tzinfo=timezone.utc),
            symbols=["AAPL"],
        )
    )
    articles, _ = pages[0]
    ids = [a["id"] for a in articles]
    assert ids == ["2"]


def test_iter_news_pages_falls_back_to_stable_id_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = [
        {
            "id": None,
            "datetime": int(datetime(2026, 4, 15, 12, tzinfo=timezone.utc).timestamp()),
            "headline": "stable headline",
            "url": "https://example.test/x",
            "related": "AAPL",
        }
    ]
    _patch_request(monkeypatch, raw)

    pages = list(
        news_client.iter_news_pages(
            start_utc=datetime(2026, 4, 15, tzinfo=timezone.utc),
            end_utc=datetime(2026, 4, 16, tzinfo=timezone.utc),
            symbols=["AAPL"],
        )
    )
    articles, _ = pages[0]
    assert articles
    article_id = articles[0]["id"]
    assert isinstance(article_id, str) and len(article_id) == 24


def test_iter_news_pages_returns_empty_for_no_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    # Pas d'appel HTTP attendu
    def _explode(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("HTTP call should not happen for empty symbols.")

    monkeypatch.setattr(news_client, "request_with_retry", _explode)
    pages = list(
        news_client.iter_news_pages(
            start_utc=datetime(2026, 4, 15, tzinfo=timezone.utc),
            end_utc=datetime(2026, 4, 16, tzinfo=timezone.utc),
            symbols=[],
        )
    )
    articles, next_token = pages[0]
    assert articles == []
    assert next_token is None


def test_iter_news_pages_throttles_consecutive_calls_across_invocations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = [
        {
            "id": 1,
            "datetime": int(datetime(2026, 4, 15, 12, tzinfo=timezone.utc).timestamp()),
            "headline": "AAPL headline",
            "url": "https://example.test/aapl",
            "related": "AAPL",
        }
    ]
    captured = _patch_request(monkeypatch, raw)
    clock = {"now": 100.0}
    sleep_calls: list[float] = []

    def _fake_monotonic() -> float:
        return clock["now"]

    def _fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        clock["now"] += seconds

    monkeypatch.setattr(news_client.time, "monotonic", _fake_monotonic)
    monkeypatch.setattr(news_client.time, "sleep", _fake_sleep)

    list(
        news_client.iter_news_pages(
            start_utc=datetime(2026, 4, 15, tzinfo=timezone.utc),
            end_utc=datetime(2026, 4, 16, tzinfo=timezone.utc),
            symbols=["AAPL"],
        )
    )
    list(
        news_client.iter_news_pages(
            start_utc=datetime(2026, 4, 15, tzinfo=timezone.utc),
            end_utc=datetime(2026, 4, 16, tzinfo=timezone.utc),
            symbols=["MSFT"],
        )
    )

    assert [call["params"]["symbol"] for call in captured] == ["AAPL", "MSFT"]
    assert sleep_calls == [pytest.approx(news_client.FINNHUB_COMPANY_NEWS_MIN_REQUEST_INTERVAL_SECONDS)]
    assert news_client.FINNHUB_COMPANY_NEWS_MAX_CALLS_PER_MINUTE == 55


