# Projection hypothétique : 70 % de trades LONG gagnants, TP20/SL10

## Statut et portée

15 octobre 2026. Demande utilisateur : « 70 % des trades sélectionnés sont
gagnants ». Projection synthétique terminée, **pas un backtest historique**, pas
une performance du modèle Oracle ou d'un modèle directionnel. Aucun apprentissage,
API, GPT, ordre, SQL ou réglage de production. Six tests ciblés passent.

Une réussite imposée à 70 % ne prouve pas qu'un modèle pourrait l'obtenir. Un
classement d'amplitude ne prédit pas le signe. Une direction terminale correcte
ne garantit pas que le stop n'ait pas été touché avant.

## Hypothèses explicites

- Capital initial : **4 000 USD**.
- Une seule position LONG à la fois, sans levier ni financement.
- Chaque entrée engage **25 % du capital courant, frais d'entrée inclus** ; le
  solde reste en espèces sans rémunération. Réinvestissement proportionnel.
- Scénario principal : exactement 70 % des trades atteignent **+20 %** et les
  autres font **−10 %**, sans gap ou dépassement du stop.
- Coûts hypothétiques : 8 points de base par sens, décomposés en commission 1,
  demi-spread 5 et slippage 2 ; coût de sortie appliqué au notionnel de sortie.
  Ce n'est ni un tarif de courtier validé, ni le moteur natif de backtest.
- Pas de durée imposée, de calendrier, de millésime2024/2025/2026 ni de
  disponibilité de signaux garantie. **Aucune annualisation**.
- Pas de valorisation intratrade, d'événement sur titre, de fiscalité, d'appel
  de marge, de contrainte de volume/secteur ou d'entrée simultanée.

Ainsi, cette projection ne revendique pas la parité live. Elle donne l'ordre de
grandeur économique d'une hypothèse, pas une validation causale ou exploitable.

## Calcul et résultats

Sans coût, espérance par dollar de notionnel engagé :

`0,70 × 0,20 − 0,30 × 0,10 = 0,11`.

Pour tenir compte exactement des deux coûts proportionnels, le rendement sur
le cash débité à l'entrée est :

`r_net = (1 + r_brut) × (1 − 0,0008) / (1 + 0,0008) − 1`.

L'espérance nette est **10,82254 % du cash engagé**, soit **108,23 USD pour
1 000 USD engagés par trade en moyenne**. Ce n'est pas 10,82 % du portefeuille
à chaque trade : ici seul un quart du capital est engagé.

Avec exactement 70 % de gains et réinvestissement proportionnel :

| Nombre de trades | Gagnants / perdants | Capital final | Rendement cumulé |
| --- | ---: | ---: | ---: |
| 20 | 14 / 6 | **6 745,26 USD** | **+68,63 %** |
| 50 | 35 / 15 | **14 770,87 USD** | **+269,27 %** |
| 100 | 70 / 30 | **54 544,66 USD** | **+1 263,62 %** |

Résultats élevés parce que l'on suppose des gains moyens très importants,
un taux de réussite exceptionnel et une capitalisation répétée. Ils ne sont
**pas des objectifs annuels ni une promesse**. Les 20/50/100 trades peuvent prendre
des durées très différentes ; avec jusqu'à 20 séances de détention par trade
et une seule position, 100 trades ne correspondent pas nécessairement à un an.

L'ordre des gains/pertes ne change pas le capital final avec ces coefficients
proportionnels constants ; il change le chemin, les creux de capital et le
drawdown. Ce résultat cesse d'être général avec marge, tailles plafonnées,
plusieurs positions, frais fixes ou contraintes de capital réelles.

## « Gagnant » ne veut pas forcément dire « TP atteint »

Le TP est un plafond, pas le gain moyen garanti. Si des gagnants expirent avec
un petit bénéfice, 70 % de réussite ne suffit pas à retrouver le tableau précédent.
Sensibilité sur 100 trades, 70 gagnants, 30 pertes de 10 %, mêmes coûts et sizing :

| Gain brut de chaque gagnant dans ce scénario simplifié | Capital final |
| --- | ---: |
| +3 % | **3 034,73 USD** |
| +5 % | **4 289,83 USD** |
| +10 % | **10 116,24 USD** |
| +15 % | **23 609,52 USD** |
| +20 % | **54 544,66 USD** |

L'espérance arithmétique devient positive si le gain brut moyen dépasse environ
**4,5145 %**, avec 70 % de gagnants et perte moyenne de 10 % sous les coûts supposés.
Ce seuil d'espérance n'est pas exactement le seuil de croissance géométrique.
Des pertes supérieures au SL lors de gaps ou d'autres coûts changent ce seuil.

## Incertitude et séries de pertes

10 000 permutations par taille ont été calculées. Avec exactement 70 gagnants
sur 100, le drawdown médian sur **capital après clôture uniquement** est 7,70 %,
et son 95e percentile 12,32 %. **Pas un drawdown intraday**, donc insuffisant pour
qualifier le risque réel.

Stress conservant 70 % de réussite : 30 pertes consécutives puis 70 gains, ou
l'inverse, donnent un drawdown de **53,73 %**. Un bon taux de réussite global
n'interdit donc pas une très mauvaise période.

Un second scénario tire chaque résultat indépendamment avec une probabilité
de 70 %, au lieu d'imposer un nombre exact de gagnants. Sur 100 trades, les
percentiles 5/95 du capital final sont 30 170/91 575 USD dans ces simulations.
Ces bornes sont **conditionnelles aux hypothèses artificielles**, pas des
intervalles de confiance sur le rendement futur d'Alpha Trade. L'indépendance
ne décrit pas les erreurs corrélées d'un modèle en régime défavorable.

## Reproduction et suite possible

- Script : `scripts/research/us_hypothetical_win70_tp20_sl10.py`.
- Tests : `tests/test_us_hypothetical_win70_tp20_sl10.py`.
- Protocole et résultat :
  `artifacts/research/us_hypothetical_win70/20261015-v2/{protocol,report}.json`.
  V1 conservée : avant ajout du scénario gagnant à +3 %, résultats principaux identiques.
- Graine 20261015, 10 000 simulations par scénario, sorties non écrasables.

Pour passer à un rendement annuel de portefeuille, il faudrait fixer le débit
de signaux, leurs dates, durées, chevauchements, tailles, échéances/gaps et
structure des erreurs, puis utiliser le moteur natif. **Cette étape n'a pas
été exécutée ici** : le seul taux de 70 % ne détermine pas ce rendement.
