CREATE TABLE IF NOT EXISTS alpha_trade.news_ticker_map (
	article_id VARCHAR(128) NOT NULL,
	symbol VARCHAR(100) NOT NULL,
	sector VARCHAR(100) NULL,
	sector_source VARCHAR(50) NULL,
	sector_updated_at DATETIME(6) NULL,
	is_primary_ticker TINYINT(1) NOT NULL DEFAULT 0,
	relevance_score FLOAT NULL COMMENT 'Score [0,1] de pertinence article->symbole (NULL = mode provider_default, COALESCE 1.0 en aval).',
	relevance_components JSON NULL COMMENT 'Audit trail des composantes du score (name_in_headline, ticker_in_text, primary_bonus, multi_ticker_penalty, version).',
	created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
	PRIMARY KEY (article_id, symbol),
	KEY idx_news_ticker_map_symbol (symbol),
	KEY idx_news_ticker_map_sector (sector),
	KEY idx_news_ticker_map_relevance (relevance_score),
	CONSTRAINT fk_news_ticker_map_article
		FOREIGN KEY (article_id) REFERENCES alpha_trade.news_raw(article_id)
		ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

