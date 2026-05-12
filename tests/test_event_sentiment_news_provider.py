"""Tests pour la sélection du provider news dans :mod:`event_sentiment`.

Couvre :

* la fabrique :meth:`EventSentimentConfig.for_provider` ;
* la résolution dynamique de l'``iter_news_pages`` dans
  :class:`NewsIngestionService` ;
* les garde-fous Niveau 1 sur le mapping article → ticker.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from event_sentiment.config import (
    PROVIDER_REGISTRY,
    EventSentimentConfig,
)
from event_sentiment import ingestion as ingestion_mod


class _StubMapper:
    def resolve(self, symbols, allow_fallback: bool = True):  # type: ignore[no-untyped-def]
        return {
            sym: {
                "sector": "Tech",
                "sector_source": "stub",
                "sector_updated_at": None,
                "company_name": "Apple" if sym == "AAPL" else None,
            }
            for sym in symbols
        }


@pytest.fixture(autouse=True)
def _patch_sector_mapper(monkeypatch: pytest.MonkeyPatch) -> None:
    """Évite la connexion DB de :class:`EntitySectorMapper`."""
    monkeypatch.setattr(ingestion_mod, "EntitySectorMapper", _StubMapper)


def test_config_for_provider_finnhub_sets_source_name() -> None:
    cfg = EventSentimentConfig.for_provider("finnhub")
    assert cfg.news_provider == "finnhub"
    assert cfg.source_name == "finnhub_news"
    assert cfg.provider_name == "finnhub"


def test_config_for_provider_alpaca_keeps_legacy_names() -> None:
    cfg = EventSentimentConfig.for_provider("alpaca")
    assert cfg.news_provider == "alpaca"
    assert cfg.source_name == "alpaca_news"
    assert cfg.provider_name == "alpaca"


def test_config_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="news_provider"):
        EventSentimentConfig(news_provider="bloomberg")  # type: ignore[arg-type]


def test_provider_registry_covers_supported_providers() -> None:
    assert set(PROVIDER_REGISTRY) == {"alpaca", "finnhub", "eodhd"}


def test_config_for_provider_eodhd_sets_source_name() -> None:
    cfg = EventSentimentConfig.for_provider("eodhd")
    assert cfg.news_provider == "eodhd"
    assert cfg.source_name == "eodhd_news"
    assert cfg.provider_name == "eodhd"


def test_event_sentiment_config_default_provider_is_eodhd() -> None:
    cfg = EventSentimentConfig()
    assert cfg.news_provider == "eodhd"
    assert cfg.source_name == "eodhd_news"
    assert cfg.provider_name == "eodhd"


# --- Dispatch dans NewsIngestionService ----------------------------------


class _StubRepo:
    def __init__(self) -> None:
        self.ticker_map_rows: list[dict[str, Any]] = []

    def get_checkpoint(self, source_name: str, symbol: str) -> dict[str, Any] | None:
        return None

    def upsert_checkpoint(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        return None

    def get_existing_article_ids(self, ids: list[str]) -> list[str]:
        return []

    def upsert_news_raw(self, rows: list[dict[str, Any]]) -> int:
        return len(rows)

    def upsert_news_ticker_map(self, rows: list[dict[str, Any]]) -> int:
        self.ticker_map_rows.extend(rows)
        return len(rows)


def _make_payload(article_id: str, tickers: list[str]) -> dict[str, Any]:
    return {
        "id": article_id,
        "created_at": datetime(2026, 4, 15, 12, tzinfo=timezone.utc).isoformat(),
        "headline": f"headline {article_id}",
        "summary": "s",
        "source": "Reuters",
        "url": f"https://example.test/{article_id}",
        "symbols": tickers,
    }


def _install_fake_provider(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    payloads: list[dict[str, Any]],
) -> dict[str, Any]:
    captured: dict[str, Any] = {"calls": 0}

    def _fake_iter(start_utc, end_utc, symbols=None, limit=50, page_token=None, session=None):  # type: ignore[no-untyped-def]
        captured["calls"] += 1
        captured["last_symbols"] = symbols
        yield payloads, None

    monkeypatch.setitem(ingestion_mod.NEWS_PROVIDERS, name, _fake_iter)
    return captured


def test_ingestion_routes_to_finnhub_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads = [_make_payload("a1", ["AAPL"])]
    captured = _install_fake_provider(monkeypatch, "finnhub", payloads)

    cfg = EventSentimentConfig.for_provider("finnhub")
    service = ingestion_mod.NewsIngestionService(_StubRepo(), cfg)
    summary = service.run(
        start_utc=datetime(2026, 4, 15, tzinfo=timezone.utc),
        end_utc=datetime(2026, 4, 16, tzinfo=timezone.utc),
        symbols=["AAPL"],
    )
    assert captured["calls"] == 1
    assert captured["last_symbols"] == ["AAPL"]
    assert summary["fetched"] == 1
    assert summary["landed"] == 1
    assert summary["ticker_maps"] == 1


def test_ingestion_routes_to_alpaca_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads = [_make_payload("a1", ["MSFT"])]
    captured = _install_fake_provider(monkeypatch, "alpaca", payloads)

    cfg = EventSentimentConfig.for_provider("alpaca")
    service = ingestion_mod.NewsIngestionService(_StubRepo(), cfg)
    service.run(
        start_utc=datetime(2026, 4, 15, tzinfo=timezone.utc),
        end_utc=datetime(2026, 4, 16, tzinfo=timezone.utc),
        symbols=["MSFT"],
    )
    assert captured["calls"] == 1


def test_ingestion_routes_to_eodhd_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads = [_make_payload("eodhd-1", ["AAPL"])]
    captured = _install_fake_provider(monkeypatch, "eodhd", payloads)

    cfg = EventSentimentConfig.for_provider("eodhd")
    service = ingestion_mod.NewsIngestionService(_StubRepo(), cfg)
    summary = service.run(
        start_utc=datetime(2026, 4, 15, tzinfo=timezone.utc),
        end_utc=datetime(2026, 4, 16, tzinfo=timezone.utc),
        symbols=["AAPL"],
    )
    assert captured["calls"] == 1
    assert captured["last_symbols"] == ["AAPL"]
    assert summary["fetched"] == 1
    assert summary["landed"] == 1
    assert summary["ticker_maps"] == 1


def test_ingestion_filters_articles_with_too_many_tickers(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads = [
        _make_payload("noisy", [f"T{i}" for i in range(30)]),
        _make_payload("clean", ["AAPL"]),
    ]
    _install_fake_provider(monkeypatch, "finnhub", payloads)

    cfg = EventSentimentConfig.for_provider("finnhub", max_tickers_per_article=10)
    service = ingestion_mod.NewsIngestionService(_StubRepo(), cfg)
    summary = service.run(
        start_utc=datetime(2026, 4, 15, tzinfo=timezone.utc),
        end_utc=datetime(2026, 4, 16, tzinfo=timezone.utc),
        symbols=["AAPL"],
    )
    assert summary["filtered_too_many_tickers"] == 1
    assert summary["landed"] == 1
    assert summary["ticker_maps"] == 1


def test_ingestion_strict_mode_keeps_primary_ticker_only(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads = [_make_payload("multi", ["AAPL", "MSFT", "NVDA"])]
    _install_fake_provider(monkeypatch, "finnhub", payloads)

    cfg = EventSentimentConfig.for_provider(
        "finnhub", provider_ticker_relevance_mode="strict"
    )
    service = ingestion_mod.NewsIngestionService(_StubRepo(), cfg)
    summary = service.run(
        start_utc=datetime(2026, 4, 15, tzinfo=timezone.utc),
        end_utc=datetime(2026, 4, 16, tzinfo=timezone.utc),
        symbols=["AAPL"],
    )
    assert summary["ticker_maps"] == 1
    assert summary["strict_dropped_tickers"] == 2


def _make_payload_with_text(article_id: str, tickers: list[str], headline: str) -> dict[str, Any]:
    payload = _make_payload(article_id, tickers)
    payload["headline"] = headline
    return payload


def test_ingestion_scored_mode_writes_relevance_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads = [_make_payload_with_text("a1", ["AAPL", "MSFT"], "Apple unveils new chip")]
    _install_fake_provider(monkeypatch, "finnhub", payloads)

    cfg = EventSentimentConfig.for_provider(
        "finnhub", provider_ticker_relevance_mode="scored"
    )
    repo = _StubRepo()
    service = ingestion_mod.NewsIngestionService(repo, cfg)
    summary = service.run(
        start_utc=datetime(2026, 4, 15, tzinfo=timezone.utc),
        end_utc=datetime(2026, 4, 16, tzinfo=timezone.utc),
        symbols=["AAPL"],
    )
    assert summary["relevance_scored"] == 2
    assert summary["relevance_filtered"] == 0
    assert summary["ticker_maps"] == 2

    rows_by_symbol = {row["symbol"]: row for row in repo.ticker_map_rows}
    assert "relevance_score" in rows_by_symbol["AAPL"]
    assert "relevance_components" in rows_by_symbol["AAPL"]
    assert rows_by_symbol["AAPL"]["relevance_score"] > rows_by_symbol["MSFT"]["relevance_score"]


def test_ingestion_scored_mode_filters_below_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads = [_make_payload_with_text("a1", ["AAPL", "MSFT"], "Apple unveils new chip")]
    _install_fake_provider(monkeypatch, "finnhub", payloads)

    cfg = EventSentimentConfig.for_provider(
        "finnhub",
        provider_ticker_relevance_mode="scored",
        min_relevance_score=0.5,
    )
    repo = _StubRepo()
    service = ingestion_mod.NewsIngestionService(repo, cfg)
    summary = service.run(
        start_utc=datetime(2026, 4, 15, tzinfo=timezone.utc),
        end_utc=datetime(2026, 4, 16, tzinfo=timezone.utc),
        symbols=["AAPL"],
    )
    assert summary["relevance_filtered"] == 1
    assert summary["ticker_maps"] == 1
    assert all(row["symbol"] == "AAPL" for row in repo.ticker_map_rows)
