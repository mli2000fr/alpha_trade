-- US alpha_trade only. Additive, no historical backfill or current-row updates.
-- Timestamps are explicit UTC DATETIME(6), not publication-derived observation times.
CREATE TABLE IF NOT EXISTS news_raw_versions (
 id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 article_id VARCHAR(128) NOT NULL, received_article_id VARCHAR(128) NOT NULL,
 ingestion_source VARCHAR(50) NOT NULL, snapshot_hash VARCHAR(64) NOT NULL,
 text_hash VARCHAR(64) NOT NULL, headline VARCHAR(1000) NOT NULL,
 summary TEXT NULL, content MEDIUMTEXT NULL, source VARCHAR(100) NULL,
 author VARCHAR(255) NULL, url VARCHAR(2083) NULL,
 published_at_utc DATETIME(6) NULL, provider_publication VARCHAR(128) NULL,
 publication_precision VARCHAR(32) NOT NULL, publication_utc DATETIME(6) NULL,
 raw_payload JSON NOT NULL, first_observed_at DATETIME(6) NOT NULL,
 CONSTRAINT uq_news_raw_version UNIQUE (article_id,snapshot_hash),
 INDEX ix_news_raw_versions_publication (published_at_utc)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS news_ticker_map_versions (
 id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 article_id VARCHAR(128) NOT NULL, raw_version_id BIGINT NOT NULL,
 snapshot_hash VARCHAR(64) NOT NULL, mapping_rows JSON NOT NULL,
 mapping_context JSON NOT NULL, payload_scope_complete BOOLEAN NOT NULL,
 first_observed_at DATETIME(6) NOT NULL,
 CONSTRAINT uq_news_map_version UNIQUE (article_id,snapshot_hash),
 FOREIGN KEY (raw_version_id) REFERENCES news_raw_versions(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS news_archive_observations (
 id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 batch_id VARCHAR(32) NOT NULL, article_id VARCHAR(128) NOT NULL,
 stream_key VARCHAR(128) NOT NULL, origin VARCHAR(32) NOT NULL,
 raw_version_id BIGINT NULL, mapping_version_id BIGINT NULL,
 observed_at DATETIME(6) NOT NULL, available_at DATETIME(6) NULL,
 CONSTRAINT ck_news_archive_one_version CHECK ((raw_version_id IS NULL) <> (mapping_version_id IS NULL)),
 FOREIGN KEY (raw_version_id) REFERENCES news_raw_versions(id) ON DELETE RESTRICT,
 FOREIGN KEY (mapping_version_id) REFERENCES news_ticker_map_versions(id) ON DELETE RESTRICT,
 INDEX ix_news_archive_stream (article_id,stream_key,id),
 INDEX ix_news_archive_available (available_at), INDEX ix_news_archive_batch (batch_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
