# Audit — Watcher de protections post-exécution

> Périmètre : `execution_engine/protection_watcher.py`,
> `run_execution_protection_watch.py`, `scripts/windows/protection_watcher_*.ps1`,
> `scripts/windows/install_protection_watcher_*.ps1`,
> `scripts/windows/get_protection_watcher_status.ps1`,
> `ihm/pages/supervision_ops.py` (read-only).
> Sources : `doc/watcher.md` (383 lignes), code listé.

> Note : ce module est conceptuellement séparé de `execution_engine` mais en
> partage le code source (`execution_engine/protection_watcher.py`). L'audit
> global du moteur d'exécution est dans `audit_execution.md` ; ce fichier se
> concentre spécifiquement sur le watcher.

---

## 1. Résumé exécutif

Le **watcher** est un runtime *post-exécution* : il surveille les protections
broker-side créées par `Execution`, vérifie les conditions de transition (par
exemple multiple R atteint), annule le stop initial et promeut vers un trailing
stop dynamique. Il est intentionnellement **séparé du pipeline 1→14** : ce n'est
pas la 15e étape, c'est un service / job d'exploitation.

État global : **module bien pensé conceptuellement**, **pédagogie irréprochable**
(`doc/watcher.md` détaille onboarding, modes de lancement, conséquence de
non-lancement, packaging Windows). Modes `once` / `service`. Trois canaux de
lancement : CLI direct, IHM Supervision Ops, packaging Windows
(Task Scheduler, NSSM).

Principaux risques :

1. **Pas de leader election** : si plusieurs canaux lancent un watcher en parallèle
   (oubli IHM + Task Scheduler actif), risque de race conditions sur les annulations
   de stop initial / création de trailing stop.
2. **Pas de heartbeat persistant clair** : la doc mentionne "heartbeat continu"
   pour le mode service, mais pas où il est consultable hors logs locaux.
3. **Mode `once` non auto-restart** : si lancé manuellement post-`Execution` puis
   l'opérateur oublie de le rejouer, les transitions ne se font plus.
4. **Couplage Windows fort** : packaging via Task Scheduler / NSSM uniquement
   documenté. Pas d'équivalent Linux (`systemd unit`) si déploiement futur change
   de cible.
5. **Bridge PowerShell allowlisté** dans IHM Supervision Ops : surface d'attaque
   minime mais non nulle si l'allowlist est trop laxe.
6. **`get_protection_watcher_status.ps1`** : si le chemin du log NSSM change ou si
   l'exécution PowerShell est restreinte (ExecutionPolicy `Restricted`), le statut
   IHM affiche faussement "down" → opérateur peut relancer un second watcher.

Priorités immédiates :
- Implémenter un lock distribué via la table SQL `execution_locks` (déjà existante)
  avec timestamp + heartbeat.
- Persister le heartbeat dans une table SQL (`watcher_heartbeats`) consultable
  depuis l'IHM.
- Garde-fou IHM : refus explicite de lancement si lock actif détecté.

---

## 2. Constat détaillé

### 2.1 `protection_watcher.py` (logique métier)

| Item | Détail |
|---|---|
| Constat | Module qui implémente la logique de transition stop initial → trailing stop dynamique. Trigger configurable (`multiple_r`, `profit_pct`). |
| Force | Conception conceptuelle propre, séparation responsabilités. |
| Risque | **Cohérence** : la transition annule un ordre puis en soumet un autre. Entre les deux, un fill peut tomber → état transitoire fragile. |
| Recommandation | Documenter explicitement le scénario "fill pendant la transition" + test. |

### 2.2 `run_execution_protection_watch.py`

| Constat | Point d'entrée CLI. Modes `once` / `service`. |
| Force | Simple. Bonne UX. |
| Risque | Pas de check "un autre watcher est-il déjà actif sur ce compte ?". |
| Recommandation | Au démarrage, lire la table de lock `execution_locks` ; refuser si verrou actif récent (< 5 min). |

### 2.3 Modes de lancement multiples

| Canal | Avantage | Risque |
|---|---|---|
| CLI direct | Simple, contrôle total | Oubli de relancer |
| IHM "Supervision Ops" service local | UX opérateur | Survit-il à un crash Streamlit ? |
| Task Scheduler `once` périodique | Robuste, simple | Latence (ex: 5 min entre runs) |
| NSSM service persistant | Heartbeat continu | Double watcher si Task Scheduler aussi configuré |

| Risque cross-canal | **Race conditions** : aucun mécanisme natif n'empêche deux watchers actifs simultanés. |
| Recommandation | Lock SQL global (1 watcher / `account_id` à la fois). |

### 2.4 Packaging Windows

| Constat | 5 scripts PowerShell : `protection_watcher_launcher.ps1`,
`install_protection_watcher_task.ps1`,
`install_protection_watcher_service_nssm.ps1`,
`protection_watcher_secrets.ps1` (DPAPI), `get_protection_watcher_status.ps1`. |
| Force | Couvert correctement. DPAPI pour les secrets locaux. |
| Risque | **Sécurité opérationnelle** : ExecutionPolicy. `Bypass` souvent utilisé dans la doc → désactive un garde-fou. |
| Risque 2 | Pas d'équivalent Linux/Mac. |
| Recommandation | (a) Préférer `RemoteSigned` + sign les scripts ; (b) prévoir un stub `systemd` ou `cron` dans `scripts/linux/` même non utilisé immédiatement, pour réduire la dette d'évolution. |

### 2.5 IHM Supervision Ops (read-only)

| Constat | Bridge PowerShell allowlisté pour la lecture du status Windows. Lecture seule. |
| Risque | **Sécurité** : un bug dans l'allowlist = surface d'élévation. |
| Recommandation | Tests unitaires explicites de l'allowlist (les seules commandes acceptées sont exactement les 5 scripts ci-dessus, rien d'autre). |

### 2.6 Heartbeat / monitoring

| Constat | Doc mentionne "heartbeat continu" en mode service. |
| Risque | Pas de précision où le heartbeat est lisible. Si seul fichier local, IHM ne peut le voir si packaging Windows séparé. |
| Recommandation | Table `watcher_heartbeats(account_id, last_seen_at, mode, hostname, pid)` upsertée à chaque cycle. IHM peut alors afficher "watcher actif depuis X min" et alerter "no heartbeat > 10 min". |

---

## 3. Risques prioritaires

### Critique
- Aucun (ne fait rien si rien à surveiller).

### Élevé
- Pas de leader election → race conditions sur transitions stop / trailing.
- Pas de heartbeat persistant lisible IHM.
- ExecutionPolicy `Bypass` recommandée par défaut → garde-fou désactivé.

### Modéré
- Mode `once` oubliable.
- Statut Windows fragile (chemin NSSM, policy).
- Pas de stub Linux.

### Faible
- Documentation très dense → onboarding long malgré une "5 min" affichée.

---

## 4. Analyse spécifique des données de marché Alpaca gratuites

Le watcher consomme :
- les ordres ouverts via `client.list_orders` (broker, pas IEX) ;
- le prix courant via `client.get_latest_quote` ou similaire (probablement IEX) →
  **biais sur le calcul de "multiple R atteint"**.

Si le trigger métier est `multiple_r=1.0`, et que le prix IEX est en retard /
décalé par rapport au prix consolidé broker, la transition peut être déclenchée
trop tôt ou trop tard par rapport à la réalité.

**Recommandation** :
- pour le watcher, préférer si possible un prix issu du broker (`get_position`
  donne `current_price` côté Alpaca trading API qui est plus consolidé que market
  data IEX) ;
- documenter explicitement la source de prix utilisée.

---

## 5. Choix recommandé `split_adjusted` vs `all`

Aucun impact direct (le watcher manipule des prix instantanés, pas des séries).

---

## 6. Quick wins

1. **Lock SQL** via `execution_locks(scope='watcher', account_id, locked_at,
   heartbeat_at)` avec TTL 5 min.
2. **Table `watcher_heartbeats`** persistant.
3. **Garde-fou IHM** : refus de lancement si lock actif (lecture du heartbeat).
4. **Test allowlist PowerShell**.
5. **Documenter source de prix** utilisée pour le calcul du trigger.
6. **Stub Linux** (`scripts/linux/protection_watcher_systemd.service`).
7. **ExecutionPolicy plus stricte** (`RemoteSigned` + signature des scripts).

## 7. Recommandations structurelles

1. **Refactor `protection_watcher`** pour séparer la **logique métier de transition**
   (testable, hors broker) du **runner** (boucle service, lock, heartbeat).
2. **Stratégie multi-broker** : si un jour un second broker est ajouté, l'interface
   `BrokerProtectionAdapter` permettrait au watcher de fonctionner sans Alpaca-only.
3. **Health endpoint HTTP** : exposer un mini-serveur `/health` sur localhost que
   l'IHM consulte → décorrèle de la table SQL pour le statut temps réel.
4. **Audit `watcher_transitions`** : table dédiée qui historise chaque transition
   stop initial → trailing (timestamp, ancien stop, nouveau stop, raison).

## 8. Plan d'action priorisé

### Court terme
- Quick wins 1, 2, 3, 4, 5.

### Moyen terme
- Quick wins 6, 7.
- Refactor logique métier vs runner.
- Audit `watcher_transitions`.

### Long terme
- Health endpoint HTTP.
- Multi-broker (si pertinent).

## 9. Lacunes de tests, monitoring et documentation

### Tests
- Détail non évident depuis la doc. **Manque probable** :
  - test "deux watchers concurrents → un seul actif".
  - test "fill pendant transition" → état cohérent.
  - test allowlist PowerShell (unitaire).

### Monitoring
- Doc mentionne supervision IHM, mais pas de heartbeat SQL clair. **Manque** :
  - heartbeat SQL.
  - alarm IHM "no heartbeat > 10 min".

### Documentation
- Excellente. **Manque** :
  - source de prix utilisée pour le trigger (IEX vs broker).
  - matrice "lock actif → comportement attendu".
  - section "déploiement Linux" (même future).

