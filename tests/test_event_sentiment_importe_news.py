from __future__ import annotations

import sys
from datetime import datetime, timezone

import event_sentiment.importe_news as importe_news


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
    monkeypatch.setattr(importe_news, "get_all_symbols_from_stock_bars_daily", lambda: ["AAPL", "MSFT"])
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

