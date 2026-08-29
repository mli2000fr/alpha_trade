# Sizing, ATR, Kelly, liquidité et levier

Retour : [références Risk](README.md)

`StopCalculator` produit `StopLevels` et valide qu'un stop long est sous l'entrée et un stop short au-dessus. Le risque par action est la distance absolue entrée-stop. `PositionSizer` divise le budget de perte par cette distance puis applique limites de poids et quantités.

`KellySizer` estime une fraction depuis win rate/payoff, gère les fallbacks configurés et borne le résultat. Kelly module un budget ; il ne remplace pas les caps. `capacity.py` et `liquidity.py` bornent participation, ADV, spread/slippage et borrow. `PreSubmissionGate` revérifie ces données juste avant envoi, car elles peuvent se dégrader après la décision.

Le levier Reg-T exige feature active, compte margin si requis, equity minimale, mode d'entrée autorisé et régime compatible. Le code borne à 2x. Le buying power effectif est lu selon priorité de champs et le minimum entre broker/caps gagne. Champ absent : désactivation ou fallback défensif selon config.

Après arrondi fractionnaire, recalculer notionnel, risque et limites. ATR nul/non fini, stop invalide, quantité sous minimum ou capacity nulle produisent un rejet explicite.

## Entrées du sizing

Le calcul reçoit au minimum equity, cash/buying power, prix d'entrée, ATR/stop, côté, conviction, limites de poids, liquidité et état de régime. Les positions existantes réduisent la capacité disponible. Une equity de config n'est pas interchangeable avec l'equity broker en paper/live.

## StopCalculator

`compute_initial_stop_price` expose le calcul fonctionnel et `is_stop_valid` vérifie la géométrie. `StopLevels` conserve niveaux/raisons. Les distances peuvent dépendre du côté et de paramètres ATR/risk. Le stop doit rester positif et du bon côté de l'entrée.

Un gap d'entrée peut rendre le stop calculé à la décision trop proche ou déjà franchi. Le pre-submission/execution gap gate doit alors rejeter/recalculer selon contrat, pas envoyer un ordre avec risque différent sans nouvelle décision.

## PositionSizer

Le budget initial est un pourcentage de l'equity. La quantité basée risque est `risk_budget_usd / stop_distance_usd`. Le cap poids est `equity * max_weight / price`. Le résultat prend le minimum avec capacité, buying power et autres caps, puis normalise la quantité.

Le `SizingResult` doit permettre de voir méthode, quantité, risque et limites actives. Une quantité réduite par cap n'est pas une erreur ; une quantité zéro doit porter une raison.

## Kelly détaillé

La fraction Kelly théorique dépend de probabilité de gain et ratio gain/perte. Le code fournit `compute_kelly_fraction` et `compute_kelly_shares`, puis applique limites/fractionnement. Les sources de win rate vivent dans les structures `WinRateInfo` et `DirectionalWinRateInfo`.

Si l'historique directionnel est indisponible, le fallback défini par `KellyFallback` s'applique. L'échantillon, la direction et la calibration doivent correspondre ; utiliser le win rate long pour un short est invalide.

## Edge

`edge.py` calcule `DirectionalEdgeEstimate` à partir de trades ou statistiques. L'edge sert à moduler/rejeter, mais reste soumis aux caps. Un edge négatif ou incertain peut provoquer abstention. Conserver méthode, taille d'échantillon et fallback.

## Liquidité

`SpreadSnapshot` conserve bid/ask/spread/fraîcheur. `BorrowSnapshot` qualifie la disponibilité short. `ParticipationLimit` borne la part d'ADV. `SlippageEstimator` estime l'impact. `LiquidityGate` produit un résultat structuré avant entrée.

`PreSubmissionGate` refait un contrôle proche de l'envoi. `_borrow_degraded` détecte une détérioration entre décision et submit. Une quote plus ancienne que le seuil ou un borrow devenu unavailable doit bloquer selon côté/politique.

## Capacité

La capacité ne se limite pas à ADV moyen : elle tient compte du dollar volume, de la participation maximale et éventuellement du nombre de jours pour liquider. Le poids autorisé est le minimum des contraintes. Une source IEX biaisée doit être identifiée dans la qualité plutôt que compensée par un multiplicateur caché.

## Quantités fractionnaires

`normalize_share_quantity` arrondit à la précision projet. `is_effectively_integer_quantity` aide pour order types non fractionnaires. `format_share_quantity` évite les représentations flottantes trompeuses. Après normalisation, vérifier que la quantité n'excède aucune limite par effet d'arrondi.

## Politique de levier

Le levier notionnel max est borné à 2,0. Conditions : enabled, mode `regt_swing`, equity min, margin si requis, entry mode et capital preservation. `max_leverage=1` revient à aucun levier additionnel.

La priorité des champs buying power vient de la configuration. Un champ doit être positif et cohérent. Le plafond final est le minimum du buying power broker et de `equity * max_leverage`, après engagements/positions. Ne pas utiliser day-trading buying power pour un swing overnight si le contrat demande Reg-T.

## Exemple conceptuel

Avec equity 100k, risque position 0,5 % = 500, entrée 50 et stop 47,50, la quantité risque brute est 200 actions. Si le cap poids 8 % autorise 160, et la capacité 120, la quantité avant arrondi est 120. La perte théorique au stop est 300, sous le budget ; elle ne doit pas être remontée à 200 pour « consommer » le budget.

## Configuration à tracer

Risque par trade, stop ATR, caps position/secteur/gross, Kelly method/fraction, participation, spread max/âge, borrow, fractional, leverage enabled/mode/max/min equity/require margin/entry mode/CP et champs buying power.

## Erreurs et reprise

| Erreur | Traitement |
|---|---|
| equity indisponible live | blocage, aucun fallback 100k |
| ATR nul | rejet données/stop |
| stop mauvais côté | rejet invariant |
| quote stale | rejet ou dégradation configurée |
| borrow dégradé short | blocage pre-submit |
| buying power absent | désactivation/fallback défensif configuré |
| quantité sous minimum | rejet/no target |
| arrondi dépasse cap | arrondir vers le bas et revérifier |

## Tests

Long/short, prix/ATR limites, Kelly fallbacks, capacity min, quote age, borrow transitions, fractional, equity minimum, margin false, CP, champ buying power manquant, cap 2x et positions existantes.
