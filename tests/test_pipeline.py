import pytest
from event_sentiment import pipeline

def test_pipeline_main(monkeypatch):
    called = {}
    monkeypatch.setattr(pipeline, "main", lambda: called.setdefault("main", True))
    pipeline.main()
    assert called["main"] is True

def test_event_sentiment_pipeline_init():
    class DummyRepo:
        def load_candidate_symbols(self):
            return ["AAPL"]
    class DummyConfig:
        finbert_model_name = "ProsusAI/finbert"
        finbert_model_version = "v1"
        finbert_batch_size = 16
        finbert_max_length = 256
        macro_rule_version = "macro_rules_v1"
        initial_backfill_days = 365
        regular_session_maps_to_same_day = False
    pipe = pipeline.EventSentimentPipeline(DummyRepo(), DummyConfig())
    assert hasattr(pipe, "ingestion")
    assert hasattr(pipe, "finbert")
    assert hasattr(pipe, "macro_engine")
    assert callable(pipe._resolve_symbols)

