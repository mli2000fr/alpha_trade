CREATE TABLE IF NOT EXISTS alpha_trade.stock_ipo_eodhd_history (
 id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
 symbol VARCHAR(32) NOT NULL,
 provider_code VARCHAR(40) NOT NULL,
 company_name TEXT,
 exchange_name VARCHAR(128),
 currency VARCHAR(16),
 start_date DATE NULL,
 filing_date DATE NULL,
 amended_date DATE NULL,
 deal_type VARCHAR(32),
 price_from DOUBLE NULL,
 price_to DOUBLE NULL,
 offer_price DOUBLE NULL,
 offered_shares DOUBLE NULL,
 snapshot_date DATE NOT NULL,
 observed_at DATETIME(6) NOT NULL,
 available_at DATETIME(6) NOT NULL,
 run_id VARCHAR(96) NOT NULL,
 historical_pit_qualified BOOLEAN NOT NULL DEFAULT FALSE,
 raw_hash CHAR(64) NOT NULL,
 raw_payload_json LONGTEXT NOT NULL,
 UNIQUE KEY uq_ipo_version (symbol,snapshot_date,raw_hash),
 KEY ix_ipo_date (symbol,start_date),
 KEY ix_ipo_run (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alpha_trade.eodhd_ipo_collection_windows (
 window_start DATE NOT NULL,
 window_end DATE NOT NULL,
 universe_hash CHAR(64) NOT NULL,
 completed_at DATETIME(6) NOT NULL,
 run_id VARCHAR(96) NOT NULL,
 PRIMARY KEY (window_start,window_end,universe_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
