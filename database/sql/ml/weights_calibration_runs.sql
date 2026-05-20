-- ==========================================================================
-- weights_calibration_runs — Calibration empirique des poids
-- ==========================================================================
-- Phase 7.2 (alembic mig 0020).
-- Réf. ``backtesting/weights_calibration.py``, ``prompt/refactor/plan.md`` Phase 7.
--
-- Persistance des résultats de calibration empirique des poids
-- ``ConvictionWeights`` et ``SentimentFusionWeights``.

CREATE TABLE IF NOT EXISTS alpha_trade.weights_calibration_runs (
    run_id                   VARCHAR(40)  NOT NULL,
    calibrated_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    scope                    VARCHAR(16)  NOT NULL
        COMMENT 'conviction | sentiment | risk',
    market_regime_mode       VARCHAR(32)  NOT NULL DEFAULT 'all'
        COMMENT 'all | normal | capital_preservation | close_only | cash_only',
    window_start             DATE         NOT NULL,
    window_end               DATE         NOT NULL,
    metric_name              VARCHAR(32)  NOT NULL
        COMMENT 'sharpe | hit_rate | ic',
    metric_value             DOUBLE       NOT NULL,
    best_weights             JSON         NOT NULL,
    candidates               JSON         NULL
        COMMENT 'Grille testée + métriques',
    observations_evaluated   INT          NULL,
    scenarios_evaluated      INT          NULL,
    latest_best_scenario_name VARCHAR(255) NULL,
    final_value              DOUBLE       NULL,
    total_return_pct         DOUBLE       NULL,
    sharpe_ratio             DOUBLE       NULL,
    max_drawdown_pct         DOUBLE       NULL,
    artifact_dir             VARCHAR(512) NULL,
    git_sha                  VARCHAR(40)  NULL,
    schema_version           INT          NOT NULL DEFAULT 2,
    PRIMARY KEY (run_id),
    KEY ix_weights_cal_scope_calibrated_at (scope, calibrated_at),
    KEY ix_weights_cal_scope_regime_window (scope, market_regime_mode, window_end, calibrated_at),
    CONSTRAINT chk_weights_cal_scope CHECK (scope IN ('conviction','sentiment','risk'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    COMMENT='Phase 7.2 / P3 — calibration empirique poids conviction/sentiment/risk segmentée par régime';

