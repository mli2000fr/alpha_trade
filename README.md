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

Ordre d'exécution actuel du pipeline :

```powershell
python -m dataIntegrityEngine.import_alpaca_bar
python -m corporate_actions sync --skip-existing
python -m dataIntegrityEngine.data_sanitizer_daily
python -m screener.stock_screener
python -m selector.alpha_scanner
python -m event_sentiment
python -m event_sentiment.signal_aggregator
python -m modelFactory --mode train            # périodique (hebdomadaire recommandé)
python -m modelFactory --mode predict           # quotidien
python -m risk_management.run_risk --account-equity 100000
python run_execution.py simulate
python -m corporate_actions apply
```

### Détail des étapes

1. **`import_alpaca_bar`** : importe les barres de marché Alpaca.
2. **`corporate_actions sync`** : ingère les dividendes / splits dans le référentiel d'événements.
3. **`data_sanitizer_daily`** : nettoie, aligne et fiabilise les données daily.
4. **`stock_screener`** : produit les premiers scores quantitatifs.
5. **`alpha_scanner`** : applique le ranking multi-facteurs et sélectionne les meilleurs candidats.
6. **`event_sentiment`** : traite les news, score le sentiment et calcule les agrégats.
7. **`signal_aggregator`** : fusionne quant + sentiment + macro en score final.
7a. **`modelFactory --mode train`** : entraîne les modèles LSTM+Attention par symbole candidat (périodique).
7b. **`modelFactory --mode predict`** : produit `predicted_proba` par symbole candidat (quotidien). Alimente le score de conviction du risk.
8. **`run_risk`** : calcule les tailles, contraintes et portefeuille cible. Utilise les prédictions ML (60%) + score quant (40%) pour le score de conviction.
9. **`run_execution.py`** : exécute en mode `simulate`, `paper` ou `live`.
10. **`corporate_actions apply`** : applique les corporate actions pending sur les positions existantes.

### Multi-comptes

Pour cibler un compte Alpaca spécifique, ajouter `--account <ID>` aux commandes :

```powershell
python -m risk_management.run_risk --account-equity 100000 --account live1
python run_execution.py paper --account live1
python -m corporate_actions sync --account live1
python -m corporate_actions apply --account live1
```

Le menu interactif de `run_execution.py` propose aussi un sélecteur de compte si plusieurs sont configurés.

---

## 7. Corporate Actions

Le module `corporate_actions/` fonctionne en **deux phases distinctes**.

### 7.1 Sync

Ingère les événements depuis Alpaca dans `corporate_actions_events`.

```powershell
python -m corporate_actions sync
python -m corporate_actions sync --skip-existing
python -m corporate_actions sync --batch-size 10
python -m corporate_actions sync --all-symbols --start 2026-01-01 --end 2026-04-19
```

Comportement utile à connaître :

- l'univers est résolu en priorité depuis `stock_metadata` ;
- fallback possible via les positions broker si nécessaire ;
- `--skip-existing` évite de recharger des symboles déjà présents ;
- l'ingestion se fait par lots avec persistance immédiate en base.

### 7.2 Apply

Applique les événements pending sur les positions internes / broker snapshot.

```powershell
python -m corporate_actions apply
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

Lancement :

```powershell
python -m streamlit run ihm/app.py
```

L'application ouvre en général une interface web locale sur :

- `http://localhost:8501`

Pour plus de détails sur les pages disponibles, voir `ihm/README.md`.

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
├── run_execution.py
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

- `DOC_FONCTIONNELLE.md` : vision métier et flux fonctionnels
- `DOC_TECHNIQUE.md` : architecture, composants, dette technique, recommandations
- `ihm/README.md` : documentation dédiée à l'interface opérateur

---

## 13. Notes utiles

- Le projet repose sur une base MySQL correctement initialisée avec les schémas SQL du dépôt.
- `run_execution.py` est le point d'entrée le plus pratique pour l'exécution opérateur.
- L'IHM est en **lecture / supervision**, pas en soumission d'ordres.
- Les commandes `paper` et surtout `live` nécessitent une validation attentive des variables d'environnement et de la configuration broker.

---

## 14. Documentation complémentaire

- `DOC_FONCTIONNELLE.md` : vision métier et flux fonctionnels
- `DOC_TECHNIQUE.md` : architecture, composants, dette technique, recommandations
- `ihm/README.md` : documentation dédiée à l'interface opérateur
