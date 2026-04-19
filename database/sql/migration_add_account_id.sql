-- ==========================================================================
-- Migration : ajout de la colonne account_id pour le support multi-comptes
-- ==========================================================================
-- Chaque table liée à un compte broker reçoit une colonne account_id.
-- Les données existantes sont migrées vers 'default'.

-- execution_runs
ALTER TABLE execution_runs
    ADD COLUMN account_id VARCHAR(32) NULL DEFAULT 'default' AFTER total_filled;
ALTER TABLE execution_runs
    ADD INDEX idx_er_account (account_id);

-- broker_positions_snapshots
ALTER TABLE broker_positions_snapshots
    ADD COLUMN account_id VARCHAR(32) NULL DEFAULT 'default' AFTER unrealized_pnl;
ALTER TABLE broker_positions_snapshots
    ADD INDEX idx_bps_account (account_id);

-- risk_decisions
ALTER TABLE risk_decisions
    ADD COLUMN account_id VARCHAR(32) NULL DEFAULT 'default' AFTER correlation_value;
ALTER TABLE risk_decisions
    ADD INDEX idx_rd_account (account_id);

-- portfolio_targets
ALTER TABLE portfolio_targets
    ADD COLUMN account_id VARCHAR(32) NULL DEFAULT 'default' AFTER kelly_fraction;
ALTER TABLE portfolio_targets
    ADD INDEX idx_pt_account (account_id);

-- corporate_actions_applications
ALTER TABLE corporate_actions_applications
    ADD COLUMN account_id VARCHAR(32) NULL DEFAULT 'default' AFTER fractional_shares;
ALTER TABLE corporate_actions_applications
    ADD INDEX idx_caa_account (account_id);

-- portfolio_cash_ledger
ALTER TABLE portfolio_cash_ledger
    ADD COLUMN account_id VARCHAR(32) NULL DEFAULT 'default' AFTER description;
ALTER TABLE portfolio_cash_ledger
    ADD INDEX idx_pcl_account (account_id);

-- Mise à jour des lignes existantes (NULL → 'default')
UPDATE execution_runs SET account_id = 'default' WHERE account_id IS NULL;
UPDATE broker_positions_snapshots SET account_id = 'default' WHERE account_id IS NULL;
UPDATE risk_decisions SET account_id = 'default' WHERE account_id IS NULL;
UPDATE portfolio_targets SET account_id = 'default' WHERE account_id IS NULL;
UPDATE corporate_actions_applications SET account_id = 'default' WHERE account_id IS NULL;
UPDATE portfolio_cash_ledger SET account_id = 'default' WHERE account_id IS NULL;

