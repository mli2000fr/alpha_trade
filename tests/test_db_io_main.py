from event_sentiment import db_io

def test_event_sentiment_repository_init():
    repo = db_io.EventSentimentRepository()
    assert hasattr(repo, "engine")
    assert hasattr(repo, "metadata")
    assert isinstance(repo._tables, dict)

def test_normalize_mysql_scalar_handles_none_and_pd(monkeypatch):
    import pandas as pd
    assert db_io.EventSentimentRepository._normalize_mysql_scalar(None) is None
    assert db_io.EventSentimentRepository._normalize_mysql_scalar(pd.NaT) is None
    assert db_io.EventSentimentRepository._normalize_mysql_scalar(5) == 5

def test_normalize_mysql_records():
    records = [{"a": None, "b": 1}, {"a": 2, "b": None}]
    repo = db_io.EventSentimentRepository()
    norm = repo._normalize_mysql_records(records)
    assert norm[0]["a"] is None and norm[0]["b"] == 1
    assert norm[1]["a"] == 2 and norm[1]["b"] is None
