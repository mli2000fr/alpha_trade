ALTER TABLE alpha_trade.weights_calibration_runs
    ADD COLUMN IF NOT EXISTS market_regime_mode VARCHAR(32) NOT NULL DEFAULT 'all' AFTER scope,
    ADD COLUMN IF NOT EXISTS observations_evaluated INT NULL AFTER candidates,
    ADD COLUMN IF NOT EXISTS scenarios_evaluated INT NULL AFTER observations_evaluated,
    ADD COLUMN IF NOT EXISTS latest_best_scenario_name VARCHAR(255) NULL AFTER scenarios_evaluated,
    ADD COLUMN IF NOT EXISTS final_value DOUBLE NULL AFTER latest_best_scenario_name,
    ADD COLUMN IF NOT EXISTS total_return_pct DOUBLE NULL AFTER final_value,
    ADD COLUMN IF NOT EXISTS sharpe_ratio DOUBLE NULL AFTER total_return_pct,
    ADD COLUMN IF NOT EXISTS max_drawdown_pct DOUBLE NULL AFTER sharpe_ratio,
    ADD COLUMN IF NOT EXISTS artifact_dir VARCHAR(512) NULL AFTER max_drawdown_pct,
    MODIFY COLUMN scope VARCHAR(16) NOT NULL COMMENT 'conviction | sentiment | risk',
    MODIFY COLUMN market_regime_mode VARCHAR(32) NOT NULL DEFAULT 'all' COMMENT 'all | normal | capital_preservation | close_only | cash_only',
    MODIFY COLUMN schema_version INT NOT NULL DEFAULT 2,
    DROP CHECK chk_weights_cal_scope,
    ADD CONSTRAINT chk_weights_cal_scope CHECK (scope IN ('conviction','sentiment','risk'));

ALTER TABLE alpha_trade.weights_calibration_runs
    ADD INDEX IF NOT EXISTS ix_weights_cal_scope_calibrated_at (scope, calibrated_at),
    ADD INDEX IF NOT EXISTS ix_weights_cal_scope_regime_window (scope, market_regime_mode, window_end, calibrated_at);

