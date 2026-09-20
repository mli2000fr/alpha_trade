-- Généré par scripts/render_sprint5_constraint_sql.py.
-- Exécuter uniquement après PASS de bootstrap_us_instruments --mode audit.
-- Alembic reste le chemin d'application canonique.

ALTER TABLE `stock_metadata`
  ADD INDEX `ix_iid_stock_metadata` (`instrument_id`),
  ADD CONSTRAINT `fk_iid_stock_metadata` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `stock_bars_daily`
  ADD INDEX `ix_iid_stock_bars_daily` (`instrument_id`, `date`),
  ADD CONSTRAINT `fk_iid_stock_bars_daily` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `stock_bars`
  ADD INDEX `ix_iid_stock_bars` (`instrument_id`, `timestamp`),
  ADD CONSTRAINT `fk_iid_stock_bars` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `stock_quote_snapshots`
  ADD INDEX `ix_iid_stock_quote_snapshots` (`instrument_id`, `quote_date`),
  ADD CONSTRAINT `fk_iid_stock_quote_snapshots` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `stock_scores`
  ADD INDEX `ix_iid_stock_scores` (`instrument_id`),
  ADD CONSTRAINT `fk_iid_stock_scores` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `stock_scores_history`
  ADD INDEX `ix_iid_stock_scores_history` (`instrument_id`, `snapshot_date`),
  ADD CONSTRAINT `fk_iid_stock_scores_history` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `tradable_universe_history`
  ADD INDEX `ix_iid_tradable_universe_history` (`instrument_id`),
  ADD CONSTRAINT `fk_iid_tradable_universe_history` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `model_predictions`
  ADD INDEX `ix_iid_model_predictions` (`instrument_id`, `prediction_date`),
  ADD CONSTRAINT `fk_iid_model_predictions` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `global_rank_history`
  ADD INDEX `ix_iid_global_rank_history` (`instrument_id`, `date`),
  ADD CONSTRAINT `fk_iid_global_rank_history` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `global_oracle_labels`
  ADD INDEX `ix_iid_global_oracle_labels` (`instrument_id`, `prediction_date`),
  ADD CONSTRAINT `fk_iid_global_oracle_labels` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `oracle_extreme_predictions`
  ADD INDEX `ix_iid_oracle_extreme_predictions` (`instrument_id`, `prediction_date`),
  ADD CONSTRAINT `fk_iid_oracle_extreme_predictions` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `model_registry`
  ADD INDEX `ix_iid_model_registry` (`instrument_id`),
  ADD CONSTRAINT `fk_iid_model_registry` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `model_metrics`
  ADD INDEX `ix_iid_model_metrics` (`instrument_id`),
  ADD CONSTRAINT `fk_iid_model_metrics` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `model_metrics_full`
  ADD INDEX `ix_iid_model_metrics_full` (`instrument_id`),
  ADD CONSTRAINT `fk_iid_model_metrics_full` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `model_batch_diagnostics`
  ADD INDEX `ix_iid_model_batch_diagnostics` (`instrument_id`),
  ADD CONSTRAINT `fk_iid_model_batch_diagnostics` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `model_directional_oos_metrics`
  ADD INDEX `ix_iid_model_directional_oos_metrics` (`instrument_id`),
  ADD CONSTRAINT `fk_iid_model_directional_oos_metrics` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `champion_history`
  ADD INDEX `ix_iid_champion_history` (`instrument_id`),
  ADD CONSTRAINT `fk_iid_champion_history` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `model_governance`
  ADD INDEX `ix_iid_model_governance` (`instrument_id`),
  ADD CONSTRAINT `fk_iid_model_governance` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `stock_fundamentals_daily`
  ADD INDEX `ix_iid_stock_fundamentals_daily` (`instrument_id`, `trade_date`),
  ADD CONSTRAINT `fk_iid_stock_fundamentals_daily` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `stock_earnings_calendar`
  ADD INDEX `ix_iid_stock_earnings_calendar` (`instrument_id`, `earnings_date`),
  ADD CONSTRAINT `fk_iid_stock_earnings_calendar` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `stock_analyst_consensus_snapshots`
  ADD INDEX `ix_iid_stock_analyst_consensus_snapshots` (`instrument_id`, `observed_at`),
  ADD CONSTRAINT `fk_iid_stock_analyst_consensus_snapshots` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `stock_analyst_eps_revision_history`
  ADD INDEX `ix_iid_stock_analyst_eps_revision_history` (`instrument_id`, `snapshot_date`),
  ADD CONSTRAINT `fk_iid_stock_analyst_eps_revision_history` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `stock_analyst_eps_trend_history`
  ADD INDEX `ix_iid_stock_analyst_eps_trend_history` (`instrument_id`, `snapshot_date`),
  ADD CONSTRAINT `fk_iid_stock_analyst_eps_trend_history` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `stock_analyst_estimate_history`
  ADD INDEX `ix_iid_stock_analyst_estimate_history` (`instrument_id`, `snapshot_date`),
  ADD CONSTRAINT `fk_iid_stock_analyst_estimate_history` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `stock_analyst_recommendation_history`
  ADD INDEX `ix_iid_stock_analyst_recommendation_history` (`instrument_id`, `snapshot_date`),
  ADD CONSTRAINT `fk_iid_stock_analyst_recommendation_history` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `stock_analyst_target_history`
  ADD INDEX `ix_iid_stock_analyst_target_history` (`instrument_id`, `snapshot_date`),
  ADD CONSTRAINT `fk_iid_stock_analyst_target_history` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `ticker_daily_sentiment_features`
  ADD INDEX `ix_iid_ticker_daily_sentiment_features` (`instrument_id`, `trade_date`),
  ADD CONSTRAINT `fk_iid_ticker_daily_sentiment_features` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `news_ticker_sentiment`
  ADD INDEX `ix_iid_news_ticker_sentiment` (`instrument_id`),
  ADD CONSTRAINT `fk_iid_news_ticker_sentiment` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `corporate_action_source_events`
  ADD INDEX `ix_iid_corporate_action_source_events` (`instrument_id`),
  ADD CONSTRAINT `fk_iid_corporate_action_source_events` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `corporate_actions_events`
  ADD INDEX `ix_iid_corporate_actions_events` (`instrument_id`, `ex_date`),
  ADD CONSTRAINT `fk_iid_corporate_actions_events` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `corporate_actions_applications`
  ADD INDEX `ix_iid_corporate_actions_applications` (`instrument_id`),
  ADD CONSTRAINT `fk_iid_corporate_actions_applications` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `sec_filing_raw`
  ADD INDEX `ix_iid_sec_filing_raw` (`instrument_id`, `filing_date`),
  ADD CONSTRAINT `fk_iid_sec_filing_raw` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

ALTER TABLE `sec_corporate_events`
  ADD INDEX `ix_iid_sec_corporate_events` (`instrument_id`, `filing_date`),
  ADD CONSTRAINT `fk_iid_sec_corporate_events` FOREIGN KEY (`instrument_id`)
    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;

DELIMITER $$
DROP TRIGGER IF EXISTS `trg_iid_stock_metadata_bi`$$
CREATE TRIGGER trg_iid_stock_metadata_bi BEFORE INSERT ON `stock_metadata` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (LOWER(COALESCE(NEW.asset_class,'')) <> 'crypto') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_metadata_bu`$$
CREATE TRIGGER trg_iid_stock_metadata_bu BEFORE UPDATE ON `stock_metadata` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (LOWER(COALESCE(NEW.asset_class,'')) <> 'crypto') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_bars_daily_bi`$$
CREATE TRIGGER trg_iid_stock_bars_daily_bi BEFORE INSERT ON `stock_bars_daily` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_bars_daily_bu`$$
CREATE TRIGGER trg_iid_stock_bars_daily_bu BEFORE UPDATE ON `stock_bars_daily` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_bars_bi`$$
CREATE TRIGGER trg_iid_stock_bars_bi BEFORE INSERT ON `stock_bars` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_bars_bu`$$
CREATE TRIGGER trg_iid_stock_bars_bu BEFORE UPDATE ON `stock_bars` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_quote_snapshots_bi`$$
CREATE TRIGGER trg_iid_stock_quote_snapshots_bi BEFORE INSERT ON `stock_quote_snapshots` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_quote_snapshots_bu`$$
CREATE TRIGGER trg_iid_stock_quote_snapshots_bu BEFORE UPDATE ON `stock_quote_snapshots` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_scores_bi`$$
CREATE TRIGGER trg_iid_stock_scores_bi BEFORE INSERT ON `stock_scores` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_scores_bu`$$
CREATE TRIGGER trg_iid_stock_scores_bu BEFORE UPDATE ON `stock_scores` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_scores_history_bi`$$
CREATE TRIGGER trg_iid_stock_scores_history_bi BEFORE INSERT ON `stock_scores_history` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_scores_history_bu`$$
CREATE TRIGGER trg_iid_stock_scores_history_bu BEFORE UPDATE ON `stock_scores_history` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_tradable_universe_history_bi`$$
CREATE TRIGGER trg_iid_tradable_universe_history_bi BEFORE INSERT ON `tradable_universe_history` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_tradable_universe_history_bu`$$
CREATE TRIGGER trg_iid_tradable_universe_history_bu BEFORE UPDATE ON `tradable_universe_history` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_model_predictions_bi`$$
CREATE TRIGGER trg_iid_model_predictions_bi BEFORE INSERT ON `model_predictions` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_model_predictions_bu`$$
CREATE TRIGGER trg_iid_model_predictions_bu BEFORE UPDATE ON `model_predictions` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_global_rank_history_bi`$$
CREATE TRIGGER trg_iid_global_rank_history_bi BEFORE INSERT ON `global_rank_history` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_global_rank_history_bu`$$
CREATE TRIGGER trg_iid_global_rank_history_bu BEFORE UPDATE ON `global_rank_history` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_global_oracle_labels_bi`$$
CREATE TRIGGER trg_iid_global_oracle_labels_bi BEFORE INSERT ON `global_oracle_labels` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_global_oracle_labels_bu`$$
CREATE TRIGGER trg_iid_global_oracle_labels_bu BEFORE UPDATE ON `global_oracle_labels` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_oracle_extreme_predictions_bi`$$
CREATE TRIGGER trg_iid_oracle_extreme_predictions_bi BEFORE INSERT ON `oracle_extreme_predictions` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_oracle_extreme_predictions_bu`$$
CREATE TRIGGER trg_iid_oracle_extreme_predictions_bu BEFORE UPDATE ON `oracle_extreme_predictions` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_model_registry_bi`$$
CREATE TRIGGER trg_iid_model_registry_bi BEFORE INSERT ON `model_registry` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_model_registry_bu`$$
CREATE TRIGGER trg_iid_model_registry_bu BEFORE UPDATE ON `model_registry` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_model_metrics_bi`$$
CREATE TRIGGER trg_iid_model_metrics_bi BEFORE INSERT ON `model_metrics` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_model_metrics_bu`$$
CREATE TRIGGER trg_iid_model_metrics_bu BEFORE UPDATE ON `model_metrics` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_model_metrics_full_bi`$$
CREATE TRIGGER trg_iid_model_metrics_full_bi BEFORE INSERT ON `model_metrics_full` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_model_metrics_full_bu`$$
CREATE TRIGGER trg_iid_model_metrics_full_bu BEFORE UPDATE ON `model_metrics_full` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_model_batch_diagnostics_bi`$$
CREATE TRIGGER trg_iid_model_batch_diagnostics_bi BEFORE INSERT ON `model_batch_diagnostics` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_model_batch_diagnostics_bu`$$
CREATE TRIGGER trg_iid_model_batch_diagnostics_bu BEFORE UPDATE ON `model_batch_diagnostics` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_model_directional_oos_metrics_bi`$$
CREATE TRIGGER trg_iid_model_directional_oos_metrics_bi BEFORE INSERT ON `model_directional_oos_metrics` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_model_directional_oos_metrics_bu`$$
CREATE TRIGGER trg_iid_model_directional_oos_metrics_bu BEFORE UPDATE ON `model_directional_oos_metrics` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_champion_history_bi`$$
CREATE TRIGGER trg_iid_champion_history_bi BEFORE INSERT ON `champion_history` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_champion_history_bu`$$
CREATE TRIGGER trg_iid_champion_history_bu BEFORE UPDATE ON `champion_history` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_model_governance_bi`$$
CREATE TRIGGER trg_iid_model_governance_bi BEFORE INSERT ON `model_governance` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_model_governance_bu`$$
CREATE TRIGGER trg_iid_model_governance_bu BEFORE UPDATE ON `model_governance` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_fundamentals_daily_bi`$$
CREATE TRIGGER trg_iid_stock_fundamentals_daily_bi BEFORE INSERT ON `stock_fundamentals_daily` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_fundamentals_daily_bu`$$
CREATE TRIGGER trg_iid_stock_fundamentals_daily_bu BEFORE UPDATE ON `stock_fundamentals_daily` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_earnings_calendar_bi`$$
CREATE TRIGGER trg_iid_stock_earnings_calendar_bi BEFORE INSERT ON `stock_earnings_calendar` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_earnings_calendar_bu`$$
CREATE TRIGGER trg_iid_stock_earnings_calendar_bu BEFORE UPDATE ON `stock_earnings_calendar` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_analyst_consensus_snapshots_bi`$$
CREATE TRIGGER trg_iid_stock_analyst_consensus_snapshots_bi BEFORE INSERT ON `stock_analyst_consensus_snapshots` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_analyst_consensus_snapshots_bu`$$
CREATE TRIGGER trg_iid_stock_analyst_consensus_snapshots_bu BEFORE UPDATE ON `stock_analyst_consensus_snapshots` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_analyst_eps_revision_history_bi`$$
CREATE TRIGGER trg_iid_stock_analyst_eps_revision_history_bi BEFORE INSERT ON `stock_analyst_eps_revision_history` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_analyst_eps_revision_history_bu`$$
CREATE TRIGGER trg_iid_stock_analyst_eps_revision_history_bu BEFORE UPDATE ON `stock_analyst_eps_revision_history` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_analyst_eps_trend_history_bi`$$
CREATE TRIGGER trg_iid_stock_analyst_eps_trend_history_bi BEFORE INSERT ON `stock_analyst_eps_trend_history` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_analyst_eps_trend_history_bu`$$
CREATE TRIGGER trg_iid_stock_analyst_eps_trend_history_bu BEFORE UPDATE ON `stock_analyst_eps_trend_history` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_analyst_estimate_history_bi`$$
CREATE TRIGGER trg_iid_stock_analyst_estimate_history_bi BEFORE INSERT ON `stock_analyst_estimate_history` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_analyst_estimate_history_bu`$$
CREATE TRIGGER trg_iid_stock_analyst_estimate_history_bu BEFORE UPDATE ON `stock_analyst_estimate_history` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_analyst_recommendation_history_bi`$$
CREATE TRIGGER trg_iid_stock_analyst_recommendation_history_bi BEFORE INSERT ON `stock_analyst_recommendation_history` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_analyst_recommendation_history_bu`$$
CREATE TRIGGER trg_iid_stock_analyst_recommendation_history_bu BEFORE UPDATE ON `stock_analyst_recommendation_history` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_analyst_target_history_bi`$$
CREATE TRIGGER trg_iid_stock_analyst_target_history_bi BEFORE INSERT ON `stock_analyst_target_history` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_stock_analyst_target_history_bu`$$
CREATE TRIGGER trg_iid_stock_analyst_target_history_bu BEFORE UPDATE ON `stock_analyst_target_history` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_ticker_daily_sentiment_features_bi`$$
CREATE TRIGGER trg_iid_ticker_daily_sentiment_features_bi BEFORE INSERT ON `ticker_daily_sentiment_features` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_ticker_daily_sentiment_features_bu`$$
CREATE TRIGGER trg_iid_ticker_daily_sentiment_features_bu BEFORE UPDATE ON `ticker_daily_sentiment_features` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_news_ticker_sentiment_bi`$$
CREATE TRIGGER trg_iid_news_ticker_sentiment_bi BEFORE INSERT ON `news_ticker_sentiment` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_news_ticker_sentiment_bu`$$
CREATE TRIGGER trg_iid_news_ticker_sentiment_bu BEFORE UPDATE ON `news_ticker_sentiment` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_corporate_action_source_events_bi`$$
CREATE TRIGGER trg_iid_corporate_action_source_events_bi BEFORE INSERT ON `corporate_action_source_events` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_corporate_action_source_events_bu`$$
CREATE TRIGGER trg_iid_corporate_action_source_events_bu BEFORE UPDATE ON `corporate_action_source_events` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_corporate_actions_events_bi`$$
CREATE TRIGGER trg_iid_corporate_actions_events_bi BEFORE INSERT ON `corporate_actions_events` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_corporate_actions_events_bu`$$
CREATE TRIGGER trg_iid_corporate_actions_events_bu BEFORE UPDATE ON `corporate_actions_events` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_corporate_actions_applications_bi`$$
CREATE TRIGGER trg_iid_corporate_actions_applications_bi BEFORE INSERT ON `corporate_actions_applications` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_corporate_actions_applications_bu`$$
CREATE TRIGGER trg_iid_corporate_actions_applications_bu BEFORE UPDATE ON `corporate_actions_applications` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_sec_filing_raw_bi`$$
CREATE TRIGGER trg_iid_sec_filing_raw_bi BEFORE INSERT ON `sec_filing_raw` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_sec_filing_raw_bu`$$
CREATE TRIGGER trg_iid_sec_filing_raw_bu BEFORE UPDATE ON `sec_filing_raw` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_sec_corporate_events_bi`$$
CREATE TRIGGER trg_iid_sec_corporate_events_bi BEFORE INSERT ON `sec_corporate_events` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DROP TRIGGER IF EXISTS `trg_iid_sec_corporate_events_bu`$$
CREATE TRIGGER trg_iid_sec_corporate_events_bu BEFORE UPDATE ON `sec_corporate_events` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND (UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\-]{0,31}$' AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\_\_%') AND (
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END$$

DELIMITER ;
