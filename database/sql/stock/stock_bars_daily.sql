CREATE TABLE IF NOT EXISTS alpha_trade.stock_bars_daily (
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
    `adj_close` DECIMAL(20, 8) NOT NULL COMMENT '復權收盤價 (Adjusted Close) — égal à close car ingestion avec adjustment=split via Alpaca',
    `vwap` DECIMAL(20, 8) DEFAULT NULL COMMENT '成交量加權平均價',
    `daily_return` DECIMAL(10, 6) DEFAULT NULL COMMENT '當日漲跌幅 (Close/Prev_Close - 1)',
    -- 數據完整性標記
    `is_filled` TINYINT(1) DEFAULT 0 COMMENT '0:真實數據, 1:停牌補全數據',
    -- 數據版本控制 (P1 — Data Versioning)
    -- Permet de distinguer les re-ingestions et de tracer la source d'ajustement
    `ingested_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Horodatage UTC d insertion dans la table (pour versioning)',
    `data_adjustment` VARCHAR(20) NOT NULL DEFAULT 'split' COMMENT 'Paramètre adjustment Alpaca utilisé : raw | split | dividend | all',
    `data_source` VARCHAR(16) NOT NULL DEFAULT 'alpaca_iex' COMMENT 'Origine des barres journalières : alpaca_iex | alpaca_sip | eodhd_eod | stooq | yahoo ; sert au lineage/audit mais la PK actuelle impose une strategie de source unique active par (symbol,date)',
    `last_updated` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    -- 核心索引設計
    PRIMARY KEY (`symbol`, `date`),
    INDEX `idx_date` (`date`),
    INDEX `idx_ingested_at` (`ingested_at`) COMMENT 'Permet d auditer les lots de re-ingestion par plage de temps',
    CONSTRAINT chk_daily_adj CHECK (data_adjustment = 'split')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 ROW_FORMAT=COMPRESSED COMMENT='Alpha Prime 每日行情數據表';