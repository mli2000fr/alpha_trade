# Sizing, ATR, Kelly, liquidité et levier

Retour : [références Risk](README.md)

`StopCalculator` produit `StopLevels` et valide qu'un stop long est sous l'entrée et un stop short au-dessus. Le risque par action est la distance absolue entrée-stop. `PositionSizer` divise le budget de perte par cette distance puis applique limites de poids et quantités.

`KellySizer` estime une fraction depuis win rate/payoff, gère les fallbacks configurés et borne le résultat. Kelly module un budget ; il ne remplace pas les caps. `capacity.py` et `liquidity.py` bornent participation, ADV, spread/slippage et borrow. `PreSubmissionGate` revérifie ces données juste avant envoi, car elles peuvent se dégrader après la décision.

Le levier Reg-T exige feature active, compte margin si requis, equity minimale, mode d'entrée autorisé et régime compatible. Le code borne à 2x. Le buying power effectif est lu selon priorité de champs et le minimum entre broker/caps gagne. Champ absent : désactivation ou fallback défensif selon config.

Après arrondi fractionnaire, recalculer notionnel, risque et limites. ATR nul/non fini, stop invalide, quantité sous minimum ou capacity nulle produisent un rejet explicite.

