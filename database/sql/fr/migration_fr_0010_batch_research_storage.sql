-- Isolated research mirror, not canonical market publication.
CREATE TABLE IF NOT EXISTS fr_batch_research_documents (
 document_id CHAR(64) NOT NULL PRIMARY KEY,
 batch_name VARCHAR(64) NOT NULL,
 market_code VARCHAR(16) NOT NULL DEFAULT 'FR_EQ',
 provider VARCHAR(64) NOT NULL,
 parser_version VARCHAR(32) NOT NULL,
 content_sha256 CHAR(64) NOT NULL,
 source_observed_at DATETIME(6) NULL,
 source_available_at DATETIME(6) NULL,
 sql_available_at DATETIME(6) NOT NULL,
 document_json LONGTEXT NOT NULL,
 record_count INT UNSIGNED NOT NULL,
 ml_eligible BOOLEAN NOT NULL DEFAULT FALSE,
 canonical BOOLEAN NOT NULL DEFAULT FALSE,
 historical_pit_qualified BOOLEAN NOT NULL DEFAULT FALSE,
 UNIQUE KEY uq_fr_batch_research_content (batch_name,content_sha256,parser_version),
 KEY ix_fr_batch_research_available (batch_name,source_available_at),
 CONSTRAINT ck_fr_batch_research_scope CHECK
  (market_code='FR_EQ' AND ml_eligible=0 AND canonical=0 AND historical_pit_qualified=0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_batch_research_file_versions (
 batch_name VARCHAR(64) NOT NULL,
 path_sha256 CHAR(64) NOT NULL,
 document_id CHAR(64) NOT NULL,
 relative_path TEXT NOT NULL,
 archived_role VARCHAR(32) NOT NULL,
 file_modified_at DATETIME(6) NOT NULL,
 imported_at DATETIME(6) NOT NULL,
 PRIMARY KEY (batch_name,path_sha256,document_id),
 CONSTRAINT fk_fr_batch_file_document FOREIGN KEY(document_id)
  REFERENCES fr_batch_research_documents(document_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_calendar_sessions_research (
 document_id CHAR(64) NOT NULL,
 record_sha256 CHAR(64) NOT NULL,
 session_date DATE NOT NULL,
 status VARCHAR(24) NOT NULL,
 open_at_utc DATETIME(6) NULL,
 close_at_utc DATETIME(6) NULL,
 source VARCHAR(64) NULL,
 details_json JSON NOT NULL,
 PRIMARY KEY (document_id,record_sha256),
 KEY ix_fr_calendar_research_date (session_date),
 CONSTRAINT fk_fr_calendar_research_document FOREIGN KEY(document_id)
  REFERENCES fr_batch_research_documents(document_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_reference_versions_research (
 document_id CHAR(64) NOT NULL,
 record_sha256 CHAR(64) NOT NULL,
 isin CHAR(12) NOT NULL,
 symbol VARCHAR(128) NULL,
 mic VARCHAR(8) NOT NULL,
 asof_from DATE NULL,
 asof_to DATE NULL,
 company_name TEXT NULL,
 currency VARCHAR(8) NULL,
 event_type VARCHAR(32) NULL,
 details_json JSON NOT NULL,
 PRIMARY KEY (document_id,record_sha256),
 KEY ix_fr_reference_research_lookup (isin,mic,asof_from),
 CONSTRAINT fk_fr_reference_research_document FOREIGN KEY(document_id)
  REFERENCES fr_batch_research_documents(document_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_corporate_actions_research (
 document_id CHAR(64) NOT NULL,
 record_sha256 CHAR(64) NOT NULL,
 symbol VARCHAR(128) NOT NULL,
 event_type VARCHAR(16) NOT NULL,
 event_date DATE NULL,
 cash_amount DECIMAL(38,12) NULL,
 currency VARCHAR(16) NULL,
 split_numerator DECIMAL(38,12) NULL,
 split_denominator DECIMAL(38,12) NULL,
 validation_status VARCHAR(16) NOT NULL,
 details_json JSON NOT NULL,
 PRIMARY KEY (document_id,record_sha256),
 KEY ix_fr_corporate_research_lookup (symbol,event_date,event_type),
 CONSTRAINT fk_fr_corporate_research_document FOREIGN KEY(document_id)
  REFERENCES fr_batch_research_documents(document_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_amf_positions_research (
 document_id CHAR(64) NOT NULL,
 record_sha256 CHAR(64) NOT NULL,
 isin CHAR(12) NOT NULL,
 symbol VARCHAR(128) NULL,
 holder TEXT NOT NULL,
 position_date DATE NOT NULL,
 publication_date DATE NOT NULL,
 publication_end DATE NULL,
 ratio_percent DECIMAL(20,10) NOT NULL,
 details_json JSON NOT NULL,
 PRIMARY KEY (document_id,record_sha256),
 KEY ix_fr_amf_research_lookup (isin,publication_date),
 CONSTRAINT fk_fr_amf_research_document FOREIGN KEY(document_id)
  REFERENCES fr_batch_research_documents(document_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fr_dila_disclosures_research (
 document_id CHAR(64) NOT NULL,
 record_sha256 CHAR(64) NOT NULL,
 isin CHAR(12) NOT NULL,
 symbol VARCHAR(128) NULL,
 announcement_id VARCHAR(128) NULL,
 publication_day DATE NULL,
 title TEXT NULL,
 document_path TEXT NULL,
 validation_status VARCHAR(16) NOT NULL,
 details_json JSON NOT NULL,
 PRIMARY KEY (document_id,record_sha256),
 KEY ix_fr_dila_research_lookup (isin,publication_day),
 CONSTRAINT fk_fr_dila_research_document FOREIGN KEY(document_id)
  REFERENCES fr_batch_research_documents(document_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
