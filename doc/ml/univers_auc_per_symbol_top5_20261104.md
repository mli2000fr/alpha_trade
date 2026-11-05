# Oracle TOP20 → classement LONG per-symbol → TOP5 achats

**Terminé le4novembre2026 :72simulations vérifiées.** Correction demandée
après constat que les deux campagnes précédentes achetaient les TOP5 du score
d'amplitude Oracle, sans tri LONG quotidien. L'utilisateur a confirmé le vivier :
**TOP20 Oracle, puis TOP5 du score LONG per-symbol**.

## Sélection quotidienne réellement exécutée

Sur chacun des univers fixes de32titres H10 et37titres H20 :

1. Reprendre les scores des six Oracles annuels dédiés déjà entraînés.
2. Figer les20premiers du score d'amplitude, avant tout score directionnel.
3. Pour chacun de ces20titres, lire la probabilité LONG de son propre modèle
   de l'année, calibrée sur son année précédente.
4. Retenir les cinq probabilités les plus élevées ; égalité : rang Oracle,
   puis symbole. Priorité d'exécution selon ce rang LONG.
5. Acheter uniquement ces cinq candidats LONG sous réserve de données, cash,
   sizing et absence de détention ; pas de remplacement depuis le rang6LONG
   ni le rang21Oracle. Pas de seuil supplémentaire de probabilité imposé.

Les AUC historiques ne remplacent **pas** le score quotidien. Elles ont servi
à définir les fichiers d'univers, comme auparavant. Les colonnes de preuve
sont `oracle_amplitude_rank`, `oracle_amplitude_score`, `long_probability`,
`long_rank`, année du modèle et empreinte des poids.

Dans les CSV compatibles avec les replays existants, `oracle_rank` est le
champ technique de priorité d'exécution : il reçoit ici **long_rank**. Le vrai
rang d'amplitude original est conservé séparément dans `oracle_amplitude_rank`.

## Modèles annuels et causalité

**207 modèles per-symbol annuels existants, vérifiés et réutilisés**, sans
nouvel entraînement :69couples cible/titre ×3années2024/25/26. Le symboleWHF
présent dans les deux listes a des modèles différents selon la cible.
Même schéma que l'audit d'origine : fit avantY−1, calibration surY−1, dates
de disponibilité de tous les labels strictement antérieures à chaque frontière.
Ni modèle2023 conservé en2026 ni calibration sur l'année testée.

LightGBM propre à chaque titre,24features prix/tendance/volatilité/volume/SPY,
bornes de winsorisation et imputation apprises au fit, calibration Platt de
l'année précédente. Les poids sont chargés après vérification SHA256.

Les caches d'origine ne contenaient des prédictions que pour les fenêtres
arrivées à maturité. Ils ne pouvaient donc pas servir directement de filtre
de trading quotidien. Les modèles ont été réappliqués aux features disponibles
de **toutes les dates de décision**, sans exiger de label futur.47 555scores
recalculés ; **46 088prédictions anciennes sur les dates communes reproduites
à1e−12 près**. Les dernières dates sans résultat futur restent scorables.

Les cibles LONG sont celles de l'audit des deux fichiers :

- **H10** : achat next open, SL5 %, sans TP/trailing, sortie open11 ; résultat
  net positif après frais.
- **H20** : pic haussier supérieur en amplitude au pic baissier absolu durant
  vingt séances depuis l'ouverture suivante. **Ce n'est pas une probabilité
  de trade rentable avec SL5 %.** Les deux scores ne sont pas interchangeables.

La sélection change réellement :3 357/3 510couples quotidiens H10 et
2 605/3 510H20 diffèrent des TOP5 Oracle seuls.28titres H10 et30H20 sont
sélectionnés au moins une fois,57symboles distincts au total.
Rang Oracle moyen retenu :14,70H10 /10,54H20 ; probabilité LONG médiane
0,5380/0,6780. Le filtre peut donc retenir des candidats moins extrêmes dans
le vivier20. Ces descriptifs ne sont pas des taux gagnants ni une preuve causale.

## Conditions de simulation conservées

4 000USD, sans levier, LONG uniquement, entiers,20positions maximum,
20 % maximum par position, budget1,25 % du capital courant,50USD minimum.
Frais estimés8bps à l'achat et8bps à la vente. SL5 %, aucun TP/trailing,
sortie open11 pour H10 etopen21 pour H20. Aucun renforcement ni rachat d'une
position détenue. Positions finales valorisées, sans liquidation de fin forcée.

Années2024 et2025 complètes,2026 jusqu'au **19octobre** ; trois comptes annuels
indépendants et un compte continu sans remise à zéro. Les résultats de ces
comptes annuels ne se multiplient pas pour reproduire le compte continu,
notamment en raison des positions à cheval sur les années et du sizing entier.

Le daily reprend exactement la fonction financière de l'audit initial. Les
variantes intraday reprennent l'adaptateur de confirmation/DD15 inchangé :
cassure du high de la veille puis deux closes5m, délai930s, un IOC au prochain
open observé plafonné à+1 %. Une opportunité à la séance suivante, pas de plans
anciens attendant20séances. DD15 : liquidation de50 % du nombre de positions,
en commençant par les moins-values latentes, puis reprise nativeB4 ; pas un
plafond garanti de15 %. Pas de contraintes supplémentaires de facteurs,
secteur ou corrélation introduites dans ce comparatif de recherche.

## Daily — comparaison directe avec les résultats initiaux

Même moteur daily, mêmes prix archivés, mêmes règles financières. **Seule la
sélection change.** Chaque année repart de4 000USD, sans confirmation ni DD15.

| Univers | Année | TOP5 Oracle : rendement | TOP5 LONG per-symbol : rendement | DD max per-symbol | Trades clos | Gagnants per-symbol |
|---|---|---:|---:|---:|---:|---:|
| H10 | 2024 | +9,81 % | **+27,33 %** | −14,49 % | 200 | 43,00 % |
| H10 | 2025 | −28,47 % | **+33,62 %** | −9,81 % | 182 | 56,59 % |
| H10 | 2026 au19/10 | +8,59 % | **+14,11 %** | −12,49 % | 151 | 48,34 % |
| H20 | 2024 | +62,01 % | +15,27 % | −30,28 % | 130 | 33,08 % |
| H20 | 2025 | +65,76 % | +55,04 % | −28,22 % | 165 | 29,09 % |
| H20 | 2026 au19/10 | −6,10 % | −32,85 % | −37,52 % | 128 | 21,88 % |

**Compte continu2024–19octobre2026, sans remise à zéro :**

| Univers | Sélection | Capital final valorisé | Rendement net | DD max clôture | Trades clos | Gagnants |
|---|---|---:|---:|---:|---:|---:|
| H10 | TOP5 Oracle seuls | 2 999,50 $ | −25,01 % | −58,68 % | 747 | 23,69 % |
| H10 | TOP20 Oracle → TOP5 LONG | **9 222,83 $** | **+130,57 %** | **−15,52 %** | 543 | **49,36 %** |
| H20 | TOP5 Oracle seuls | **10 684,29 $** | **+167,11 %** | −45,17 % | 534 | 17,60 % |
| H20 | TOP20 Oracle → TOP5 LONG | 5 039,42 $ | +25,99 % | **−36,50 %** | 423 | **29,31 %** |

Pour les comptes per-symbol :

| Mesure | H10 | H20 |
|---|---:|---:|
| Gagnants /perdants | 268 /275 | 124 /299 |
| Somme des PnL gagnants après frais | +14 620,98 $ | +12 318,04 $ |
| Somme des PnL perdants après frais | −9 614,24 $ | −11 288,73 $ |
| Gain moyen gagnant | +54,56 $ | +99,34 $ |
| Perte moyenne perdant | −34,96 $ | −37,75 $ |
| Détention moyenne gagnants | 10,00 séances | 20,00 séances |
| Détention moyenne perdants | 6,58 séances | 6,18 séances |
| Engagement moyen en dollars | 5 723,57 $ | 4 304,58 $ |
| Engagement moyen /equity courante | 92,63 % | 90,67 % |
| Engagement maximal | 9 282,81 $ | 5 890,08 $ |
| Positions ouvertes finales | 6 | 5 |

![Comparaison daily](../../artifacts/research/us_selected_universe_per_symbol/20261104-v1/daily-comparison.png)

## Intraday — nouvelles sélections LONG, confirmation et DD15

Même nouvelle sélection TOP20→TOP5LONG dans les quatre bras. Même historique
SIP et même masque de qualité. Capital4 000USD sans remise à zéro ; métriques
DD sur les clôtures5m connues, pas sur des extrêmes intrabar inventés.

| Univers | Variante | Capital final | Rendement | DD max | Trades clos | Gagnants | Exposition moyenne /equity |
|---|---|---:|---:|---:|---:|---:|---:|
| H10 | Sans confirmation/DD15 | **5 398,65 $** | **+34,97 %** | −12,58 % | 231 | 47,62 % | 49,42 % |
| H10 | Confirmation Winner | 4 317,59 $ | +7,94 % | **−10,89 %** | 140 | 49,29 % | 29,51 % |
| H10 | DD15/B4 | **5 398,65 $** | **+34,97 %** | −12,58 % | 231 | 47,62 % | 49,42 % |
| H10 | Winner + DD15/B4 | 4 317,59 $ | +7,94 % | **−10,89 %** | 140 | 49,29 % | 29,51 % |
| H20 | Sans confirmation/DD15 | 3 688,35 $ | −7,79 % | −28,20 % | 103 | 30,10 % | 31,95 % |
| H20 | Confirmation Winner | 3 395,63 $ | −15,11 % | −22,10 % | 67 | 26,87 % | 19,73 % |
| H20 | DD15/B4 | **3 998,71 $** | **−0,03 %** | −21,17 % | 104 | 30,77 % | 25,69 % |
| H20 | Winner + DD15/B4 | 3 501,98 $ | −12,45 % | **−18,04 %** | 65 | 26,15 % | 12,94 % |

Le DD15 ne se déclenche sur aucun des comptes H10 qualifiés : l'égalité
BASE/DD15 et WINNER/WINNER_DD15 est attendue, pas un oubli du contrôleur.
Il est actif et se déclenche sur les cas H20 concernés.

Pour comparaison à données intraday identiques, les contrôles TOP5Oracle ont
également été rejoués. Leurs **32résultats reproduisent les anciens contrôles
intraday à1e−8 près** : aucune différence de référence cachée par les nouveaux
titres téléchargés. Comptes continus :

| Univers /sélection | Sans confirmation/DD15 | Winner | DD15/B4 | Winner + DD15/B4 |
|---|---:|---:|---:|---:|
| H10 TOP5Oracle | +4,44 % | +17,74 % | −3,75 % | +15,68 % |
| H10 TOP5LONG per-symbol | **+34,97 %** | +7,94 % | **+34,97 %** | +7,94 % |
| H20 TOP5Oracle | +3,04 % | −13,80 % | −15,30 % | −19,10 % |
| H20 TOP5LONG per-symbol | −7,79 % | −15,11 % | **−0,03 %** | **−12,45 %** |

**Résultats annuels intraday per-symbol**, cellules rendement /DD max :

| Univers /année | Sans confirmation/DD15 | Winner | DD15/B4 | Winner + DD15/B4 |
|---|---:|---:|---:|---:|
| H10 /2024 | −3,76 % /−8,12 % | +0,22 % /−6,24 % | −3,76 % /−8,12 % | +0,22 % /−6,24 % |
| H10 /2025 | +15,80 % /−10,47 % | −0,51 % /−10,81 % | +15,80 % /−10,47 % | −0,51 % /−10,81 % |
| H10 /2026 | +16,26 % /−13,13 % | +7,83 % /−7,06 % | +16,26 % /−13,13 % | +7,83 % /−7,06 % |
| H20 /2024 | +3,62 % /−9,96 % | −11,07 % /−14,71 % | +3,62 % /−9,96 % | −11,07 % /−14,71 % |
| H20 /2025 | +6,83 % /−11,16 % | +7,78 % /−5,50 % | +6,83 % /−11,16 % | +7,78 % /−5,50 % |
| H20 /2026 | −18,26 % /−20,23 % | −12,27 % /−17,96 % | −21,11 % /−22,08 % | −11,57 % /−15,70 % |

![Variantes intraday](../../artifacts/research/us_selected_universe_per_symbol/20261104-v1/intraday-comparison.png)

## Limites et données

**Les univers ont été sélectionnés avec leurs AUC2023–2025 ET2026.** Ce sont
des tests rétrospectifs sur un univers choisi avec les résultats observés,
même si les modèles et la sélection quotidienne sont chronologiquement causaux.
L'amélioration H10 ne constitue pas une validation indépendante ni une
autorisation de passage en production. Prix ajustés actuels et historique
reconstruit : pas de certification PIT des corrections du fournisseur.

Les replays daily ne demandent pas une couverture5m. Leurs exclusions de
qualité continuent à intervenir par date d'entrée, notamment37H10/54H20 sur
les comptes continus, pour changement de fournisseur. Ils restent des proxies
daily, sans confirmation ni moteur risque complet.

En intraday, le contrôle strict exige des séances régulières complètes sur
la veille et toute la fenêtre projetée, ainsi qu'identité/base de prix stables.
Il utilise l'existence future des données : **biais rétrospectif supplémentaire**.
Les fenêtres de split ne sont pas transformées en rendements. Ce contrôle
ne doit pas être assimilé à un filtre disponible en live.

| Univers /sélection | Occasions qualifiées2024 | 2025 | 2026 |
|---|---:|---:|---:|
| H10 TOP5Oracle | 10,52 % | 20,64 % | 30,90 % |
| H10 TOP5LONG per-symbol | 23,35 % | 26,16 % | 39,50 % |
| H20 TOP5Oracle | 4,30 % | 11,68 % | 20,50 % |
| H20 TOP5LONG per-symbol | 20,08 % | 9,04 % | 25,00 % |

Même règle de qualification pour toutes les variantes et les deux sélections,
mais les occasions retenues changent. Les chiffres intraday ne représentent
donc **pas les univers complets**, et ne sont pas directement comparables aux
rendements daily. La moindre exposition contribue également aux DD plus faibles.

Les données ont été étendues aux61titres de l'union des anciennes/nouvelles
sélections, sans écriture SQL : snapshot SELECT-only1 320 489barres, réemploi
des23historiques déjà récupérés,12historiques supplémentaires manquants
téléchargés en SIP (184nouvelles réponses,563réponses dans le cache agrégé),
queues complétées et variantes daily raw/split. Cinq transitions de base
fournisseur sont qualifiées dans cette union, dont les trois déjà identifiées.
Les anciens fichiers de recherche et modèles restent inchangés.

## Artefacts et vérification

Dossier `artifacts/research/us_selected_universe_per_symbol/20261104-v1/` :

- `selection-report.json`, `models-reused.json` : sources, dates des207modèles,
  probabilités reproduites et comparaison des sélections.
- Sous chaque univers : `per-symbol-long-scores.parquet`,
  `oracle-top20-long-ranking.parquet`, `daily-top5.csv`, **`selection-proof.csv`**.
  Ce dernier ne présente que les données de décision, sans réalisation future.
- `daily-comparison.csv`, `daily-report.json`, `daily/{univers}/{année,continuous}/`.
- **`intraday-comparison.csv`** :64cas, deux sélections ×deux univers ×quatre
  périodes ×quatre variantes ; sorties détaillées sous`intraday/{sélection}/runs/`.
- Masques partagés et par sélection, `coverage-summary.csv`, archives SQL/API,
  courbes, transactions, raisons de rejet et journaux de confirmation/liquidation.
- `protocol.json`, `report.json`, `progress.json`, `verification.json` et
  `verification-cases.csv`.

Vérification **PASS_WITH_RETROSPECTIVE_SELECTION_AND_COVERAGE_LIMITS** :
72comptes et5 767trades contrôlés (avec répétitions économiques entre comptes
annuels et continus), cash/coûts/PnL latent, chronologie, horizons, stops/gaps,
TOP20 avant TOP5LONG, priorité d'achat LONG, preuve de calibration annuelle,
délai et plafond IOC, DD15 et trajectoires identiques avant premier trip.
Les32contrôles Oracle précédents sont reproduits exactement aux tolérances
monétaires documentées. **52tests ciblés passent**.

Aucun appel LLM, ordre broker, modèle entraîné à nouveau, écriture SQL,
modification de configuration, de batch ou promotion. Même assistant : pas
une seconde revue humaine indépendante. Modules natifs de confirmation/B4,
mais ledger et hypothèses d'exécution de recherche ; pas de garantie de
remplissage broker réel ou de spread sur petites valeurs.

Scripts sous`scripts/research` :
`us_selected_universe_per_symbol_selection_20261104.py`,
`us_selected_universe_per_symbol_inputs_20261104.py`,
`us_selected_universe_per_symbol_replay_20261104.py`,
`us_selected_universe_per_symbol_review_20261104.py`.

**Conclusion bornée :** le tri per-symbol est favorable à H10 dans le replay
daily et dans le bras intraday sans confirmation. Il ne produit pas une
amélioration transversale pour H20 ou avec confirmation Winner. Ce résultat
ne transforme pas les listes choisies avec2026 en univers validés prospectivement.

## Diagnostic complémentaire : pourquoi H10 et H20 diffèrent

Les deux fichiers sont issus de classements séparés sur deux cibles, malgré
le même double seuil AUC>0,60. **WHF est leur seul symbole commun** :31titres
propres à H10 et36propres à H20. Ce n'est pas le même univers observé à deux
horizons ; les Oracles dédiés, la cible des modèles LONG et la durée de
détention changent également. La taille boursière n'est pas un critère de ces listes.

Le point central est l'alignement entre cible et exécution : H10 apprend la
rentabilité nette du LONG SL5/open11, tandis que H20 apprend la domination du
pic haussier sur le pic baissier, sans SL. Un parcours100→94→125 est haussier
selon cette seconde cible, mais le trade avecSL95 est déjà sorti perdant.
Un pic favorable peut aussi être restitué avant la sortie temporelle.

Diagnostic des TOP5 et trades du **compte daily continu**, pas des replays
intraday partiels :

| Mesure | H10 | H20 |
|---|---:|---:|
| ATR20 médian des3 510couples sélectionnés, en %du prix à J | 2,83 % | 4,25 % |
| Distance SL5 en unités d'ATR, médiane | 1,76ATR | 1,18ATR |
| Trades clos sortis au SL ou en gap sous SL | 183 /543 —33,70 % | 287 /423 —67,85 % |

Le même SL5 représente donc une distance plus faible relativement à la
volatilité des candidats H20. Une détention plus longue et une composition
différente contribuent potentiellement à l'écart ; ce diagnostic ne permet
pas d'attribuer une part causale à chacun.

Sur les414trades H20 disposant d'un label de parcours réellement mature au
19octobre,233ont un **pic haussier dominant observé a posteriori**. Pourtant,
111de ces233trades sont perdants avec les règles financières SL5/open21 :
99sorties stop/gap et12sorties temporelles. Ce sont des étiquettes de parcours
réalisées, **pas des avis LONG du modèle présentés comme certains**.
Cela quantifie le décalage entre cible et trade. La concordance du label de
rentabilité H10 avec son PnL est, elle, par construction ; ce n'est pas une
mesure supplémentaire d'exactitude du modèle.

2026 pèse également dans le résultat : compte annuel H10+14,11 % contre
H20−32,85 %, alors que H20 avait mieux fait en2025 (+55,04 % contre+33,62 %).
Il n'est donc pas établi que H10 soit intrinsèquement meilleur dans toute période.

Le diagnostic est archivé dans`diagnostic-h10-vs-h20.json` sous le dossier
de campagne, avec les empreintes des sélections, transactions et panels.
Aucun nouveau fit, replay, téléchargement ou changement de trading.
Pour isoler l'horizon, un futur test devra conserver le même univers et une
cible de rentabilité SL5 commune, puis comparer les sorties open11/open21.
