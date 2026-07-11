from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from typing import cast

import pytest
from event_sentiment.db_io import EventSentimentRepository

import event_sentiment.importe_news as importe_news


class _FakeRepository:
    def load_tradable_universe_symbols(self) -> list[str]:
        return ["MSFT", "AAPL", "MSFT"]

    def get_checkpoints(self, source_name: str, symbols: list[str]) -> dict[str, dict[str, object]]:
        return {}


class _FakeService:
    def __init__(self, repository, config) -> None:  # type: ignore[no-untyped-def]
        self.repository = repository
        self.config = config
        self.calls: list[dict[str, object]] = []

    def run(
        self,
        *,
        start_utc,
        end_utc,
        symbols,
        resume_checkpoints,
        symbol_start_overrides=None,
        symbol_resume_overrides=None,
    ):  # type: ignore[no-untyped-def]
        self.calls.append(
            {
                "start_utc": start_utc,
                "end_utc": end_utc,
                "symbols": symbols,
                "resume_checkpoints": resume_checkpoints,
                "symbol_start_overrides": symbol_start_overrides,
                "symbol_resume_overrides": symbol_resume_overrides,
            }
        )
        return {"fetched": len(symbols or [])}


def test_importe_news_main_propagates_provider_and_relevance_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(importe_news, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(importe_news, "get_all_symbols_from_tradable_universe", lambda: ["AAPL", "MSFT"])
    monkeypatch.setattr(importe_news, "get_all_symbols_from_stock_scores", lambda **kwargs: ["ZZZZ"])
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


def test_importe_news_main_accepts_scoring_flags_but_warns_they_are_ignored(monkeypatch, caplog) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(importe_news, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(importe_news, "get_all_symbols_from_tradable_universe", lambda: ["AAPL", "MSFT"])
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
            "--sentiment-pending-limit",
            "5000",
            "--sentiment-pending-max-batches",
            "10",
            "--finbert-batch-size",
            "32",
        ],
    )

    with caplog.at_level(logging.WARNING, logger="importe_news"):
        importe_news.main()

    service = captured["service"]
    assert isinstance(service, _FakeService)
    assert len(service.calls) == 1
    assert "Flags de scoring ignorés par importe_news.py" in caplog.text
    assert "--sentiment-pending-limit" in caplog.text
    assert "--sentiment-pending-max-batches" in caplog.text
    assert "--finbert-batch-size" in caplog.text


def test_importe_news_main_blocks_when_max_symbols_is_exceeded(monkeypatch) -> None:
    monkeypatch.setattr(importe_news, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(importe_news, "EventSentimentRepository", lambda: object())
    monkeypatch.setattr(importe_news, "get_all_symbols_from_tradable_universe", lambda: ["AAPL", "MSFT", "NVDA"])

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


def test_resolve_checkpoint_aware_import_scope_uses_watermarks_and_skips_up_to_date_symbols(caplog) -> None:
    class _RepoWithCheckpoints(_FakeRepository):
        def get_checkpoints(self, source_name: str, symbols: list[str]) -> dict[str, dict[str, object]]:
            return {
                "AAPL": {"watermark_published_at_utc": datetime(2026, 4, 15, tzinfo=timezone.utc)},
                "MSFT": {"watermark_published_at_utc": datetime(2026, 4, 10, tzinfo=timezone.utc)},
                "NVDA": {},
            }

    class _Config:
        source_name = "eodhd_news"
        checkpoint_overlap_minutes = 60

    with caplog.at_level(logging.INFO, logger="importe_news"):
        symbols, start_overrides, resume_overrides, skipped = importe_news._resolve_checkpoint_aware_import_scope(
            symbols=["AAPL", "MSFT", "NVDA"],
            start_utc=datetime(2026, 4, 1, tzinfo=timezone.utc),
            end_utc=datetime(2026, 4, 15, tzinfo=timezone.utc),
            repository=cast(EventSentimentRepository, cast(object, _RepoWithCheckpoints())),
            config=cast(object, _Config()),
            logger=logging.getLogger("importe_news"),
        )

    assert symbols == ["MSFT", "NVDA"]
    assert skipped == 1
    assert start_overrides["MSFT"] == datetime(2026, 4, 9, 23, 0, tzinfo=timezone.utc)
    assert start_overrides["NVDA"] == datetime(2026, 4, 1, tzinfo=timezone.utc)
    assert resume_overrides == {"MSFT": True, "NVDA": False}


def test_importe_news_main_can_resume_from_checkpoints(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _RepoWithCheckpoints:
        def get_checkpoints(self, source_name: str, symbols: list[str]) -> dict[str, dict[str, object]]:
            return {
                "AAPL": {"watermark_published_at_utc": datetime(2026, 4, 12, tzinfo=timezone.utc)},
                "MSFT": {"watermark_published_at_utc": datetime(2026, 4, 15, tzinfo=timezone.utc)},
            }

    monkeypatch.setattr(importe_news, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(importe_news, "get_all_symbols_from_tradable_universe", lambda: ["AAPL", "MSFT"])
    monkeypatch.setattr(importe_news, "EventSentimentRepository", lambda: _RepoWithCheckpoints())

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
            "--resume-checkpoints",
        ],
    )

    importe_news.main()

    service = captured["service"]
    assert isinstance(service, _FakeService)
    assert len(service.calls) == 1
    assert service.calls[0]["symbols"] == ["AAPL"]
    assert service.calls[0]["resume_checkpoints"] is False
    assert service.calls[0]["symbol_resume_overrides"] == {"AAPL": True}
    assert service.calls[0]["symbol_start_overrides"] == {
        "AAPL": datetime(2026, 4, 11, 23, 0, tzinfo=timezone.utc)
    }


def test_resolve_symbols_from_inputs_uses_explicit_csv_first() -> None:
    symbols, source = importe_news.resolve_symbols_from_inputs(
        symbols_csv="msft, aapl,MSFT,nvda",
        symbol_source="stock_bars_daily",
        repository=cast(EventSentimentRepository, cast(object, _FakeRepository())),
    )

    assert source == "explicit"
    assert symbols == ["MSFT", "AAPL", "NVDA"]


def test_resolve_symbols_from_inputs_uses_tradable_universe_source(monkeypatch) -> None:
    monkeypatch.setattr(importe_news, "get_all_symbols_from_tradable_universe", lambda: ["MSFT", "AAPL", "MSFT"])

    symbols, source = importe_news.resolve_symbols_from_inputs(
        symbols_csv=None,
        symbol_source="tradable-universe",
        repository=cast(EventSentimentRepository, cast(object, _FakeRepository())),
    )

    assert source == "tradable-universe"
    assert symbols == ["MSFT", "AAPL"]


def test_resolve_symbols_from_inputs_uses_stock_scores_source(monkeypatch) -> None:
    monkeypatch.setattr(importe_news, "get_all_symbols_from_stock_scores", lambda **kwargs: ["nvda", "AAPL", "NVDA"])
    monkeypatch.setattr(importe_news, "get_all_symbols_from_stock_scores_all", lambda: ["ZZZZ"])

    symbols, source = importe_news.resolve_symbols_from_inputs(
        symbols_csv=None,
        symbol_source="stock_scores",
        repository=cast(EventSentimentRepository, cast(object, _FakeRepository())),
    )

    assert source == "stock_scores"
    assert symbols == ["NVDA", "AAPL"]


def test_resolve_symbols_from_inputs_uses_stock_scores_history_source(monkeypatch) -> None:
    monkeypatch.setattr(importe_news, "get_all_symbols_from_stock_scores_history", lambda: ["msft", "AAPL", "MSFT"])
    monkeypatch.setattr(importe_news, "get_all_symbols_from_stock_scores", lambda **kwargs: ["ZZZZ"])

    symbols, source = importe_news.resolve_symbols_from_inputs(
        symbols_csv=None,
        symbol_source="stock_scores_history",
        repository=cast(EventSentimentRepository, cast(object, _FakeRepository())),
    )

    assert source == "stock_scores_history"
    assert symbols == ["MSFT", "AAPL"]


def test_resolve_symbols_from_inputs_uses_stock_scores_all_source(monkeypatch) -> None:
    monkeypatch.setattr(importe_news, "get_all_symbols_from_stock_scores_all", lambda: ["nvda", "AAPL", "NVDA"])
    monkeypatch.setattr(importe_news, "get_all_symbols_from_stock_scores", lambda **kwargs: ["ZZZZ"])

    symbols, source = importe_news.resolve_symbols_from_inputs(
        symbols_csv=None,
        symbol_source="stock_scores_all",
        repository=cast(EventSentimentRepository, cast(object, _FakeRepository())),
    )

    assert source == "stock_scores_all"
    assert symbols == ["NVDA", "AAPL"]


def test_resolve_symbols_from_inputs_uses_tradable_universe_source(monkeypatch) -> None:
    monkeypatch.setattr(importe_news, "get_all_symbols_from_tradable_universe", lambda: ["nvda", "AAPL", "NVDA"])

    symbols, source = importe_news.resolve_symbols_from_inputs(
        symbols_csv=None,
        symbol_source="tradable-universe",
        repository=cast(EventSentimentRepository, cast(object, _FakeRepository())),
    )

    assert source == "tradable-universe"
    assert symbols == ["NVDA", "AAPL"]


def test_get_all_symbols_from_stock_scores_all_uses_union_query(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def _fake_load_distinct_symbols(query: str) -> list[str]:
        captured["query"] = query
        return ["AAPL", "MSFT", "NVDA"]

    monkeypatch.setattr(importe_news, "_load_distinct_symbols", _fake_load_distinct_symbols)

    symbols = importe_news.get_all_symbols_from_stock_scores_all()

    assert symbols == ["AAPL", "MSFT", "NVDA"]
    assert "UNION" in captured["query"]
    assert "INNER JOIN" not in captured["query"]


