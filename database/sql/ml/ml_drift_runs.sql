-- ==========================================================================
-- ml_drift_runs — Drift monitoring ML
-- ==========================================================================
-- Phase 7.4 (alembic mig 0021).
-- Réf. ``modelFactory/drift_monitor.py``, ``prompt/refactor/plan.md`` Phase 7.
--
-- Une ligne par calcul de drift (souvent quotidien, après ``run_predict``).

CREATE TABLE IF NOT EXISTS alpha_trade.ml_drift_runs (
    run_id          VARCHAR(40) NOT NULL,
    computed_at     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    model_id        VARCHAR(64) NOT NULL,
    ks_stat         DOUBLE      NULL,
    ks_pvalue       DOUBLE      NULL,
    psi             DOUBLE      NULL,
    n_samples       INT         NOT NULL,
    n_baseline      INT         NOT NULL,
    status          VARCHAR(8)  NOT NULL
        COMMENT 'OK | WARN | ALERT',
    payload         JSON        NULL,
    schema_version  INT         NOT NULL DEFAULT 1,
    PRIMARY KEY (run_id),
    KEY ix_ml_drift_model_at (model_id, computed_at),
    CONSTRAINT chk_ml_drift_status CHECK (status IN ('OK','WARN','ALERT'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    COMMENT='Phase 7.4 — drift monitoring ML (KS / PSI)';

