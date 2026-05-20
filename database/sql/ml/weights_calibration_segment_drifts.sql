-- ==========================================================================
-- weights_calibration_segment_drifts — Drift inter-segments calibration risk
-- ==========================================================================
-- Phase 7.2 / P3+.
-- Réf. ``backtesting/weights_calibration.py``.

CREATE TABLE IF NOT EXISTS alpha_trade.weights_calibration_segment_drifts (
    run_id               VARCHAR(40)  NOT NULL,
    compared_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    comparison_kind      VARCHAR(48)  NOT NULL
        COMMENT 'vs_all_same_horizon_window | vs_reference_live_segment',
    calibration_batch_id VARCHAR(40)  NULL,
    source_run_id        VARCHAR(40)  NULL,
    target_run_id        VARCHAR(40)  NULL,
    source_segment_key   VARCHAR(160) NULL,
    target_segment_key   VARCHAR(160) NULL,
    metric_name          VARCHAR(32)  NULL,
    metric_delta         DOUBLE       NULL,
    final_value_drift_pct DOUBLE      NULL,
    payload              JSON         NULL,
    schema_version       INT          NOT NULL DEFAULT 1,
    PRIMARY KEY (run_id),
    KEY ix_weights_cal_seg_drift_batch (calibration_batch_id, compared_at),
    KEY ix_weights_cal_seg_drift_source (source_run_id, comparison_kind)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    COMMENT='Phase 7.2 / P3+ — drift inter-segments des calibrations de poids';

