-- E19-A2 / migration 0074 — execute once on alpha_trade.
-- The application reports DATA_READY only after the SEC rows are refreshed
-- and their lineage columns are populated.

ALTER TABLE alpha_trade.stock_fundamentals_daily
    ADD COLUMN available_date DATE NULL
        COMMENT 'First calendar date at which this row may be consumed (strict PIT)'
        AFTER trade_date,
    ADD COLUMN fiscal_period_end DATE NULL
        COMMENT 'Fiscal period represented by the filing'
        AFTER fetched_at,
    ADD COLUMN form VARCHAR(16) NULL
        COMMENT 'SEC form, for example 10-Q or 10-K'
        AFTER fiscal_period_end,
    ADD COLUMN accession_number VARCHAR(32) NULL
        COMMENT 'SEC filing accession number'
        AFTER form,
    ADD COLUMN dividend_per_share FLOAT NULL
        COMMENT 'Dividend per share; distinct from dividend yield'
        AFTER dividend_yield;

UPDATE alpha_trade.stock_fundamentals_daily
SET available_date = CASE
    WHEN UPPER(source) = 'SEC_EDGAR' THEN DATE_ADD(trade_date, INTERVAL 1 DAY)
    ELSE DATE_ADD(DATE(fetched_at), INTERVAL 1 DAY)
END
WHERE available_date IS NULL;

ALTER TABLE alpha_trade.stock_fundamentals_daily
    MODIFY COLUMN available_date DATE NOT NULL
        COMMENT 'First calendar date at which this row may be consumed (strict PIT)',
    ADD INDEX idx_sfd_symbol_available_date (symbol, available_date);
