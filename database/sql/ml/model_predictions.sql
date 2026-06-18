CREATE TABLE IF NOT EXISTS alpha_trade.model_predictions (
    prediction_id       BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    symbol              VARCHAR(20)     NOT NULL,
    prediction_date     DATE            NOT NULL  COMMENT 'Date à laquelle la prédiction est faite',
    predicted_proba     DOUBLE          NOT NULL  COMMENT 'Probabilité classe 1 (hausse 5j) — mode binaire',
    predicted_class     TINYINT(1)      NOT NULL  COMMENT '1=hausse, 0=baisse — mode binaire',
    predicted_side      VARCHAR(10)     DEFAULT NULL COMMENT 'ML Sprint 3 — long | flat | short (mode ternaire)',
    proba_long          DOUBLE          DEFAULT NULL COMMENT 'ML Sprint 3 — probabilité classe long',
    proba_flat          DOUBLE          DEFAULT NULL COMMENT 'ML Sprint 3 — probabilité classe flat',
    proba_short         DOUBLE          DEFAULT NULL COMMENT 'ML Sprint 3 — probabilité classe short',
    run_id              VARCHAR(64)     NOT NULL,
    selected_model      VARCHAR(32)     DEFAULT NULL COMMENT 'Backend réellement servi: lstm_attention|lightgbm|catboost|global_model',
    decision_threshold  DOUBLE          DEFAULT NULL COMMENT 'Seuil utilisé pour convertir la probabilité en classe',
    signal_label        VARCHAR(32)     DEFAULT NULL COMMENT 'Signal dérivé: long|no_trade',
    calibration_method  VARCHAR(32)     DEFAULT NULL COMMENT 'Méthode de calibration appliquée à la probabilité',
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (prediction_id),
    UNIQUE KEY uq_symbol_date_run (symbol, prediction_date, run_id),
    INDEX idx_date (prediction_date),
    INDEX idx_symbol (symbol),
    INDEX idx_selected_model (selected_model),
    INDEX idx_predicted_side (predicted_side)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Predictions quotidiennes du module ML';


