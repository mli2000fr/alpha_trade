-- ==========================================================================
-- corporate_actions_applications — Trace des effets appliqués
-- ==========================================================================
-- Chaque ligne documente un ajustement effectif sur une position ou du cash.
-- Lie un événement (corporate_actions_events.id) à son impact concret.

CREATE TABLE IF NOT EXISTS alpha_trade.corporate_actions_applications (
    id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_id            BIGINT        NOT NULL
        COMMENT 'FK vers corporate_actions_events.id',
    symbol              VARCHAR(20)   NOT NULL,
    ca_type             VARCHAR(30)   NOT NULL,
    -- Contexte position au moment de l'application
    position_qty_before DOUBLE        NOT NULL
        COMMENT 'Nombre de parts avant ajustement',
    position_qty_after  DOUBLE        NOT NULL
        COMMENT 'Nombre de parts après ajustement',
    cost_basis_before   DOUBLE        NULL
        COMMENT 'Prix de revient moyen avant ajustement',
    cost_basis_after    DOUBLE        NULL
        COMMENT 'Prix de revient moyen après ajustement',
    -- Impact financier
    cash_impact         DOUBLE        NOT NULL DEFAULT 0
        COMMENT 'Montant cash crédité (dividende) ou débité (cash-in-lieu)',
    fractional_shares   DOUBLE        NOT NULL DEFAULT 0
        COMMENT 'Parts fractionnaires résultant d un split (converties en cash-in-lieu si > 0)',
    -- Audit
    applied_at          TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_caa_event (event_id),
    INDEX idx_caa_sym   (symbol),
    CONSTRAINT fk_caa_event FOREIGN KEY (event_id)
        REFERENCES corporate_actions_events(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    COMMENT='Trace immuable des ajustements appliqués par corporate action';

