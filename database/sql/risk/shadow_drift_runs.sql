-- ==========================================================================
-- shadow_drift_runs - Comparaison offline live vs simule
-- ==========================================================================
-- Phase 7.7 (alembic mig 0022).
-- Ref. risk_management/shadow_compare.py.
CREATE TABLE IF NOT EXISTS alpha_trade.shadow_drift_runs (
    run_id                  VARCHAR(40) NOT NULL,
    compared_at             DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    live_run_id             VARCHAR(40) NOT NULL,
    simulated_run_id        VARCHAR(40) NOT NULL,
    symbols_only_in_live    JSON        NULL,
    symbols_only_in_sim     JSON        NULL,
    avg_qty_drift_pct       DOUBLE      NULL,
    avg_price_drift_pct     DOUBLE      NULL,
    avg_conviction_drift    DOUBLE      NULL,
    payload                 JSON        NULL,
    schema_version          INT         NOT NULL DEFAULT 1,
    PRIMARY KEY (run_id),
    KEY ix_shadow_drift_compared_at (compared_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    COMMENT='Phase 7.7 - comparaison offline live vs simule';
