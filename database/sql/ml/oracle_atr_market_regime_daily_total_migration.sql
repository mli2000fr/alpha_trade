-- Exécuter l'ALTER seulement si la colonne est absente ; Alembic 0091 le vérifie.
ALTER TABLE alpha_trade.oracle_atr_market_regime_daily
 ADD COLUMN d1_d10_total_pct DOUBLE NULL AFTER d10_d1_ratio;

UPDATE alpha_trade.oracle_atr_market_regime_daily
 SET d1_d10_total_pct = CASE WHEN evaluated_count > 0
                           THEN 100.0 * (d1_count + d10_count) / evaluated_count
                           ELSE NULL END;
