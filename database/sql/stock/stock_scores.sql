
CREATE TABLE alpha_trade.stock_scores (

    -- -------------------------------------------------------------------------
    -- Clé primaire
    -- -------------------------------------------------------------------------
    symbol                  VARCHAR(20)    NOT NULL,

    -- -------------------------------------------------------------------------
    -- Scores quantitatifs de base — écrits par stock_screener.py (mensuel)
    -- -------------------------------------------------------------------------
    liquidity_val           DOUBLE         NOT NULL        COMMENT 'Dollar volume moyen 30j (filtre liquidité)',
    relative_strength_index DOUBLE         NOT NULL        COMMENT 'Force relative 6 mois vs benchmark (SPY)',
    historical_range_score  DOUBLE         NOT NULL        COMMENT 'Position du close dans le range 10 ans (0-100)',
    total_score             DOUBLE         NOT NULL        COMMENT 'Score composite pondéré (screener)',
    last_updated_score      DATETIME       NOT NULL        COMMENT 'Horodatage calcul scores screener',

    -- -------------------------------------------------------------------------
    -- Scores AlphaScanner — écrits par alpha_scanner.py (quotidien/hebdo)
    -- -------------------------------------------------------------------------
    trend_score             DOUBLE         DEFAULT NULL    COMMENT 'Score template de tendance Minervini (0-1)',
    vcp_score               DOUBLE         DEFAULT NULL    COMMENT 'Score compression VCP (0-1)',
    final_score             DOUBLE         DEFAULT NULL    COMMENT 'Score final quantitatif AlphaScanner (quant only)',
    is_candidate            TINYINT(1)     DEFAULT 0       COMMENT '1 = retenu dans le Top N, 0 = non retenu',
    last_updated_scan       DATETIME       DEFAULT NULL    COMMENT 'Horodatage dernier scan AlphaScanner',

    -- -------------------------------------------------------------------------
    -- Métadonnées symbole
    -- -------------------------------------------------------------------------
    sector                  VARCHAR(50)    DEFAULT NULL    COMMENT 'Secteur (neutralisation sectorielle)',

    -- -------------------------------------------------------------------------
    -- Audit qualité données — écrits par data_sanitizer_daily.py
    -- -------------------------------------------------------------------------
    anomaly_count           INT            DEFAULT 0       COMMENT 'Nb anomalies MAD détectées',
    missing_days_count      INT            DEFAULT 0       COMMENT 'Nb jours Forward Fill appliqués',
    last_updated_audit      DATETIME       DEFAULT NULL    COMMENT 'Horodatage dernier audit qualité',

    -- -------------------------------------------------------------------------
    -- Scores sentiment — écrits par signal_aggregator.py (quotidien/hebdo)
    -- Exécuté APRÈS sentiment_pipeline.py (FinBERT)
    -- -------------------------------------------------------------------------
    sentiment_net_agg       DOUBLE         DEFAULT NULL    COMMENT 'Sentiment net pondéré sur fenêtre glissante',
    sector_impact_agg       DOUBLE         DEFAULT NULL    COMMENT 'Impact macro sectoriel moyen sur fenêtre glissante',
    sentiment_signal_norm   DOUBLE         DEFAULT NULL    COMMENT 'sentiment_net_agg normalisé min-max [0,1]',
    macro_signal_norm       DOUBLE         DEFAULT NULL    COMMENT 'sector_impact_agg normalisé min-max [0,1]',
    final_score_sentiment   DOUBLE         DEFAULT NULL    COMMENT 'Score final fusionné quant+FinBERT+macro (signal_aggregator)',
    signal_active           TINYINT(1)     DEFAULT 0       COMMENT '1 si min_news_count atteint sur la fenêtre',
    major_event_flag_agg    TINYINT(1)     DEFAULT 0       COMMENT '1 si major_event détecté sur la fenêtre ticker',
    macro_event_flag_agg    TINYINT(1)     DEFAULT 0       COMMENT '1 si macro_event détecté sur la fenêtre secteur',
    total_news              INT            DEFAULT 0       COMMENT 'Nb total d\'articles sur la fenêtre sentiment',
    last_updated_sentiment  DATETIME       DEFAULT NULL    COMMENT 'Horodatage dernière fusion sentiment',

    -- -------------------------------------------------------------------------
    -- Contraintes & index
    -- -------------------------------------------------------------------------
    PRIMARY KEY (symbol),
    INDEX idx_total_score           (total_score),
    INDEX idx_final_score           (final_score),
    INDEX idx_final_score_sentiment (final_score_sentiment),
    INDEX idx_scan_candidate        (is_candidate, total_score)  COMMENT 'Accélère la lecture Top N en inférence'

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;




------------------------------------
DROP TABLE IF EXISTS alpha_trade.stock_scores;

CREATE TABLE alpha_trade.stock_scores (

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
    final_score             DOUBLE         DEFAULT NULL,
    is_candidate            TINYINT(1)     DEFAULT 0,
    last_updated_scan       DATETIME       DEFAULT NULL,

    -- métadonnées
    sector                  VARCHAR(50)    DEFAULT NULL,

    -- data_sanitizer_daily.py
    anomaly_count           INT            DEFAULT 0,
    missing_days_count      INT            DEFAULT 0,
    last_updated_audit      DATETIME       DEFAULT NULL,

    -- signal_aggregator.py (après sentiment_pipeline.py)
    sentiment_net_agg       DOUBLE         DEFAULT NULL,
    sector_impact_agg       DOUBLE         DEFAULT NULL,
    sentiment_signal_norm   DOUBLE         DEFAULT NULL,
    macro_signal_norm       DOUBLE         DEFAULT NULL,
    final_score_sentiment   DOUBLE         DEFAULT NULL,
    signal_active           TINYINT(1)     DEFAULT 0,
    major_event_flag_agg    TINYINT(1)     DEFAULT 0,
    macro_event_flag_agg    TINYINT(1)     DEFAULT 0,
    total_news              INT            DEFAULT 0,
    last_updated_sentiment  DATETIME       DEFAULT NULL,

    PRIMARY KEY (symbol),
    INDEX idx_total_score           (total_score),
    INDEX idx_final_score           (final_score),
    INDEX idx_final_score_sentiment (final_score_sentiment),
    INDEX idx_scan_candidate        (is_candidate, total_score)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
