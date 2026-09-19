CREATE TABLE IF NOT EXISTS instrument_provider_symbols (
    mapping_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    instrument_id BIGINT UNSIGNED NOT NULL,
    provider VARCHAR(64) NOT NULL,
    provider_symbol VARCHAR(128) NOT NULL,
    provider_exchange VARCHAR(64) NULL,
    valid_from DATE NOT NULL,
    valid_to DATE NULL,
    is_primary BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (mapping_id),
    UNIQUE KEY uq_ips_identity_start (
        provider, provider_symbol, instrument_id, valid_from
    ),
    KEY ix_ips_resolve (provider, provider_symbol, valid_from, valid_to),
    KEY ix_ips_instrument_provider (
        instrument_id, provider, is_primary, valid_from, valid_to
    ),
    CONSTRAINT fk_ips_instrument
        FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id)
        ON DELETE RESTRICT,
    CONSTRAINT ck_ips_dates CHECK (valid_to IS NULL OR valid_to >= valid_from)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;