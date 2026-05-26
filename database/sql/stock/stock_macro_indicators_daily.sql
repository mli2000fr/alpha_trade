CREATE TABLE IF NOT EXISTS alpha_trade.stock_macro_indicators_daily (
    trade_date  DATE      NOT NULL,
    vix         DOUBLE    DEFAULT NULL,
    vix9d       DOUBLE    DEFAULT NULL,
    ten_y       DOUBLE    DEFAULT NULL,
    created_at  DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (trade_date),
    INDEX idx_stock_macro_indicators_daily_vix (vix),
    INDEX idx_stock_macro_indicators_daily_vix9d (vix9d),
    INDEX idx_stock_macro_indicators_daily_ten_y (ten_y)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Historique quotidien des indicateurs macro VIX, VIX9D et taux US 10Y';

