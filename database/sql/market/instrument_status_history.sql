CREATE TABLE IF NOT EXISTS instrument_status_history (
    status_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    instrument_id BIGINT UNSIGNED NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE NULL,
    listing_status VARCHAR(32) NOT NULL,
    trading_status VARCHAR(32) NOT NULL,
    is_tradable BOOLEAN NOT NULL,
    is_special_treatment BOOLEAN NOT NULL DEFAULT FALSE,
    board_code VARCHAR(32) NULL,
    source VARCHAR(64) NOT NULL,
    observed_at DATETIME(6) NOT NULL,
    available_at DATETIME(6) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (status_id),
    UNIQUE KEY uq_ish_instrument_start_source (
        instrument_id, valid_from, source
    ),
    KEY ix_ish_asof (instrument_id, valid_from, valid_to),
    CONSTRAINT fk_ish_instrument
        FOREIGN KEY (instrument_id) REFERENCES instruments(instrument_id)
        ON DELETE RESTRICT,
    CONSTRAINT ck_ish_dates CHECK (valid_to IS NULL OR valid_to >= valid_from),
    CONSTRAINT ck_ish_pit CHECK (available_at >= observed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;