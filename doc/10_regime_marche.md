# Régime de marché

Le moteur `service/market/` produit un `MarketRegimeSnapshot` injecté au risque et au backtest. Il est conçu avec providers injectables pour conserver les mêmes règles entre live et replay.

## Modes

Du moins au plus restrictif : `normal`, `capital_preservation`, `close_only`, `cash_only`. Quand plusieurs signaux se déclenchent, le moteur conserve le mode le plus restrictif.

Le mode brut exprime les signaux du jour ; le mode final peut rester plus défensif à cause de l’hystérésis. `why` et la trace structurée expliquent source, valeur, seuil, mode suggéré et priorité. Ne pas reconstruire l’explication depuis le seul nom du mode.

## Sources de signaux

- VIX et VIX9D : niveau et inversion de courbe ;
- VXN, VIX3M, MOVE et RVX selon activation ;
- variation du taux US 10Y ;
- sentiment agrégé warning/critical ;
- patterns calendaires ;
- earnings shield ;
- qualité/disponibilité des données macro.

Les providers macro supportés sont configurables (`stooq`, `eodhd`, `composite`, `none`; FRED est utilisé pour certaines séries). Une donnée obligatoire absente peut lever `MacroDataUnavailableError` selon la politique, plutôt que produire un faux régime normal.

`MacroDataProvider` définit VIX, volatilité court terme, VXN, VIX3M, MOVE, RVX et historique US10Y. Les implémentations comprennent Stooq, EODHD, FRED, composite, routage par signal et table-first avec fallback réseau. Le summary conserve la source effective par signal.

Le mode PIT macro peut imposer une lecture strictement antérieure à la date de décision. Une valeur publiée/révisée après le cutoff ne doit pas être utilisée rétroactivement. Le remplissage de `stock_macro_indicators_daily` et le recalcul du régime sont exposés par `python -m service.market`.

Le sentiment vient d’un provider DB et produit niveaux normal/warning/critical. Les patterns calendrier incluent notamment troisième vendredi et fenêtre de fin de mois selon configuration. L’earnings shield produit aussi une contrainte par symbole ; il ne doit pas être confondu avec un stress macro global.

## Hystérésis

`regime_manager.py` maintient un état : mode courant/précédent, date d'entrée, streaks soft/hard, jours dans le mode et jours de release. Les signaux soft peuvent demander plusieurs confirmations ; les hard triggers peuvent agir immédiatement. Cela évite des bascules quotidiennes instables.

Les paramètres parsés bornent au minimum : nombre de sources soft, jours de confirmation d’entrée, maximum soft pour sortir, jours de confirmation de sortie, durée minimale défensive, immédiateté hard et jours calmes hard. Des flags peuvent retarder séparément contraintes, multiplicateur, limites de positions, caps d’exposition et blocages secteur jusqu’à confirmation.

Avec hystérésis désactivée, le mode brut devient final et l’état est néanmoins mis à jour. Avec hystérésis active, une escalade hard peut être immédiate ; une désescalade attend durée minimale et streaks de calme. Persister l’état entre runs est indispensable : le recalcul isolé d’un jour ne reproduit pas la transition.

## Capital preservation CP-V2

La configuration distingue plafond long, réserve short, exposition gross totale et délai de release. En CP-V2, le sleeve long est réduit tandis qu'une capacité short peut rester réservée dans le gross. La sortie du mode suit un nombre fixe de séances après le dernier signal selon l'état de release.

`capital_preservation_policy` distingue le comportement legacy de `cp_v2`. Les champs long/short ne s’appliquent que sous la politique prévue. À la sortie de CP, le compteur de release est réarmé par un nouveau signal et décrémenté en séances, pas en jours calendaires.

## Application au portefeuille

Le snapshot fournit contraintes, multiplicateurs de risque, secteurs bloqués, nombre/poids/exposition maximum et trace `why`. `risk_management/regime_apply.py` les applique aux candidats. `regime_state_machine.py` et `transition_handler.py` gèrent les transitions de portefeuille existant.

`apply_structural_market_guards` et `apply_snapshot` resserrent la configuration ; ils ne doivent jamais élargir une limite déjà plus restrictive. `apply_account_cp_policy` tient compte des capacités du compte.

La state machine Risk distingue escalade et désescalade et associe une action : maintenir, réduire, close-only ou cash-only. `TransitionHandler` construit un plan ordonné sur positions et ordres ouverts. Les étapes destructives sont identifiables ; le plan doit être audité avant exécution et rester idempotent.

| Mode | Nouvelles entrées | Positions existantes |
|---|---|---|
| normal | selon règles usuelles | suivi normal |
| capital_preservation | budgets réduits/side-aware | réduction éventuelle |
| close_only | bloquées | sorties et protections seulement |
| cash_only | bloquées | liquidation/aucune nouvelle exposition selon plan |

## Parité

Le contexte `live` ou `backtest` peut choisir des valeurs spécifiques, mais les règles partagées restent les mêmes. Le backtest doit persister le snapshot et ses raisons pour permettre un audit. Un régime reconstruit après coup avec des séries révisées n'est pas automatiquement PIT.

Les defaults hard peuvent différer : certaines configurations proposent `close_only` en live et `cash_only` en backtest. Cette différence doit être visible dans la configuration effective ; elle empêche de comparer directement deux résultats sans diff.

## Échec et fallback

Une source absente peut être non critique, déclencher un fallback ou bloquer selon `macro_data_quality` et les signaux requis. Le fallback conserve la source effective. « Donnée manquante = signal non déclenché » n’est acceptable que si la politique le prévoit explicitement.

Le cache de snapshot inclut date, contexte, configuration et état précédent. Après modification de configuration ou dans les tests, utiliser le reset prévu plutôt que réutiliser un snapshot mis en cache.

## Tests et diagnostic

Tester chaque seuil juste dessous/dessus, combinaison de modes, provider manquant, source fallback, strict-before, signal hard, confirmation soft, durée minimale, sortie hard, CP-V2 et release, compte long-only, mode live/backtest et persistance d’état.

| Symptôme | Vérification |
|---|---|
| mode trop défensif | raw mode, état précédent, hold/streak/release |
| mode normal avec données absentes | qualité requise et politique fail-closed |
| backtest ≠ live | contexte, provider PIT et seuil hard |
| exposition trop basse | snapshot, CP-V2, caps déjà plus stricts |
| transition répétée | état persisté, idempotence du plan et ordres ouverts |
