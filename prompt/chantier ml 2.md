Chantier 2 — Filtre mécanique dans le module risque / entrée LONG

Nom de branche / expérience

PersistentTopLongEntryGate

Objectif

Tester une règle mécanique indépendante du ML :

un LONG est autorisé uniquement si :

le symbole est resté TOP10% Oracle pendant N séances consécutives ;
son prix a augmenté entre J-N et J.

Cette branche ne doit PAS modifier GlobalDirection.

1. Paramètres

Ajouter une configuration research-only :

persistent_top_long_gate:
  enabled: false
  source: oracle_extreme
  top_pct: 0.10
  consecutive_days: 3
  require_price_up: true

consecutive_days doit accepter uniquement :

2, 3, 4, 5

pour cette expérience.

2. Définition de la règle

Pour un signal LONG à la date J :

top10[J] = extreme_pct[J] >= 0.90

Vérifier :

top10[J]
top10[J-1]
...
top10[J-N+1]

tous vrais.

Puis :

price_confirm =
close[J] > close[J-N]

Finalement :

long_allowed =
persistent_top10_N
AND
price_confirm

Si faux :

rejeter seulement la nouvelle entrée LONG

Ne pas toucher aux positions déjà ouvertes.

3. PIT / exécution

La condition utilise le close J.

Donc :

calcul après close J
=> entrée possible au prochain open J+1

Interdiction d'exécuter au close J avec cette information.

4. Ne rien changer d'autre

Garder identiques :

modèle
ranking
sizing
max_positions
CP
B4
stops
TP
trailing
costs
lifecycle

Le seul changement est le gate d'entrée LONG.

5. Variantes pré-enregistrées

Tester exactement :

BASE = pas de gate

P2 =
TOP10 2 jours
+ close[J] > close[J-2]

P3 =
TOP10 3 jours
+ close[J] > close[J-3]

P4 =
TOP10 4 jours
+ close[J] > close[J-4]

P5 =
TOP10 5 jours
+ close[J] > close[J-5]

Ne pas ajouter ensuite N=6,7,8... en fonction du résultat.

6. Diagnostic de sélection

Pour BASE/P2/P3/P4/P5 produire :

candidates_before
candidates_after
coverage
rejected_pct

D1...D10
BAD5
GOOD5

mean_forward_return
median_forward_return
P(return > 0)

Ajouter :

D1_reduction
D2_reduction
BAD5_reduction

D10_retention
GOOD5_retention

Exemple :

D10_retention =
D10_rate_filtered / D10_rate_baseline

7. Mesurer le coût du retard

Pour chaque trade retenu :

pre_entry_return =
close[J] / close[J-N] - 1

puis mesurer le rendement réellement disponible après entrée J+1 :

post_entry_H20_return
MFE_after_entry
MAE_after_entry

Le but est de vérifier que le filtre ne confirme pas le bon mouvement trop tard.

8. Backtest portefeuille

Pour chaque variante :

return
Sharpe
Sortino
MaxDD
PF
win rate
trades
exposure
turnover

Toujours mêmes périodes et coûts que baseline.

9. Critère GO

Un gate est intéressant s'il fait :

BAD5 ↓ significativement
GOOD5 largement conservé
rendement/trade ↑
PF ↑
MaxDD stable ou meilleur

avec coverage encore exploitable.

Exemple intéressant :

D1 : 20% -> 14%
D10 : 25% -> 23%

Exemple NO-GO :

D1 : 20% -> 10%
D10 : 25% -> 11%

car le gate supprime simplement tous les extrêmes.

10. Aucun tuning supplémentaire

Dans cette première expérience :

price_return_N > 0

uniquement.

Ne pas tester simultanément :

>1%
>2%
>3%

Si la règle >0 montre déjà un signal stable, les seuils pourront constituer une expérience ultérieure séparée.