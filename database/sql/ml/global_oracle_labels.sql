CREATE TABLE alpha_trade.global_oracle_labels (
    prediction_date        DATE         NOT NULL COMMENT 'Date D de la prédiction du Global Model',
    symbol                 VARCHAR(10)  NOT NULL,
    batch_id               VARCHAR(64)  NOT NULL COMMENT 'Batch du Global Model (B25)',
    horizon                INT          NOT NULL COMMENT 'H20=20 (horizon canonique de la 1ʳᵉ expérience)',
    future_return          DOUBLE       NULL COMMENT 'Rendement futur réalisé adj_close[D+H]/adj_close[D]-1 (target brut)',
    oracle_pct_rank        DOUBLE       NULL COMMENT 'Percentile cross-sectionnel intra-date [0,1]',
    oracle_decile          SMALLINT     NULL COMMENT 'Décile 1..10 (10 = meilleur rendement futur)',
    oracle_top10           TINYINT(1)   NULL COMMENT '1 si le titre est dans le TOP 10% cross-sectionnel du jour',
    oracle_bottom10        TINYINT(1)   NULL COMMENT '1 si le titre est dans le BOTTOM 10% cross-sectionnel du jour',
    oracle_exit_date       DATE         NULL COMMENT 'D + horizon',
    oracle_available_date  DATE         NULL COMMENT 'oracle_exit_date + 1 jour ouvrés — garde anti-leakage',
    created_at             DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (prediction_date, symbol, batch_id, horizon),
    KEY idx_gol_batch_date (batch_id, prediction_date),
    KEY idx_gol_available_date (oracle_available_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;