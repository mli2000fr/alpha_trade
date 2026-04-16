CREATE TABLE IF NOT EXISTS alpha_trade.news_ticker_map (
	article_id VARCHAR(128) NOT NULL,
	symbol VARCHAR(100) NOT NULL,
	sector VARCHAR(100) NULL,
	sector_source VARCHAR(50) NULL,
	sector_updated_at DATETIME(6) NULL,
	is_primary_ticker TINYINT(1) NOT NULL DEFAULT 0,
	created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
	PRIMARY KEY (article_id, symbol),
	KEY idx_news_ticker_map_symbol (symbol),
	KEY idx_news_ticker_map_sector (sector),
	CONSTRAINT fk_news_ticker_map_article
		FOREIGN KEY (article_id) REFERENCES alpha_trade.news_raw(article_id)
		ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

