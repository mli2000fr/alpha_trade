CREATE TABLE IF NOT EXISTS alpha_trade.cleaning_audit_latest (
    `symbol` VARCHAR(20) NOT NULL,
    `last_sync_date` DATE NULL COMMENT 'Dernière date daily considérée fiable pour ce symbole',
    `missing_days_count` INT NULL COMMENT 'Nombre de séances forward-filled du dernier run',
    `anomaly_count` INT NULL COMMENT 'Nombre d’anomalies détectées sur le dernier run',
    `status` ENUM('success', 'failed', 'processing') NOT NULL DEFAULT 'processing',
    `error_message` TEXT NULL COMMENT 'Détail de l’échec le plus récent si status=failed',
    `latest_run_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`symbol`),
    KEY `idx_cleaning_audit_latest_status` (`status`, `latest_run_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
