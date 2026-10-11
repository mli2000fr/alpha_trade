# 3 — Entraînement, walk-forward et champion sectoriel

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

## Modèles

LightGBM choisit régresseur ou classifieur binaire/multiclasse. CatBoost choisit
Regressor ou Classifier avec support catégoriel du symbole. Les poids de classes
sont équilibrés en classification. Chaque horizon écrit ses résultats sous
`h{N}/lightgbm` et `h{N}/catboost`.

L’horizon primaire est `forecast_horizon`; s’il manque, le premier horizon
effectivement produit devient fallback. Les résultats primaires conservent aussi
le dictionnaire complet `horizons`.

## Walk-forward

`run_tabular_walk_forward` est appelé avec `by_dates=True` pour les deux
backends. Il utilise les mêmes paramètres temporels généraux. Les métriques
complètes et moyennes sont rattachées au résultat de l’horizon.

## Sélection champion

Lorsque les deux challengers ont au moins trois splits F1 exploitables, le code
calcule pour chacun F1 moyen, écart-type, F1 IR et proportion de F1 positifs.
Gates : F1 moyen > 0, IR ≥ 0,30 et au plus deux splits non positifs.

Si les deux sont éligibles :

```text
score = 55 % F1 normalisé + 30 % IR normalisé + 15 % splits positifs
```

Un seul éligible gagne. Si aucun n’est éligible, si les données WF sont
insuffisantes ou absentes, le code choisit le meilleur `selection_score`. En cas
d’égalité composite, LightGBM gagne par l’opérateur `>=`.

## Persistance

`_persist_sector_metrics` écrit métriques complètes, challengers, champion,
route d’inférence, configuration et manifeste de signatures. Le `run_id` est
construit depuis batch et slug secteur lorsque le batch existe. Une erreur DB est
journalisée sans nécessairement supprimer les artefacts disque.

