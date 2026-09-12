-- Migration manuelle 0078 - Alpaca SIP opening window + versions PIT.
-- A exécuter sur le schéma alpha_trade si Alembic n'est pas utilisé.

ALTER TABLE alpha_trade.stock_opening_window_bars
  ADD COLUMN feed VARCHAR(16) NOT NULL DEFAULT 'legacy' AFTER provider,
  ADD COLUMN adjustment_mode VARCHAR(16) NOT NULL DEFAULT 'raw' AFTER feed,
  ADD COLUMN trade_count BIGINT NULL AFTER minute_volume,
  ADD COLUMN vwap DOUBLE NULL AFTER trade_count,
  DROP PRIMARY KEY,
  ADD PRIMARY KEY (provider, feed, symbol, bar_timestamp),
  ADD INDEX idx_sowb_symbol_time (symbol, bar_timestamp);

CREATE TABLE IF NOT EXISTS alpha_trade.stock_opening_window_bar_versions (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  provider VARCHAR(32) NOT NULL,
  feed VARCHAR(16) NOT NULL,
  adjustment_mode VARCHAR(16) NOT NULL DEFAULT 'raw',
  symbol VARCHAR(32) NOT NULL,
  bar_timestamp DATETIME(6) NOT NULL,
  observed_at DATETIME(6) NOT NULL,
  available_at DATETIME(6) NOT NULL,
  open DOUBLE NOT NULL,
  high DOUBLE NOT NULL,
  low DOUBLE NOT NULL,
  close DOUBLE NOT NULL,
  cumulative_volume BIGINT,
  minute_volume BIGINT,
  trade_count BIGINT,
  vwap DOUBLE,
  session_name VARCHAR(16),
  payload_hash VARCHAR(64) NOT NULL,
  run_id VARCHAR(64) NOT NULL,
  UNIQUE KEY uq_sowbv_identity_hash
    (provider, feed, symbol, bar_timestamp, payload_hash),
  INDEX idx_sowbv_symbol_time (symbol, bar_timestamp),
  INDEX idx_sowbv_available (provider, feed, available_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
