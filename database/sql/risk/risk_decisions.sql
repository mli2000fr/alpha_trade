CREATE TABLE IF NOT EXISTS risk_decisions (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id          VARCHAR(32)   NOT NULL,
    trade_date      DATE          NOT NULL,
    symbol          VARCHAR(20)   NOT NULL,
    decision        VARCHAR(20)   NOT NULL,
    reason          VARCHAR(255)  NOT NULL,
    score_used      DOUBLE        NULL,
    score_source    VARCHAR(40)   NULL,
    entry_price     DOUBLE        NULL,
    proposed_shares INT           NULL,
    approved_shares INT           NULL,
    target_weight   DOUBLE        NULL,
    sector          VARCHAR(60)   NULL,
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_rd_run       (run_id),
    INDEX idx_rd_date_sym  (trade_date, symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
