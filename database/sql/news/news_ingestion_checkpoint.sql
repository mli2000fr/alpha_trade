CREATE TABLE IF NOT EXISTS alpha_trade.news_ingestion_checkpoint (
    source_name VARCHAR(50) NOT NULL,
    watermark_published_at_utc DATETIME(6) NULL,
    next_page_token VARCHAR(255) NULL,
    status ENUM('idle', 'running', 'success', 'failed') NOT NULL DEFAULT 'idle',
    last_error TEXT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (source_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;