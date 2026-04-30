CREATE TABLE IF NOT EXISTS account_risk_snapshots (
    id                   BIGINT AUTO_INCREMENT PRIMARY KEY,
    account_id           VARCHAR(32)   NOT NULL DEFAULT 'default',
    trade_date           DATE          NOT NULL,
    cash                 DOUBLE        NOT NULL,
    equity               DOUBLE        NOT NULL,
    buying_power         DOUBLE        NOT NULL,
    high_watermark       DOUBLE        NULL,
    daily_realized_pnl   DOUBLE        NULL,
    daily_unrealized_pnl DOUBLE        NULL,
    daily_total_pnl      DOUBLE        NULL,
    created_at           TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_ars_account_trade_created (account_id, trade_date, created_at),
    INDEX idx_ars_account_trade_date (account_id, trade_date),
    INDEX idx_ars_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
