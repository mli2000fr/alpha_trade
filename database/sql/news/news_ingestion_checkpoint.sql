CREATE TABLE IF NOT EXISTS alpha_trade.news_ingestion_checkpoint (
    source_name VARCHAR(50) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    watermark_published_at_utc DATETIME(6) NULL,
    next_page_token VARCHAR(255) NULL,
    status ENUM('idle', 'running', 'success', 'failed') NOT NULL DEFAULT 'idle',
    last_error TEXT NULL,
    news_ingested_at DATETIME(6) NULL,
    relevance_backfill_at DATETIME(6) NULL,
    contextual_scoring_at DATETIME(6) NULL,
    features_aggregated_at DATETIME(6) NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (source_name, symbol),
    KEY idx_news_ingestion_checkpoint_symbol (symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;