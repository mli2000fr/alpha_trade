# Alpha Trade — Documentation Technique

> *Version : 0.3.0 — Python ≥ 3.12 — Dernière mise à jour : mai 2026*

---

## 1. Architecture Générale

### 1.1 Structure des dossiers

```
alpha_trade/
├── run_execution.py              ← Point d'entrée principal (CLI interactif ou arguments)
├── run_execution_protection_watch.py ← Point d'entrée opérateur du watcher post-exécution
├── pyproject.toml                ← Config build, dépendances, ruff, mypy
├── requirements.txt / -dev.txt   ← Dépendances runtime et dev
├── config.yaml                   ← Configuration centralisée YAML (DB, Alpaca, risk)
├── alembic.ini + alembic/        ← Migrations de schéma DB (Alembic)
├── mypy.ini / pytest.ini         ← Config mypy et pytest (cov ≥ 60%)
├── README.md                     ← Documentation rapide + ordre d'exécution
├── doc/
│   ├── DOC_FONCTIONNELLE.md      ← Documentation fonctionnelle complète
│   └── DOC_TECHNIQUE.md          ← Ce document
├── core/interfaces.py            ← Contrats (Protocol) : PriceRepository, RiskChecker, etc.
├── common/utils.py               ← Calendrier NYSE, RotatingFileHandler, load_config()
├── database/                     ← Persistance MySQL (SQLAlchemy + pymysql)
│   ├── connection.py             ← Engine, Session, pool configuré
│   ├── assets.py / bar_metadata.py / sanitizer_db_ops.py
│   └── sql/                      ← DDL : stock/, news/, ml/, risk/, execution/, corporate_actions/
├── service/alpaca/               ← Clients HTTP Alpaca (data, news, trading) + registre multi-comptes
├── service/finnhub/              ← Client HTTP Finnhub (profil société)
├── dataIntegrityEngine/          ← Ingestion & nettoyage des données
├── screener/                     ← Screening liquidité/force relative (ProcessPoolExecutor)
├── selector/                     ← AlphaScanner multi-facteurs (ThreadPoolExecutor)
├── event_sentiment/              ← Pipeline NLP : news → FinBERT → agrégation → fusion
├── modelFactory/                 ← LSTM + Temporal Attention (Lightning)
├── risk_management/              ← Sizing, contraintes, circuit breaker, portefeuille cible
├── execution_engine/             ← Exécution canonique : targets snapshot, requests, ordres broker, fills observés, positions/lots, réconciliation, TCA, watcher post-exécution secondaire
├── scripts/windows/              ← Packaging Windows : launcher, Task Scheduler, NSSM, secret store, bridge read-only
├── corporate_actions/            ← Corporate actions : dividendes, splits, audit, cash ledger
├── ihm/                          ← IHM opérateur Streamlit (dashboard de supervision)
├── artifacts/models/             ← Checkpoints PyTorch
├── tests/                        ← 40+ tests unitaires (pytest)
├── .github/                      ← CI/CD GitHub Actions
└── htmlcov/                      ← Rapports couverture
```

### 1.2 Responsabilités par module

| Module | Rôle |
|---|---|
| `core/interfaces.py` | Protocols partagés pour découplage et mocking |
| `database/` | Persistance MySQL (SQLAlchemy Core + pymysql) |
| `service/` | Clients HTTP (Alpaca data/trading/news, Finnhub) + registre multi-comptes (`accounts.py`) |
| `dataIntegrityEngine/` | Import et nettoyage données de marché |
| `screener/` | Scores de base (liquidité, RSI relatif, range historique) |
| `selector/` | Scoring avancé (Minervini, VCP, neutralisation sectorielle) + profils de filtres stricts partagés |
| `event_sentiment/` | NLP FinBERT + fusion scores quant/sentiment |
| `modelFactory/` | Gouvernance ML multi-modèles : LSTM per-symbol, challengers tabulaires locaux, modèle global optionnel, sélection du champion et serving d'inférence |
| `risk_management/` | Sizing ATR/Kelly, contraintes, circuit breaker, portefeuille |
| `execution_engine/` | Chaîne canonique d'exécution (requests, ordres broker, fills, positions/lots, réconciliation) + watcher post-exécution secondaire |
| `corporate_actions/` | Gestion dividendes, splits, reverse splits (audit + comptabilité portefeuille) |
| `backtesting/` | Backtest intégré research/pipeline : replay PIT, contraintes compte, phases de fidélité 2/3/4/5/7, backfill, diagnostics screener, calibration sentiment, reporting structuré |
| `ihm/` | IHM Streamlit : supervision pipeline, scores, risque, exécution, CA |

---

## 2. Analyse Détaillée du Code

### 2.1 Classes principales

**`ProductionExecutor`** (`execution_engine/executor.py`) — Orchestrateur en 10 phases :
1. Init (build_run_id)
2. Pre-flight (chargement cibles, circuit breaker, market hours, snapshot contraintes de compte)
3. Build intents + déduplication par idempotency_key + filtrage capital/PDT/cash/swing
4. Submit entries (avec retry réseau, kill switch, throttle batch)
5. Poll fills (polling broker jusqu'à terminal state)
6. Submit children / protections broker-side (stop initial + take-profit ; promotion trailing éventuelle via watcher secondaire), avec report possible en cas de `swing_only` / `PDT`
7. *(phase réservée)*
8. Réconciliation (positions broker vs cibles, rebalance optionnel)
9. TCA (slippage, implementation shortfall)
10. Finalize (persist events, update run status)

**`AlphaScanner`** (`selector/alpha_scanner.py`) — Scanner multi-facteurs en chunks parallèles (ThreadPoolExecutor) : `fetch_market_data()` → `compute_factors()` → `merge_scores()` → enrichissement instrument / quotes / earnings → `apply_filters()` → neutralisation sectorielle cross-sectorielle sur univers complet → `rank_and_select()`.

Points d'implémentation importants :

- les filtres `min_close` et `liquidity_threshold` existent à la fois en présélection SQL et en filet de sécurité pandas ;
- le filtre `max_volatility_ratio` est appliqué **dans `apply_filters()`**, pas dans la présélection SQL, car il dépend de `compute_factors()` (`vol_10`, `vol_60`, puis `volatility_ratio = vol_10 / vol_60`) ;
- les seuils stricts swing cash sont centralisés dans `selector/strict_filter_profiles.py` (`STRICT_SWING_CASH_FILTERS`) ; `AlphaScannerConfig.strict_swing_cash()` les projette côté scanner, et le chemin CLI standard charge désormais ce profil implicitement ;
- les filtres `market_cap`, `beta_126`, `spread_bps` et `earnings_blackout` sont appliqués dans `apply_filters()` après enrichissement via `stock_metadata`, `stock_quote_snapshots` et `stock_earnings_calendar` ;
- `beta_126` est calculé localement contre `SPY` à partir des rendements journaliers alignés ;
- `fetch_quote_snapshots(..., reference_date=...)` et `fetch_next_earnings(..., reference_date=...)` permettent au live et au backfill PIT de réutiliser exactement les mêmes règles métier.

**`PortfolioBuilder`** (`risk_management/portfolio_builder.py`) — Construction portefeuille : enrichir candidats (conviction score) → trier par conviction DESC → filtre corrélation → sizing ATR/Kelly → check contraintes → ACCEPTED / REDUCED / REJECTED.

**`SentimentSignalAggregator`** (`event_sentiment/signal_aggregator.py`) — Fusion `75% quant + 15% sentiment ticker + 10% macro sectoriel` → `final_score_sentiment`.

**`LSTMAttentionModule`** (`modelFactory/model.py`) — LightningModule : LSTM multi-couche + Temporal Attention (soft-attention axe temporel) + classification binaire (CrossEntropyLoss). Métriques : BinaryAccuracy, BinaryPrecision, BinaryRecall, BinaryAUROC.

**`train_symbol()` / `predict_symbol()`** (`modelFactory/trainer.py`, `modelFactory/predictor.py`) — services d'entraînement et d'inférence par symbole. Ils ne se limitent plus au LSTM : `train_symbol()` peut désormais produire un manifeste d'artefacts multi-backends (`lstm_attention`, `lightgbm`, `catboost`, `global_model`) et `predict_symbol()` route vers le backend réellement sélectionné. Les deux chemins supportent `accelerator=auto|cpu|gpu` :

- `train` s'appuie sur Lightning et résout `cuda:0` si disponible ;
- `predict` charge explicitement le checkpoint sur `cuda:0` en mode `auto`/`gpu` lorsque CUDA est disponible, sinon retombe sur CPU ;
- les logs du module ML journalisent le `requested_accelerator`, le `resolved_device` et le `device_name` effectif.

Points d'implémentation importants côté `modelFactory` :

- `trainer.py` persiste `config.json` et `metrics.json` comme **manifeste d'inférence** et **rapport de gouvernance** par symbole ;
- `tabular_baseline.py` persiste désormais les artefacts tabulaires locaux (`lightgbm_model.pkl`, `catboost_model.pkl`, calibrateurs associés) ;
- `champion_selection.py` n'autorise un champion que s'il est **réellement inférable** (backend + chemins artefacts présents) ;
- `predictor.py` sait router vers `lstm_attention`, `lightgbm_tabular`, `catboost_tabular` et `global_tabular` ;
- la base MySQL reste volontairement **résumée** : la gouvernance détaillée des challengers vit surtout dans les artefacts disque.

**`BrokerAdapter`** (`execution_engine/broker_adapter.py`) — Couche d'isolation broker : traduit `OrderIntent` → payload Alpaca → `BrokerOrder`. Expose aussi le snapshot de compte (`equity`, `buying_power`, `cash`, `non_marginable_buying_power`, `daytrade_count`) utilisé pour appliquer les contraintes `margin/cash/PDT` côté exécution. Seul fichier à modifier pour changer de broker.

**`ProtectionTransitionWatcher`** / **`ProtectionWatcherService`** (`execution_engine/protection_watcher.py`) — Watcher post-exécution secondaire chargé de surveiller les protections créées par `Execution` et, si ce mode est activé, de promouvoir les stops initiaux vers un trailing stop dynamique selon les conditions métier. `ProtectionWatcherService` encapsule la boucle persistante, les heartbeats, la persistance de santé dans `run_business_summaries` et les garde-fous de résilience.

**`watcher_runtime`** (`ihm/services/watcher_runtime.py`) — Couche IHM de pilotage local du watcher. Elle construit les commandes `once` / `service`, lance les processus managés par `process_registry`, expose l'historique dédié et sépare explicitement le pilotage local IHM du packaging Windows machine-wide.

**`windows_watcher_bridge`** (`ihm/services/windows_watcher_bridge.py`) — Bridge IHM → PowerShell strictement allowlisté. Il n'expose que des opérations read-only sur Windows : lecture du statut watcher, inventaire des sources de logs détectables et import borné de ces logs.

**`CircuitBreaker`** (`risk_management/circuit_breaker.py`) — Suspend le trading si drawdown ≥ 15% ou perte daily ≥ 5%.

**`OcoManager`** (`execution_engine/oco_manager.py`) — Gestion OCO logique : quand une protection enfant est `FILLED`, annule le sibling.

**`CorporateActionEngine`** (`corporate_actions/engine.py`) — Orchestrateur corporate actions en 2 phases : `sync()` (ingestion provider → DB) et `apply()` (application idempotente sur positions). Stratégie : les OHLCV restent gérés par Alpaca avec la convention projet `adjustment="split"`, ce module gère uniquement la comptabilité portefeuille (qty, cost basis, cash). La sync résout par défaut l'univers depuis `stock_metadata` (`status='active'`, `tradable=1`, `bars_available=1`), puis interroge Alpaca par lots configurables (`batch_size`, défaut 25) avec persistance immédiate en base après chaque lot.

**`AlpacaCorporateActionProvider`** (`corporate_actions/provider.py`) — Provider abstrait pour l'ingestion des dividendes et splits depuis l'API Alpaca Corporate Actions (`v1/corporate-actions`). Gère pagination (`next_page_token`), tri `asc`, `limit=1000`, retry réseau/HTTP, et retry spécifique aux timeouts sur le modèle de `fetch_bars` du client Alpaca. Extensible vers Polygon, Finnhub, etc.

**`CorporateActionRepository`** (`corporate_actions/db_io.py`) — Accès DB (SQLAlchemy Core) : insert/load événements, applications, cash ledger, lecture des positions broker et résolution de l'univers de sync depuis `stock_metadata`. Compatible MySQL et SQLite (tests).

**`AccountRegistry`** (`service/alpaca/accounts.py`) — Singleton de résolution multi-comptes. Charge les comptes depuis `config.yaml`, env vars préfixées, ou fallback classique. Fournit `resolve(account_id)` → `BrokerAccount(api_key, secret_key, mode)`. Tous les clients (trading, market data, news, corporate actions) passent par cette résolution.

**`BacktestEngine`** (`backtesting/simulator.py`) — Moteur de backtest stateful utilisé par la CLI `run`. Il applique la convention `signal J -> entrée J+1 open`, simule les contraintes de compte (`margin`, `cash`, `PDT`, `swing_only`), supporte les phases opt-in `execution_replay`, `protection_replay`, `watcher_replay`, `exit_lifecycle_replay`, et sait consommer les bundles `MicrostructureConfig` et `RiskOverlayConfig`. Le moteur conserve un `BacktestDiagnostics` structuré exporté dans `report.json`.

**`TradingConstraintConfig`** (`backtesting/trading_constraints.py`) — Dataclass pure décrivant les contraintes de compte backtesting via trois axes indépendants : `account_type` (`margin|cash`), `pdt_rule` (`auto|off`) et `swing_only` (`bool`). Encapsule le seuil `25 000 $`, la limite `3 day trades / 5 séances` et le settlement simplifié `T+1` pour les cash accounts.

**`replay_signals()`** (`backtesting/signal_replay.py`) — Reconstruction jour par jour des signaux de conviction à partir des scores PIT, avec cascade de fallback factorisée `final_score_walk_forward -> final_score_sentiment -> final_score`, fusion vectorisée des probabilités ML et ranking top-N quotidien.

**`BacktestReport`** (`backtesting/report.py`) — Dataclass de résumé : rendement total, dividendes, CAGR, Sharpe, Sortino, Calmar, Ulcer Index, max drawdown, win rate, profit factor. Le module exporte `report.json`, `equity_curve.csv/png`, `trades.csv` et sérialise les sentinels comme `"inf"` pour rester JSON-friendly.

**`BackfillScoresHistoryService`** (`backtesting/backfill_scores_history.py`) — Orchestrateur de backfill point-in-time de `stock_scores_history`. Rejoue, pour chaque séance manquante, le screener sur `stock_bars_daily`, le scoring `AlphaScanner`, la fusion sentiment `SentimentSignalAggregator`, puis insère un snapshot historisé avec `capital_preset_key` et `config_fingerprint`. Il intègre aussi une logique de couverture PIT pour les overlays quotes/earnings.

**`prepare_predictions_for_ml_mode()` / `prepare_scores_for_sentiment_mode()`** (`backtesting/resilience.py`) — Couche de résilience du backtest. Implémente les politiques `auto | off | rebuild-missing` pour les prédictions ML et le sentiment, et s'articule avec `engine_mode` / `ml_pit_strategy` pour distinguer comportement tolérant et comportement PIT strict.

**`build_fidelity_manifest()`** (`backtesting/fidelity.py`) — Construit le manifeste de fidélité PIT (`fidelity_manifest.json`) à partir des diagnostics de chargement scores, sentiment et ML.

**`build_run_metadata()`** (`backtesting/run_metadata.py`) — Construit le bloc `run_metadata` avec `git_commit_sha`, branche courante, statut dirty, version Python, plateforme, versions de packages et `dataset_hash`.

**`ParquetCache`** (`backtesting/cache.py`) — Cache Parquet utilitaire pour OHLCV / scores / predictions. Présent dans le code et les tests, mais pas encore branché par défaut à la commande `run`.

**`compute_benchmark_analytics()` / `compute_tail_analytics()`** (`backtesting/analytics.py`) — Utilitaires benchmark, tail analytics, attribution sectorielle et exports HTML interactifs. Là encore, briques disponibles côté code mais non encore automatiquement branchées à la CLI standard.

**`bootstrap_trades()` / `parameter_sensitivity()`** (`backtesting/statistical_validation.py`) — Fonctions de validation statistique pour bootstrap Monte Carlo et analyse de sensibilité paramétrique.

### 2.2 Fonctions clés

| Fonction | Module | Description |
|---|---|---|
| `build_entry_intents()` | `order_intents` | Construit OrderIntent d'entrée depuis les ExecutionTarget |
| `intent_to_alpaca_payload()` | `order_intents` | Convertit OrderIntent → dict API Alpaca |
| `reconcile_targets_vs_broker()` | `reconciliation` | Compare cibles vs positions → ReconcileDiff[] |
| `compute_slippage_bps()` | `tca` | Slippage en basis points |
| `map_alpaca_status()` | `state_machine` | Mapping statuts Alpaca → statuts internes |
| `compute_conviction()` | `conviction` | score × 40% + prediction × 60% |
| `filter_correlated()` | `correlation_filter` | Filtre par matrice de corrélation (seuil 0.80) |
| `_idempotency_key()` | `order_intents` | SHA-256 tronqué pour déduplication |
| `process_dividend()` | `corporate_actions.processors` | Calcul dividende cash : qty × amount → crédit cash ledger |
| `process_split()` | `corporate_actions.processors` | Ajustement split/reverse : qty × ratio, cost / ratio, cash-in-lieu si fractions |
| `reconcile_after_corporate_actions()` | `corporate_actions.reconciliation` | Compare positions internes post-CA vs broker |

### 2.3 Modèles de données clés

- `ExecutionTarget` : cible lue depuis `portfolio_targets` (symbol, shares, entry_price, weight, sector)
- `OrderIntent` : intention d'ordre pré-soumission (idempotency_key, role, decision_price)
- `BrokerOrder` : ordre soumis au broker (broker_order_id, status, filled_qty, avg_fill_price)
- `ExecutionFill` : fill reçu (slippage_bps, implementation_shortfall)
- `ExecutionEvent` : événement auditable (type, message, payload JSON)
- `CandidateScore` / `EnrichedCandidate` / `PortfolioEntry` : pipeline risk management
- `CorporateActionEvent` : événement CA ingéré (provider, symbol, ca_type, ex_date, amount/ratio, idempotency_key)
- `CorporateActionApplication` : trace immuable d'un ajustement appliqué (qty before/after, cost basis, cash impact)
- `CashLedgerEntry` : entrée ledger cash (dividend_credit, cash_in_lieu)
- `PositionSnapshot` : état d'une position pour traitement CA

---

## 3. Technologies Utilisées

- **Python** ≥ 3.12, build setuptools
- **DB** : SQLAlchemy + pymysql (MySQL 8.x)
- **Data** : pandas, numpy, polars
- **Calendrier** : pandas-market-calendars, pytz, python-dateutil
- **HTTP** : requests, python-dotenv
- **NLP** : transformers (HuggingFace), modèle `ProsusAI/finbert`
- **ML** : PyTorch, Lightning, torchmetrics
- **Tests** : pytest ≥ 8, pytest-cov ≥ 5, pytest-xdist ≥ 3, pytest-timeout ≥ 2
- **Lint** : ruff ≥ 0.4 — **Types** : mypy ≥ 1.10

### APIs externes

| API | Base URL | Usage |
|---|---|---|
| Alpaca Market Data | `data.alpaca.markets/v2` | Bars OHLCV, assets |
| Alpaca News | `data.alpaca.markets/v1beta1/news` | Articles financiers |
| Alpaca Trading paper | `paper-api.alpaca.markets/v2` | Ordres, positions, compte |
| Alpaca Trading live | `api.alpaca.markets/v2` | Ordres, positions, compte |
| Finnhub | `finnhub.io/api/v1` | Profil société, secteur, market cap, earnings calendar |

---

## 4. Configuration Technique

### 4.1 Variables d'environnement

| Variable | Requis | Description |
|---|---|---|
| `LOGIN_DB` | ✅ | Utilisateur MySQL |
| `PASSWORD_DB` | ✅ | Mot de passe MySQL |
| `ALPACA_API_KEY` | ✅ | Clé API Alpaca (compte par défaut) |
| `ALPACA_SECRET_KEY` | ✅ | Secret Alpaca (compte par défaut) |
| `ALPACA_<ID>_API_KEY` | ⚠️ | Clé API pour un compte supplémentaire (ex: `ALPACA_LIVE1_API_KEY`) |
| `ALPACA_<ID>_SECRET_KEY` | ⚠️ | Secret pour un compte supplémentaire |
| `ALPACA_<ID>_MODE` | ⚠️ | Mode du compte (paper/live, défaut: paper) |
| `FINNHUB_API_KEY` | ⚠️ | Token Finnhub (ou `CLE_FINNHUB`) — requis pour `update_sector` |

Pour le watcher Windows, ces variables peuvent être injectées via :

- environnement de la session ;
- fichier `.env` ;
- secret store DPAPI chargé par `scripts/windows/protection_watcher_launcher.ps1`.

### 4.2 Configuration multi-comptes (`config.yaml`)

Le fichier `config.yaml` permet de déclarer plusieurs comptes Alpaca :

```yaml
alpaca:
  accounts:
    - id: default
      label: "Compte principal (paper)"
      api_key: "${ALPACA_API_KEY}"
      secret_key: "${ALPACA_SECRET_KEY}"
      mode: paper
    - id: live1
      label: "Compte live"
      api_key: "${ALPACA_LIVE1_API_KEY}"
      secret_key: "${ALPACA_LIVE1_SECRET_KEY}"
      mode: live
```

**Résolution des credentials** (ordre de priorité) :
1. `config.yaml` → `alpaca.accounts` (placeholders `${VAR}` résolus depuis l'env)
2. Variables d'env préfixées : `ALPACA_<ID>_API_KEY` / `ALPACA_<ID>_SECRET_KEY`
3. Fallback classique : `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` → compte `default`

**Classe `AccountRegistry`** (`service/alpaca/accounts.py`) : singleton qui charge les comptes au premier accès. API : `list_accounts()`, `resolve(account_id)`, `get_credentials(account_id)`.

**Propagation** : chaque module accepte un paramètre `--account <ID>` en CLI. Si omis, le premier compte configuré est utilisé (rétrocompatibilité).

### 4.3 Base de données

- **SGBD** : MySQL 8.x, base `alpha_trade`, host `localhost`, charset `utf8mb4`
- **Pool** : `pool_size=2`, `max_overflow=3`, `pool_pre_ping=True`, `pool_recycle=3600`

### 4.5 Supervision Windows read-only

Le packaging Windows du watcher repose sur un script de supervision dédié :

- `scripts/windows/get_protection_watcher_status.ps1`

Ce script :

- interroge la tâche planifiée watcher ;
- interroge le service Windows / NSSM watcher ;
- remonte les chemins `stdout` / `stderr` détectables ;
- retourne un JSON structuré ;
- n'exécute aucune action `start/stop/install/remove`.

Payload fonctionnel remonté :

- bloc `task` : `exists`, `state`, `enabled`, `lastRunTime`, `nextRunTime`, `lastTaskResult`, `stdoutPath`, `stderrPath`, `actionArguments` ;
- bloc `service` : `exists`, `status`, `startType`, `displayName`, `stdoutPath`, `stderrPath` ;
- bloc `logSources` : sources importables `Task Scheduler stdout/stderr`, `NSSM stdout/stderr` quand détectables.

Le bridge Python impose plusieurs garde-fous :

- allowlist stricte (`status` uniquement à ce stade) ;
- exécution limitée à Windows (`os.name == "nt"`) ;
- timeout PowerShell ;
- absence d'arguments libres pour des scripts non allowlistés ;
- aucun start/stop/install/remove exposé.

### 4.4 Tables SQL (`database/sql/`)

- **stock/** : `stock_metadata`, `stock_bars`, `stock_bars_daily`, `stock_scores`, `stock_scores_history`, `stock_quote_snapshots`, `stock_earnings_calendar`, `cleaning_audit_latest`, `cleaning_audit_runs`
- **news/** : `news_raw`, `news_sentiment`, `news_ticker_map`, `macro_event_audit`, `ticker_daily_sentiment_features`, `sector_daily_sentiment_features`, `news_ingestion_checkpoint`
- **ml/** : `model_registry`, `model_training_run`, `model_metrics`, `model_predictions`
- **risk/** : `risk_decisions` ★, `portfolio_targets` ★
- **execution/** : `execution_runs` ★, `execution_targets_snapshot` ★, `execution_order_requests` ★, `execution_broker_orders`, `execution_broker_fills`, `execution_positions` ★, `execution_position_lots` ★, `execution_reconciliation_results` ★, `execution_locks` ★, `execution_events`, `broker_account_snapshots` ★, `broker_positions_snapshots` ★
- **corporate_actions/** : `corporate_actions_events`, `corporate_actions_applications` ★, `portfolio_cash_ledger` ★

> ★ = tables avec colonne `account_id VARCHAR(32)` pour le support multi-comptes. Migration : `database/sql/migration_add_account_id.sql` ou Alembic `0002_add_account_id`.

---

## 5. Flux Techniques

### 5.1 Initialisation (`run_execution.py`)

```python
config   = ExecutionConfig(**preset, account_id="live1")  # ou None pour le compte par défaut
repo     = ExecutionRepository()              # lazy SQLAlchemy engine
client   = AlpacaTradingClient(broker_mode, account_id="live1")  # credentials résolues via AccountRegistry
broker   = BrokerAdapter(client, config)      # couche d'isolation
oco      = OcoManager(broker, repo)           # OCO synthétique
executor = ProductionExecutor(config, repo, broker, oco)
metrics  = executor.execute_run(risk_run_id, trade_date)
```

### 5.2 Appels API

- Transport via `requests.Session`, headers `APCA-API-KEY-ID` / `APCA-API-SECRET-KEY`
- Retry : 5 tentatives max, backoff `1.0 * 2^attempt` secondes
- 4xx → `BrokerApiError` immédiat (pas de retry) ; 429/5xx → retry ; timeout → retry

### 5.3 Gestion des erreurs

| Couche | Stratégie |
|---|---|
| Client HTTP | Retry borné + backoff, `BrokerApiError` pour 4xx |
| Executor | Retry réseau/5xx/429 uniquement, pas de retry 4xx (403 = permanent) |
| Kill switch | Arrêt après 3 échecs consécutifs |
| Circuit breaker | Abandon du run si drawdown/perte excessive |
| DB | `try/except` avec logging, pas de crash si table absente en test |
| Pipeline chunks | Isolation : un chunk en erreur ne bloque pas les autres |

### 5.4 Logs

- Format : `%(asctime)s %(levelname)-8s %(name)s -- %(message)s`
- Niveaux : DEBUG / INFO / WARNING / ERROR / CRITICAL
- Chaque module : `LOGGER = logging.getLogger(__name__)`
- Sortie : stdout + **RotatingFileHandler** (`alpha_trade.log`, 5 Mo, 3 backups)
- Fonction utilitaire : `common.utils.setup_logging_with_file_handler()`

### 5.5 Flux techniques `modelFactory`

#### Entraînement (`python -m modelFactory --mode train`)

1. résolution de l'univers depuis `--symbols` ou `stock_scores.is_candidate=1` ;
2. chargement des bars, benchmark, sentiment et univers selon les options activées ;
3. entraînement du `LSTMAttentionModule` ;
4. calibration / optimisation de seuil côté LSTM ;
5. entraînement optionnel des challengers locaux `LightGBM` et `CatBoost` ;
6. entraînement optionnel du `global_model` ;
7. construction des `artifact_routes` par symbole ;
8. évaluation de l'éligibilité de chaque backend ;
9. sélection du champion servi (`default`, `fallback_default_champion` ou `auto_selected_champion`) ;
10. persistance des artefacts sur disque et des résumés DB.

#### Inférence (`python -m modelFactory --mode predict`)

1. résolution `config.json` / artefacts ;
2. lecture de `artifact_routes.selected_model` ;
3. routage du backend effectivement servi ;
4. rechargement PIT-safe des données jusqu'à `prediction_date` / `as_of_date` ;
5. génération des features ;
6. calcul de `predicted_proba` et `predicted_class` ;
7. insertion dans `model_predictions` si `persist=True`.

#### Limite DB actuelle

`model_predictions` ne persiste aujourd'hui que :

- `symbol`
- `prediction_date`
- `predicted_proba`
- `predicted_class`
- `run_id`

Le détail de serving (`selected_model`, `decision_threshold`, `signal_label`, `calibration_method`) est présent dans les résultats en mémoire et les artefacts, mais pas encore dans le schéma SQL.

### 5.6 Flux technique du watcher post-exécution

Positionnement technique :

- le watcher ne s'exécute pas avant le pipeline 1→11 ;
- il devient pertinent **après** `run_execution.py` / l'étape 12 `execution` ;
- il peut tourner en parallèle des étapes 13 et 14 `corporate_actions_*`.

Séquence type :

1. `Execution` écrit `execution_runs`, fige `execution_targets_snapshot`, persiste `execution_order_requests`, `execution_broker_orders`, `execution_broker_fills`, `execution_events` et les instantanés broker ;
2. le watcher lit les ordres/protections en attente depuis le repository d'exécution ;
3. il vérifie les conditions de transition stop initial → trailing stop ;
4. il annule / soumet les ordres broker nécessaires ;
5. il persiste un résumé métier `execution_protection_watch` ou `execution_protection_watch_service` ;
6. l'IHM `Supervision Ops` lit ensuite ces résumés, les logs IHM locaux et, côté Windows, le statut read-only de Task Scheduler / NSSM.

Points d'entrée principaux :

```powershell
python run_execution_protection_watch.py --mode once --account default
python run_execution_protection_watch.py --mode service --account default
```

Packaging Windows :

- `scripts/windows/protection_watcher_launcher.ps1` : bootstrap `.env` / DPAPI / Python ;
- `scripts/windows/install_protection_watcher_task.ps1` : mode `once` périodique ;
- `scripts/windows/install_protection_watcher_service_nssm.ps1` : service persistant ;
- `scripts/windows/get_protection_watcher_status.ps1` : supervision read-only.

Référence dédiée : voir aussi `doc/watcher.md`.

---

## 6. Sécurité

- Secrets via `os.getenv()`, masqués à l'affichage (4 chars + `****`)
- Pas de secrets en dur dans le code
- SQLAlchemy `text()` + `bindparam` contre l'injection SQL
- Confirmation interactive pour le mode live (`oui` requis)
- **Risques** : credentials en clair dans l'env shell → recommander Vault/AWS SSM ; pas de SSL DB par défaut

---

## 7. Performance / Robustesse

- **Parallélisme** : ProcessPoolExecutor (screener), ThreadPoolExecutor (scanner, I/O bound)
- **Rate limiting** : 200ms (bars), 350ms (ordres), backoff 20-60s sur 429
- **Pool DB** : 2+3 connexions/worker, pre-ping, recycle 1h
- **Idempotence** : clés SHA-256 contre les doublons d'ordres
- **Kill switch** : 3 échecs consécutifs → arrêt
- **Batch throttle** : pause tous les 20 ordres
- **Fill timeout** : 120s (paper) / 180s (live)
- **ML GPU** : sur une machine avec un seul GPU CUDA, `modelFactory` force l'entraînement séquentiel (`effective_workers=1`) même si `max_workers>1`, afin d'éviter plusieurs sous-processus concurrents sur la même carte. Les `DataLoader` activent `pin_memory=True` quand CUDA est disponible.

---

## 8. Dette Technique

| Élément | Priorité |
|---|---|
| ~~Double `return selected` dans `alpha_scanner.py` ligne 766 (code mort)~~ → ✅ Corrigé | ~~P0~~ |
| ~~`bar_metadata.py` utilise DB-API raw au lieu de SQLAlchemy Core~~ → ✅ Migré vers `sqlalchemy.text()` | ~~P1~~ |
| ~~Pas de migration DB (Alembic absent)~~ → ✅ Alembic ajouté | ~~P1~~ |
| ~~Pas de handler fichier pour les logs (stdout seul)~~ → ✅ RotatingFileHandler ajouté | ~~P1~~ |
| ~~Import dynamique `risk_management` dans `executor.py` (couplage runtime)~~ → ✅ Circuit breaker injecté via constructeur | ~~P2~~ |
| ~~Méthode `_make_entry` V1 inutilisée dans `portfolio_builder.py`~~ → ✅ Supprimée (seul `_make_entry_v2` reste) | ~~P2~~ |
| `prompt/execution/` : historique audit → plan → sprints → cutover désormais structuré ; homogénéisation du reste de `prompt/` encore perfectible | P3 |
| ~~`configure_optimizers()` sans type hint dans `model.py`~~ → ✅ Type hint `-> torch.optim.Optimizer` ajouté | ~~P3~~ |
| ~~`corporate_actions*` absent de `pyproject.toml` packages.find.include~~ → ✅ Ajouté (`corporate_actions*`, `ihm*`) | ~~P1~~ |

---

## 9. Recommandations de Refactoring

**Court terme (P0-P1)** :
1. ~~Supprimer le `return selected` dupliqué dans `alpha_scanner.py:766`~~ → ✅ Fait
2. ~~Migrer `bar_metadata.py` vers SQLAlchemy Core~~ → ✅ Fait
3. ~~Ajouter Alembic pour les migrations de schéma~~ → ✅ Fait
4. ~~Ajouter RotatingFileHandler pour les logs~~ → ✅ Fait
5. ~~Supprimer `_make_entry` V1 dans `portfolio_builder.py`~~ → ✅ Fait
6. ~~Ajouter `corporate_actions*` et `ihm*` dans `pyproject.toml` packages.find.include~~ → ✅ Fait

**Moyen terme (P2)** :
7. ~~Extraire le circuit breaker de l'import dynamique → injection via constructeur~~ → ✅ Fait
8. Ajouter une interface `BrokerPort` (Protocol) pour abstraire le broker
9. ~~Unifier les configs : YAML/TOML centralisé~~ → ✅ `config.yaml` + `load_config()` ajoutés
10. Tests d'intégration avec MySQL Docker (testcontainers)

**Long terme (P3)** :
11. Orchestrateur pipeline (Airflow/Prefect)
12. Monitoring (Prometheus/Grafana)
13. Containerisation Docker
14. ~~Framework de backtest intégré~~ → ✅ Implémenté : module `backtesting/` (vectorbt)

---

## 10. Comment Lancer le Projet Localement

### Installation

```powershell
pip install -e ".[dev]"
```

### Configuration

```powershell
$env:LOGIN_DB = "user"; $env:PASSWORD_DB = "pass"
$env:ALPACA_API_KEY = "PK..."; $env:ALPACA_SECRET_KEY = "..."
$env:FINNHUB_API_KEY = "..."   # optionnel
```

### Créer les tables

Utiliser le bundle SQL cible de `database/sql/` (stock/ → news/ → ml/ → risk/ → execution/ → corporate_actions/), par exemple via `database/sql/all_tables.py`.

Dans le périmètre `execution/`, le cutover canonique n'installe plus les anciens fichiers `execution_orders.sql` et `execution_fills.sql` : le bootstrap cible repose désormais sur `execution_targets_snapshot`, `execution_order_requests`, `execution_broker_orders`, `execution_broker_fills`, `execution_positions`, `execution_position_lots`, `execution_reconciliation_results`, `execution_locks`, `execution_events`, `broker_account_snapshots` et `broker_positions_snapshots`.

### Pipeline complet

```powershell
# Init (une fois) — correspond dans l'IHM aux steps auxiliaires Data Integrity hors workflow quotidien :
python -m dataIntegrityEngine.import_alpaca_assets
python -m dataIntegrityEngine.update_sector

# Quotidien — workflow IHM 1 → 14, dans cet ordre strict :
python -m dataIntegrityEngine.import_alpaca_bar           # 1.  import bars
python -m dataIntegrityEngine.data_sanitizer_daily        # 2.  sanitize bars
python -m screener.stock_screener                         # 3.  screener
python -m dataIntegrityEngine.sync_latest_quotes          # 4.  snapshot quotes pour filtre de spread
python -m dataIntegrityEngine.sync_earnings_calendar      # 5.  earnings blackout
python -m selector.alpha_scanner                          # 6.  alpha scanner
python -m event_sentiment                                 # 7.  sentiment pipeline
python -m event_sentiment.signal_aggregator               # 8.  signal aggregator
python -m modelFactory --mode train --include-sentiment --compare-lightgbm --enable-catboost --select-champion --optimize-thresholds --accelerator gpu --max-workers 1  # 9.  ML train périodique
python -m modelFactory --mode predict --accelerator gpu   # 10. ML predict quotidien
python -m risk_management.run_risk --account-equity 100000  # 11. risk management
python run_execution.py simulate                          # 12. execution (ou paper / live)
python -m corporate_actions sync --portfolio-only         # 13. sync CA sur positions détenues
python -m corporate_actions apply                         # 14. appliquer CA sur positions

# Pour cibler un compte spécifique (multi-comptes) :
python -m risk_management.run_risk --account-equity 100000 --account live1
python run_execution.py paper --account live1
python -m corporate_actions sync --account live1
python -m corporate_actions apply --account live1
```

Notes ML GPU :

- `--accelerator auto` : utilise le GPU si CUDA est détecté, sinon CPU ;
- `--accelerator gpu` : demande explicitement le GPU ; si CUDA est indisponible, l'inférence retombe sur CPU avec un warning, tandis que l'entraînement Lightning reste dépendant du backend disponible ;
- sur une machine à GPU unique, préférer `--max-workers 1` pour `ml_train`.

### IHM Streamlit

```powershell
python -m streamlit run ihm/app.py
```

La page `ihm/pages/pipeline.py` expose désormais :

- un **workflow quotidien complet 1 → 14** ;
- une zone **Bootstrap / maintenance Data Integrity** hors workflow avec :
  - `B1. Import univers Alpaca` → `python -m dataIntegrityEngine.import_alpaca_assets`
  - `B2. Mise à jour fondamentaux` → `python -m dataIntegrityEngine.update_sector ...`
- un **centre d'exécution & d'investigation** pour suivre les runs actifs, consulter/télécharger les logs et comparer deux runs ;
- des **résumés métier structurés** extraits automatiquement quand un script écrit un payload préfixé par `::alpha_trade_run_summary::`.

Depuis la page `ihm/pages/pipeline.py`, les étapes `ML Train` et `ML Predict` exposent aussi un sous-ensemble cohérent des options `modelFactory` :

- **Accélérateur ML** (`auto | cpu | gpu`) ;
- inclusion du **sentiment** ;
- activation des challengers **LightGBM** et **CatBoost** ;
- activation optionnelle du **modèle global** ;
- activation des **features cross-sectionnelles** ;
- activation de la **sélection automatique du champion** ;
- choix de la **métrique de sélection** ;
- optimisation du **seuil de décision** ;
- optimisation optionnelle de la **target**.

Le bloc de paramètres Pipeline expose en plus les options `Data Integrity` réellement supportées côté backend :

- `sync_latest_quotes` : `limit`, `batch-size` ;
- `sync_earnings_calendar` : `from-date`, `to-date`, `limit`, `sleep-seconds` ;
- `update_sector` : `limit`, `sleep-seconds`, `log-every`.

`ML Predict` n'expose pas de choix de backend manuel : il réutilise le `selected_model` trouvé dans les artefacts du symbole.

Le workflow complet IHM insère `python -m dataIntegrityEngine.sync_latest_quotes` puis `python -m dataIntegrityEngine.sync_earnings_calendar` avant `Alpha Scanner`, afin d'alimenter automatiquement `stock_quote_snapshots` et `stock_earnings_calendar`.

L'étape `Alpha Scanner` n'expose plus de toggle de preset : `python -m selector.alpha_scanner` applique déjà le profil strict partagé.

Enfin, les résumés métier capturés par l'IHM sont réexposés dans :

- la page `Pipeline` (run individuel + workflow parent) ;
- la page `Overview` (résumés récents) ;
- la page `Screening` (contexte qualité amont).

### Backtesting

```powershell
# Backtest standard
python -m backtesting run --start 2025-01-01 --end 2025-03-31 --equity 100000

# Mode pipeline strict PIT
python -m backtesting run --start 2025-01-01 --end 2025-03-31 --engine-mode pipeline --equity 100000

# Compte < 25k avec règle PDT
python -m backtesting run --start 2025-01-01 --end 2025-03-31 --equity 2000 --account-type margin --pdt-rule auto

# Cash account + swing strict
python -m backtesting run --start 2025-01-01 --end 2025-03-31 --equity 2000 --account-type cash --swing-only

# Replay le plus proche du pipeline live aujourd'hui
python -m backtesting run --start 2025-01-01 --end 2025-03-31 --engine-mode pipeline --ml-pit-strategy use-persisted --phase2-mode risk_execution --phase3-mode execution_replay --phase4-mode protection_replay --phase5-mode watcher_replay --phase7-mode exit_lifecycle_replay

# Microstructure et overlays research-grade
python -m backtesting run --start 2025-01-01 --end 2025-03-31 --slippage-model sqrt --slippage-base-bps 2 --slippage-impact-coef 25 --initial-stop-pct 0.07 --max-sector-exposure-pct 0.30 --target-annual-vol 0.15

# Backfill PIT
python -m backtesting backfill-scores-history --start 2025-01-01 --screener-workers 2

# Diagnostic et recommandation screener
python -m backtesting diagnose-screener --start 2024-01-01 --end 2024-12-31 --mode oat --limit-days 60
python -m backtesting recommend-screener --input-dir artifacts/screener_diagnostics

# Calibration sentiment / walk-forward
python -m backtesting calibrate-sentiment-weights --start 2024-01-01 --end 2025-12-31 --top-n 20 --horizons 5,10,20
python -m backtesting walk-forward-sentiment --start 2024-01-01 --end 2025-12-31 --min-train-days 252 --test-days 63 --max-positions 20
```

Notes :

- `--engine-mode pipeline` exige un historique PIT valide dans `stock_scores_history` ;
- `--phase3-mode` dépend de `phase2_mode=risk_execution`, `--phase4-mode` dépend de `phase3-mode`, `--phase5-mode` dépend de `phase4-mode`, `--phase7-mode` dépend de `phase5-mode` ;
- `report.json` inclut `summary`, `params`, `diagnostics`, `run_metadata` et `fidelity` ;
- `fidelity_manifest.json` documente les dégradations PIT éventuelles ;
- les modules `analytics.py`, `cache.py` et `statistical_validation.py` fournissent des briques complémentaires non branchées automatiquement à la commande `run` standard.

### Execution Engine — contraintes de compte

Le moteur d'exécution applique désormais la même sémantique métier que le backtesting autour de trois axes :

- `account_type = margin|cash`
- `pdt_rule = auto|off`
- `swing_only = True|False`

Effets principaux :

- en `margin`, l'executor se base sur `buying_power` broker pour autoriser les achats ;
- en `cash`, il se base sur `non_marginable_buying_power` / `cash` settled ;
- si `pdt_rule=auto` et `equity < 25 000 $`, les armements de children susceptibles de produire du day trading peuvent être différés quand le quota de day trades est épuisé ;
- si `swing_only=True`, le take-profit et le trailing stop ne sont pas armés le jour même du fill.

### Backfill historique des snapshots de scores

```powershell
# Test rapide sur 1 séance (validation technique)
python -m backtesting backfill-scores-history --start 2026-04-17 --limit-days 1 --screener-workers 1

# Backfill complet des séances manquantes depuis 2025-01-01
# La borne haute est résolue automatiquement jusqu'à la dernière séance AVANT
# le premier snapshot déjà présent dans stock_scores_history.
python -m backtesting backfill-scores-history --start 2025-01-01 --screener-workers 1

# Variante avec borne explicite
python -m backtesting backfill-scores-history --start 2025-01-01 --end 2026-04-16 --screener-workers 1

# Recalcul forcé des jours déjà historisés
python -m backtesting backfill-scores-history --start 2026-04-17 --end 2026-04-17 --overwrite-existing --screener-workers 1
```

Notes :
- le backfill reconstruit `stock_scores_history` directement depuis `stock_bars_daily` + features sentiment déjà en base ;
- il recharge aussi les overlays `market_cap`, `spread_bps` et `earnings` de manière point-in-time via `reference_date=as_of_date` ;
- il n'écrit PAS dans `stock_scores` courant ;
- il saute automatiquement les dates déjà historisées, sauf avec `--overwrite-existing` ;
- pour un backfill massif, commencer avec `--limit-days 1` ou `--limit-days 5` pour valider le débit sur la machine.

### Tests

```powershell
python -m pytest                # tous les tests
python -m pytest -v -k executor # tests ciblés
ruff check .                    # lint
mypy .                          # types
python run_execution.py check   # vérif environnement
```
