-- ==========================================================================
-- corporate_actions_audit_runs — Trace exécutions CLI corporate_actions
-- ==========================================================================
-- Phase 5.3.b — Réf. prompt/refactor/plan_phase5.md § 5.3.b.
-- Trace chaque exécution de `python -m corporate_actions {sync,apply,status,run}`
-- afin de surveiller volume, anomalies, divergences cross-check (Phase 5.3.c).
-- Modèle aligné sur cleaning_audit_runs (Phase 3.1).

CREATE TABLE IF NOT EXISTS alpha_trade.corporate_actions_audit_runs (
    run_id              VARCHAR(64)   NOT NULL PRIMARY KEY,
    run_kind            VARCHAR(16)   NOT NULL
        COMMENT 'sync | apply | reconcile | run',
    account_id          VARCHAR(64)   NULL,
    started_at          DATETIME      NOT NULL,
    finished_at         DATETIME      NOT NULL,
    duration_seconds    DOUBLE        NOT NULL DEFAULT 0,
    fetched             INT           NOT NULL DEFAULT 0,
    inserted            INT           NOT NULL DEFAULT 0,
    duplicates          INT           NOT NULL DEFAULT 0,
    invalid             INT           NOT NULL DEFAULT 0,
    applied             INT           NOT NULL DEFAULT 0,
    skipped             INT           NOT NULL DEFAULT 0,
    failed              INT           NOT NULL DEFAULT 0,
    reconcile_diffs     INT           NOT NULL DEFAULT 0,
    anomalies_json      TEXT          NULL
        COMMENT 'JSON anomalies détectées (cross-check Yahoo Phase 5.3.c, divergences ratios, etc.)',
    status              VARCHAR(16)   NOT NULL DEFAULT 'completed',
    summary_json        LONGBLOB      NULL
        COMMENT 'JSON sérialisé du run_summary émis par le CLI',
    created_at          TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_corporate_actions_audit_runs_kind_started (run_kind, started_at),
    INDEX idx_corporate_actions_audit_runs_account (account_id, started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    COMMENT='Trace audit des runs CLI corporate_actions (Phase 5.3.b).';

