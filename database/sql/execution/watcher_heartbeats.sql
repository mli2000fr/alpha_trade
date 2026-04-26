-- Phase 1 refactor (audit_watcher.md, audit_global.md §6.8) :
-- heartbeat persistant SQL pour les watchers transverses
-- (execution_protection_watcher et tout futur watcher).
CREATE TABLE IF NOT EXISTS watcher_heartbeats (
    watcher_name        VARCHAR(64)  NOT NULL,
    account_id          VARCHAR(32)  NOT NULL DEFAULT 'default',
    hostname            VARCHAR(128) NULL,
    pid                 INT          NULL,
    status              VARCHAR(16)  NOT NULL DEFAULT 'RUNNING',
    last_heartbeat_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_error          VARCHAR(512) NULL,
    PRIMARY KEY (watcher_name, account_id),
    INDEX idx_watcher_heartbeats_last_heartbeat (last_heartbeat_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

