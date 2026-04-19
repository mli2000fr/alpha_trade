import pytest
from event_sentiment import scoring

def test_scoring_main(monkeypatch):
    called = {}
    monkeypatch.setattr(scoring, "main", lambda: called.setdefault("main", True))
    scoring.main()
    assert called["main"] is True

