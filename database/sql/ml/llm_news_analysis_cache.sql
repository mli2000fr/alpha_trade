-- US stored-news research cache. Does not publish selections or orders.
-- available_at is the local post-commit receipt, never a historical news date.
CREATE TABLE IF NOT EXISTS alpha_trade.llm_news_analysis_cache (
    cache_key VARCHAR(64) NOT NULL,
    market_code VARCHAR(16) NOT NULL,
    symbol VARCHAR(100) NOT NULL,
    analysis_scope VARCHAR(32) NOT NULL,
    provider VARCHAR(20) NOT NULL,
    model_requested VARCHAR(128) NOT NULL,
    model_returned VARCHAR(128) NULL,
    protocol_sha256 VARCHAR(64) NOT NULL,
    request_json LONGTEXT NOT NULL,
    response_json LONGTEXT NULL,
    response_sha256 VARCHAR(64) NULL,
    usage_json LONGTEXT NULL,
    assessment_json LONGTEXT NULL,
    status VARCHAR(24) NOT NULL,
    owner_token VARCHAR(32) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    response_received_at DATETIME(6) NULL,
    available_at DATETIME(6) NULL,
    error_type VARCHAR(128) NULL,
    PRIMARY KEY (cache_key),
    KEY ix_llm_news_symbol (symbol, analysis_scope)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alpha_trade.llm_news_analysis_research_runs (
    import_id VARCHAR(64) NOT NULL,
    source_ref TEXT NOT NULL,
    snapshot_sha256 VARCHAR(64) NOT NULL,
    snapshot_json LONGTEXT NOT NULL,
    imported_at DATETIME(6) NOT NULL,
    PRIMARY KEY (import_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alpha_trade.llm_news_analysis_articles (
    cache_key VARCHAR(64) NOT NULL,
    article_position INT NOT NULL,
    article_id VARCHAR(128) NOT NULL,
    article_sha256 VARCHAR(64) NOT NULL,
    PRIMARY KEY (cache_key, article_position),
    KEY ix_llm_news_article (article_id, article_sha256),
    FOREIGN KEY (cache_key) REFERENCES alpha_trade.llm_news_analysis_cache(cache_key) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alpha_trade.llm_news_analysis_uses (
    use_key VARCHAR(64) NOT NULL,
    cache_key VARCHAR(64) NOT NULL,
    consumer_run_id VARCHAR(255) NOT NULL,
    use_kind VARCHAR(24) NOT NULL,
    recorded_at DATETIME(6) NOT NULL,
    details_json LONGTEXT NOT NULL,
    PRIMARY KEY (use_key),
    KEY ix_llm_news_consumer (consumer_run_id),
    FOREIGN KEY (cache_key) REFERENCES alpha_trade.llm_news_analysis_cache(cache_key) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
