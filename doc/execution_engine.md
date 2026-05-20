# Execution Engine — Guide d'usage

## Objectif

Ce document résume le fonctionnement du module `execution_engine/` et les commandes utiles pour :

- exécuter un portefeuille cible produit par `risk_management`,
- soumettre des ordres Alpaca en mode simulation, paper ou live,
- gérer des protections broker-side initiales et, si explicitement activé, une transition trailing secondaire,
- auditer les requests, ordres broker, fills, positions et écarts de réconciliation.

---

## 1. Ce que contient le module

### Fichiers clés

| Fichier | Rôle |
|---|---|
| `execution_engine/__init__.py` | Package Python |
| `execution_engine/__main__.py` | Point d'entrée `python -m execution_engine` (façade de compatibilité) |
| `execution_engine/cli.py` | Shim CLI : délègue le chemin `run` vers `run_execution.py`, garde `cancel-all` natif |
| `execution_engine/executor.py` | Orchestrateur principal `ProductionExecutor` |
| `execution_engine/broker_adapter.py` | Adaptation des intents vers le broker |
| `execution_engine/order_intents.py` | Construction des ordres d'entrée et de rebalance |
| `execution_engine/state_machine.py` | Mapping et états d'ordres internes |
| `execution_engine/oco_manager.py` | Gestion logique OCO des protections broker-side |
| `execution_engine/reconciliation.py` | Réconciliation analytique targets / requests / broker / positions / protections |
| `execution_engine/tca.py` | Transaction Cost Analysis |
| `execution_engine/db_io.py` | Persistance SQL du module |
| `execution_engine/models.py` | Modèles métiers d'exécution |
| `execution_engine/config.py` | Paramètres immuables de l'exécution |
| `run_execution.py` | Launcher canonique du flux `run` |

---

## 2. Prérequis

### 2.1 Tables et données requises

#### Obligatoires

- `portfolio_targets`
- `execution_runs`
- `execution_targets_snapshot`
- `execution_order_requests`
- `execution_broker_orders`
- `execution_broker_fills`
- `execution_positions`
- `execution_position_lots`
- `execution_reconciliation_results`
- `execution_events`
- `broker_positions_snapshots`
- `broker_account_snapshots`

#### Utiles selon le contexte

- `risk_decisions`
- `corporate_actions_events` pour l'alerte pré-flight sur CA pending

### 2.2 Variables d'environnement minimales

```powershell
$env:LOGIN_DB = "user"
$env:PASSWORD_DB = "pass"
$env:ALPACA_API_KEY = "PK..."
$env:ALPACA_SECRET_KEY = "..."
```

### 2.3 Multi-comptes

Le moteur supporte `--account <ID>` via `service.alpaca.accounts.AccountRegistry`.

Il supporte aussi désormais des contraintes de compte/trading explicites :

- `--account-type margin|cash`
- `--pdt-rule auto|off`
- `--swing-only`

---

## 3. Commandes utiles

### Launcher canonique du flux `run`

```powershell
python run_execution.py
```

### Compatibilité CLI historique

```powershell
python -m execution_engine --broker-mode paper --dry-run
python -m execution_engine --broker-mode live --account live1 --run-id risk-123
```

Le point d'entrée `python -m execution_engine` reste supporté pour compatibilité,
mais il délègue désormais le flux `run` au launcher canonique `run_execution.py`.
La sous-commande `cancel-all`, elle, reste native à `execution_engine`.

### Simulation pure

```powershell
python run_execution.py simulate
```

### Paper trading

```powershell
python run_execution.py paper
```

### Live trading

```powershell
python run_execution.py live --account live1
```

### Exécution avec contraintes de compte

```powershell
# Compte margin soumis à PDT
python run_execution.py paper --account default --account-type margin --pdt-rule auto

# Compte cash : capital disponible limité au cash settled
python run_execution.py paper --account default --account-type cash

# Swing strict : ne pas armer les exits le jour même
python run_execution.py paper --account default --account-type margin --pdt-rule off --swing-only
```

### Watcher post-exécution

Le watcher se lance **après** `Execution`, pas avant. Il ne fait plus partie du chemin nominal : il supervise en secondaire la vie des protections broker-side déjà créées par le run d'exécution.

```powershell
# contrôle ponctuel juste après l'étape 12 Execution
python run_execution_protection_watch.py --mode once --account default

# surveillance continue pendant la session
python run_execution_protection_watch.py --mode service --account default
```

En exploitation Windows, on préfère généralement :

- **Task Scheduler** pour un `once` périodique ;
- **NSSM** pour un service persistant.

### Vérification de l'environnement

```powershell
python run_execution.py check
```

### Exécution via le CLI bas niveau du module

```powershell
python -m execution_engine --broker-mode paper --dry-run
python -m execution_engine --trade-date 2026-04-21 --risk-run-id abc123 --broker-mode paper
```

---

## 4. Ce que fait le moteur

### 4.1 Préflight

`ProductionExecutor.execute_run()` :

1. construit un `exec_run_id` ;
2. charge les `portfolio_targets` ;
3. crée la ligne `execution_runs` ;
4. vérifie éventuellement le circuit breaker ;
5. vérifie les horaires de marché ;
6. construit un snapshot de contraintes de compte (`margin|cash`, `PDT`, `swing_only`) ;
7. alerte s'il existe des corporate actions pending sur les symboles cibles.

### 4.2 Construction et soumission des intents

Le module :

1. transforme les cibles en `OrderIntent` ;
2. filtre les doublons via `idempotency_key` ;
3. bloque les achats qui dépassent le capital réellement mobilisable selon le type de compte ;
4. persiste les intents ;
5. soumet les ordres d'entrée au broker.

En particulier :

- en `margin`, le moteur s'appuie sur `buying_power` broker ;
- en `cash`, le moteur s'appuie sur `non_marginable_buying_power` / `cash` settled ;
- en `dry_run`, un multiplicateur de buying power simulé permet de distinguer un compte `margin` d'un compte `cash`.

### 4.3 Protections broker-side

Le moteur overnight nominal privilégie les protections simples et traçables.

Le pattern canonique (« synthetic bracket ») est :

1. soumettre l'entrée ;
2. observer l'ordre broker puis les fills ;
3. soumettre le take-profit (limit) et le stop initial broker-side une fois l'entrée remplie (`_submit_children`) ;
4. journaliser les requests, ordres broker et événements ;
5. reconstruire positions, lots et réconciliation.

> ℹ️ Alpaca ne supporte pas le `trailing_stop` comme leg native d'un bracket order. Le moteur utilise donc un **bracket synthétique** : l'entrée est soumise seule, puis TP + SL sont armés post-fill côté application. L'OCO est gérée applicativement (`oco_manager.py`).

#### 4.3.bis Filet de sécurité TP/SL (Phase 7b — sprint S26)

**Problème historique** : en profil `overnight_cash_swing` (presets `paper`/`live`), l'entrée est soumise hors RTH. La phase de polling et `_submit_children` étaient sautées (`if not dry_run and market_open_for_poll:`). Résultat : si l'entrée se remplissait à l'ouverture suivante, **TP/SL n'étaient jamais armés**.

**Correctif (S26)** — Deux filets idempotents :

1. **Phase 7b (`executor.py`)** — Après `BrokerStateSynchronizer.sync`, `db_io.load_unprotected_filled_parents(exec_run_id, account_id)` retourne les parents `entry/buy` `FILLED` (ou `PARTIALLY_FILLED` avec `filled_qty>0`) **sans** enfant `take_profit` ouvert **et sans** enfant `initial_stop`/`trailing_stop` ouvert. Pour chaque ligne, `_reconstruct_parent_for_arming(row)` rebâtit un `OrderIntent` (role `ENTRY`) + un `BrokerOrder` synthétique `FILLED`, puis appelle `_submit_children`. Métriques exposées dans le `run_summary` :
   - `children_armed_post_sync`
   - `children_armed_post_sync_failed`
   - événement audit : `CHILDREN_SUBMITTED` avec payload `{"trigger": "post_broker_sync", ...}`.

2. **Filet `protection_watcher` (`_arm_missing_protections`)** — Le watcher (mode `once` ou `service`) rejoue la même requête à chaque tick et arme TP + SL via `build_take_profit_intent` / `build_initial_stop_intent` (avec fallback `build_trailing_stop_intent` si l'initial échoue). Métriques :
   - `armed_missing_protections`
   - `armed_missing_protections_failed`
   - événement audit : `CHILDREN_SUBMITTED` avec `trigger="watcher_safety_net"`.

**Idempotence** : la requête SQL exclut tout parent ayant déjà un enfant non-cancellé → relance sans risque de doublons.

**Observabilité opérateur** : un `armed_missing_protections > 0` récurrent indique que l'executor termine systématiquement avant l'ouverture (cas `overnight_cash_swing` nominal) — c'est attendu, le watcher fait le travail. Un `children_armed_post_sync_failed` ou `armed_missing_protections_failed` > 0 doit être investigué (cf. runbook §positions sans protection).

Quand `--swing-only` est activé, ou quand une contrainte PDT ne laisse plus de slot de day trade, le moteur diffère l'armement des children le jour même. Le run journalise alors un événement `CHILDREN_DEFERRED_ACCOUNT_CONSTRAINT`.

Le trailing dynamique, s'il reste activé, doit être considéré comme une capacité secondaire de supervision plutôt qu'un prérequis du run nominal.

### 4.4 Réconciliation et TCA

Après soumission et synchronisation broker, le moteur peut :

- relire le snapshot figé `execution_targets_snapshot`,
- comparer `execution_order_requests`, `execution_broker_orders`, `execution_positions`, positions broker et protections,
- produire des résultats `execution_reconciliation_results` avec statuts `SAFE_AUTO`, `MANUAL_REVIEW`, `BLOCKED`,
- calculer slippage et implementation shortfall,
- écrire l'audit complet en base.

### 4.4.bis Runbook réconciliation `MANUAL_REVIEW` / `BLOCKED` (Phase 5.2.d)

À la fin d'un run d'exécution, chaque cible est classée par
`execution_reconciliation_results.reconciliation_status`. Le `run_summary`
expose désormais (Phase 5.2.d) la liste des symboles concernés via
`reconciliation_manual_review_symbols` et `reconciliation_blocked_symbols`
pour faciliter le pointage opérateur.

| Statut | Cause typique | Action opérateur | SQL d'inspection |
|---|---|---|---|
| `SAFE_AUTO` | Tout aligné (positions, protections, ordres open). | Aucune action. | `SELECT * FROM execution_reconciliation_results WHERE reconciliation_status='SAFE_AUTO' AND exec_run_id=:run` |
| `MANUAL_REVIEW` | Delta qty > tolérance, prix décalé > N %, ordre open inattendu, protection manquante. | 1) Inspecter `execution_reconciliation_results.reason_code`. 2) Vérifier `execution_broker_orders` (statut, broker_order_id). 3) Décider : compléter manuellement via UI broker ou attendre le prochain run. | `SELECT symbol, target_qty, broker_position_qty, position_delta, action, reason_code FROM execution_reconciliation_results WHERE reconciliation_status='MANUAL_REVIEW' AND exec_run_id=:run` |
| `BLOCKED` | Symbole en trading halt, position broker non identifiée, mismatch lot critique. | 1) **STOP** : ne pas relancer le run. 2) Vérifier `service.alpaca` halt status. 3) Si nécessaire, déclencher kill switch (cf. §4.4.ter). 4) Reconcilier manuellement avant le prochain run. | `SELECT symbol, reason_code, position_delta, has_open_protection FROM execution_reconciliation_results WHERE reconciliation_status='BLOCKED' AND exec_run_id=:run` |

> **Astuce** : `SELECT reconciliation_blocked_symbols FROM run_business_summaries
> WHERE step_key='execution' ORDER BY started_at DESC LIMIT 5` permet d'obtenir
> directement la liste des symboles bloqués des 5 derniers runs.

### 4.4.ter Kill switch global (Phase 5.2.c)

Pour annuler **tous** les ordres open d'un compte broker en une seule
commande (sans passer par l'IHM ou un script ad-hoc) :

```powershell
# Mode paper — exécution réelle des cancels
python -m execution_engine cancel-all --account paper1 --reason "incident X"

# Mode paper — dry-run (liste les ordres sans les annuler)
python -m execution_engine cancel-all --account paper1 --dry-run

# Mode live — exige --confirm-account == --account (garde-fou audit_execution.md §6 QW#5)
python -m execution_engine cancel-all --account live1 --broker-mode live --confirm-account live1 --reason "halt-trading"
```

**Comportement** :

1. Charge tous les ordres `status=open` via `BrokerAdapter.cancel_all_open_orders`.
2. En mode normal : appelle `cancel_order(broker_order_id)` séquentiellement ;
   un échec d'un ordre n'interrompt pas la boucle (chaque erreur est
   capturée par-ordre dans la colonne `results_json`).
3. En mode `--dry-run` : ne modifie rien côté broker, mais persiste
   quand même un audit `execution_kill_switch_runs(dry_run=1)`.
4. Persiste un row dans `execution_kill_switch_runs(run_id, account_id,
   broker_mode, reason, total_open, canceled, failed, dry_run, started_at,
   finished_at, results_json)`.
5. Émet une ligne `::alpha_trade_run_summary::{...}` parsable par l'IHM,
   avec `event_type=KILL_SWITCH_TRIGGERED` (à ne pas confondre avec
   `KILL_SWITCH_ACTIVATED` interne sur N échecs consécutifs).

**Pré-conditions** :

- `--broker-mode live` exige `--confirm-account` strictement identique à
  `--account` (sinon `SystemExit`).
- Si un run d'exécution est en cours sur ce compte (`execution_locks` actif),
  utiliser `--force` pour outrepasser le verrou (dangereux).

**Post-conditions** :

- `SELECT * FROM execution_kill_switch_runs ORDER BY created_at DESC LIMIT 5`
  retourne les derniers kill switches.
- L'IHM peut afficher l'historique via la table `execution_kill_switch_runs`.

### 4.5 Watcher post-exécution

Le watcher n'est pas une phase du pipeline 1→14 lui-même. C'est un runtime complémentaire et secondaire qui s'accroche juste après `Execution` pour :

1. détecter les ordres/protections à surveiller ;
2. vérifier les conditions de transition ;
3. promouvoir un stop initial vers un trailing stop dynamique ;
4. persister la santé du mécanisme pour `Supervision Ops`.

---

## 5. Pourquoi un run peut s'arrêter ou n'exécuter aucun ordre

### 5.1 Aucun target disponible

Causes probables :

1. `risk_management` n'a pas encore écrit dans `portfolio_targets` ;
2. le `risk_run_id` demandé n'existe pas ;
3. la date ciblée ne correspond à aucun run de risque.

### 5.2 Abandon en préflight

Causes probables :

1. circuit breaker actif ;
2. marché fermé et `allow_outside_rth = False` ;
3. environnement Alpaca incomplet ;
4. erreur broker lors du contrôle d'horloge ;
5. contraintes de capital/cash account trop restrictives pour soumettre les achats.

### 5.3 Ordres rejetés

Causes probables :

1. erreur 4xx broker (permanente) ;
2. symbole interdit ou payload invalide ;
3. compte ou permissions Alpaca inadaptés ;
4. `client_order_id` déjà utilisé.

### 5.4 Warnings corporate actions

Le moteur ne bloque pas automatiquement sur les CA pending, mais il loggue un warning pour signaler que les quantités ou prix peuvent être obsolètes tant que `python -m corporate_actions apply` n'a pas été exécuté.

---

## 6. Vérifications utiles

### Vérifier l'environnement broker/DB

```powershell
python run_execution.py check
```

### Vérifier les derniers runs d'exécution

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text("SELECT exec_run_id, risk_run_id, trade_date, status, broker_mode, account_id FROM execution_runs ORDER BY created_at DESC LIMIT 10")).mappings().all();
    print([dict(r) for r in rows])'
```

### Vérifier les derniers événements d'exécution

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text("SELECT event_type, message, symbol, created_at FROM execution_events ORDER BY created_at DESC LIMIT 20")).mappings().all();
    print([dict(r) for r in rows])'
```

---

## 7. Tests

### Tests ciblés du moteur d'exécution

```powershell
python -m pytest tests/test_execution_engine_executor.py tests/test_execution_engine_db_io.py tests/test_execution_engine_state_machine.py tests/test_execution_engine_oco_manager.py tests/test_execution_engine_reconciliation.py tests/test_execution_engine_tca.py -q -o addopts=""
```

### Tests CLI et intégration légère

```powershell
python -m pytest tests/test_execution_engine_main.py tests/test_run_execution.py tests/test_broker_adapter.py tests/test_trading_client.py -q -o addopts=""
```

---

## 8. Recommandation pratique

Ordre conseillé :

1. lancer `risk_management` ;
2. contrôler que `portfolio_targets` contient bien des lignes ;
3. exécuter `Execution` et vérifier la chaîne `target snapshot → request → broker order → fill → position → réconciliation` ;
4. démarrer en `simulate` ;
5. passer ensuite en `paper` ;
6. réserver `live` au contexte opérateur validé.

### Séquence recommandée

```powershell
python -m risk_management.run_risk --account-equity 100000 --account live1
python run_execution.py simulate --account live1
python run_execution.py paper --account live1
```
