# Model Factory — Guide d'usage

## Objectif

Ce document résume le fonctionnement du module `modelFactory/` et les commandes utiles pour :

- entraîner des modèles LSTM + attention par symbole,
- produire des prédictions de probabilité directionnelle,
- persister les artefacts modèles et les métriques,
- alimenter `model_predictions` pour le module `risk_management` et le backtesting.

---

## 1. Ce que contient le module

### Fichiers clés

| Fichier | Rôle |
|---|---|
| `modelFactory/__init__.py` | Package Python |
| `modelFactory/__main__.py` | Point d'entrée `python -m modelFactory` |
| `modelFactory/cli.py` | CLI train / predict |
| `modelFactory/orchestrator.py` | Orchestration multi-symboles |
| `modelFactory/trainer.py` | Entraînement mono-symbole |
| `modelFactory/predictor.py` | Inférence mono-symbole et batch |
| `modelFactory/data_loader.py` | Chargement depuis `stock_bars_daily` et sentiment |
| `modelFactory/features.py` | Feature engineering |
| `modelFactory/dataset.py` | DataModule et scaling |
| `modelFactory/model.py` | `LSTMAttentionModule` |
| `modelFactory/db_registry.py` | Registre DB, métriques, prédictions |
| `modelFactory/run_train.py` | Lanceur `train` |
| `modelFactory/run_predict.py` | Lanceur `predict` |
| `artifacts/models/` | Répertoire cible des artefacts |

---

## 2. Prérequis

### 2.1 Données minimales pour l'entraînement

#### Obligatoires

- `stock_bars_daily`
- `stock_scores` avec `is_candidate = 1` si aucun symbole n'est fourni explicitement
- `model_registry`
- `model_training_run`
- `model_metrics`

#### Optionnelles

- `ticker_daily_sentiment_features` si `--include-sentiment` est activé

### 2.2 Données minimales pour la prédiction

#### Obligatoires

- `stock_bars_daily`
- artefacts présents sous `artifacts/models/<SYMBOL>/`
- `model_predictions`

#### Optionnelles

- `ticker_daily_sentiment_features` si le modèle entraîné utilisait des features sentiment

### 2.3 Variables d'environnement minimales

```powershell
$env:LOGIN_DB = "user"
$env:PASSWORD_DB = "pass"
```

### 2.4 Artefacts produits

Par symbole, le module crée typiquement :

- `best.ckpt`
- `scaler.pkl`
- `config.json`
- `metrics.json`

---

## 3. Commandes utiles

### Entraînement via le point d'entrée principal

```powershell
python -m modelFactory --mode train
```

### Entraînement avec sentiment et accélérateur auto

```powershell
python -m modelFactory --mode train --include-sentiment --accelerator auto --max-workers 1
```

### Entraînement ciblé

```powershell
python -m modelFactory --mode train --symbols AAPL MSFT NVDA --max-epochs 20 --batch-size 32 --sequence-length 60 --forecast-horizon 5
```

### Prédiction batch

```powershell
python -m modelFactory --mode predict
```

### Prédiction ciblée

```powershell
python -m modelFactory --mode predict --symbols AAPL MSFT NVDA --accelerator cpu
```

### Lanceurs dédiés

```powershell
python -m modelFactory.run_train --include-sentiment --accelerator gpu --max-workers 1
python -m modelFactory.run_predict --accelerator auto
```

---

## 4. Ce que fait le module

### 4.1 Résolution de l'univers

Si aucun symbole n'est fourni, `db_registry.load_candidate_symbols()` charge les symboles `is_candidate = 1` depuis `stock_scores`.

### 4.2 Entraînement

Pour chaque symbole, `train_symbol()` :

1. vérifie qu'il y a assez d'historique ;
2. construit le `SymbolDataModule` ;
3. instancie `LSTMAttentionModule` ;
4. entraîne avec Lightning ;
5. sauvegarde checkpoint, scaler, config et métriques ;
6. met à jour `model_training_run` et `model_metrics`.

### 4.3 Parallélisme et GPU

`run_training_batch()` :

- utilise plusieurs processus sur CPU ;
- force `effective_workers = 1` si le GPU est demandé ou disponible en mode `auto`.

Cela évite plusieurs workers concurrents sur une même carte CUDA.

### 4.4 Prédiction

`predict_symbol()` :

1. résout les artefacts depuis le registre DB ou le dossier symbole ;
2. recharge la config et le scaler ;
3. recharge les données jusqu'à `prediction_date` ou `as_of_date` ;
4. calcule les features ;
5. produit `predicted_proba` et `predicted_class` ;
6. écrit dans `model_predictions` si `persist=True`.

### 4.5 Sécurité PIT

Le prédicteur borne le chargement des données à `end_date <= cutoff_date`, ce qui permet une utilisation compatible avec le backtesting et la reconstruction historique sans look-ahead évident au niveau chargement.

---

## 5. Pourquoi un symbole peut être ignoré

### 5.1 Historique insuffisant

Causes probables :

1. moins de `min_history_days` lignes en `stock_bars_daily` ;
2. trop peu de séquences après split train / val / test ;
3. sentiment demandé mais données sentiment trop pauvres.

### 5.2 Prédiction impossible

Causes probables :

1. artefacts absents ;
2. `best.ckpt`, `scaler.pkl` ou `config.json` manquants ;
3. historique de bars insuffisant ;
4. modèle entraîné avec sentiment mais features sentiment indisponibles.

### 5.3 GPU non utilisé

Causes probables :

1. `--accelerator cpu` forcé ;
2. `--accelerator gpu` demandé mais CUDA indisponible ;
3. fallback automatique vers CPU en inférence.

---

## 6. Vérifications utiles

### Vérifier les derniers runs d'entraînement

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text("SELECT run_id, symbol, status, started_at, finished_at FROM model_training_run ORDER BY started_at DESC LIMIT 10")).mappings().all();
    print([dict(r) for r in rows])'
```

### Vérifier les dernières prédictions

```powershell
python -c 'from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text("SELECT symbol, prediction_date, predicted_proba, predicted_class, run_id FROM model_predictions ORDER BY prediction_date DESC LIMIT 10")).mappings().all();
    print([dict(r) for r in rows])'
```

### Vérifier les artefacts d'un symbole

```powershell
Get-ChildItem "C:\Users\PC MLI\PycharmProjects\alpha_trade\artifacts\models\AAPL"
```

---

## 7. Tests

### Tests ciblés configuration / dataset / entraînement

```powershell
python -m pytest tests/test_model_factory_config.py tests/test_model_factory_dataset.py tests/test_model_factory_trainer.py tests/test_model_factory_orchestrator.py tests/test_model_factory_model.py -q -o addopts=""
```

### Tests ciblés prédiction / registry / CLI

```powershell
python -m pytest tests/test_model_factory_predictor.py tests/test_model_factory_db_registry.py tests/test_model_factory_cli.py tests/test_model_factory_run_train.py tests/test_model_factory_run_predict.py tests/test_model_factory_main.py -q -o addopts=""
```

---

## 8. Recommandation pratique

Ordre conseillé :

1. valider `stock_bars_daily` ;
2. entraîner périodiquement avec `train` ;
3. produire les prédictions quotidiennes avec `predict` ;
4. laisser `risk_management` consommer `model_predictions`.

### Séquence recommandée

```powershell
python -m modelFactory --mode train --include-sentiment --accelerator auto --max-workers 1
python -m modelFactory --mode predict --accelerator auto
```
