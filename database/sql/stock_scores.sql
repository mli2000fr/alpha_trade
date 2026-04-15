
CREATE TABLE alpha_trade.stock_scores (
    symbol VARCHAR(20) NOT NULL,
    liquidity_val DOUBLE NOT NULL,          -- 成交額過濾
    relative_strength_index DOUBLE NOT NULL, -- RS 排名
    historical_range_score DOUBLE NOT NULL,  -- VCP 壓縮評分
    total_score DOUBLE NOT NULL,            -- 綜合因子權重
    last_updated_score DATETIME NOT NULL,   -- 分數計算時間
    is_candidate TINYINT(1) DEFAULT 0,      -- 取代 top_swing, 1為入選, 0為落選
    sector VARCHAR(50),                     -- 存儲板塊，用於模塊四的「板塊中性化」
    last_updated_scan DATETIME NOT NULL,    -- 掃描器標記時間
    anomaly_count INT DEFAULT 0,            -- 異常點數量 (來自清洗審核的 MAD 檢測結果)
    missing_days_count INT DEFAULT 0,       -- 被 Forward Fill 的天數
    last_updated_audit DATETIME NOT NULL,   -- 審核標記時間
    PRIMARY KEY (symbol),
    INDEX idx_total_score (total_score),
    INDEX idx_scan_candidate (is_candidate, total_score) -- 複合索引：加速模型推理時的讀取
) ENGINE=InnoDB;