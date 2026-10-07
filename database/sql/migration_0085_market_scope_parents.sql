-- Sprint 3 CN - à exécuter uniquement après 0084_market_instrument_foundation.
ALTER TABLE model_training_batch
  ADD COLUMN market_code VARCHAR(16) COLLATE utf8mb4_unicode_ci NULL,
  ADD COLUMN calendar_id VARCHAR(32) NULL,
  ADD COLUMN base_currency CHAR(3) NULL,
  ADD COLUMN benchmark_instrument_id BIGINT UNSIGNED NULL,
  ADD COLUMN universe_id VARCHAR(255) NULL,
  ADD COLUMN universe_fingerprint CHAR(64) NULL,
  ADD COLUMN sector_taxonomy VARCHAR(32) NULL,
  ADD COLUMN market_context_fingerprint CHAR(64) NULL;
UPDATE model_training_batch SET market_code='US_EQ', calendar_id='NYSE', base_currency='USD',
  sector_taxonomy='GICS', market_context_fingerprint='ac71a3039fb43e25ac732d0393a7748bca85272db35ee89472d46368809546e2'
WHERE market_code IS NULL;
ALTER TABLE model_training_batch
  MODIFY market_code VARCHAR(16) COLLATE utf8mb4_unicode_ci NOT NULL, MODIFY calendar_id VARCHAR(32) NOT NULL,
  MODIFY base_currency CHAR(3) NOT NULL, MODIFY sector_taxonomy VARCHAR(32) NOT NULL,
  MODIFY market_context_fingerprint CHAR(64) NOT NULL,
  ADD INDEX idx_mtb_market_status_started (market_code,status,started_at),
  ADD CONSTRAINT fk_mtb_market FOREIGN KEY (market_code) REFERENCES markets(market_code),
  ADD CONSTRAINT fk_mtb_benchmark FOREIGN KEY (benchmark_instrument_id) REFERENCES instruments(instrument_id);

ALTER TABLE model_registry ADD COLUMN market_code VARCHAR(16) COLLATE utf8mb4_unicode_ci NULL;
UPDATE model_registry SET market_code='US_EQ' WHERE market_code IS NULL;
ALTER TABLE model_registry MODIFY market_code VARCHAR(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  DROP INDEX uq_symbol_arch_version,
  ADD UNIQUE KEY uq_market_symbol_arch_version (market_code,symbol,architecture,version),
  ADD INDEX idx_registry_market_active (market_code,is_active,symbol),
  ADD CONSTRAINT fk_registry_market FOREIGN KEY (market_code) REFERENCES markets(market_code);

ALTER TABLE model_training_run ADD COLUMN market_code VARCHAR(16) COLLATE utf8mb4_unicode_ci NULL;
UPDATE model_training_run r LEFT JOIN model_training_batch b ON b.batch_id=r.batch_id
SET r.market_code=COALESCE(b.market_code,'US_EQ') WHERE r.market_code IS NULL;
ALTER TABLE model_training_run MODIFY market_code VARCHAR(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  ADD INDEX idx_mtr_market_batch_status (market_code,batch_id,status),
  ADD CONSTRAINT fk_mtr_market FOREIGN KEY (market_code) REFERENCES markets(market_code);

ALTER TABLE model_serving_batch ADD COLUMN market_code VARCHAR(16) COLLATE utf8mb4_unicode_ci NULL;
UPDATE model_serving_batch SET market_code='US_EQ' WHERE market_code IS NULL;
ALTER TABLE model_serving_batch MODIFY market_code VARCHAR(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  DROP PRIMARY KEY, ADD PRIMARY KEY (market_code,scope),
  ADD CONSTRAINT fk_serving_market FOREIGN KEY (market_code) REFERENCES markets(market_code);

ALTER TABLE tradable_universe_runs
  ADD COLUMN market_code VARCHAR(16) COLLATE utf8mb4_unicode_ci NULL, ADD COLUMN calendar_id VARCHAR(32) NULL,
  ADD COLUMN base_currency CHAR(3) NULL, ADD COLUMN sector_taxonomy VARCHAR(32) NULL,
  ADD COLUMN market_context_fingerprint CHAR(64) NULL, ADD COLUMN universe_fingerprint CHAR(64) NULL;
UPDATE tradable_universe_runs SET market_code='US_EQ', calendar_id='NYSE', base_currency='USD',
  sector_taxonomy='GICS', market_context_fingerprint='ac71a3039fb43e25ac732d0393a7748bca85272db35ee89472d46368809546e2',
  universe_fingerprint=config_fingerprint WHERE market_code IS NULL;
ALTER TABLE tradable_universe_runs MODIFY market_code VARCHAR(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  MODIFY calendar_id VARCHAR(32) NOT NULL, MODIFY base_currency CHAR(3) NOT NULL,
  MODIFY sector_taxonomy VARCHAR(32) NOT NULL, MODIFY market_context_fingerprint CHAR(64) NOT NULL,
  MODIFY universe_fingerprint CHAR(64) NOT NULL,
  ADD INDEX idx_tur_market_status_started (market_code,status,started_at),
  ADD CONSTRAINT fk_tur_market FOREIGN KEY (market_code) REFERENCES markets(market_code);

ALTER TABLE execution_runs
  ADD COLUMN market_code VARCHAR(16) COLLATE utf8mb4_unicode_ci NULL, ADD COLUMN calendar_id VARCHAR(32) NULL,
  ADD COLUMN base_currency CHAR(3) NULL, ADD COLUMN market_context_fingerprint CHAR(64) NULL;
UPDATE execution_runs SET market_code='US_EQ', calendar_id='NYSE', base_currency='USD',
  market_context_fingerprint='ac71a3039fb43e25ac732d0393a7748bca85272db35ee89472d46368809546e2'
WHERE market_code IS NULL;
ALTER TABLE execution_runs MODIFY market_code VARCHAR(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  MODIFY calendar_id VARCHAR(32) NOT NULL, MODIFY base_currency CHAR(3) NOT NULL,
  MODIFY market_context_fingerprint CHAR(64) NOT NULL,
  ADD INDEX idx_execution_market_status_started (market_code,status,started_at),
  ADD CONSTRAINT fk_execution_market FOREIGN KEY (market_code) REFERENCES markets(market_code);
DROP TRIGGER IF EXISTS trg_mtr_market_guard_insert;
DROP TRIGGER IF EXISTS trg_mtr_market_guard_update;
DELIMITER $$
CREATE TRIGGER trg_mtr_market_guard_insert
BEFORE INSERT ON model_training_run FOR EACH ROW
BEGIN
  IF NEW.batch_id IS NOT NULL AND EXISTS (
    SELECT 1 FROM model_training_batch b
    WHERE b.batch_id=NEW.batch_id AND b.market_code<>NEW.market_code
  ) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='training run market differs from batch';
  END IF;
  IF EXISTS (
    SELECT 1 FROM model_registry r
    WHERE r.registry_id=NEW.registry_id AND r.market_code<>NEW.market_code
  ) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='training run market differs from registry';
  END IF;
END$$
CREATE TRIGGER trg_mtr_market_guard_update
BEFORE UPDATE ON model_training_run FOR EACH ROW
BEGIN
  IF NEW.batch_id IS NOT NULL AND EXISTS (
    SELECT 1 FROM model_training_batch b
    WHERE b.batch_id=NEW.batch_id AND b.market_code<>NEW.market_code
  ) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='training run market differs from batch';
  END IF;
  IF EXISTS (
    SELECT 1 FROM model_registry r
    WHERE r.registry_id=NEW.registry_id AND r.market_code<>NEW.market_code
  ) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='training run market differs from registry';
  END IF;
END$$
DELIMITER ;