-- Migration 0082: annexes SEC stockées séparément du formulaire principal.
CREATE TABLE IF NOT EXISTS alpha_trade.sec_filing_documents (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 accession_number VARCHAR(32) NOT NULL,
 document_sequence INT,
 document_type VARCHAR(32) NOT NULL,
 document_name VARCHAR(255) NOT NULL,
 description VARCHAR(512),
 document_url VARCHAR(512) NOT NULL,
 mime_type VARCHAR(128),
 content_bytes BIGINT,
 content_sha256 VARCHAR(64),
 content_blob LONGBLOB,
 observed_at DATETIME(6) NOT NULL,
 available_at DATETIME(6) NOT NULL,
 run_id VARCHAR(64) NOT NULL,
 UNIQUE KEY uq_sfd_accession_document(accession_number, document_name),
 INDEX idx_sfd_type_available(document_type, available_at),
 INDEX idx_sfd_accession(accession_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
