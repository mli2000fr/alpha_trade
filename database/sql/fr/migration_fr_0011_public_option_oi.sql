-- Anonymous public Euronext observations, not an official licensed OI feed.
CREATE TABLE IF NOT EXISTS fr_option_oi_public_runs (
 run_id VARCHAR(96) NOT NULL PRIMARY KEY,
 market_code VARCHAR(16) NOT NULL DEFAULT 'FR_EQ',
 started_at DATETIME(6) NOT NULL,
 finished_at DATETIME(6) NULL,
 status VARCHAR(16) NOT NULL,
 config_json JSON NOT NULL,
 details_json JSON NOT NULL,
 CONSTRAINT ck_fr_public_oi_run_scope CHECK (market_code='FR_EQ')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_option_oi_public_responses (
 response_id CHAR(64) NOT NULL PRIMARY KEY,
 run_id VARCHAR(96) NOT NULL,
 endpoint TEXT NOT NULL,
 method VARCHAR(4) NOT NULL,
 request_json JSON NOT NULL,
 http_status INT NOT NULL,
 body_sha256 CHAR(64) NOT NULL,
 body LONGBLOB NOT NULL,
 observed_at DATETIME(6) NOT NULL,
 available_at DATETIME(6) NULL,
 parse_status VARCHAR(24) NOT NULL,
 KEY ix_fr_public_oi_response_run (run_id),
 CONSTRAINT fk_fr_public_oi_response_run FOREIGN KEY(run_id) REFERENCES fr_option_oi_public_runs(run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_option_oi_public_contracts (
 response_id CHAR(64) NOT NULL,
 contract_key CHAR(64) NOT NULL,
 symbol VARCHAR(32) NOT NULL,
 underlying_isin CHAR(12) NOT NULL,
 product_code VARCHAR(32) NOT NULL,
 venue VARCHAR(8) NOT NULL,
 option_type VARCHAR(4) NOT NULL,
 strike DECIMAL(38,12) NOT NULL,
 maturity_selector VARCHAR(16) NOT NULL,
 expiry_month DATE NOT NULL,
 expiration_date DATE NULL,
 contract_isin CHAR(12) NULL,
 oi_raw VARCHAR(128) NULL,
 open_interest BIGINT UNSIGNED NULL,
 oi_reference_date DATE NULL,
 volume_date DATE NULL,
 daily_volume_raw VARCHAR(128) NULL,
 daily_volume BIGINT UNSIGNED NULL,
 settlement_price DECIMAL(38,12) NULL,
 quality_status VARCHAR(24) NOT NULL,
 quality_json JSON NOT NULL,
 raw_row_json JSON NOT NULL,
 ml_eligible BOOLEAN NOT NULL DEFAULT FALSE,
 PRIMARY KEY (response_id,contract_key),
 KEY ix_fr_public_oi_contract_lookup (symbol,expiry_month,option_type,strike),
 CONSTRAINT fk_fr_public_oi_contract_response FOREIGN KEY(response_id)
  REFERENCES fr_option_oi_public_responses(response_id),
 CONSTRAINT ck_fr_public_oi_contract_scope CHECK
  (option_type IN ('CALL','PUT') AND ml_eligible=0 AND expiration_date IS NULL AND oi_reference_date IS NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
