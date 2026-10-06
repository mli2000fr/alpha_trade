CREATE TABLE IF NOT EXISTS market_sessions (
    market_code VARCHAR(16) NOT NULL,
    session_date DATE NOT NULL,
    session_status VARCHAR(24) NOT NULL DEFAULT 'open',
    open_at_utc DATETIME(6) NULL,
    close_at_utc DATETIME(6) NULL,
    session_segments_json JSON NULL,
    settlement_date DATE NULL,
    source VARCHAR(64) NOT NULL,
    observed_at DATETIME(6) NOT NULL,
    available_at DATETIME(6) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (market_code, session_date),
    CONSTRAINT fk_market_sessions_market
        FOREIGN KEY (market_code) REFERENCES markets(market_code),
    CONSTRAINT ck_market_sessions_status CHECK (
        session_status IN ('open', 'closed', 'half_day', 'special')
    ),
    CONSTRAINT ck_market_sessions_hours CHECK (
        close_at_utc IS NULL OR open_at_utc IS NULL OR close_at_utc > open_at_utc
    ),
    CONSTRAINT ck_market_sessions_pit CHECK (available_at >= observed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;