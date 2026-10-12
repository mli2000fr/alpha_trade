# Oracle TP avant SL — audit TOP10 et choix LONG/SHORT

Audit terminé le **12 octobre 2026**, sur le batch utilisateur
`model-factory-20261011221400-867a1e`. Aucun nouvel entraînement, changement de
modèle, écriture SQL, appel fournisseur, ordre ou backtest portefeuille.

**Conclusion : le classement par sens concentre les succès, mais le choix du
sens par comparaison directe des deux scores n'apporte pas d'avantage stable.**
Ce sont des labels TP avant SL, pas les anciens déciles D1/D10 à H20.

## Périmètre réellement testé

- Univers figé de **1 790 titres** ; 173 features, deux LightGBM globaux.
- Campagne configurée `2016-01-01 → 2024-12-31`.
- Prédictions hors échantillon disponibles : **2018-07-05 → 2024-07-09**,
  **12 folds**, **1 512 séances**, **2 603 627 observations titre/date**.
- 2018 et 2024 sont partielles. **2025 et 2026 ne sont pas testées ici**.
- Contrat inchangé : entrée open J+1, TP 20 %, SL 7 %, vingt séances,
  expiration open J21, disponibilité conservatrice des labels J22.
- Le SL n'est pas un plafond garanti de perte : gaps traités à l'open.

Les checksums des modèles et OOF de chaque fold correspondent aux checkpoints.
Absence de doublons date/titre et contrôle des bornes de test ; disponibilité des
labels train strictement avant validation et validation strictement avant test.
L'intégrité du fichier OOF principal est contrôlée avant/après l'audit. Ces
contrôles ne certifient pas à eux seuls le PIT de toutes les features et prix.

## Règles d'audit, sans ajustement sur les pertes

Quatre sélections, **dix titres par séance** (pas 10 % de l'univers) :

1. `LONG_TOP10` : dix plus grands scores LONG, tous évalués dans le sens LONG.
2. `SHORT_TOP10` : dix plus grands scores SHORT, tous évalués SHORT.
3. `MAX_TOP10_ARGMAX_DIAGNOSTIC` : dix plus grands maxima des deux scores,
   sens du plus grand score, **sans seuil** ; diagnostic séparé, pas modification
   de la politique livrée. Égalité des scores à 1e−12 près → abstention.
4. `MAX_TOP10_FROZEN_THRESHOLD` : mêmes dix maxima, mais conservation de la
   règle réelle archivée : maximum ≥ **0,55**, sinon abstention.

Égalité de rang départagée par symbole croissant. Les candidats sont sélectionnés
**avant** d'exclure les résultats futurs inconnus : aucun remplacement par un
onzième titre mieux documenté. Les inconnus, abstentions, TP, SL et expirations
sont comptés séparément ; le taux de TP a pour dénominateur les résultats connus.

Le diagnostic sans seuil a été défini avant son calcul. Il ne constitue ni une
nouvelle politique déployée, ni une optimisation rétrospective du seuil 0,55.

## Résultats globaux

| Sélection | Sélectionnés | TP | SL | Expiration | Résultat inconnu | Abstention | Taux TP évalué |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| TOP10 LONG | 15 120 | 3 682 | 9 990 | 1 414 | 34 | 0 | **24,41 %** |
| TOP10 SHORT | 15 120 | 2 461 | 10 442 | 2 085 | 132 | 0 | **16,42 %** |
| TOP10 maximum, sens argmax sans seuil | 15 120 | 3 326 | 10 217 | 1 543 | 34 | 0 | **22,05 %** |
| TOP10 maximum, politique figée seuil 0,55 | 15 120 | 99 | 267 | 36 | 1 | 14 717 | **24,63 %** |

Le classement LONG améliore la fréquence de succès par rapport à l'univers
scoré (**6,93 %**), et le classement SHORT aussi (**4,86 %**). La majorité des
candidats TOP10 se termine néanmoins au SL. Cela ne démontre pas une rentabilité.
Les expirations ne sont pas forcément perdantes, mais ne sont pas des succès TP.

Sur les **mêmes 15 083 observations qualifiées** de la sélection maximum :

| Sens appliqué aux mêmes candidats | Taux TP |
| --- | ---: |
| Sens du plus grand score, sans seuil | **22,05 %** |
| Toujours LONG | **24,18 %** |
| Toujours SHORT | **18,10 %** |

L'argmax perd **2,13 points** face à toujours LONG. Intervalle descriptif par
blocs : **[−3,50 ; −0,74] points**. Ce n'est pas la comparaison de deux sélections
différentes : les trois sens sont évalués sur les mêmes titres et dates.

La politique figée ne choisit que **403 / 15 120** candidats (2,67 %), dont
402 qualifiés : **24,63 %** de TP contre **25,87 %** en prenant toujours LONG
sur ces mêmes 402 observations. La couverture est trop faible et variable pour
la promouvoir sur cette seule moyenne.

## Par année

| Année | Séances | TOP10 LONG | TOP10 SHORT | TOP10 maximum, sens argmax | Choix effectifs de la politique figée |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2018 partielle | 124 | 16,45 % | 23,19 % | 16,45 % | 0 |
| 2019 | 252 | 26,45 % | 15,90 % | 24,66 % | 6 |
| 2020 | 253 | 28,41 % | 20,87 % | 28,37 % | 268 |
| 2021 | 252 | 24,41 % | 18,00 % | 24,31 % | 21 |
| 2022 | 251 | 22,10 % | 18,97 % | 20,93 % | 108 |
| 2023 | 250 | 27,09 % | 9,60 % | 21,88 % | 0 |
| 2024 partielle | 130 | 19,54 % | 7,85 % | **8,15 %** | 0 |

Les tableaux par **12 folds** et par **73 mois**, avec couverture, concentration
et comptages, sont conservés dans le rapport JSON. Les années/folds ne sont pas
des observations indépendantes : les chemins de vingt séances se chevauchent.
Le nombre de sélections titre/date n'est pas un nombre d'ordres exécutables.

## Réserve technique : deux scores non calibrés, donc pas automatiquement comparables

Sur les candidats de la sélection maximum en 2024 :

- argmax choisit **1 241 SHORT / 59 LONG** ;
- taux TP argmax **8,15 %** ;
- toujours LONG sur les mêmes candidats : **20,38 %** ;
- toujours SHORT : **7,77 %**.

Le classement global change donc fortement le sens choisi, sans gain associé.
Le diagnostic sur toute la population qualifiée 2024 montre :

| Modèle | Score moyen | Fréquence TP réellement observée |
| --- | ---: | ---: |
| LONG | 5,66 % | 5,75 % |
| SHORT | **3,48 %** | **1,78 %** |

Le SHORT surestime globalement sa fréquence de succès dans cette période ; les
bins fixes confirment une surestimation dans plusieurs plages de score. Un score
supérieur à celui du LONG peut donc être trompeur pour le choix du sens.
La proximité de la moyenne LONG et de sa fréquence ne prouve pas une calibration
parfaite de chaque titre ou du TOP10. Les modèles ont notamment retenu **12 arbres
LONG / 109 arbres SHORT** pour le dernier fold, pas le même modèle constant.

**Ce n'est pas la preuve d'un bug**, ni la démonstration que la calibration résoudra
la direction. Les fréquences changent avec les périodes et les modèles ; les deux
scores sont indépendants et ne sont pas complémentaires. Aucune calibration
n'a été ajustée sur ces résultats hors échantillon.

## Incertitude et limites

- Bootstrap descriptif : blocs de **vingt dates de décision consécutives**,
  2 000 réplications, graine 12026. Les titres restent groupés par date.
  La persistance des régimes peut dépasser vingt jours ; les intervalles ne
  sont pas une certification statistique ou économique.
- Les dix symboles les plus répétés constituent **17,39 %** des sélections
  maximum ; les récurrences et dépendances sont archivées, pas assimilées à
  autant de paris indépendants.
- Univers actuel statique : survivance possible ; prix ajustés actuels, pas
  revision-PIT ; features selon leurs propres garanties de disponibilité.
- `either_tp_rate = 42,28 %` sur les mêmes candidats qualifiés maximum désigne
  une opportunité connue **a posteriori** dans au moins un sens. Ce n'est pas
  une direction prédite ni une réussite de trading de 42,28 %.
- Coûts, capital, concurrence des positions, liquidité, emprunt SHORT et fills
  ne sont pas qualifiés ici. Pas de PnL net, ni promotion PAPER/LIVE.

## Suite bornée proposée — pas encore exécutée

Le classement par sens mérite une confirmation ; ne pas le jeter simplement
parce que l'argmax des deux scores échoue. En revanche, ne pas déployer ce choix
LONG/SHORT tel quel.

Une éventuelle remédiation doit avoir un protocole séparé : comparer/calibrer les
deux scores **uniquement sur train/validation chronologiques**, jamais sur les
labels du test, puis comparer aux règles non calibrées et aux baselines de sens.
Elle exige un nouveau GO ; aucune modification du batch utilisateur ici.

Ensuite, confirmation **2025–2026** avec modèles et règles figés, sans optimisation
sur les pertes de ces années. Ces périodes ont déjà été étudiées ailleurs : elles
ne sont pas des holdouts totalement vierges. Le test économique vient après une
confirmation suffisamment stable, pas après une seule AUC ou un taux TP agrégé.

## Reproduction et artefacts

```powershell
python -u -m scripts.research.us_oracle_barrier_top10_audit --source artifacts/models/model-factory-20261011221400-867a1e/oracle_barrier --output artifacts/research/us_oracle_barrier_top10/audit-NOUVEAU
```

Une destination non vide est refusée ; aucun artefact de modèle n'est remplacé.

- [Rapport complet lisible](../../artifacts/research/us_oracle_barrier_top10/audit-20261012-v2/report.md).
- [Rapport JSON](../../artifacts/research/us_oracle_barrier_top10/audit-20261012-v2/report.json) : global/année/fold/mois, baselines appariées, bins, Brier, concentration.
- `selected.parquet` : 60 480 sélections (4 règles × 15 120), rang, scores,
  direction, résultat et motif de réserve.
- `daily_counts.parquet` : comptages par date/règle, sans données imputées.
- `protocol.json` : règles, seuil, bootstrap, empreintes des sources et campagne.
- `progress.json` : `COMPLETED`.

V1 était le même audit de sélections ; V2 ajoute le diagnostic descriptif des
scores, sans changer aucun classement, seuil ou résultat. Les deux sont conservés.
**64 tests ciblés réussis** : 51 du modèle et 13 de l'audit. Tests synthétiques,
sans base ni fournisseur ; pas la suite complète du dépôt ou sa couverture globale.

Référence : [contrat et entraînement](oracle_barrier_training.md).
