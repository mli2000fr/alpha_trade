CREATE TABLE IF NOT EXISTS markets (
    market_code VARCHAR(16) NOT NULL,
    database_alias VARCHAR(64) NOT NULL,
    country_code CHAR(2) NOT NULL,
    currency CHAR(3) NOT NULL,
    timezone VARCHAR(64) NOT NULL,
    calendar_id VARCHAR(32) NOT NULL,
    benchmark_symbol VARCHAR(64) NOT NULL,
    sector_taxonomy VARCHAR(64) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    live_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    context_fingerprint CHAR(64) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (market_code),
    UNIQUE KEY uq_markets_database_alias_market (database_alias, market_code),
    CONSTRAINT ck_markets_country_iso CHECK (CHAR_LENGTH(country_code) = 2),
    CONSTRAINT ck_markets_currency_iso CHECK (CHAR_LENGTH(currency) = 3),
    CONSTRAINT ck_markets_live_enabled CHECK (live_enabled = FALSE OR enabled = TRUE)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;