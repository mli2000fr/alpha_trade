# Temporal D1/D10 V2

## Statut et verdict final

Campagne Dataset A terminée le 7 septembre 2026 : **`NO_GO_DATASET_A`**.
Recherche uniquement : aucun artefact de serving, aucune prédiction applicative,
aucune table et aucun backtest n'ont été modifiés.

Le résultat est sans ambiguïté : les trajectoires locales récentes n'ajoutent
pas l'information directionnelle exigée pour séparer D1 de D10 à H20. Aucun
T2 ne franchit le gain pré-enregistré de `+0,01` d'AUC same-date contre T0.
Conformément au protocole, Dataset B Oracle TOP20, Dataset C, N=20, TCN/LSTM,
divergences et modèle multi-horizon ne sont donc pas ouverts.

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

## Résultats Dataset A

Le panel source contient 630 883 lignes, 1 764 dates et 399 symboles. Les
prédictions OOF comparables couvrent 91 831 lignes et 1 260 dates. Les 27
features de base prévues sont toutes disponibles.

### Résultat principal

| Variante | Modèle | AUC same-date moyenne | Delta contre T0 du modèle | Folds > 0,50 | Années > 0,50 | Spearman buckets |
|---|---|---:|---:|---:|---:|---:|
| T0 état J | Logistic | **0,51429** | référence | 70 % | 5 | **0,939** |
| T1 delta N3 | Logistic | 0,51139 | -0,00290 | 70 % | 5 | 0,842 |
| T2 trajectoire N3 | Logistic | 0,51084 | -0,00345 | 80 % | 5 | 0,915 |
| T2 trajectoire N5 | Logistic | **0,51119** | **-0,00310** | 70 % | 5 | 0,891 |
| T2 trajectoire N10 | Logistic | 0,50768 | -0,00661 | 70 % | 4 | 0,600 |
| T2 trajectoire N10 | CatBoost | 0,49614 | +0,00660 | 60 % | 4 | -0,406 |
| T2 trajectoire N3 | PairLogit | 0,49786 | +0,00311 | 60 % | 3 | -0,018 |

La photographie statique T0 avec régression logistique est la meilleure des
21 variantes. L'ajout de deltas ou de trajectoires la dégrade à toutes les
fenêtres. Il n'existe pas non plus de progression N3 → N5 → N10 : la fenêtre
N10 est la moins bonne pour Logistic.

Le `+0,00660` de CatBoost T2-N10 n'est pas un signal exploitable. Il compare
une variante à un T0 CatBoost déjà inférieur au hasard ; son AUC absolue reste
à 0,49614 et ses buckets sont inversés/non monotones. PairLogit présente le
même problème : ses petits deltas positifs restent sous `+0,01`, avec une AUC
absolue inférieure à 0,50 et des buckets non monotones.

### Taille réelle du signal statique

T0 Logistic est légèrement supérieur au hasard, mais insuffisant pour une
promotion :

- AUC globale OOF : 0,51466 ;
- AUC same-date moyenne/médiane : 0,51429 / 0,51335 ;
- seulement 55,56 % des dates dépassent 0,50 et 34,44 % dépassent 0,55 ;
- 10 % supérieurs du score : 53,11 % de D10 ;
- 10 % inférieurs du score : 51,75 % de D1 ;
- AUC d'amplitude tirée de la confiance directionnelle : 0,55272.

Le dernier point est important : les features semblent davantage reconnaître
une journée/société à forte amplitude qu'ordonner correctement son signe. Cela
confirme le problème déjà observé dans les expériences Oracle et
GlobalDirection.

### Stabilité temporelle

Pour T0 Logistic, l'AUC annuelle vaut 0,476 en 2020, puis 0,514 en 2021,
0,538 en 2022, 0,511 en 2023, 0,510 en 2024 et 0,531 en 2025. Trois des dix
folds restent sous 0,50, dont le premier à 0,474. Le signal statique est donc
faible et dépendant de la période ; sa belle monotonie agrégée ne suffit pas à
en faire un modèle servable.

T2 Logistic N5 ne corrige pas cette faiblesse : 2020 reste à 0,471 et trois
folds sur dix sont sous 0,50. Son décile supérieur contient 52,63 % de D10 et
son décile inférieur seulement 50,46 % de D1, tous deux inférieurs à T0.

### Audit des labels

L'audit autoritatif porte sur 130 385 observations D1/D10 :

- `P(rendement < 0 | D1) = 99,51 %` ;
- `P(rendement > 0 | D10) = 98,87 %` ;
- `P(rendement <= -3 % | D1) = 97,59 %` ;
- `P(rendement >= +3 % | D10) = 97,27 %` ;
- seulement 0,68 % des dates ont les deux tails du même signe absolu.

La cible représente donc bien une polarité future économiquement distincte.
L'échec ne vient pas d'un mélange massif des labels D1/D10, mais de l'absence
d'information prédictive directionnelle suffisante dans les trajectoires
locales testées. L'univers construit depuis les symboles disponibles dans le
gate Oracle OOF conserve néanmoins un risque de biais de survivants, explicitement
signalé dans le rapport.

Les rendements moyens ne doivent pas être interprétés comme une espérance
économique robuste à ce stade. L'[audit de l'anomalie D10](d10_corporate_action_anomaly_audit.md)
a identifié deux ruptures de continuité WFRD/CHRD : 36 lignes, soit 0,058 % des
D10, produisent 67,66 % de la somme des rendements D10. En 2019, la moyenne
D10 atteint ainsi +281,63 % contre +17,08 % en médiane. La sensibilité sans les
deux symboles confirme néanmoins le rejet, fondé sur l'AUC same-date.

## Décision scientifique

1. **Ne pas lancer Dataset B** : le gate Dataset A a échoué.
2. **Ne pas lancer bootstrap/placebo** : ces contrôles étaient prévus pour une
   variante candidate à la promotion ; aucune variante ne l'est.
3. **Ne pas complexifier le modèle temporel** avec N20, TCN, LSTM ou Transformer.
4. **Ne rien servir** : `serving_ready=false` et la confirmation finale est
   `UNAVAILABLE_ALREADY_OBSERVED`.
5. Conserver T0 Logistic uniquement comme témoin de recherche faible, pas comme
   politique de trading.

La suite rationnelle doit apporter une information réellement nouvelle et plus
proche de la formation du prix : microstructure pré-market/ouverture, flux
d'ordres ou données de marché intraday strictement PIT. Une autre transformation
des mêmes 27 séries journalières n'est plus prioritaire.

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

Une variante terminée est reprise depuis son Parquet. Le run final comporte
21 variantes : trois modèles pour T0, puis trois modèles pour T1 et T2 à chacune
des fenêtres 3/5/10. La campagne a exécuté six variantes en parallèle,
avec deux threads internes par variante, soit au maximum douze threads de
calcul modèle. Ce réglage privilégie le débit inter-variantes tout en respectant
les douze processeurs logiques de la machine.

Artefact final :
`artifacts/models/shared_directional/temporal-d1d10-v2-a-20260906-0802c8/report.json`.

La configuration figée est
[`config/research/temporal_d1d10_v2.json`](../../config/research/temporal_d1d10_v2.json).
Le protocole scientifique complet reste décrit dans
[`prompt/todo_tail_direction_classifier_V2.md`](../../prompt/todo_tail_direction_classifier_V2.md).
