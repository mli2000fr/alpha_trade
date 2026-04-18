CREATE TABLE IF NOT EXISTS execution_events (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_id        VARCHAR(32) NOT NULL UNIQUE,
    exec_run_id     VARCHAR(32) NOT NULL,
    symbol          VARCHAR(20) NULL,
    event_type      VARCHAR(40) NOT NULL,
    message         VARCHAR(255) NOT NULL,
    broker_order_id VARCHAR(64) NULL,
    intent_id       VARCHAR(32) NULL,
    payload_json    JSON NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ee_run (exec_run_id),
    INDEX idx_ee_type (event_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

