-- EODHD décrit `volume` EOD comme ajusté des splits. Ne pas le ranger dans
-- `volume_shares` qui désigne le volume brut tel que négocié à l'époque.
ALTER TABLE fr_provider_bars_daily
  ADD COLUMN provider_volume_split_adjusted BIGINT UNSIGNED NULL AFTER volume_shares;

ALTER TABLE stock_bars_daily
  ADD COLUMN volume_split_adjusted BIGINT UNSIGNED NULL AFTER volume_shares;
