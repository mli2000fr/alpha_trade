ALTER TABLE alpha_trade.global_oracle_labels
    ADD COLUMN future_return_raw DOUBLE NULL
        COMMENT 'Rendement brut conserve pour audit, meme si la target est invalidee'
        AFTER future_return,
    ADD COLUMN target_quality_valid TINYINT(1) NOT NULL DEFAULT 0
        COMMENT '1 uniquement si barres D/D+H reelles et continuite du titre valide'
        AFTER oracle_available_date,
    ADD COLUMN target_quality_reason VARCHAR(128) NULL
        COMMENT 'Premier motif deterministe de quarantaine de la target'
        AFTER target_quality_valid,
    ADD COLUMN price_start_source VARCHAR(64) NULL
        COMMENT 'Source de la barre reellement observee a D'
        AFTER target_quality_reason,
    ADD COLUMN price_end_source VARCHAR(64) NULL
        COMMENT 'Source de la barre reellement observee a D+H'
        AFTER price_start_source,
    ADD KEY idx_gol_quality_batch
        (batch_id, horizon, target_quality_valid, prediction_date);
