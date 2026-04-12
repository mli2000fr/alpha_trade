CREATE TABLE alpha_trade.stock_bars (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,          -- 股票代碼 (如 AAPL, NVDA)
    timeframe VARCHAR(5) NOT NULL,       -- 數據頻率 (如 1D, 1H, 15M)
    `timestamp` DATETIME NOT NULL,         -- 時間戳
    open_price DECIMAL(16, 4) NOT NULL,  -- 開盤價
    high_price DECIMAL(16, 4) NOT NULL,  -- 最高價
    low_price DECIMAL(16, 4) NOT NULL,   -- 最低價
    close_price DECIMAL(16, 4) NOT NULL, -- 收盤價
    volume BIGINT NOT NULL,              -- 成交量

    -- 建立複合索引加速查詢：這對回測至關重要
    UNIQUE KEY unique_bar (symbol, timeframe, timestamp),
    INDEX idx_lookup (symbol, timestamp)
) ENGINE=InnoDB;
