# Protections OCO, break-even, trailing et watcher

Retour : [références Execution](README.md)

Le `ProtectionContract` décrit SLA, stop/TP et état attendu. `build_oco_group` relie les enfants ; `check_protection_state` vérifie couverture et cohérence. Les enfants sont soumis après fill et leur quantité ne dépasse jamais la position.

`protection_watcher.py` synchronise positions/ordres, identifie protections manquantes/orphelines, applique transitions break-even/trailing et écrit heartbeat/événements. Il ne sélectionne pas de nouveaux trades.

`protection_break_even.py` évalue le progrès minimal. `protection_transition.py` calcule le nouvel état ; `protection_state_bridge.py` assure la persistance. Le peak, le côté, le moment d'activation et le previous peak font partie du contrat.

Une position manuelle peut être adoptée seulement si politique active, compte correct et stop dédié. En live, watcher malsain est un probe critique. Toute analyse doit distinguer protection configurée, soumise, acceptée et effectivement active.

