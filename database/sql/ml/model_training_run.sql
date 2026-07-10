CREATE TABLE IF NOT EXISTS alpha_trade.model_training_run (
    run_id          VARCHAR(64)     NOT NULL  COMMENT 'UUID ou hash unique du run',
    registry_id     BIGINT UNSIGNED NOT NULL,
    symbol          VARCHAR(20)     NOT NULL,
    status          VARCHAR(20)     NOT NULL  COMMENT 'pending|running|completed|failed|skipped',
    skip_reason     VARCHAR(200)    DEFAULT NULL,
    started_at      DATETIME        DEFAULT NULL,
    finished_at     DATETIME        DEFAULT NULL,
    train_start_date DATE           DEFAULT NULL  COMMENT 'Première date des données d entraînement',
    train_end_date   DATE           DEFAULT NULL  COMMENT 'Dernière date des données d entraînement',
    epochs_run      INT UNSIGNED    DEFAULT 0,
    best_epoch      INT UNSIGNED    DEFAULT NULL,
    checkpoint_path VARCHAR(500)    DEFAULT NULL,
    scaler_path     VARCHAR(500)    DEFAULT NULL,
    config_path     VARCHAR(500)    DEFAULT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id),
    INDEX idx_symbol_status (symbol, status),
    INDEX idx_registry (registry_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Historique des runs d entrainement ML';


