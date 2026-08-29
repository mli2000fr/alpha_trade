# Pré-live et montée progressive du capital

## Deux niveaux

`execution_engine/preflight.py`, appelé par `scripts/run_pre_live_checklist.py`, vérifie l’environnement courant. `risk_management/pre_live_checklist.py` formalise les gates de gouvernance shadow, paper et live progressif. L’un ne remplace pas l’autre.

## Rapport exécutable

`python scripts/run_pre_live_checklist.py --account <compte> --broker-mode live` exécute le preflight, ajoute commit, empreinte de configuration, hôte et utilisateur, puis écrit `artifacts/pre_live_checks/<UTC>_<compte>.json`. Code 0 si passé, 1 sinon. `--skip-network` réduit la preuve ; l’âge maximal du dry-run vaut 24 h par défaut.

Vérifier aussi sauvegarde restaurable, compte/mode, dry-run, drift, watcher, protections, kill switch, locks pipeline, alerting et disponibilité opérateur.

## Gates de gouvernance

Les gates canoniques couvrent parité/recherche, calibration, PIT/survivorship, labels, benchmark, contrat ML→risque, caps/ADV/fingerprint, walk-forward/holdout, edge/abstention, régime, borrow, contraintes/turnover, protections/OCO, registry/fraîcheur/drift/rollback et opérations.

`FAILED` bloque et `PENDING` avertit ; le GO exige zéro bloquant et zéro pending. Les paliers connus sont `shadow`, `paper`, puis `live_5pct`, `10pct`, `25pct`, `50pct`, `100pct`. Le code ne mesure pas automatiquement les durées mentionnées dans ses docstrings.

## NO-GO

- identité/mode/secrets incohérents ;
- audit, sauvegarde ou réconciliation non fiables ;
- position sans protection ;
- donnée critique périmée ou univers non PIT ;
- drift sévère, modèle non promu ou fingerprint inattendu ;
- breaker/kill switch/failover actif ;
- gate bloquante ou pending non résolue.

Après séance, réconcilier, archiver le rapport, attribuer les anomalies et ne monter de palier qu’après observation suffisante.

