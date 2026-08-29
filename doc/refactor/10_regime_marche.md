# Régime de marché

Le moteur `service/market/` produit un `MarketRegimeSnapshot` injecté au risque et au backtest. Il est conçu avec providers injectables pour conserver les mêmes règles entre live et replay.

## Modes

Du moins au plus restrictif : `normal`, `capital_preservation`, `close_only`, `cash_only`. Quand plusieurs signaux se déclenchent, le moteur conserve le mode le plus restrictif.

## Sources de signaux

- VIX et VIX9D : niveau et inversion de courbe ;
- VXN, VIX3M, MOVE et RVX selon activation ;
- variation du taux US 10Y ;
- sentiment agrégé warning/critical ;
- patterns calendaires ;
- earnings shield ;
- qualité/disponibilité des données macro.

Les providers macro supportés sont configurables (`stooq`, `eodhd`, `composite`, `none`; FRED est utilisé pour certaines séries). Une donnée obligatoire absente peut lever `MacroDataUnavailableError` selon la politique, plutôt que produire un faux régime normal.

## Hystérésis

`regime_manager.py` maintient un état : mode courant/précédent, date d'entrée, streaks soft/hard, jours dans le mode et jours de release. Les signaux soft peuvent demander plusieurs confirmations ; les hard triggers peuvent agir immédiatement. Cela évite des bascules quotidiennes instables.

## Capital preservation CP-V2

La configuration distingue plafond long, réserve short, exposition gross totale et délai de release. En CP-V2, le sleeve long est réduit tandis qu'une capacité short peut rester réservée dans le gross. La sortie du mode suit un nombre fixe de séances après le dernier signal selon l'état de release.

## Application au portefeuille

Le snapshot fournit contraintes, multiplicateurs de risque, secteurs bloqués, nombre/poids/exposition maximum et trace `why`. `risk_management/regime_apply.py` les applique aux candidats. `regime_state_machine.py` et `transition_handler.py` gèrent les transitions de portefeuille existant.

## Parité

Le contexte `live` ou `backtest` peut choisir des valeurs spécifiques, mais les règles partagées restent les mêmes. Le backtest doit persister le snapshot et ses raisons pour permettre un audit. Un régime reconstruit après coup avec des séries révisées n'est pas automatiquement PIT.

