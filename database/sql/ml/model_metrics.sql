CREATE TABLE IF NOT EXISTS alpha_trade.model_metrics (
    metric_id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    run_id                  VARCHAR(64)     NOT NULL,
    symbol                  VARCHAR(20)     NOT NULL,
    split_name              VARCHAR(10)     NOT NULL  COMMENT 'train|val|test',
    loss                    DOUBLE          DEFAULT NULL,
    directional_accuracy    DOUBLE          DEFAULT NULL,
    `precision`             DOUBLE          DEFAULT NULL,
    recall                  DOUBLE          DEFAULT NULL,
    auc                     DOUBLE          DEFAULT NULL,
    created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (metric_id),
    INDEX idx_run (run_id),
    INDEX idx_symbol (symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Metriques resumees par run et split';


