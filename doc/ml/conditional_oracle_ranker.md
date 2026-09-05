# Ranker conditionnel au TOP20 Oracle Extreme

## Statut

Ce module est une expérience de recherche. Il n'est relié ni au serving, ni à
la persistance des prédictions de production, ni aux modes de cascade du
backtest. Ses contrats déclarent `research_only=true` et
`serving_ready=false`.

Code : `modelFactory/conditional_oracle_ranker.py`.

## Question étudiée

Oracle Extreme estime la magnitude d'un futur mouvement, sans son sens. Après
avoir calculé le percentile Oracle sur l'univers quotidien canonique, le module
conserve le TOP20 %, puis entraîne un ranker mutualisé pour ordonner uniquement
ces événements :

```text
univers complet
  -> percentile Oracle OOF
  -> TOP20 % par magnitude probable
  -> CatBoostRanker groupé par date
  -> 20 % supérieurs : candidats LONG
  -> 20 % inférieurs : candidats SHORT potentiels
```

Chaque queue représente environ 4 % de l'univers initial. Le terme « potentiel »
est essentiel côté SHORT : un mauvais rang relatif n'implique pas un rendement
absolu négatif.

## Horizons et modèles

La campagne pré-enregistre deux horizons, sans chercher le meilleur a posteriori :

- H3, comparable à E2-B LONG H3 ;
- H20, horizon naturel de l'Oracle Extreme étudié.

Un modèle indépendant est entraîné par horizon. H5, H10 et H15 ne font pas
partie de cette campagne.

## Population Oracle

La population de développement vient exclusivement de
`artifacts/models/<oracle_batch>/_oracle_oof_gate.parquet`. Le chargeur :

1. exige les colonnes d'éligibilité et de disponibilité OOF ;
2. refuse une ligne déclarée éligible sans disponibilité OOF ;
3. recalcule le TOP20 depuis le percentile persisté ;
4. joint le gate au dataset de features par `(date, symbol)` ;
5. conserve le percentile Oracle pour les benchmarks seulement.

`proba_extreme`, son percentile, `global_rank_20` et toutes les cibles futures
sont interdits dans les features du ranker.

## Cible de ranking

Pour chaque horizon et chaque date, le module calcule le rendement futur brut
ajusté de chaque membre du pool, puis son percentile transversal. Ce percentile
est transformé en relevance entière `0..9` :

```text
conditional_rank_label = floor(rank_pct(future_return_H) * 10), borné à 0..9
```

La query CatBoost est la date. Le modèle optimise `PairLogit` et ne voit donc ni
les classes D1/D10 de l'Oracle, ni une probabilité absolue de hausse.

Les rendements excess-SPY et résiduels secteur sont conservés pour les
diagnostics, mais la cible primaire est le sens absolu du rendement brut. Une
cible relative pourrait sélectionner un titre qui baisse moins que le marché et
serait insuffisante pour autoriser un LONG ou un SHORT absolu.

## Walk-Forward et purge

Le découpage réutilise `build_folds_adaptive` :

```text
train expansif -> validation early stopping -> test strictement OOS
```

Les groupes d'une date restent entiers. `forecast_horizon` vaut 3 ou 20 selon le
modèle et crée la purge correspondante. La garde de disponibilité Oracle reste
également appliquée. Le test ne participe jamais à l'early stopping.

Valeurs canoniques de la campagne :

| Paramètre | Valeur |
|---|---:|
| train minimal | 504 dates |
| validation | 126 dates |
| test | 126 dates |
| pas | 126 dates |
| maximum | 12 folds |
| itérations maximales | 600 |
| profondeur | 6 |
| learning rate | 0,03 |

## Politiques évaluées

La politique primaire est figée à 20 % de chaque côté du pool Oracle. Le nombre
quotidien est `ceil(taille_pool * 0.20)`, avec un minimum d'un symbole. Les
égalités sont résolues de manière déterministe par Pandas après l'ordre des
lignes du dataset.

Le rapport publie séparément :

- rendement brut et signé ;
- médiane ;
- hit rate ;
- précision LONG `return >= +3 %` ;
- précision SHORT `return <= -3 %` ;
- lift contre l'espérance d'un tirage quotidien de même taille ;
- spread de rendement queue haute moins queue basse.

## Métriques de ranking

Le rapport conserve :

- IC Spearman quotidien moyen et médian ;
- dispersion, taux de jours positifs et intervalle à 95 % indicatif ;
- NDCG à la fraction de sélection ;
- buckets de score ;
- métriques par semestre ;
- stabilité et nombre de folds positifs.

L'intervalle IC repose sur l'erreur standard des IC quotidiens ; il s'agit d'un
diagnostic et non d'une preuve indépendante si les jours sont autocorrélés.

## Baselines

Toutes les baselines sont recalculées dans le même pool et à taille quotidienne
identique :

- tirage aléatoire apparié, calculé par espérance quotidienne ;
- percentile Oracle utilisé volontairement comme contrôle sans direction ;
- `momentum_20` ;
- `relative_strength_20` ;
- Global Ranking existant lorsqu'un batch explicitement fourni possède des
  rangs exploitables ;
- score E2-B H3 sur son intersection OOS, si son artefact est fourni.

Une baseline absente est publiée avec `available=false`. Elle n'est jamais
remplacée silencieusement. Les rangs historiques d'un batch Global Ranking ne
sont pas automatiquement considérés OOS : leur provenance doit être vérifiée
avant interprétation.

## Gates préfixés

Au moins 75 % des folds valides doivent confirmer la stabilité. Les gates de
ranking sont :

- IC quotidien moyen >= 0,02 ;
- IC positif dans au moins 75 % des folds ;
- spread brut >= 0,50 point de pourcentage ;
- spread positif dans au moins 75 % des folds.

Une branche LONG exige en plus : rendement signé positif, lift rendement >=
0,25 point, lift précision >= 2 points et lift rendement positif dans au moins
75 % des folds.

Une branche SHORT exige les mêmes lifts, mais également un rendement brut moyen
réellement négatif dans la queue basse. Les verdicts sont indépendants :
`GO_DEVELOPMENT` ou `NO_GO` pour chaque côté et chaque horizon.

Un GO de développement n'autorise pas le serving. Il ouvre seulement une
confirmation postérieure. La période 2026H1 ayant déjà été observée lors des
expériences précédentes, elle ne peut plus être présentée comme confirmation
totalement intacte pour cette nouvelle hypothèse.

## Artefacts

Une campagne produit :

```text
artifacts/models/conditional_oracle_ranker/conditional-oracle-ranker-*/
  campaign.json
  feature_profile.json
  h3/
    ranker.cbm
    metrics.json
    oof_predictions.parquet
  h20/
    ranker.cbm
    metrics.json
    oof_predictions.parquet
```

`campaign.json` enregistre le batch Oracle, le profil, les features ordonnées,
la population, les paramètres Walk-Forward, les gates et les verdicts.

## Commande complète

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.conditional_oracle_ranker --oracle-batch-id model-factory-20260904192500-0802c8 --start-date 2016-01-01 --end-date 2025-12-31 --horizons 3,20 --pool-pct 0.20 --selection-fraction 0.20 --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 126 --wf-max-splits 12 --iterations 600 --depth 6 --learning-rate 0.03 --context-mode none --target-up-threshold 0.03 --target-down-threshold -0.03 --e2b-artifact artifacts\models\shared_directional\shared-long-h3-confirm-20260905074401-0802c8 --log-level INFO
```

Ne pas ajouter un batch Global Ranking à cette commande sans avoir démontré que
les lignes comparées sont OOS sur chaque date. Son absence n'affecte pas
l'entraînement ; elle retire uniquement cette baseline du rapport.

## Interdictions

- ne pas interpréter le percentile Oracle comme une direction ;
- ne pas forcer SHORT lorsque le rendement brut de la queue basse est positif ;
- ne pas changer 20 % / 20 % après lecture des résultats ;
- ne pas choisir H3 ou H20 a posteriori sans tenir compte des deux tests ;
- ne pas brancher les modèles dans la cascade avant confirmation et GO ;
- ne pas utiliser 2026H1 comme si cette période n'avait jamais été observée.

## Résultat de la campagne du 5 septembre 2026

La campagne complète
`conditional-oracle-ranker-20260905082051-0802c8` a entraîné H3 et H20 sur le
TOP20 OOF du batch Oracle `model-factory-20260904192500-0802c8`. Elle couvre
86 256 prédictions OOS, 1 134 dates et neuf folds par horizon.

| Horizon | IC quotidien | folds IC+ | spread haut-bas | LONG signé | lift LONG vs pool | SHORT signé | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| H3 | +0,0136 | 6/9 | +0,21 % | +0,50 % | +0,17 % | -0,29 % | NO-GO |
| H20 | +0,0266 | 5/9 | +0,54 % | +2,42 % | +0,57 % | -1,87 % | NO-GO |

H3 échoue tous les gates de ranking : IC inférieur à 0,02, seulement six folds
positifs, spread inférieur à 0,50 % et seulement six folds au spread positif.
La queue SHORT baisse insuffisamment : son rendement brut reste positif, donc
le short signé est négatif.

H20 passe les seuils agrégés d'IC et de spread. La branche LONG passe également
les lifts agrégés de rendement et de précision. Cependant, IC et spread ne sont
positifs que dans cinq folds sur neuf, et le lift LONG dans six folds au lieu de
sept. Le signal est principalement concentré en 2021–2022 puis s'inverse ou
devient faible sur plusieurs fenêtres récentes.

Le contrôle Oracle sans direction reste meilleur côté LONG : à H20, sélectionner
les plus fortes amplitudes du TOP20 produit +3,00 % contre +2,42 % pour le
ranker. À H3, Oracle obtient +0,64 %, E2-B +0,53 % et le ranker +0,50 %. Le
ranker ne démontre donc pas d'apport incrémental au gate Oracle.

Verdict final : ne pas ouvrir de confirmation et ne pas intégrer le ranker dans
la cascade. Les artefacts restent des résultats de recherche. La prochaine
hypothèse indépendante est l'audit univarié des règles screener PIT après
Oracle, sans combiner ni retuner le ranker rejeté.
