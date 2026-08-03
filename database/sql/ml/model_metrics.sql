CREATE TABLE IF NOT EXISTS alpha_trade.model_metrics (
    metric_id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    run_id                  VARCHAR(64)     NOT NULL,
    symbol                  VARCHAR(50)     NOT NULL,
    model_name              VARCHAR(32)     NOT NULL DEFAULT 'lstm_attention' COMMENT 'lstm_attention|lightgbm|catboost|global_model',
    split_name              VARCHAR(10)     NOT NULL  COMMENT 'train|val|test|wf',
    loss                    DOUBLE          DEFAULT NULL,
    directional_accuracy    DOUBLE          DEFAULT NULL,
    `precision`             DOUBLE          DEFAULT NULL,
    recall                  DOUBLE          DEFAULT NULL,
    auc                     DOUBLE          DEFAULT NULL,
    -- ML Sprint 7 — support ternaire
    f1_macro                DOUBLE          DEFAULT NULL COMMENT 'F1 macro (ternaire uniquement)',
    f1_short                DOUBLE          DEFAULT NULL COMMENT 'F1 classe short',
    f1_flat                 DOUBLE          DEFAULT NULL COMMENT 'F1 classe flat',
    f1_long                 DOUBLE          DEFAULT NULL COMMENT 'F1 classe long',
    created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    true_short_pct          DOUBLE          DEFAULT NULL COMMENT 'Pourcentage reel de la classe short',
    true_flat_pct           DOUBLE          DEFAULT NULL COMMENT 'Pourcentage reel de la classe flat',
    true_long_pct           DOUBLE          DEFAULT NULL COMMENT 'Pourcentage reel de la classe long',
    pred_short_pct          DOUBLE          DEFAULT NULL COMMENT 'Pourcentage predit de la classe short',
    pred_flat_pct           DOUBLE          DEFAULT NULL COMMENT 'Pourcentage predit de la classe flat',
    pred_long_pct           DOUBLE          DEFAULT NULL COMMENT 'Pourcentage predit de la classe long',
    PRIMARY KEY (metric_id),
    INDEX idx_run (run_id),
    INDEX idx_symbol (symbol),
    INDEX idx_model_name (model_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Metriques resumees par run, split et modele';


