CREATE TABLE IF NOT EXISTS execution_fills (
    id                        BIGINT AUTO_INCREMENT PRIMARY KEY,
    exec_run_id               VARCHAR(32) NOT NULL,
    fill_id                   VARCHAR(32) NOT NULL UNIQUE,
    broker_order_id           VARCHAR(64) NOT NULL,
    intent_id                 VARCHAR(32) NOT NULL,
    symbol                    VARCHAR(20) NOT NULL,
    filled_qty                DOUBLE NOT NULL,
    avg_fill_price            DOUBLE NOT NULL,
    fill_timestamp            TIMESTAMP NOT NULL,
    decision_price            DOUBLE NOT NULL,
    slippage_bps              DOUBLE NOT NULL DEFAULT 0,
    implementation_shortfall  DOUBLE NOT NULL DEFAULT 0,
    created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ef_run (exec_run_id),
    INDEX idx_ef_order (broker_order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

