# 7 — Métriques, diagnostics et historique

## IC de rang

`compute_ic_rank` calcule la corrélation de Spearman entre scores prédits et
target réelle. Il retourne `None` avec moins de dix observations ou si une série
est quasi constante. L’IC est adapté au classement ; F1 n’est pas la métrique
primaire de ce modèle.

Pour un horizon :

- `ic_mean` moyenne les IC des folds ;
- `ic_std` mesure leur dispersion ;
- `ic_ir = mean/std` lorsque l’écart-type est positif ;
- `positive_pct` est la proportion de splits à IC positif ;
- `worst_split_ic` intervient dans le tie-break des horizons.

Les commentaires du code citent 0,05 comme bon ordre de grandeur et 0,10 comme
excellent. Ce sont des repères, pas des gates universels. L’effectif, les coûts
et la stabilité doivent accompagner l’IC.

## IC cross-sectionnel comparable

`compute_cross_sectional_ic` calcule l’IC par date et peut vol-scaler la target.
Il permet de comparer un modèle per-symbol au Global Ranking avec la même
méthode. Par défaut, une date exige au moins dix symboles.

## Spread de déciles

Les scores sont découpés par date en dix quantiles via `qcut`; le diagnostic
calcule rendement moyen de chaque décile et spread top moins bottom. Une bonne
monétisation attend une progression raisonnablement monotone, pas seulement un
spread positif dû à un décile extrême.

Le `actual_return` de ce diagnostic est la target transformée du chemin
d’entraînement. Il ne doit pas être confondu sans vérification avec un rendement
brut en pourcentage.

## Matrice de diagnostic

| Diagnostic | Question |
|---|---|
| IC par fold | signal stable dans le temps ? |
| IC/IR/% positifs | qualité et robustesse ? |
| déciles | ordre économiquement monotone ? |
| feature importance | dépendance excessive à quelques colonnes ? |
| couverture symbole/date | biais de sous-univers ? |
| champion par horizon | backend stable ou variable ? |
| score/tie-break horizon | gagnant clair ou quasi ex æquo ? |
| distribution des rangs | rangs neutres/constantes anormaux ? |
| performance aval | signal survivant aux coûts, filtres et risque ? |

## IHM Diagnostic ML

La page affiche métriques du modèle global, détails par horizon et
`global_rank_history`. Elle peut proposer des variantes exploratoires ou générer
une commande de backtest. Elles ne remplacent pas la validation complète avec
contrat d’exécution et baseline gelée.

## Interpréter l’historique

Toujours filtrer par `batch_id`. Deux batches peuvent contenir la même date avec
univers, features, modèles et rangs différents. Une valeur `0.5` peut être un
vrai rang médian ou un fallback : couverture et manifeste sont nécessaires pour
les distinguer.

## Historique expérimental

Les campagnes B0–B44 ont comparé features, backends/objectifs, univers et
variantes. Elles sont synthétisées dans
[Expériences Global Ranking et per-sector](../../experiences/global_ranking_et_per_sector.md).
Ce dossier décrit le contrat observable dans le code courant.

## Gate scientifique

Exiger données PIT, IC positif et stable, déciles cohérents, couverture
acceptable, stabilité multi-périodes, backtest réaliste et parité du consommateur.
Une amélioration du seul IC moyen ne suffit pas si turnover, coûts ou
concentration annulent sa valeur.

