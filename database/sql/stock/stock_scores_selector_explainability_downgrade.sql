-- Rollback manuel selector : suppression des colonnes de persistance enrichie / explicabilite.
-- Attention : destructive sur les donnees deja ecrites dans ces colonnes.

ALTER TABLE alpha_trade.stock_scores_history
    DROP COLUMN selection_explanation,
    DROP COLUMN selector_signal_mode,
    DROP COLUMN volatility_ratio,
    DROP COLUMN high_52w_proximity,
    DROP COLUMN weekly_trend_score,
    DROP COLUMN atr_pct_20,
    DROP COLUMN rsi_component,
    DROP COLUMN total_score_component,
    DROP COLUMN trend_vcp_component,
    DROP COLUMN relative_strength_index_neutralized,
    DROP COLUMN total_score_neutralized,
    DROP COLUMN normalized_rsi,
    DROP COLUMN normalized_total_score,
    DROP COLUMN raw_final_score,
    DROP COLUMN candidate_rank;

ALTER TABLE alpha_trade.stock_scores
    DROP COLUMN selection_explanation,
    DROP COLUMN selector_signal_mode,
    DROP COLUMN volatility_ratio,
    DROP COLUMN high_52w_proximity,
    DROP COLUMN weekly_trend_score,
    DROP COLUMN atr_pct_20,
    DROP COLUMN rsi_component,
    DROP COLUMN total_score_component,
    DROP COLUMN trend_vcp_component,
    DROP COLUMN relative_strength_index_neutralized,
    DROP COLUMN total_score_neutralized,
    DROP COLUMN normalized_rsi,
    DROP COLUMN normalized_total_score,
    DROP COLUMN raw_final_score,
    DROP COLUMN candidate_rank;

