CREATE TABLE IF NOT EXISTS instruments (
    instrument_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    instrument_uid CHAR(36) NOT NULL,
    market_code VARCHAR(16) NOT NULL,
    exchange_mic CHAR(4) NULL,
    local_symbol VARCHAR(64) NOT NULL,
    display_name VARCHAR(255) NULL,
    instrument_type VARCHAR(32) NOT NULL DEFAULT 'equity',
    currency CHAR(3) NOT NULL,
    listing_date DATE NULL,
    delisting_date DATE NULL,
    mapping_status VARCHAR(32) NOT NULL DEFAULT 'mapped',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (instrument_id),
    UNIQUE KEY uq_instruments_uid (instrument_uid),
    UNIQUE KEY uq_instruments_mic_symbol (exchange_mic, local_symbol),
    KEY ix_instruments_market_active (market_code, is_active),
    KEY ix_instruments_market_symbol (market_code, local_symbol),
    CONSTRAINT fk_instruments_market
        FOREIGN KEY (market_code) REFERENCES markets(market_code),
    CONSTRAINT ck_instruments_currency_iso CHECK (CHAR_LENGTH(currency) = 3),
    CONSTRAINT ck_instruments_dates CHECK (
        delisting_date IS NULL OR listing_date IS NULL OR delisting_date >= listing_date
    ),
    CONSTRAINT ck_instruments_mapping_status CHECK (
        mapping_status IN ('mapped', 'mapping_pending', 'retired')
    ),
    CONSTRAINT ck_instruments_mic_when_mapped CHECK (
        mapping_status <> 'mapped' OR exchange_mic IS NOT NULL
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;