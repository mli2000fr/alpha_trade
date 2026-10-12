-- US only. Apply once if absent. Existing rows remain NULL until recalculated.
ALTER TABLE alpha_trade.oracle_atr_market_regime_daily
 ADD COLUMN predicted_oracle_score_order_max_prices JSON NULL
 COMMENT 'N premiers Oracle en ordre score: max high J+1..J+H, USD sur echelle prix J; retrospectif';
