import logging
from datetime import UTC, datetime

from event_sentiment.config import EventSentimentConfig
from event_sentiment.pipeline import EventSentimentPipeline


class _FakeRepository:
    def __init__(self, checkpoint=None, candidates=None) -> None:
        self.checkpoint = checkpoint
        self.candidates = candidates or []
        self.ingestion_rows = []
        self.sentiment_rows = []
        self.macro_rows = []
        self.ticker_rows = []
        self.sector_rows = []

    def get_checkpoint(self, source_name: str):
        return self.checkpoint

    def load_candidate_symbols(self) -> list[str]:
        return list(self.candidates)

    def load_pending_articles(self, limit: int = 1000):
        return []

    def upsert_news_sentiment(self, records):
        self.sentiment_rows.extend(records)
        return len(records)

    def upsert_macro_event_audit(self, records):
        self.macro_rows.extend(records)
        return len(records)

    def load_feature_frames(self, start_date, end_date):
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

    def run(self, start_utc, end_utc, symbols):
        self.calls.append({"start_utc": start_utc, "end_utc": end_utc, "symbols": symbols})
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


def test_pipeline_uses_candidate_symbols_when_symbols_none(monkeypatch) -> None:
    repository = _FakeRepository(candidates=["msft", "AAPL", "MSFT"])
    fake_ingestion = _FakeIngestionService(repository, EventSentimentConfig())

    monkeypatch.setattr("event_sentiment.pipeline.NewsIngestionService", lambda repository, config: fake_ingestion)
    monkeypatch.setattr("event_sentiment.pipeline.FinBERTSentimentService", _FakeFinBERTSentimentService)
    monkeypatch.setattr("event_sentiment.pipeline.MacroRuleEngine", _FakeMacroRuleEngine)

    pipeline = EventSentimentPipeline(repository=repository, config=EventSentimentConfig())
    pipeline.run(start_utc=datetime(2026, 1, 1, tzinfo=UTC), end_utc=datetime(2026, 1, 2, tzinfo=UTC), symbols=None)

    assert fake_ingestion.calls[0]["symbols"] == ["AAPL", "MSFT"]


def test_pipeline_uses_checkpoint_watermark_as_time_fallback(monkeypatch) -> None:
    watermark = datetime(2026, 1, 10, 15, 0, 0)
    repository = _FakeRepository(checkpoint={"watermark_published_at_utc": watermark}, candidates=["AAPL"])
    config = EventSentimentConfig(checkpoint_overlap_minutes=60)
    fake_ingestion = _FakeIngestionService(repository, config)

    monkeypatch.setattr("event_sentiment.pipeline.NewsIngestionService", lambda repository, config: fake_ingestion)
    monkeypatch.setattr("event_sentiment.pipeline.FinBERTSentimentService", _FakeFinBERTSentimentService)
    monkeypatch.setattr("event_sentiment.pipeline.MacroRuleEngine", _FakeMacroRuleEngine)

    pipeline = EventSentimentPipeline(repository=repository, config=config)
    explicit_end = datetime(2026, 1, 10, 18, 0, 0, tzinfo=UTC)
    pipeline.run(start_utc=None, end_utc=explicit_end, symbols=None)

    assert fake_ingestion.calls[0]["start_utc"] == datetime(2026, 1, 10, 14, 0, 0, tzinfo=UTC)
    assert fake_ingestion.calls[0]["end_utc"] == explicit_end


def test_pipeline_skips_ingestion_when_no_candidate_symbols(monkeypatch) -> None:
    repository = _FakeRepository(candidates=[])
    fake_ingestion = _FakeIngestionService(repository, EventSentimentConfig())

    monkeypatch.setattr("event_sentiment.pipeline.NewsIngestionService", lambda repository, config: fake_ingestion)
    monkeypatch.setattr("event_sentiment.pipeline.FinBERTSentimentService", _FakeFinBERTSentimentService)
    monkeypatch.setattr("event_sentiment.pipeline.MacroRuleEngine", _FakeMacroRuleEngine)

    pipeline = EventSentimentPipeline(repository=repository, config=EventSentimentConfig())
    stats = pipeline.run(start_utc=datetime(2026, 1, 1, tzinfo=UTC), end_utc=datetime(2026, 1, 2, tzinfo=UTC), symbols=None)

    assert fake_ingestion.calls == []
    assert stats["ingestion"] == {"fetched": 0, "deduped": 0, "landed": 0, "ticker_maps": 0}


def test_pipeline_logs_resolved_run_window_and_symbol_count(monkeypatch, caplog) -> None:
    repository = _FakeRepository(candidates=["AAPL", "MSFT"])
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


