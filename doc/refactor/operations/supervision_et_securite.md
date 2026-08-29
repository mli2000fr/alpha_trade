# Supervision, notifications et sécurité

Retour : [IHM et opérations](../16_ihm_et_operations.md)

La supervision agrège run summaries, processus, logs, métriques, watcher, provider/DB et réconciliation. `ops_supervision.py`, `watcher_runtime.py` et `sandbox_health_loader.py` exposent ces états. Prometheus/Grafana complètent l'IHM.

`security.py` limite réseau/chemins et masque les secrets. Les commandes sont construites depuis options validées, pas concaténées depuis texte libre. Les credentials restent variables d'environnement. DB admin et actions financières/destructives exigent intention explicite.

`email_notifier.py` envoie les résultats selon préférences SMTP ; une panne email ne transforme pas un run métier réussi en échec, mais doit être visible. Ne jamais inclure secret ou payload broker complet.

Runbook : vérifier lock/PID avant relance, conserver stdout/stderr, identifier première étape failed, reprendre idempotemment, puis contrôler les tables et summaries. Un processus terminé sans summary final est suspect.

