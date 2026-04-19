import pytest
from event_sentiment import event_sentiment_pipeline

def test_run_pipeline_main(monkeypatch):
    called = {}
    monkeypatch.setattr(event_sentiment_pipeline, "main", lambda: called.setdefault("main", True))
    event_sentiment_pipeline.main()
    assert called["main"] is True

