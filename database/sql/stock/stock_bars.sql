

CREATE TABLE IF NOT EXISTS alpha_trade.stock_bars (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    timeframe VARCHAR(5) NOT NULL,
    `timestamp` DATETIME NOT NULL,
    open_price DECIMAL(20, 8) NOT NULL,
    high_price DECIMAL(20, 8) NOT NULL,
    low_price DECIMAL(20, 8) NOT NULL,
    close_price DECIMAL(20, 8) NOT NULL,
    trade_count DECIMAL(20, 8) NOT NULL,
    volume BIGINT NOT NULL,
    vwa_price DECIMAL(20, 8) NOT NULL,
    UNIQUE KEY unique_bar (symbol, timeframe, timestamp),
    INDEX idx_lookup (symbol, timestamp)
) ENGINE=InnoDB;