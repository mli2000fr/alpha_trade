-- Migration 0080: plusieurs fournisseurs peuvent être associés à un même run.
ALTER TABLE alpha_trade.pit_collection_runs
  MODIFY COLUMN provider VARCHAR(255) NULL;
