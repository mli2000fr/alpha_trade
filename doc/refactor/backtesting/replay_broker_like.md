# Architecture de replay broker-like

Retour : [références Backtesting](README.md)

Le replay reproduit les couches, pas seulement les rendements. `signal_replay` produit les candidats ; `risk_bridge` appelle le contrat portefeuille ; `execution_replay` simule tentatives/fills ; `execution_lifecycle_replay` crée les protections ; `protection_watcher_replay` déclenche leurs transitions ; `exit_lifecycle_replay` produit les sorties.

Chaque phase normalise ses frames et sauvegarde des artefacts. Pour diagnostiquer une divergence, comparer : candidats, entries, intents, fills, enfants, triggers, exits, puis positions. Le premier écart est la cause probable ; le PnL n'est que la conséquence.

La date de décision et la date d'exécution sont séparées. Les barres utilisées pour les features s'arrêtent au cutoff. Les positions initiales, cash, corporate actions et régime doivent être identiques au scénario comparé.

`execution_broker_like.py` calcule des compteurs d'états/événements par séance. Un fill synthétique doit respecter quantité, liquidité, gap et prix définis par microstructure.

