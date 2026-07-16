CREATE TABLE IF NOT EXISTS model_serving_batch (
    scope VARCHAR(32) NOT NULL,
    batch_id VARCHAR(64) NOT NULL,
    promoted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (scope)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COMMENT='Campagne ML promue comme source de serving';