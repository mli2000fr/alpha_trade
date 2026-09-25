-- Sprint 12-A : contrat CN_A daté, isolé dans alpha_trade_cn.
-- Exécuter sur alpha_trade_cn uniquement, après migration_cn_0007.
-- Aucune règle/prix/frais de ce fichier n'autorise le trading live.

CREATE TABLE IF NOT EXISTS market_execution_rules (
    rule_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    market_code VARCHAR(16) NOT NULL,
    exchange_mic CHAR(4) NULL,
    board_code VARCHAR(32) NULL,
    valid_from DATE NOT NULL,
    valid_to DATE NULL,
    currency CHAR(3) NOT NULL,
    settlement_cycle_days SMALLINT UNSIGNED NOT NULL,
    buy_lot_size INT UNSIGNED NOT NULL DEFAULT 1,
    sell_lot_size INT UNSIGNED NOT NULL DEFAULT 1,
    tick_size DECIMAL(18, 8) NULL,
    daily_price_limit_pct DECIMAL(10, 6) NULL,
    short_selling_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    same_day_sell_allowed BOOLEAN NOT NULL DEFAULT TRUE,
    metadata_json JSON NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (rule_id),
    UNIQUE KEY uq_mer_scope_start (market_code, exchange_mic, board_code, valid_from),
    KEY ix_mer_asof (market_code, exchange_mic, board_code, valid_from, valid_to),
    CONSTRAINT fk_mer_market FOREIGN KEY (market_code) REFERENCES markets(market_code),
    CONSTRAINT ck_mer_lots CHECK (buy_lot_size > 0 AND sell_lot_size > 0),
    CONSTRAINT ck_mer_dates CHECK (valid_to IS NULL OR valid_to >= valid_from),
    CONSTRAINT ck_mer_price_limit CHECK (
        daily_price_limit_pct IS NULL OR (daily_price_limit_pct > 0 AND daily_price_limit_pct <= 1)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cn_execution_cost_profiles (
    profile_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    market_code VARCHAR(16) NOT NULL DEFAULT 'CN_A',
    profile_key VARCHAR(64) NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE NULL,
    currency CHAR(3) NOT NULL DEFAULT 'CNY',
    source_type VARCHAR(24) NOT NULL,
    commission_bps_buy DECIMAL(12, 6) NOT NULL,
    commission_bps_sell DECIMAL(12, 6) NOT NULL,
    commission_min_cny DECIMAL(18, 6) NOT NULL,
    transfer_fee_bps_buy DECIMAL(12, 6) NOT NULL DEFAULT 0,
    transfer_fee_bps_sell DECIMAL(12, 6) NOT NULL DEFAULT 0,
    stamp_duty_bps_sell DECIMAL(12, 6) NOT NULL DEFAULT 0,
    slippage_bps_buy DECIMAL(12, 6) NOT NULL DEFAULT 0,
    slippage_bps_sell DECIMAL(12, 6) NOT NULL DEFAULT 0,
    source_ref VARCHAR(512) NOT NULL,
    metadata_json JSON NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (profile_id),
    UNIQUE KEY uq_cn_cost_key_from (market_code, profile_key, valid_from),
    KEY ix_cn_cost_asof (market_code, profile_key, valid_from, valid_to),
    CONSTRAINT fk_cn_cost_market FOREIGN KEY (market_code) REFERENCES markets(market_code),
    CONSTRAINT ck_cn_cost_market CHECK (market_code = 'CN_A'),
    CONSTRAINT ck_cn_cost_dates CHECK (valid_to IS NULL OR valid_to >= valid_from),
    CONSTRAINT ck_cn_cost_source CHECK (source_type IN ('RESEARCH_PROXY','VERIFIED_BROKER')),
    CONSTRAINT ck_cn_cost_nonnegative CHECK (
        commission_bps_buy >= 0 AND commission_bps_sell >= 0 AND commission_min_cny >= 0
        AND transfer_fee_bps_buy >= 0 AND transfer_fee_bps_sell >= 0
        AND stamp_duty_bps_sell >= 0
        AND slippage_bps_buy >= 0 AND slippage_bps_sell >= 0
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Les règles de lot/T+1 sont historiques et bornées. Les pourcentages de
-- limites sont volontairement NULL : IPO/ST/exceptions exigent les lignes
-- instrument/séance de cn_daily_price_limits et un état de qualité vérifié.
-- metadata_json.minimum_buy_shares est requis pour STAR (minimum 200,
-- incrément de 1). La vente peut solder une quantité résiduelle.
INSERT INTO market_execution_rules
    (market_code,exchange_mic,board_code,valid_from,valid_to,currency,
     settlement_cycle_days,buy_lot_size,sell_lot_size,tick_size,
     daily_price_limit_pct,short_selling_allowed,same_day_sell_allowed,metadata_json)
VALUES
    ('CN_A','XSHG','SH_MAIN','2018-01-01','2025-12-31','CNY',1,100,1,0.01,NULL,FALSE,FALSE,
     JSON_OBJECT('minimum_buy_shares',100,'minimum_sell_shares',100,'research_only',TRUE,'rule_version','cn_a_2018_2025_v1')),
    ('CN_A','XSHE','SZ_MAIN','2018-01-01','2025-12-31','CNY',1,100,1,0.01,NULL,FALSE,FALSE,
     JSON_OBJECT('minimum_buy_shares',100,'minimum_sell_shares',100,'research_only',TRUE,'rule_version','cn_a_2018_2025_v1')),
    ('CN_A','XSHE','CHINEXT','2018-01-01','2025-12-31','CNY',1,100,1,0.01,NULL,FALSE,FALSE,
     JSON_OBJECT('minimum_buy_shares',100,'minimum_sell_shares',100,'research_only',TRUE,'rule_version','cn_a_2018_2025_v1')),
    ('CN_A','XSHG','STAR','2019-07-22','2025-12-31','CNY',1,1,1,0.01,NULL,FALSE,FALSE,
     JSON_OBJECT('minimum_buy_shares',200,'minimum_sell_shares',200,'research_only',TRUE,'rule_version','cn_a_2018_2025_v1'))
ON DUPLICATE KEY UPDATE rule_id = rule_id;

-- Ces profils reproduisent uniquement les stress H11-B ; ils ne sont pas
-- des commissions constatées ni un barème de taxes. Le resolver bloque
-- RESEARCH_PROXY sans autorisation explicite du scénario de recherche.
INSERT INTO cn_execution_cost_profiles
    (market_code,profile_key,valid_from,valid_to,currency,source_type,
     commission_bps_buy,commission_bps_sell,commission_min_cny,
     transfer_fee_bps_buy,transfer_fee_bps_sell,stamp_duty_bps_sell,
     slippage_bps_buy,slippage_bps_sell,source_ref,metadata_json)
VALUES
    ('CN_A','cn_a_research','2018-01-01','2025-12-31','CNY','RESEARCH_PROXY',
     10,10,5,0,0,0,0,0,'Sprint 11-B : hypothèse 10 bps/côté et minimum 5 CNY',
     JSON_OBJECT('not_official_fee_schedule',TRUE,'version','cn_a_research_v1')),
    ('CN_A','cn_a_research_stress','2018-01-01','2025-12-31','CNY','RESEARCH_PROXY',
     25,25,5,0,0,0,0,0,'Sprint 11-B : hypothèse 25 bps/côté et minimum 5 CNY',
     JSON_OBJECT('not_official_fee_schedule',TRUE,'version','cn_a_research_stress_v1'))
ON DUPLICATE KEY UPDATE profile_id = profile_id;
