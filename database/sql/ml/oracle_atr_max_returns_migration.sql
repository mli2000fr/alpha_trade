-- US only. Apply once if absent. Preserve the separate maximum-price column.
ALTER TABLE alpha_trade.oracle_atr_market_regime_daily
 ADD COLUMN predicted_oracle_score_order_max_returns_pct JSON NULL
 COMMENT 'N premiers Oracle en ordre score: excursion high/low J+1..J+H de plus forte amplitude, signe conserve, % entiers; retrospectif';
