si le modèle ou l'univers change radicalement, il ne faut pas seulement recalibrer le ML ; il faut requalifier toute la chaîne qui dépend de la distribution des trades.

Je garderais cependant certaines règles comme architecture de départ plutôt que de tout remettre à zéro.

Checklist de recalibration après changement majeur modèle/univers
Bloc	À recalibrer ?	Ce qu'il faut revalider
1. Alpha / ranking ML	🔴 Oui	IC Rank, ICIR, deciles TOP/BOTTOM, stabilité temporelle, horizons H3/H5/H10/H15/H20
2. Horizon de trading	🔴 Oui	H5/H10/H15/H20 : quel horizon fournit réellement le meilleur spread net
3. Seuils de sélection	🔴 Oui	TOP/BOTTOM deciles, seuils de probabilité, nombre de candidats
4. Long vs Short	🔴 Oui	Alpha LONG et SHORT séparément, PF/WR/expectancy, comportement par régime
5. Structure du book	🔴 Oui	6L/2S n'est plus automatiquement valable : tester allocation L/S et nombre de slots
6. Nombre de positions	🔴 Oui	m8 / autres tailles, diversification vs dilution de l'alpha
7. Sizing	🔴 Oui	ATR risk, poids par trade, min/max notional
8. Gross exposure	🔴 Oui	C'est précisément E46 : retrouver la frontière efficiente Return/DD
9. Levier	🔴 Oui	Le 1.x/2x autorisé par le compte ≠ levier optimal du nouveau modèle
10. Net exposure	🔴 Oui	biais long/short approprié au nouvel alpha
11. Concentration symbole	🔴 Oui	max trades/symbole ; ton ancien résultat 3/sym ne doit pas être transféré aveuglément
12. Concentration secteur	🔴 Oui	cap secteur, corrélations du nouvel univers
13. Stops ATR	🔴 Oui	stop initial / ATR multiple selon volatilité et comportement du nouveau signal
14. Take-profit	🔴 Oui	ATR multiple, TP max %, asymétrie gain/perte
15. Time stop	🔴 Oui	20 jours peut ne plus correspondre au nouvel horizon
16. Trailing stop	🟠 Revalider	actif/inactif et paramètres ; dépend fortement du profil des gagnants
17. Coûts	🔴 Oui si univers change	spread, slippage, commission, borrow short, impact de marché
18. Liquidité	🔴 Oui si univers change	ADV, min notional, capacité, fills
19. CP-V2	🟠 Oui	Son principe peut rester, mais budgets long/short et release doivent être revalidés
20. Budgets CP par side	🔴 Oui	long/short/gross : extrêmement dépendants de la contribution des shorts
21. Release CP	🟠 Oui	J+6/hystérésis : vérifier coût 1-3j / 4-10j / >10j
22. B4 / DD breaker	🔴 Oui	−15 % ne doit pas devenir automatiquement le seuil du nouveau système
23. B4 staged éventuel	🔴 Oui	paliers 15/20/25 et expositions résiduelles si on adopte cette architecture
24. Force-close B4	🟠 Oui	KEEP vs WORST50 ; ton résultat E45 n=1 ne doit surtout pas devenir une vérité universelle
25. Recovery B4	🟠 Oui	RecoveryRatio, hystérésis, relapse et vitesse de réarmement
26. Régimes marché	🟠 Oui	vérifier que BULL/SLIDE/CORRECTION/REBOUND restent prédictifs/utiles
27. Risk factor / corrélation	🔴 Oui	beta, secteurs, facteurs, corrélation intra-book
28. Stress tests	🔴 Oui	bear lent, crash/V-recovery, coûts dégradés, CP-off, exposition élevée
29. Long-only	🔴 si compte concerné	certification séparée : ne pas réutiliser automatiquement les paramètres 6L/2S
30. Parité LIVE ↔ BT	🔴 Obligatoire	une fois le nouveau calibrage choisi, harness zéro-divergence avant activation

Mais je ne voudrais surtout pas que ton IA fasse 30 sweeps indépendants. Ce serait une énorme machine à overfitting.

Je les organiserais en 6 gates successifs.

Gate 1 — Alpha. Vérifier que le nouveau modèle produit réellement de l'alpha OOS : IC, spreads TOP/BOTTOM, long/short séparés, stabilité par période et régime. Si ça échoue, on s'arrête immédiatement. Aucun intérêt de calibrer le risk management d'un alpha mauvais.

Gate 2 — Construction du portefeuille. Déterminer horizon, sélection, L/S, nombre de positions, concentration symbole/secteur. Ici, on répond essentiellement : comment transformer les prédictions en book ?

Gate 3 — Trade management. Revalider sizing ATR, stop, TP, time-stop et coûts. L'objectif est de transformer le book théorique en trades exécutables net de coûts.

Gate 4 — Risk scaling. C'est l'équivalent de ton E46 : faire monter progressivement l'exposition et obtenir une courbe du genre :

gross → Return / DD / Sharpe / worst6m / recovery

C'est ici qu'on détermine le gross certifié et le levier, et non à partir du max_leverage=2.0 du compte.

Gate 5 — Protections catastrophe. Une fois seulement le niveau de risque choisi : CP-V2 → B4 → éventuellement B4 staged → force-close → recovery. C'est important : on calibre le breaker sur le portefeuille choisi, pas l'inverse.

Gate 6 — Qualification production. Stress tests, PIT, coûts dégradés, périodes historiques, parité backtest/live, puis éventuellement shadow/dry-run avant promotion.

Il y a également quelques éléments que je considérerais plutôt comme des invariants de sécurité : PIT/no-lookahead, coûts réalistes, contrôles de marge, fail-safe en cas de données manquantes, audit logs, limite absolue de levier broker, et principe selon lequel le nouveau modèle ne récupère jamais automatiquement le risk budget de l'ancien.

Le point le plus important

Il faudrait finalement que ton application produise quelque chose comme :

B25 + univers U1 → certification risque R25 → gross cible 85 %, book 6L/2S, B4 X, CP Y

puis, après un changement radical :

B50 + univers U2 → nouvelle certification R50 → gross cible 105 %, book 7L/1S, B4 Z, CP W

Ainsi les paramètres de risque appartiennent à la version du modèle + univers, et non à l'application entière.

Je pense que c'est une évolution importante pour α-Trade : tous les travaux que tu as faits depuis E31/E32 jusqu'à CP-V2/E45/E46 peuvent devenir progressivement un pipeline automatique de certification risque, au lieu d'être une série de tests manuels qu'il faudrait réinventer à chaque nouveau modèle.