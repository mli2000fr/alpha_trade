CREATE TABLE IF NOT EXISTS alpha_trade.stock_bars (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(5) NOT NULL COMMENT '1D, 1H, 30M, ...',
    `timestamp` DATETIME NOT NULL COMMENT 'Horodatage RTH normalisé America/New_York',
    open_price DECIMAL(20, 8) NOT NULL,
    high_price DECIMAL(20, 8) NOT NULL,
    low_price DECIMAL(20, 8) NOT NULL,
    close_price DECIMAL(20, 8) NOT NULL,
    volume BIGINT UNSIGNED NOT NULL,
    trade_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
    vwa_price DECIMAL(20, 8) NULL,
    ingested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_stock_bars_symbol_timeframe_timestamp (symbol, timeframe, `timestamp`),
    KEY idx_stock_bars_symbol_timestamp (symbol, `timestamp`),
    KEY idx_stock_bars_timeframe_symbol_timestamp (timeframe, symbol, `timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
