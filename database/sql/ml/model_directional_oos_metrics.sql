CREATE TABLE model_directional_oos_metrics (
    run_id VARCHAR(64) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    side VARCHAR(8) NOT NULL,
    split_name VARCHAR(16) NOT NULL,
    as_of_date DATE NOT NULL,
    hit_rate FLOAT NOT NULL,
    payoff FLOAT NOT NULL,
    tail_loss FLOAT NULL,
    trade_count INTEGER NOT NULL,
    policy_version INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (run_id, symbol, side, split_name),

    CONSTRAINT ck_directional_oos_side
        CHECK (side IN ('long', 'short')),

    CONSTRAINT ck_directional_oos_hit_rate
        CHECK (hit_rate >= 0 AND hit_rate <= 1),

    CONSTRAINT ck_directional_oos_payoff
        CHECK (payoff > 0),

    CONSTRAINT ck_directional_oos_trade_count
        CHECK (trade_count > 0),

    CONSTRAINT fk_model_directional_oos_metrics_run
        FOREIGN KEY (run_id)
        REFERENCES model_training_run(run_id)
        ON DELETE CASCADE
);

CREATE INDEX idx_directional_oos_metrics_pit
    ON model_directional_oos_metrics (
        symbol,
        side,
        as_of_date,
        split_name
    );