-- Autorise les identifiants dynamiques `universe-file:<nom-du-fichier>.txt`.
-- Migration non destructive : les valeurs existantes sont conservées.
ALTER TABLE alpha_trade.model_training_batch
    MODIFY COLUMN symbol_source VARCHAR(255) NOT NULL
    COMMENT 'Source native ou universe-file:<nom>.txt';
