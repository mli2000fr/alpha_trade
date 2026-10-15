-- Compagnon des scores dans oracle_extreme_predictions, même clé date/titre/batch.
-- Ces scores prédisent l'amplitude du parcours ; aucun label terminal ni direction.
CREATE TABLE IF NOT EXISTS alpha_trade.oracle_path_prediction_lineage (
 prediction_date DATE NOT NULL, symbol VARCHAR(20) NOT NULL, batch_id VARCHAR(255) NOT NULL,
 fold_start DATE NOT NULL, model_available_date DATE NOT NULL,
 target_name VARCHAR(64) NOT NULL, target_horizon INT NOT NULL,
 model_sha256 CHAR(64) NOT NULL, feature_profile_sha256 CHAR(64) NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(prediction_date,symbol,batch_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
