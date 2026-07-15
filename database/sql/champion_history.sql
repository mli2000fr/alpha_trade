CREATE TABLE IF NOT EXISTS alpha_trade.champion_history (
    id BIGINT NOT NULL AUTO_INCREMENT,
    symbol VARCHAR(32) NOT NULL,
    model_id VARCHAR(128) NOT NULL,
    version VARCHAR(64) DEFAULT NULL,
    promoted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    demoted_at DATETIME DEFAULT NULL,
    reason VARCHAR(256) NOT NULL DEFAULT '',
    previous_model_id VARCHAR(128) DEFAULT NULL COMMENT 'model_id du champion remplace (NULL si premier).',
    dry_run TINYINT(1) NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_champion_history_symbol_promoted (symbol, promoted_at),
    INDEX idx_champion_history_symbol_demoted (symbol, demoted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;