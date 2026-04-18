CREATE TABLE IF NOT EXISTS execution_runs (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    exec_run_id     VARCHAR(32) NOT NULL UNIQUE,
    risk_run_id     VARCHAR(32) NOT NULL,
    trade_date      DATE NOT NULL,
    broker_mode     VARCHAR(10) NOT NULL,
    dry_run         BOOLEAN NOT NULL DEFAULT FALSE,
    status          VARCHAR(20) NOT NULL DEFAULT 'RUNNING',
    started_at      TIMESTAMP NULL,
    completed_at    TIMESTAMP NULL,
    error_message   TEXT NULL,
    total_targets   INT NOT NULL DEFAULT 0,
    total_submitted INT NOT NULL DEFAULT 0,
    total_filled    INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_er_run (exec_run_id),
    INDEX idx_er_risk (risk_run_id),
    INDEX idx_er_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

