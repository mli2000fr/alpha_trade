-- Staging conservateur : PA n'est pas une preuve du MIC individuel XPAR.
-- Aucun instrument_id, aucune propriété de tradabilité historique inférée.
CREATE TABLE IF NOT EXISTS fr_provider_universe_staging (
  provider VARCHAR(32) NOT NULL,
  provider_symbol VARCHAR(128) NOT NULL,
  provider_exchange VARCHAR(32) NOT NULL,
  provider_status VARCHAR(16) NOT NULL,
  provider_type VARCHAR(64) NOT NULL,
  currency CHAR(3) NOT NULL,
  reported_isin CHAR(12) NULL,
  reported_name VARCHAR(255) NULL,
  verified_mic CHAR(4) NULL,
  raw_payload_id BIGINT UNSIGNED NULL,
  observed_at DATETIME(6) NOT NULL,
  PRIMARY KEY (provider,provider_symbol),
  KEY ix_fr_provider_universe_isin (reported_isin),
  CONSTRAINT fk_fr_provider_universe_raw FOREIGN KEY (raw_payload_id) REFERENCES fr_raw_payloads(raw_payload_id),
  CONSTRAINT ck_fr_provider_universe_status CHECK (provider_status IN ('active','delisted'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_provider_bars_staging (
  provider VARCHAR(32) NOT NULL,
  provider_symbol VARCHAR(128) NOT NULL,
  session_date DATE NOT NULL,
  raw_payload_id BIGINT UNSIGNED NOT NULL,
  open_price DECIMAL(22,8) NULL,
  high_price DECIMAL(22,8) NULL,
  low_price DECIMAL(22,8) NULL,
  close_price DECIMAL(22,8) NULL,
  provider_adjusted_close DECIMAL(22,8) NULL,
  provider_volume_split_adjusted BIGINT UNSIGNED NULL,
  quality_code VARCHAR(32) NOT NULL,
  observed_at DATETIME(6) NOT NULL,
  available_at DATETIME(6) NOT NULL,
  PRIMARY KEY (provider,provider_symbol,session_date,raw_payload_id),
  KEY ix_fr_staging_bars_day (session_date,quality_code),
  KEY ix_fr_staging_bars_symbol (provider_symbol,session_date),
  CONSTRAINT fk_fr_staging_bar_raw FOREIGN KEY (raw_payload_id) REFERENCES fr_raw_payloads(raw_payload_id),
  CONSTRAINT ck_fr_staging_bar_pit CHECK (available_at>=observed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_provider_actions_staging (
  provider VARCHAR(32) NOT NULL,
  provider_symbol VARCHAR(128) NOT NULL,
  action_type VARCHAR(16) NOT NULL,
  event_date DATE NOT NULL,
  event_ordinal SMALLINT UNSIGNED NOT NULL,
  raw_payload_id BIGINT UNSIGNED NOT NULL,
  event_json JSON NOT NULL,
  observed_at DATETIME(6) NOT NULL,
  available_at DATETIME(6) NOT NULL,
  PRIMARY KEY (provider,provider_symbol,action_type,event_date,event_ordinal,raw_payload_id),
  KEY ix_fr_staging_action_day (event_date,action_type),
  CONSTRAINT fk_fr_staging_action_raw FOREIGN KEY (raw_payload_id) REFERENCES fr_raw_payloads(raw_payload_id),
  CONSTRAINT ck_fr_staging_action_pit CHECK (available_at>=observed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_staging_progress (
  provider VARCHAR(32) NOT NULL,
  provider_symbol VARCHAR(128) NOT NULL,
  raw_payload_id BIGINT UNSIGNED NOT NULL,
  dataset VARCHAR(16) NOT NULL,
  row_count INT UNSIGNED NOT NULL,
  valid_count INT UNSIGNED NOT NULL DEFAULT 0,
  status VARCHAR(16) NOT NULL,
  completed_at DATETIME(6) NOT NULL,
  PRIMARY KEY (provider,provider_symbol,raw_payload_id,dataset),
  CONSTRAINT fk_fr_staging_progress_raw FOREIGN KEY (raw_payload_id) REFERENCES fr_raw_payloads(raw_payload_id),
  CONSTRAINT ck_fr_staging_progress_status CHECK (status IN ('COMPLETED','FAILED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
