-- Anti-SL: preserve the Python/manifest double precision during SQL round trips.
-- Apply once to an existing US table, before restarting ML Predict.
-- Widening preserves old values but cannot recover their lost precision:
-- regenerate the required dates with the exact original model batch afterwards.
-- Readers keep the strict 1e-12 contract check and perform no SQL repair.
ALTER TABLE alpha_trade.oracle_path_anti_sl_predictions
  MODIFY anti_sl_probability DOUBLE NULL,
  MODIFY anti_sl_threshold DOUBLE NULL;
