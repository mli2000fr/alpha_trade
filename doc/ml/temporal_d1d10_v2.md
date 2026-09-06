# Temporal D1/D10 V2

## Statut

Campagne Dataset A en cours. Recherche uniquement : aucun artefact de serving,
aucune prédiction applicative, aucune table et aucun backtest ne sont modifiés.

## Hypothèse

Le niveau d'une feature au signal J peut masquer sa trajectoire récente. V2
teste si les chemins strictement passés `[J-N,...,J]` distinguent le futur D1
du futur D10 mieux que la photographie prise uniquement à J.

```text
features locales PIT J-N ... J
              │
              ▼
    Temporal Tail Classifier
       score D1 ◄──► D10
```

La sortie s'appelle `tail_polarity_score`. Elle n'est pas une probabilité LONG
ou SHORT et ne peut pas entrer en production pendant Dataset A.

## Contrat de la campagne principale

- Batch de labels : `model-factory-20260904192500-0802c8`.
- Horizon : H20.
- D1 : bottom 10 % du rendement futur cross-sectionnel de la date.
- D10 : top 10 % de ce même rendement.
- Dataset A : D1/D10 pour le fit ; D2-D9 conservés dans le test pour les audits.
- Univers : 399 symboles présents dans le gate Oracle OOF du batch.
- Période : 2018-07-05 au 2025-07-11.
- Fenêtres pré-enregistrées : N=3, 5 et 10.
- Convention : N représente `[J-N,...,J]`, donc N+1 observations.
- Purge : une ligne de train n'est admise que si
  `oracle_available_date < test_start`.
- Validation : walk-forward par blocs de 126 séances après au moins 504 séances.
- Confirmation finale : `UNAVAILABLE_ALREADY_OBSERVED`; la campagne ne peut
  produire au mieux qu'un `GO_RESEARCH` interne avant une nouvelle période.

## Features

Le budget est figé à 27 features de base locales : prix/momentum, force relative,
position dans la tendance, volume/CMF, volatilité et régime marché. Elles sont
recalculées par le moteur Oracle autoritatif avec le profil O0 du batch. Aucun
symbol ID, score Oracle, Global Rank, date ordinale ou variable future n'entre
dans le modèle.

Représentations :

- `T0_STATE` : valeurs à J uniquement ;
- `T1_STATE_DELTA_N` : état J et variation signée J moins J-N ;
- `T2_STATE_TRAJECTORY_N` : T1 plus pente OLS, dispersion, persistance positive
  pour les séries signées et une accélération canonique sur quatre familles.

Tous les calculs rolling sont groupés par symbole, triés par date et exigent une
fenêtre complète. Aucun backward-fill n'est utilisé.

## Modèles et métriques

Chaque représentation est comparée sur exactement les mêmes folds avec :

- régression logistique, imputation médiane et scaling appris sur train ;
- CatBoost classification ;
- CatBoost PairLogit groupé par date.

La métrique principale est la moyenne de l'AUC D1/D10 calculée séparément à
chaque date. Le rapport contient également médiane et dispersion, taux de dates
au-dessus de 0,50/0,55/0,60, AUC globale, stabilité fold/année, enrichissement
des 10 % extrêmes du score, buckets, métriques secondaires et un contrôle
direction contre amplitude.

Le gate T2 exige simultanément :

- gain d'AUC same-date moyen d'au moins +0,01 contre T0 du même modèle ;
- au moins 60 % des folds au-dessus de 0,50 ;
- au moins trois années au-dessus de 0,50 ;
- monotonie de buckets de Spearman au moins égale à 0,70.

Si aucun T2 ne passe, Dataset B Oracle TOP20 n'est pas lancé. N=20 et les
modèles séquentiels restent interdits sauf progression cohérente de N=3 à N=10.

## Artefacts et reprise

```text
artifacts/models/shared_directional/temporal-d1d10-v2-a-20260906-0802c8/
  base_feature_panel.parquet
  dataset_a.parquet
  variants/*.parquet
  variants/*.json
  oof_predictions.parquet
  comparison.csv
  report.json
  TEMPORAL_D1D10_CLASSIFIER_REPORT.md
```

Une variante terminée est reprise depuis son Parquet. Le run complet comporte
21 variantes : trois modèles pour T0, puis trois modèles pour T1 et T2 à chacune
des fenêtres 3/5/10. La campagne courante exécute six variantes en parallèle,
avec deux threads internes par variante, soit au maximum douze threads de
calcul modèle. Ce réglage privilégie le débit inter-variantes tout en respectant
les douze processeurs logiques de la machine.

La configuration figée est
[`config/research/temporal_d1d10_v2.json`](../../config/research/temporal_d1d10_v2.json).
Le protocole scientifique complet reste décrit dans
[`prompt/todo_tail_direction_classifier_V2.md`](../../prompt/todo_tail_direction_classifier_V2.md).
