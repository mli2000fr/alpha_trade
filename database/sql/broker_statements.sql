CREATE TABLE IF NOT EXISTS alpha_trade.broker_statements (
    id BIGINT NOT NULL AUTO_INCREMENT,
    account_id VARCHAR(64) NOT NULL,
    activity_id VARCHAR(128) NOT NULL,
    activity_type VARCHAR(32) NOT NULL,
    symbol VARCHAR(32) DEFAULT NULL,
    side VARCHAR(16) DEFAULT NULL,
    qty DECIMAL(20, 8) DEFAULT NULL,
    price DECIMAL(20, 8) DEFAULT NULL,
    transaction_time DATETIME DEFAULT NULL,
    raw_json TEXT NOT NULL,
    ingested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_broker_statements_acct_activity (account_id, activity_id),
    INDEX idx_broker_statements_acct_time (account_id, transaction_time),
    INDEX idx_broker_statements_symbol_time (symbol, transaction_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;