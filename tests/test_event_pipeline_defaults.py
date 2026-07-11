import logging
from datetime import UTC, datetime

from event_sentiment.config import EventSentimentConfig
from event_sentiment.pipeline import EventSentimentPipeline


class _FakeRepository:
    def __init__(self, checkpoints=None, universe_symbols=None, candidates=None) -> None:
        self.checkpoints = checkpoints or {}
        self.universe_symbols = universe_symbols if universe_symbols is not None else (candidates or [])
        self.ingestion_rows = []
        self.sentiment_rows = []
        self.macro_rows = []
        self.ticker_rows = []
        self.sector_rows = []
        self.pending_load_calls = []

    def get_checkpoint(self, source_name: str, symbol: str):
        return self.checkpoints.get(symbol)

    def get_checkpoints(self, source_name: str, symbols: list[str]):
        return {symbol: self.checkpoints[symbol] for symbol in symbols if symbol in self.checkpoints}

    def load_tradable_universe_symbols(self) -> list[str]:
        return list(self.universe_symbols)

    def list_ticker_map_symbols(self, **_kwargs) -> list[str]:
        return []

    def load_pending_articles(
        self,
        limit: int = 1000,
        *,
        start_date=None,
        end_date=None,
        ingestion_source=None,
        symbols=None,
    ):
        self.pending_load_calls.append(
            {
                "limit": limit,
                "start_date": start_date,
                "end_date": end_date,
                "ingestion_source": ingestion_source,
                "symbols": symbols,
            }
        )
        return []

    def upsert_news_sentiment(self, records):
        self.sentiment_rows.extend(records)
        return len(records)

    def upsert_macro_event_audit(self, records):
        self.macro_rows.extend(records)
        return len(records)

    def load_feature_frames(self, start_date=None, end_date=None, trade_dates=None):
        import pandas as pd

        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    def upsert_ticker_daily_features(self, records):
        self.ticker_rows.extend(records)
        return len(records)

    def upsert_sector_daily_features(self, records):
        self.sector_rows.extend(records)
        return len(records)


class _FakeIngestionService:
    def __init__(self, repository, config) -> None:
        self.calls = []

    def run(
        self,
        start_utc,
        end_utc,
        symbols,
        symbol_start_overrides=None,
        symbol_resume_overrides=None,
        resume_checkpoints=True,
    ):
        self.calls.append({
            "start_utc": start_utc,
            "end_utc": end_utc,
            "symbols": symbols,
            "symbol_start_overrides": symbol_start_overrides,
            "symbol_resume_overrides": symbol_resume_overrides,
            "resume_checkpoints": resume_checkpoints,
        })
        return {"fetched": 0, "deduped": 0, "landed": 0, "ticker_maps": 0}


class _FakeFinBERTSentimentService:
    def __init__(self, *args, **kwargs) -> None:
        self.calls = []

    def score_articles(self, articles):
        self.calls.append(list(articles))
        return []


class _FakeMacroRuleEngine:
    def __init__(self, *args, **kwargs) -> None:
        self.calls = []

    def classify(self, article, sentiment):
        self.calls.append((article, sentiment))
        return []


def test_pipeline_uses_tradable_universe_symbols_when_symbols_none(monkeypatch) -> None:
    repository = _FakeRepository(universe_symbols=["msft", "AAPL", "MSFT"])
    fake_ingestion = _FakeIngestionService(repository, EventSentimentConfig())

    monkeypatch.setattr("event_sentiment.pipeline.NewsIngestionService", lambda repository, config: fake_ingestion)
    monkeypatch.setattr("event_sentiment.pipeline.FinBERTSentimentService", _FakeFinBERTSentimentService)
    monkeypatch.setattr("event_sentiment.pipeline.MacroRuleEngine", _FakeMacroRuleEngine)

    pipeline = EventSentimentPipeline(repository=repository, config=EventSentimentConfig())
    pipeline.run(start_utc=datetime(2026, 1, 1, tzinfo=UTC), end_utc=datetime(2026, 1, 2, tzinfo=UTC), symbols=None)

    assert fake_ingestion.calls[0]["symbols"] == ["AAPL", "MSFT"]


def test_pipeline_uses_checkpoint_watermark_as_time_fallback(monkeypatch) -> None:
    watermark = datetime(2026, 1, 10, 15, 0, 0)
    repository = _FakeRepository(checkpoints={"AAPL": {"watermark_published_at_utc": watermark}}, universe_symbols=["AAPL"])
    config = EventSentimentConfig(checkpoint_overlap_minutes=60)
    fake_ingestion = _FakeIngestionService(repository, config)

    monkeypatch.setattr("event_sentiment.pipeline.NewsIngestionService", lambda repository, config: fake_ingestion)
    monkeypatch.setattr("event_sentiment.pipeline.FinBERTSentimentService", _FakeFinBERTSentimentService)
    monkeypatch.setattr("event_sentiment.pipeline.MacroRuleEngine", _FakeMacroRuleEngine)

    pipeline = EventSentimentPipeline(repository=repository, config=config)
    explicit_end = datetime(2026, 1, 10, 18, 0, 0, tzinfo=UTC)
    pipeline.run(start_utc=None, end_utc=explicit_end, symbols=None)

    assert fake_ingestion.calls[0]["start_utc"] is None
    assert fake_ingestion.calls[0]["end_utc"] == explicit_end
    assert fake_ingestion.calls[0]["resume_checkpoints"] is True
    assert fake_ingestion.calls[0]["symbol_start_overrides"] == {"AAPL": datetime(2026, 1, 10, 14, 0, 0, tzinfo=UTC)}
    assert fake_ingestion.calls[0]["symbol_resume_overrides"] == {"AAPL": True}


def test_pipeline_uses_initial_backfill_for_symbol_without_checkpoint(monkeypatch) -> None:
    watermark = datetime(2026, 1, 10, 15, 0, 0)
    repository = _FakeRepository(
        checkpoints={"MSFT": {"watermark_published_at_utc": watermark}},
        candidates=["AAPL", "MSFT"],
    )
    config = EventSentimentConfig(checkpoint_overlap_minutes=60, initial_backfill_days=7)
    fake_ingestion = _FakeIngestionService(repository, config)

    monkeypatch.setattr("event_sentiment.pipeline.NewsIngestionService", lambda repository, config: fake_ingestion)
    monkeypatch.setattr("event_sentiment.pipeline.FinBERTSentimentService", _FakeFinBERTSentimentService)
    monkeypatch.setattr("event_sentiment.pipeline.MacroRuleEngine", _FakeMacroRuleEngine)

    pipeline = EventSentimentPipeline(repository=repository, config=config)
    explicit_end = datetime(2026, 1, 10, 18, 0, 0, tzinfo=UTC)
    pipeline.run(start_utc=None, end_utc=explicit_end, symbols=None)

    assert fake_ingestion.calls[0]["symbol_start_overrides"] == {
        "AAPL": datetime(2026, 1, 3, 18, 0, 0, tzinfo=UTC),
        "MSFT": datetime(2026, 1, 10, 14, 0, 0, tzinfo=UTC),
    }
    assert fake_ingestion.calls[0]["symbol_resume_overrides"] == {"AAPL": False, "MSFT": True}


def test_pipeline_forces_backfill_from_checkpoint_when_absence_exceeds_threshold(monkeypatch) -> None:
    watermark = datetime(2026, 1, 1, 12, 0, 0)
    repository = _FakeRepository(
        checkpoints={"AAPL": {"watermark_published_at_utc": watermark, "updated_at": watermark}},
        candidates=["AAPL"],
    )
    config = EventSentimentConfig(candidate_reactivation_backfill_days=7)
    fake_ingestion = _FakeIngestionService(repository, config)

    monkeypatch.setattr("event_sentiment.pipeline.NewsIngestionService", lambda repository, config: fake_ingestion)
    monkeypatch.setattr("event_sentiment.pipeline.FinBERTSentimentService", _FakeFinBERTSentimentService)
    monkeypatch.setattr("event_sentiment.pipeline.MacroRuleEngine", _FakeMacroRuleEngine)

    pipeline = EventSentimentPipeline(repository=repository, config=config)
    explicit_end = datetime(2026, 1, 12, 12, 0, 1, tzinfo=UTC)
    pipeline.run(start_utc=None, end_utc=explicit_end, symbols=None)

    assert fake_ingestion.calls[0]["symbol_start_overrides"] == {"AAPL": watermark.replace(tzinfo=UTC)}
    assert fake_ingestion.calls[0]["symbol_resume_overrides"] == {"AAPL": False}


def test_pipeline_keeps_overlap_resume_when_absence_within_threshold(monkeypatch) -> None:
    watermark = datetime(2026, 1, 10, 15, 0, 0)
    repository = _FakeRepository(
        checkpoints={"AAPL": {"watermark_published_at_utc": watermark, "updated_at": watermark}},
        candidates=["AAPL"],
    )
    config = EventSentimentConfig(checkpoint_overlap_minutes=60, candidate_reactivation_backfill_days=7)
    fake_ingestion = _FakeIngestionService(repository, config)

    monkeypatch.setattr("event_sentiment.pipeline.NewsIngestionService", lambda repository, config: fake_ingestion)
    monkeypatch.setattr("event_sentiment.pipeline.FinBERTSentimentService", _FakeFinBERTSentimentService)
    monkeypatch.setattr("event_sentiment.pipeline.MacroRuleEngine", _FakeMacroRuleEngine)

    pipeline = EventSentimentPipeline(repository=repository, config=config)
    explicit_end = datetime(2026, 1, 12, 12, 0, 0, tzinfo=UTC)
    pipeline.run(start_utc=None, end_utc=explicit_end, symbols=None)

    assert fake_ingestion.calls[0]["symbol_start_overrides"] == {"AAPL": datetime(2026, 1, 10, 14, 0, 0, tzinfo=UTC)}
    assert fake_ingestion.calls[0]["symbol_resume_overrides"] == {"AAPL": True}


def test_pipeline_skips_ingestion_when_tradable_universe_is_empty(monkeypatch) -> None:
    repository = _FakeRepository(universe_symbols=[])
    fake_ingestion = _FakeIngestionService(repository, EventSentimentConfig())

    monkeypatch.setattr("event_sentiment.pipeline.NewsIngestionService", lambda repository, config: fake_ingestion)
    monkeypatch.setattr("event_sentiment.pipeline.FinBERTSentimentService", _FakeFinBERTSentimentService)
    monkeypatch.setattr("event_sentiment.pipeline.MacroRuleEngine", _FakeMacroRuleEngine)

    pipeline = EventSentimentPipeline(repository=repository, config=EventSentimentConfig())
    stats = pipeline.run(start_utc=datetime(2026, 1, 1, tzinfo=UTC), end_utc=datetime(2026, 1, 2, tzinfo=UTC), symbols=None)

    assert fake_ingestion.calls == []
    assert stats["ingestion"] == {"fetched": 0, "deduped": 0, "landed": 0, "ticker_maps": 0}


def test_pipeline_logs_resolved_run_window_and_symbol_count(monkeypatch, caplog) -> None:
    repository = _FakeRepository(universe_symbols=["AAPL", "MSFT"])
    fake_ingestion = _FakeIngestionService(repository, EventSentimentConfig())

    monkeypatch.setattr("event_sentiment.pipeline.NewsIngestionService", lambda repository, config: fake_ingestion)
    monkeypatch.setattr("event_sentiment.pipeline.FinBERTSentimentService", _FakeFinBERTSentimentService)
    monkeypatch.setattr("event_sentiment.pipeline.MacroRuleEngine", _FakeMacroRuleEngine)

    caplog.set_level(logging.INFO)
    pipeline = EventSentimentPipeline(repository=repository, config=EventSentimentConfig())
    pipeline.run(start_utc=datetime(2026, 1, 1, tzinfo=UTC), end_utc=datetime(2026, 1, 2, tzinfo=UTC), symbols=None)

    assert "Début event sentiment run" in caplog.text
    assert "start_utc=2026-01-01 00:00:00+00:00" in caplog.text
    assert "end_utc=2026-01-02 00:00:00+00:00" in caplog.text
    assert "symbol_count=2" in caplog.text


def test_pipeline_skip_ingestion_scopes_pending_backlog_to_window_and_provider(monkeypatch) -> None:
    repository = _FakeRepository(candidates=["AAPL"])

    monkeypatch.setattr(
        "event_sentiment.pipeline.NewsIngestionService",
        lambda repository, config: _FakeIngestionService(repository, config),
    )
    monkeypatch.setattr("event_sentiment.pipeline.FinBERTSentimentService", _FakeFinBERTSentimentService)
    monkeypatch.setattr("event_sentiment.pipeline.MacroRuleEngine", _FakeMacroRuleEngine)

    pipeline = EventSentimentPipeline(
        repository=repository,
        config=EventSentimentConfig(provider_name="alpaca", news_provider="alpaca"),
    )
    stats = pipeline.run(
        start_utc=datetime(2026, 1, 1, tzinfo=UTC),
        end_utc=datetime(2026, 1, 2, tzinfo=UTC),
        symbols=None,
        skip_ingestion=True,
    )

    assert stats["ingestion_skipped"] is True
    assert pipeline.ingestion.calls == []
    assert repository.pending_load_calls == [
        {
            "limit": 1000,
            "start_date": datetime(2026, 1, 1, tzinfo=UTC).date(),
            "end_date": datetime(2026, 1, 2, tzinfo=UTC).date(),
            "ingestion_source": "alpaca",
            "symbols": None,
        }
    ]


