-- US only. Apply once if the column is absent; no existing data is overwritten.
ALTER TABLE alpha_trade.oracle_atr_market_regime_daily
 ADD COLUMN intersection_oracle_score_order_returns_pct JSON NULL
 COMMENT 'Intersection Oracle ATR: rendements connus en ordre score Oracle decroissant, sans remplacement';
