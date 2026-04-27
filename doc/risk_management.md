# Risk Management — Guide d'usage

## Objectif

Ce document résume le fonctionnement du module `risk_management/` et les commandes utiles pour :

- construire un portefeuille cible à partir des candidats scorés,
- appliquer sizing, contraintes et filtre de corrélation,
- intégrer la composante ML dans le score de conviction,
- écrire les décisions et les cibles en base pour l'exécution.

---

## 1. Ce que contient le module

### Fichiers clés

| Fichier | Rôle |
|---|---|
| `risk_management/__init__.py` | Package Python |
| `risk_management/__main__.py` | Point d'entrée package |
| `risk_management/run_risk.py` | Lanceur recommandé |
| `risk_management/cli.py` | CLI standalone |
| `risk_management/portfolio_builder.py` | Orchestrateur principal de construction du portefeuille |
| `risk_management/position_sizer.py` | Sizing ATR |
| `risk_management/kelly.py` | Sizing Kelly optionnel |
| `risk_management/constraints.py` | Contraintes portefeuille |
| `risk_management/risk_checker.py` | Vérifications de risque |
| `risk_management/circuit_breaker.py` | Suspension sur drawdown / perte quotidienne |
| `risk_management/conviction.py` | Fusion score quant + prédiction ML |
| `risk_management/correlation_filter.py` | Filtre de corrélation |
| `risk_management/db_io.py` | Chargement candidats, prix, prédictions, historique |
| `risk_management/audit.py` | Persistance décisions et cibles |
| `risk_management/config.py` | Paramètres immuables |

---

## 2. Prérequis

### 2.1 Tables et données requises

#### Obligatoires

- `stock_scores`
- `stock_bars_daily`
- `risk_decisions`
- `portfolio_targets`

#### Optionnelles mais très utiles

- `model_predictions`
- historique de rendements suffisant dans `stock_bars_daily`
- `portfolio_cash_ledger` si l'on veut que les dividendes cumulés soient réintégrés dans l'equity effective

### 2.2 Variables d'environnement minimales

```powershell
$env:LOGIN_DB = "user"
$env:PASSWORD_DB = "pass"
```

### 2.3 Entrées consommées par le module

Le module charge principalement :

- les candidats depuis `stock_scores`,
- les prix / ATR depuis `stock_bars_daily`,
- les prédictions depuis `model_predictions`,
- les win rates et rendements historiques via le repository de risque.

---

## 3. Commandes utiles

### Lancement standard

```powershell
python -m risk_management.run_risk
```

### Lancement avec equity explicite

```powershell
python -m risk_management.run_risk --account-equity 100000 --max-positions 10
```

### Dry-run

```powershell
python -m risk_management.run_risk --account-equity 100000 --dry-run
```

### Date explicite

```powershell
python -m risk_management.run_risk --trade-date 2026-04-21
```

### Activation Kelly + paramètres de corrélation

```powershell
python -m risk_management.run_risk --enable-kelly-sizing --correlation-threshold 0.80 --correlation-lookback-days 60 --correlation-min-overlap 40
```

### Multi-comptes

```powershell
python -m risk_management.run_risk --account-equity 100000 --account live1
```

---

## 4. Ce que fait le module

### 4.1 Chargement des données

Le CLI :

1. construit un `RiskConfig` ;
2. charge les candidats ;
3. charge les prix et ATR ;
4. charge les prédictions ML ;
5. charge les win rates ;
6. charge la matrice de rendements.

### 4.2 Construction des entrées

`PortfolioBuilder.build()` :

1. enrichit les candidats avec `predicted_proba` et `historical_win_rate` ;
2. calcule `conviction_score` ;
3. trie les candidats par conviction décroissante ;
4. applique le filtre de corrélation ;
5. applique le sizing ATR ou Kelly ;
6. vérifie les contraintes ;
7. produit des `PortfolioEntry` avec statut `ACCEPTED`, `REDUCED` ou `REJECTED`.

### 4.3 Conviction score

Le score de conviction combine :

- une composante quant (`score_weight`) ;
- une composante ML (`prediction_weight`).

Par défaut, le builder marque `score_source = final_score_sentiment`, ce qui fait du module risk un consommateur direct de la fusion quant + sentiment si elle a déjà été calculée.

> **Phase 5.1.b — Centralisation `core/conviction.py`** :
> la formule est désormais hébergée nativement par `core.conviction.fuse(...)`
> (objet typé `ConvictionWeights`). `risk_management.portfolio_builder.PortfolioBuilder`
> et `event_sentiment.signal_aggregator` consomment la même API.
> Le module `risk_management.conviction` reste exposé en wrapper rétrocompat,
> mais émet désormais un `DeprecationWarning` ; à ne plus utiliser dans le code neuf.

### 4.3.bis Pondérations conviction (40 / 60)

Convention historique du projet : `score_weight = 0.40`, `prediction_weight = 0.60`
(voir `RiskConfig` et `core.conviction.ConvictionWeights`).

Hypothèses :

- la prédiction ML (probabilité calibrée) est *plus* informative que le score
  quant pur sur l'horizon swing typique 5–15 jours ;
- les poids somment exactement à 1.0 (validation `__post_init__`).

**Plan de calibration empirique (backlog Phase 7)** : reposer sur un backtest
glissant 6 mois (table `weights_calibration_runs`) pour optimiser le couple
`(score_weight, prediction_weight)` par horizon / régime de volatilité. En
attendant, le `run_summary` expose `conviction_weights_calibration =
{"source": "default", "calibration_run_id": null}` afin de tracer qu'aucune
calibration personnalisée n'est encore active.

### 4.4 Dividendes cumulés

Le CLI tente d'ajouter au capital de base le total des dividendes cumulés issus de `corporate_actions`, quand cette information est disponible.

### 4.5 Persistance

Si `--dry-run` n'est pas activé, le module écrit :

- les décisions dans `risk_decisions` ;
- les cibles dans `portfolio_targets`.

### 4.6 `run_summary` risk (Phase 5.1.a → 5.1.c)

Chaque exécution émet une ligne `::alpha_trade_run_summary::{...}` (parsée par
l'IHM). Champs Phase 5 :

| Clé | Description |
|---|---|
| `schema_version` | Version du payload (1, ajoutée Phase 5.1.a). |
| `account_equity_breakdown` | Décomposition de l'equity (cash, settled_cash, long_positions_value, short_positions_value, dividends_ledger, total, source). Source ∈ {`broker_account_snapshots`, `missing`}. |
| `conviction_weights` | `{score_weight, prediction_weight, source: "core.conviction"}`. Trace l'utilisation de l'API centralisée. |
| `conviction_weights_calibration` | `{source: "default", calibration_run_id: null}`. Placeholder pour la calibration empirique Phase 7. |

L'`account_equity_breakdown` est best-effort : aucune exception ne remonte au
CLI. Si les tables `broker_account_snapshots` / `broker_positions_snapshots` /
`portfolio_cash_ledger` sont absentes, le payload conserve `source="missing"`.

---

## 5. Pourquoi peu de positions peuvent être retenues

### 5.1 Peu de candidats au départ

Causes probables :

1. `stock_scores` peu alimentée ;
2. pipeline amont non exécuté ;
3. `is_candidate = 1` trop restrictif.

### 5.2 Beaucoup de rejets

Causes probables :

1. filtre de corrélation trop strict ;
2. contraintes portefeuille trop strictes ;
3. prix ou ATR indisponibles ;
4. sizing insuffisant ;
5. circuit breaker actif.

### 5.3 Composante ML absente

Le module peut continuer même si certaines prédictions ML sont absentes, mais la conviction sera moins riche qu'en production complète.

---

## 6. Vérifications utiles

### Vérifier les dernières décisions de risque

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text("SELECT run_id, trade_date, symbol, decision, approved_shares, account_id FROM risk_decisions ORDER BY created_at DESC LIMIT 20")).mappings().all();
    print([dict(r) for r in rows])'
```

### Vérifier les dernières cibles de portefeuille

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text("SELECT run_id, trade_date, symbol, shares, weight, account_id FROM portfolio_targets ORDER BY created_at DESC LIMIT 20")).mappings().all();
    print([dict(r) for r in rows])'
```

---

## 7. Tests

### Tests ciblés logique risque

```powershell
python -m pytest tests/test_risk_management_portfolio_builder.py tests/test_risk_management_position_sizer.py tests/test_risk_management_constraints.py tests/test_risk_management_circuit_breaker.py tests/test_risk_management_risk_checker.py tests/test_risk_management_conviction.py tests/test_risk_management_correlation_filter.py -q -o addopts=""
```

### Tests CLI et repository

```powershell
python -m pytest tests/test_risk_management_cli.py tests/test_risk_management_db_io.py tests/test_risk_management_run_risk.py tests/test_risk_management_main.py -q -o addopts=""
```

---

## 8. Recommandation pratique

Ordre conseillé :

1. produire `stock_scores` et `final_score_sentiment` ;
2. produire les prédictions ML si disponibles ;
3. lancer `run_risk` ;
4. vérifier `portfolio_targets` avant de passer à l'exécution.

### Séquence recommandée

```powershell
python -m event_sentiment.signal_aggregator --trade-date 2026-04-21
python -m modelFactory --mode predict --accelerator auto
python -m risk_management.run_risk --account-equity 100000 --account live1
```
