CREATE TABLE IF NOT EXISTS execution_order_requests (
    request_id         VARCHAR(32) PRIMARY KEY,
    exec_run_id        VARCHAR(32) NOT NULL,
    account_id         VARCHAR(32) NOT NULL,
    risk_run_id        VARCHAR(32) NOT NULL,
    symbol             VARCHAR(20) NOT NULL,
    side               VARCHAR(10) NOT NULL,
    target_qty         DOUBLE NOT NULL,
    order_type         VARCHAR(20) NOT NULL,
    business_key       VARCHAR(64) NOT NULL,
    submission_key     VARCHAR(64) NULL,
    attempt_no         INT NOT NULL, -- numéro entier de tentative pour ce business_key (contrat applicatif strict)
    parent_request_id  VARCHAR(32) NULL,
    intent_role        VARCHAR(20) NOT NULL,
    decision_price     DOUBLE NULL,
    limit_price        DOUBLE NULL,
    stop_price         DOUBLE NULL,
    trail_percent      DOUBLE NULL,
    status             VARCHAR(20) NOT NULL DEFAULT 'NEW',
    failure_reason     VARCHAR(255) NULL,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_eor_account_business_attempt (account_id, business_key, attempt_no), -- unicité par tentative pour un ordre logique
    UNIQUE KEY uq_eor_submission_key (submission_key),
    KEY idx_eor_exec_run (exec_run_id),
    KEY idx_eor_business_key (business_key),
    KEY idx_eor_parent_request (parent_request_id),
    KEY idx_eor_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

