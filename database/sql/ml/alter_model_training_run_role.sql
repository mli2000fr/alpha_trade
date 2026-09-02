-- Contrat directionnel combiné : distinguer les runs LONG et SHORT.
-- À exécuter sur une base déjà créée. La migration Alembic 0070 applique
-- les mêmes opérations de manière idempotente.

ALTER TABLE alpha_trade.model_training_run
    ADD COLUMN model_role VARCHAR(32) NULL
        COMMENT 'Rôle du modèle: direction_legacy|direction_long|direction_short'
        AFTER batch_id;

UPDATE alpha_trade.model_training_run
SET model_role = 'direction_long'
WHERE model_role IS NULL
  AND LOCATE('_direction_long_', run_id) > 0;

UPDATE alpha_trade.model_training_run
SET model_role = 'direction_short'
WHERE model_role IS NULL
  AND LOCATE('_direction_short_', run_id) > 0;

CREATE INDEX idx_batch_role_symbol
    ON alpha_trade.model_training_run (batch_id, model_role, symbol);
