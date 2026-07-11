ALTER TABLE execution_targets_snapshot
    ADD COLUMN IF NOT EXISTS selection_rank INT NULL AFTER symbol,
    ADD COLUMN IF NOT EXISTS selector_signal_mode VARCHAR(32) NULL AFTER decision_rank,
    ADD COLUMN IF NOT EXISTS selection_explanation VARCHAR(255) NULL AFTER selector_signal_mode,
    ADD COLUMN IF NOT EXISTS selector_earnings_blackout TINYINT(1) NULL AFTER selection_explanation;

