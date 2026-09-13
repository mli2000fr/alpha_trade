-- Migration 0081: uniformise toutes les provenances Forward PIT à 255 caractères.
ALTER TABLE alpha_trade.pit_raw_payloads MODIFY COLUMN provider VARCHAR(255) NOT NULL;
ALTER TABLE alpha_trade.stock_bars_daily_versions MODIFY COLUMN provider VARCHAR(255) NOT NULL;
ALTER TABLE alpha_trade.security_master_snapshots MODIFY COLUMN provider VARCHAR(255) NOT NULL;
ALTER TABLE alpha_trade.security_master_changes MODIFY COLUMN provider VARCHAR(255) NOT NULL;
ALTER TABLE alpha_trade.corporate_action_source_events MODIFY COLUMN provider VARCHAR(255) NOT NULL;
ALTER TABLE alpha_trade.stock_borrow_status_snapshots MODIFY COLUMN provider VARCHAR(255) NOT NULL;
ALTER TABLE alpha_trade.stock_analyst_consensus_snapshots MODIFY COLUMN provider VARCHAR(255) NOT NULL;
ALTER TABLE alpha_trade.stock_option_snapshots MODIFY COLUMN provider VARCHAR(255) NOT NULL;
ALTER TABLE alpha_trade.stock_opening_window_bars MODIFY COLUMN provider VARCHAR(255) NOT NULL;
ALTER TABLE alpha_trade.stock_opening_window_bar_versions MODIFY COLUMN provider VARCHAR(255) NOT NULL;
ALTER TABLE alpha_trade.macro_vintage_observations MODIFY COLUMN provider VARCHAR(255) NOT NULL;
ALTER TABLE alpha_trade.pit_data_quality_metrics MODIFY COLUMN provider VARCHAR(255) NULL;
ALTER TABLE alpha_trade.pit_data_quality_issues MODIFY COLUMN provider VARCHAR(255) NULL;
ALTER TABLE alpha_trade.stock_short_volume_daily MODIFY COLUMN provider VARCHAR(255) NOT NULL;
ALTER TABLE alpha_trade.stock_option_contract_versions MODIFY COLUMN provider VARCHAR(255) NOT NULL;
ALTER TABLE alpha_trade.stock_option_bars_delayed MODIFY COLUMN provider VARCHAR(255) NOT NULL;
ALTER TABLE alpha_trade.option_contract_adjustments MODIFY COLUMN provider VARCHAR(255) NOT NULL;
