CREATE TABLE IF NOT EXISTS execution_positions (
    id                          BIGINT AUTO_INCREMENT PRIMARY KEY,
    account_id                  VARCHAR(32) NOT NULL,
    symbol                      VARCHAR(20) NOT NULL,
    net_qty                     DOUBLE NOT NULL,
    avg_entry_price             DOUBLE NULL,
    market_price                DOUBLE NULL,
    market_value                DOUBLE NULL,
    unrealized_pnl              DOUBLE NULL,
    broker_mode                 VARCHAR(10) NULL,
    source_exec_run_id          VARCHAR(32) NULL,
    position_status             VARCHAR(16) NOT NULL DEFAULT 'OPEN',
    last_broker_snapshot_at     TIMESTAMP NULL,
    updated_at                  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_ep_account_symbol (account_id, symbol),
    KEY idx_ep_account_status (account_id, position_status),
    KEY idx_ep_source_exec_run (source_exec_run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

