# E12 — Pont de monétisation Oracle H20

## Statut

`FAIT_NO_GO_OR_BLOCKED` — expérience de recherche uniquement. Aucun artefact de
serving, signal persistant, backtest applicatif ou flux live n'a été modifié.

Artefact canonique :
`artifacts/research/oracle_monetization_bridge/oracle-monetization-bridge-20260911154131`.

Le premier artefact `.../oracle-monetization-bridge-20260911153630` est
supplanté : il conservait la capacité bloquée jusqu'à H20 même lorsqu'un TP ou
un stop libérait une position plus tôt. Le schéma 2 réalloue les places au fil
des sorties réelles, sans anticiper une sortie intraday.

## Question falsifiable

E11 montre que le Global Ranking ne donne pas la direction, tandis que l'étude
d'événements Oracle suggère qu'acheter tout le TOP20 reste positif en moyenne.
E12 cherche donc à localiser la rupture entre ce rendement théorique et les
backtests décevants :

```text
Oracle TOP20 OOF
  -> rendement fixe H20 de tous les événements
  -> déduplication des signaux qui se chevauchent par symbole
  -> portefeuille limité à 8 positions
  -> priorité Oracle / liquidité / tirages aléatoires
  -> sensibilité à l'univers tradable PIT disponible
  -> lifecycle PROD avec réallocation dynamique des places
```

L'expérience est LONG-only. Elle ne prétend pas résoudre D1/D10 ; elle mesure
si le signal d'amplitude peut être monétisé sans modèle directionnel.

## Contrat figé

- Source : `_oracle_oof_gate.parquet` du batch
  `model-factory-20260909051302-323684`.
- Population : événements `directional_oracle_eligible=true` et
  `directional_oracle_oof_available=true` uniquement.
- Horizon : H20, non optimisé pendant E12.
- Entrée : open ajusté de J+1.
- Sortie fixe de référence : open ajusté de J+21.
- Coûts : 1 bp de commission et 2 bp de slippage par côté, soit 6 bp
  aller-retour.
- Déduplication : premier signal par symbole, puis prochain signal dont
  l'entrée n'est pas antérieure à la sortie H20 du précédent.
- Capacité : 8 positions simultanées.
- Priorités comparées : probabilité Extreme Oracle, ADV20 et 200 ordres
  aléatoires reproductibles.
- Bootstrap : 2 000 réplications, blocs de 21 séances.
- Lifecycle PROD : stop initial 2,5 ATR, trailing 2,5 ATR actif à partir de la
  deuxième séance, TP `min(3 ATR, 7 %)`, résolution intraday conservatrice,
  filtre de gap 3 %, aucun time stop.
- Une sortie intraday en J ne libère une place qu'à partir de J+1. La capacité
  disponible à l'open de J ne bénéficie donc d'aucune connaissance future.

Les métriques dites `daily_mean` sont des moyennes des cohortes de nouvelles
entrées par date. Elles ne constituent ni une courbe de capital, ni un CAGR.

## Résultats par couche

| Couche | Événements | Dates | Rendement net moyen | Win rate | IC95 de la moyenne par date |
|---|---:|---:|---:|---:|---:|
| Tous les Oracle, sortie H20 | 582 700 | 1 764 | +1,103 % | 51,31 % | [-0,197 % ; +2,498 %] |
| Dédupliqués, sortie H20 | 37 659 | 1 764 | +1,139 % | 51,57 % | [-0,211 % ; +2,362 %] |
| Capacité 8, priorité Oracle, sortie H20 | 712 | 89 | +2,540 % | 52,95 % | [-0,070 % ; +4,614 %] |
| Capacité 8, priorité liquidité, sortie H20 | 712 | 89 | +2,283 % | 54,49 % | [-0,554 % ; +4,952 %] |
| Capacité 8, aléatoire seed 0, sortie H20 | 712 | 89 | +0,606 % | 49,44 % | [-0,695 % ; +2,345 %] |
| Tradable dégradé, priorité Oracle, sortie H20 | 451 | 355 | -0,791 % | 49,22 % | [-2,412 % ; +1,804 %] |
| Lifecycle PROD dynamique, priorité Oracle | 2 013 | 1 160 | +0,276 % | 62,30 % | [-0,290 % ; +0,900 %] |

La priorité Oracle bat le 95e percentile des 200 tirages aléatoires et se situe
au percentile 100 de cette distribution. C'est un résultat utile : le score
Oracle porte une information de sélection à l'intérieur de ses propres
événements. Il reste toutefois insuffisant pour un GO, car les intervalles de
confiance de l'étude globale, de la capacité et du lifecycle recouvrent zéro.

## Attribution du lifecycle

Sur les 2 013 trades exécutés par le replay dynamique :

| Sortie | Trades | Rendement PROD moyen | Rendement H20 des mêmes événements | Delta |
|---|---:|---:|---:|---:|
| Take profit | 1 214 | +6,91 % | +9,51 % | -2,59 pts |
| Trailing stop | 686 | -10,93 % | -9,23 % | -1,70 pt |
| Initial stop | 12 | -7,32 % | -11,48 % | +4,16 pts |
| Toujours ouvert à H20 | 101 | -2,45 % | -2,45 % | 0 |

Le lifecycle enlève en moyenne `2,119 points` au rendement H20 des mêmes
événements. Le delta journalier est `-2,182 points`, avec un IC95 entièrement
négatif `[-3,737 ; -0,482]`. Le constat est donc statistiquement plus solide
que le petit rendement résiduel positif du replay.

Le stop initial protège les rares événements concernés. Le principal frottement
vient du couple TP/trailing : le TP cristallise 1 214 gains avant leur H20 moyen,
et 686 trailing stops perdent en moyenne 10,93 %. Ce résultat ne prouve pas
qu'il suffit d'élargir un stop ou un TP : toute modification doit être évaluée
OOF et sur plusieurs semestres, sans optimiser les paramètres sur ce rapport.

707 candidats supplémentaires sont rejetés à l'entrée par le filtre de gap 3 %.
Ce filtre est conforme au contrat PROD et explique une partie de l'écart avec
l'étude d'événements abstraite, qui suppose l'achat de chaque événement.

## Stabilité temporelle

Le lifecycle dynamique est négatif ou presque nul en 2018H2, 2019H2, 2020H1,
2021H2, 2022H1 et 2023H1. Il est notamment à `-1,73 %` en 2021H2 et `-1,41 %`
en 2022H1. Il devient plus favorable en 2020H2 (`+2,20 %`), 2024H1
(`+0,97 %`), 2024H2 (`+1,70 %`) et 2025H1 (`+1,01 %`). Cette instabilité
interdit de transformer la moyenne globale en politique de production.

## Limite bloquante : univers tradable PIT

Les snapshots stricts `data_quality_grade=full` ne couvrent que 60 des 1 764
dates Oracle : 1 428 couples date/symbole et 451 symboles. La couche canonique
PIT n'est donc pas disponible sur l'historique complet.

La sensibilité qui accepte aussi les snapshots `degraded` couvre 1 799 dates,
mais seulement 742 symboles, et produit `-0,791 %` net à H20 sur 451 trades.
Ce résultat alerte fortement sur l'investabilité du pool Oracle, sans pouvoir
être présenté comme une preuve historique canonique : la qualité et la
couverture de ces snapshots ne satisfont pas le contrat exact.

## Verdict

E12 est `NO_GO_OR_BLOCKED` :

- l'Oracle conserve un signal moyen positif et sa priorité bat les sélections
  aléatoires ;
- la capacité de 8 positions n'est pas la cause principale de l'échec ;
- le lifecycle PROD détruit une part significative du rendement H20 ;
- le rendement résiduel du lifecycle n'est pas statistiquement supérieur à
  zéro ;
- la sensibilité tradable disponible devient négative ;
- l'historique tradable PIT strict est insuffisant pour autoriser une promotion.

Aucun exact backtest promotionnel n'est autorisé sur la base de cette expérience.
La prochaine expérience justifiée doit séparer, sans sweep opportuniste :

1. la valeur réellement accessible après filtre de gap et investabilité ;
2. les événements qui finissent en trailing stop des TP durables ;
3. une politique d'abstention/entrée retardée fondée exclusivement sur des
   informations disponibles avant l'entrée ;
4. la reconstruction d'un historique tradable PIT `full` avant toute conclusion
   de production.

## Reproduction

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.oracle_monetization_bridge --oracle-gate artifacts/models/model-factory-20260909051302-323684/_oracle_oof_gate.parquet --random-seeds 200 --bootstrap-samples 2000 --log-level INFO
```

Tests ciblés : `tests/test_oracle_monetization_bridge.py` (10 tests).

