-- stock_scores_history : archivage quotidien du snapshot stock_scores.
-- Table séparée pour accumuler l'historique sans risque sur stock_scores (PK = symbol).
-- Chaque run du screener/scanner/aggregator produit un snapshot archivé par
-- (snapshot_date, capital_preset_key, symbol) afin de versionner les univers
-- PIT par preset capital/backtest.
-- Utilisations futures :
--   - features temporelles pour le module LSTM (trend_score_history, final_score_history)
--   - backtest walk-forward (quels symboles étaient candidats à quelle date)
--   - audit et monitoring de la dérive des scores


CREATE TABLE IF NOT EXISTS alpha_trade.stock_scores_history (
    id                      BIGINT AUTO_INCREMENT PRIMARY KEY,
    snapshot_date           DATE           NOT NULL COMMENT 'Date du snapshot (as_of_date ou CURDATE)',
    capital_preset_key      VARCHAR(64)    NOT NULL DEFAULT 'capital_50001_100000' COMMENT 'Preset capital utilisé pour produire le snapshot PIT',
    config_fingerprint      VARCHAR(32)    DEFAULT NULL COMMENT 'Empreinte stable de la configuration preset appliquée',
    symbol                  VARCHAR(20)    NOT NULL,
    sector                  VARCHAR(50)    DEFAULT NULL,
    liquidity_val           DOUBLE         DEFAULT NULL,
    relative_strength_index DOUBLE         DEFAULT NULL,
    historical_range_score  DOUBLE         DEFAULT NULL,
    total_score             DOUBLE         DEFAULT NULL,
    trend_score             DOUBLE         DEFAULT NULL,
    vcp_score               DOUBLE         DEFAULT NULL,
    final_score             DOUBLE         DEFAULT NULL,
    market_cap              DOUBLE         DEFAULT NULL,
    beta_126                DOUBLE         DEFAULT NULL,
    spread_bps              DOUBLE         DEFAULT NULL,
    earnings_date           DATE           DEFAULT NULL,
    days_to_earnings        INT            DEFAULT NULL,
    earnings_blackout       TINYINT(1)     DEFAULT 0,
    is_candidate            TINYINT(1)     DEFAULT 0,
    sentiment_net_agg       DOUBLE         DEFAULT NULL,
    sector_impact_agg       DOUBLE         DEFAULT NULL,
    company_idio_score      DOUBLE         DEFAULT NULL,
    macro_regime_score      DOUBLE         DEFAULT NULL,
    company_idio_signal_norm DOUBLE        DEFAULT NULL,
    macro_regime_signal_norm DOUBLE        DEFAULT NULL,
    company_idio_component  DOUBLE         DEFAULT NULL,
    macro_regime_component  DOUBLE         DEFAULT NULL,
    quant_component         DOUBLE         DEFAULT NULL,
    final_score_sentiment   DOUBLE         DEFAULT NULL,
    final_score_walk_forward DOUBLE        DEFAULT NULL,
    walk_forward_sentiment_weight DOUBLE   DEFAULT NULL,
    walk_forward_macro_weight DOUBLE       DEFAULT NULL,
    walk_forward_quant_weight DOUBLE       DEFAULT NULL,
    calibration_run_id      VARCHAR(64)    DEFAULT NULL,
    calibration_source      VARCHAR(64)    DEFAULT NULL,
    signal_active           TINYINT(1)     DEFAULT 0,
    anomaly_count           INT            DEFAULT 0,
    missing_days_count      INT            DEFAULT 0,
    sanitizer_status        VARCHAR(16)    NOT NULL DEFAULT 'pending',
    created_at              TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_snapshot_preset_symbol (snapshot_date, capital_preset_key, symbol),
    INDEX idx_history_symbol     (symbol, snapshot_date),
    INDEX idx_history_candidate  (snapshot_date, is_candidate),
    INDEX idx_history_preset_candidate (capital_preset_key, snapshot_date, is_candidate)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Archivage quotidien des snapshots stock_scores';