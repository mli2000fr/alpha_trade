# Alpha Trade

Plateforme Python de **trading algorithmique swing US** orientée production, construite autour d'un pipeline modulaire : ingestion marché, nettoyage, screening, sélection alpha, sentiment news, gestion du risque, exécution et suivi post-trade.

Le projet s'appuie principalement sur **Python 3.12**, **MySQL**, **SQLAlchemy**, **Alpaca**, **Finnhub**, **PyTorch/Lightning** et une **IHM Streamlit** pour la supervision opérateur.

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
| `execution_engine/` | Exécution des ordres, fills, réconciliation, TCA |
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

### Ordre d'exécution

```powershell
# 1. Import des barres OHLCV depuis Alpaca
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
python -m event_sentiment

# 8. Fusion quant + sentiment + macro → score final
python -m event_sentiment.signal_aggregator

# 9. Entraînement LSTM (périodique — hebdomadaire recommandé)
python -m modelFactory --mode train

# 10. Prédiction LSTM → predicted_proba (quotidien)
python -m modelFactory --mode predict

# 11. Calcul du portefeuille cible (sizing, contraintes, circuit breaker)
python -m risk_management.run_risk --account-equity 100000

# 12. Exécution des ordres (simulate | paper | live)
python run_execution.py simulate

# 13. Sync corporate actions — uniquement les symboles détenus en portefeuille
#     (re-interroge Alpaca à chaque fois — pas de --skip-existing)
python -m corporate_actions sync --portfolio-only

# 14. Application des dividendes/splits sur les positions existantes
python -m corporate_actions apply
```

### Détail des étapes

| # | Commande | Rôle |
|---|---|---|
| 1 | `import_alpaca_bar` | Import barres OHLCV journalières Alpaca |
| 2 | `data_sanitizer_daily` | Nettoyage, alignement calendrier, détection anomalies |
| 3 | `stock_screener` | Scores liquidité / force relative / range |
| 4 | `sync_latest_quotes` | Snapshot bid/ask pour le filtre de spread aval |
| 5 | `sync_earnings_calendar` | Calendrier earnings pour blackout résultats |
| 6 | `alpha_scanner` | Ranking Minervini/VCP, neutralisation sectorielle |
| 7 | `event_sentiment` | News → FinBERT → features sentiment |
| 8 | `signal_aggregator` | Fusion quant (75%) + sentiment (15%) + macro (10%) |
| 9 | `modelFactory --mode train` | Entraînement LSTM+Attention *(périodique)* |
| 10 | `modelFactory --mode predict` | Inférence → `predicted_proba` *(quotidien)* |
| 11 | `run_risk` | Portefeuille cible, sizing ATR/Kelly, conviction ML+quant |
| 12 | `run_execution.py` | Soumission ordres + snapshot positions broker |
| 13 | `corporate_actions sync --portfolio-only` | Sync CA uniquement pour les positions détenues |
| 14 | `corporate_actions apply` | Crédit dividendes + ajustement qty/cost basis splits |

> **Pourquoi sync en étape 11 et non au début ?**  
> `sync --portfolio-only` lit la liste des positions depuis `broker_positions_snapshots`, table qui n'est alimentée qu'après `run_execution` (étape 10). Le placer avant rendrait le périmètre de sync inexact (positions d'hier) ou vide (premier run).

### Multi-comptes

Pour cibler un compte Alpaca spécifique, ajouter `--account <ID>` :

```powershell
python -m risk_management.run_risk --account-equity 100000 --account live1
python run_execution.py paper --account live1
python -m corporate_actions sync --portfolio-only --account live1
python -m corporate_actions apply --account live1
```

Le menu interactif de `run_execution.py` propose aussi un sélecteur de compte si plusieurs sont configurés.

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
python -m selector.alpha_scanner
```

### Sentiment

```powershell
python -m event_sentiment
python -m event_sentiment --start-utc 2026-01-01T00:00:00Z --end-utc 2026-01-31T23:59:59Z --symbols AAPL,MSFT,NVDA
python -m event_sentiment.signal_aggregator
python -m event_sentiment.signal_aggregator --all-symbols --trade-date 2026-04-17
```

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
python -m execution_engine
python -m execution_engine --account live1
```

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
| Exécution | `/execution` | Ordres, fills, TCA, réconciliation |
| ML | `/ml` | Métriques des modèles LSTM, prédictions |
| Corporate Actions | `/corporate_actions` | Événements CA, dividendes, splits |
| Reporting | `/reporting` | Rapports agrégés |
| Paramètres | `/settings` | Configuration DB, comptes Alpaca |

Pour plus de détails sur les pages disponibles, voir `ihm/README.md`.

Le dashboard **Vue d'ensemble** remonte aussi un résumé compact des dernières recommandations screener par objectif quand les artefacts `artifacts/screener_diagnostics/` sont présents.

La page **🧪 Backtesting** de l'IHM permet désormais aussi de lancer directement `diagnose-screener` et `recommend-screener`, avec exécution en arrière-plan et logs historisés dans l'interface.

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
├── run.py                  ← point d'entrée IHM (python run.py)
├── run_execution.py        ← point d'entrée exécution ordres
├── config.yaml
├── pyproject.toml
├── README.md
├── DOC_FONCTIONNELLE.md
├── DOC_TECHNIQUE.md
├── dataIntegrityEngine/
├── screener/
├── selector/
├── event_sentiment/
├── risk_management/
├── execution_engine/
├── corporate_actions/
├── modelFactory/
├── ihm/
└── tests/
```

---

## 12. Configuration multi-comptes

Alpha Trade supporte **plusieurs comptes Alpaca** en parallèle (paper et/ou live).

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

Les tables suivantes possèdent une colonne `account_id VARCHAR(32)` :

- `execution_runs`
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
- `run_execution.py` est le point d'entrée le plus pratique pour l'exécution opérateur.
- L'IHM permet la **supervision et le lancement des pipelines** depuis l'interface web.
- Les commandes `paper` et surtout `live` nécessitent une validation attentive des variables d'environnement et de la configuration broker.

---

## 14. Documentation complémentaire

- `DOC_FONCTIONNELLE.md` : vision métier et flux fonctionnels
- `DOC_TECHNIQUE.md` : architecture, composants, dette technique, recommandations
- `ihm/README.md` : documentation dédiée à l'interface opérateur
