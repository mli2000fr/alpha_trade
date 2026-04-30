-- ==========================================================================
-- execution_kill_switch_runs — Audit des kill switches d'exécution
-- ==========================================================================
-- Phase 5.2.c (alembic mig 0017).
-- Réf. ``prompt/refactor/plan_phase5.md`` § 5.2.c.
--
-- Trace chaque exécution de la sous-commande
-- ``python -m execution_engine cancel-all --account <id>`` afin d'auditer
-- qui a déclenché un kill switch global, sur quel compte, en quel mode et
-- combien d'ordres ont été annulés vs en échec.

CREATE TABLE IF NOT EXISTS alpha_trade.execution_kill_switch_runs (
    run_id          VARCHAR(64)  NOT NULL,
    account_id      VARCHAR(64)  NOT NULL,
    broker_mode     VARCHAR(16)  NOT NULL
        COMMENT 'paper | live',
    reason          VARCHAR(255) NOT NULL,
    total_open      INT          NOT NULL DEFAULT 0,
    canceled        INT          NOT NULL DEFAULT 0,
    failed          INT          NOT NULL DEFAULT 0,
    dry_run         TINYINT(1)   NOT NULL DEFAULT 0,
    started_at      DATETIME     NOT NULL,
    finished_at     DATETIME     NOT NULL,
    results_json    TEXT         NULL
        COMMENT 'JSON sérialisé list[CancelResult] (broker_order_id, symbol, canceled, error)',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id),
    KEY idx_execution_kill_switch_runs_account_created (account_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    COMMENT='Phase 5.2.c — audit des kill switches global cancel-all';

