CREATE TABLE IF NOT EXISTS alpha_trade.stock_metadata (
    symbol VARCHAR(100) PRIMARY KEY,
    id_alpaca VARCHAR(88),
    company_name VARCHAR(255),
    exchange VARCHAR(20),
    asset_class VARCHAR(20),      -- 資產類別 (us_equity)
    status VARCHAR(20),           -- 狀態 (active/inactive)
    tradable BOOLEAN,             -- 是否可交易
    bars_available BOOLEAN,        -- 是否有K線數據
    history_status VARCHAR(32) DEFAULT 'pending', -- pending | ready | no_history | provider_error | suspended_or_stale | excluded_by_policy
    sector VARCHAR(50),                     -- 存儲板塊，用於模塊四的「板塊中性化」
    provider_sector VARCHAR(120) NULL,
    market_cap DOUBLE DEFAULT NULL,         -- Capitalisation boursière (USD) synchronisée depuis Finnhub
    -- Provenance & TTL (Phase 1 refactor — audit_global.md §6 et audit_selector.md).
    data_source VARCHAR(16) DEFAULT NULL COMMENT 'Source primaire metadata : finnhub | alpaca | manual',
    market_cap_refreshed_at DATETIME DEFAULT NULL COMMENT 'Dernier refresh market_cap (TTL filtre selector)',
    metadata_synced_at DATETIME DEFAULT NULL COMMENT 'Dernier refresh metadata Finnhub',
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);


