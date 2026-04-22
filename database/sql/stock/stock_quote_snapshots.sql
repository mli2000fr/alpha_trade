CREATE TABLE IF NOT EXISTS alpha_trade.stock_quote_snapshots (
    symbol         VARCHAR(20) NOT NULL,
    quote_date     DATE        NOT NULL,
    quote_timestamp DATETIME   DEFAULT NULL,
    bid_price      DOUBLE      DEFAULT NULL,
    ask_price      DOUBLE      DEFAULT NULL,
    bid_size       DOUBLE      DEFAULT NULL,
    ask_size       DOUBLE      DEFAULT NULL,
    spread_bps     DOUBLE      DEFAULT NULL,
    last_updated   TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, quote_date),
    INDEX idx_quote_date (quote_date),
    INDEX idx_spread_bps (spread_bps)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Snapshots quotidiens des quotes bid/ask pour le filtre de spread du selector';

