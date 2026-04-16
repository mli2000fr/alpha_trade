CREATE TABLE IF NOT EXISTS alpha_trade.ticker_daily_sentiment_features (
    symbol VARCHAR(100) NOT NULL,
    trade_date DATE NOT NULL,
    news_count_1d INT NOT NULL DEFAULT 0,
    sentiment_pos_mean_1d DOUBLE NOT NULL DEFAULT 0,
    sentiment_neg_mean_1d DOUBLE NOT NULL DEFAULT 0,
    sentiment_neu_mean_1d DOUBLE NOT NULL DEFAULT 0,
    sentiment_net_mean_1d DOUBLE NOT NULL DEFAULT 0,
    sentiment_net_sum_1d DOUBLE NOT NULL DEFAULT 0,
    sentiment_confidence_mean_1d DOUBLE NOT NULL DEFAULT 0,
    major_event_flag TINYINT(1) NOT NULL DEFAULT 0,
    source_diversity_count INT NOT NULL DEFAULT 0,
    after_close_news_count INT NOT NULL DEFAULT 0,
    pre_market_news_count INT NOT NULL DEFAULT 0,
    latest_event_timestamp_ny DATETIME(6) NULL,
    feature_version VARCHAR(30) NOT NULL DEFAULT 'v1',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, trade_date),
    KEY idx_ticker_daily_trade_date (trade_date, symbol),
    KEY idx_ticker_daily_major_event (trade_date, major_event_flag)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

