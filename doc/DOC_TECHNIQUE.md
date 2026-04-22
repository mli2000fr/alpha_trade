# Alpha Trade — Documentation Technique

> *Version : 0.3.0 — Python ≥ 3.12 — Dernière mise à jour : avril 2026*

---

## 1. Architecture Générale

### 1.1 Structure des dossiers

```
alpha_trade/
├── run_execution.py              ← Point d'entrée principal (CLI interactif ou arguments)
├── pyproject.toml                ← Config build, dépendances, ruff, mypy
├── requirements.txt / -dev.txt   ← Dépendances runtime et dev
├── config.yaml                   ← Configuration centralisée YAML (DB, Alpaca, risk)
├── alembic.ini + alembic/        ← Migrations de schéma DB (Alembic)
├── mypy.ini / pytest.ini         ← Config mypy et pytest (cov ≥ 60%)
├── README.md                     ← Documentation rapide + ordre d'exécution
├── DOC_FONCTIONNELLE.md          ← Documentation fonctionnelle complète
├── DOC_TECHNIQUE.md              ← Ce document
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
├── execution_engine/             ← OMS/EMS : ordres, polling, bracket, réconciliation, TCA
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
| `modelFactory/` | Entraînement/prédiction LSTM per-symbol |
| `risk_management/` | Sizing ATR/Kelly, contraintes, circuit breaker, portefeuille |
| `execution_engine/` | OMS/EMS complet (10 phases) |
| `corporate_actions/` | Gestion dividendes, splits, reverse splits (audit + comptabilité portefeuille) |
| `backtesting/` | Backtest intégré vectorbt : replay signaux conviction, bracket TP/TS, métriques, equity curve |
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
6. Submit children (synthetic bracket : TP limit + TS trailing), avec report possible en cas de `swing_only` / `PDT`
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

**`train_symbol()` / `predict_symbol()`** (`modelFactory/trainer.py`, `modelFactory/predictor.py`) — services d'entraînement et d'inférence par symbole. Les deux chemins supportent désormais `accelerator=auto|cpu|gpu` :

- `train` s'appuie sur Lightning et résout `cuda:0` si disponible ;
- `predict` charge explicitement le checkpoint sur `cuda:0` en mode `auto`/`gpu` lorsque CUDA est disponible, sinon retombe sur CPU ;
- les logs du module ML journalisent le `requested_accelerator`, le `resolved_device` et le `device_name` effectif.

**`BrokerAdapter`** (`execution_engine/broker_adapter.py`) — Couche d'isolation broker : traduit `OrderIntent` → payload Alpaca → `BrokerOrder`. Expose aussi le snapshot de compte (`equity`, `buying_power`, `cash`, `non_marginable_buying_power`, `daytrade_count`) utilisé pour appliquer les contraintes `margin/cash/PDT` côté exécution. Seul fichier à modifier pour changer de broker.

**`CircuitBreaker`** (`risk_management/circuit_breaker.py`) — Suspend le trading si drawdown ≥ 15% ou perte daily ≥ 5%.

**`OcoManager`** (`execution_engine/oco_manager.py`) — Gestion OCO synthétique : quand un enfant bracket est FILLED, annule le sibling.

**`CorporateActionEngine`** (`corporate_actions/engine.py`) — Orchestrateur corporate actions en 2 phases : `sync()` (ingestion provider → DB) et `apply()` (application idempotente sur positions). Stratégie : les OHLCV restent gérés par Alpaca (`adjustment="all"`), ce module gère uniquement la comptabilité portefeuille (qty, cost basis, cash). La sync résout par défaut l'univers depuis `stock_metadata` (`status='active'`, `tradable=1`, `bars_available=1`), puis interroge Alpaca par lots configurables (`batch_size`, défaut 25) avec persistance immédiate en base après chaque lot.

**`AlpacaCorporateActionProvider`** (`corporate_actions/provider.py`) — Provider abstrait pour l'ingestion des dividendes et splits depuis l'API Alpaca Corporate Actions (`v1/corporate-actions`). Gère pagination (`next_page_token`), tri `asc`, `limit=1000`, retry réseau/HTTP, et retry spécifique aux timeouts sur le modèle de `fetch_bars` du client Alpaca. Extensible vers Polygon, Finnhub, etc.

**`CorporateActionRepository`** (`corporate_actions/db_io.py`) — Accès DB (SQLAlchemy Core) : insert/load événements, applications, cash ledger, lecture des positions broker et résolution de l'univers de sync depuis `stock_metadata`. Compatible MySQL et SQLite (tests).

**`AccountRegistry`** (`service/alpaca/accounts.py`) — Singleton de résolution multi-comptes. Charge les comptes depuis `config.yaml`, env vars préfixées, ou fallback classique. Fournit `resolve(account_id)` → `BrokerAccount(api_key, secret_key, mode)`. Tous les clients (trading, market data, news, corporate actions) passent par cette résolution.

**`BacktestEngine`** (`backtesting/simulator.py`) — Moteur de backtest. En mode `standard`, il s'appuie sur vectorbt (`vbt.Portfolio.from_signals()`) avec bracket TP/trailing SL. Quand une contrainte de compte est activée, il bascule sur une simulation Python stateful pour appliquer correctement les règles `PDT`, `swing-only` et `cash account` (cash settled T+1). Sizing equal-weight plafonné à `max_positions`. Paramétrable via `BacktestConfig` (hérite de `RiskConfig` + `ExecutionConfig`).

**`TradingConstraintConfig`** (`backtesting/trading_constraints.py`) — Dataclass pure décrivant les contraintes de compte backtesting via trois axes indépendants : `account_type` (`margin|cash`), `pdt_rule` (`auto|off`) et `swing_only` (`bool`). Encapsule le seuil `25 000 $`, la limite `3 day trades / 5 séances` et le settlement simplifié `T+1` pour les cash accounts. Un mapping legacy depuis `standard|pdt|swing|cash` est conservé temporairement pour compatibilité CLI.

**`replay_signals()`** (`backtesting/signal_replay.py`) — Reconstruction jour par jour des signaux de conviction à partir des scores `stock_scores`, avec fallback ligne par ligne `final_score_sentiment -> final_score` si le sentiment est absent, et fusion optionnelle des prédictions ML `model_predictions`. Top-N candidats sélectionnés par jour.

**`BacktestReport`** (`backtesting/report.py`) — Dataclass de résumé : Sharpe, Sortino, CAGR, max drawdown, win rate, profit factor. Génère equity curve PNG et export trades CSV dans `artifacts/backtesting/`.

**`BackfillScoresHistoryService`** (`backtesting/backfill_scores_history.py`) — Orchestrateur de backfill point-in-time de `stock_scores_history`. Rejoue, pour chaque séance manquante, le screener sur `stock_bars_daily`, le scoring `AlphaScanner`, puis la fusion sentiment `SentimentSignalAggregator`, avant insertion idempotente dans `stock_scores_history`. Permet de rendre le backtest réellement exploitable sur plusieurs années sans dépendre d'un snapshot courant unique. Quand un run strict impose des filtres d'éligibilité plus durs (prix, liquidité, volatilité relative), ceux-ci doivent être injectés dans `scanner_config` dès le backfill pour que les snapshots PIT reflètent exactement le même univers que le rerun.

**`prepare_predictions_for_ml_mode()` / `prepare_scores_for_sentiment_mode()`** (`backtesting/resilience.py`) — Couche de résilience du backtest. Implémente les politiques `auto | off | rebuild-missing` pour les prédictions ML et le sentiment : fallback sans ML, neutralisation du boost sentiment, ou reconstruction ciblée des données manquantes lorsque les artefacts / tables nécessaires sont disponibles.

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

### 4.4 Tables SQL (`database/sql/`)

- **stock/** : `stock_metadata`, `stock_bars`, `stock_bars_daily`, `stock_scores`, `stock_scores_history`, `stock_quote_snapshots`, `stock_earnings_calendar`, `cleaning_audit_log`
- **news/** : `news_raw`, `news_sentiment`, `news_ticker_map`, `macro_event_audit`, `ticker_daily_sentiment_features`, `sector_daily_sentiment_features`, `news_ingestion_checkpoint`
- **ml/** : `model_registry`, `model_training_run`, `model_metrics`, `model_predictions`
- **risk/** : `risk_decisions` ★, `portfolio_targets` ★
- **execution/** : `execution_runs` ★, `execution_orders`, `execution_fills`, `execution_events`, `broker_positions_snapshots` ★
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
| Dossier `prompt/` (fichiers non structurés, hors code) | P3 |
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

Exécuter les `.sql` de `database/sql/` dans MySQL (stock/ → news/ → ml/ → risk/ → execution/ → corporate_actions/).

### Pipeline complet

```powershell
# Init (une fois)
python -m dataIntegrityEngine.import_alpaca_assets
python -m dataIntegrityEngine.update_sector

# Quotidien — dans cet ordre strict :
python -m dataIntegrityEngine.import_alpaca_bar         # 1.  import bars
python -m dataIntegrityEngine.data_sanitizer_daily       # 2.  sanitize bars
python -m screener.stock_screener                        # 3.  screener
python -m selector.alpha_scanner                         # 4.  alpha scanner
python -m event_sentiment                                # 5.  sentiment pipeline
python -m event_sentiment.signal_aggregator              # 6.  signal aggregator
python -m modelFactory --mode train --include-sentiment --accelerator gpu --max-workers 1  # 7.  ML train périodique
python -m modelFactory --mode predict --accelerator gpu  # 8.  ML predict quotidien
python -m risk_management.run_risk --account-equity 100000  # 9.  risk management
python run_execution.py simulate                         # 10. execution (ou paper / live)
python -m corporate_actions sync --portfolio-only        # 11. sync CA sur positions détenues
python -m corporate_actions apply                        # 12. appliquer CA sur positions

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

Depuis la page `ihm/pages/pipeline.py`, les étapes `ML Train` et `ML Predict` exposent un paramètre **Accélérateur ML** (`auto | cpu | gpu`). L'IHM détecte la disponibilité locale de CUDA et transmet `--accelerator <mode>` aux sous-processus `modelFactory` lancés en arrière-plan. Le workflow complet IHM insère désormais `python -m dataIntegrityEngine.sync_latest_quotes` puis `python -m dataIntegrityEngine.sync_earnings_calendar` avant `Alpha Scanner`, afin d'alimenter automatiquement `stock_quote_snapshots` et `stock_earnings_calendar`. L'étape `Alpha Scanner` n'expose plus de toggle de preset : `python -m selector.alpha_scanner` applique déjà le profil strict partagé.

### Backtesting

```powershell
# Backtest complet sur 10 ans (paramètres production)
python -m backtesting run --start 2016-01-01 --end 2026-04-20 --equity 100000

# Backtest personnalisé (TP=10%, TS=4%, 15 positions max)
python -m backtesting run --start 2020-01-01 --end 2026-04-20 --equity 50000 --tp 0.10 --ts 0.04 --max-positions 15

# Compte < 25k avec règle PDT (3 day trades max sur 5 séances)
python -m backtesting run --start 2025-01-01 --end 2025-03-31 --equity 2000 --account-type margin --pdt-rule auto

# Swing strict : aucune sortie le jour même
python -m backtesting run --start 2025-01-01 --end 2025-03-31 --equity 2000 --account-type margin --pdt-rule off --swing-only

# Cash account : cash settled uniquement (T+1)
python -m backtesting run --start 2025-01-01 --end 2025-03-31 --equity 2000 --account-type cash

# Cash account + swing strict
python -m backtesting run --start 2025-01-01 --end 2025-03-31 --equity 2000 --account-type cash --swing-only

# Sans sauvegarde artefacts (console only)
python -m backtesting run --start 2023-01-01 --no-save

# Modes de résilience ML / sentiment
python -m backtesting run --start 2025-01-01 --end 2026-04-17 --equity 100000 --ml-mode off --sentiment-mode off
python -m backtesting run --start 2025-01-01 --end 2026-04-17 --equity 100000 --ml-mode auto --sentiment-mode auto
python -m backtesting run --start 2025-01-01 --end 2026-04-17 --equity 100000 --ml-mode rebuild-missing --artifacts-dir artifacts/models
python -m backtesting run --start 2025-01-01 --end 2026-04-17 --equity 100000 --sentiment-mode rebuild-missing

# Reconstruction ML + sentiment en même temps
python -m backtesting run --start 2025-01-01 --end 2026-04-17 --equity 100000 --ml-mode rebuild-missing --sentiment-mode rebuild-missing --artifacts-dir artifacts/models

# Artefacts générés dans artifacts/backtesting/ :
#   - equity_curve.png   (courbe de valeur du portefeuille)
#   - trades.csv         (liste de tous les trades avec P&L)
```

Notes :

- `--ml-mode auto` (défaut) : utilise les prédictions disponibles et ignore les trous ;
- `--ml-mode off` : désactive entièrement la composante ML ;
- `--ml-mode rebuild-missing` : tente de reconstruire les prédictions historiques manquantes depuis `artifacts/models/`, en bornant l'inférence à la date du signal ;
- `--account-type margin` (défaut) : simule un compte margin ;
- `--account-type cash` : simule un cash account, sans levier implicite et avec utilisation du cash settled uniquement ;
- `--pdt-rule auto` (défaut) : applique la règle PDT sur un compte margin si `equity < 25 000 $` ;
- `--pdt-rule off` : désactive la contrainte PDT dans le backtest ;
- `--swing-only` : interdit les sorties le jour même de l'entrée ;
- `--sentiment-mode auto` (défaut) : utilise `final_score_sentiment` si disponible, sinon fallback sur `final_score` ;
- `--sentiment-mode off` : neutralise le sentiment (`final_score_sentiment = final_score`) ;
- `--sentiment-mode rebuild-missing` : tente de reconstruire les snapshots PIT manquants dans `stock_scores_history`, puis applique un fallback sur `final_score` pour les lignes encore incomplètes.

Le manifeste `report.json` produit par le backtest inclut désormais un bloc `diagnostics` permettant d'auditer l'effet de ces contraintes (`blocked_pdt_day_trades`, `blocked_same_day_exits`, `blocked_cash_entries`, `executed_day_trades`).

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
