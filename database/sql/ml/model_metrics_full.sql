-- ==========================================================================
-- model_metrics_full — Persistance ``metrics.json`` complet en BLOB
-- ==========================================================================
-- Phase 4.2.f (alembic mig 0016).
-- Réf. ``prompt/refactor/plan_phase4.md`` § 4.2.f.
--
-- Une ligne par run de training champion. Permet un round-trip 1:1 du
-- ``metrics.json`` indépendamment du fichier disque sous
-- ``artifacts/models/<symbol>/metrics.json`` (qui peut être effacé).
--
-- ``symbol`` est dénormalisé pour faciliter les recherches
-- "tous les runs récents d'un symbole".

CREATE TABLE IF NOT EXISTS alpha_trade.model_metrics_full (
    run_id          VARCHAR(64) NOT NULL,
    symbol          VARCHAR(32) NOT NULL,
    metrics_json    LONGBLOB    NOT NULL
        COMMENT 'JSON sérialisé de metrics.json (champion only)',
    created_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id),
    KEY idx_model_metrics_full_symbol_created_at (symbol, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    COMMENT='Phase 4.2.f — metrics.json complet round-trip BLOB';

