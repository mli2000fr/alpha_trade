import pandas as pd
from event_sentiment.aggregation import build_sector_daily_features, build_ticker_daily_features
def test_ticker_aggregation_basic() -> None:
    ticker_df = pd.DataFrame([
        {
            "article_id": "a1",
            "effective_trade_date": "2026-01-02",
            "event_timestamp_ny": "2026-01-01 17:00:00",
            "market_session_tag": "post_market",
            "source": "Reuters",
            "is_major_event": 1,
            "symbol": "AAPL",
            "sector": "Technology",
            "sentiment_label": "positive",
            "positive_score": 0.9,
            "neutral_score": 0.08,
            "negative_score": 0.02,
            "sentiment_confidence": 0.9,
            "sentiment_net_score": 0.88,
        }
    ])
    result = build_ticker_daily_features(ticker_df)
    assert result.loc[0, "symbol"] == "AAPL"
    assert result.loc[0, "news_count_1d"] == 1
    assert result.loc[0, "after_close_news_count"] == 1
def test_sector_aggregation_deduplicates_same_article_same_sector() -> None:
    sector_df = pd.DataFrame([
        {
            "article_id": "a1",
            "effective_trade_date": "2026-01-02",
            "event_timestamp_ny": "2026-01-01 17:00:00",
            "market_session_tag": "post_market",
            "source": "Reuters",
            "is_major_event": 1,
            "sector": "Technology",
            "sentiment_label": "positive",
            "sentiment_confidence": 0.9,
            "sentiment_net_score": 0.88,
        },
        {
            "article_id": "a1",
            "effective_trade_date": "2026-01-02",
            "event_timestamp_ny": "2026-01-01 17:00:00",
            "market_session_tag": "post_market",
            "source": "Reuters",
            "is_major_event": 1,
            "sector": "Technology",
            "sentiment_label": "positive",
            "sentiment_confidence": 0.9,
            "sentiment_net_score": 0.88,
        },
    ])
    macro_df = pd.DataFrame([
        {
            "article_id": "a1",
            "trade_date": "2026-01-02",
            "sector": "Technology",
            "macro_event_type": "monetary_policy",
            "impact_direction": "positive",
            "impact_score": 0.4,
            "macro_event_intensity": 0.4,
        }
    ])
    result = build_sector_daily_features(sector_df, macro_df)
    assert result.loc[0, "sector_news_count_1d"] == 1
    assert result.loc[0, "macro_event_flag"] == 1
