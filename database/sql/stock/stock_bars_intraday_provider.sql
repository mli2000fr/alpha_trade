-- Mise à jour pour une table déjà créée avant l'ajout du fournisseur.
-- Exécuter une seule fois, seulement si la colonne provider est absente.
ALTER TABLE alpha_trade.stock_bars_intraday
    ADD COLUMN provider VARCHAR(16) NOT NULL DEFAULT 'eodhd'
    COMMENT 'alpaca or eodhd; data_source also distinguishes IEX/SIP' AFTER data_source;
