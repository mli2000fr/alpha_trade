-- Exécuter uniquement si la colonne est absente ; Alembic 0090 est idempotent.
ALTER TABLE alpha_trade.oracle_atr_market_regime_daily
 ADD COLUMN d10_d1_ratio DOUBLE NULL AFTER d10_pct;

-- Aucun recalcul des prix/modèles n'est nécessaire pour les lignes existantes.
UPDATE alpha_trade.oracle_atr_market_regime_daily
 SET d10_d1_ratio = CASE WHEN evaluated_count > 0 AND d1_count > 0
                        THEN d10_count / d1_count ELSE NULL END;
