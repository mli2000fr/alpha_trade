# Q051 H10 seuils 0,50 : filtre de régime ou plafond d'achat 2×

Demandés et lancés le 8 novembre 2026, deux replays en parallèle. Témoin exact :
Q051_050 continu du 01/01/2021 au 01/10/2026, 4 000 USD initiaux, six modèles
annuels H10, +206,51 %, DD −36,89 %, 1 234 trades, 35,01 % gagnants.

## Règles fixées avant résultats

- REGIME : B4/DD15 et liquidation désactivés, plafond d'achat 1× conservé.
  Autoriser les nouvelles entrées uniquement si la clôture SPY du jour de signal
  est strictement supérieure à 98 % de sa moyenne des 200 dernières séances.
  À égalité ou sous ce seuil, les candidatures du jour ne sont pas achetées.
  Pas de remplacement par d'autres candidats, pas de liquidation des positions
  existantes ; SL5/open11 inchangés. Les achats reprennent dès que la condition
  est satisfaite. Cette règle est le filtre d'entrée existant
  `RegimeFilterConfig(enabled=True, sma_window=200, bear_threshold=-.02)`.
  Le replay Winner ne consomme pas l'overlay historique automatiquement :
  raccordement explicite via `winner_selection_source` au moment de la décision
  journalière, avec audit `result/regime-decisions.csv`. Historique complet de
  200 séances et clôture précédente exigés ; aucune tolérance implicite aux trous.
- GROSS2 : B4/DD15, liquidation et filtre régime restent désactivés. Seul le
  plafond `risk_config.max_gross_exposure` passe de 1 à 2. Le compte margin avait
  déjà une capacité 2× ; il s'agit de lever le plafond d'achat 1× effectif. La
  capacité initiale est donc 8 000 USD pour 4 000 USD de fonds propres, puis suit
  deux fois le capital courant. Ce n'est ni un plafond fixe de 8 000 USD sur toute
  la période, ni une obligation d'investir tout le disponible.

Autres réglages communs intacts : TOP10 % Oracle → TOP5 LONG, score > 0,50,
AUC ≥ 0,50, position complète, entrée J+1 à l'ouverture sans confirmation,
SL5 %, sans TP/trailing/renforcement, sortie open11, risque par entrée 1,25 %,
poids 20 %, 20 positions max, minimum 50 USD, quantités entières. Facteurs,
corrélation, limites sectorielles, options et GPT off. Frais 8 bps/opération et
intérêt de marge annuel 6,5 %. Même capital, positions et exclusions conservés
entre années. Même archive de prix et candidatures, lecture seule, sans nouveau
modèle, téléchargement, inférence ou ordre broker.

Le précontrôle reproduit intégralement la configuration du témoin, puis exige
une seule différence par variante : activation du filtre d'entrée ou plafond
d'achat 2×. Les empreintes du moteur et du jeu de données source sont vérifiées.
Trois tests passent pour le filtre : blocage/permissivité, ordre des candidatures,
absence d'effet des prix futurs et refus des données SPY insuffisantes.

## Exécution

Programme : `scripts/research/us_winner_q051_regime_gross2_20261108.py`.
Dossier : `artifacts/research/us_winner_q051_regime_gross2/20261108-v1`.
Journal : `artifacts/research/us_winner_continuous_q051_q088/launch-Q051-regime-gross2-20261108-v1.log`.
Suivi global `progress.json`, puis `REGIME/progress.json` et `GROSS2/progress.json`.
Bilans annuels, trades, courbes, exposition et coûts dans chaque `result/`.
Comparaison au témoin dans `comparison.csv`.

Import IHM automatique et séquentiel par le coordinateur après chaque réussite :

- `20261108_continu_Q051_050_REGIME_v1`
- `20261108_continu_Q051_050_GROSS2_v1`

Les deux simulations sont réellement en cours au lancement ; aucun rendement
annoncé à l'avance. Résultats exploratoires : secteurs actuels, périodes déjà
examinées, couverture intraday incomplète avec recours OHLC journalier explicite.
Ni la production ni les anciens résultats ne sont modifiés.

## Résultats finaux — vérifiés le 8 novembre à 23h02, Paris

Les deux replays sont terminés sans échec et leurs imports IHM sont `completed`.
Les résultats natifs restent `INCOMPLETE_COVERAGE`, comme le témoin : ne pas
masquer le badge de réserve ni présenter les résultats comme une parité live.

| Variante H10 Q051 0,50 | Capital final USD | Rendement | DD maximal | Trades | Taux gagnant | Capital engagé moyen USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Témoin sans B4, plafond 1× | 12 260,32 | +206,51 % | −36,89 % | 1 234 | 35,01 % | 5 461,32 |
| Filtre régime, sans B4, plafond 1× | 10 805,53 | +170,14 % | −30,44 % | 1 077 | 35,28 % | 4 279,72 |
| Sans régime ni B4, plafond 2× | 13 706,18 | +242,65 % | −49,49 % | 1 516 | 35,36 % | 9 003,29 |

Le régime bloque 985 candidatures sur 215 séances parmi 1 437 décisions ayant
des candidatures. Il réduit le DD de 6,45 points et le rendement de 36,37 points
par rapport au témoin. Ce compromis observé est plus modéré que la variante B4
séparée (+19,93 %, DD −28,21 %), sans prouver une supériorité future.
Le plafond 2× augmente le rendement de 36,15 points, mais le DD se dégrade de
12,60 points ; le taux gagnant évolue peu. L'exposition maximale observée atteint
29 191,26 USD, contre 11 327,49 USD pour la variante régime. La capacité suit le
capital courant et n'est pas bornée à 8 000 USD sur toute la période. Les
montants moyens en dollars suivent aussi des trajectoires de capital différentes.

## Repère SPY sur la même période

Calcul sur les cours split archivés du même jeu de données, sans levier,
dividendes ni frais : achat à l'ouverture du 04/01/2021 (première séance après
le début demandé), 375,31 USD, valorisation à la clôture du 01/10/2026, 763,99 USD.
4 000 USD deviennent 8 142,50 USD : +103,56 %. DD calculé sur les clôtures
journalières : −25,36 %, sommet du 03/01/2022 à 477,71 USD, creux du 12/10/2022
à 356,56 USD. 1 443 séances, aucune barre remplie ou date dupliquée.
Les bougies 5m SPY ne sont pas dans l'archive de replay ; ce DD journalier n'est
pas strictement comparable aux DD des stratégies mesurés aussi en intraday.
Les dividendes SPY ne sont pas présents dans l'inventaire d'opérations sur titres
de cette archive : aucune performance totale dividendes réinvestis inventée.
Reçu : `artifacts/research/us_winner_q051_regime_gross2/20261108-v1/spy-benchmark-daily.json`.
