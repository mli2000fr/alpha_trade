-- Sprint 7-A CN : socle canonique pilote, exclusivement dans alpha_trade_cn.
CREATE TABLE IF NOT EXISTS markets (
  market_code VARCHAR(16) NOT NULL PRIMARY KEY,
  database_alias VARCHAR(64) NOT NULL,
  country_code CHAR(2) NOT NULL,
  currency CHAR(3) NOT NULL,
  timezone VARCHAR(64) NOT NULL,
  calendar_id VARCHAR(32) NOT NULL,
  benchmark_symbol VARCHAR(64) NOT NULL,
  sector_taxonomy VARCHAR(64) NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT FALSE,
  live_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  context_fingerprint CHAR(64) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS instruments (
  instrument_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  instrument_uid CHAR(36) NOT NULL,
  market_code VARCHAR(16) NOT NULL,
  exchange_mic CHAR(4) NOT NULL,
  local_symbol VARCHAR(64) NOT NULL,
  display_name VARCHAR(255) NULL,
  instrument_type VARCHAR(32) NOT NULL DEFAULT 'equity',
  currency CHAR(3) NOT NULL DEFAULT 'CNY',
  listing_date DATE NULL,
  delisting_date DATE NULL,
  mapping_status VARCHAR(32) NOT NULL DEFAULT 'mapped',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_instruments_uid (instrument_uid),
  UNIQUE KEY uq_instruments_mic_symbol (exchange_mic, local_symbol),
  KEY ix_instruments_market_active (market_code, is_active),
  CONSTRAINT fk_cn_instruments_market FOREIGN KEY (market_code) REFERENCES markets(market_code),
  CONSTRAINT ck_cn_instruments_dates CHECK (delisting_date IS NULL OR listing_date IS NULL OR delisting_date >= listing_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS instrument_provider_symbols (
  mapping_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  instrument_id BIGINT UNSIGNED NOT NULL,
  provider VARCHAR(64) NOT NULL,
  provider_symbol VARCHAR(128) NOT NULL,
  provider_exchange VARCHAR(64) NULL,
  valid_from DATE NOT NULL,
  valid_to DATE NULL,
  is_primary BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_cn_ips_identity_start (provider, provider_symbol, instrument_id, valid_from),
  KEY ix_cn_ips_resolve (provider, provider_symbol, valid_from, valid_to),
  CONSTRAINT fk_cn_ips_instrument FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id),
  CONSTRAINT ck_cn_ips_dates CHECK (valid_to IS NULL OR valid_to >= valid_from)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS instrument_status_history (
  status_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  instrument_id BIGINT UNSIGNED NOT NULL,
  valid_from DATE NOT NULL,
  valid_to DATE NULL,
  listing_status VARCHAR(32) NOT NULL,
  trading_status VARCHAR(32) NOT NULL,
  is_tradable BOOLEAN NOT NULL,
  is_special_treatment BOOLEAN NOT NULL DEFAULT FALSE,
  board_code VARCHAR(32) NULL,
  source VARCHAR(64) NOT NULL,
  observed_at DATETIME(6) NOT NULL,
  available_at DATETIME(6) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_cn_ish_instrument_start_source (instrument_id, valid_from, source),
  KEY ix_cn_ish_asof (instrument_id, valid_from, valid_to),
  CONSTRAINT fk_cn_ish_instrument FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id),
  CONSTRAINT ck_cn_ish_dates CHECK (valid_to IS NULL OR valid_to >= valid_from),
  CONSTRAINT ck_cn_ish_pit CHECK (available_at >= observed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS market_sessions (
  market_code VARCHAR(16) NOT NULL,
  session_date DATE NOT NULL,
  session_status VARCHAR(24) NOT NULL,
  open_at_utc DATETIME(6) NULL,
  close_at_utc DATETIME(6) NULL,
  session_segments_json JSON NULL,
  settlement_date DATE NULL,
  source VARCHAR(64) NOT NULL,
  observed_at DATETIME(6) NOT NULL,
  available_at DATETIME(6) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (market_code, session_date),
  CONSTRAINT fk_cn_market_sessions_market FOREIGN KEY (market_code) REFERENCES markets(market_code),
  CONSTRAINT ck_cn_market_sessions_status CHECK (session_status IN ('open','closed','half_day','special')),
  CONSTRAINT ck_cn_market_sessions_hours CHECK (close_at_utc IS NULL OR open_at_utc IS NULL OR close_at_utc > open_at_utc),
  CONSTRAINT ck_cn_market_sessions_pit CHECK (available_at >= observed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS stock_bars_daily (
  instrument_id BIGINT UNSIGNED NOT NULL,
  symbol VARCHAR(64) NOT NULL,
  market_code VARCHAR(16) NOT NULL DEFAULT 'CN_A',
  `date` DATE NOT NULL,
  `open` DECIMAL(20,6) NOT NULL,
  high DECIMAL(20,6) NOT NULL,
  low DECIMAL(20,6) NOT NULL,
  `close` DECIMAL(20,6) NOT NULL,
  pre_close DECIMAL(20,6) NULL,
  adj_close DECIMAL(20,6) NOT NULL,
  volume DECIMAL(28,6) NULL,
  amount DECIMAL(28,6) NULL,
  daily_return DECIMAL(20,10) NULL,
  trading_status VARCHAR(32) NOT NULL DEFAULT 'TRADE',
  is_special_treatment BOOLEAN NOT NULL DEFAULT FALSE,
  data_adjustment VARCHAR(16) NOT NULL DEFAULT 'raw',
  data_source VARCHAR(64) NOT NULL,
  source_payload_hash CHAR(64) NOT NULL,
  observed_at DATETIME(6) NOT NULL,
  available_at DATETIME(6) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (instrument_id, `date`),
  KEY ix_cn_daily_symbol_date (symbol, `date`),
  KEY ix_cn_daily_market_date (market_code, `date`),
  CONSTRAINT fk_cn_daily_instrument FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id),
  CONSTRAINT ck_cn_daily_ohlc CHECK (high >= low AND high >= `open` AND high >= `close` AND low <= `open` AND low <= `close`),
  CONSTRAINT ck_cn_daily_nonnegative CHECK (`open` >= 0 AND high >= 0 AND low >= 0 AND `close` >= 0 AND (volume IS NULL OR volume >= 0) AND (amount IS NULL OR amount >= 0)),
  CONSTRAINT ck_cn_daily_raw_price CHECK (data_adjustment = 'raw' AND adj_close = `close`),
  CONSTRAINT ck_cn_daily_pit CHECK (available_at >= observed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS instrument_adjustment_factors (
  instrument_id BIGINT UNSIGNED NOT NULL,
  effective_date DATE NOT NULL,
  provider VARCHAR(64) NOT NULL,
  adjustment_factor DECIMAL(24,10) NOT NULL,
  source_payload_hash CHAR(64) NOT NULL,
  observed_at DATETIME(6) NOT NULL,
  available_at DATETIME(6) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (instrument_id, effective_date, provider),
  CONSTRAINT fk_cn_factor_instrument FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id),
  CONSTRAINT ck_cn_factor_positive CHECK (adjustment_factor > 0),
  CONSTRAINT ck_cn_factor_pit CHECK (available_at >= observed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cn_canonicalization_runs (
  canonicalization_run_id VARCHAR(96) NOT NULL PRIMARY KEY,
  staging_cutoff DATETIME(6) NOT NULL,
  pilot_manifest_hash CHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  selected_instruments INT NOT NULL DEFAULT 0,
  promoted_instruments INT NOT NULL DEFAULT 0,
  promoted_sessions INT NOT NULL DEFAULT 0,
  promoted_bars BIGINT NOT NULL DEFAULT 0,
  promoted_factors BIGINT NOT NULL DEFAULT 0,
  rejected_rows BIGINT NOT NULL DEFAULT 0,
  details_json JSON NULL,
  started_at DATETIME(6) NOT NULL,
  finished_at DATETIME(6) NULL,
  KEY ix_cn_canonical_runs_status_started (status, started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO markets (market_code,database_alias,country_code,currency,timezone,calendar_id,benchmark_symbol,sector_taxonomy,enabled,live_enabled,context_fingerprint)
VALUES ('CN_A','cn_primary','CN','CNY','Asia/Shanghai','CN_A','000300.SH','SW_2021',FALSE,FALSE,'428aee24c2ae09ab9659af003f823bd1e4b54fad5df53670d520ce49220fa712')
ON DUPLICATE KEY UPDATE updated_at=CURRENT_TIMESTAMP(6);
