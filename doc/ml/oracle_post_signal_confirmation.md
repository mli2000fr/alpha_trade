# E9 — Confirmation directionnelle après le signal Oracle

## Verdict

E9-A est `NO_GO`. E9-B (lifecycle canonique) n'est pas ouvert. Le serving, le backtest applicatif et le live restent inchangés.

Observer le prix pendant une à cinq séances après un signal Oracle TOP20 ne permet pas de déterminer de façon stable si le mouvement restant sera haussier ou baissier. La politique primaire `absolute_d2` perd en moyenne 0,309 % net par date, avec une précision directionnelle de 49,40 %. Une seule fenêtre sur douze et un seul semestre sur treize sont positifs.

Artefact canonique :

```text
artifacts/research/oracle_post_signal_confirmation/oracle-post-signal-confirmation-20260910230114
```

## Question et horloge causale

E9 change l'ensemble d'information : le système accepte de ne pas entrer tout de suite et attend que le prix commence à révéler le sens du mouvement.

```text
close J : Oracle H20 classe le titre TOP20 amplitude
close J+D : observation, D = 1, 2, 3 ou 5 séances
open J+D+1 : LONG, SHORT ou abstention
open J+21 : mesure jusqu'au terminal H20 original
```

La décision au close J+D n'utilise jamais l'open J+D+1. E7 décidait KEEP/EXIT sur une position déjà ouverte et le rolling J+5 ouvrait d'abord une position LONG. E9-A n'ouvre aucune position avant confirmation.

## Population

| Élément | Valeur |
|---|---:|
| Événements TOP20 | 82 212 |
| Dates | 1 512 |
| Symboles | 194 |
| Folds OOF | 12 |
| Période | 2018-07-05 au 2024-07-09 |

Les prix sont recalculés depuis `stock_bars_daily` en convention ajustée. Les coûts sont 1 bp de commission plus 2 bp de slippage par côté, soit 6 bps aller-retour. Aucune table n'est écrite.

Le secteur provient du `stock_metadata` courant et n'est pas PIT historique. La variante sectorielle est donc seulement secondaire.

## Politiques et sélection des seuils

Trois mesures sont testées à J+1/J+2/J+3/J+5 : rendement absolu, rendement relatif à SPY et rendement relatif à la médiane sectorielle.

```text
signal >= +seuil  → LONG
signal <= -seuil  → SHORT
sinon             → abstention
```

Les seuils possibles sont 0 %, 0,25 %, 0,50 %, 1 % et 2 %. Pour chaque fold, le seuil est choisi uniquement sur les folds OOF antérieurs, avec au moins 500 événements et 15 % de couverture. Le premier fold utilise le seuil préfixé de 0,50 %. La politique primaire est `absolute_d2` ; les onze autres sont secondaires.

## Résultats

| Politique | Trades | Couverture | Précision | Net quotidien | Folds positifs |
|---|---:|---:|---:|---:|---:|
| absolute D1 | 64 237 | 78,14 % | 49,58 % | -0,308 % | 2/12 |
| **absolute D2** | **74 125** | **90,16 %** | **49,40 %** | **-0,309 %** | **1/12** |
| absolute D3 | 76 892 | 93,53 % | 49,25 % | -0,385 % | 2/12 |
| absolute D5 | 79 749 | 97,00 % | 49,41 % | -0,306 % | 3/12 |
| SPY relatif D1 | 73 875 | 89,86 % | 49,62 % | -0,368 % | 1/12 |
| secteur relatif D1 | 52 304 | 63,62 % | 48,38 % | -0,378 % | 1/12 |

Pour `absolute_d2`, l'intervalle bootstrap par blocs de 21 séances du net quotidien est [-0,739 % ; +0,124 %]. L'écart quotidien contre une position LONG sur les mêmes événements vaut -2,063 %, intervalle [-4,230 % ; +0,105 %].

## Attribution LONG et SHORT

| Politique | Côté | Trades | Précision | Futur du titre | Net directionnel |
|---|---|---:|---:|---:|---:|
| absolute D1 | LONG | 32 293 | 51,67 % | +1,933 % | +1,873 % |
| absolute D1 | SHORT | 31 944 | 47,47 % | **+2,443 %** | **-2,503 %** |
| absolute D2 | LONG | 37 347 | 51,41 % | +1,625 % | +1,565 % |
| absolute D2 | SHORT | 36 778 | 47,37 % | **+2,201 %** | **-2,261 %** |
| absolute D5 | LONG | 40 752 | 51,38 % | +1,263 % | +1,203 % |
| absolute D5 | SHORT | 38 997 | 47,35 % | **+1,839 %** | **-1,899 %** |

Le signe négatif initial n'est pas une confirmation baissière : ces titres remontent ensuite davantage que les titres classés LONG. Le meilleur écran LONG descriptif, `sector_relative_d1`, gagne 2,528 % net contre 1,865 % pour tous les événements au même délai, mais son delta n'est positif que dans 4 folds sur 12 et vient surtout de 2020H1. Il n'est pas promu.

## Gates et règle d'arrêt

Les gates de volume et couverture passent. Échouent : net directionnel positif, delta contre LONG positif, borne basse IC95 positive, 60 % de folds positifs et 60 % de semestres positifs.

E9 rejette donc la politique symétrique « hausse observée → LONG, baisse observée → SHORT ». Retarder l'entrée consomme une partie du mouvement sans rendre le signe restant prédictible. E9-B est fermé : optimiser le lifecycle ne doit pas masquer l'absence de direction. Une réouverture exige une nouvelle source PIT directionnelle ou une période intacte définie avant observation.

## Observation exploratoire et suite autorisée

L'échec du SHORT révèle une hypothèse différente : une baisse juste après la
détection Oracle pourrait constituer un **pullback d'entrée LONG**, et non une
confirmation baissière. Ce résultat est exploratoire, car l'hypothèse a été
formulée après lecture des résultats E9.

| Écran exploratoire | Trades | Couverture | LONG net jusqu'au terminal H20 | Oracle LONG au même délai | Delta | Folds avec delta positif |
|---|---:|---:|---:|---:|---:|---:|
| baisse absolue à J+1, seuil E9 préquentiel | 31 944 | 38,86 % | 2,383 % | 1,865 % | +0,518 pt | 11/12 |
| baisse absolue à J+2, seuil E9 préquentiel | 36 778 | 44,74 % | 2,141 % | 1,770 % | +0,371 pt | 10/12 |
| sous-performance secteur à J+1 | 26 629 | 32,39 % | 3,106 % | 1,865 % | +1,241 pt | 9/12 |

La variante sectorielle reste secondaire : son secteur est issu du metadata
courant et son pire fold perd 1,221 point contre le benchmark. La formulation
primaire proposée pour E10 est donc la plus simple et la plus causale : Oracle
TOP20, baisse absolue observée au close J+1, entrée LONG au prochain open.

E10 a ensuite gelé cette hypothèse comme **filtre d'entrée LONG contrariant** et
l'a confirmée sur une période postérieure avec un autre batch Oracle H20 OOF.
Le delta quotidien devient -0,056 point, IC95 [-0,603 ; +0,436], avec seulement
1/2 folds et 1/3 semestres favorables. Verdict `NO_GO` : l'effet exploratoire ne
se généralise pas et E10-B n'est pas ouvert. Voir
[E10 — Pullback LONG](oracle_pullback_long.md).

## Reproduction

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.oracle_post_signal_confirmation --phase1-artifact artifacts/research/multi_horizon_oracle_rolling/multi-horizon-rolling-20260910141708-d5b30f --bootstrap-samples 2000 --log-level INFO
```

Fichiers : `eligible_events.parquet`, `prequential_decisions.parquet`, `threshold_history.jsonl`, `policy_summary.csv`, `policy_by_side.csv`, `policy_by_fold.csv`, `policy_by_semester.csv` et `report.json`.
