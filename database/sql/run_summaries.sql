CREATE TABLE IF NOT EXISTS `run_summaries` (
    `summary_run_id` VARCHAR(96) NOT NULL,
    `source_run_id` VARCHAR(96) NULL,
    `entity_run_id` VARCHAR(96) NULL,
    `parent_summary_run_id` VARCHAR(96) NULL,
    `step_key` VARCHAR(64) NOT NULL,
    `run_kind` VARCHAR(16) NOT NULL DEFAULT 'step',
    `status` VARCHAR(32) NULL,
    `account_id` VARCHAR(64) NULL,
    `trade_date` DATE NULL,
    `started_at` DATETIME NULL,
    `finished_at` DATETIME NULL,
    `summary_json` TEXT NOT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`summary_run_id`),
    KEY `idx_run_summaries_step` (`step_key`),
    KEY `idx_run_summaries_entity` (`entity_run_id`),
    KEY `idx_run_summaries_source` (`source_run_id`),
    KEY `idx_run_summaries_run_kind` (`run_kind`),
    KEY `idx_run_summaries_trade_date` (`trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

