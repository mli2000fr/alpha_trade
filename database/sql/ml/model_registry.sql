CREATE TABLE IF NOT EXISTS alpha_trade.model_registry (
    registry_id     BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    market_code     VARCHAR(16) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'US_EQ',
    symbol          VARCHAR(50)     NOT NULL,
    architecture    VARCHAR(50)     NOT NULL DEFAULT 'lstm_attention',
    version         INT UNSIGNED    NOT NULL DEFAULT 1,
    is_active       TINYINT(1)      NOT NULL DEFAULT 1   COMMENT '1=modèle courant pour inférence',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (registry_id),
    UNIQUE KEY uq_market_symbol_arch_version (market_code, symbol, architecture, version),
    INDEX idx_active (is_active, symbol),
    INDEX idx_registry_market_active (market_code, is_active, symbol),
    CONSTRAINT fk_registry_market FOREIGN KEY (market_code) REFERENCES alpha_trade.markets (market_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Registre des modeles ML par symbole';


