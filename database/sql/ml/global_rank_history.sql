CREATE TABLE alpha_trade.global_rank_history (
    symbol          VARCHAR(10)     NOT NULL,
    date            DATE            NOT NULL,
    global_rank_3   DOUBLE          NULL    COMMENT 'Rang cross-sectional H3 [0,1] — 1=meilleur',
    global_rank_5   DOUBLE          NULL    COMMENT 'Rang cross-sectional H5 [0,1]',
    global_rank_10  DOUBLE          NULL    COMMENT 'Rang cross-sectional H10 [0,1]',
    global_rank_15  DOUBLE          NULL    COMMENT 'Rang cross-sectional H15 [0,1]',
    global_rank_20  DOUBLE          NULL    COMMENT 'Rang cross-sectional H20 [0,1]',
    batch_id        VARCHAR(64)     NOT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, date, batch_id),
    INDEX idx_grh_date (date),
    INDEX idx_grh_batch_date (batch_id, date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;