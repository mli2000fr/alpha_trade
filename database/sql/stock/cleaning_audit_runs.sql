CREATE TABLE IF NOT EXISTS alpha_trade.cleaning_audit_runs (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `symbol` VARCHAR(20) NOT NULL,
    `last_sync_date` DATE NULL COMMENT 'Dernière date daily calculée pour ce run',
    `missing_days_count` INT NULL COMMENT 'Nombre de séances forward-filled sur la fenêtre recalculée',
    `anomaly_count` INT NULL COMMENT 'Nombre d’anomalies détectées sur la fenêtre recalculée',
    `status` ENUM('success', 'failed', 'processing') NOT NULL DEFAULT 'processing',
    `error_message` TEXT NULL COMMENT 'Message d’erreur métier/technique du run si échec',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY `idx_cleaning_audit_runs_symbol_created_at` (`symbol`, `created_at`),
    KEY `idx_cleaning_audit_runs_status_created_at` (`status`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

