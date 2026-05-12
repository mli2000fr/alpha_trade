from datetime import date

from sqlalchemy import create_engine, text

from service.market.sentiment_provider import DbSentimentScoreProvider, load_market_sentiment_reading


def test_load_market_sentiment_reading_uses_ticker_features_first() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE ticker_daily_sentiment_features (
                symbol TEXT,
                trade_date TEXT,
                news_count_1d INTEGER,
                sentiment_net_mean_1d REAL
            )
        """))
        conn.execute(text("""
            INSERT INTO ticker_daily_sentiment_features(symbol, trade_date, news_count_1d, sentiment_net_mean_1d)
            VALUES
                ('AAPL', '2025-05-01', 3, -0.50),
                ('MSFT', '2025-05-02', 1, 0.10)
        """))

    reading = load_market_sentiment_reading(date(2025, 5, 2), 5, engine=engine)

    assert reading.source == "ticker_daily_sentiment_features"
    assert reading.data_quality == "ok"
    assert reading.total_news_count == 4
    assert reading.score == (-1.5 + 0.1) / 4


def test_load_market_sentiment_reading_falls_back_to_sector_features() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE sector_daily_sentiment_features (
                sector TEXT,
                trade_date TEXT,
                sector_news_count_1d INTEGER,
                sector_sentiment_net_mean_1d REAL
            )
        """))
        conn.execute(text("""
            INSERT INTO sector_daily_sentiment_features(sector, trade_date, sector_news_count_1d, sector_sentiment_net_mean_1d)
            VALUES
                ('Technology', '2025-05-02', 2, -0.30),
                ('Healthcare', '2025-05-02', 1, 0.30)
        """))

    reading = load_market_sentiment_reading(date(2025, 5, 2), 3, engine=engine)

    assert reading.source == "sector_daily_sentiment_features"
    assert reading.data_quality == "ok"
    assert reading.total_news_count == 3
    assert reading.score == (-0.6 + 0.3) / 3


def test_db_sentiment_score_provider_caches_last_reading() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE ticker_daily_sentiment_features (
                symbol TEXT,
                trade_date TEXT,
                news_count_1d INTEGER,
                sentiment_net_mean_1d REAL
            )
        """))
        conn.execute(text("""
            INSERT INTO ticker_daily_sentiment_features(symbol, trade_date, news_count_1d, sentiment_net_mean_1d)
            VALUES ('AAPL', '2025-05-02', 2, -0.25)
        """))

    provider = DbSentimentScoreProvider(date(2025, 5, 2), engine=engine)

    first = provider(7)
    second = provider(7)

    assert first == -0.25
    assert second == -0.25
    assert provider.last_reading is not None
    assert provider.last_reading.source == "ticker_daily_sentiment_features"
    assert provider.last_reading.lookback_days == 7

