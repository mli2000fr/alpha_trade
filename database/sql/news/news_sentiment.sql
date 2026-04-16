CREATE TABLE IF NOT EXISTS alpha_trade.news_sentiment (
    article_id VARCHAR(128) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    text_strategy ENUM('content_full', 'headline_summary', 'headline_only') NOT NULL,
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
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (article_id),
    KEY idx_news_sentiment_label (sentiment_label),
    KEY idx_news_sentiment_net (sentiment_net_score),
    CONSTRAINT fk_news_sentiment_article
        FOREIGN KEY (article_id) REFERENCES alpha_trade.news_raw(article_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;