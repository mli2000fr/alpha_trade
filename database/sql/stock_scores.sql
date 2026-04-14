CREATE TABLE IF NOT EXISTS stock_scores (
    symbol VARCHAR(20) NOT NULL,

    -- Passage 1 : Liquidité (ex: Volume moyen * Prix moyen)
    liquidity_val DOUBLE DEFAULT 0,

    -- Passage 2 : Force Relative (Performance vs SPY)
    relative_strength_index DOUBLE DEFAULT 0,

    -- Passage 3 : Position dans le range 10 ans (0 à 100)
    historical_range_score DOUBLE DEFAULT 0,

    -- Score final agrégé pour le tri
    total_score DOUBLE AS (liquidity_val * 0.2 + relative_strength_index * 0.4 + historical_range_score * 0.4) STORED,

    -- Métadonnées
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (symbol),
    -- Index crucial pour récupérer les meilleurs scores immédiatement
    INDEX idx_total_score (total_score DESC)
) ENGINE=InnoDB;



-------------------------------
Quelques précisions sur ce script :
total_score (Colonne générée) : J'ai utilisé une colonne calculée (AS ... STORED). Cela permet à MySQL de calculer automatiquement le score final basé sur les trois passages. Tu peux ajuster les coefficients (0.2, 0.4, etc.) selon l'importance que tu accordes à chaque critère.

INDEX idx_total_score : C'est l'élément le plus important. Sans cet index, si tu fais un ORDER BY total_score DESC, MySQL devra trier toute la table à chaque fois. Avec l'index, c'est pré-trié.

PRIMARY KEY (symbol) : Garantit qu'un stock n'apparaît qu'une seule fois. Si tu relances ton script Python, il mettra à jour la ligne existante au lieu d'en créer une nouvelle.