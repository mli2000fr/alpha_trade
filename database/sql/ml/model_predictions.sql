CREATE TABLE alpha_trade.model_predictions (
    prediction_id       BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    symbol              VARCHAR(20)     NOT NULL,
    prediction_date     DATE            NOT NULL  COMMENT 'Date à laquelle la prédiction est faite',
    predicted_proba     DOUBLE          NOT NULL  COMMENT 'Probabilité classe 1 (hausse 5j)',
    predicted_class     TINYINT(1)      NOT NULL  COMMENT '1=hausse, 0=baisse',
    run_id              VARCHAR(64)     NOT NULL,
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (prediction_id),
    UNIQUE KEY uq_symbol_date_run (symbol, prediction_date, run_id),
    INDEX idx_date (prediction_date),
    INDEX idx_symbol (symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Predictions quotidiennes du module ML';


