-- stock_scores_history : archivage quotidien du snapshot stock_scores.
-- Table séparée pour accumuler l'historique sans risque sur stock_scores (PK = symbol).
-- Chaque run du screener/scanner/aggregator produit un snapshot archivé par (snapshot_date, symbol).
-- Utilisations futures :
--   - features temporelles pour le module LSTM (trend_score_history, final_score_history)
--   - backtest walk-forward (quels symboles étaient candidats à quelle date)
--   - audit et monitoring de la dérive des scores

CREATE TABLE IF NOT EXISTS alpha_trade.stock_scores_history (
    id                      BIGINT AUTO_INCREMENT PRIMARY KEY,
    snapshot_date           DATE           NOT NULL COMMENT 'Date du snapshot (as_of_date ou CURDATE)',

    -- Identité
    symbol                  VARCHAR(20)    NOT NULL,
    sector                  VARCHAR(50)    DEFAULT NULL,

    -- Screener
    liquidity_val           DOUBLE         DEFAULT NULL,
    relative_strength_index DOUBLE         DEFAULT NULL,
    historical_range_score  DOUBLE         DEFAULT NULL,
    total_score             DOUBLE         DEFAULT NULL,

    -- AlphaScanner
    trend_score             DOUBLE         DEFAULT NULL,
    vcp_score               DOUBLE         DEFAULT NULL,
    final_score             DOUBLE         DEFAULT NULL,
    is_candidate            TINYINT(1)     DEFAULT 0,

    -- Sentiment (signal_aggregator)
    sentiment_net_agg       DOUBLE         DEFAULT NULL,
    sector_impact_agg       DOUBLE         DEFAULT NULL,
    final_score_sentiment   DOUBLE         DEFAULT NULL,
    signal_active           TINYINT(1)     DEFAULT 0,

    -- Audit qualité
    anomaly_count           INT            DEFAULT 0,
    missing_days_count      INT            DEFAULT 0,

    -- Timestamps
    created_at              TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Contraintes
    UNIQUE KEY uk_snapshot_symbol (snapshot_date, symbol),
    INDEX idx_history_symbol     (symbol, snapshot_date),
    INDEX idx_history_candidate  (snapshot_date, is_candidate)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Archivage quotidien des snapshots stock_scores';


------------------------------------

CREATE TABLE IF NOT EXISTS alpha_trade.stock_scores_history (
    id                      BIGINT AUTO_INCREMENT PRIMARY KEY,
    snapshot_date           DATE           NOT NULL COMMENT 'Date du snapshot (as_of_date ou CURDATE)',
    symbol                  VARCHAR(20)    NOT NULL,
    sector                  VARCHAR(50)    DEFAULT NULL,
    liquidity_val           DOUBLE         DEFAULT NULL,
    relative_strength_index DOUBLE         DEFAULT NULL,
    historical_range_score  DOUBLE         DEFAULT NULL,
    total_score             DOUBLE         DEFAULT NULL,
    trend_score             DOUBLE         DEFAULT NULL,
    vcp_score               DOUBLE         DEFAULT NULL,
    final_score             DOUBLE         DEFAULT NULL,
    is_candidate            TINYINT(1)     DEFAULT 0,
    sentiment_net_agg       DOUBLE         DEFAULT NULL,
    sector_impact_agg       DOUBLE         DEFAULT NULL,
    final_score_sentiment   DOUBLE         DEFAULT NULL,
    signal_active           TINYINT(1)     DEFAULT 0,
    anomaly_count           INT            DEFAULT 0,
    missing_days_count      INT            DEFAULT 0,
    created_at              TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_snapshot_symbol (snapshot_date, symbol),
    INDEX idx_history_symbol     (symbol, snapshot_date),
    INDEX idx_history_candidate  (snapshot_date, is_candidate)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Archivage quotidien des snapshots stock_scores';