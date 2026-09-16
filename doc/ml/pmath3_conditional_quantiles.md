# P‑MATH‑3 — distribution conditionnelle du rendement H20

## Objectif

P‑MATH‑0, 1 et 2 n'ont pas trouvé de séparation D1/D10 stable avec les
variables d'état, les relations leader–suiveur ou la forme du chemin. P‑MATH‑3
change la cible statistique : au lieu d'apprendre directement une classe,
estimer plusieurs quantiles du rendement H20 dans le pool Oracle TOP20.

La question est double et les verdicts sont séparés :

1. Peut-on mieux prédire la **distribution** H20 qu'avec les quantiles constants
   calculés sur le train ?
2. Cette distribution apporte-t-elle une **direction** D1/D10 exploitable, au
   delà du classifieur Logistic direct sur les mêmes variables ?

Une amélioration du pinball sans séparation D1/D10 n'autorise aucune
intégration directionnelle. Elle pourrait seulement intéresser une recherche
ultérieure sur le risque ou l'amplitude.

## Population, PIT et folds

- batch Oracle `model-factory-20260909051302-323684`, horizon H20 ;
- événements du gate Oracle OOF TOP20 ;
- même panel de 84 variables d'état que P‑MATH‑0 ;
- labels `future_return` brut H20 et déciles Oracle D1/D10 ;
- calendrier 504/126/126, pas 126, au plus 12 folds récents ;
- `oracle_available_date < val_start` pour tout entraînement ;
- aucune transformation, quantile constant ou sous-sélection appris sur le test.

Le modèle de quantile est entraîné sur **tout le pool Oracle du train**, pas
seulement sur D1/D10. Le classifieur de référence est entraîné uniquement sur
les extrêmes D1/D10 disponibles dans le train. Les deux sont évalués sur le
même test OOS.

## Modèles et scores gelés

Sept LightGBM de régression quantile, aux niveaux 5, 10, 25, 50, 75, 90 et
95 %. Hyperparamètres fixes dans
`config/research/pmath3_conditional_quantiles.json` ; au plus 100 000 lignes
de train par fold, tirées de façon reproductible. Les quantiles prédits sont
réordonnés si les sept modèles se croisent ; le taux de croisement brut est
conservé dans les diagnostics.

Le `subsample` fixé en configuration est activé à chaque itération
(`subsample_freq=1`) ; cette précision technique a été verrouillée après le
smoke et avant le run complet. Elle ne change ni les seuils, ni les quantiles,
ni la population testée.

Le score directionnel primaire, fixé avant le run, est :

```text
S = (q10 + q90) / 2
```

Il mesure le centre des deux queues prédites : S élevé privilégie D10, S bas
privilégie D1. La médiane `q50` et l'asymétrie
`q90 + q10 − 2×q50` sont **diagnostiques secondaires**. On ne choisit pas
après coup celui qui gagne. Ces scores ne sont pas calibrés sur les labels
D1/D10. Le témoin directionnel est une Logistic L2 entraînée directement sur
D1/D10 avec les mêmes 84 features PIT.

## Évaluation et gates pré-enregistrées

Qualité distributionnelle : pinball moyen des sept quantiles, comparé aux
sept quantiles constants du train, et fréquence réalisée sous q10/q90. Un GO
distributionnel exige simultanément :

- amélioration médiane pinball d'au moins 2 % ;
- pinball meilleur dans au moins 67 % des folds ;
- erreur absolue moyenne de couverture q10/q90 au plus 3 points.

Qualité directionnelle : AUC D1/D10 du score primaire, AUC de la Logistic,
et rendement brut H20 des 10 % les mieux classés **chaque jour dans tout le
pool Oracle**, pas dans les seuls vrais extrêmes. Un GO directionnel exige
également :

- AUC médiane du score primaire ≥ 0,53 ;
- delta AUC médian contre Logistic ≥ +0,01 ;
- delta AUC positif dans au moins 67 % des folds ;
- gain médian du rendement H20 du top décile quotidien ≥ +0,25 point.

Il faut passer **les gates distributionnels et directionnels** pour parler
d'amélioration de la direction. Les scores q50 et asymétrie ne peuvent pas
remplacer le score primaire après observation du test.

## Exécution

Smoke technique :

```powershell
python -u -m modelFactory.oracle_conditional_quantiles_pmath3 --batch-id model-factory-20260909051302-323684 --horizon 20 --start-date 2016-01-01 --end-date 2025-12-31 --max-symbols 50 --max-folds 2 --log-level INFO
```

Run complet : retirer `--max-symbols` et `--max-folds`. Chaque fold terminé
met à jour `progress.json`. `report.json`, `fold_metrics.csv`,
`quantile_metrics.csv` et `oos_predictions.parquet` permettent l'audit.

Aucune table SQL, configuration live, prédiction de production ou règle de
backtest n'est modifiée.

## Smoke technique

Smoke sur 50 symboles demandés, 33 dans le pool, 12 537 événements, 84
features et deux folds. Les sept modèles et les deux verdicts terminent,
les fichiers d'audit sont produits. Le pinball médian est 6,81 % moins bon
que le témoin constant et l'AUC D1/D10 vaut 0,4309, mais ce petit sous-univers
alphabétique n'est pas utilisé pour statuer sur la piste. Artefact :
`artifacts/research/pmath3_conditional_quantiles/pmath3-smoke50-20260916`.

## Résultat complet — double NO‑GO

Artefact :
`artifacts/research/pmath3_conditional_quantiles/pmath3-full-20260916`.

Le run couvre 582 700 événements, 1 764 dates, 1 472 symboles, 84 variables
et neuf folds OOS de janvier 2021 à juillet 2025. Chaque modèle quantile est
entraîné sur au plus 100 000 exemples du train. Les taux de croisement brut
des sept quantiles sont compris entre 0,002 % et 1,34 % selon le fold ; le
réordonnancement n'est donc pas la cause principale de l'échec.

### Qualité de la distribution

L'amélioration médiane du pinball moyen est **−1,67 %** : le modèle est plus
mauvais que les quantiles constants du train, contre le gate +2 %. Seuls 2/9
folds ont un pinball moyen meilleur, contre au moins 67 % requis. L'erreur
médiane de couverture q10/q90 est de 2,40 points et passe son gate de 3 points,
mais une couverture correcte ne compense pas un score pinball dégradé.

Par quantile, q90 (+1,05 %) et q95 (+3,17 %) présentent une amélioration
médiane du pinball, chacune dans 6/9 folds. q10 (−1,82 %), q25 (−2,38 %) et
q50 (−2,79 %) se dégradent. Ces indications de queue supérieure sont
**exploratoires** : la famille de sept quantiles et la règle directionnelle
pré-enregistrées échouent. Elles ne doivent pas servir à ne conserver que q95
après observation du test.

### Qualité directionnelle

| Mesure | Score quantile primaire | Logistic directe | Gate |
|---|---:|---:|---:|
| AUC médiane D1/D10 | 0,4793 | 0,4890 | ≥ 0,53 et delta ≥ +0,01 |
| Delta AUC médian | −0,0100 | référence | ≥ +0,01 |
| Folds delta AUC positif | 4/9 | référence | ≥ 67 % |
| Lift médian rendement H20 top décile quotidien | −0,527 point | référence | ≥ +0,25 point |

Le score primaire dépasse 0,53 dans seulement deux folds ; le dernier fold
2025H1 atteint 0,5512, mais cela ne répare ni la médiane ni la stabilité.
La médiane q50 seule atteint AUC 0,4925 et l'asymétrie de queue 0,4979 : ces
scores secondaires ne sont pas promus a posteriori.

La Logistic témoin de ce protocole n'est **pas bit-à-bit identique** à celle de
P‑MATH‑0 : ici, le prétraitement est estimé sur l'échantillon de régression
quantile et l'AUC utilise tous les vrais D1/D10 du test, sans équilibrage de ce
test. On compare les deux scores P‑MATH‑3 sur exactement les mêmes lignes OOS ;
on ne compare pas directement leur AUC aux chiffres de P‑MATH‑0.

### Décision

`NO_GO_DISTRIBUTION` et `NO_GO_DIRECTION`. Aucun quantile ou score ne passe en
serving/backtest. Ne pas réoptimiser les seuils, quantiles, profondeur des
arbres ou fenêtre de train sur les neuf folds déjà consultés. La faible
amélioration de q90/q95 peut seulement motiver, avec un nouveau protocole et
une période vierge, une étude séparée de la queue haussière ; elle ne démontre
pas une capacité actuelle à distinguer D1 de D10.
