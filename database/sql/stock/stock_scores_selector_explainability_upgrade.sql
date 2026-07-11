-- Upgrade manuel selector : persistance enrichie + explicabilite candidat
-- Cible : MySQL / MariaDB compatibles avec la syntaxe ADD COLUMN IF NOT EXISTS.
-- Si votre version ne supporte pas IF NOT EXISTS, retirez la clause sur les colonnes deja absentes.

ALTER TABLE alpha_trade.stock_scores
    ADD COLUMN IF NOT EXISTS selection_rank INT DEFAULT NULL AFTER earnings_blackout,
    ADD COLUMN IF NOT EXISTS raw_final_score DOUBLE DEFAULT NULL AFTER selection_rank,
    ADD COLUMN IF NOT EXISTS normalized_total_score DOUBLE DEFAULT NULL AFTER raw_final_score,
    ADD COLUMN IF NOT EXISTS normalized_rsi DOUBLE DEFAULT NULL AFTER normalized_total_score,
    ADD COLUMN IF NOT EXISTS total_score_neutralized DOUBLE DEFAULT NULL AFTER normalized_rsi,
    ADD COLUMN IF NOT EXISTS relative_strength_index_neutralized DOUBLE DEFAULT NULL AFTER total_score_neutralized,
    ADD COLUMN IF NOT EXISTS trend_vcp_component DOUBLE DEFAULT NULL AFTER relative_strength_index_neutralized,
    ADD COLUMN IF NOT EXISTS total_score_component DOUBLE DEFAULT NULL AFTER trend_vcp_component,
    ADD COLUMN IF NOT EXISTS rsi_component DOUBLE DEFAULT NULL AFTER total_score_component,
    ADD COLUMN IF NOT EXISTS atr_pct_20 DOUBLE DEFAULT NULL AFTER rsi_component,
    ADD COLUMN IF NOT EXISTS weekly_trend_score DOUBLE DEFAULT NULL AFTER atr_pct_20,
    ADD COLUMN IF NOT EXISTS high_52w_proximity DOUBLE DEFAULT NULL AFTER weekly_trend_score,
    ADD COLUMN IF NOT EXISTS volatility_ratio DOUBLE DEFAULT NULL AFTER high_52w_proximity,
    ADD COLUMN IF NOT EXISTS selector_signal_mode VARCHAR(32) DEFAULT NULL AFTER volatility_ratio,
    ADD COLUMN IF NOT EXISTS selection_explanation VARCHAR(255) DEFAULT NULL AFTER selector_signal_mode;

ALTER TABLE alpha_trade.stock_scores_history
    ADD COLUMN IF NOT EXISTS selection_rank INT DEFAULT NULL AFTER earnings_blackout,
    ADD COLUMN IF NOT EXISTS raw_final_score DOUBLE DEFAULT NULL AFTER selection_rank,
    ADD COLUMN IF NOT EXISTS normalized_total_score DOUBLE DEFAULT NULL AFTER raw_final_score,
    ADD COLUMN IF NOT EXISTS normalized_rsi DOUBLE DEFAULT NULL AFTER normalized_total_score,
    ADD COLUMN IF NOT EXISTS total_score_neutralized DOUBLE DEFAULT NULL AFTER normalized_rsi,
    ADD COLUMN IF NOT EXISTS relative_strength_index_neutralized DOUBLE DEFAULT NULL AFTER total_score_neutralized,
    ADD COLUMN IF NOT EXISTS trend_vcp_component DOUBLE DEFAULT NULL AFTER relative_strength_index_neutralized,
    ADD COLUMN IF NOT EXISTS total_score_component DOUBLE DEFAULT NULL AFTER trend_vcp_component,
    ADD COLUMN IF NOT EXISTS rsi_component DOUBLE DEFAULT NULL AFTER total_score_component,
    ADD COLUMN IF NOT EXISTS atr_pct_20 DOUBLE DEFAULT NULL AFTER rsi_component,
    ADD COLUMN IF NOT EXISTS weekly_trend_score DOUBLE DEFAULT NULL AFTER atr_pct_20,
    ADD COLUMN IF NOT EXISTS high_52w_proximity DOUBLE DEFAULT NULL AFTER weekly_trend_score,
    ADD COLUMN IF NOT EXISTS volatility_ratio DOUBLE DEFAULT NULL AFTER high_52w_proximity,
    ADD COLUMN IF NOT EXISTS selector_signal_mode VARCHAR(32) DEFAULT NULL AFTER volatility_ratio,
    ADD COLUMN IF NOT EXISTS selection_explanation VARCHAR(255) DEFAULT NULL AFTER selector_signal_mode;

-- Verification post-migration
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = 'alpha_trade'
  AND TABLE_NAME IN ('stock_scores', 'stock_scores_history')
  AND COLUMN_NAME IN (
    'selection_rank',
      'raw_final_score',
      'normalized_total_score',
      'normalized_rsi',
      'total_score_neutralized',
      'relative_strength_index_neutralized',
      'trend_vcp_component',
      'total_score_component',
      'rsi_component',
      'atr_pct_20',
      'weekly_trend_score',
      'high_52w_proximity',
      'volatility_ratio',
      'selector_signal_mode',
      'selection_explanation'
  )
ORDER BY TABLE_NAME, ORDINAL_POSITION;

