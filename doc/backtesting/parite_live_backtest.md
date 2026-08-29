# Parité live/backtest

Retour : [références Backtesting](README.md)

`parity.py` compare décisions live et replay indexées par symbole. Il normalise action/quantité, applique tolérance relative 5 % et absolue 1 action par défaut, puis classe missing/action/quantity mismatches. Le seuil global de divergence par défaut est 10 %.

`compare_risk_layers` descend dans les couches : éligibilité, côté, taille, contraintes et raisons. `summarize_paper_coverage` mesure la couverture réelle. `run_daily_parity` écrit les artefacts et peut construire une alerte.

Une bonne parité exige mêmes données as-of, univers, batch, config, equity, positions initiales, régime, calendrier, arrondi et lifecycle. Les tolérances n'autorisent pas un contrat différent.

Workflow : figer ids live ; reconstruire avec hashes ; comparer première couche ; expliquer chaque mismatch ; corriger code/data ; rejouer un golden. Ne pas ajuster les tolérances pour faire disparaître l'alerte.

## Inputs à figer

Trade date, account/equity, positions/ordres initiaux, universe run, prediction/model run, config fingerprint, régime/state, prix/quotes et calendrier. Sans ces identifiants, un replay peut être plausible sans être le replay du live.

## Normalisation

Les symboles et actions sont normalisés. Les quantités sont comparées avec tolérance absolue/relative. Les côtés et raisons doivent rester séparés. Une missing row est différente d'une quantité zéro.

## Compare decisions

`compare_decisions` indexe les rows live/replay. Il produit `ParityRow` avec présence, actions, quantités, écarts et statut. Le rapport calcule total/comparables/divergences et taux.

## Compare risk layers

La comparaison descend dans score/côté, gates, sizing et contraintes. Elle doit identifier si l'écart vient d'une donnée, d'un paramètre ou d'un ordre d'application. Les reason codes sont plus utiles que la quantité finale seule.

## Couverture paper

`summarize_paper_coverage` vérifie combien de décisions/replays disposent de faits paper comparables. Un taux de divergence bas sur 5 % de couverture n'est pas une validation.

## Artefacts et alertes

`write_parity_artifacts` écrit résumé et détails dans `artifacts/parity_runs`. `run_daily_parity` compare et construit une alerte si le seuil 10 % est dépassé. L'alerte contient les principales divergences, pas de secrets.

## Tolérances

5 % relatif et 1 action absolue sont des defaults techniques. Pour fractional/petit capital, l'absolu peut dominer ; analyser l'impact notionnel. Modifier une tolérance est un changement de contrat d'audit.

## Golden tests

Les golden fixtures fixent un cas complet. Lors d'un changement intentionnel, expliquer la différence, mettre à jour code partagé puis golden. Ne pas régénérer aveuglément le résultat attendu.

## Causes fréquentes

Univers actuel au lieu de PIT, batch/horizon différent, equity live non reproduite, positions initiales absentes, arrondi fractional, régime reconstruit, quote/gap, lifecycle watcher et corporate actions.
