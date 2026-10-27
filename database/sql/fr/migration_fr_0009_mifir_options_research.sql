-- Dedicated FR research storage. No canonical prices, instruments or US writes.
CREATE TABLE IF NOT EXISTS fr_option_mifir_snapshots (
  snapshot_id CHAR(64) NOT NULL PRIMARY KEY,
  archive_sha256 CHAR(64) NOT NULL,
  source_sha256 CHAR(64) NOT NULL,
  market_code VARCHAR(16) NOT NULL DEFAULT 'FR_EQ',
  provider VARCHAR(40) NOT NULL DEFAULT 'euronext_mifir_esma_firds',
  observed_at DATETIME(6) NOT NULL,
  available_at DATETIME(6) NOT NULL,
  imported_at DATETIME(6) NOT NULL,
  first_trade_date DATE NOT NULL,
  last_trade_date DATE NOT NULL,
  collection_status VARCHAR(16) NOT NULL,
  contract_count INT UNSIGNED NOT NULL,
  accepted_trade_rows INT UNSIGNED NOT NULL,
  rejected_trade_rows INT UNSIGNED NOT NULL,
  universe_count INT UNSIGNED NOT NULL,
  coverage_json JSON NOT NULL,
  source_receipts_json JSON NOT NULL,
  archive_path TEXT NOT NULL,
  archive_json LONGTEXT NOT NULL,
  ml_eligible BOOLEAN NOT NULL DEFAULT FALSE,
  historical_pit_qualified BOOLEAN NOT NULL DEFAULT FALSE,
  canonical BOOLEAN NOT NULL DEFAULT FALSE,
  KEY ix_fr_option_mifir_snapshot_dates (first_trade_date,last_trade_date),
  KEY ix_fr_option_mifir_snapshot_available (available_at),
  CONSTRAINT ck_fr_option_mifir_snapshot_scope CHECK
    (market_code='FR_EQ' AND ml_eligible=0 AND historical_pit_qualified=0 AND canonical=0),
  CONSTRAINT ck_fr_option_mifir_snapshot_clock CHECK (available_at>=observed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_option_mifir_contracts (
  snapshot_id CHAR(64) NOT NULL,
  option_isin CHAR(12) NOT NULL,
  symbol VARCHAR(32) NOT NULL,
  underlying_isin CHAR(12) NOT NULL,
  option_type VARCHAR(4) NOT NULL,
  strike DECIMAL(38,12) NOT NULL,
  strike_currency VARCHAR(8) NOT NULL,
  expiration_date DATE NOT NULL,
  multiplier DECIMAL(38,12) NOT NULL,
  exercise_style VARCHAR(16) NULL,
  delivery_type VARCHAR(16) NULL,
  cfi VARCHAR(16) NULL,
  details_json JSON NOT NULL,
  adjustment_history_qualified BOOLEAN NOT NULL DEFAULT FALSE,
  historical_reference_pit_qualified BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (snapshot_id,option_isin),
  KEY ix_fr_option_mifir_contract_lookup (symbol,expiration_date,option_type,strike),
  CONSTRAINT fk_fr_option_mifir_contract_snapshot FOREIGN KEY (snapshot_id)
    REFERENCES fr_option_mifir_snapshots(snapshot_id),
  CONSTRAINT ck_fr_option_mifir_contract_scope CHECK
    (option_type IN ('CALL','PUT') AND adjustment_history_qualified=0 AND historical_reference_pit_qualified=0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_option_mifir_trades (
  snapshot_id CHAR(64) NOT NULL,
  source_row_sha256 CHAR(64) NOT NULL,
  option_isin CHAR(12) NOT NULL,
  symbol VARCHAR(32) NOT NULL,
  option_type VARCHAR(4) NOT NULL,
  trade_uid VARCHAR(128) NOT NULL,
  venue VARCHAR(16) NOT NULL,
  publication_venue VARCHAR(16) NOT NULL,
  trade_date DATE NULL,
  traded_at DATETIME(6) NULL,
  published_at DATETIME(6) NULL,
  price DECIMAL(38,12) NULL,
  reported_quantity DECIMAL(38,12) NULL,
  currency VARCHAR(8) NULL,
  acceptance_status VARCHAR(16) NOT NULL,
  rejection_reason VARCHAR(255) NULL,
  source_occurrences INT UNSIGNED NOT NULL DEFAULT 1,
  raw_row_json JSON NOT NULL,
  quantity_unit_qualified BOOLEAN NOT NULL DEFAULT FALSE,
  ml_eligible BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (snapshot_id,source_row_sha256),
  KEY ix_fr_option_mifir_trade_symbol_day (symbol,trade_date,acceptance_status),
  KEY ix_fr_option_mifir_trade_id (venue,publication_venue,trade_uid),
  CONSTRAINT fk_fr_option_mifir_trade_contract FOREIGN KEY (snapshot_id,option_isin)
    REFERENCES fr_option_mifir_contracts(snapshot_id,option_isin),
  CONSTRAINT ck_fr_option_mifir_trade_scope CHECK
    (acceptance_status IN ('ACCEPTED','REJECTED') AND quantity_unit_qualified=0 AND ml_eligible=0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_option_mifir_observations (
  observation_id CHAR(64) NOT NULL PRIMARY KEY,
  snapshot_id CHAR(64) NULL,
  collection_complete BOOLEAN NOT NULL,
  finished_at DATETIME(6) NOT NULL,
  imported_at DATETIME(6) NOT NULL,
  requested_count INT UNSIGNED NOT NULL,
  received_count INT UNSIGNED NOT NULL,
  archive_persisted_count INT UNSIGNED NOT NULL,
  receipt_path TEXT NOT NULL,
  receipt_json LONGTEXT NOT NULL,
  KEY ix_fr_option_mifir_observation_finished (finished_at),
  CONSTRAINT fk_fr_option_mifir_observation_snapshot FOREIGN KEY (snapshot_id)
    REFERENCES fr_option_mifir_snapshots(snapshot_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
