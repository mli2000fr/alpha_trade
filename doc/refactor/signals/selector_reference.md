# Selector / AlphaScanner — référence

Retour : [vue signaux](../13_screener_selector_sentiment.md)

`AlphaScanner` assemble données via `db_io`, calcule facteurs, applique filtres, scoring/ranking, régime et explicabilité. `alpha_scanner.py` porte le run CLI ; `config.py` valide les options.

`factors.py` calcule composants techniques Minervini/VCP, momentum et autres signaux. `filters.py` applique contraintes ; `strict_filter_profiles.py` reste une façade vers les profils communs. `ranking.py` combine/neutralise ; `regime_scoring.py` adapte les scores ; `explainability.py` produit contributions/reasons.

`short_score.py` calcule un contexte short et peut injecter le `predicted_side` reçu du ML. Il ne décide pas ce côté. `dip_filter.py` applique un filtre de persistance/dip long selon profils prod/backtest ; son activation dans la synthèse ML doit être cohérente avec le replay.

Les écritures enrichissent `stock_scores` et artefacts/run summary. Conserver valeurs brutes, normalisées, rang et raisons pour expliquer un veto. Un score sector-neutral dépend de la population/date et du mapping secteur.

Tests : profil strict, side ML, absence secteur, petite coupe, régime, dip prod/backtest et reproductibilité du ranking.

