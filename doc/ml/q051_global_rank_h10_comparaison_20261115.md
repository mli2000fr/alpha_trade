# Q051 vol20 + régime : Global Ranking H10

## Protocole fixé avant les nouveaux résultats

Demande utilisateur du15novembre2026 : comparer le classement per-symbol
actuel, le classement Global H10 et une fusion de leurs rangs à50/50.
La comparaison doit être hors échantillon avec disponibilité causale, distincte
du replay c59bed avec anticipation autorisée. Aucun nouveau poids de fusion
ni seuil choisi selon les résultats des années testées.

Les trois variantes conservent le même TOP10 % Oracle (179sur1 790), cinq
candidats avant seuils LONG>0,50/AUCcalibration≥0,50, sans remplacement après
échec. Même risque Q051, vol20/cov60, SPYJ>98 %SMA200, SL5/open11 sans TP,
trailing, renforcement ni confirmation5m ; frais8pb/opération, capital4 000USD
continu, achats1×/capacité2×. Aucun ordre ni changement du pipeline PAPER.

1. `Q051_REFERENCE` : classement par probabilité LONG.
2. `GLOBAL_H10` : classement par score Global H10, mêmes seuils per-symbol.
3. `FUSION_50_50` : percentiles des deux scores dans le même pool Oracle
   couvert, moyenne50/50, puis TOP5 et mêmes seuils.

Les scores globaux absents restent absents : aucun rang0,5 synthétique. Une
valeur0,5 réellement calculée reste valide. Les couvertures seront publiées,
et une modification de population ne sera pas attribuée artificiellement au
nouveau classement. Toutes les AUC de calibration doivent être connues avant
la décision. Le ranking global est relatif, pas une probabilité de hausse.

Base de comparaison : référence annuelle causale2021–01/10/2026 déjà figée,
avec un Oracle/per-symbol correspondant à chaque année. Les poids doivent
être arrêtés avant chaque évaluation ; aucun champion Global choisi sur
l'ensemble des performances des années de test.

## Inventaire initial

`global_rank_history` est vide ; aucun fichier `_global_ranking_features.json`,
poids Global ou `global_rank_cache.parquet` dans les dossiers de modèles
actuellement présents. Les trois archives `oracle_global_rank_cross` sont des
diagnostics historiques, et les recherches `us_winner_global_selector` et
`us_oracle_path_trend_ranking` n'apportent pas un modèle Global H10 servable
et compatible avec cette expérience.

L'utilisateur a choisi le 15 novembre d'entraîner un nouveau Global Ranking H10
pour cette comparaison hors échantillon. Le sélecteur pur se trouve dans
`scripts/research/q051_global_rank_selection.py` ; le pilote local dans
`scripts/research/us_q051_global_rank_h10_20261115.py`.

## Préparation vérifiée

Sept tests du sélecteur passent : mêmes pools Oracle, seuils après TOP5 sans
remplissage, scores Global absents laissés absents, vrai rang médian accepté,
AUC futures refusées et fusion des rangs à50/50. Aucun changement de production.

Le nouveau sélecteur témoin reproduit exactement les dates, titres et priorités
des sélections Q051 archivées :907/1164/768/1227/1095/912signaux pour2021→2026,
la dernière année jusqu'au1eroctobre. Preuve :
`artifacts/research/us_q051_global_rank_h10/20261115-v1/baseline-selection-validation.json`.

## Entraînement autorisé et démarré

Six modèles annuels LightGBM LambdaRank, fenêtres de début identiques aux
Oracle annuels (2014, 2015, …, 2019), dernier cours et dernière étiquette
strictement antérieurs au premier signal utilisé. Les premières entrées de
janvier peuvent utiliser un signal de décembre : la limite n'est donc pas
simplement le 31 décembre précédent. Validation sur 126 séances passées, purge
des étiquettes qui chevauchent le début de cette validation. Aucun choix de
backend ou de paramètres selon les résultats économiques des années de test.

Cible figée : rendement de clôture entre J et la véritable séance J+10,
divisé par volatilité passée 20 séances, winsorisation 1/99 % et déciles
cross-sectionnels. Variante `raw_target` du Global : aucun mélange H15/H20
ni neutralisation sectorielle/factorielle de la cible. Ce choix mesure un
classement directionnel H10, pas la probabilité de gagner avec SL5/open11.
Une séance manquante ne décale jamais J+10 ; les changements connus d'identité
économique sont exclus des étiquettes traversantes.

156 variables techniques et rangs dérivés du moteur Global existant, sans news,
consensus, options, fondamentaux actuels ou scores de sélection. Les variables
sont relues dans les caches Oracle vérifiés, puis les rangs sont recalculés
sur l'univers complet, pas les blocs de 25 titres. Pour les dates 2026, le
cache de variables de c59bed est utilisé uniquement comme calcul de données
passées : aucun poids, score ou AUC de ce modèle n'est utilisé par le Global.
Les générateurs entraînement/prédiction doivent être identiques.

Paramètres fixés : 200 arbres maximum, profondeur 5, 31 feuilles, taux 0,03,
minimum 150 observations par feuille, pénalités L1/L2 0,1/0,1, fractions
0,8/0,7, graine 42 ; arrêt anticipé après 20 itérations sans amélioration
NDCG@5 de validation. Poids temporels exp(−âge calendaire/360), aucune
ré-estimation après validation. Deux entraînements simultanés, quatre threads
par modèle. Les poids et leur date de disponibilité seront scellés avant replay.

Le témoin économique doit reproduire la référence native précédente avant
conclusion. Les trois simulations garderont les archives de prix d'origine et
leurs compléments déjà figés. Limites : univers contemporain (biais de survie),
cours archivés potentiellement révisés, replis OHLC journaliers lorsque le 5m
n'est pas qualifié. La chronologie des modèles est hors échantillon ; cela
ne certifie pas l'ensemble des données point-in-time historiques.

Onze tests passent, dont horizon exact malgré une séance absente, purge de
validation, rupture d'identité et indépendance des labels entre dates.
Suivi : `artifacts/research/us_q051_global_rank_h10/20261115-v1/progress.json`
et `years/<année>/progress.json`. Aucun téléchargement, écriture SQL, appel
broker ou changement du parcours PAPER dans cette expérience.

## Modèles terminés et sélection figée

Les six modèles annuels sont entraînés. Les itérations retenues par la seule
validation passée sont 1 / 3 / 41 / 9 / 62 / 1 pour 2021 à 2026. Cela ne
constitue pas un avantage démontré : les IC moyens de validation restent faibles
et variables (environ −0,019 à +0,024). Aucun minimum d'arbres ajouté après coup,
aucune nouvelle recherche de paramètres déclenchée par ces chiffres.
Dates précises et compteurs : `annual-global-models.csv` à la racine du run.
Chaque `years/<année>/receipt.json` scelle les poids, sources, dates et scores.

Sur 258 297 couples du pool Oracle, 16 n'ont pas de score Global, soit une
couverture de 99,994 %. Contrôle supplémentaire : limiter le témoin au pool
réellement couvert par le Global ne change aucun de ses 6 073 signaux.
Preuve `coverage-reference-control.json`. Aucun cours ou score absent inventé.

| Année d'entrée | Témoin per-symbol | Classement Global | Fusion 50/50 |
| --- | ---: | ---: | ---: |
| 2021 | 907 | 30 | 409 |
| 2022 | 1 164 | 78 | 509 |
| 2023 | 768 | 42 | 278 |
| 2024 | 1 227 | 116 | 750 |
| 2025 | 1 095 | 172 | 966 |
| 2026 au 1 octobre | 912 | 88 | 603 |
| Total | 6 073 | 526 | 3 515 |

Ce sont des **signaux après seuils**, pas des trades exécutés : doublons de
positions détenues, régime, sizing et budget de volatilité interviennent ensuite.
Les cinq candidats Global sont souvent refusés par les seuils per-symbol
conservés ; aucun remplacement n'est effectué. Une éventuelle baisse du DD
doit donc aussi être examinée avec l'exposition et l'activité, pas attribuée
d'office à une meilleure direction.

Les 5 811 fichiers référencés dans les deux manifestes de marché sont vérifiés
intacts : `market-validation.json`. Les précisions de commande/provenance pour
l'historique IHM sont ajoutées aux protocoles des cas sans modifier la
configuration numérique du replay ; version antérieure conservée localement.

## Parité économique du témoin

Replay complet des 1 443 séances terminé, contrôles natifs **PASS**, aucune
différence sur capital final, rendement, DD intraday, comptes gagnants/perdants,
frais et capital engagé moyen. Référence : 9 039,00 USD finaux, +125,98 %, DD
−24,29 %, 940 trades, taux gagnant 36,17 %, capital engagé moyen 2 396,13 USD
(44,76 % du capital courant). C'est la référence annuelle causale jusqu'au
1 octobre 2026, distincte du test c59bed avec anticipation jusqu'au 13 novembre.
Reçu `economic-baseline-validation.json`. Historique IHM :
`20261115_q051_global_q051_reference`.

Les deux variantes Global et fusion sont ensuite lancées simultanément.

## Premier résultat : classement Global seul

`GLOBAL_H10` terminé : 4 007,43 USD finaux, **+0,19 %**, DD maximal intraday
**−17,70 %**, 155 trades, **30,32 %** gagnants. Capital engagé moyen 411,73 USD,
soit **9,95 %** du capital courant, contre 44,76 % pour le témoin. Ce Global H10
ne remplace donc pas avantageusement le classement per-symbol dans ce protocole.
Son DD inférieur ne constitue pas une amélioration isolée de qualité : la
stratégie investit beaucoup moins, et son taux gagnant baisse. La fusion reste
en cours à ce stade intermédiaire. Aucune activation de ces nouveaux poids en production.

## Bilan final — terminé et validé le 15 novembre 2026

Trois replays continus, même capital de départ de 4 000 USD, du 1 janvier 2021
au 1 octobre 2026, frais inclus. Les six Global ne voient aucune étiquette
postérieure à leur premier signal de test. C'est une validation de chronologie
des modèles, avec les limites historiques d'univers et de prix décrites plus haut.

| Classement après Oracle | Capital final valorisé | Rendement | DD maximal intraday | Trades | Gagnants | Capital engagé moyen |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Per-symbol — référence | 9 039,00 USD | +125,98 % | −24,29 % | 940 | 36,17 % | 2 396,13 USD / 44,76 % |
| Global H10 | 4 007,43 USD | +0,19 % | −17,70 % | 155 | 30,32 % | 411,73 USD / 9,95 % |
| Fusion des rangs 50/50 | 8 366,86 USD | +109,17 % | −23,54 % | 674 | 35,31 % | 2 240,29 USD / 36,45 % |

Les pourcentages d'engagement sont la moyenne du ratio engagement/capital
courant sur les marques régulières 5m, pas le ratio des deux moyennes.
Les capitaux finaux incluent la valorisation des positions encore ouvertes.
Les frais sont de 862,12 / 171,63 / 822,87 USD ; intérêts de marge nuls dans
les trois cas. Gagnants/perdants : 340/600, 47/108, 238/436. Gain moyen d'un
gagnant : 64,42 / 80,76 / 88,51 USD ; perte moyenne : −28,04 / −35,26 / −38,34 USD.

| Rendement annuel continu | Référence | Global H10 | Fusion 50/50 |
| --- | ---: | ---: | ---: |
| 2021 | −8,00 % | −5,23 % | +16,94 % |
| 2022 | +6,12 % | −4,87 % | −4,86 % |
| 2023 | +24,66 % | +8,85 % | +37,97 % |
| 2024 | +29,11 % | +10,51 % | +19,06 % |
| 2025 | +1,84 % | −2,57 % | −0,22 % |
| 2026 jusqu'au 1 octobre | +41,21 % | −5,17 % | +14,71 % |

**Conclusion : ne pas ajouter ce Global à la référence actuelle.** Le Global
seul dégrade fortement le rendement et le taux gagnant. La fusion améliore
2021 et 2023, mais dégrade les quatre autres années. Sur toute la période, elle
abandonne 16,80 points de rendement pour seulement 0,75 point de DD en moins,
avec un taux gagnant inférieur de 0,86 point et une exposition moindre.
Ce n'est pas une amélioration transversale démontrée. Aucun poids 30/70,
nouveau seuil ou choix de variante par année n'est recherché après ces résultats.
Cette conclusion porte sur ce Global H10 et cette intégration, pas sur tous
les modèles Global possibles. Le pipeline PAPER conserve sa référence.

Validation finale `validation.json` **PASS** : six disponibilités causales,
purges de validation, paramètres identiques, sorties scellées et percentiles
réellement calculés ; seuils LONG/AUC, même configuration de portefeuille,
comptes de trades, capital final, composition des rendements annuels, parité
financière et descriptifs de l'historique IHM. Onze tests techniques repassent.
Les trois bilans conservent `INCOMPLETE_COVERAGE` pour les replis OHLC journaliers
au lieu d'inventer des parcours 5m. Aucune certification de parité live complète.

Historique IHM :

- `20261115_q051_global_q051_reference`
- `20261115_q051_global_global_h10`
- `20261115_q051_global_fusion_50_50`

Résultats dans `artifacts/research/us_q051_global_rank_h10/20261115-v1/` :
`comparison.csv`, `comparison-validated.csv`, `annual-comparison.csv`,
`capital-comparison.png`, `capital-comparison.csv`, `annual-global-models.csv`.
Le graphique de DD utilise les clôtures ; le tableau ci-dessus utilise les
marques intraday natives. Une colonne de présentation d'exposition laissée vide
par le pilote a été complétée depuis les ratios natifs validés, sans modifier
les simulations ; export initial conservé pour traçabilité.
Les dossiers `cases/<variante>/result/` contiennent trades, événements, equity,
frais et décisions de risque. Zéro appel fournisseur/broker, zéro écriture SQL,
aucune modification des modèles ou paramètres servables de production.
