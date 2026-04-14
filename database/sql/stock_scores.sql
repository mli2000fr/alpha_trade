DROP TABLE IF EXISTS stock_scores;

CREATE TABLE stock_scores (
    symbol VARCHAR(20) NOT NULL,
    liquidity_val DOUBLE NOT NULL,
    relative_strength_index DOUBLE NOT NULL,
    historical_range_score DOUBLE NOT NULL,
    total_score DOUBLE NOT NULL,
    last_updated DATETIME NOT NULL,
    PRIMARY KEY (symbol),
    INDEX idx_total_score (total_score)
) ENGINE=InnoDB;
