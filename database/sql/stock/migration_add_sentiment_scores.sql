-- =============================================================================
-- OBSOLÈTE — colonnes intégrées directement dans stock_scores.sql
-- Ce fichier n'est conservé qu'à titre d'historique.
-- Pour une installation fraîche, utiliser uniquement stock_scores.sql.
-- =============================================================================

ALTER TABLE alpha_trade.stock_scores
    -- Score de sentiment ticker agrégé sur la fenêtre glissante (pondéré par nb d'articles)
    ADD COLUMN sentiment_net_agg       DOUBLE     DEFAULT NULL COMMENT 'Sentiment net pondéré (fenêtre glissante)',
    -- Score d'impact macro sectoriel agrégé
    ADD COLUMN sector_impact_agg       DOUBLE     DEFAULT NULL COMMENT 'Impact macro sectoriel moyen (fenêtre glissante)',
    -- Signaux normalisés [0,1] utilisés dans la formule de fusion
    ADD COLUMN sentiment_signal_norm   DOUBLE     DEFAULT NULL COMMENT 'sentiment_net_agg normalisé min-max [0,1]',
    ADD COLUMN macro_signal_norm       DOUBLE     DEFAULT NULL COMMENT 'sector_impact_agg normalisé min-max [0,1]',
    -- Score final fusionné (quant + sentiment) — distinct de final_score qui reste purement quantitatif
    -- final_score          = score AlphaScanner (trend + VCP)          → écrit par alpha_scanner.py
    -- final_score_sentiment = score fusionné (quant + FinBERT + macro)  → écrit par signal_aggregator.py
    ADD COLUMN final_score_sentiment   DOUBLE     DEFAULT NULL COMMENT 'Score final fusionné quant+sentiment (signal_aggregator)',
    -- Indicateurs d'activité du signal
    ADD COLUMN signal_active           TINYINT(1) DEFAULT 0   COMMENT '1 si min_news_count atteint sur la fenêtre',
    ADD COLUMN major_event_flag_agg    TINYINT(1) DEFAULT 0   COMMENT '1 si un major_event_flag détecté sur la fenêtre ticker',
    ADD COLUMN macro_event_flag_agg    TINYINT(1) DEFAULT 0   COMMENT '1 si un macro_event_flag détecté sur la fenêtre secteur',
    -- Nombre total d'articles sur la fenêtre glissante
    ADD COLUMN total_news              INT        DEFAULT 0   COMMENT 'Nombre total d\'articles sur la fenêtre sentiment',
    -- Horodatage de la dernière fusion sentiment
    ADD COLUMN last_updated_sentiment  DATETIME   DEFAULT NULL COMMENT 'Horodatage de la dernière fusion sentiment';

-- Index pour trier/filtrer sur le score fusionné
ALTER TABLE alpha_trade.stock_scores
    ADD INDEX idx_final_score_sentiment (final_score_sentiment);

