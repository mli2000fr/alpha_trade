# US — Répétition des signaux et fiabilité opérationnelle de P(LONG)

## Décision au 5 octobre 2026

Les deux audits sont terminés en diagnostic. Aucun entraînement, accès SQL,
modification du serving ou blacklist n'a été effectué. La répétition explique
une partie des effectifs, mais sa réduction ne résout pas janvier 2026.
Les probabilités LONG n'offrent pas un classement fiable et monotone des
rendements sur toutes les périodes. Aucun nouveau seuil n'est proposé.

Cette analyse prolonge l'[audit des contextes et de la concentration](us_degradation_commune_2026q1_audit.md).
Elle porte uniquement sur le batch ancien `model-factory-20260903174624-014164`,
les véritables prédictions `directional_bundle` conservées et les labels H20
natifs reconstruits. Le groupe `oracle_synth` est exclu du filtre directionnel.
Les fichiers source sont ceux de `original-monthly-20261005-v1`.

## 1. Trois manières de compter les signaux

Un événement est un symbole à une date de signal. Le même titre peut apparaître
chaque jour et les fenêtres H20 se chevauchent. Cela ne donne pas autant de
positions ni d'observations économiques indépendantes.

Le protocole est enregistré avant le calcul dans `protocol.json` :

1. **Tous les signaux** : même filtre LONG que précédemment, sans changement.
2. **Début d'épisode continu** : premier signal ; un nouveau début est autorisé
   après au moins une séance du calendrier sans signal LONG retenu pour le titre.
   Un épisode n'est pas une position réelle ni une observation indépendante.
3. **Premier signal puis délai de 20 séances** : garder le premier signal d'un
   titre, attendre au moins 20 séances avant d'en garder un autre. La règle ne
   dépend pas du rendement futur. Elle est appliquée sur toute la série, sans
   remise à zéro au changement de mois ou d'année.

Le calendrier est celui des séances ayant des scores Oracle dans le snapshot.
Le premier signal du début du fichier est censuré à gauche : un épisode commencé
avant juillet 2024 ne peut pas être reconstitué. La réduction des chevauchements
au sein d'un titre n'enlève pas la dépendance entre titres exposés aux mêmes jours.

### Résultats par fenêtre

Rendements moyens des événements clôture ajustée J → J+20, sans coûts ni lifecycle.
Les effectifs entre parenthèses sont des événements, pas des trades.

| Fenêtre | Tous les signaux | Début d'épisode | Délai de 20 séances |
|---|---:|---:|---:|
| 2024H2 | −2,14 % (442) | −0,84 % (90) | +0,61 % (51) |
| 2025H1 | +1,16 % (695) | +2,16 % (98) | +2,35 % (63) |
| 2025H2 | +2,05 % (408) | +1,93 % (68) | +1,71 % (40) |
| 2026Q1 | +0,81 % (297) | −0,004 % (57) | −0,84 % (28) |
| 2026Q2 | −0,24 % (358) | +4,51 % (35) | +1,13 % (27) |

Au total, 2 200 signaux correspondent à 348 débuts d'épisodes ou 209 événements
avec délai de 20 séances. Cela réduit beaucoup les effectifs statistiques,
mais ne produit pas un avantage uniforme. Les petits effectifs, notamment en
2026, empêchent de conclure à une amélioration économique stable.

### Janvier 2026

| Comptage | Événements | Rendement H20 moyen | Rendement positif |
|---|---:|---:|---:|
| Tous | 80 | −7,56 % | 30,00 % |
| Débuts d'épisodes | 14 | −5,28 % | 28,57 % |
| Délai 20 séances | 8 | −10,51 % | 12,50 % |

Les mauvaises anticipations ne disparaissent donc pas lorsqu'on retire une
grande partie des répétitions. Il serait incorrect d'attribuer tout janvier à
un simple problème de comptage ou de recommander ce délai comme correctif validé.

TTD illustre la persistance : ses 20 signaux de janvier font partie d'un épisode
continu commencé le 10 septembre 2025 et encore présent au 30 juin 2026, soit
202 signaux. Le rendement H20 du premier signal de cet épisode était **+17,19 %**,
mais la moyenne des rendements H20 chevauchants de l'épisode est **−7,95 %**.
Un bon premier signal ne garantit donc pas une direction favorable durable.
En janvier, P(LONG) de TTD reste entre 0,812 et 0,820 alors que toutes les
fenêtres H20 de ces 20 observations sont perdantes.

### Illustration d'un plafond de concentration

Un plafond figé de 10 % par titre sur le budget de chaque journée de signal a
également été calculé, avec le solde laissé en cash. Il ne constitue **pas** un
portefeuille exécutable : ces budgets H20 se chevauchent et le capital disponible
entre journées n'est pas simulé. Diminuer les pertes en investissant moins réduit
également les gains ; il ne faut pas appeler cela une amélioration du modèle.
Les chiffres et la fraction de cash sont conservés dans `repetition_windows`.

## 2. Ce que vérifie l'audit des probabilités

Trois populations distinctes sont examinées :

- Oracle TOP20 avec un modèle directionnel réellement disponible ;
- les candidats LONG passant le filtre figé ;
- ces candidats LONG avec délai de 20 séances.

Les tranches sont fixées à 0–0,35, 0,35–0,55, 0,55–0,65, 0,65–0,75,
0,75–0,85, 0,85–0,95 et 0,95–1, borne supérieure incluse. Les effectifs,
dates, symboles, P(LONG) moyenne, rendements positifs, rendements >3 %, D1/D10
et rendement moyen sont conservés par tranche et semestre.

Deux événements opérationnels sont évalués : rendement ajusté H20 >0 et >3 %.
Le rapport d'entraînement archivé mentionne une cible ternaire avec seuils
±3 %, mais le manifeste original complet n'est plus disponible. La construction
exacte des cibles conditionnelles et la version du calibrateur ne sont pas
certifiées. **Il ne s'agit donc pas d'une validation formelle de calibration
sur le label exact ayant servi à l'entraînement.**

P(LONG) n'est pas directement P(D10), ni P(trade gagnant après stops/coûts).
Les probabilités LONG et SHORT proviennent de branches distinctes : elles ne
sont pas renormalisées ici comme si elles formaient une distribution unique.

### Classement sur tous les candidats Oracle servables

AUC pour le rendement H20 positif ; 0,5 signifie absence de classement sur ce
critère dans l'échantillon. Pas de test de significativité : les observations
sont corrélées et les mêmes historiques ont déjà été examinés.

| Fenêtre | AUC P(LONG) → rendement positif |
|---|---:|
| 2024H2 | 0,439 |
| 2025H1 | 0,487 |
| 2025H2 | 0,500 |
| 2026Q1 | 0,511 |
| 2026Q2 | 0,516 |

Le pouvoir de classement global n'est pas stable et fort. Le Brier opérationnel
(erreur quadratique entre probabilité et événement observé, plus petit = mieux)
est supérieur à celui d'une probabilité constante sur chaque fenêtre. La
constante est la fréquence 2024–2025 sur les candidats Oracle servables : elle
est rétrospective sur cette période, et figée pour 2026. En 2026Q1, Brier
0,272 contre 0,253 pour le rendement positif ; en 2026Q2, 0,291 contre 0,249.
Cela motive une réserve sur l'interprétation opérationnelle des probabilités,
pas la preuve d'un bug du calibrateur.

### Les fortes probabilités ne sont pas systématiquement meilleures

Parmi les LONG filtrés de 2025H2 :

| Tranche | Événements | P(LONG) moyenne | H20 positif | Rendement H20 moyen |
|---|---:|---:|---:|---:|
| 0,55–0,65 | 96 | 0,595 | 70,83 % | +5,47 % |
| 0,65–0,75 | 174 | 0,706 | 55,75 % | +3,11 % |
| 0,75–0,85 | 125 | 0,787 | 44,80 % | −2,82 % |
| 0,85–0,95 | 13 | 0,880 | 69,23 % | +9,43 % |

En 2026Q1, la tranche 0,75–0,85 compte 124 observations, avec P(LONG) moyenne
0,802 mais seulement 41,94 % de rendements positifs et −0,70 % en moyenne.
La tranche 0,85–0,95 compte 19 observations sur **deux titres seulement** :
son résultat favorable ne permet pas de fixer un seuil production à 0,85.
La tranche >0,95 ne compte que deux observations sur un titre.

## 3. Hétérogénéité entre symboles et nouvelle réserve technique

Sur les titres avec au moins 30 événements évalués et les deux classes de
rendement présentes, la médiane des AUC par symbole est 0,449 en 2024 (41 titres),
0,494 en 2025 (39 titres) et 0,558 en 2026H1 (32 titres).
Ce n'est pas une preuve de progression généralisable : les titres et périodes
diffèrent, les fenêtres se chevauchent et les estimations ont des effectifs
variables. L'écart avec l'AUC globale suggère aussi des échelles de probabilité
différentes entre modèles ; il ne faut pas sélectionner rétrospectivement les
« bons » symboles de 2026.

En 2026H1, TTD affiche 123 événements Oracle servables, P(LONG) moyenne 0,770,
24,39 % de rendements positifs et AUC 0,458 sur ce critère. Cette faiblesse
n'est pas limitée au seul mois de janvier.

Certains scores sont presque constants dans les lignes conservées :

- PENN : 0,331023–0,331025 sur 87 observations ;
- ROKU : 0,543148–0,543152 sur 56 observations ;
- GH : 0,329111–0,329114 sur 123 observations.

Cela constitue une **réserve à auditer**, pas un défaut applicatif démontré.
Causes possibles à distinguer : modèle intrinsèquement peu discriminant,
calibration comprimant les scores, features de serving peu variables ou
fallback. Les AUC calculées sur des variations de quelques millionièmes doivent
être interprétées avec prudence. Les artefacts originaux absents limitent la
vérification de ces causes sur cet ancien batch.

## Conclusion et prochaine action

Pas de nouveau seuil LONG, blacklist ou cooldown intégré à la production.
La suite la plus utile serait une vérification de la chaîne **features → modèle
sélectionné → sortie brute → calibration → probabilité persistée**, sur un batch
dont les artefacts sont disponibles, avec traçabilité et sans réentraînement.
Cette vérification serait une tâche distincte à autoriser. Elle ne démontrera
pas rétrospectivement la cause sur l'ancien batch si ses artefacts restent absents.

Le net économique et l'impact réel d'une limite de concentration restent à
examiner avec des journaux de portefeuille ou un nouveau rejeu séparé.

## Fichiers et tests

Script : `scripts/research/us_original_repetition_reliability_audit.py`.
Sortie de référence :
`artifacts/research/us_common_degradation/repetition-reliability-20261005-v2/`.
La v1 demeure archivée ; la v2 ajoute min/max/écart-type des probabilités par titre.

- `report.json` : résultats par fenêtre, mois et tranche ;
- `selected_episode_flags.parquet` : indicateurs d'épisode et de délai ;
- `episodes.csv` : dates et rendements du début de chaque épisode ;
- `symbol_reliability.csv` : distribution des scores et mesures par titre/année ;
- `protocol.json` : règles figées et limites.

Cinq tests nouveaux vérifient les ruptures d'épisodes, le délai de calendrier,
l'absence de remise à zéro annuelle, le rejet des doublons, le cash résiduel et
les tranches de probabilité. Les dix tests ciblés des trois audits passent.

Suite réalisée : [diagnostic technique des scores constants](us_bundle_probabilites_constantes_diagnostic.md).
Les trois LONG sont CatBoost/vector sur 501 dates. Artefacts absents des quatre
sauvegardes ; cause historique non prouvée. Un défaut distinct de température
non positive et d'incohérence fit/predict a été reproduit puis corrigé après GO.
89 tests ciblés passent ; l'aplatissement historique reste de cause non certifiée.
