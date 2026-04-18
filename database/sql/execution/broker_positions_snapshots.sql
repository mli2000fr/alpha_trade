CREATE TABLE IF NOT EXISTS broker_positions_snapshots (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    exec_run_id     VARCHAR(32) NOT NULL,
    broker_mode     VARCHAR(10) NOT NULL,
    symbol          VARCHAR(20) NOT NULL,
    qty             DOUBLE NOT NULL DEFAULT 0,
    avg_entry_price DOUBLE NOT NULL DEFAULT 0,
    market_value    DOUBLE NOT NULL DEFAULT 0,
    unrealized_pnl  DOUBLE NOT NULL DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_bps_run (exec_run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

