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
| `selector/` | Scoring avancé (Minervini, VCP, neutralisation sectorielle) |
| `event_sentiment/` | NLP FinBERT + fusion scores quant/sentiment |
| `modelFactory/` | Entraînement/prédiction LSTM per-symbol |
| `risk_management/` | Sizing ATR/Kelly, contraintes, circuit breaker, portefeuille |
| `execution_engine/` | OMS/EMS complet (10 phases) |
| `corporate_actions/` | Gestion dividendes, splits, reverse splits (audit + comptabilité portefeuille) |
| `ihm/` | IHM Streamlit : supervision pipeline, scores, risque, exécution, CA |

---

## 2. Analyse Détaillée du Code

### 2.1 Classes principales

**`ProductionExecutor`** (`execution_engine/executor.py`) — Orchestrateur en 10 phases :
1. Init (build_run_id)
2. Pre-flight (chargement cibles, circuit breaker, market hours)
3. Build intents + déduplication par idempotency_key
4. Submit entries (avec retry réseau, kill switch, throttle batch)
5. Poll fills (polling broker jusqu'à terminal state)
6. Submit children (synthetic bracket : TP limit + TS trailing)
7. *(phase réservée)*
8. Réconciliation (positions broker vs cibles, rebalance optionnel)
9. TCA (slippage, implementation shortfall)
10. Finalize (persist events, update run status)

**`AlphaScanner`** (`selector/alpha_scanner.py`) — Scanner multi-facteurs en chunks parallèles (ThreadPoolExecutor) : `fetch_market_data()` → `compute_factors()` → `merge_scores()` → `apply_filters()` → neutralisation sectorielle cross-sectorielle sur univers complet → `rank_and_select()`.

**`PortfolioBuilder`** (`risk_management/portfolio_builder.py`) — Construction portefeuille : enrichir candidats (conviction score) → trier par conviction DESC → filtre corrélation → sizing ATR/Kelly → check contraintes → ACCEPTED / REDUCED / REJECTED.

**`SentimentSignalAggregator`** (`event_sentiment/signal_aggregator.py`) — Fusion `75% quant + 15% sentiment ticker + 10% macro sectoriel` → `final_score_sentiment`.

**`LSTMAttentionModule`** (`modelFactory/model.py`) — LightningModule : LSTM multi-couche + Temporal Attention (soft-attention axe temporel) + classification binaire (CrossEntropyLoss). Métriques : BinaryAccuracy, BinaryPrecision, BinaryRecall, BinaryAUROC.

**`BrokerAdapter`** (`execution_engine/broker_adapter.py`) — Couche d'isolation broker : traduit `OrderIntent` → payload Alpaca → `BrokerOrder`. Seul fichier à modifier pour changer de broker.

**`CircuitBreaker`** (`risk_management/circuit_breaker.py`) — Suspend le trading si drawdown ≥ 15% ou perte daily ≥ 5%.

**`OcoManager`** (`execution_engine/oco_manager.py`) — Gestion OCO synthétique : quand un enfant bracket est FILLED, annule le sibling.

**`CorporateActionEngine`** (`corporate_actions/engine.py`) — Orchestrateur corporate actions en 2 phases : `sync()` (ingestion provider → DB) et `apply()` (application idempotente sur positions). Stratégie : les OHLCV restent gérés par Alpaca (`adjustment="all"`), ce module gère uniquement la comptabilité portefeuille (qty, cost basis, cash). La sync résout par défaut l'univers depuis `stock_metadata` (`status='active'`, `tradable=1`, `bars_available=1`), puis interroge Alpaca par lots configurables (`batch_size`, défaut 25) avec persistance immédiate en base après chaque lot.

**`AlpacaCorporateActionProvider`** (`corporate_actions/provider.py`) — Provider abstrait pour l'ingestion des dividendes et splits depuis l'API Alpaca Corporate Actions (`v1/corporate-actions`). Gère pagination (`next_page_token`), tri `asc`, `limit=1000`, retry réseau/HTTP, et retry spécifique aux timeouts sur le modèle de `fetch_bars` du client Alpaca. Extensible vers Polygon, Finnhub, etc.

**`CorporateActionRepository`** (`corporate_actions/db_io.py`) — Accès DB (SQLAlchemy Core) : insert/load événements, applications, cash ledger, lecture des positions broker et résolution de l'univers de sync depuis `stock_metadata`. Compatible MySQL et SQLite (tests).

**`AccountRegistry`** (`service/alpaca/accounts.py`) — Singleton de résolution multi-comptes. Charge les comptes depuis `config.yaml`, env vars préfixées, ou fallback classique. Fournit `resolve(account_id)` → `BrokerAccount(api_key, secret_key, mode)`. Tous les clients (trading, market data, news, corporate actions) passent par cette résolution.

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
| Finnhub | `finnhub.io/api/v1` | Profil société, secteur |

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

- **stock/** : `stock_metadata`, `stock_bars`, `stock_bars_daily`, `stock_scores`, `cleaning_audit_log`
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
14. Framework de backtest intégré

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
python -m corporate_actions sync --skip-existing         # 1a. ingérer CA (référentiel)
python -m dataIntegrityEngine.data_sanitizer_daily       # 2.  sanitize bars
python -m dataIntegrityEngine.stock_screener             # 3.  screener
python -m selector.alpha_scanner                         # 4.  alpha scanner
python -m event_sentiment                                # 5.  sentiment pipeline
python -m event_sentiment.signal_aggregator              # 6.  signal aggregator
python -m risk_management.run_risk --account-equity 100000  # 7.  risk management
python run_execution.py simulate                         # 8.  execution (ou paper / live)
python -m corporate_actions apply                        # 8a. appliquer CA sur positions

# Pour cibler un compte spécifique (multi-comptes) :
python -m risk_management.run_risk --account-equity 100000 --account live1
python run_execution.py paper --account live1
python -m corporate_actions sync --account live1
python -m corporate_actions apply --account live1
```

### IHM Streamlit

```powershell
python -m streamlit run ihm/app.py
```

### Tests

```powershell
python -m pytest                # tous les tests
python -m pytest -v -k executor # tests ciblés
ruff check .                    # lint
mypy .                          # types
python run_execution.py check   # vérif environnement
```
