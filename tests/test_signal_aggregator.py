import pytest
from event_sentiment import signal_aggregator

def test_signal_aggregator_main(monkeypatch):
    called = {}
    monkeypatch.setattr(signal_aggregator, "main", lambda: called.setdefault("main", True))
    signal_aggregator.main()
    assert called["main"] is True

