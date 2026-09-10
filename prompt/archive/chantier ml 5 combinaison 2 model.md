Chantier research-only — global_rank_x_oracle_complementarity
0. Hypothèse correcte

Ne PAS supposer que Global Rank fournit la direction.

Les observations historiques montrent que le TOP10 Global Rank contient encore beaucoup de futurs mauvais déciles.

Interprétation :

Global Rank
= préférence / qualité relative cross-sectionnelle

Oracle Extreme
= probabilité de futur mouvement extrême D1 ∪ D10

Aucun des deux n’est un classifieur LONG propre.

Question centrale :

lorsque Global Rank et Oracle Extreme sont combinés, est-ce que leur interaction fait pencher favorablement la distribution D1→D10 ?

Hypothèses :

H0:
Oracle n’apporte aucune information marginale
conditionnellement au Global Rank,
ou vice versa.
H1:
les deux modèles contiennent des informations différentes
et leur combinaison améliore GOOD/BAD,
D10/D1, rendement futur et/ou portfolio.
1. Aucun N4X2 dans ce chantier

Désactiver :

N4X2 Global
N4X2 Oracle
N4X-2
dip_quality
dip saturated

On doit mesurer uniquement :

Global Rank × Oracle Extreme
2. Sources strictement gelées

Utiliser :

GLOBAL_BATCH_ID = <batch global gelé>
ORACLE_RUN_ID   = <run Oracle OOS gelé>

Assertions :

un seul batch Global
un seul run Oracle
unique(date,symbol)
predictions PIT/OOS
aucun mélange silencieux
3. Baselines

Construire :

G0 = Global Rank TOP10
O0 = Oracle TOP20

puis :

C1 = Global TOP10 ∩ Oracle TOP20

et :

C2 = Global TOP20,
     puis sélectionner les Oracle les plus élevés
     à l’intérieur de ce pool

Ces groupes doivent reproduire conceptuellement :

oracle_filter
oracle_pool
4. Test principal = distribution D1→D10

Pour G0/O0/C1/C2 :

n
D1
D2
...
D10

Ajouter :

BAD  = D1-D3
GOOD = D8-D10

Le test principal est :

C1/C2 vs G0

Calculer :

ΔD1
ΔBAD
ΔGOOD
ΔD10

On ne suppose aucun résultat à l’avance.

5. Question directionnelle

Vérifier explicitement :

P(D10 | Global élevé, Oracle élevé)
vs
P(D10 | Global élevé)

et :

P(D1 | Global élevé, Oracle élevé)
vs
P(D1 | Global élevé)

Si :

D10 ↑
et D1 ↓

alors la combinaison résout partiellement l’ambiguïté directionnelle.

Si :

D10 ↑
et D1 ↑

Oracle apporte surtout de l’amplitude, pas de direction.

6. Matrice 2D obligatoire

Découper Global Rank :

0.80–0.90
0.90–0.95
0.95–1.00

Oracle percentile :

0.00–0.80
0.80–0.90
0.90–1.00

Pour chaque cellule :

n
mean H5
mean H10
mean H20
P(H20>0)
BAD
GOOD
D1
D10

Question A :

à Global Rank comparable, Oracle plus élevé améliore-t-il la distribution ?

Question B :

à Oracle comparable, Global Rank plus élevé améliore-t-il la distribution ?

Cette matrice est prioritaire.

7. Analyse conditionnelle continue

Faire un diagnostic OOF/WF simple :

y_direction = 1 si H20 > 0

Comparer :

M0:
global_rank
M1:
oracle_pct
M2:
global_rank + oracle_pct
M3:
global_rank + oracle_pct
+ global_rank * oracle_pct

Utiliser uniquement LogisticRegression simple.

Ce modèle n’est PAS destiné au trading.

Il sert seulement à mesurer l’information marginale.

Reporter :

AUC OOF
IC
coefficients
signe
stabilité par fold

Test important :

AUC(M2/M3) - AUC(M0)

et :

AUC(M2/M3) - AUC(M1)
8. Same-date test

Pour chaque date où Global TOP10 contient :

Oracle élevés
ET
Oracle moins élevés

comparer dans la même journée :

H20
P>0
BAD
GOOD

Cela évite de confondre :

effet Oracle

avec :

effet régime/date.
9. Breadth

Pour chaque groupe :

candidates/day
median
P10/P90
days with 0
days with <4
days with <8

Très important :

une meilleure qualité qui détruit la breadth peut être inutilisable en portefeuille.

C’est une leçon déjà observée sur Oracle N4X2.

10. Overlap / redondance

Calculer :

corr(global_rank, oracle_pct)
Spearman
Jaccard TOP sets
P(OracleTOP20 | GlobalTOP10)
P(GlobalTOP10 | OracleTOP20)

Si les deux modèles choisissent presque toujours les mêmes titres et que l’information marginale est faible :

NO_GO_REDUNDANT
11. Analyse par année

Produire toutes les métriques pour :

2022
2023
2024
2025
2026

selon disponibilité PIT/OOS.

Le gain de combinaison doit exister sur plusieurs périodes.

12. Régime = diagnostic seulement

Ne pas créer de stratégie régime dans ce chantier.

Découper simplement par régimes déjà définis dans le repo :

bull
normal
stress tradable

Vérifier si la complémentarité est :

stable
ou
regime-dependent

Aucun seuil ne doit être retuné.

13. Gate avant portfolio

Un mode combiné ne passe au backtest que s’il montre au signal-level :

GOOD ↑ ou BAD ↓
mean H20 >= baseline
P>0 >= baseline
breadth suffisante
stabilité multi-périodes

Sinon :

NO_GO_SIGNAL
14. Backtests candidats

Si gate signal passé :

P0 = ml
P1 = oracle_filter
P2 = oracle_pool

oracle_rerank uniquement après audit de sa formule.

extreme_gate reste une baseline Oracle indépendante.

15. Audit oracle_rerank

Vérifier :

pool = Global TOP10
score = oracle_pct * pred.long_prob

Question :

une fois dans le pool, Global Rank intervient-il encore dans l’ordre ?

Si non, documenter que ce mode est plutôt :

Global = gate
Oracle/per-symbol = ranking

et non une vraie fusion équilibrée.

16. Portfolio PROD-parity

Utiliser exactement le même :

capital
max positions
sector cap
risk
sizing
entry
exits
costs
regimes
lifecycle

Seul cascade_rank_mode varie.

17. Attribution

Comparer chaque mode à P0 :

trades communs
ajoutés
retirés

Puis :

PnL ajoutés
PnL retirés
marginal PnL after costs

Question :

l’Oracle fait-il réellement remplacer de mauvais candidats Global par de meilleurs ?

18. Critères GO
GO_GLOBAL_ORACLE_COMBO

seulement si :

information marginale signal-level réelle
+
breadth acceptable
+
PnL net > baseline
+
Sharpe > baseline
+
PF >= baseline
+
DD non matériellement pire
+
stabilité temporelle
19. Verdicts possibles
GO_GLOBAL_ORACLE_COMBO
SIGNAL_GO_PORTFOLIO_NO_GO
NO_GO_REDUNDANT
NO_GO_GLOBAL_ORACLE_COMBO
REGIME_DEPENDENT_SIGNAL
INVALID_RUN
20. Interdiction de tuning

Ne pas faire ensuite :

Oracle threshold 0.75/0.80/0.85/0.90
Global pool 10/15/20/25%
poids multiplicatifs divers

Les paramètres actuels sont gelés pour cette étude.

Le but est de tester la complémentarité, pas d’optimiser une combinaison.

Oui, cette version est meilleure : elle ne suppose plus que Global Rank sait donner la direction. Elle demande justement aux données de montrer si la combinaison Global Rank + Oracle réduit l’ambiguïté D1/D10.