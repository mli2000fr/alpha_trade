-- =====================================================================
-- oracle_extreme_predictions — prédictions OOS de l'Oracle Extreme (O0)
-- =====================================================================
-- Source (écriture) : modelFactory/oracle/walk_forward.py::persist_oos
--   (double écriture avec le parquet, option b : table + parquet puis bascule).
-- Lecture (backtest) : modelFactory/oracle/predictions_store.load_oracle_predictions
--   via --oracle-batch-id (backtesting/cli/_impl.py).
--
-- DISCIPLINE BATCH (cf. doc/controle_couverture.md) :
--   La table accumule les prédictions de TOUTES les campagnes Oracle.
--   TOUJOURS filtrer par batch_id au chargement (jamais "tous batchs confondus").
--   La clé primaire inclut (batch_id, run_id) pour autoriser plusieurs runs
--   par batch sans collision, tout en restant idempotent par run.
-- =====================================================================
CREATE TABLE IF NOT EXISTS alpha_trade.oracle_extreme_predictions (
  prediction_date  DATE         NOT NULL,
  symbol           VARCHAR(20)  NOT NULL,
  proba_extreme    DOUBLE       NOT NULL,
  future_return    DOUBLE       NULL,
  oracle_extreme10 TINYINT      NULL,
  fold_start       DATE         NULL,
  batch_id         VARCHAR(255) NOT NULL,
  run_id           VARCHAR(255) NOT NULL,
  created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (prediction_date, symbol, batch_id, run_id),
  KEY idx_oracle_extreme_batch_date (batch_id, prediction_date),
  KEY idx_oracle_extreme_batch_symbol (batch_id, symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
