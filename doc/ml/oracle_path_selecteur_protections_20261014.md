# Sélecteur des trois profils — protocole d'apprentissage et comparaison

## GO — 14 octobre 2026

Entraîner un petit sélecteur, puis comparer les trois protections fixes avec
les modèles annuels fournis. **Recherche isolée** : aucun changement du live,
du champion Oracle, des batchs, de SQL ou ordre courtier. Aucun réentraînement
des trois Oracles annuels. Capital initial4 000USD par année/cas, LONG TOP5,
pas de renforcement d'un titre déjà détenu, plafond d'entrée levier×2.

## Contrat figé avant le fit

Dataset `us_oracle_path_protection_dataset/20261014-v1`, vérifié.24 features
autorisées à J, pas de symbole/année/score Oracle brut, ni prix/gap J+1 ou résultat
futur en entrée. Développement2018–2021 :3342 lignes, disponibilité des labels
avant2022 ; validation2022 :752 lignes, disponibilité avant2023 ; contrôle2023
partiel :557 lignes.209/65/39 observations non chevauchantes seulement : réserve
de dépendance et de puissance statistique, pas3342 trades indépendants.

Deux petits régresseurs **LightGBM CPU**, pour prédire les avantages unitaires
nets COURT−REFERENCE et LARGE−REFERENCE, en **points de rendement**, pas des
probabilités/confidences de réussite. Paramètres uniques : objectifL2, profondeur2,
4 feuilles, minimum150 lignes/feuille, learning rate0,03, L1=0,1, L2=10,
150 itérations maximum, early stopping15 sur2022 seulement, seed731,2 threads,
aucun sous-échantillonnage. Chaque date a le même poids total, normalisé pour
une moyenne de poids1 ; pas de recherche d'hyperparamètres ni de refit2023.

Décision à J : REFERENCE a avantage0 ; choisir le plus grand avantage prédit,
avec égalité à1e-10 près dans l'ordre REFERENCE puis COURT puis LARGE.
Si aucun avantage strictement positif, REFERENCE. Pas de marge optimisée,
pas de filtre qui supprime l'entrée selon le gain prédit. Une feature à J non
qualifiée bloque cette nouvelle entrée **dans les quatre bras**, pas seulement
le sélecteur ; ce contrôle ne peut pas fermer/supprimer une position existante.

| Profil | SL | Trailing | TP |
| --- | ---: | ---: | ---: |
| COURT | 5 % | 10 % | 10 % |
| REFERENCE | 5 % | 15 % | 20 % |
| LARGE | 5 % | 20 % | 30 % |

Choix conservé pour toute la position, barrières ancrées au fill J+1. Trailing
effectif à la séance suivante, sommet antérieur seulement, jamais desserrage
du SL dur initial. Pas de mise à jour quotidienne des pourcentages. Le label
d'apprentissage est borné60 séances et peut être MTM ; le portefeuille n'a
**pas de sortie forcée à60 ou H20**, ni de liquidation terminale artificielle.
Cette différence label/détention illimitée reste une réserve explicite.

## Contrôles unitaires avant portefeuille

Le profil constant de comparaison est sélectionné **uniquement sur le rendement
unitaire moyen de validation2022**, égalité préférenceREFERENCE. Le choix est
gelé dans `fit.json` avant le calcul2023 et tout score/portefeuille2024–2026.
Comparaison unitaire du sélecteur et des trois constants sur validation et2023,
plus comptage des profils.2023 n'est pas utilisé pour régler le sélecteur.
Une association unitaire ne suffit pas à promouvoir un gain économique.

## Modèles annuels et nouveaux TOP5

| Test | Oracle | Fold autorisé |
| --- | --- | --- |
| 2024 | `model-factory-20261014113215-437ed1` | 2023-12-05 |
| 2025 | `model-factory-20261014113226-102eca` | 2024-12-05 |
| 2026 jusqu'au30septembre | `model-factory-20261014113232-bc35a7` | 2025-12-10 |

Recalcul des scores avec **ces** poids, mêmes173 features/générateur et univers
1 790, cache observable original avant qualité future, rangs XS sur tout le pool.
TOP5 figé par score décroissant, symbole croissant. Pas de relecture du TOP des
modèles supprimés comme si c'étaient ces nouveaux poids. X du sélecteur est
recalculé à J sur les prix locaux corrigés et SPY, préfixes vérifiés, mêmes24
colonnes que le fit. Pas de lecture des résultats futurs pour choisir les profils.
Historique121 barres/identité à J et201 closes benchmark requis, sans imputation.
Les secteurs actuels sont acceptés seulement par le risque natif, pas feature ML.

## Douze portefeuilles appariés

Pour chaque année : FIXED_COURT, FIXED_REFERENCE, FIXED_LARGE, LEARNED.
Mêmes scores, admissions à J, risque, calendrier, prix, coûts et levier.
Le constant choisi sur validation est l'un des trois témoins, pas un cinquième
cas ajusté sur les pertes. Les portfolios ont leurs propres positions/capital :
les dates de sortie et réinvestissements peuvent diverger légitimement.

Ledger natif partagé, frais canoniques et impact natif, intérêts sur débitEOD
6,5 % ACT/360, maintenances génériques, marge/secteur/circuit/régime conservés.
Pas de réduction progressive supplémentaire d'exposition ; le risque natif peut
réduire l'allocation. Ordre contraint au fill : rejet entier, pas resize caché.
Gaps de stop pouvant dépasser5 %. Opérations sur titres en modeSTRICT : une
preuve de cash manquante ou un prix/volume détenu inconnu fait échouer le cas,
ne supprime pas rétrospectivement un perdant. Equity finale avec positions MTM.

Rapports : rendement, capital final, gains/pertes réalisés, latent, intérêts,
taux gagnant des positions closes, DD max, levier moyen/max, profils décidés/
tentés/exécutés et vérification SL/TP/trailing, dates et cash. Réserves héritées :
univers actuel de survivants, secteur nonPIT, historiques ajustés actuels,
dividendes incomplets, macro/régime natif à vintages non certifiés, marge et
spreads/fills simulés. Les résultats ne certifient pas une parité brokerLIVE.

## Verdict et arrêt

Seuil de promotion **exploratoire** figé : douze cas complets, aucun échec/
cash inconnu, LEARNED supérieur en rendement aux trois constants dans chaque
période, et DD pas plus mauvais que REFERENCE et le constant choisi sur2022
dans chaque période. Sinon `NO_GO_STABLE_PERSONALIZATION` ; un échec technique
donne `PARTIAL_FAILED`, sans conclure financièrement sur le cas échoué.
Même un gate passé n'est pas une promotionLIVE :2024–2026 déjà observées,
confirmation prospective nécessaire. Aucun ajout de profils, seuil, autre
modèle ou nouvelle expérience après lecture des pertes dans ce GO.

Artefacts dédiés :
`artifacts/research/us_oracle_path_protection_selector/20261014-v1`.
Protocole/empreintes avant fit, modèles auxiliaires et données de décision
archivés, reprise par phase/cas avec verrou exclusif. `progress.json` global
et un `progress.json` dans chaque portefeuille. Aucun écrasement des recherches
précédentes.

## Résultats terminés — NO_GO_STABLE_PERSONALIZATION

**Douze cas complets, zéro échec.** Sources, poids, décisions et artefacts
revérifiés. Les scores ont bien été recalculés avec les trois nouveaux modèles
fournis, et non relus depuis les sélections des modèles supprimés. Les profils
fixes et le sélecteur utilisent exactement les mêmes nouvelles admissions à J.

### Ce que le sélecteur a effectivement appris

Early stopping : COURT5 itérations, LARGE1. Ce n'est pas un nouvel Oracle
directionnel et il ne retourne aucune probabilité de gain. Sur les décisions
annuelles qualifiées : avantage COURT entre−1,053 et−0,728 points ; avantage
LARGE entre+0,290 et+0,412 points, REFERENCE0. Selon la règle figée, il choisit
donc **LARGE sur toutes les observations**, malgré de petites variations des
sorties numériques. Pas de bug de tri/choix détecté : les deux régressions ne
séparent pas utilement les situations pour sélectionner un profil différent.

Validation2022 :752/752 LARGE ; rendement unitaire moyen−1,425 %, contre−0,299 %
COURT,−0,828 % REFERENCE. Le constant sélectionné sur2022 estCOURT et reste
gelé pour les tests. Contrôle2023 :557/557 LARGE, moyenne+3,281 %, contre+1,022 %
COURT/+2,573 % REFERENCE. Son avantage2023 est donc celui d'un profil constant,
**pas une preuve de personnalisation**. Aucun paramètre n'a été changé après
ces chiffres ; les douze replays autorisés ont été exécutés tels quels.

### Comparaison économique réelle du portefeuille simulé

Capital initial4 000USD réinitialisé par année, frais/financement et risque natifs,
pas de vente forcée H20 ; capital final inclut les positions encore ouvertes.
2026 =2 janvier…30 septembre, pas année complète.

| Année | COURT fixe | REFERENCE fixe | LARGE fixe | Sélecteur appris |
| --- | ---: | ---: | ---: | ---: |
| 2024 | −23,10 % | **−16,74 %** | −33,96 % | −33,96 % |
| 2025 | +7,01 % | **+33,12 %** | +20,71 % | +20,71 % |
| 2026 partiel | −9,37 % | **+36,14 %** | −10,73 % | −10,73 % |

Le sélecteur sous-performe REFERENCE de17,22 /12,41 /46,88 points selon la période.
Il ne bat le constant choisi sur validationCOURT qu'en2025. **Aucun avantage
stable à promouvoir**, ni raison d'ajouter des profils plus fins à partir de ce
seul résultat. REFERENCE domine ces trois périodes observées, sans en faire une
stratégie gagnante partout :2024 reste perdante et les drawdowns restent importants.

| Année | DD COURT | DD REFERENCE | DD LARGE/sélecteur |
| --- | ---: | ---: | ---: |
| 2024 | −29,98 % | −32,83 % | −40,90 % |
| 2025 | −22,65 % | −21,79 % | −24,11 % |
| 2026 partiel | −30,27 % | −26,19 % | −39,84 % |

### Détails financiers et trades clos

Gains/pertes sont les sommes des PnL **réalisés** positifs/négatifs avec frais
de trade natifs ; les intérêts sont séparés. Le latent des positions ouvertes
et les intérêts expliquent l'écart avec le capital final. Les pourcentages de
gagnants portent uniquement sur les positions closes.

| Année | Profil | Capital final USD | Gains réalisés USD | Pertes réalisées USD | Clos | Gagnants % | Latent USD | Intérêts USD |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 | COURT | 3 075,87 | 4 564,67 | −5 451,28 | 172 | 30,23 | −21,07 | 16,45 |
| 2024 | REFERENCE | 3 330,30 | 5 807,60 | −6 385,68 | 151 | 20,53 | −22,81 | 68,81 |
| 2024 | LARGE/appris | 2 641,46 | 3 034,20 | −4 407,23 | 127 | 15,75 | +90,15 | 75,66 |
| 2025 | COURT | 4 280,36 | 5 597,61 | −5 278,76 | 167 | 37,72 | −28,48 | 10,01 |
| 2025 | REFERENCE | 5 324,92 | 7 758,26 | −6 480,69 | 140 | 29,29 | +118,24 | 70,89 |
| 2025 | LARGE/appris | 4 828,46 | 6 215,56 | −5 583,67 | 116 | 24,14 | +284,39 | 87,82 |
| 2026 | COURT | 3 625,30 | 5 204,96 | −5 578,55 | 145 | 31,03 | +12,45 | 13,56 |
| 2026 | REFERENCE | 5 445,76 | 6 399,92 | −5 142,77 | 146 | 26,71 | +205,56 | 16,95 |
| 2026 | LARGE/appris | 3 570,67 | 2 857,94 | −3 472,12 | 91 | 14,29 | +201,41 | 16,56 |

### Vérifications et limite de conclusion

**56 tests ciblés réussis** : sélecteur, dataset, diagnostic et protections
dynamiques. Les avertissements pandas de concaténation sont conservés, pas des
échecs de cas ni de tests.

La revue `completion-audit.json` reproduit les prédictions à partir des deux
poids LightGBM et des24 features annuelles. Décisions :1 260/1 250/933 profils
LARGE (2024/2025/2026), deux candidats2026 non qualifiés à J bloqués dans tous
les bras, aucun remplacement par des rangs suivants. Lots effectivement ouverts
pour le sélecteur :130/121/94 ; clos127/116/91, restants3/5/3. Les décisions et
tentatives ne sont pas présentées comme des fills réels.

Les **trades et courbes quotidiennes sont exactement identiques** entre LEARNED
et FIXED_LARGE sur les trois années. SL5, TP/trailing par lot, chronologie J/fill,
lots clos, coûts, equity/DD et réconciliation du cash vérifiés. Les témoins fixes
ont une parité native exacte dans les fixtures, ainsi que LEARNED=REFERENCE
lorsqu'on impose ce choix. Un test de fit prouve que modifier les labels du
contrôle2023 ne change pas les poids appris. Aucun Oracle n'a été réentraîné.

Conclusion bornée : le **plafond rétrospectif** du diagnostic existait, mais ce
petit modèle et ces variables n'arrivent pas à l'exploiter. Cela n'est pas une
preuve universelle d'impossibilité ; cette expérience ne justifie toutefois
ni intégration live, ni nouveaux seuils/profils optimisés sur ces pertes.
Les réserves de données/portefeuille du protocole restent inchangées.

Résultats : `artifacts/research/us_oracle_path_protection_selector/20261014-v1/report.json`,
`annual-summary.csv`, `selector/fit.json`, `selector/unit-comparison.json` et les
sous-dossiers des douze portefeuilles. Plus aucun run en cours pour cette expérience.
