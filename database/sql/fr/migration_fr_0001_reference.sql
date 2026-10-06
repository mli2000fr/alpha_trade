-- Sprint 2 France : exclusivement dans alpha_trade_fr. Exécuter via alembic_fr.ini.
CREATE TABLE IF NOT EXISTS markets (
  market_code VARCHAR(16) NOT NULL PRIMARY KEY,
  database_alias VARCHAR(64) NOT NULL,
  country_code CHAR(2) NOT NULL,
  currency CHAR(3) NOT NULL,
  timezone VARCHAR(64) NOT NULL,
  calendar_id VARCHAR(32) NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT FALSE,
  live_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  CONSTRAINT ck_fr_market_identity CHECK (market_code='FR_EQ' AND database_alias='fr_primary'
    AND country_code='FR' AND currency='EUR' AND timezone='Europe/Paris' AND calendar_id='XPAR'
    AND enabled=FALSE AND live_enabled=FALSE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS instruments (
  instrument_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  instrument_uid CHAR(36) NOT NULL,
  market_code VARCHAR(16) NOT NULL DEFAULT 'FR_EQ',
  canonical_isin CHAR(12) NULL,
  display_name VARCHAR(255) NULL,
  instrument_type VARCHAR(32) NOT NULL,
  currency CHAR(3) NOT NULL DEFAULT 'EUR',
  first_seen_at DATETIME(6) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_fr_instrument_uid (instrument_uid),
  KEY ix_fr_instrument_isin (canonical_isin),
  CONSTRAINT fk_fr_instrument_market FOREIGN KEY (market_code) REFERENCES markets(market_code),
  CONSTRAINT ck_fr_instrument_market CHECK (market_code='FR_EQ'),
  CONSTRAINT ck_fr_instrument_currency CHECK (currency='EUR')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS instrument_listings (
  listing_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  instrument_id BIGINT UNSIGNED NOT NULL,
  isin CHAR(12) NOT NULL,
  exchange_mic CHAR(4) NOT NULL,
  market_segment VARCHAR(64) NOT NULL,
  currency CHAR(3) NOT NULL,
  valid_from DATE NOT NULL,
  valid_to DATE NULL,
  source VARCHAR(64) NOT NULL,
  observed_at DATETIME(6) NOT NULL,
  available_at DATETIME(6) NOT NULL,
  source_payload_hash CHAR(64) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_fr_listing_identity_start (instrument_id,exchange_mic,valid_from),
  KEY ix_fr_listing_isin_mic_asof (isin,exchange_mic,valid_from,valid_to),
  CONSTRAINT fk_fr_listing_instrument FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id),
  CONSTRAINT ck_fr_listing_dates CHECK (valid_to IS NULL OR valid_to >= valid_from),
  CONSTRAINT ck_fr_listing_pit CHECK (available_at >= observed_at),
  CONSTRAINT ck_fr_listing_market CHECK (exchange_mic='XPAR' AND currency='EUR')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS instrument_provider_symbols (
  mapping_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  instrument_id BIGINT UNSIGNED NOT NULL,
  provider VARCHAR(64) NOT NULL,
  provider_symbol VARCHAR(128) NOT NULL,
  provider_exchange VARCHAR(64) NULL,
  valid_from DATE NOT NULL,
  valid_to DATE NULL,
  source_payload_hash CHAR(64) NOT NULL,
  observed_at DATETIME(6) NOT NULL,
  available_at DATETIME(6) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_fr_provider_symbol_start (provider,provider_symbol,instrument_id,valid_from),
  KEY ix_fr_provider_resolve (provider,provider_symbol,valid_from,valid_to),
  CONSTRAINT fk_fr_provider_instrument FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id),
  CONSTRAINT ck_fr_provider_dates CHECK (valid_to IS NULL OR valid_to >= valid_from),
  CONSTRAINT ck_fr_provider_pit CHECK (available_at >= observed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS instrument_status_history (
  status_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  instrument_id BIGINT UNSIGNED NOT NULL,
  valid_from DATE NOT NULL,
  valid_to DATE NULL,
  listing_status VARCHAR(32) NOT NULL,
  trading_status VARCHAR(32) NOT NULL,
  is_tradable BOOLEAN NOT NULL,
  source VARCHAR(64) NOT NULL,
  source_payload_hash CHAR(64) NOT NULL,
  observed_at DATETIME(6) NOT NULL,
  available_at DATETIME(6) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_fr_status_identity_start_source (instrument_id,valid_from,source),
  KEY ix_fr_status_asof (instrument_id,valid_from,valid_to),
  CONSTRAINT fk_fr_status_instrument FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id),
  CONSTRAINT ck_fr_status_dates CHECK (valid_to IS NULL OR valid_to >= valid_from),
  CONSTRAINT ck_fr_status_pit CHECK (available_at >= observed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS market_sessions (
  market_code VARCHAR(16) NOT NULL,
  session_date DATE NOT NULL,
  session_status VARCHAR(24) NOT NULL,
  open_at_utc DATETIME(6) NULL,
  close_at_utc DATETIME(6) NULL,
  session_segments_json JSON NULL,
  source VARCHAR(64) NOT NULL,
  source_revision VARCHAR(64) NULL,
  observed_at DATETIME(6) NOT NULL,
  available_at DATETIME(6) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (market_code,session_date),
  CONSTRAINT fk_fr_session_market FOREIGN KEY (market_code) REFERENCES markets(market_code),
  CONSTRAINT ck_fr_session_market CHECK (market_code='FR_EQ'),
  CONSTRAINT ck_fr_session_status CHECK (session_status IN ('open','closed','half_day','special')),
  CONSTRAINT ck_fr_session_hours CHECK (close_at_utc IS NULL OR open_at_utc IS NULL OR close_at_utc>open_at_utc),
  CONSTRAINT ck_fr_session_pit CHECK (available_at>=observed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_ingestion_runs (
  run_id VARCHAR(96) NOT NULL PRIMARY KEY,
  provider VARCHAR(64) NOT NULL,
  dataset VARCHAR(64) NOT NULL,
  status VARCHAR(24) NOT NULL,
  requested BIGINT UNSIGNED NOT NULL DEFAULT 0,
  received BIGINT UNSIGNED NOT NULL DEFAULT 0,
  persisted BIGINT UNSIGNED NOT NULL DEFAULT 0,
  failed BIGINT UNSIGNED NOT NULL DEFAULT 0,
  warnings BIGINT UNSIGNED NOT NULL DEFAULT 0,
  effective_config_hash CHAR(64) NOT NULL,
  details_json JSON NULL,
  started_at DATETIME(6) NOT NULL,
  finished_at DATETIME(6) NULL,
  KEY ix_fr_ingestion_dataset_started (dataset,started_at),
  CONSTRAINT ck_fr_ingestion_status CHECK (status IN ('RUNNING','COMPLETED','FAILED','SKIPPED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO markets (market_code,database_alias,country_code,currency,timezone,calendar_id,enabled,live_enabled)
VALUES ('FR_EQ','fr_primary','FR','EUR','Europe/Paris','XPAR',FALSE,FALSE)
ON DUPLICATE KEY UPDATE updated_at=CURRENT_TIMESTAMP(6);
