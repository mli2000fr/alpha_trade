# 2 — Features et targets sectorielles

## Features

Le modèle reprend les familles activées dans `DataConfig` : techniques,
benchmark, sentiment, screener/short, macro, fondamentaux, facteurs, composants
de score, volume, cross-sectionnel et stacking global. La colonne `symbol` est
optionnelle et réservée aux modèles tabulaires.

## Neutralisation sectorielle

Lorsque les options correspondantes sont actives, les targets d’horizon peuvent
être neutralisées dans le secteur. L’objectif est d’apprendre la différence
relative entre titres comparables plutôt qu’un mouvement commun sectoriel.

## T2 — rang intra-sector

`target_intra_sector_rank` convertit les targets en percentiles `[0,1]` dans le
groupe secteur/date. Ce contrat transforme une régression absolue en problème
relatif. Le percentile dépend de l’effectif observable à cette date.

## T3 — classification ternaire intra-sector

Lorsque le mode initial est `regression` et
`target_ternary_intra_sector=True`, les quantiles bas/haut sont calculés sur le
TRAIN uniquement avec `target_ternary_quantile`. Les labels deviennent :

```text
target < quantile bas  → SHORT (-1)
entre les quantiles    → FLAT (0)
target > quantile haut → LONG (+1)
```

Les seuils appris sur train sont appliqués à validation et test, y compris aux
targets multi-horizons. Le config local est remplacé par `target_mode=ternary`
pour les fonctions aval. Recalculer les quantiles sur chaque partition serait
une fuite et changerait la prévalence artificiellement.

## Modes généraux

Sans T2/T3, le secteur respecte `binary`, `ternary` ou `regression` et les
labels/horizons préparés par le pipeline de dataset partagé. Les losses ranking
CatBoost sont refusées en régression sectorielle et remplacées par RMSE.

