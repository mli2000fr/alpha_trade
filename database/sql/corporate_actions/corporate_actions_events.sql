-- ==========================================================================
-- corporate_actions_events — Journal immuable des événements corporate actions
-- ==========================================================================
-- Chaque ligne représente un événement brut ingéré depuis un provider.
-- La table est append-only : on ne modifie jamais une ligne existante.

CREATE TABLE IF NOT EXISTS alpha_trade.corporate_actions_events (
    id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
    -- Clé d'idempotence déterministe : provider + symbol + ca_type + ex_date + amount/ratio
    idempotency_key     VARCHAR(64)   NOT NULL UNIQUE
        COMMENT 'SHA-256 tronqué pour déduplication stricte',
    provider            VARCHAR(30)   NOT NULL DEFAULT 'alpaca'
        COMMENT 'Source du corporate action event (alpaca, polygon, manual…)',
    provider_event_id   VARCHAR(128)  NULL
        COMMENT 'Identifiant brut chez le provider si disponible',
    symbol              VARCHAR(20)   NOT NULL,
    ca_type             VARCHAR(30)   NOT NULL
        COMMENT 'cash_dividend | split | reverse_split | special_dividend | …',
    -- Montants / ratios
    amount_per_share    DOUBLE        NULL
        COMMENT 'Dividende par action (NULL si split)',
    split_from          INT           NULL
        COMMENT 'Dénominateur du ratio split (ex: 1 pour 2:1)',
    split_to            INT           NULL
        COMMENT 'Numérateur du ratio split (ex: 2 pour 2:1)',
    currency            VARCHAR(5)    NOT NULL DEFAULT 'USD',
    -- Dates utiles
    announcement_date   DATE          NULL,
    ex_date             DATE          NOT NULL
        COMMENT 'Date ex-dividende ou date effective du split',
    record_date         DATE          NULL,
    payable_date        DATE          NULL,
    -- Payload brut source
    raw_payload         JSON          NULL
        COMMENT 'Payload JSON brut reçu du provider pour audit',
    -- Statut de traitement
    status              VARCHAR(20)   NOT NULL DEFAULT 'pending'
        COMMENT 'pending | applied | skipped | failed',
    error_message       VARCHAR(500)  NULL,
    -- Timestamps
    ingested_at         TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    applied_at          TIMESTAMP     NULL,
    -- Phase 5.3.a — clé d'idempotence scopée par account_id (mig 0019)
    account_idempotency_key VARCHAR(64) NULL
        COMMENT 'sha256(account_or_GLOBAL|provider|symbol|ca_type|ex_date|amount_or_split)[:32] — NULL = events historiques pré-migration',
    INDEX idx_cae_symbol    (symbol),
    INDEX idx_cae_type      (ca_type),
    INDEX idx_cae_ex_date   (ex_date),
    INDEX idx_cae_status    (status),
    UNIQUE KEY uq_corporate_actions_events_account_idem (account_idempotency_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    COMMENT='Journal immuable des corporate actions ingérées';

