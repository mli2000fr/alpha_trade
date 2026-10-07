-- Sprint 5 : structures vides uniquement. Aucune barre n'est importée tant que
-- le fournisseur, sa licence et sa couverture historique n'ont pas passé S3.
CREATE TABLE IF NOT EXISTS fr_source_versions (
  source_version_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  provider VARCHAR(64) NOT NULL,
  dataset VARCHAR(64) NOT NULL,
  provider_revision VARCHAR(128) NOT NULL,
  license_reference VARCHAR(512) NULL,
  observed_at DATETIME(6) NOT NULL,
  UNIQUE KEY uq_fr_source_version (provider,dataset,provider_revision)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_raw_payloads (
  raw_payload_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  run_id VARCHAR(96) NOT NULL,
  provider VARCHAR(64) NOT NULL,
  dataset VARCHAR(64) NOT NULL,
  request_key VARCHAR(255) NOT NULL,
  content_sha256 CHAR(64) NOT NULL,
  payload_uri VARCHAR(512) NOT NULL,
  observed_at DATETIME(6) NOT NULL,
  available_at DATETIME(6) NOT NULL,
  UNIQUE KEY uq_fr_raw_content (provider,dataset,request_key,content_sha256),
  KEY ix_fr_raw_run (run_id),
  CONSTRAINT fk_fr_raw_run FOREIGN KEY (run_id) REFERENCES fr_ingestion_runs(run_id),
  CONSTRAINT ck_fr_raw_pit CHECK (available_at>=observed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_provider_bars_daily (
  provider VARCHAR(64) NOT NULL,
  instrument_id BIGINT UNSIGNED NOT NULL,
  session_date DATE NOT NULL,
  source_revision VARCHAR(128) NOT NULL,
  currency CHAR(3) NOT NULL DEFAULT 'EUR',
  open_price DECIMAL(22,8) NOT NULL,
  high_price DECIMAL(22,8) NOT NULL,
  low_price DECIMAL(22,8) NOT NULL,
  close_price DECIMAL(22,8) NOT NULL,
  volume_shares BIGINT UNSIGNED NULL,
  provider_adjusted_close DECIMAL(22,8) NULL,
  raw_payload_id BIGINT UNSIGNED NOT NULL,
  observed_at DATETIME(6) NOT NULL,
  available_at DATETIME(6) NOT NULL,
  PRIMARY KEY (provider,instrument_id,session_date,source_revision),
  KEY ix_fr_provider_bars_day (session_date,instrument_id),
  CONSTRAINT fk_fr_provider_bar_instrument FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id),
  CONSTRAINT fk_fr_provider_bar_raw FOREIGN KEY (raw_payload_id) REFERENCES fr_raw_payloads(raw_payload_id),
  CONSTRAINT ck_fr_provider_bar_ohlc CHECK (low_price<=open_price AND low_price<=close_price AND high_price>=open_price AND high_price>=close_price AND low_price>0),
  CONSTRAINT ck_fr_provider_bar_pit CHECK (available_at>=observed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_corporate_actions (
  action_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  instrument_id BIGINT UNSIGNED NOT NULL,
  action_type VARCHAR(32) NOT NULL,
  ex_date DATE NOT NULL,
  cash_amount DECIMAL(22,8) NULL,
  split_numerator DECIMAL(22,8) NULL,
  split_denominator DECIMAL(22,8) NULL,
  currency CHAR(3) NULL,
  provider VARCHAR(64) NOT NULL,
  provider_event_id VARCHAR(128) NOT NULL,
  raw_payload_id BIGINT UNSIGNED NULL,
  observed_at DATETIME(6) NOT NULL,
  available_at DATETIME(6) NOT NULL,
  UNIQUE KEY uq_fr_action_source (provider,provider_event_id),
  KEY ix_fr_action_instrument_date (instrument_id,ex_date),
  CONSTRAINT fk_fr_action_instrument FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id),
  CONSTRAINT fk_fr_action_raw FOREIGN KEY (raw_payload_id) REFERENCES fr_raw_payloads(raw_payload_id),
  CONSTRAINT ck_fr_action_pit CHECK (available_at>=observed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_canonicalization_runs (
  canonicalization_run_id VARCHAR(96) NOT NULL PRIMARY KEY,
  rule_version VARCHAR(64) NOT NULL,
  status VARCHAR(24) NOT NULL,
  source_provider VARCHAR(64) NOT NULL,
  started_at DATETIME(6) NOT NULL,
  finished_at DATETIME(6) NULL,
  input_rows BIGINT UNSIGNED NOT NULL DEFAULT 0,
  output_rows BIGINT UNSIGNED NOT NULL DEFAULT 0,
  anomaly_rows BIGINT UNSIGNED NOT NULL DEFAULT 0,
  details_json JSON NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS stock_bars_daily (
  instrument_id BIGINT UNSIGNED NOT NULL,
  session_date DATE NOT NULL,
  currency CHAR(3) NOT NULL DEFAULT 'EUR',
  open_price DECIMAL(22,8) NOT NULL,
  high_price DECIMAL(22,8) NOT NULL,
  low_price DECIMAL(22,8) NOT NULL,
  close_price DECIMAL(22,8) NOT NULL,
  volume_shares BIGINT UNSIGNED NULL,
  split_adjusted_close DECIMAL(22,8) NULL,
  total_return_close DECIMAL(22,8) NULL,
  vwap DECIMAL(22,8) NULL,
  provider VARCHAR(64) NOT NULL,
  source_revision VARCHAR(128) NOT NULL,
  raw_payload_id BIGINT UNSIGNED NOT NULL,
  canonicalization_run_id VARCHAR(96) NOT NULL,
  observed_at DATETIME(6) NOT NULL,
  available_at DATETIME(6) NOT NULL,
  PRIMARY KEY (instrument_id,session_date),
  KEY ix_fr_canonical_bars_day (session_date,instrument_id),
  CONSTRAINT fk_fr_canonical_bar_instrument FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id),
  CONSTRAINT fk_fr_canonical_bar_raw FOREIGN KEY (raw_payload_id) REFERENCES fr_raw_payloads(raw_payload_id),
  CONSTRAINT fk_fr_canonical_bar_run FOREIGN KEY (canonicalization_run_id) REFERENCES fr_canonicalization_runs(canonicalization_run_id),
  CONSTRAINT ck_fr_canonical_bar_ohlc CHECK (low_price<=open_price AND low_price<=close_price AND high_price>=open_price AND high_price>=close_price AND low_price>0),
  CONSTRAINT ck_fr_canonical_bar_pit CHECK (available_at>=observed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_data_anomalies (
  anomaly_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  canonicalization_run_id VARCHAR(96) NOT NULL,
  instrument_id BIGINT UNSIGNED NULL,
  session_date DATE NULL,
  anomaly_code VARCHAR(64) NOT NULL,
  severity VARCHAR(16) NOT NULL,
  details_json JSON NULL,
  detected_at DATETIME(6) NOT NULL,
  KEY ix_fr_anomaly_day (session_date,anomaly_code),
  CONSTRAINT fk_fr_anomaly_run FOREIGN KEY (canonicalization_run_id) REFERENCES fr_canonicalization_runs(canonicalization_run_id),
  CONSTRAINT fk_fr_anomaly_instrument FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
