-- Migration manuelle équivalente à Alembic 0077_yahoo_analyst_trends.
SOURCE database/sql/stock/stock_analyst_eps_trend_history.sql;
SOURCE database/sql/stock/stock_analyst_eps_revision_history.sql;

ALTER TABLE `analyst_snapshot_collection_run`
  ADD COLUMN `eps_trend_rows_inserted` int DEFAULT NULL AFTER `estimates_rows_inserted`,
  ADD COLUMN `eps_revision_rows_inserted` int DEFAULT NULL AFTER `eps_trend_rows_inserted`,
  ADD COLUMN `eps_trend_coverage` double DEFAULT NULL AFTER `revenue_coverage`,
  ADD COLUMN `eps_revision_coverage` double DEFAULT NULL AFTER `eps_trend_coverage`;
