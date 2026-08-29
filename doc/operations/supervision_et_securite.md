# Supervision, notifications et sécurité

Voir aussi [failover broker](broker_failover.md), [pré-live](pre_live_et_progression.md) et [sandbox health](sandbox_health.md).

Retour : [IHM et opérations](../16_ihm_et_operations.md)

## Modèle de supervision

La supervision combine processus locaux, résultats métier persistés, santé des dépendances et état broker. Aucun signal isolé ne suffit : un PID vivant ne prouve pas qu’un import progresse, un code retour nul ne prouve pas qu’un univers full a été publié et une DB disponible ne prouve pas que ses données sont fraîches.

`ops_supervision.py`, `process_registry.py`, `watcher_runtime.py`, `sandbox_health_loader.py` et les loaders de summaries exposent ces états. Prometheus/Grafana les complètent lorsqu’ils sont installés.

## Accès à l’IHM

`ihm/services/security.py` fournit des protections simples, optionnelles :

- `IHM_AUTH_TOKEN` active un token partagé, mémorisé dans la session Streamlit ;
- `IHM_REQUIRE_LOCALHOST=1|true|yes|on` exige une écoute loopback ;
- `STREAMLIT_SERVER_ADDRESS` indique l’adresse examinée ;
- sans adresse explicite, le code suppose le défaut local de Streamlit ;
- une écoute non locale sans token déclenche une alerte.

Ce n’est pas une IAM multi-utilisateur : aucun rôle, aucune identité nominative ni révocation individuelle. Une exposition réseau nécessite proxy/TLS, filtrage réseau et authentification adaptés. En local, définir les deux variables puis lancer Streamlit avec `--server.address=localhost`.

## Secrets et surfaces sensibles

Les credentials DB, brokers et providers restent dans l’environnement ou un gestionnaire de secrets. Les logs et notifications masquent clés API, tokens, mots de passe, cookies, paramètres sensibles d’URL et DSN complet. `_http_retry.py` expurge les clés de query sensibles de ses messages.

Ne pas notifier le payload complet d’un ordre, les headers HTTP, une URL signée ou un traceback contenant un secret. Les exports de logs sont aussi sensibles que la console.

## Processus, locks et rétention

Le lock pipeline/backtest protège les tables et artefacts partagés. Avant relance :

1. lire scope, run id, owner et PID ;
2. vérifier vie et date de création du processus ;
3. inspecter sorties et dernier summary ;
4. laisser le code récupérer les locks stale ;
5. ne supprimer manuellement qu’après exclusion de toute écriture active.

Le registre conserve commande, statut, durée et sorties. `IHM_RUNS_RETENTION_DAYS` pilote la rotation des artefacts locaux. Cette rotation ne doit pas supprimer événements d’exécution, summaries DB ou chaîne d’audit.

## Matrice de santé

| Domaine | Signaux | Blocage typique |
|---|---|---|
| données | date, couverture, sanitizer, source | stale ou univers non full |
| ML | champion, batch/horizon, couverture | modèle absent/incompatible |
| risque | rejets, targets, circuit | absence de target inexpliquée |
| exécution | orders, fills, positions, réconciliation | divergence cash/position |
| watcher | heartbeat, protections, erreurs | watcher malsain en live |
| DB | pool, latence, migration | schéma en retard/saturation |
| provider | erreurs, retry, quota, circuit | quota épuisé/circuit ouvert |

## Notifications

`email_notifier.py` applique les préférences SMTP. Une panne email ne transforme pas automatiquement un run métier réussi en échec, mais reste un incident visible. La réception d’un email ne prouve pas non plus que les contrôles aval sont passés.

Une notification utile indique environnement, compte non secret, date, run id, statut, première erreur, conséquence et emplacement du détail. Dédupliquer les alertes pour éviter une tempête lors d’une panne provider.

## Runbooks

### Processus terminé sans summary

Conserver stdout/stderr, relever le code retour, rechercher la dernière écriture, vérifier transaction et exception, puis établir si la reprise est idempotente. Ne pas déclarer un succès sur la seule absence d’exception visible.

### Pipeline apparemment figé

Vérifier dernière progression, latence DB/provider, quota, circuit HTTP, sous-processus et lock. Un retry/backoff peut sembler immobile ; comparer la durée aux timeouts avant interruption.

### Divergence broker/base

Suspendre les nouvelles actions financières, prendre un snapshot broker, lancer la réconciliation canonique, classer les écarts et vérifier ids client/broker. Ne pas corriger directement les positions sans reconstruire orders, fills et lots.

### Mauvaise configuration live

Conserver commande et config effective, stopper avant envoi si possible, identifier compte/mode/date/provider et invalider le run. La reprise crée un nouveau run id avec paramètres corrigés.

## Tests attendus

La sécurité couvre token absent/présent/invalide, session validée, loopback et adresse exposée. Les locks couvrent conflit, release idempotent, PID mort, fichier corrompu, PID réutilisé et lock orphelin. La supervision couvre running/failed/completed, logs tronqués, summary absent et rotation.

## Checklist quotidienne

1. Confirmer date de marché et provider.
2. Vérifier fraîcheur, sanitizer et univers full.
3. Vérifier champion ML et couverture.
4. Lire rejets risque, targets et circuit breaker.
5. En live, confirmer compte, watcher et préflight.
6. Rapprocher ordres, fills, positions, cash et TCA.
7. Traiter les incidents d’observabilité séparément du statut métier.
