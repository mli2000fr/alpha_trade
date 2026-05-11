from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

import pytest

import event_sentiment.importe_news as importe_news


class _FakeRepository:
    def load_candidate_symbols(self) -> list[str]:
        return ["MSFT", "AAPL", "MSFT"]


class _FakeService:
    def __init__(self, repository, config) -> None:  # type: ignore[no-untyped-def]
        self.repository = repository
        self.config = config
        self.calls: list[dict[str, object]] = []

    def run(self, *, start_utc, end_utc, symbols, resume_checkpoints):  # type: ignore[no-untyped-def]
        self.calls.append(
            {
                "start_utc": start_utc,
                "end_utc": end_utc,
                "symbols": symbols,
                "resume_checkpoints": resume_checkpoints,
            }
        )
        return {"fetched": len(symbols or [])}


def test_importe_news_main_propagates_provider_and_relevance_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(importe_news, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(importe_news, "get_all_symbols_from_stock_scores", lambda **kwargs: ["AAPL", "MSFT"])
    monkeypatch.setattr(importe_news, "get_all_symbols_from_stock_bars_daily", lambda: ["ZZZZ"])
    monkeypatch.setattr(importe_news, "EventSentimentRepository", lambda: object())

    def _fake_service_factory(repository, config):  # type: ignore[no-untyped-def]
        service = _FakeService(repository, config)
        captured["service"] = service
        return service

    monkeypatch.setattr(importe_news, "NewsIngestionService", _fake_service_factory)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "importe_news.py",
            "--start-date",
            "2026-04-01",
            "--end-date",
            "2026-04-15",
            "--news-provider",
            "finnhub",
            "--ticker-relevance-mode",
            "scored",
            "--min-relevance-score",
            "0.35",
        ],
    )

    importe_news.main()

    service = captured["service"]
    assert isinstance(service, _FakeService)
    assert service.config.news_provider == "finnhub"
    assert service.config.provider_ticker_relevance_mode == "scored"
    assert service.config.min_relevance_score == 0.35
    assert len(service.calls) == 1
    assert service.calls[0]["symbols"] == ["AAPL", "MSFT"]
    assert service.calls[0]["resume_checkpoints"] is False
    assert service.calls[0]["start_utc"] == datetime(2026, 4, 1, tzinfo=timezone.utc)
    assert service.calls[0]["end_utc"] == datetime(2026, 4, 15, tzinfo=timezone.utc)


def test_importe_news_main_can_force_stock_bars_daily_source(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(importe_news, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(importe_news, "get_all_symbols_from_stock_scores", lambda **kwargs: ["AAPL"])
    monkeypatch.setattr(importe_news, "get_all_symbols_from_stock_bars_daily", lambda: ["MSFT", "NVDA"])
    monkeypatch.setattr(importe_news, "EventSentimentRepository", lambda: object())

    def _fake_service_factory(repository, config):  # type: ignore[no-untyped-def]
        service = _FakeService(repository, config)
        captured["service"] = service
        return service

    monkeypatch.setattr(importe_news, "NewsIngestionService", _fake_service_factory)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "importe_news.py",
            "--start-date",
            "2026-04-01",
            "--end-date",
            "2026-04-15",
            "--symbol-source",
            "stock_bars_daily",
        ],
    )

    importe_news.main()

    service = captured["service"]
    assert isinstance(service, _FakeService)
    assert len(service.calls) == 1
    assert service.calls[0]["symbols"] == ["MSFT", "NVDA"]


def test_importe_news_main_symbols_override_source(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(importe_news, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(importe_news, "get_all_symbols_from_stock_scores", lambda **kwargs: ["AAPL"])
    monkeypatch.setattr(importe_news, "get_all_symbols_from_stock_bars_daily", lambda: ["MSFT"])
    monkeypatch.setattr(importe_news, "EventSentimentRepository", lambda: object())

    def _fake_service_factory(repository, config):  # type: ignore[no-untyped-def]
        service = _FakeService(repository, config)
        captured["service"] = service
        return service

    monkeypatch.setattr(importe_news, "NewsIngestionService", _fake_service_factory)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "importe_news.py",
            "--start-date",
            "2026-04-01",
            "--symbols",
            "msft, aapl,MSFT,nvda",
            "--symbol-source",
            "stock_bars_daily",
        ],
    )

    importe_news.main()

    service = captured["service"]
    assert isinstance(service, _FakeService)
    assert len(service.calls) == 1
    assert service.calls[0]["symbols"] == ["MSFT", "AAPL", "NVDA"]


def test_importe_news_main_warns_for_large_stock_bars_daily_universe(monkeypatch, caplog) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(importe_news, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(importe_news, "EventSentimentRepository", lambda: object())
    monkeypatch.setattr(importe_news, "get_all_symbols_from_stock_bars_daily", lambda: ["AAPL", "MSFT", "NVDA"])
    monkeypatch.setattr(importe_news, "STOCK_BARS_DAILY_WARNING_THRESHOLD", 2)

    def _fake_service_factory(repository, config):  # type: ignore[no-untyped-def]
        service = _FakeService(repository, config)
        captured["service"] = service
        return service

    monkeypatch.setattr(importe_news, "NewsIngestionService", _fake_service_factory)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "importe_news.py",
            "--start-date",
            "2026-04-01",
            "--symbol-source",
            "stock_bars_daily",
        ],
    )

    with caplog.at_level(logging.WARNING, logger="importe_news"):
        importe_news.main()

    service = captured["service"]
    assert isinstance(service, _FakeService)
    assert len(service.calls) == 1
    assert "Univers d'import très large détecté" in caplog.text


def test_importe_news_main_blocks_when_max_symbols_is_exceeded(monkeypatch) -> None:
    monkeypatch.setattr(importe_news, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(importe_news, "EventSentimentRepository", lambda: object())
    monkeypatch.setattr(importe_news, "get_all_symbols_from_stock_scores", lambda **kwargs: ["AAPL", "MSFT", "NVDA"])

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "importe_news.py",
            "--start-date",
            "2026-04-01",
            "--max-symbols",
            "2",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        importe_news.main()

    assert exc_info.value.code == 2


def test_resolve_symbols_from_inputs_uses_explicit_csv_first() -> None:
    symbols, source = importe_news.resolve_symbols_from_inputs(
        symbols_csv="msft, aapl,MSFT,nvda",
        symbol_source="stock_bars_daily",
        repository=_FakeRepository(),
    )

    assert source == "explicit"
    assert symbols == ["MSFT", "AAPL", "NVDA"]


def test_resolve_symbols_from_inputs_uses_candidates_repository(monkeypatch) -> None:
    monkeypatch.setattr(importe_news, "get_all_symbols_from_stock_scores", lambda **kwargs: ["ZZZZ"])
    monkeypatch.setattr(importe_news, "get_all_symbols_from_stock_bars_daily", lambda: ["YYYY"])

    symbols, source = importe_news.resolve_symbols_from_inputs(
        symbols_csv=None,
        symbol_source="candidates",
        repository=_FakeRepository(),
    )

    assert source == "candidates"
    assert symbols == ["MSFT", "AAPL"]


