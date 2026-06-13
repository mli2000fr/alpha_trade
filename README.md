# Alpha Trade

Plateforme Python de **trading algorithmique swing US** orientée production, construite autour d'un pipeline modulaire : ingestion marché, nettoyage, screening, sélection alpha, sentiment news, gestion du risque, exécution et suivi post-trade.

Le projet s'appuie principalement sur **Python 3.12**, **MySQL**, **SQLAlchemy**, **Alpaca**, **Finnhub**, **PyTorch/Lightning** et une **IHM Streamlit** pour la supervision opérateur.

> ℹ️ **Conventions clés (Phase 1 refactor — `prompt/refactor/audit_global.md`)**
>
> - **Politique de prix : `data_adjustment = 'split'`** (canonique projet).
>   Les splits sont neutralisés au niveau Alpaca ; les **dividendes** sont
>   comptabilisés séparément via le ledger `portfolio_cash_ledger`. Une
>   contrainte SQL `CHECK chk_bars_adj` / `chk_daily_adj` matérialise cette
>   convention sur `stock_bars` / `stock_bars_daily`. Voir `doc/database.md` §9
>   et `doc/dataIntegrityEngine.md`.
>   - Performance totale (dividendes inclus) =
>     `MTM(positions, stock_bars_daily.close) + cumulative(portfolio_cash_ledger)`
>
> - **Limites Alpaca free / IEX** : le feed gratuit IEX couvre ~2-3 % du volume
>   consolidé US. `volume`, `vwap`, spreads `stock_quote_snapshots` sont
>   biaisés ; les compteurs `symbols_zero_volume_30d`, `stale_quote_pct`,
>   `stale_market_cap_pct` sont propagés dans tous les `run_summary`
>   (helper `core.run_summary.merge_iex_bias_counters`). Voir le bandeau IEX
>   dans `doc/dataIntegrityEngine.md`.
>
> - **Sécurité opérationnelle** :
>   - `run_execution.py` est le **launcher canonique** du flux `run`
>     (`simulate | paper | live | check`). En mode `paper` / `live`, il lève désormais une
>     `RuntimeError` si `broker.get_account_equity()` échoue (plus de fallback
>     silencieux à 100 000 $).
>   - Le mode `live` exige la ressaisie exacte du label du compte broker.
>   - `python -m execution_engine` reste une **façade de compatibilité**
>     pour le flux `run` ; la sous-commande `cancel-all` y reste native.
>   - Les secrets DB (`LOGIN_DB`, `PASSWORD_DB`) doivent être en variables
>     d'environnement ; les valeurs sentinelles `pass`, `user`, `changeme`
>     sont rejetées au démarrage. `config.yaml` n'utilise que des
>     placeholders `${VAR}` (voir `core.secrets`).

---

## 1. Vue d'ensemble

Le pipeline couvre les besoins suivants :

- ingestion des actifs et barres de marché depuis Alpaca ;
- synchronisation et application des **corporate actions** ;
- nettoyage et alignement des données daily ;
- screening quantitatif et sélection multi-facteurs ;
- enrichissement par **sentiment news** via FinBERT ;
- construction du portefeuille cible avec contraintes de risque ;
- exécution des ordres en modes simulation, paper ou live ;
- supervision via une IHM Streamlit.

---

## 2. Modules principaux

| Module | Rôle |
|---|---|
| `dataIntegrityEngine/` | Import Alpaca, nettoyage daily, enrichissements de données |
| `screener/` | Screening initial liquidité / force relative / range historique |
| `selector/` | `AlphaScanner` multi-facteurs et sélection finale |
| `event_sentiment/` | Pipeline news, FinBERT, agrégations ticker / secteur |
| `risk_management/` | Sizing, contraintes, circuit breaker, portefeuille cible |
| `execution_engine/` | Exécution canonique : snapshot des targets, requests, ordres broker, fills observés, positions/lots, réconciliation, TCA ; watcher post-run secondaire |
| `corporate_actions/` | Sync des événements et application sur les positions |
| `modelFactory/` | Entraînement et prédiction LSTM par symbole |
| `ihm/` | IHM Streamlit de supervision et de consultation |

---

## 3. Prérequis

### Environnement

- Python **3.12+**
- MySQL disponible localement ou à distance
- Accès API Alpaca
- Token Finnhub pour l'enrichissement secteur
- Token EODHD pour les barres OHLCV et le feed news `Financial News Feed`

### Variables d'environnement

```powershell
# --- Base de données ---
$env:LOGIN_DB = "user"
$env:PASSWORD_DB = "pass"

# --- Compte Alpaca par défaut ---
$env:ALPACA_API_KEY = "PK..."
$env:ALPACA_SECRET_KEY = "..."

# --- Comptes supplémentaires (multi-comptes, optionnel) ---
$env:ALPACA_LIVE1_API_KEY = "AK..."
$env:ALPACA_LIVE1_SECRET_KEY = "..."
$env:ALPACA_LIVE1_MODE = "live"

# --- Finnhub (optionnel) ---
$env:FINNHUB_API_KEY = "..."

# --- EODHD (recommandé pour OHLCV + Event Sentiment) ---
$env:EODHD_API_TOKEN = "..."
```

Les comptes peuvent aussi être déclarés dans `config.yaml` (voir section 12).

`FINNHUB_API_KEY` peut selon le code être remplacée par `CLE_FINNHUB` pour compatibilité historique.

---

## 4. Installation

Installation recommandée en mode editable :

```powershell
python -m pip install -e ".[dev]"
```

Alternative minimale runtime :

```powershell
python -m pip install -r requirements.txt
```

---

## 5. Initialisation du projet

À exécuter une fois lors de la mise en place de l'environnement :

```powershell
python -m dataIntegrityEngine.import_alpaca_assets
python -m dataIntegrityEngine.update_sector
```

Ces commandes permettent notamment de :

- alimenter `stock_metadata` ;
- enrichir les secteurs depuis Finnhub ;
- préparer l'univers tradable exploité par le pipeline.

---

## 6. Pipeline quotidien recommandé

> ⚠️ **Choix du provider OHLCV — étape 1 conditionnelle.**
> Le provider primaire des barres (`stock_bars`, `stock_bars_daily`) est
> piloté par `config.yaml › market_data.bars_provider`.
> - `bars_provider: eodhd` (**défaut recommandé actuel**) → étape 1 =
>   `python -m dataIntegrityEngine.import_eodhd_bar`. Lancer
>   `import_alpaca_bar` dans ce mode est un **no-op** (rien ingéré).
> - `bars_provider: alpaca` → étape 1 =
>   `python -m dataIntegrityEngine.import_alpaca_bar` (mode rétrocompat IEX).
>
> Les autres étapes (quotes, metadata, exécution) restent toujours sur
> Alpaca quel que soit ce flag.
>
> ⚙️ **Profil régime par défaut** : `config.yaml` embarque désormais la
> calibration Market-Aware promue **R13a** (`market_regimes`), avec
> `macro_provider: eodhd`, `vix.high_threshold: 30.0` et `yields.risk_mult: 0.85`.

### Ordre d'exécution

```powershell
# 1. Import des barres OHLCV — choisir UNE seule commande selon bars_provider :
#    a) bars_provider = eodhd  (défaut recommandé)
python -m dataIntegrityEngine.import_eodhd_bar
#    b) bars_provider = alpaca (rétrocompat IEX)
python -m dataIntegrityEngine.import_alpaca_bar

# 2. Nettoyage et alignement des données daily
python -m dataIntegrityEngine.data_sanitizer_daily

# 3. Screening initial (liquidité, force relative, range historique)
python -m screener.stock_screener

# 4. Sync latest quotes pour le filtre de spread aval
python -m dataIntegrityEngine.sync_latest_quotes

# 5. Sync earnings calendar pour le blackout résultats aval
python -m dataIntegrityEngine.sync_earnings_calendar

# 6. Scoring avancé Minervini/VCP + neutralisation sectorielle
python -m selector.alpha_scanner

# 7. Pipeline news FinBERT + agrégats ticker/secteur
#    Ordre canonique interne : import news large -> relevance backfill ->
#    scoring standard -> scoring contextuel -> agrégation journalière
python -m event_sentiment

# 8. Fusion quant + sentiment + macro → score final
python -m event_sentiment.signal_aggregator

# 9. Entraînement LSTM (périodique — hebdomadaire recommandé)
python -m modelFactory --mode train

# 10. Prédiction LSTM → predicted_proba (quotidien)
python -m modelFactory --mode predict

# 11. Calcul du portefeuille cible (sizing, contraintes, circuit breaker)
python -m risk_management.run_risk --account-equity 100000

# 12. Exécution canonique des ordres (simulate | paper | live)
python run_execution.py simulate

# 12.bis. Watcher post-run de protections (optionnel, supervision secondaire)
python run_execution_protection_watch.py --mode once --account default

# 13. Sync corporate actions — uniquement les symboles détenus en portefeuille
#     (re-interroge Alpaca à chaque fois — pas de --skip-existing)
python -m corporate_actions sync --portfolio-only

# 14. Application des dividendes/splits sur les positions existantes
python -m corporate_actions apply
```

### Détail des étapes

| # | Commande | Rôle |
|---|---|---|
| 1 | `import_eodhd_bar` *ou* `import_alpaca_bar` | Import barres OHLCV journalières (provider piloté par `market_data.bars_provider`) |
| 2 | `data_sanitizer_daily` | Nettoyage, alignement calendrier, détection anomalies |
| 3 | `stock_screener` | Scores liquidité / force relative / range |
| 4 | `sync_latest_quotes` | Snapshot bid/ask pour le filtre de spread aval |
| 5 | `sync_earnings_calendar` | Calendrier earnings pour blackout résultats |
| 6 | `alpha_scanner` | Ranking Minervini/VCP, neutralisation sectorielle |
| 7 | `event_sentiment` | News → relevance → FinBERT standard → FinBERT contextuel → features sentiment |
| 8 | `signal_aggregator` | Fusion quant (75%) + sentiment (15%) + macro (10%) |
| 9 | `modelFactory --mode train` | Entraînement LSTM+Attention *(périodique)* |
| 10 | `modelFactory --mode predict` | Inférence → `predicted_proba` *(quotidien)* |
| 11 | `run_risk` | Portefeuille cible, sizing ATR/Kelly, conviction ML+quant |
| 12 | `run_execution.py` | Snapshot des targets, requests, ordres broker, fills observés, reconstruction positions/lots, réconciliation |
| 13 | `corporate_actions sync --portfolio-only` | Sync CA uniquement pour les positions détenues |
| 14 | `corporate_actions apply` | Crédit dividendes + ajustement qty/cost basis splits |

> **Pourquoi le sync CA vient-il après l’exécution et non au début ?**  
> `sync --portfolio-only` lit la liste des positions depuis `broker_positions_snapshots`, table qui n'est alimentée qu'après `run_execution` (étape 12). Le placer avant rendrait le périmètre de sync inexact (positions d'hier) ou vide (premier run).

### Multi-comptes

Pour cibler un compte Alpaca spécifique, ajouter `--account <ID>` :

```powershell
python -m risk_management.run_risk --account-equity 100000 --account live1
python run_execution.py paper --account live1
python -m corporate_actions sync --portfolio-only --account live1
python -m corporate_actions apply --account live1
```

Le menu interactif de `run_execution.py` propose aussi un sélecteur de compte si plusieurs sont configurés.

### Exécution canonique et watcher post-run

Après cutover, la chaîne nominale d'exécution à superviser est :

- `execution_targets_snapshot`
- `execution_order_requests`
- `execution_broker_orders`
- `execution_broker_fills`
- `execution_positions`
- `execution_position_lots`
- `execution_reconciliation_results`

La page `Exécution` de l'IHM privilégie cette lecture **scopée par run**. Le watcher de protections reste un composant **secondaire** de supervision post-run : utile si l'on souhaite promouvoir un stop initial vers un trailing stop dynamique, mais distinct du pipeline quotidien `1 → 14`.

### Mode fractionnaire : backtest + pipeline live

Le dépôt supporte désormais explicitement l'activation des **quantités fractionnaires** sur les deux surfaces opérateur principales :

- **Backtesting IHM** : switch persistant activé par défaut sur la page `🧪 Backtesting` ;
- **Pipeline IHM** : switch persistant activé par défaut sur la page `🔄 Pipeline` pour propager le mode fractionnaire aux étapes `risk_management` et `execution` ;
- **CLI backtest** : `python -m backtesting run ... --allow-fractional-shares` ;
- **CLI exécution** : `python run_execution.py paper --allow-fractional-shares` (ou `simulate` / `live`) ;
- **CLI risk** : `python -m risk_management.run_risk ... --allow-fractional-shares`.

La préférence IHM est persistée côté serveur dans :

- `artifacts/ihm_preferences/fractional_trading.json`

En backtest, le journal quotidien portefeuille / positions affiché dans l'IHM enrichit aussi la colonne **`Détail positions`** avec :

- la **quantité** détenue ;
- le **montant d'entrée cumulé** par position quand `trades.csv` expose `entry_cost` ou `entry_price`.

Exemples CLI :

```powershell
python -m backtesting run --start 2025-01-01 --end 2025-03-31 --equity 2000 --account-type cash --swing-only --allow-fractional-shares
python -m risk_management.run_risk --account-equity 100000 --allow-fractional-shares
python run_execution.py paper --allow-fractional-shares
```

---

## 7. Corporate Actions

Le module `corporate_actions/` fonctionne en **deux phases distinctes**.

### 7.1 Sync

Ingère les événements depuis Alpaca dans `corporate_actions_events`.

**Usage quotidien recommandé** — uniquement les symboles détenus en portefeuille :

```powershell
python -m corporate_actions sync --portfolio-only
python -m corporate_actions sync --portfolio-only --account live1
```

**Usage exceptionnel** — backfill complet ou ciblé :

```powershell
python -m corporate_actions sync --all-symbols --start 2026-01-01 --end 2026-04-19
python -m corporate_actions sync --symbols AAPL MSFT NVDA
python -m corporate_actions sync --all-symbols --skip-existing   # backfill sans doublons
```

Comportement utile à connaître :

- `--portfolio-only` : lit directement `broker_positions_snapshots` → seulement les positions réelles ; **toujours re-interroge Alpaca** pour ne rater aucun événement récent
- `--all-symbols` : interroge Alpaca sans filtre de symboles (backfill initial)
- `--skip-existing` : ignore les symboles déjà présents en base (pour backfill optimisé uniquement)
- l'ingestion se fait par lots avec persistance immédiate en base

### 7.2 Apply

Applique les événements pending sur les positions internes / broker snapshot.

```powershell
python -m corporate_actions apply
python -m corporate_actions apply --account live1
```

Cette étape :

- crédite les dividendes dans `portfolio_cash_ledger` ;
- ajuste quantités et cost basis pour les splits / reverse splits ;
- laisse une trace d'application idempotente en base.

> `apply` n'a d'effet que s'il existe déjà des positions à ajuster.

---

## 8. Commandes essentielles par module

### Ingestion / qualité des données

```powershell
python -m dataIntegrityEngine.import_alpaca_assets
python -m dataIntegrityEngine.import_alpaca_bar
python -m dataIntegrityEngine.data_sanitizer_daily
python -m dataIntegrityEngine.update_sector
```

### Screening / sélection

```powershell
python -m screener.stock_screener
python -m screener.stock_screener --chunk-size 500 --max-workers 8 --benchmark SPY
python -m screener.stock_screener --trade-date 2026-04-17
python -m selector.alpha_scanner
```

Notes opérateur sur `stock_screener` :

- le runtime CLI est désormais aligné sur la baseline stricte `STRICT_SWING_CASH_FILTERS` ;
- `--trade-date` borne aussi les lectures via `as_of_date` pour garder une cohérence PIT ;
- un run vide ou partiel **ne remplace pas** `stock_scores` : le snapshot précédent est conservé ;
- le `run_summary` structuré expose notamment `persistence_status`, `chunk_failure_ratio` et `chunk_error_samples` (échantillon borné d'erreurs de chunks).

### Bench outillage pipeline

```powershell
python scripts/bench_full_pipeline.py --symbols 5000 --output artifacts/benchmarks
```

Le JSON généré dans `artifacts/benchmarks/` contient désormais, pour chaque stage, un bloc :

- `seconds`
- `error`
- `details`

Voir `doc/perf_pipeline.md` pour le format exact et la méthodologie de mesure.

### Sentiment

```powershell
python -m event_sentiment
python -m event_sentiment --news-provider eodhd
python -m event_sentiment --news-provider eodhd --start-utc 2026-01-01T00:00:00Z --end-utc 2026-01-31T23:59:59Z --symbols AAPL,MSFT,NVDA
python event_sentiment/importe_news.py --start-date 2026-05-05 --end-date 2026-05-12 --news-provider eodhd
python -m event_sentiment --start-utc 2026-01-01T00:00:00Z --end-utc 2026-01-31T23:59:59Z --symbols AAPL,MSFT,NVDA
python -m event_sentiment.signal_aggregator
python -m event_sentiment.signal_aggregator --all-symbols --trade-date 2026-04-17
```

Le launcher IHM `7. Sentiment Pipeline` ne lance pas un simple `python -m event_sentiment` monolithique :

1. import news brut sur `stock_scores_all` ;
2. backfill `relevance_score` sur le scope candidats (ou override CSV) ;
3. scoring FinBERT standard sur le scope candidats ;
4. scoring FinBERT contextuel sur le scope candidats ;
5. `history_backfill` en dernier pour reconstruire `ticker_daily_sentiment_features` / `sector_daily_sentiment_features` à partir des scores déjà persistés.

Cette mise en ordre est volontaire : l'agrégation journalière reste **après** le scoring contextuel afin de bénéficier du fallback `COALESCE(news_ticker_sentiment, news_sentiment)` lors de la reconstruction des features downstream.

> `event_sentiment` utilise désormais `eodhd` comme provider news par défaut.
> Les providers `alpaca` et `finnhub` restent disponibles via `--news-provider`.
> Les checkpoints d'ingestion restent isolés par `source_name` (`eodhd_news`, `alpaca_news`, `finnhub_news`).

> Si `signal_aggregator.py` est exécuté séparément, éviter une double application éventuelle du sentiment côté scanner.

### Gestion du risque

```powershell
python -m risk_management.run_risk
python -m risk_management.run_risk --account-equity 100000 --max-positions 10 --dry-run
python -m risk_management.run_risk --trade-date 2026-04-17 --log-level DEBUG
```

### Exécution

```powershell
python run_execution.py
python run_execution.py simulate
python run_execution.py paper
python run_execution.py paper --account live1
python run_execution.py live --account live1
python run_execution.py check

# Façade de compatibilité historique pour le flux run
python -m execution_engine --broker-mode paper --dry-run
python -m execution_engine --account live1 --run-id risk-123

# Kill switch global natif
python -m execution_engine cancel-all --account paper1 --dry-run
python -m execution_engine cancel-all --account live1 --broker-mode live --confirm-account live1 --reason "incident"
```

Doctrine opérateur : `run_execution.py` est le launcher canonique du flux
`run`. `python -m execution_engine` reste disponible pour compatibilité sur ce
flux et conserve `cancel-all` comme point d'entrée natif.

### Machine Learning

```powershell
python -m modelFactory.run_train
python -m modelFactory.run_predict
python -m modelFactory --mode train
python -m modelFactory --mode predict
```

---

## 9. IHM Streamlit

L'IHM opérateur est disponible dans `ihm/`.

### Lancement rapide (recommandé)

```powershell
python run.py
```

`run.py` est le point d'entrée à la racine du projet. Il lance automatiquement Streamlit avec le bon interpréteur Python.

### Lancement manuel équivalent

```powershell
python -m streamlit run ihm/app.py
```

L'application ouvre une interface web locale sur :

- `http://localhost:8501`

### Pages disponibles

| Page | URL | Rôle |
|---|---|---|
| Accueil | `/` | Vue d'ensemble, statut DB, sélecteur de compte |
| Pipeline Quotidien | `/pipeline` | Lancement et supervision des étapes du pipeline |
| Screening | `/screening` | Résultats du screener et de l'alpha scanner, plus recommandations par objectif issues des artefacts de diagnostic |
| Portefeuille | `/portfolio` | Positions, performance, exposition sectorielle |
| Exécution | `/execution` | Vue run-scopée : targets snapshot, requests, ordres broker, fills, positions/lots, TCA, réconciliation |
| ML | `/ml` | Métriques des modèles LSTM, prédictions |
| Corporate Actions | `/corporate_actions` | Événements CA, dividendes, splits |
| Reporting | `/reporting` | Rapports agrégés |
| Paramètres | `/settings` | Configuration DB, comptes Alpaca |

Pour plus de détails sur les pages disponibles, voir `ihm/README.md`.

Le dashboard **Vue d'ensemble** remonte aussi un résumé compact des dernières recommandations screener par objectif quand les artefacts `artifacts/screener_diagnostics/` sont présents.

La page **🧪 Backtesting** de l'IHM permet désormais aussi de lancer directement `diagnose-screener` et `recommend-screener`, avec exécution en arrière-plan et logs historisés dans l'interface.

Le launcher `python -m backtesting run` et la page **🧪 Backtesting** exposent aussi un mode PIT scores `scores_pit_mode` :

- `exact` *(défaut)* : ne consomme que les snapshots `stock_scores_history.snapshot_date = trade_date` ;
- `asof_latest` : applique une sémantique PIT *as-of* et réutilise, pour chaque séance, le dernier snapshot `<= trade_date` quand le snapshot du jour n'existe pas encore.

---

## 10. Tests et qualité

### Tests globaux

```powershell
python -m pytest
```

### Exemples de tests ciblés

```powershell
python -m pytest tests/test_event_temporal_alignment.py tests/test_event_macro_rules.py tests/test_event_aggregation.py tests/test_finbert_preprocessor.py
python -m pytest tests/test_position_sizer.py tests/test_constraints.py tests/test_circuit_breaker.py tests/test_risk_checker.py tests/test_portfolio_builder.py
python -m pytest -v -k executor
```

### Lint / types

```powershell
ruff check .
mypy .
```

### Vérification environnement exécution

```powershell
python run_execution.py check
```

---

## 11. Structure racine simplifiée

```text
alpha_trade/
├── run.py                      ← point d'entrée IHM (python run.py)
├── run_execution.py            ← launcher canonique du flux run d'exécution
├── run_execution_protection_watch.py
├── config.yaml
├── config/
│   └── capital_presets.yaml    ← presets risk/selector/execution par tranche d'equity
├── pyproject.toml
├── requirements.txt
├── README.md
├── alembic/                    ← migrations DB
├── doc/
│   ├── DOC_FONCTIONNELLE.md
│   ├── DOC_TECHNIQUE.md
│   └── …                       ← docs par module
├── common/                     ← utilitaires transverses (config, logging, calendar)
├── core/                       ← types, interfaces, conviction, run_summary
├── database/                   ← repositories SQL + schémas
├── service/                    ← clients providers externes (eodhd, alpaca, finnhub)
├── dataIntegrityEngine/
├── corporate_actions/
├── screener/
├── selector/
├── event_sentiment/
├── modelFactory/
├── risk_management/
├── execution_engine/
├── backtesting/
├── ihm/
└── tests/
```

> **Rétention `artifacts/`** : voir
> [`doc/artifacts_retention_policy.md`](doc/artifacts_retention_policy.md)
> et le script `scripts/prune_artifacts.py` (Sprint S4 / A-023).

---

## 12. Configuration multi-comptes

Alpha Trade supporte **plusieurs comptes Alpaca** en parallèle (paper et/ou live).

### Sécurité — secrets (Sprint S5 / A-013)

> **Aucune clé API en clair n'est tolérée dans `config.yaml`**. Le scanner
> [`core.secrets.scan_yaml_for_literal_secrets`](core/secrets.py) bloque
> `PK…`, `AK…`, `sk-…` et secrets base64 ≥ 36 chars. Test garde-fou :
> `tests/test_config_no_literal_secrets.py`.

Les credentials par compte vivent **uniquement** sous `alpaca.accounts[*]`
avec des placeholders `${VAR}` résolus depuis l'environnement par
`service.alpaca.accounts.AccountRegistry`. Les credentials DB
(`LOGIN_DB`/`PASSWORD_DB`) sont également lus exclusivement depuis l'env.

Avant toute bascule live, exécuter la **recette pré-live** :

```powershell
python -m execution_engine.preflight --account <id> --broker-mode live
# ou (avec archivage du rapport):
python scripts/run_pre_live_checklist.py --account <id>
```

Détail : [`doc/pre_live_checklist.md`](doc/pre_live_checklist.md).

### Déclaration dans `config.yaml`

```yaml
alpaca:
  accounts:
    - id: default
      label: "Compte paper principal"
      api_key: "${ALPACA_API_KEY}"        # résolu depuis l'env
      secret_key: "${ALPACA_SECRET_KEY}"
      mode: paper
    - id: live1
      label: "Compte live production"
      api_key: "${ALPACA_LIVE1_API_KEY}"
      secret_key: "${ALPACA_LIVE1_SECRET_KEY}"
      mode: live
```

### Levier optionnel (`config.yaml`)

Le moteur d'exécution supporte désormais une **politique explicite de levier
long-only**, pilotée par `config.yaml`. Quand ce bloc est activé, le budget
effectif est borné par le snapshot broker (`get_account`) et par les garde-fous
suivants :

- **compte `margin` requis** ;
- **equity minimale 2 000 $** ;
- **max 2.0x** en swing overnight ;
- priorité au champ broker **`regt_buying_power`**, sinon fallback
  `buying_power` ;
- désactivation automatique hors `entry_mode="normal"`.

> Important : avec `account_type: margin`, le comportement historique du dépôt
> (usage du `buying_power` broker) reste préservé si la feature `leverage`
> n'est pas activée. Le bloc `leverage` sert donc à **encadrer** ce budget par
> une politique plus stricte, pas à réécrire silencieusement la sémantique
> legacy des comptes margin.

Exemple de bloc :

```yaml
leverage:
  enabled: false
  mode: disabled                  # disabled | regt_swing
  max_leverage: 1.5
  min_equity_usd: 2000
  require_margin_account: true
  only_in_entry_mode: normal
  disable_in_capital_preservation: true
  disable_if_buying_power_field_missing: false
  buying_power_field_priority:
    - regt_buying_power
    - buying_power
  dry_run_simulated_leverage: 1.5
  audit_log: true
```

En exécution, `run_execution.py` affiche désormais explicitement :

- la **configuration de levier** chargée ;
- le **levier effectif** du run (ex. `1.50x`) ;
- le **budget disponible**, l'`equity` et le champ broker retenu.

### Déclaration par variables d'environnement

Alternative sans `config.yaml` — le système détecte automatiquement les paires :

```powershell
$env:ALPACA_LIVE1_API_KEY = "AK..."
$env:ALPACA_LIVE1_SECRET_KEY = "..."
$env:ALPACA_LIVE1_MODE = "live"
$env:ALPACA_LIVE1_LABEL = "Compte live"
```

### Ordre de résolution

1. `config.yaml` → `alpaca.accounts`
2. Variables d'env préfixées `ALPACA_<ID>_*`
3. Fallback classique `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` → compte `default`

### IHM Streamlit

Quand plusieurs comptes sont configurés, un **sélecteur de compte** apparaît dans la sidebar de l'IHM. Les données affichées (runs d'exécution, positions broker) sont automatiquement filtrées par le compte sélectionné.

### Tables DB impactées

Les tables suivantes portent désormais `account_id VARCHAR(32)` sur les périmètres métier critiques :

- `execution_runs`
- `execution_targets_snapshot`
- `execution_order_requests`
- `execution_broker_orders`
- `execution_broker_fills`
- `execution_positions`
- `execution_position_lots`
- `execution_reconciliation_results`
- `execution_locks`
- `broker_positions_snapshots`
- `risk_decisions`
- `portfolio_targets`
- `corporate_actions_applications`
- `portfolio_cash_ledger`

Migration : `database/sql/migration_add_account_id.sql` ou Alembic `alembic upgrade head`.

---

## 13. Notes utiles

- Le projet repose sur une base MySQL correctement initialisée avec les schémas SQL du dépôt.
- `run.py` est le point d'entrée pour lancer l'IHM (`python run.py`).
- `run_execution.py` est le launcher canonique du flux `run` pour l'exécution opérateur.
- `python -m execution_engine` reste une façade de compatibilité pour `run` et le point d'entrée natif de `cancel-all`.
- L'IHM permet la **supervision et le lancement des pipelines** depuis l'interface web.
- Les commandes `paper` et surtout `live` nécessitent une validation attentive des variables d'environnement et de la configuration broker.

---

## 14. Documentation complémentaire

- 📚 **[`doc/INDEX.md`](doc/INDEX.md)** — index cherchable de toute la
  documentation (généré par `scripts/generate_doc_index.py`, Sprint S25.5).
- `doc/DOC_FONCTIONNELLE.md` : vision métier et flux fonctionnels
- `doc/DOC_TECHNIQUE.md` : architecture, composants, dette technique, recommandations
- `ihm/README.md` : documentation dédiée à l'interface opérateur
- `prompt/execution/` : historique d'audit, de sprints et de cutover du module `execution` (archive projet, pas guide opérateur)
