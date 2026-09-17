-- Préserve exactement les volumes FINRA à six décimales; aucun arrondi.
ALTER TABLE alpha_trade.stock_short_volume_daily
  MODIFY short_volume DECIMAL(24,6) NOT NULL,
  MODIFY short_exempt_volume DECIMAL(24,6) NOT NULL,
  MODIFY total_volume DECIMAL(24,6) NOT NULL;
