DROP TABLE IF EXISTS stock_scores;

CREATE TABLE alpha_trade.stock_scores (
    symbol VARCHAR(20) NOT NULL,
    liquidity_val DOUBLE NOT NULL,
    relative_strength_index DOUBLE NOT NULL,
    historical_range_score DOUBLE NOT NULL,
    total_score DOUBLE NOT NULL,
    last_updated DATETIME NOT NULL,
    PRIMARY KEY (symbol),
    INDEX idx_total_score (total_score)
) ENGINE=InnoDB;

----------------------------
symbol:
Le code du titre boursier (ex: AAPL, MSFT). C’est la clé primaire, donc chaque ligne correspond à un titre unique.
liquidity_val:
Indicateur de liquidité du titre, généralement basé sur le volume d’échanges ou la facilité à acheter/vendre sans impacter le prix. Plus la valeur est élevée, plus le titre est liquide.
relative_strength_index:
RSI (Relative Strength Index), un indicateur technique qui mesure la vitesse et le changement des mouvements de prix. Il varie généralement entre 0 et 100. Un RSI élevé (>70) indique un titre suracheté, un RSI bas (<30) indique un titre survendu.
historical_range_score:
Score basé sur la position actuelle du prix dans sa fourchette historique (par exemple, sur 52 semaines). Cela permet de savoir si le prix est proche de ses plus hauts ou plus bas historiques.
total_score:
Score global agrégé, calculé à partir des autres indicateurs (liquidité, RSI, range, etc.). Il sert à classer ou filtrer les titres selon une stratégie.
last_updated:
Date et heure de la dernière mise à jour de ce score pour le titre.
PRIMARY KEY (symbol):
Garantit qu’il n’y a qu’une seule ligne par titre.
INDEX idx_total_score (total_score):
Index pour accélérer les requêtes qui trient ou filtrent sur le score global.