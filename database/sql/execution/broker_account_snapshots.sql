CREATE TABLE IF NOT EXISTS broker_account_snapshots (
    id               BIGINT AUTO_INCREMENT PRIMARY KEY,
    exec_run_id      VARCHAR(32) NOT NULL,
    account_id       VARCHAR(32) NOT NULL,
    broker_mode      VARCHAR(10) NOT NULL,
    snapshot_kind    VARCHAR(20) NOT NULL,
    equity           DOUBLE NOT NULL,
    cash             DOUBLE NOT NULL,
    settled_cash     DOUBLE NOT NULL,
    buying_power     DOUBLE NOT NULL,
    daytrade_count   INT NOT NULL DEFAULT 0,
    raw_payload_json JSON NULL,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_bas_exec_run (exec_run_id),
    KEY idx_bas_account_kind (account_id, snapshot_kind)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
