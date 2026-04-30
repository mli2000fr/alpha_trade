CREATE TABLE IF NOT EXISTS alpha_trade.cleaning_audit_earnings_runs (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `run_id` VARCHAR(64) NOT NULL,
    `started_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `finished_at` DATETIME NULL,
    `duration_seconds` DOUBLE NULL,
    `symbols_requested` INT NOT NULL DEFAULT 0,
    `rows_upserted` INT NOT NULL DEFAULT 0,
    `status` ENUM('success', 'failed', 'partial') NOT NULL DEFAULT 'success',
    `error_message` TEXT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `idx_cleaning_audit_earnings_runs_run_id` (`run_id`),
    KEY `idx_cleaning_audit_earnings_runs_status_created_at` (`status`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='Phase 3.1.d — audit dédié sync_earnings_calendar (1 ligne par run).';

