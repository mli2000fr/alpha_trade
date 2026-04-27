CREATE TABLE IF NOT EXISTS execution_locks (
    account_id        VARCHAR(32) NOT NULL PRIMARY KEY,
    locked_by_run_id  VARCHAR(32) NOT NULL,
    acquired_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at        TIMESTAMP NOT NULL,
    INDEX idx_execution_locks_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
