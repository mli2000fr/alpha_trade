-- Table FinBERT contextualisée (Niveau 4) — un score par couple (article, symbol).
-- Les colonnes sont calquées sur ``news_sentiment`` mais clavetées par
-- ``(article_id, symbol)``. ``scoring_version`` permet de tracer l'évolution
-- du prompt contextuel ("contextual_v1" = `For {company_name} ({symbol}): ...`).
-- La consommation downstream (``db_io.load_feature_frames``) applique un
-- ``COALESCE(news_ticker_sentiment.X, news_sentiment.X)`` pour rester
-- rétro-compatible avec les runs antérieurs au Niveau 4.
CREATE TABLE IF NOT EXISTS alpha_trade.news_ticker_sentiment (
    article_id VARCHAR(128) NOT NULL,
    symbol VARCHAR(100) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    text_strategy ENUM('contextual_company','contextual_symbol_only','contextual_headline_only') NOT NULL,
    text_hash CHAR(64) NOT NULL,
    truncated TINYINT(1) NOT NULL DEFAULT 0,
    max_length_tokens INT NOT NULL,
    sentiment_label ENUM('positive', 'neutral', 'negative') NOT NULL,
    positive_score DOUBLE NOT NULL,
    neutral_score DOUBLE NOT NULL,
    negative_score DOUBLE NOT NULL,
    sentiment_confidence DOUBLE NOT NULL,
    sentiment_net_score DOUBLE NOT NULL,
    inference_status ENUM('success', 'failed') NOT NULL DEFAULT 'success',
    error_message TEXT NULL,
    model_fingerprint VARCHAR(32) NULL,
    scoring_version VARCHAR(30) NOT NULL DEFAULT 'contextual_v1',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (article_id, symbol),
    KEY idx_nts_symbol_label (symbol, sentiment_label),
    KEY idx_nts_net (sentiment_net_score),
    KEY idx_nts_fingerprint (model_fingerprint),
    KEY idx_nts_scoring_version (scoring_version),
    CONSTRAINT fk_nts_article
        FOREIGN KEY (article_id) REFERENCES alpha_trade.news_raw(article_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_nts_ticker_map
        FOREIGN KEY (article_id, symbol) REFERENCES alpha_trade.news_ticker_map(article_id, symbol)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

