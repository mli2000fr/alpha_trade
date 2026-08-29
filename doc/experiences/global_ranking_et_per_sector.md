# Expériences Global Ranking et per-sector — synthèse

Retour : [dossier technique Global Ranking](../ml/global_ranking/README.md)

Références courantes : [per-symbol](../ml/per_symbol/README.md) ·
[per-sector](../ml/per_sector/README.md)

## Sources regroupées

Les archives comprennent la série B0–B44 sous `doc/ml/global_per_sector/test/`, `per_sector.md`, `per_sector_todo.md`, les checks de performance Global, les synthèses per-symbol/whitelist et les anciens documents ML.

## Axes testés

- ajouts sentiment, screener et scores short ;
- SPY, volatilités macro et CAPM ;
- fondamentaux, secteurs et historique de scores ;
- stacking ;
- targets T1/T2/T3 ;
- profondeur historique et nombre de splits ;
- objectifs YetiRank, QueryRMSE, QuerySoftMax et XGBoost rank ;
- tailles d’univers ;
- volume features ;
- global-only, per-sector et per-symbol.

## Enseignements durables

Le ranking cross-sectionnel global doit être évalué par date avec IC, spreads et top-N, pas seulement par classification. Les ajouts de features ne sont utiles que s’ils varient dans la coupe et restent stables OOS.

Les modèles per-sector/per-symbol souffrent d’échantillons plus petits, d’hétérogénéité et de multiple testing. Un champion apparent sur validation peut disparaître en walk-forward. Le mapping secteurs, l’univers et la profondeur historique changent le problème autant que l’algorithme.

Le code courant conserve un Global Ranking multi-horizons et des capacités de features/neutralisation. La présence d’anciens chemins per-sector ne signifie pas que leurs batches sont promus.

## Règles pour une nouvelle campagne

Geler univers PIT, folds, horizons, target, baseline et budget d’essais. Publier IC par date, déciles, couverture, turnover et coûts. Réserver un holdout et comparer le batch candidat en production parity avant promotion.
