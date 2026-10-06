-- Existing US database only. Execute once, or use Alembic 0092 instead.
ALTER TABLE alpha_trade.oracle_atr_market_regime_daily
 ADD COLUMN real_oracle_top_returns_pct JSON NULL,
 ADD COLUMN intersection_returns_pct JSON NULL,
 ADD COLUMN predicted_oracle_top_returns_pct JSON NULL,
 ADD COLUMN atr_top_returns_pct JSON NULL;
-- Re-run service.market.oracle_atr_study to populate these columns.
-- Old complete rows are automatically recomputed by calculation version v2.
