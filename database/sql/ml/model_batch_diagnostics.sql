CREATE TABLE IF NOT EXISTS alpha_trade.model_batch_diagnostics (
    id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    batch_id            VARCHAR(64)     NOT NULL,
    batch_started_at    DATETIME        NOT NULL,
    symbol              VARCHAR(20)     NOT NULL,
    f1_macro_wf         DOUBLE          NOT NULL,
    f1_long_wf          DOUBLE          DEFAULT NULL,
    f1_short_wf         DOUBLE          DEFAULT NULL,
    f1_flat_wf          DOUBLE          DEFAULT NULL,
    rank_type           VARCHAR(20)     NOT NULL,
    rank_position       INT UNSIGNED    DEFAULT NULL,
    threshold_used      DOUBLE          DEFAULT NULL,
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_batch_diag_batch_rank (batch_id, rank_type),
    INDEX idx_batch_diag_symbol (symbol),
    INDEX idx_batch_diag_started (batch_started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ML batch diagnostics for live and backtest symbol filtering';
