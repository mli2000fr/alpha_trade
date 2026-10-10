-- US only, execute once. No source-price/model mutation; rerun the study after migration.
ALTER TABLE alpha_trade.oracle_atr_market_regime_daily
 ADD COLUMN missing_returns_policy VARCHAR(16) NOT NULL DEFAULT 'strict',
 ADD COLUMN movement_quality JSON NULL
 COMMENT 'Couverture, ordre des symboles et inconnus de chaque liste; TOP reel partiel explicite';
