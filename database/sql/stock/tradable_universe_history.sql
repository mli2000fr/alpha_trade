CREATE TABLE IF NOT EXISTS alpha_trade.tradable_universe_runs (
    universe_run_id VARCHAR(64) PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    capital_preset_key VARCHAR(64) NOT NULL,
    config_fingerprint VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL,
    is_canonical BOOLEAN NOT NULL DEFAULT FALSE,
    rows_expected INT NOT NULL,
    rows_written INT NOT NULL DEFAULT 0,
    tradable_rows INT NOT NULL DEFAULT 0,
    data_quality_grade VARCHAR(16) NOT NULL DEFAULT 'unknown',
    failure_reason TEXT NULL,
    started_at DATETIME NOT NULL,
    finished_at DATETIME NULL,
    INDEX idx_universe_runs_asof (
        capital_preset_key,
        snapshot_date,
        status,
        is_canonical
    )
);

CREATE TABLE IF NOT EXISTS alpha_trade.tradable_universe_history (
    universe_run_id VARCHAR(64) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    is_tradable BOOLEAN NOT NULL,
    tradability_reason_code VARCHAR(64) NOT NULL,
    tradability_reasons_json JSON NULL,
    history_days INT NULL,
    bars_available BOOLEAN NULL,
    data_source VARCHAR(32) NULL,
    close_price DOUBLE NULL,
    adv_usd DOUBLE NULL,
    spread_bps DOUBLE NULL,
    market_cap DOUBLE NULL,
    atr_pct_20 DOUBLE NULL,
    earnings_blackout BOOLEAN NULL,
    data_quality_grade VARCHAR(16) NOT NULL DEFAULT 'unknown',
    created_at DATETIME NOT NULL,
    PRIMARY KEY (universe_run_id, symbol),
    CONSTRAINT fk_universe_history_run
        FOREIGN KEY (universe_run_id)
        REFERENCES alpha_trade.tradable_universe_runs (universe_run_id)
        ON DELETE CASCADE,
    INDEX idx_universe_history_scope (universe_run_id, is_tradable, symbol)
);