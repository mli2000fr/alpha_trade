CREATE TABLE alpha_trade.stock_bars_daily (
    -- 識別信息
    `symbol` VARCHAR(20) NOT NULL COMMENT '股票代碼，如 AAPL',
    `date` DATE NOT NULL COMMENT '交易日期',
    -- 標準 OHLCV 數據 (使用 DECIMAL 確保價格精準度，避免浮點數誤差)
    `open` DECIMAL(20, 8) NOT NULL,
    `high` DECIMAL(20, 8) NOT NULL,
    `low` DECIMAL(20, 8) NOT NULL,
    `close` DECIMAL(20, 8) NOT NULL,
    `volume` BIGINT UNSIGNED NOT NULL COMMENT '原始成交量',
    -- 量化專用字段
    `adj_close` DECIMAL(20, 8) NOT NULL COMMENT '復權收盤價 (Adjusted Close)',
    `vwap` DECIMAL(20, 8) DEFAULT NULL COMMENT '成交量加權平均價',
    `daily_return` DECIMAL(10, 6) DEFAULT NULL COMMENT '當日漲跌幅 (Close/Prev_Close - 1)',
    -- 數據完整性標記
    `is_filled` TINYINT(1) DEFAULT 0 COMMENT '0:真實數據, 1:停牌補全數據',
    `last_updated` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    -- 核心索引設計
    -- 1. 聯合主鍵：確保 (股票 + 日期) 唯一，且物理上按股票聚合存放，極大提升單個股票的歷史查詢速度
    PRIMARY KEY (`symbol`, `date`),
    -- 2. 日期索引：方便進行「全市場掃描」，例如查詢 2024-01-01 當天所有漲幅大於 5% 的股票
    INDEX `idx_date` (`date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 ROW_FORMAT=COMPRESSED COMMENT='Alpha Prime 每日行情數據表';