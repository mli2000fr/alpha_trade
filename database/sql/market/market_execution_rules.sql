CREATE TABLE IF NOT EXISTS market_execution_rules (
    rule_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    market_code VARCHAR(16) NOT NULL,
    exchange_mic CHAR(4) NULL,
    board_code VARCHAR(32) NULL,
    valid_from DATE NOT NULL,
    valid_to DATE NULL,
    currency CHAR(3) NOT NULL,
    settlement_cycle_days SMALLINT UNSIGNED NOT NULL,
    buy_lot_size INT UNSIGNED NOT NULL DEFAULT 1,
    sell_lot_size INT UNSIGNED NOT NULL DEFAULT 1,
    tick_size DECIMAL(18, 8) NULL,
    daily_price_limit_pct DECIMAL(10, 6) NULL,
    short_selling_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    same_day_sell_allowed BOOLEAN NOT NULL DEFAULT TRUE,
    metadata_json JSON NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (rule_id),
    UNIQUE KEY uq_mer_scope_start (
        market_code, exchange_mic, board_code, valid_from
    ),
    KEY ix_mer_asof (
        market_code, exchange_mic, board_code, valid_from, valid_to
    ),
    CONSTRAINT fk_mer_market
        FOREIGN KEY (market_code) REFERENCES markets(market_code),
    CONSTRAINT ck_mer_currency_iso CHECK (CHAR_LENGTH(currency) = 3),
    CONSTRAINT ck_mer_dates CHECK (valid_to IS NULL OR valid_to >= valid_from),
    CONSTRAINT ck_mer_lots CHECK (buy_lot_size > 0 AND sell_lot_size > 0),
    CONSTRAINT ck_mer_tick CHECK (tick_size IS NULL OR tick_size > 0),
    CONSTRAINT ck_mer_price_limit CHECK (
        daily_price_limit_pct IS NULL OR
        (daily_price_limit_pct > 0 AND daily_price_limit_pct <= 1)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;