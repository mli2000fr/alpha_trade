CREATE TABLE IF NOT EXISTS stock_earnings_calendar_date_corrections (
    correction_id VARCHAR(32) PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    old_earnings_date DATE NOT NULL,
    replacement_earnings_date DATE NOT NULL,
    observed_at DATETIME NOT NULL,
    provider VARCHAR(32) NOT NULL,
    original_row_json TEXT NOT NULL,
    replacement_evidence_json TEXT NOT NULL,
    INDEX ix_earnings_date_correction_symbol (symbol, old_earnings_date)
);
