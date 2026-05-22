ALTER TABLE alpha_trade.news_ingestion_checkpoint
    ADD COLUMN news_ingested_at DATETIME(6) NULL AFTER last_error,
    ADD COLUMN relevance_backfill_at DATETIME(6) NULL AFTER news_ingested_at,
    ADD COLUMN contextual_scoring_at DATETIME(6) NULL AFTER relevance_backfill_at,
    ADD COLUMN features_aggregated_at DATETIME(6) NULL AFTER contextual_scoring_at;

