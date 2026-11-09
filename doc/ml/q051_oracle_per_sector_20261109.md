# Oracle H10 + LONG per-sector — Q051 et volatilité 20 % + régime

GO utilisateur du 9 novembre 2026, avec confirmation que « Q055 » désignait
**Q051**, puis ajout du profil de risque actuellement choisi par défaut.

## Comparaison figée

Période continue **01/01/2021–31/12/2025**, capital initial **4 000 USD**,
aucune remise à zéro annuelle. Les cinq Oracles annuels déjà utilisés par
Q051 sont conservés strictement à l’identique pour isoler le nouveau filtre.
Les entraîner de nouveau changerait simultanément le classement d’amplitude.
Chaque ensemble annuel de recherche référence son Oracle original vérifié et
ses nouveaux modèles LONG sectoriels ; aucun batch existant n’est modifié.

| Année testée | Oracle annuel | Fenêtre originale de données |
|---|---|---|
| 2021 | model-factory-20261107222539-837309 | 2014–2020 |
| 2022 | model-factory-20261107222557-280d86 | 2015–2021 |
| 2023 | model-factory-20261107222607-f44095 | 2016–2022 |
| 2024 | model-factory-20261107222618-89a4d2 | 2017–2023 |
| 2025 | model-factory-20261106203103-91b063 | 2018–2024 |

Le per-sector historique de l’application utilise notamment une synthèse depuis
le rang global : ce n’est pas le score LONG qui est évalué ici. Cette expérience
entraîne **un véritable LightGBM LONG par secteur GICS**, appliqué aux features
propres de chaque titre de ce secteur. Les titres d’un même secteur n’obtiennent
donc pas tous un score identique. L’identifiant du titre n’est pas une feature.

Deux protections de portefeuille, chacune comparée sur trois sélections :

| Profil | Sans filtre directionnel | Per-symbol existant | Nouveau per-sector |
|---|---|---|---|
| Q051 | TOP10 % Oracle en ordre d’amplitude | TOP5 LONG | TOP5 LONG |
| Q051 + volatilité 20 % + régime | Même témoin avec protection | Même sélection avec protection | Nouvelle sélection avec protection |

Les témoins existants sont tronqués au 31 décembre 2025, sans inventer une
liquidation finale. Les nouveaux replays s’arrêtent à cette même date, en
valorisant aussi les positions encore détenues. La sélection transmet les
TOP5 puis applique score **strictement >0,50** et **AUC ≥0,50**, sans remplacer
les refus. Le pool Oracle reste 179 titres sur l’univers figé de 1 790.

## Cible, apprentissage et calibration

Mêmes 24 features techniques/marché que le bundle LONG per-symbol et mêmes
labels : gain net après frais, SL5 % ou sortie open11. Ni nouveau signal
macro, ni consensus/options, ni recherche de meilleurs seuils/poids.

LightGBM 120 arbres, profondeur 3, sept feuilles, learning rate 0,03,
min_child_samples 60, régularisations 1/10, seed 42. Imputation et bornes
1–99 % ajustées sur le train uniquement ; calibration Platt sur l’année
précédente. Données de train avant cette année de calibration, **labels déjà
connus avant chaque frontière**. Les observations de l’année testée ne servent
ni au fit, ni à la calibration, ni au choix d’un seuil.

L’AUC utilisée pour le seuil est **celle du titre sur la calibration du modèle
sectoriel**, pas l’AUC future du titre ni seulement l’AUC agrégée du secteur.
Minimum 126 observations de calibration et 15 par classe pour ce titre ;
sinon son AUC est absente et il ne passe pas le filtre. L’AUC sectorielle
agrégée est conservée comme diagnostic distinct.

Les modèles annuels per-symbol d’origine gèrent le signal du dernier jour de
l’année précédente avec le millésime correspondant à l’année du signal.
Pour reproduire cette frontière, chaque ensemble sectoriel annuel prépare
le millésime testé **et celui de l’année précédente** à partir du même
contexte de données, toujours avec une disponibilité strictement antérieure
au signal. Les modèles de l’année précédente ne peuvent lire aucun label futur.

Les sous-ensembles train/calibration recalculés sont rapprochés des effectifs
per-symbol archivés lorsqu’un modèle original existe, avant mutualisation.
Les nouveaux poids, probabilités, AUC, sélections, dates de disponibilité et
empreintes restent dans des fichiers de recherche dédiés, sans écriture SQL.

## Risque et exécution simulée

Position complète, entrée à l’ouverture J+1 sans confirmation, SL5 %, sans
TP, trailing ou renforcement, sortie open11. Risque 1,25 % par entrée, poids
maximal 20 %, 20 positions, minimum 50 USD, plafond d’achat **1×** ; compte
margin de capacité 2×. B4/DD15, facteurs, corrélation et limites sectorielles
désactivés. Frais 8 pb par opération et financement annuel 6,5 %.

Le second profil ajoute uniquement le budget de volatilité annualisée du
portefeuille **20 %**, covariance des **60 séances antérieures**, et le filtre
des nouvelles entrées **SPY à J >98 % de sa SMA200**. La quantité native peut
seulement diminuer ; pas de liquidation des détenus par ces deux règles.

Le module de risque natif et Winner sont réutilisés, sans changement du moteur.
Les données quotidiennes et 5m déjà figées dans les comparaisons précédentes
sont réutilisées. Aucun téléchargement, appel LLM, ordre ou compte réel.

## Couverture et limites

Classification sectorielle actuelle figée : **1 788/1 790 titres** répartis
sur 11 groupes. Transport est rangé dans Industrials ; BAR et PHYS restent
sans secteur utilisable, sans score de secours. Ce référentiel courant n’est
pas une reconstitution certifiée des secteurs historiques.

Le bundle de novembre 6 utilisé pour 2025 n’avait pas archivé son benchmark.
Il est reconstitué pour ce nouvel entraînement depuis les benchmarks stockés
des bundles 2024/2026 : leurs **1 258 dates communes ont des OHLC et volumes
identiques**, union de lignes complètes puis restriction à 2018–2024. Aucun
cours n’est inventé. Les autres années conservent leur benchmark original.

Deux préparations antérieures sont conservées : v1 arrêtée sur ce benchmark
absent ; v2 protocole sans entraînement, remplacé par v3 pour classer les
49 titres Transportation. Les **110 modèles sectoriels** ont été entraînés
dans v3 (11 secteurs × deux millésimes × cinq ensembles annuels), sans saut
de modèle. Les 15 212 rapprochements d’effectifs train/calibration avec les
modèles per-symbol ont passé.

### Reprise des prédictions, v4

La première campagne v3 s’est arrêtée avant les backtests : seules les
prédictions 2021 étaient terminées, les quatre autres échouaient sur `date`.
La cause est l’index conservé sur le benchmark après restriction à la fenêtre
d’inférence ; le constructeur de features réinitialise les prix mais aligne
encore les dates sur cet ancien index. Cela décalait les features SPY ou
supprimait les dates de l’année testée. Les prédictions 2021 étaient elles
aussi potentiellement affectées et ne sont pas réutilisées.

La reprise **v4** normalise l’index du benchmark dans le seul processus de
recherche, avant le constructeur de features inchangé. Elle recalcule les
cinq années de prédictions. Les 110 poids, leurs AUC de calibration et les
Oracles sont réutilisés après contrôle de leurs empreintes, sans réentraînement
ni modification de production. Les benchmarks d’entraînement, relus depuis
Parquet avec index normalisé, n’étaient pas affectés.

Un test supplémentaire vérifie l’identité des features avec un benchmark
réindexé, la présence de plus de 200 séances de 2022 et le rendement SPY cinq
séances calculé directement depuis les cours. **Quatre tests passent.**
Les archives v3 et ses prédictions défaillantes restent conservées séparément.

Tests : mapping sectoriel, reconstruction sans divergence de benchmark,
purge temporelle et invariance de l’entraînement à une modification des
observations de l’année future testée. Trois tests passent.

Les taux gagnants porteront sur les trades clôturés après frais. Ils ne sont
pas l’AUC du modèle. Les capitaux et états du risque restent continus entre
années. Les témoins ont une couverture intraday partielle avec secours daily ;
ces limites et le biais de survivance du fichier courant restent explicites.
Aucun résultat financier sectoriel n’est déclaré au lancement.

## Exécution et suivi

Script initial : `scripts/research/us_q051_per_sector_20261109.py`.
Reprise active : `scripts/research/us_q051_per_sector_recovery_20261109.py`.

Racine active : `artifacts/research/us_q051_per_sector/20261109-v4/`.
Poids entraînés réutilisés depuis `20261109-v3`, manifestes et empreintes copiés
avec reçu explicite `verified-model-reuse.json` dans v4.

- `request.json` : protocole, modèles Oracle, paramètres, sources et classification.
- `progress.json` et `years/<année>/progress.json` : phases et compteurs.
- `years/<année>/manifest.json` : nouveaux modèles par secteur et disponibilité.
- `years/<année>/calibration-by-symbol.parquet` : AUC passées par titre.
- `years/<année>/ranking.parquet`, `signals.parquet` : prédictions et sélection.
- `cases/Q051_PER_SECTOR/result/` et `cases/VOL20_REGIME_PER_SECTOR/result/` : replays.
- À la fin : `comparison.csv`, `annual-comparison.csv`, `report.json` et imports
  des deux replays dans l’historique IHM.

Deux ensembles annuels s’exécutent simultanément ; les deux replays sont
enchaînés uniquement après réussite des cinq préparations/entraînements/prédictions.
Une erreur est publiée avec sa cause ; aucun résultat de remplacement n’est inventé.

## Bilan terminal vérifié — 2021–2025

**TERMINÉ : cinq prédictions annuelles corrigées et deux replays sectoriels terminés, sans échec lors de la reprise v4. Les deux replays sont importés dans l’historique IHM.**

Le périmètre s’arrête au **31/12/2025**. Il ne faut pas comparer directement ses rendements aux +206,51 % du témoin Q051 allant jusqu’au 01/10/2026.

| Variante | Capital final USD | Rendement cumulé | DD maximal intraday | Gagnants / clôturés | Taux gagnant | Capital engagé moyen USD |
|---|---:|---:|---:|---:|---:|---:|
| Q051 sans filtre | 6051,82 | 51,30 % | -74,62 % | 419/1598 | 26,22 % | 4306,21 |
| Q051 per-symbol | 8788,86 | 119,72 % | -36,89 % | 361/1046 | 34,51 % | 4800,14 |
| Q051 per-sector | 3046,44 | -23,84 % | -51,79 % | 124/395 | 31,39 % | 1002,66 |
| Volatilité/régime sans filtre | 3666,91 | -8,33 % | -43,39 % | 630/1987 | 31,71 % | 1658,51 |
| Volatilité/régime per-symbol | 6401,27 | 60,03 % | -24,29 % | 279/784 | 35,59 % | 2189,74 |
| Volatilité/régime per-sector | 3285,19 | -17,87 % | -37,12 % | 85/270 | 31,48 % | 597,70 |

Le per-sector améliore le taux gagnant brut de Q051 sans filtre (+5,17 points), mais reste moins bon que per-symbol (−3,12 points). Le rendement devient négatif et le capital utilisé est faible. Avec protection vol/régime, il n’améliore même pas le taux gagnant sans filtre (31,48 % contre 31,71 %) et reste derrière per-symbol (35,59 %). Aucune promotion du per-sector sur cet essai.

### Taux gagnants annuels — Q051

| Année de clôture | Sans filtre | Per-symbol | Per-sector | Gagnants/clôturés per-sector |
|---|---:|---:|---:|---:|
| 2021 | 22,91 % | 33,00 % | 16,67 % | 6/36 |
| 2022 | 18,84 % | 28,16 % | 19,78 % | 18/91 |
| 2023 | 34,44 % | 40,35 % | 83,33 % | 5/6 |
| 2024 | 25,59 % | 36,21 % | 32,61 % | 45/138 |
| 2025 | 32,05 % | 35,44 % | 40,32 % | 50/124 |

### Taux gagnants annuels — protection vol.20 % + régime

| Année de clôture | Sans filtre | Per-symbol | Per-sector | Gagnants/clôturés per-sector |
|---|---:|---:|---:|---:|
| 2021 | 25,55 % | 28,57 % | 20,00 % | 6/30 |
| 2022 | 21,50 % | 40,82 % | 4,55 % | 1/22 |
| 2023 | 37,06 % | 40,69 % | — | 0/0 |
| 2024 | 32,11 % | 38,64 % | 31,15 % | 38/122 |
| 2025 | 34,66 % | 33,33 % | 41,67 % | 40/96 |

**2023 : le taux de 83,33 % n’est pas une performance robuste du modèle sectoriel 2023.** Il provient de six sorties : cinq titres achetés en décembre 2022 et HCI acheté le 3 janvier sur un signal du 30 décembre 2022. Le millésime sectoriel 2023 n’a retenu aucun nouveau signal daté de 2023 au seuil >0,50. Le profil protégé n’a eu aucun trade en 2023 (taux absent, pas 0 % de gagnants).

Les nombres de signaux retenus dans les cinq ensembles annuels sont **120 / 315 / 3 / 810 / 449** (2021–2025). Les trois du bundle 2023 sont précisément ceux du signal du 30/12/2022. Le filtre sectoriel s’abstient donc presque totalement pendant 2023 ; il ne faut pas comparer les taux sans tenir compte du nombre et de la répartition des trades.

### Rendements annuels des deux nouvelles variantes

| Année | Q051 per-sector | Vol.20 % + régime per-sector |
|---|---:|---:|
| 2021 | 1,03 % | 9,10 % |
| 2022 | -24,10 % | -15,66 % |
| 2023 | 10,73 % | 0,00 % |
| 2024 | -16,93 % | -14,51 % |
| 2025 | 7,98 % | 4,42 % |

### Vérifications terminales

- `validation.json` : **PASS**, 110 empreintes/dates des modèles vérifiées, 1 697 décisions retenues recontrôlées avec le sélecteur de production, dix recomptages annuels des nouveaux trades sans écart.
- Configuration de portefeuille Q051 strictement égale au témoin, sauf date de fin ramenée au 31 décembre 2025 ; la variante protégée utilise les mêmes protections de volatilité/régime.
- Taux gagnants calculés par année de sortie réelle, après frais ; les positions non clôturées restent valorisées dans le capital. Risque, capital et positions continus sans reset annuel.
- Les deux rapports natifs portent `INCOMPLETE_COVERAGE` avec secours OHLC daily : campagne terminée techniquement ne signifie pas couverture intraday complète ou parité live.
- Même assistant, pas de revue humaine indépendante. Aucun ordre, fournisseur, écriture SQL ou changement de production.

Imports IHM : `20261109_q051_q051_per_sector_v1` et `20261109_q051_vol20_regime_per_sector_v1`.

**Conclusion : garder per-symbol comme référence sur cet essai. La variante sectorielle telle que testée ne fournit pas un meilleur compromis, même si son taux gagnant dépasse le Q051 brut. Cela ne rejette pas toute architecture sectorielle possible ; aucune nouvelle variante n’a été optimisée après observation de ces résultats.**

## Chevauchement des filtres : OU / ET, sans nouveau replay

Comptage sur les 1 255 dates de signal associées aux entrées 2021–2025,
après TOP5 LONG et seuils propres à chaque modèle. Même pool TOP179 Oracle.
Les risques et le capital n’ont pas été rejoués pour les combinaisons.

| Liste quotidienne | Moyenne de candidats | Maximum théorique | Maximum observé |
|---|---:|---:|---:|
| Per-symbol | 4,11 | 5 | 5 |
| Per-sector | 1,35 | 5 | 5 |
| OU, union dédupliquée | 5,42 | 10 | 10 |
| ET, accord des deux listes | 0,049 | 5 | 1 |

Il y a **61 accords titre/date**, sur 61 dates différentes (4,86 % des dates),
portant sur 16 titres distincts. L’union compte 6 797 signaux titre/date
et 342 titres distincts sur toute la période. Les nombres quotidiens ne sont
pas les nombres d’achats : les positions détenues et contrôles du risque restent
à appliquer. Les 5 161 signaux per-symbol et 1 697 per-sector ne sont donc pas
6 858 achats ; les 61 doublons doivent être dédupliqués.

| Année d’entrée associée | Per-symbol moyen | Per-sector moyen | OU moyen | ET moyen | Dates avec accord |
|---|---:|---:|---:|---:|---:|
| 2021 | 3,60 | 0,48 | 4,02 | 0,052 | 13 |
| 2022 | 4,64 | 1,25 | 5,88 | 0,016 | 4 |
| 2023 | 3,07 | 0,01 | 3,08 | 0,004 | 1 |
| 2024 | 4,87 | 3,21 | 7,96 | 0,123 | 31 |
| 2025 | 4,38 | 1,80 | 6,13 | 0,048 | 12 |

Le ET strict serait très peu actif. Le OU augmente les candidatures, mais peut
ajouter des entrées sectorielles défavorables et occuper du capital autrement
alloué au per-symbol ; aucune amélioration économique n’est démontrée par ces
comptages. Un éventuel replay doit figer l’ordre : priorité per-symbol, puis
ajouts per-sector en leur ordre propre, sans addition ni moyenne opportuniste
des probabilités. Aucun replay OU/ET n’a été lancé par ce diagnostic.

Fichiers : `filter-overlap/daily-counts.csv`, `summary.json`, `provenance.json`
sous la racine v4. Seuls des fichiers existants ont été lus, sans SQL ni modèles.
