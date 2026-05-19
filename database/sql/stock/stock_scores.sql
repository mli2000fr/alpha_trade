CREATE TABLE IF NOT EXISTS alpha_trade.stock_scores (

    symbol                  VARCHAR(20)    NOT NULL,

    -- stock_screener.py (mensuel)
    liquidity_val           DOUBLE         NOT NULL,
    relative_strength_index DOUBLE         NOT NULL,
    historical_range_score  DOUBLE         NOT NULL,
    total_score             DOUBLE         NOT NULL,
    last_updated_score      DATETIME       NOT NULL,

    -- alpha_scanner.py (quotidien/hebdo)
    trend_score             DOUBLE         DEFAULT NULL,
    vcp_score               DOUBLE         DEFAULT NULL,
    market_cap              DOUBLE         DEFAULT NULL,
    beta_126                DOUBLE         DEFAULT NULL,
    spread_bps              DOUBLE         DEFAULT NULL,
    earnings_date           DATE           DEFAULT NULL,
    days_to_earnings        INT            DEFAULT NULL,
    earnings_blackout       TINYINT(1)     DEFAULT 0,
    candidate_rank          INT            DEFAULT NULL,
    raw_final_score         DOUBLE         DEFAULT NULL,
    normalized_total_score  DOUBLE         DEFAULT NULL,
    normalized_rsi          DOUBLE         DEFAULT NULL,
    total_score_neutralized DOUBLE         DEFAULT NULL,
    relative_strength_index_neutralized DOUBLE DEFAULT NULL,
    trend_vcp_component     DOUBLE         DEFAULT NULL,
    total_score_component   DOUBLE         DEFAULT NULL,
    rsi_component           DOUBLE         DEFAULT NULL,
    atr_pct_20              DOUBLE         DEFAULT NULL,
    weekly_trend_score      DOUBLE         DEFAULT NULL,
    high_52w_proximity      DOUBLE         DEFAULT NULL,
    volatility_ratio        DOUBLE         DEFAULT NULL,
    selector_signal_mode    VARCHAR(32)    DEFAULT NULL,
    selection_explanation   VARCHAR(255)   DEFAULT NULL,
    final_score             DOUBLE         DEFAULT NULL,
    is_candidate            TINYINT(1)     DEFAULT 0,
    last_updated_scan       DATETIME       DEFAULT NULL,

    -- métadonnées
    sector                  VARCHAR(50)    DEFAULT NULL,

    -- data_sanitizer_daily.py
    anomaly_count           INT            DEFAULT 0,
    missing_days_count      INT            DEFAULT 0,
    sanitizer_status        VARCHAR(16)    NOT NULL DEFAULT 'pending',
    last_updated_audit      DATETIME       DEFAULT NULL,

    -- signal_aggregator.py (après sentiment_pipeline.py)
    sentiment_net_agg       DOUBLE         DEFAULT NULL,
    sector_impact_agg       DOUBLE         DEFAULT NULL,
    company_idio_score      DOUBLE         DEFAULT NULL,
    macro_regime_score      DOUBLE         DEFAULT NULL,
    sentiment_signal_norm   DOUBLE         DEFAULT NULL,
    macro_signal_norm       DOUBLE         DEFAULT NULL,
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
    major_event_flag_agg    TINYINT(1)     DEFAULT 0,
    macro_event_flag_agg    TINYINT(1)     DEFAULT 0,
    total_news              INT            DEFAULT 0,
    last_updated_sentiment  DATETIME       DEFAULT NULL,

    PRIMARY KEY (symbol),
    INDEX idx_total_score           (total_score),
    INDEX idx_final_score           (final_score),
    INDEX idx_final_score_sentiment (final_score_sentiment),
    INDEX idx_final_score_walk_forward (final_score_walk_forward),
    INDEX idx_scan_candidate        (is_candidate, total_score)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
