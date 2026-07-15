CREATE TABLE IF NOT EXISTS alpha_trade.audit_chain_events (
    id BIGINT NOT NULL AUTO_INCREMENT,
    run_kind VARCHAR(32) NOT NULL COMMENT 'execution_runs | risk_runs | corporate_action_runs | ...',
    run_id VARCHAR(64) NOT NULL,
    payload_canonical_json TEXT NOT NULL COMMENT 'JSON canonique (sort_keys=True) signe.',
    prev_hash VARCHAR(64) NOT NULL DEFAULT '' COMMENT 'HMAC du precedent maillon de la chaine (par run_kind).',
    hmac_sha256 VARCHAR(64) NOT NULL COMMENT 'HMAC-SHA256(key_version, prev_hash || payload_canonical_json).',
    key_version INT NOT NULL DEFAULT 1,
    signed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_audit_chain_events_kind_signed (run_kind, signed_at),
    INDEX idx_audit_chain_events_kind_run (run_kind, run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;