ALTER TABLE alpha_trade.weights_calibration_runs
    ADD COLUMN IF NOT EXISTS calibration_batch_id VARCHAR(40) NULL AFTER scope,
    ADD COLUMN IF NOT EXISTS market_regime_mode VARCHAR(32) NOT NULL DEFAULT 'all' AFTER calibration_batch_id,
    ADD COLUMN IF NOT EXISTS segment_key VARCHAR(160) NULL AFTER market_regime_mode,
    ADD COLUMN IF NOT EXISTS horizon_days INT NOT NULL DEFAULT 5 AFTER segment_key,
    ADD COLUMN IF NOT EXISTS lookback_months INT NOT NULL DEFAULT 12 AFTER horizon_days,
    ADD COLUMN IF NOT EXISTS distinct_snapshot_days INT NULL AFTER candidates,
    ADD COLUMN IF NOT EXISTS distinct_symbols INT NULL AFTER distinct_snapshot_days,
    ADD COLUMN IF NOT EXISTS eligible_for_live TINYINT(1) NOT NULL DEFAULT 0 AFTER distinct_symbols,
    ADD COLUMN IF NOT EXISTS eligibility_reason VARCHAR(255) NULL AFTER eligible_for_live,
    ADD COLUMN IF NOT EXISTS observations_evaluated INT NULL AFTER eligibility_reason,
    ADD COLUMN IF NOT EXISTS scenarios_evaluated INT NULL AFTER observations_evaluated,
    ADD COLUMN IF NOT EXISTS latest_best_scenario_name VARCHAR(255) NULL AFTER scenarios_evaluated,
    ADD COLUMN IF NOT EXISTS final_value DOUBLE NULL AFTER latest_best_scenario_name,
    ADD COLUMN IF NOT EXISTS total_return_pct DOUBLE NULL AFTER final_value,
    ADD COLUMN IF NOT EXISTS sharpe_ratio DOUBLE NULL AFTER total_return_pct,
    ADD COLUMN IF NOT EXISTS max_drawdown_pct DOUBLE NULL AFTER sharpe_ratio,
    ADD COLUMN IF NOT EXISTS artifact_dir VARCHAR(512) NULL AFTER max_drawdown_pct,
    MODIFY COLUMN scope VARCHAR(16) NOT NULL COMMENT 'conviction | sentiment | risk',
    MODIFY COLUMN market_regime_mode VARCHAR(32) NOT NULL DEFAULT 'all' COMMENT 'all | normal | capital_preservation | close_only | cash_only',
    MODIFY COLUMN horizon_days INT NOT NULL DEFAULT 5,
    MODIFY COLUMN lookback_months INT NOT NULL DEFAULT 12,
    MODIFY COLUMN schema_version INT NOT NULL DEFAULT 2,
    DROP CHECK chk_weights_cal_scope,
    ADD CONSTRAINT chk_weights_cal_scope CHECK (scope IN ('conviction','sentiment','risk'));

ALTER TABLE alpha_trade.weights_calibration_runs
    ADD INDEX IF NOT EXISTS ix_weights_cal_scope_calibrated_at (scope, calibrated_at),
    ADD INDEX IF NOT EXISTS ix_weights_cal_scope_regime_window (scope, market_regime_mode, window_end, calibrated_at),
    ADD INDEX IF NOT EXISTS ix_weights_cal_batch_segment (calibration_batch_id, segment_key),
    ADD INDEX IF NOT EXISTS ix_weights_cal_live_promotion (scope, horizon_days, lookback_months, market_regime_mode, eligible_for_live, window_end);

CREATE TABLE IF NOT EXISTS alpha_trade.weights_calibration_segment_drifts (
    run_id                VARCHAR(40)  NOT NULL,
    compared_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    comparison_kind       VARCHAR(48)  NOT NULL,
    calibration_batch_id  VARCHAR(40)  NULL,
    source_run_id         VARCHAR(40)  NULL,
    target_run_id         VARCHAR(40)  NULL,
    source_segment_key    VARCHAR(160) NULL,
    target_segment_key    VARCHAR(160) NULL,
    metric_name           VARCHAR(32)  NULL,
    metric_delta          DOUBLE       NULL,
    final_value_drift_pct DOUBLE       NULL,
    payload               JSON         NULL,
    schema_version        INT          NOT NULL DEFAULT 1,
    PRIMARY KEY (run_id),
    KEY ix_weights_cal_seg_drift_batch (calibration_batch_id, compared_at),
    KEY ix_weights_cal_seg_drift_source (source_run_id, comparison_kind)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

