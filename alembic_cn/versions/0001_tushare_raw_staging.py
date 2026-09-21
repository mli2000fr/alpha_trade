"""Crée le staging brut Tushare dans alpha_trade_cn.

Revision ID: 0001_tushare_raw_staging
Revises: None
"""

from __future__ import annotations

from alembic import op

revision = "0001_tushare_raw_staging"
down_revision = None
branch_labels = ("cn",)
depends_on = None

TABLES_SQL = """
CREATE TABLE IF NOT EXISTS cn_ingestion_runs (
  run_id VARCHAR(96) PRIMARY KEY,
  batch_name VARCHAR(96) NOT NULL,
  market_code VARCHAR(16) NOT NULL,
  database_alias VARCHAR(32) NOT NULL,
  provider VARCHAR(32) NOT NULL,
  status VARCHAR(32) NOT NULL,
  started_at DATETIME(6) NOT NULL,
  finished_at DATETIME(6) NULL,
  requested_count BIGINT NOT NULL DEFAULT 0,
  received_count BIGINT NOT NULL DEFAULT 0,
  persisted_count BIGINT NOT NULL DEFAULT 0,
  empty_count BIGINT NOT NULL DEFAULT 0,
  failed_count BIGINT NOT NULL DEFAULT 0,
  warning_count BIGINT NOT NULL DEFAULT 0,
  quota_calls BIGINT NOT NULL DEFAULT 0,
  error_message TEXT NULL,
  details_json JSON NULL,
  INDEX ix_cn_runs_batch_started (batch_name, started_at),
  INDEX ix_cn_runs_status_started (status, started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS tushare_raw_payloads (
  raw_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  run_id VARCHAR(96) NOT NULL,
  provider VARCHAR(32) NOT NULL DEFAULT 'tushare',
  endpoint VARCHAR(64) NOT NULL,
  request_hash CHAR(64) NOT NULL,
  page_key VARCHAR(128) NOT NULL,
  payload_hash CHAR(64) NOT NULL,
  http_status SMALLINT NULL,
  provider_code INT NULL,
  observed_at DATETIME(6) NOT NULL,
  available_at DATETIME(6) NOT NULL,
  source_revision VARCHAR(128) NULL,
  raw_payload JSON NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_tushare_raw_page (endpoint, request_hash, page_key, payload_hash),
  INDEX ix_tushare_raw_run (run_id),
  INDEX ix_tushare_raw_endpoint_observed (endpoint, observed_at),
  CONSTRAINT fk_tushare_raw_run FOREIGN KEY (run_id)
    REFERENCES cn_ingestion_runs(run_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS tushare_staging_rows (
  staging_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  run_id VARCHAR(96) NOT NULL,
  raw_id BIGINT UNSIGNED NULL,
  provider VARCHAR(32) NOT NULL DEFAULT 'tushare',
  endpoint VARCHAR(64) NOT NULL,
  market_code VARCHAR(16) NOT NULL,
  provider_symbol VARCHAR(32) NULL,
  entity_key VARCHAR(192) NOT NULL,
  business_date DATE NULL,
  payload_hash CHAR(64) NOT NULL,
  observed_at DATETIME(6) NOT NULL,
  available_at DATETIME(6) NOT NULL,
  source_revision VARCHAR(128) NULL,
  name VARCHAR(255) NULL,
  exchange_code VARCHAR(16) NULL,
  board_code VARCHAR(32) NULL,
  status_code VARCHAR(32) NULL,
  open_price DECIMAL(20,6) NULL,
  high_price DECIMAL(20,6) NULL,
  low_price DECIMAL(20,6) NULL,
  close_price DECIMAL(20,6) NULL,
  pre_close DECIMAL(20,6) NULL,
  volume DECIMAL(28,6) NULL,
  amount DECIMAL(28,6) NULL,
  adjustment_factor DECIMAL(24,10) NULL,
  limit_up DECIMAL(20,6) NULL,
  limit_down DECIMAL(20,6) NULL,
  is_open TINYINT(1) NULL,
  list_date DATE NULL,
  delist_date DATE NULL,
  reason_text TEXT NULL,
  raw_payload JSON NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_tushare_staging_revision (endpoint, entity_key, payload_hash),
  INDEX ix_tushare_staging_endpoint_date (endpoint, business_date),
  INDEX ix_tushare_staging_symbol_date (provider_symbol, business_date),
  INDEX ix_tushare_staging_available (available_at),
  INDEX ix_tushare_staging_run (run_id),
  CONSTRAINT fk_tushare_staging_run FOREIGN KEY (run_id)
    REFERENCES cn_ingestion_runs(run_id) ON DELETE RESTRICT,
  CONSTRAINT fk_tushare_staging_raw FOREIGN KEY (raw_id)
    REFERENCES tushare_raw_payloads(raw_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cn_staging_quality_metrics (
  metric_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  run_id VARCHAR(96) NOT NULL,
  metric_date DATE NOT NULL,
  endpoint VARCHAR(64) NOT NULL,
  metric_name VARCHAR(96) NOT NULL,
  metric_value DOUBLE NULL,
  threshold_value DOUBLE NULL,
  status VARCHAR(24) NOT NULL,
  details_json JSON NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_cn_quality_run_metric (run_id, endpoint, metric_name),
  INDEX ix_cn_quality_date_status (metric_date, status),
  CONSTRAINT fk_cn_quality_run FOREIGN KEY (run_id)
    REFERENCES cn_ingestion_runs(run_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""


def upgrade() -> None:
    connection = op.get_bind()
    database = connection.exec_driver_sql("SELECT DATABASE()").scalar()
    if database != "alpha_trade_cn":
        raise RuntimeError(f"Migration CN refusée sur {database!r}")
    for statement in TABLES_SQL.split(";\n"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    for table in (
        "cn_staging_quality_metrics",
        "tushare_staging_rows",
        "tushare_raw_payloads",
        "cn_ingestion_runs",
    ):
        op.execute(f"DROP TABLE IF EXISTS `{table}`")
