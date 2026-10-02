-- v2 distingue OHLC plausible sans volume négocié de VALID pour le trading.
ALTER TABLE fr_staging_progress
  ADD COLUMN classifier_version VARCHAR(32) NOT NULL DEFAULT 'fr_eod_v1' AFTER dataset;
