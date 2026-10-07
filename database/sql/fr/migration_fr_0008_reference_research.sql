-- Sprint 6-C : identités et benchmark de recherche, secteurs datés.
-- Aucun INSERT/UPDATE sur instruments, stock_bars_daily ou une base US/CN.
CREATE TABLE IF NOT EXISTS fr_reference_runs (
  run_id VARCHAR(96) NOT NULL PRIMARY KEY,
  market_code VARCHAR(16) NOT NULL DEFAULT 'FR_EQ',
  policy_version VARCHAR(64) NOT NULL,
  policy_fingerprint CHAR(64) NOT NULL,
  source_fingerprint CHAR(64) NOT NULL,
  status VARCHAR(24) NOT NULL,
  details_json JSON NOT NULL,
  started_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  completed_at DATETIME(6) NULL,
  UNIQUE KEY uq_fr_reference_source (policy_fingerprint,source_fingerprint),
  CONSTRAINT fk_fr_reference_market FOREIGN KEY (market_code) REFERENCES markets(market_code),
  CONSTRAINT ck_fr_reference_market CHECK (market_code='FR_EQ'),
  CONSTRAINT ck_fr_reference_status CHECK (status IN ('RUNNING','COMPLETED','FAILED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_research_identities (
  run_id VARCHAR(96) NOT NULL,
  provider_symbol VARCHAR(128) NOT NULL,
  research_uid CHAR(36) NULL,
  isin CHAR(12) NULL,
  instrument_id BIGINT UNSIGNED NULL,
  identity_state VARCHAR(24) NOT NULL,
  primary_reason VARCHAR(255) NOT NULL,
  sector_state VARCHAR(16) NOT NULL,
  details_json JSON NOT NULL,
  PRIMARY KEY (run_id,provider_symbol),
  KEY ix_fr_research_uid (research_uid),
  CONSTRAINT fk_fr_identity_run FOREIGN KEY (run_id) REFERENCES fr_reference_runs(run_id),
  CONSTRAINT fk_fr_identity_canonical FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id),
  CONSTRAINT ck_fr_identity_state CHECK (identity_state IN ('VERIFIED_RESEARCH','AMBIGUOUS','UNKNOWN')),
  CONSTRAINT ck_fr_identity_sector CHECK (sector_state IN ('KNOWN','UNKNOWN','AMBIGUOUS'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_research_benchmark_daily (
  run_id VARCHAR(96) NOT NULL,
  source_session_date DATE NOT NULL,
  decision_session_date DATE NOT NULL,
  constituent_count INT UNSIGNED NOT NULL,
  valid_return_count INT UNSIGNED NOT NULL,
  return_coverage DECIMAL(12,10) NOT NULL,
  price_return DOUBLE NULL,
  index_level DOUBLE NULL,
  segment_id INT UNSIGNED NULL,
  benchmark_state VARCHAR(16) NOT NULL,
  primary_reason VARCHAR(96) NOT NULL,
  details_json JSON NOT NULL,
  PRIMARY KEY (run_id,source_session_date),
  KEY ix_fr_benchmark_decision (decision_session_date),
  CONSTRAINT fk_fr_benchmark_run FOREIGN KEY (run_id) REFERENCES fr_reference_runs(run_id),
  CONSTRAINT ck_fr_benchmark_state CHECK (benchmark_state IN ('KNOWN','UNKNOWN')),
  CONSTRAINT ck_fr_benchmark_availability CHECK (decision_session_date>source_session_date),
  CONSTRAINT ck_fr_benchmark_coverage CHECK (return_coverage>=0 AND return_coverage<=1),
  CONSTRAINT ck_fr_benchmark_values CHECK ((benchmark_state='KNOWN' AND price_return IS NOT NULL AND index_level IS NOT NULL) OR (benchmark_state='UNKNOWN' AND price_return IS NULL AND index_level IS NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_research_benchmark_constituents (
  run_id VARCHAR(96) NOT NULL,
  source_session_date DATE NOT NULL,
  provider_symbol VARCHAR(128) NOT NULL,
  research_uid CHAR(36) NOT NULL,
  eligibility_source_session DATE NOT NULL,
  price_return DOUBLE NULL,
  return_state VARCHAR(16) NOT NULL,
  target_weight DOUBLE NOT NULL,
  details_json JSON NOT NULL,
  PRIMARY KEY (run_id,source_session_date,provider_symbol),
  CONSTRAINT fk_fr_benchmark_constituent_day FOREIGN KEY (run_id,source_session_date) REFERENCES fr_research_benchmark_daily(run_id,source_session_date),
  CONSTRAINT fk_fr_benchmark_constituent_identity FOREIGN KEY (run_id,provider_symbol) REFERENCES fr_research_identities(run_id,provider_symbol),
  CONSTRAINT ck_fr_constituent_lag CHECK (eligibility_source_session<source_session_date),
  CONSTRAINT ck_fr_constituent_state CHECK (return_state IN ('KNOWN','UNKNOWN')),
  CONSTRAINT ck_fr_constituent_weight CHECK (target_weight>0 AND target_weight<=1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Cette table reste vide tant qu'une source sectorielle datée n'est pas validée.
CREATE TABLE IF NOT EXISTS fr_research_sector_memberships (
  run_id VARCHAR(96) NOT NULL,
  provider_symbol VARCHAR(128) NOT NULL,
  taxonomy VARCHAR(64) NOT NULL,
  sector_code VARCHAR(128) NOT NULL,
  valid_from DATE NOT NULL,
  valid_to DATE NULL,
  observed_at DATETIME(6) NOT NULL,
  available_at DATETIME(6) NOT NULL,
  source VARCHAR(255) NOT NULL,
  details_json JSON NOT NULL,
  PRIMARY KEY (run_id,provider_symbol,taxonomy,valid_from,available_at),
  CONSTRAINT fk_fr_sector_identity FOREIGN KEY (run_id,provider_symbol) REFERENCES fr_research_identities(run_id,provider_symbol),
  CONSTRAINT ck_fr_sector_available CHECK (available_at>=observed_at),
  CONSTRAINT ck_fr_sector_interval CHECK (valid_to IS NULL OR valid_to>=valid_from)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
