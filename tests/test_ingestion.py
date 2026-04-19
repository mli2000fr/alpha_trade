import pytest
from event_sentiment import ingestion

def test_news_ingestion_service_normalize_article():
    class DummyAligner:
        def align(self, dt):
            class Alignment:
                event_timestamp_utc = dt
                event_timestamp_ny = dt
                effective_trade_date = dt.date()
                market_session_tag = "regular"
            return Alignment()
    class DummyConfig:
        provider_name = "alpaca"
        regular_session_maps_to_same_day = False
    service = ingestion.NewsIngestionService(repository=None, config=DummyConfig())
    service.aligner = DummyAligner()
    payload = {
        "id": "123",
        "created_at": "2026-04-19T12:00:00Z",
        "symbols": ["AAPL"],
        "headline": "Titre",
        "source": "Reuters"
    }
    article = service._normalize_article(payload)
    assert article.article_id.startswith("alpaca:123")
    assert article.headline == "Titre"
    assert article.tickers == ["AAPL"] or article.tickers == ["AAPL"]  # selon nom du champ
