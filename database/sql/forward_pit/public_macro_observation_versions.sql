-- Migration 0096, US only. Non-destructive and safe to execute before Alembic.
CREATE TABLE IF NOT EXISTS alpha_trade.macro_public_observation_versions (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 provider VARCHAR(255) NOT NULL,
 native_series_id VARCHAR(64) NOT NULL,
 metric_key VARCHAR(64) NOT NULL,
 period_start DATE NOT NULL,
 period_end DATE NOT NULL,
 frequency VARCHAR(16) NOT NULL,
 value_num DOUBLE NULL,
 value_raw VARCHAR(64) NOT NULL,
 unit VARCHAR(128) NOT NULL,
 metadata_json LONGTEXT NOT NULL,
 version_hash VARCHAR(64) NOT NULL,
 observed_at DATETIME(6) NOT NULL,
 available_at DATETIME(6) NOT NULL,
 available_at_basis VARCHAR(32) NOT NULL,
 source_url VARCHAR(512) NOT NULL,
 run_id VARCHAR(64) NOT NULL,
 UNIQUE KEY uq_mpov_identity_observed(provider,native_series_id,period_start,observed_at,version_hash),
 INDEX idx_mpov_metric_available(metric_key,available_at),
 INDEX idx_mpov_identity_observed(provider,native_series_id,period_start,observed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
