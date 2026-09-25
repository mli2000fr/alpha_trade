-- Sprint 8 : snapshots CN_A avant séance et audit ex post, sans tables US.
CREATE TABLE IF NOT EXISTS cn_universe_runs (
  universe_run_id VARCHAR(64) NOT NULL PRIMARY KEY,
  market_code VARCHAR(16) NOT NULL DEFAULT 'CN_A',
  session_date DATE NOT NULL,
  decision_at DATETIME(6) NOT NULL,
  policy_fingerprint CHAR(64) NOT NULL,
  universe_fingerprint CHAR(64) NOT NULL,
  status VARCHAR(20) NOT NULL,
  instrument_count INT NOT NULL,
  candidate_count INT NOT NULL,
  audited_count INT NOT NULL DEFAULT 0,
  details_json JSON NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_cn_universe_session_fingerprint (market_code, session_date, universe_fingerprint),
  KEY ix_cn_universe_session (market_code, session_date, status),
  CONSTRAINT ck_cn_universe_market CHECK (market_code = 'CN_A')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cn_universe_decisions (
  universe_run_id VARCHAR(64) NOT NULL,
  instrument_id BIGINT UNSIGNED NOT NULL,
  provider_symbol VARCHAR(128) NOT NULL,
  decision_state VARCHAR(16) NOT NULL,
  primary_reason VARCHAR(64) NOT NULL,
  reasons_json JSON NOT NULL,
  history_bars INT NOT NULL,
  recent_bars INT NOT NULL,
  last_bar_date DATE NULL,
  last_close DECIMAL(20,6) NULL,
  avg_amount_cny DECIMAL(28,6) NULL,
  source_available_at DATETIME(6) NULL,
  PRIMARY KEY (universe_run_id, instrument_id),
  KEY ix_cn_universe_decision_state (universe_run_id, decision_state),
  CONSTRAINT fk_cn_universe_decision_run FOREIGN KEY (universe_run_id) REFERENCES cn_universe_runs(universe_run_id),
  CONSTRAINT fk_cn_universe_decision_instrument FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cn_universe_execution_audit (
  universe_run_id VARCHAR(64) NOT NULL,
  instrument_id BIGINT UNSIGNED NOT NULL,
  audit_state VARCHAR(24) NOT NULL,
  audit_reason VARCHAR(64) NOT NULL,
  bar_available_at DATETIME(6) NULL,
  limit_available_at DATETIME(6) NULL,
  audited_at DATETIME(6) NOT NULL,
  PRIMARY KEY (universe_run_id, instrument_id),
  KEY ix_cn_universe_audit_state (universe_run_id, audit_state),
  CONSTRAINT fk_cn_universe_audit_decision FOREIGN KEY (universe_run_id, instrument_id)
    REFERENCES cn_universe_decisions(universe_run_id, instrument_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
