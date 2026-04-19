from event_sentiment import macro_rules

def test_macro_rules_classification():
    from event_sentiment.models import NormalizedNewsArticle, SentimentRecord
    from datetime import datetime, date
    engine = macro_rules.MacroRuleEngine()
    article = NormalizedNewsArticle(
        article_id="alpaca:2",
        headline="Fed signals dovish pause after FOMC meeting",
        summary=None,
        content=None,
        source="Reuters",
        author=None,
        url=None,
        published_at_utc=datetime(2026, 1, 1),
        event_timestamp_utc=datetime(2026, 1, 1),
        event_timestamp_ny=datetime(2026, 1, 1),
        effective_trade_date=date(2026, 1, 2),
        market_session_tag="post_market",
    )
    sentiment = SentimentRecord(
        article_id="alpaca:2",
        model_name="ProsusAI/finbert",
        model_version="v1",
        text_strategy="headline_only",
        text_hash="x",
        truncated=0,
        max_length_tokens=256,
        sentiment_label="positive",
        positive_score=0.90,
        neutral_score=0.08,
        negative_score=0.02,
        sentiment_confidence=0.90,
        sentiment_net_score=0.88,
    )
    records = engine.classify(article, sentiment)
    assert records
    assert records[0].macro_event_type == "monetary_policy"
