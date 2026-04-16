CREATE TABLE IF NOT EXISTS alpha_trade.sector_daily_sentiment_features (
    sector VARCHAR(100) NOT NULL,
    trade_date DATE NOT NULL,
    sector_news_count_1d INT NOT NULL DEFAULT 0,
    sector_sentiment_net_mean_1d DOUBLE NOT NULL DEFAULT 0,
    sector_sentiment_net_sum_1d DOUBLE NOT NULL DEFAULT 0,
    sector_positive_ratio DOUBLE NOT NULL DEFAULT 0,
    sector_negative_ratio DOUBLE NOT NULL DEFAULT 0,
    sector_impact_score DOUBLE NOT NULL DEFAULT 0,
    macro_event_flag TINYINT(1) NOT NULL DEFAULT 0,
    macro_event_intensity DOUBLE NOT NULL DEFAULT 0,
    latest_event_timestamp_ny DATETIME(6) NULL,
    feature_version VARCHAR(30) NOT NULL DEFAULT 'v1',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (sector, trade_date),
    KEY idx_sector_daily_trade_date (trade_date, sector),
    KEY idx_sector_daily_macro_flag (trade_date, macro_event_flag)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

