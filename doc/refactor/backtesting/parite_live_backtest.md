# Parité live/backtest

Retour : [références Backtesting](README.md)

`parity.py` compare décisions live et replay indexées par symbole. Il normalise action/quantité, applique tolérance relative 5 % et absolue 1 action par défaut, puis classe missing/action/quantity mismatches. Le seuil global de divergence par défaut est 10 %.

`compare_risk_layers` descend dans les couches : éligibilité, côté, taille, contraintes et raisons. `summarize_paper_coverage` mesure la couverture réelle. `run_daily_parity` écrit les artefacts et peut construire une alerte.

Une bonne parité exige mêmes données as-of, univers, batch, config, equity, positions initiales, régime, calendrier, arrondi et lifecycle. Les tolérances n'autorisent pas un contrat différent.

Workflow : figer ids live ; reconstruire avec hashes ; comparer première couche ; expliquer chaque mismatch ; corriger code/data ; rejouer un golden. Ne pas ajuster les tolérances pour faire disparaître l'alerte.

