CREATE TABLE IF NOT EXISTS alpha_trade.stock_earnings_calendar (
    symbol            VARCHAR(20) NOT NULL,
    earnings_date     DATE        NOT NULL,
    eps_estimate      DOUBLE      DEFAULT NULL,
    eps_actual        DOUBLE      DEFAULT NULL,
    revenue_estimate  DOUBLE      DEFAULT NULL,
    revenue_actual    DOUBLE      DEFAULT NULL,
    fiscal_period     VARCHAR(32) DEFAULT NULL,
    last_updated      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, earnings_date),
    INDEX idx_earnings_date (earnings_date),
    INDEX idx_symbol_earnings_date (symbol, earnings_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Calendrier des earnings pour filtre blackout du selector';

