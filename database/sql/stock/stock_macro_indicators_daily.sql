CREATE TABLE IF NOT EXISTS alpha_trade.stock_macro_indicators_daily (
    trade_date  DATE      NOT NULL,
    vix         DOUBLE    DEFAULT NULL,
    vix9d       DOUBLE    DEFAULT NULL,
    ten_y       DOUBLE    DEFAULT NULL,
    mode        VARCHAR(32) DEFAULT NULL,
    risk_multiplier DOUBLE DEFAULT NULL,
    effective_max_positions INT DEFAULT NULL,
    allow_new_entries TINYINT(1) DEFAULT NULL,
    vix_curve_inverted TINYINT(1) DEFAULT NULL,
    yield_10y_5d_pct DOUBLE DEFAULT NULL,
    sentiment_score DOUBLE DEFAULT NULL,
    sentiment_level VARCHAR(16) DEFAULT NULL,
    sentiment_source VARCHAR(64) DEFAULT NULL,
    created_at  DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (trade_date),
    INDEX idx_stock_macro_indicators_daily_vix (vix),
    INDEX idx_stock_macro_indicators_daily_vix9d (vix9d),
    INDEX idx_stock_macro_indicators_daily_ten_y (ten_y)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Historique quotidien des indicateurs macro et snapshots Régime Marché';

