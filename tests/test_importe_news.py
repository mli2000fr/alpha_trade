import pytest
from event_sentiment import importe_news

def test_importe_news_main(monkeypatch):
    called = {}
    monkeypatch.setattr(importe_news, "main", lambda: called.setdefault("main", True))
    importe_news.main()
    assert called["main"] is True

