CREATE TABLE IF NOT EXISTS model_serving_batch (
    market_code VARCHAR(16) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'US_EQ',
    scope VARCHAR(32) NOT NULL,
    batch_id VARCHAR(64) NOT NULL,
    promoted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (market_code, scope),
    CONSTRAINT fk_serving_market FOREIGN KEY (market_code) REFERENCES markets (market_code)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COMMENT='Campagne ML promue comme source de serving';