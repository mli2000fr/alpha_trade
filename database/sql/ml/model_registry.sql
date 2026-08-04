CREATE TABLE IF NOT EXISTS alpha_trade.model_registry (
    registry_id     BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    symbol          VARCHAR(50)     NOT NULL,
    architecture    VARCHAR(50)     NOT NULL DEFAULT 'lstm_attention',
    version         INT UNSIGNED    NOT NULL DEFAULT 1,
    is_active       TINYINT(1)      NOT NULL DEFAULT 1   COMMENT '1=modèle courant pour inférence',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (registry_id),
    UNIQUE KEY uq_symbol_arch_version (symbol, architecture, version),
    INDEX idx_active (is_active, symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Registre des modeles ML par symbole';


