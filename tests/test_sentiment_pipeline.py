import pytest
from event_sentiment import sentiment_pipeline

def test_sentiment_pipeline_main(monkeypatch):
    called = {}
    monkeypatch.setattr(sentiment_pipeline, "main", lambda: called.setdefault("main", True))
    sentiment_pipeline.main()
    assert called["main"] is True

