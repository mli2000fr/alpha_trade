CREATE TABLE alpha_trade.stock_fundamentals_daily (
    id BIGINT AUTO_INCREMENT NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    fetched_at DATETIME NOT NULL COMMENT 'UTC timestamp of the EODHD API fetch',
    -- Valuation
    pe_ratio FLOAT COMMENT 'Trailing P/E (Highlights.PERatio)',
    forward_pe FLOAT COMMENT 'Forward P/E (Valuation.ForwardPE)',
    peg_ratio FLOAT COMMENT 'PEG ratio (Highlights.PEGRatio)',
    pb_ratio FLOAT COMMENT 'Price/Book MRQ (Valuation.PriceBookMRQ)',
    ps_ratio FLOAT COMMENT 'Price/Sales TTM (Valuation.PriceSalesTTM)',
    ev_to_ebitda FLOAT COMMENT 'EV/EBITDA (Valuation.EnterpriseValueEbitda)',
    -- Profitability
    roe FLOAT COMMENT 'Return on Equity TTM (Highlights.ReturnOnEquityTTM)',
    roa FLOAT COMMENT 'Return on Assets TTM (Highlights.ReturnOnAssetsTTM)',
    net_margin FLOAT COMMENT 'Net profit margin (Highlights.ProfitMargin)',
    operating_margin FLOAT COMMENT 'Operating margin TTM (Highlights.OperatingMarginTTM)',
    gross_margin FLOAT COMMENT 'Gross margin = GrossProfitTTM / RevenueTTM',
    -- Growth
    eps_growth_yoy FLOAT COMMENT 'Quarterly earnings growth YoY',
    revenue_growth_yoy FLOAT COMMENT 'Quarterly revenue growth YoY',
    -- Health
    debt_to_equity FLOAT COMMENT 'Total Debt / Equity',
    current_ratio FLOAT COMMENT 'Current assets / Current liabilities',
    -- Yield
    dividend_yield FLOAT COMMENT 'Dividend yield % (Highlights.DividendYield)',
    -- Market
    market_cap FLOAT COMMENT 'Market capitalization',
    beta FLOAT COMMENT 'Beta (Technicals.Beta)',
    eps FLOAT COMMENT 'Earnings per share (Highlights.EarningsShare)',
    book_value_per_share FLOAT COMMENT 'Book value per share (Highlights.BookValue)',
    ebitda FLOAT COMMENT 'EBITDA (Highlights.EBITDA)',
    -- Estimates
    eps_estimate_current FLOAT COMMENT 'EPS estimate current year',
    eps_estimate_next FLOAT COMMENT 'EPS estimate next year',
    -- Metadata
    source VARCHAR(32) NOT NULL DEFAULT 'EODHD' COMMENT 'Data provider',
    PRIMARY KEY (id),
    UNIQUE KEY uq_symbol_date (symbol, trade_date),
    INDEX idx_sfd_symbol (symbol),
    INDEX idx_sfd_date (trade_date),
    INDEX idx_sfd_symbol_date (symbol, trade_date)
);