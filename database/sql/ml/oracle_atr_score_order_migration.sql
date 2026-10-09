-- US only. Execute once; existing rows are populated by rerunning the study.
ALTER TABLE alpha_trade.oracle_atr_market_regime_daily
 ADD COLUMN predicted_oracle_score_order_returns_pct JSON NULL
 COMMENT 'N rendements realises signes en %, ordre score Oracle decroissant sans reclassement';
