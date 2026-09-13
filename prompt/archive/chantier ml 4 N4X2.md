Chantier research-only — oracle_extreme_continuation
0. Contexte gelé

Oracle Extreme prédit :

P(futur H20 dans D1 ∪ D10 | features PIT à J)

donc amplitude extrême, pas direction.

Le backtest A/B propre a montré :

Extreme Gate sans DIP : +25.72%
Extreme Gate + N4/X2 :  -3.98%

Conclusion déjà acquise :

Oracle + N4/X2 = NO-GO

Ne pas retuner N4/X2.

1. Question unique

Tester si le mouvement initial du prix permet de résoudre partiellement l’ambiguïté directionnelle de l’Oracle.

Hypothèse :

proba_extreme élevée
+ persistance
+ hausse récente
=>
probabilité accrue d'être futur D8-D10 / D10
et meilleure stratégie LONG
2. Paramètres gelés

Utiliser :

N = 4
percentile proba_extreme >= 0.90
X = 2%

Sémantique :

N4 =
percentile(proba_extreme) >= 0.90
à J, J-1, J-2, J-3

Prix :

ret_4 =
close[J] / close[J-4] - 1

Ne tester aucun autre N/X/seuil.

3. Quatre groupes

Construire exactement :

E0 = Oracle TOP10 actuel
     aucune persistance obligatoire
     aucune condition prix
E1 = Oracle N4
     persistance TOP10 4 jours
     aucune condition prix
E2 = Oracle N4 + FORCE
     N4
     AND ret_4 >= +2%
E_NEG = Oracle N4 + DIP
        N4
        AND ret_4 <= -2%

E_NEG est uniquement un contrôle négatif.

Ne pas optimiser cette branche.

4. Étude signal-level avant tout backtest

Pour E0/E1/E2/E_NEG, mesurer :

n events
n dates
n symbols
mean H5
mean H10
mean H15
mean H20
median H20
P(H20 > 0)

Et surtout distribution réalisée :

D1
D2
D3
D4
D5
D6
D7
D8
D9
D10

Ajouter :

BAD = D1-D3
GOOD = D8-D10
extreme_realized = D1 ∪ D10
5. Test central directionnel

Comparer :

E2 vs E1

pour savoir si la hausse +2% ajoute réellement une information directionnelle.

Calculer :

ΔP(D10)
ΔP(D8-D10)
ΔP(D1)
ΔP(D1-D3)
Δmean_H20
ΔP(H20>0)

Résultat recherché :

E2 :
D10 ↑
GOOD ↑
D1 ↓
BAD ↓
mean_H20 ↑

Si E2 augmente seulement D1+D10 sans déplacer le ratio vers D10, alors la confirmation prix n'apporte pas réellement de direction.

6. Test de persistance

Comparer :

E1 vs E0

Question :

la persistance 4 jours de proba_extreme apporte-t-elle quelque chose ?

Mesurer :

enrichment D1+D10
mean H20
P>0
GOOD/BAD

Si E1 < E0, conclure :

Oracle persistence N4 = NO-GO

même si E2 semble ponctuellement intéressant.

7. Contrôle négatif

Vérifier que :

E_NEG

reproduit bien l'échec observé de N4/X2.

Cela sert à valider que le dataset/semantics du diagnostic correspond au backtest précédent.

Ne pas chercher à améliorer E_NEG.

8. Analyse par année

Produire E0/E1/E2/E_NEG pour :

2022
2023
2024
2025
2026

ou toutes les périodes disponibles en PIT propre.

Pour chaque année :

n
mean H20
P>0
D1
D10
BAD
GOOD

Vérifier notamment si E2 :

fonctionne certaines années
et échoue fortement d'autres années

Ce diagnostic déterminera si un chantier régime est justifié.

9. Analyse par régime — DIAGNOSTIC uniquement

Ne construire aucune stratégie dynamique à ce stade.

Utiliser seulement des variables PIT fiables :

SPY > SMA200
SPY ret60
breadth_above_sma50

VIX uniquement si coverage valide sur toute la période.

Régimes diagnostics pré-spécifiés :

STRONG_BULL:
SPY > SMA200
AND SPY_ret60 > +3%
AND breadth_above_sma50 >= 0.60
NORMAL_BULL:
SPY > SMA200
AND NOT STRONG_BULL
WEAK:
SPY <= SMA200

Toujours :

allow_new_entries == True

Exclure close_only/cash_only.

10. Matrice régime × E2

Pour chaque régime, comparer :

E0
E1
E2

Mesurer :

n
mean H20
P>0
D1
D10
BAD
GOOD

Question :

la confirmation haussière E2 est-elle particulièrement efficace en STRONG_BULL ?

On cherche un motif du type :

STRONG_BULL:
E2 >> E0

NORMAL/WEAK:
E2 <= E0

mais ne pas changer les seuils de régime selon les résultats.

11. Same-date comparison

Quand E0 contient simultanément :

candidats E2
et candidats non-E2

comparer sur la même date :

mean H20 E2
vs
mean H20 autres Oracle TOP10

Cela permet d'éviter qu'E2 semble bon simplement parce qu'il apparaît dans de meilleures périodes de marché.

Reporter :

paired dates
mean paired spread
median paired spread
fraction dates E2 > others
12. Pas de ML

Aucun modèle supplémentaire dans cette étude :

pas LightGBM
pas Logistic
pas direction model
pas LSTM

On teste uniquement la structure économique :

Oracle amplitude
× confirmation prix
× régime
13. Gate avant backtest

Lancer le vrai backtest E2 uniquement si :

E2 > E1 sur mean H20
E2 GOOD > E1 GOOD
E2 BAD < E1 BAD
E2 P(H20>0) > E1

et si ces améliorations ne proviennent pas d'une seule année.

Sinon :

NO_GO_ORACLE_CONTINUATION

et stopper.

14. Backtest PROD-parity si signal GO

Comparer uniquement :

P0 = Extreme Gate actuel, aucun N4
P1 = Extreme Gate + N4 persistence only
P2 = Extreme Gate + N4 + hausse >=2%

Même moteur :

mêmes scores Oracle
même batch ce6d09
même cascade
même risk
même sizing
même max positions
mêmes coûts
même slippage
même entry
mêmes TP/stops/trailing
mêmes force-close
mêmes régimes

La seule différence est le gate E0/E1/E2.

15. Métriques portfolio

Utiliser la source comptable réellement autoritative.

Vu l'incohérence actuelle :

trades.csv != report.json/equity_curve

documenter explicitement quelle source est utilisée.

Avant toute conclusion fine, expliquer pourquoi trades.csv ne réconcilie pas avec le PnL portfolio.

Reporter :

Total Return
Net PnL
Sharpe
Sortino
MaxDD
PF
Win Rate
trades
turnover
costs
exposure
avg positions
entries/day
average holding period
stop count
force-close count
16. Analyse du churn

Puisque N4/X2 avait :

moins de candidats
MAIS plus de trades

mesurer pour E0/E1/E2 :

candidates/day
entries/day
trades
median holding period
exits by reason
re-entry rate
turnover
costs

Déterminer si E2 crée :

meilleure sélection

ou simplement :

davantage de turnover/churn
17. Critère GO Oracle continuation

Verdict :

GO_ORACLE_CONTINUATION

uniquement si E2 :

améliore la direction D10 vs D1 au signal-level
+
améliore le portefeuille net vs E0
+
Sharpe/PF non dégradés
+
DD acceptable
+
effet présent sur plusieurs périodes
18. Si E2 dépend fortement du régime

Si :

E2 excellent en STRONG_BULL
mais mauvais en NORMAL/WEAK

ne pas déclarer GO global.

Verdict :

REGIME_DEPENDENT_SIGNAL

et seulement alors ouvrir un nouveau chantier séparé :

oracle_regime_selector

avec règle pré-enregistrée.

19. NO-GO

Si E2 :

ne réduit pas D1
ne monte pas D10
reste instable par année
ou portfolio <= E0

alors :

NO_GO_ORACLE_CONTINUATION

Ne pas tester X=1%, 3%, N=3/5, percentile=80/85/etc.

20. Livrables

Produire :

oracle_continuation_events.csv
oracle_continuation_deciles.csv
oracle_continuation_summary.csv
oracle_continuation_by_year.csv
oracle_continuation_by_regime.csv
oracle_continuation_same_date.csv
oracle_continuation_churn.csv

Si backtest :

oracle_continuation_portfolio.csv
oracle_continuation_attribution.csv

Rapport final :

oracle_continuation_report.md

Verdict obligatoire parmi :

GO_ORACLE_CONTINUATION
REGIME_DEPENDENT_SIGNAL
NO_GO_ORACLE_CONTINUATION
INVALID_RUN

La différence essentielle avec mon ancien prompt est donc : on ne cherche plus tout de suite une stratégie dynamique de régime. On teste d’abord si Oracle + N4 + hausse ≥2% transforme réellement l’Oracle symétrique D1/D10 en signal davantage orienté D10. Si oui mais uniquement dans certains régimes, alors seulement on ouvre le chantier régime.