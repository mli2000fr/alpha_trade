-- ==========================================================================
-- portfolio_cash_ledger — Ledger cash immuable
-- ==========================================================================
-- Enregistre tout mouvement de cash lié aux corporate actions.

CREATE TABLE IF NOT EXISTS alpha_trade.portfolio_cash_ledger (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_id        BIGINT        NULL
        COMMENT 'FK vers corporate_actions_events.id (NULL si entrée manuelle)',
    symbol          VARCHAR(20)   NOT NULL,
    entry_type      VARCHAR(30)   NOT NULL
        COMMENT 'dividend_credit | cash_in_lieu | tax_withholding | manual_adjustment',
    amount          DOUBLE        NOT NULL
        COMMENT 'Montant positif = crédit, négatif = débit',
    currency        VARCHAR(5)    NOT NULL DEFAULT 'USD',
    description     VARCHAR(255)  NULL,
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_pcl_symbol (symbol),
    INDEX idx_pcl_type   (entry_type),
    INDEX idx_pcl_event  (event_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    COMMENT='Ledger cash immuable pour dividendes et ajustements corporate actions';

