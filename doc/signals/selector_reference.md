# Selector / AlphaScanner — référence

Retour : [vue signaux](../13_screener_selector_sentiment.md)

`AlphaScanner` assemble données via `db_io`, calcule facteurs, applique filtres, scoring/ranking, régime et explicabilité. `alpha_scanner.py` porte le run CLI ; `config.py` valide les options.

`factors.py` calcule composants techniques Minervini/VCP, momentum et autres signaux. `filters.py` applique contraintes ; `strict_filter_profiles.py` reste une façade vers les profils communs. `ranking.py` combine/neutralise ; `regime_scoring.py` adapte les scores ; `explainability.py` produit contributions/reasons.

`short_score.py` calcule un contexte short et peut injecter le `predicted_side` reçu du ML. Il ne décide pas ce côté. `dip_filter.py` applique un filtre de persistance/dip long selon profils prod/backtest ; son activation dans la synthèse ML doit être cohérente avec le replay.

Les écritures enrichissent `stock_scores` et artefacts/run summary. Conserver valeurs brutes, normalisées, rang et raisons pour expliquer un veto. Un score sector-neutral dépend de la population/date et du mapping secteur.

Tests : profil strict, side ML, absence secteur, petite coupe, régime, dip prod/backtest et reproductibilité du ranking.

## Entrées

L'AlphaScanner charge scores screener, barres daily, metadata/secteur, quotes/audits et prédictions/contextes disponibles. Le scope nominal reste l'univers publié ; une liste explicite est un override de run.

## Facteurs

`factors.py` calcule les composantes techniques à partir de fenêtres passées. Les règles Minervini/VCP utilisent moyennes, highs/lows, contraction/volume selon implémentation. Chaque facteur doit conserver valeur brute avant normalisation.

## Filtres

`filters.py` applique critères stricts et raisons. Les profils communs évitent la divergence selector/backtest. Un filtre peut être dur ou diagnostic selon config ; documenter ce statut dans le summary.

## Ranking

`ranking.py` normalise/combine et classe. Les percentiles sont intra-snapshot. Les égalités doivent produire un ordre déterministe avec tiebreaker stable. Un top N est appliqué après les gates prévus, pas avant les calculs sectoriels.

## Régime

`regime_filters.py` et `regime_scoring.py` adaptent admissibilité/score au snapshot marché. Ils ne recalculent pas un régime indépendant. Conserver mode et raisons appliquées par candidat.

## Short score

`resolve_short_trigger` et `resolve_regime_adaptive_short_params` déterminent paramètres de contexte. `compute_short_score` enrichit ; `tag_short_candidates` étiquette. `inject_predicted_side` importe le côté ML : le score short seul ne crée pas un short.

## Dip filter

Le filtre persistent DIP possède contextes prod/backtest distincts et batch strict. En mode Oracle, il utilise percentile quotidien. Un échec de chargement peut être fail-open dans le predictor avec warning ; surveiller explicitement ce comportement.

## Explainability

L'explication doit présenter facteurs, contributions, gates et reasons, sans prétendre être une causalité. Les valeurs doivent correspondre au même run/date que le score affiché.

## Persistance et artifacts

Le latest score est mutable ; les historiques/artifacts rendent le run PIT. `run_summary.py` du selector agrège breakdown des filtres, populations et paramètres. L'IHM charge aussi l'historique d'artefacts.

## Maintenance

Ajouter un facteur exige calcul pur, colonnes DB/artefact si nécessaire, normalisation, poids/config, explainability, tests PIT et mise à jour des feature contracts ML s'il est consommé.
