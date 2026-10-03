-- Sprint 6-B France : métriques d'historique/liquidité de recherche J+1.
-- provider_symbol reste l'identité de staging ; instrument_id est nullable tant
-- que les identités n'ont pas reçu de promotion canonique.
CREATE TABLE IF NOT EXISTS fr_liquidity_runs (
  liquidity_run_id VARCHAR(96) NOT NULL PRIMARY KEY,
  market_code VARCHAR(16) NOT NULL DEFAULT 'FR_EQ',
  policy_version VARCHAR(64) NOT NULL,
  policy_fingerprint CHAR(64) NOT NULL,
  source_manifest_sha256 CHAR(64) NOT NULL,
  status VARCHAR(24) NOT NULL,
  snapshot_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
  training_eligible_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
  training_ineligible_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
  details_json JSON NULL,
  started_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  completed_at DATETIME(6) NULL,
  UNIQUE KEY uq_fr_liquidity_policy_source (policy_fingerprint,source_manifest_sha256),
  CONSTRAINT fk_fr_liquidity_run_market FOREIGN KEY (market_code) REFERENCES markets(market_code),
  CONSTRAINT ck_fr_liquidity_run_market CHECK (market_code='FR_EQ'),
  CONSTRAINT ck_fr_liquidity_run_status CHECK (status IN ('RUNNING','COMPLETED','FAILED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_liquidity_snapshots (
  liquidity_run_id VARCHAR(96) NOT NULL,
  provider_symbol VARCHAR(128) NOT NULL,
  instrument_id BIGINT UNSIGNED NULL,
  mic CHAR(4) NOT NULL,
  source_session_date DATE NOT NULL,
  decision_session_date DATE NOT NULL,
  availability_lag_sessions SMALLINT UNSIGNED NOT NULL DEFAULT 1,
  history_sessions INT UNSIGNED NOT NULL,
  liquidity_lookback_sessions SMALLINT UNSIGNED NOT NULL,
  liquidity_observations SMALLINT UNSIGNED NOT NULL,
  last_close_eur DECIMAL(22,8) NOT NULL,
  avg_volume_shares DECIMAL(24,6) NOT NULL,
  avg_traded_value_eur DECIMAL(28,6) NOT NULL,
  history_state VARCHAR(16) NOT NULL,
  liquidity_state VARCHAR(16) NOT NULL,
  training_state VARCHAR(16) NOT NULL,
  primary_reason VARCHAR(96) NOT NULL,
  details_json JSON NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (liquidity_run_id,provider_symbol,decision_session_date),
  KEY ix_fr_liquidity_decision_state (decision_session_date,training_state),
  KEY ix_fr_liquidity_symbol_date (provider_symbol,decision_session_date),
  KEY ix_fr_liquidity_instrument_date (instrument_id,decision_session_date),
  CONSTRAINT fk_fr_liquidity_snapshot_run FOREIGN KEY (liquidity_run_id) REFERENCES fr_liquidity_runs(liquidity_run_id),
  CONSTRAINT fk_fr_liquidity_snapshot_instrument FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id),
  CONSTRAINT ck_fr_liquidity_dates CHECK (decision_session_date>source_session_date),
  CONSTRAINT ck_fr_liquidity_history_state CHECK (history_state IN ('KNOWN','INSUFFICIENT','UNKNOWN')),
  CONSTRAINT ck_fr_liquidity_state CHECK (liquidity_state IN ('KNOWN','INSUFFICIENT','UNKNOWN')),
  CONSTRAINT ck_fr_liquidity_training_state CHECK (training_state IN ('ELIGIBLE','INELIGIBLE','UNKNOWN'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
