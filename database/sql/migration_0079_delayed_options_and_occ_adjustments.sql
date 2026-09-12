CREATE TABLE IF NOT EXISTS alpha_trade.stock_option_contract_versions (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, provider VARCHAR(32) NOT NULL,
 contract_symbol VARCHAR(64) NOT NULL, underlying_symbol VARCHAR(32) NOT NULL,
 root_symbol VARCHAR(32), status VARCHAR(24), expiration_date DATE, strike DOUBLE,
 option_type VARCHAR(8), exercise_style VARCHAR(16), multiplier DOUBLE, contract_size DOUBLE,
 open_interest BIGINT, open_interest_date DATE, close_price DOUBLE, close_price_date DATE,
 deliverables_json LONGTEXT, observed_at DATETIME(6) NOT NULL, available_at DATETIME(6) NOT NULL,
 payload_hash VARCHAR(64) NOT NULL, run_id VARCHAR(64) NOT NULL,
 UNIQUE KEY uq_socv_provider_contract_hash(provider,contract_symbol,payload_hash),
 INDEX idx_socv_underlying_available(underlying_symbol,available_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alpha_trade.stock_option_bars_delayed (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, provider VARCHAR(32) NOT NULL, feed VARCHAR(32) NOT NULL,
 provenance_status VARCHAR(32) NOT NULL, underlying_symbol VARCHAR(32) NOT NULL,
 contract_symbol VARCHAR(64) NOT NULL, expiration_date DATE, strike DOUBLE, option_type VARCHAR(8),
 timeframe VARCHAR(12) NOT NULL, bar_timestamp DATETIME(6) NOT NULL,
 observed_at DATETIME(6) NOT NULL, available_at DATETIME(6) NOT NULL,
 open DOUBLE NOT NULL, high DOUBLE NOT NULL, low DOUBLE NOT NULL, close DOUBLE NOT NULL,
 volume BIGINT, trade_count BIGINT, vwap DOUBLE, payload_hash VARCHAR(64) NOT NULL,
 run_id VARCHAR(64) NOT NULL,
 UNIQUE KEY uq_sobd_identity_hash(provider,feed,contract_symbol,timeframe,bar_timestamp,payload_hash),
 INDEX idx_sobd_underlying_time(underlying_symbol,bar_timestamp),
 INDEX idx_sobd_available(provider,available_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alpha_trade.option_contract_adjustments (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, provider VARCHAR(32) NOT NULL,
 occ_memo_number VARCHAR(16) NOT NULL, published_at DATETIME(6), effective_at DATETIME(6),
 category VARCHAR(128), title VARCHAR(1024) NOT NULL, source_url VARCHAR(1024),
 adjustment_type VARCHAR(32), old_option_root VARCHAR(64), new_option_root VARCHAR(64),
 observed_at DATETIME(6) NOT NULL, available_at DATETIME(6) NOT NULL,
 payload_hash VARCHAR(64) NOT NULL, run_id VARCHAR(64) NOT NULL,
 UNIQUE KEY uq_oca_provider_memo_hash(provider,occ_memo_number,payload_hash),
 INDEX idx_oca_published(published_at), INDEX idx_oca_roots(old_option_root,new_option_root)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
