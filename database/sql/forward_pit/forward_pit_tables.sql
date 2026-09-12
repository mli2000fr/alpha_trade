-- Forward PIT collection foundation (migration 0075).
CREATE TABLE IF NOT EXISTS alpha_trade.pit_collection_runs (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, run_id VARCHAR(64) NOT NULL UNIQUE,
 batch_name VARCHAR(64) NOT NULL, provider VARCHAR(32), status VARCHAR(24) NOT NULL,
 started_at DATETIME(6) NOT NULL, finished_at DATETIME(6), requested_count INT DEFAULT 0,
 received_count INT DEFAULT 0, persisted_count INT DEFAULT 0, empty_count INT DEFAULT 0,
 failed_count INT DEFAULT 0, warning_count INT DEFAULT 0, schema_hash VARCHAR(64),
 error_message TEXT, details_json LONGTEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_pcr_batch_started(batch_name, started_at), INDEX idx_pcr_status(status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alpha_trade.pit_raw_payloads (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, run_id VARCHAR(64) NOT NULL, batch_name VARCHAR(64) NOT NULL,
 provider VARCHAR(32) NOT NULL, endpoint VARCHAR(128) NOT NULL, entity_key VARCHAR(128),
 observed_at DATETIME(6) NOT NULL, available_at DATETIME(6) NOT NULL,
 http_status SMALLINT, payload_hash VARCHAR(64) NOT NULL, schema_hash VARCHAR(64),
 payload_json LONGTEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY uq_prp_run_provider_endpoint_entity(run_id, provider, endpoint, entity_key),
 INDEX idx_prp_run(run_id), INDEX idx_prp_available(provider, available_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alpha_trade.stock_bars_daily_versions (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, provider VARCHAR(32) NOT NULL, symbol VARCHAR(32) NOT NULL,
 trade_date DATE NOT NULL, observed_at DATETIME(6) NOT NULL, available_at DATETIME(6) NOT NULL,
 open DOUBLE NOT NULL, high DOUBLE NOT NULL, low DOUBLE NOT NULL, close DOUBLE NOT NULL,
 volume BIGINT, provider_timestamp DATETIME(6), payload_hash VARCHAR(64) NOT NULL,
 adjustment_mode VARCHAR(16) NOT NULL DEFAULT 'raw',
 run_id VARCHAR(64) NOT NULL, is_correction BOOLEAN NOT NULL DEFAULT 0,
 UNIQUE KEY uq_sbdv_provider_symbol_date_hash(provider, symbol, trade_date, payload_hash),
 INDEX idx_sbdv_symbol_date(symbol, trade_date), INDEX idx_sbdv_available(available_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alpha_trade.security_master_snapshots (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, provider VARCHAR(32) NOT NULL, snapshot_date DATE NOT NULL,
 observed_at DATETIME(6) NOT NULL, available_at DATETIME(6) NOT NULL, symbol VARCHAR(32) NOT NULL,
 cik VARCHAR(10), cusip VARCHAR(16), company_name VARCHAR(255), exchange VARCHAR(32),
 security_type VARCHAR(64), asset_class VARCHAR(32), etf_flag BOOLEAN, test_issue BOOLEAN,
 listing_status VARCHAR(32), sector VARCHAR(120), industry VARCHAR(160), raw_hash VARCHAR(64),
 run_id VARCHAR(64) NOT NULL, UNIQUE KEY uq_sms_provider_date_symbol(provider, snapshot_date, symbol),
 INDEX idx_sms_symbol_date(symbol, snapshot_date), INDEX idx_sms_cik(cik)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alpha_trade.security_master_changes (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, provider VARCHAR(32) NOT NULL, detected_date DATE NOT NULL,
 symbol VARCHAR(32) NOT NULL, change_type VARCHAR(48) NOT NULL, previous_value TEXT,
 current_value TEXT, confirmed BOOLEAN NOT NULL DEFAULT 0, run_id VARCHAR(64) NOT NULL,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY uq_smc_provider_date_symbol_type(provider, detected_date, symbol, change_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alpha_trade.corporate_action_source_events (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, provider VARCHAR(32) NOT NULL, provider_event_id VARCHAR(128),
 symbol VARCHAR(32) NOT NULL, action_type VARCHAR(48) NOT NULL, effective_date DATE NOT NULL,
 value_num DOUBLE, related_symbol VARCHAR(32), related_name VARCHAR(255), notes TEXT,
 observed_at DATETIME(6) NOT NULL, available_at DATETIME(6) NOT NULL, payload_hash VARCHAR(64) NOT NULL,
 run_id VARCHAR(64) NOT NULL, conflict_group_key VARCHAR(64),
 UNIQUE KEY uq_case_provider_symbol_type_date_hash(provider, symbol, action_type, effective_date, payload_hash),
 INDEX idx_case_symbol_date(symbol, effective_date), INDEX idx_case_conflict(conflict_group_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alpha_trade.sec_filing_raw (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, accession_number VARCHAR(32) NOT NULL UNIQUE,
 cik VARCHAR(10) NOT NULL, symbol VARCHAR(32), company_name VARCHAR(255), form_type VARCHAR(24) NOT NULL,
 filing_date DATE NOT NULL, acceptance_datetime DATETIME(6), primary_document VARCHAR(255),
 filing_url VARCHAR(512), content_sha256 VARCHAR(64), content_text LONGTEXT,
 observed_at DATETIME(6) NOT NULL, available_at DATETIME(6) NOT NULL, run_id VARCHAR(64) NOT NULL,
 amendment BOOLEAN NOT NULL DEFAULT 0, INDEX idx_sfr_cik_filing(cik, filing_date),
 INDEX idx_sfr_form_available(form_type, available_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alpha_trade.stock_borrow_status_snapshots (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, provider VARCHAR(32) NOT NULL, symbol VARCHAR(32) NOT NULL,
 observed_at DATETIME(6) NOT NULL, available_at DATETIME(6) NOT NULL, shortable BOOLEAN,
 easy_to_borrow BOOLEAN, marginable BOOLEAN, tradable BOOLEAN, status VARCHAR(32),
 borrow_status VARCHAR(32), payload_hash VARCHAR(64), run_id VARCHAR(64) NOT NULL,
 UNIQUE KEY uq_sbss_provider_symbol_observed(provider, symbol, observed_at),
 INDEX idx_sbss_symbol_available(symbol, available_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alpha_trade.stock_analyst_consensus_snapshots (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, provider VARCHAR(32) NOT NULL, symbol VARCHAR(32) NOT NULL,
 metric VARCHAR(16) NOT NULL, dimension_name VARCHAR(16), fiscal_period VARCHAR(32) NOT NULL,
 data_type VARCHAR(16), consensus_value DOUBLE, high_value DOUBLE, low_value DOUBLE,
 actual_value DOUBLE, observed_at DATETIME(6) NOT NULL, available_at DATETIME(6) NOT NULL,
 payload_hash VARCHAR(64), run_id VARCHAR(64) NOT NULL,
 UNIQUE KEY uq_sacs_provider_symbol_metric_period_obs(provider, symbol, metric, fiscal_period, observed_at),
 INDEX idx_sacs_symbol_available(symbol, available_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alpha_trade.stock_option_snapshots (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, provider VARCHAR(32) NOT NULL, feed VARCHAR(24) NOT NULL,
 underlying_symbol VARCHAR(32) NOT NULL, contract_symbol VARCHAR(64) NOT NULL,
 expiration_date DATE, strike DOUBLE, option_type VARCHAR(8), observed_at DATETIME(6) NOT NULL,
 available_at DATETIME(6) NOT NULL, provider_timestamp DATETIME(6), bid DOUBLE, ask DOUBLE,
 bid_size DOUBLE, ask_size DOUBLE, trade_price DOUBLE, trade_size DOUBLE, implied_volatility DOUBLE,
 delta DOUBLE, gamma DOUBLE, theta DOUBLE, vega DOUBLE, open_interest BIGINT, volume BIGINT,
 payload_hash VARCHAR(64), run_id VARCHAR(64) NOT NULL,
 UNIQUE KEY uq_sos_provider_feed_contract_observed(provider, feed, contract_symbol, observed_at),
 INDEX idx_sos_underlying_available(underlying_symbol, available_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alpha_trade.stock_opening_window_bars (
 provider VARCHAR(32) NOT NULL, symbol VARCHAR(32) NOT NULL, bar_timestamp DATETIME(6) NOT NULL,
 observed_at DATETIME(6) NOT NULL, available_at DATETIME(6) NOT NULL,
 open DOUBLE NOT NULL, high DOUBLE NOT NULL, low DOUBLE NOT NULL, close DOUBLE NOT NULL,
 cumulative_volume BIGINT, minute_volume BIGINT, session_name VARCHAR(16), payload_hash VARCHAR(64),
 run_id VARCHAR(64) NOT NULL, PRIMARY KEY(provider, symbol, bar_timestamp),
 INDEX idx_sowb_available(available_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alpha_trade.sec_corporate_events (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, accession_number VARCHAR(32) NOT NULL, cik VARCHAR(10) NOT NULL,
 symbol VARCHAR(32), form_type VARCHAR(24) NOT NULL, item_code VARCHAR(16) NOT NULL,
 event_type VARCHAR(64), event_text LONGTEXT, filing_date DATE NOT NULL,
 acceptance_datetime DATETIME(6), available_at DATETIME(6) NOT NULL, amendment BOOLEAN DEFAULT 0,
 content_sha256 VARCHAR(64), run_id VARCHAR(64) NOT NULL,
 UNIQUE KEY uq_sce_accession_item(accession_number, item_code), INDEX idx_sce_symbol_available(symbol, available_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alpha_trade.sec_ownership_snapshots (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, accession_number VARCHAR(32) NOT NULL, form_type VARCHAR(24) NOT NULL,
 filer_cik VARCHAR(10) NOT NULL, issuer_cik VARCHAR(10), issuer_name VARCHAR(255), issuer_symbol VARCHAR(32),
 cusip VARCHAR(16), report_period DATE, acceptance_datetime DATETIME(6), available_at DATETIME(6) NOT NULL,
 shares DOUBLE, value_usd DOUBLE, put_call VARCHAR(8), ownership_pct DOUBLE, amendment BOOLEAN DEFAULT 0,
 payload_hash VARCHAR(64), run_id VARCHAR(64) NOT NULL,
 UNIQUE KEY uq_sos_accession_issuer_cusip_put(accession_number, issuer_name, cusip, put_call),
 INDEX idx_ownership_issuer_available(issuer_symbol, available_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alpha_trade.macro_vintage_observations (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, provider VARCHAR(16) NOT NULL, series_id VARCHAR(32) NOT NULL,
 observation_date DATE NOT NULL, value_num DOUBLE, value_raw VARCHAR(64), realtime_start DATE NOT NULL,
 realtime_end DATE NOT NULL, vintage_date DATE NOT NULL, observed_at DATETIME(6) NOT NULL,
 available_at DATETIME(6) NOT NULL, run_id VARCHAR(64) NOT NULL,
 UNIQUE KEY uq_mvo_provider_series_obs_vintage(provider, series_id, observation_date, vintage_date),
 INDEX idx_mvo_series_available(series_id, available_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alpha_trade.pit_data_quality_metrics (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, metric_date DATE NOT NULL, batch_name VARCHAR(64) NOT NULL,
 provider VARCHAR(32), metric_name VARCHAR(96) NOT NULL, metric_value DOUBLE,
 threshold_value DOUBLE, status VARCHAR(16) NOT NULL, details_json LONGTEXT,
 run_id VARCHAR(64) NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY uq_pdqm_date_batch_provider_metric(metric_date, batch_name, provider, metric_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alpha_trade.pit_data_quality_issues (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, detected_at DATETIME(6) NOT NULL, severity VARCHAR(16) NOT NULL,
 batch_name VARCHAR(64) NOT NULL, provider VARCHAR(32), entity_key VARCHAR(128), issue_type VARCHAR(64) NOT NULL,
 message TEXT NOT NULL, details_json LONGTEXT, status VARCHAR(16) NOT NULL DEFAULT 'OPEN',
 run_id VARCHAR(64) NOT NULL, resolved_at DATETIME(6), INDEX idx_pdqi_status_severity(status, severity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alpha_trade.stock_short_volume_daily (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, provider VARCHAR(32) NOT NULL,
 trade_date DATE NOT NULL, symbol VARCHAR(32) NOT NULL, market VARCHAR(16) NOT NULL,
 short_volume BIGINT NOT NULL, short_exempt_volume BIGINT NOT NULL,
 total_volume BIGINT NOT NULL, observed_at DATETIME(6) NOT NULL,
 available_at DATETIME(6) NOT NULL, payload_hash VARCHAR(64) NOT NULL,
 run_id VARCHAR(64) NOT NULL, is_correction BOOLEAN NOT NULL DEFAULT 0,
 UNIQUE KEY uq_ssvd_provider_date_symbol_market_hash
   (provider, trade_date, symbol, market, payload_hash),
 INDEX idx_ssvd_symbol_available(symbol, available_at),
 INDEX idx_ssvd_trade_date(trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
