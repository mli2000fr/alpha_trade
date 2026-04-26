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
| `execution_engine/__main__.py` | Point d'entrée `python -m execution_engine` |
| `execution_engine/cli.py` | CLI bas niveau du moteur d'exécution |
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
| `run_execution.py` | Point d'entrée opérateur recommandé |

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

### Point d'entrée opérateur recommandé

```powershell
python run_execution.py
```

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

Le pattern canonique est :

1. soumettre l'entrée ;
2. observer l'ordre broker puis les fills ;
3. soumettre le stop initial broker-side si le contexte le permet ;
4. journaliser les requests, ordres broker et événements ;
5. reconstruire positions, lots et réconciliation.

Quand `--swing-only` est activé, ou quand une contrainte PDT ne laisse plus de slot de day trade, le moteur diffère l'armement des children le jour même. Le run journalise alors un événement `CHILDREN_DEFERRED_ACCOUNT_CONSTRAINT`.

Le trailing dynamique, s'il reste activé, doit être considéré comme une capacité secondaire de supervision plutôt qu'un prérequis du run nominal.

### 4.4 Réconciliation et TCA

Après soumission et synchronisation broker, le moteur peut :

- relire le snapshot figé `execution_targets_snapshot`,
- comparer `execution_order_requests`, `execution_broker_orders`, `execution_positions`, positions broker et protections,
- produire des résultats `execution_reconciliation_results` avec statuts `SAFE_AUTO`, `MANUAL_REVIEW`, `BLOCKED`,
- calculer slippage et implementation shortfall,
- écrire l'audit complet en base.

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
