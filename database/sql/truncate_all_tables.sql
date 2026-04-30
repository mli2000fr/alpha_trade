-- =============================================================================
-- truncate_all_tables.sql
-- Vide toutes les tables de la base alpha_trade (MySQL)
-- =============================================================================
-- ⚠️  ATTENTION : Cette opération est IRRÉVERSIBLE.
--     Faire un backup avant exécution.
-- =============================================================================

USE alpha_trade;

SET FOREIGN_KEY_CHECKS = 0;

-- ── Stock ──────────────────────────────────────────────────────────────────
TRUNCATE TABLE stock_bars;
TRUNCATE TABLE stock_bars_daily;
TRUNCATE TABLE stock_metadata;
TRUNCATE TABLE stock_scores;
TRUNCATE TABLE cleaning_audit_latest;
TRUNCATE TABLE cleaning_audit_runs;

-- ── News / Sentiment ───────────────────────────────────────────────────────
DELETE FROM news_sentiment;
DELETE FROM news_raw;
TRUNCATE TABLE news_ticker_map;
TRUNCATE TABLE news_ingestion_checkpoint;

-- ── Macro / Événements ────────────────────────────────────────────────────
TRUNCATE TABLE macro_event_audit;

-- ── Features journalières ─────────────────────────────────────────────────
TRUNCATE TABLE ticker_daily_sentiment_features;
TRUNCATE TABLE sector_daily_sentiment_features;

SET FOREIGN_KEY_CHECKS = 1;

-- =============================================================================
-- Vérification rapide : nombre de lignes par table après TRUNCATE
-- =============================================================================
SELECT 'stock_bars'                       AS table_name, COUNT(*) AS nb FROM stock_bars
UNION ALL
SELECT 'stock_bars_daily',                               COUNT(*) FROM stock_bars_daily
UNION ALL
SELECT 'stock_metadata',                                 COUNT(*) FROM stock_metadata
UNION ALL
SELECT 'stock_scores',                                   COUNT(*) FROM stock_scores
UNION ALL
SELECT 'cleaning_audit_latest',                          COUNT(*) FROM cleaning_audit_latest
UNION ALL
SELECT 'cleaning_audit_runs',                            COUNT(*) FROM cleaning_audit_runs
UNION ALL
SELECT 'news_raw',                                       COUNT(*) FROM news_raw
UNION ALL
SELECT 'news_sentiment',                                 COUNT(*) FROM news_sentiment
UNION ALL
SELECT 'news_ticker_map',                                COUNT(*) FROM news_ticker_map
UNION ALL
SELECT 'news_ingestion_checkpoint',                      COUNT(*) FROM news_ingestion_checkpoint
UNION ALL
SELECT 'macro_event_audit',                              COUNT(*) FROM macro_event_audit
UNION ALL
SELECT 'ticker_daily_sentiment_features',                COUNT(*) FROM ticker_daily_sentiment_features
UNION ALL
SELECT 'sector_daily_sentiment_features',                COUNT(*) FROM sector_daily_sentiment_features;

TRUNCATE table alpha_trade.cleaning_audit_latest;
TRUNCATE table alpha_trade.cleaning_audit_runs;
TRUNCATE table alpha_trade.stock_scores;
TRUNCATE table alpha_trade.news_ingestion_checkpoint;
TRUNCATE table alpha_trade.news_sentiment;
TRUNCATE table alpha_trade.news_ticker_map;
TRUNCATE table alpha_trade.sector_daily_sentiment_features;
TRUNCATE table alpha_trade.ticker_daily_sentiment_features;
delete from alpha_trade.news_raw;
TRUNCATE table alpha_trade.risk_decisions;
TRUNCATE table alpha_trade.portfolio_targets;