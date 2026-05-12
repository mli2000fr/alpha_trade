"""Tests unitaires pour ``service.eodhd.news_client``.

Couvre :
- normalisation des payloads EODHD (mapping ``date→created_at``,
  ``title→headline``, ``link→url``, requêtes acceptant `AAPL.US` mais
  symboles downstream canoniques `AAPL`, conservation ``tags`` /
  ``sentiment`` dans ``raw_provider_payload``) ;
- pagination par offset encapsulée derrière ``next_token`` ;
- filtrage de la fenêtre UTC côté client ;
- garantie que le symbole interrogé est toujours présent ;
- identifiant article stable (hash déterministe).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from service.eodhd import news_client


class _FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def json(self) -> Any:
        return self._payload


def _fake_request_factory(pages: list[list[dict[str, Any]]]):
    captured: dict[str, Any] = {"calls": []}

    def _fake(client, method, url, params=None, policy=None):  # type: ignore[no-untyped-def]
        captured["calls"].append({"url": url, "params": dict(params or {})})
        offset = int((params or {}).get("offset", 0))
        # On retourne la "page" indexée par son offset / limit observé.
        limit = int((params or {}).get("limit", 50))
        page_index = offset // max(limit, 1)
        if 0 <= page_index < len(pages):
            return _FakeResponse(pages[page_index])
        return _FakeResponse([])

    return _fake, captured


@pytest.fixture(autouse=True)
def _patch_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(news_client, "_get_token", lambda: "test-token")
    monkeypatch.setattr(news_client, "_get_base_url", lambda: "https://eodhd.test/api")


def _raw_article(
    *,
    title: str,
    date_iso: str,
    link: str,
    symbols: list[str] | None = None,
    tags: list[str] | None = None,
    sentiment: dict[str, float] | None = None,
    content: str = "Body content",
) -> dict[str, Any]:
    return {
        "date": date_iso,
        "title": title,
        "content": content,
        "link": link,
        "symbols": symbols if symbols is not None else ["AAPL.US"],
        "tags": tags if tags is not None else ["earnings"],
        "sentiment": sentiment
        if sentiment is not None
        else {"polarity": 0.42, "neg": 0.1, "neu": 0.4, "pos": 0.5},
    }


def test_normalize_payload_maps_eodhd_fields_and_preserves_provider_payload() -> None:
    raw = _raw_article(
        title="Apple beats earnings",
        date_iso="2026-04-15T14:00:00+00:00",
        link="https://news.test/apple-q1",
        symbols=["AAPL.US", "BRK-B.US"],
        tags=["earnings", "tech"],
    )
    payload = news_client._normalize_payload("AAPL", raw)

    assert payload["headline"] == "Apple beats earnings"
    assert payload["created_at"] == "2026-04-15T14:00:00+00:00"
    assert payload["url"] == "https://news.test/apple-q1"
    assert payload["content"] == "Body content"
    assert payload["source"] == "eodhd"
    assert payload["summary"] is None
    # AAPL.US -> AAPL ; BRK-B.US -> BRK.B ; AAPL conservé en tête.
    assert payload["symbols"][0] == "AAPL"
    assert "BRK.B" in payload["symbols"]
    # raw_provider_payload doit conserver tags + sentiment intacts
    assert payload["raw_provider_payload"]["tags"] == ["earnings", "tech"]
    assert payload["raw_provider_payload"]["sentiment"]["polarity"] == 0.42
    # Identifiant stable et préfixé par le provider en sortie ingestion.
    assert isinstance(payload["id"], str)
    assert len(payload["id"]) == 24


def test_normalize_payload_accepts_native_query_symbol_without_leaking_exchange_suffix() -> None:
    raw = _raw_article(
        title="Apple native symbol",
        date_iso="2026-04-15T14:00:00+00:00",
        link="https://news.test/apple-native",
        symbols=["AAPL.US"],
    )

    payload = news_client._normalize_payload("AAPL.US", raw)

    assert payload["symbols"] == ["AAPL"]
    assert "AAPL.US" not in payload["symbols"]


def test_normalize_payload_guarantees_query_symbol_is_present() -> None:
    raw = _raw_article(
        title="Generic note",
        date_iso="2026-04-15T14:00:00+00:00",
        link="https://news.test/x",
        symbols=["MSFT.US"],
    )
    payload = news_client._normalize_payload("AAPL", raw)
    assert payload["symbols"][0] == "AAPL"
    assert "MSFT" in payload["symbols"]


def test_stable_article_id_is_identical_for_project_and_native_provider_symbol() -> None:
    raw = _raw_article(
        title="same article",
        date_iso="2026-04-15T14:00:00+00:00",
        link="https://x/same",
    )
    assert news_client._stable_article_id("AAPL", raw) == news_client._stable_article_id("AAPL.US", raw)


def test_stable_article_id_is_deterministic() -> None:
    raw = _raw_article(
        title="t", date_iso="2026-04-15T14:00:00+00:00", link="https://x"
    )
    aid1 = news_client._stable_article_id("AAPL", raw)
    aid2 = news_client._stable_article_id("AAPL", raw)
    aid3 = news_client._stable_article_id("MSFT", raw)
    assert aid1 == aid2
    assert aid1 != aid3


def test_fetch_news_page_filters_outside_window(monkeypatch: pytest.MonkeyPatch) -> None:
    pages = [
        [
            _raw_article(
                title="In window",
                date_iso="2026-04-15T12:00:00+00:00",
                link="https://x/1",
            ),
            _raw_article(
                title="Too old",
                date_iso="2026-04-10T08:00:00+00:00",
                link="https://x/2",
            ),
            _raw_article(
                title="Future",
                date_iso="2026-04-20T08:00:00+00:00",
                link="https://x/3",
            ),
        ]
    ]
    fake, captured = _fake_request_factory(pages)
    monkeypatch.setattr(news_client, "request_with_retry", fake)

    articles, next_token = news_client.fetch_news_page(
        start_utc=datetime(2026, 4, 15, tzinfo=timezone.utc),
        end_utc=datetime(2026, 4, 16, tzinfo=timezone.utc),
        symbols=["AAPL"],
        limit=50,
        offset=0,
    )
    assert len(articles) == 1
    assert articles[0]["headline"] == "In window"
    # Page courte (3 < 50) -> pas de next_token
    assert next_token is None
    assert captured["calls"][0]["params"]["s"] == "AAPL.US"
    assert captured["calls"][0]["params"]["from"] == "2026-04-15"
    assert captured["calls"][0]["params"]["to"] == "2026-04-16"


def test_fetch_news_page_accepts_native_provider_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    pages = [[_raw_article(title="Native query", date_iso="2026-04-15T12:00:00+00:00", link="https://x/native")]]
    fake, captured = _fake_request_factory(pages)
    monkeypatch.setattr(news_client, "request_with_retry", fake)

    articles, next_token = news_client.fetch_news_page(
        start_utc=datetime(2026, 4, 15, tzinfo=timezone.utc),
        end_utc=datetime(2026, 4, 16, tzinfo=timezone.utc),
        symbols=["AAPL.US"],
        limit=50,
        offset=0,
    )

    assert next_token is None
    assert captured["calls"][0]["params"]["s"] == "AAPL.US"
    assert articles[0]["symbols"] == ["AAPL"]


def test_iter_news_pages_paginates_with_offset(monkeypatch: pytest.MonkeyPatch) -> None:
    # 2 pages "pleines" (limit=2) puis page courte → arrêt.
    pages = [
        [
            _raw_article(
                title=f"a{i}",
                date_iso="2026-04-15T12:00:00+00:00",
                link=f"https://x/{i}",
            )
            for i in range(2)
        ],
        [
            _raw_article(
                title=f"b{i}",
                date_iso="2026-04-15T13:00:00+00:00",
                link=f"https://x/b{i}",
            )
            for i in range(2)
        ],
        [
            _raw_article(
                title="c0",
                date_iso="2026-04-15T14:00:00+00:00",
                link="https://x/c0",
            )
        ],
    ]
    fake, captured = _fake_request_factory(pages)
    monkeypatch.setattr(news_client, "request_with_retry", fake)

    collected: list[tuple[list[dict[str, Any]], str | None]] = []
    for batch, token in news_client.iter_news_pages(
        start_utc=datetime(2026, 4, 15, tzinfo=timezone.utc),
        end_utc=datetime(2026, 4, 16, tzinfo=timezone.utc),
        symbols=["AAPL"],
        limit=2,
    ):
        collected.append((batch, token))

    # 3 pages : 2 pleines + 1 courte (token final = None)
    assert [token for _, token in collected] == ["2", "4", None]
    assert sum(len(b) for b, _ in collected) == 5
    # Offsets envoyés : 0, 2, 4
    assert [c["params"]["offset"] for c in captured["calls"]] == [0, 2, 4]


def test_iter_news_pages_empty_symbols_yields_empty() -> None:
    out = list(
        news_client.iter_news_pages(
            start_utc=datetime(2026, 4, 15, tzinfo=timezone.utc),
            end_utc=datetime(2026, 4, 16, tzinfo=timezone.utc),
            symbols=[],
        )
    )
    assert out == [([], None)]

