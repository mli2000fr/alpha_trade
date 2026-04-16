ALTER TABLE alpha_trade.stock_bars_daily
    ADD COLUMN `ingested_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        AFTER `is_filled`,
    ADD COLUMN `data_adjustment` VARCHAR(20) NOT NULL DEFAULT 'all'
        AFTER `ingested_at`,
    ADD INDEX `idx_ingested_at` (`ingested_at`);

-- =============================================================================
-- Vérification post-migration
-- =============================================================================
SELECT
    COLUMN_NAME,
    COLUMN_TYPE,
    COLUMN_DEFAULT,
    IS_NULLABLE,
    COLUMN_COMMENT
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = 'alpha_trade'
  AND TABLE_NAME   = 'stock_bars_daily'
  AND COLUMN_NAME  IN ('is_filled', 'ingested_at', 'data_adjustment', 'last_updated')
ORDER BY ORDINAL_POSITION;
