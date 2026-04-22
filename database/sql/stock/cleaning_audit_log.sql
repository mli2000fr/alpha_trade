CREATE TABLE IF NOT EXISTS alpha_trade.cleaning_audit_log (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `symbol` VARCHAR(20) NOT NULL,
    `last_sync_date` DATE COMMENT '該股票目前同步到的最新日期',
    `missing_days_count` INT DEFAULT 0 COMMENT '被 Forward Fill 的天數',
    `anomaly_count` INT DEFAULT 0 COMMENT '被 MAD 檢測出的異常點數量',
    `status` ENUM('success', 'failed', 'processing') DEFAULT 'success',
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_symbol` (`symbol`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;