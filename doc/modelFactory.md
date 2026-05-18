# Model Factory — Référence complète

## Objectif

`modelFactory/` est le module ML opérationnel du projet. Il ne se limite plus à un simple entraînement LSTM par symbole.

Aujourd'hui, il assure :

- l'entraînement **par symbole** d'un modèle séquentiel `LSTM + Attention` ;
- l'entraînement de **challengers tabulaires locaux** `LightGBM` et `CatBoost` ;
- l'entraînement optionnel d'un **modèle global multi-symboles** ;
- la **calibration** des probabilités ;
- l'**optimisation du seuil de décision** ;
- l'**optimisation optionnelle de la target** (horizon / seuils swing) ;
- la **gouvernance multi-modèles** avec sélection automatique du champion servi ;
- l'**inférence batch ou ciblée** en rechargeant automatiquement le backend servi (`lstm_attention`, `lightgbm`, `catboost`, `global_model`) ;
- l'alimentation de la base via `model_training_run`, `model_metrics`, `model_governance` et `model_predictions`.

Ce document doit être lu comme la **source de vérité métier et technique** du module. Si une personne reprend le projet, elle doit pouvoir comprendre ici :

1. ce que fait réellement `modelFactory` ;
2. quels artefacts il produit ;
3. comment le pipeline et l'IHM l'utilisent ;
4. quelles données de gouvernance et de serving il persiste réellement en base ;
5. comment le diagnostiquer et le faire évoluer.

---

## 1. Vue d'ensemble fonctionnelle

### 1.1 Rôle dans le pipeline global

Dans le pipeline quotidien, `modelFactory` intervient après :

- les données de marché nettoyées (`stock_bars_daily`) ;
- le screening / scoring (`stock_scores`) ;
- le pipeline sentiment (`ticker_daily_sentiment_features`) si activé ;
- le `signal_aggregator` qui prépare l'univers final candidat.

Il intervient en deux temps :

1. **`train`** : entraînement périodique des modèles et publication des artefacts ;
2. **`predict`** : inférence quotidienne sur les candidats pour alimenter `risk_management`.

### 1.2 Familles de modèles supportées

#### Modèle principal local

- `lstm_attention`

#### Challengers locaux par symbole

- `lightgbm`
- `catboost`

#### Modèle global optionnel

- `global_model` avec backend tabulaire `lightgbm` ou `catboost`

### 1.3 Ce qui est réellement servi en prédiction

Le backend servi n'est **pas forcément** le LSTM.

Le backend réellement utilisé par `predict_symbol()` dépend des artefacts présents dans `artifacts/models/<SYMBOL>/config.json` :

- `artifact_routes.selected_model`
- `artifact_routes.models.*`

Le prédicteur sait aujourd'hui router vers :

- `lstm_attention`
- `lightgbm_tabular`
- `catboost_tabular`
- `global_tabular`

---

## 2. Structure du module

### 2.1 Fichiers clés

| Fichier | Rôle |
|---|---|
| `modelFactory/__main__.py` | point d'entrée `python -m modelFactory` |
| `modelFactory/cli.py` | CLI unifiée `train` / `predict` |
| `modelFactory/orchestrator.py` | orchestration multi-symboles, parallélisme, injection du modèle global |
| `modelFactory/trainer.py` | entraînement mono-symbole, persistance artefacts, sélection du champion |
| `modelFactory/predictor.py` | inférence mono-symbole et batch, routage du backend servi |
| `modelFactory/model.py` | implémentation Lightning du `LSTMAttentionModule` |
| `modelFactory/dataset.py` | `SymbolDataModule`, scaling, datasets séquentiels |
| `modelFactory/data_loader.py` | chargement DB des bars, benchmark, sentiment et univers |
| `modelFactory/features.py` | feature engineering local |
| `modelFactory/cross_sectional.py` | features cross-sectionnelles PIT-safe |
| `modelFactory/lightgbm_baseline.py` | challenger local LightGBM |
| `modelFactory/catboost_baseline.py` | challenger local CatBoost |
| `modelFactory/tabular_baseline.py` | helper commun des challengers tabulaires |
| `modelFactory/global_model.py` | entraînement du modèle global multi-symboles |
| `modelFactory/champion_selection.py` | gouvernance et éligibilité du champion |
| `modelFactory/calibration.py` | calibration Platt |
| `modelFactory/evaluation.py` | métriques, scores business, optimisation de seuil |
| `modelFactory/target_optimization.py` | optimisation horizon / seuils de target |
| `modelFactory/db_registry.py` | persistance DB résumée |
| `modelFactory/run_train.py` | wrapper `python -m modelFactory.run_train` |
| `modelFactory/run_predict.py` | wrapper `python -m modelFactory.run_predict` |

### 2.2 Répertoire d'artefacts

Par défaut :

```text
artifacts/models/
```

Convention :

```text
artifacts/models/
  AAPL/
    best.ckpt
    scaler.pkl
    calibrator.pkl                # LSTM si calibration activée
    lightgbm_model.pkl            # si challenger LightGBM entraîné
    lightgbm_calibrator.pkl       # si calibration LightGBM
    catboost_model.pkl            # si challenger CatBoost entraîné
    catboost_calibrator.pkl       # si calibration CatBoost
    config.json
    metrics.json
  MSFT/
    ...
  __GLOBAL__/
    global_model.pkl
    calibrator.pkl                # si calibration modèle global
    config.json
    metrics.json
```

---

## 3. Données et prérequis

### 3.1 Tables requises côté DB

#### Requises pour l'entraînement

- `stock_bars_daily`
- `stock_scores` si aucun `--symbols` explicite n'est fourni
- `model_registry`
- `model_training_run`
- `model_metrics`

#### Requises pour la prédiction

- `stock_bars_daily`
- `model_predictions`
- artefacts présents sur disque dans `artifacts/models/`

#### Optionnelles selon les options activées

- `ticker_daily_sentiment_features` si `--include-sentiment`
- univers multi-symboles si `--enable-cross-sectional`
- artefacts globaux si `global_model` est sélectionné

### 3.2 Variables d'environnement minimales

```powershell
$env:LOGIN_DB = "user"
$env:PASSWORD_DB = "pass"
```

Suivant l'environnement, `DB_HOST` et `DB_NAME` peuvent aussi être nécessaires.

### 3.3 Prérequis runtime ML

- Python 3.12+
- PyTorch / Lightning pour le chemin `lstm_attention`
- `lightgbm` si `--compare-lightgbm`
- `catboost` si `--enable-catboost` ou `--global-model-name catboost`

En l'absence d'une dépendance challenger, le run ne plante pas nécessairement : le challenger concerné peut être marqué `unavailable`.

---

## 4. CLI complète

### 4.1 Point d'entrée principal

```powershell
python -m modelFactory --mode train
python -m modelFactory --mode predict
```

### 4.2 Modes supportés

- `--mode train`
- `--mode predict`

### 4.3 Options d'univers et d'exécution

| Option | Rôle |
|---|---|
| `--symbols ...` | liste explicite de symboles |
| `--max-workers` | parallélisme CPU côté orchestrateur |
| `--artifacts-dir` | dossier racine des artefacts |
| `--accelerator auto|cpu|gpu` | résolution device train/predict |
| `--log-level` | niveau de log CLI |

### 4.4 Options data / features

| Option | Rôle |
|---|---|
| `--sequence-length` | longueur de séquence LSTM |
| `--forecast-horizon` | horizon de prédiction |
| `--training-start-date` | date minimale des barres utilisées pour le training (`YYYY-MM-DD`, défaut `2020-01-01`) |
| `--include-sentiment` | ajoute les features sentiment ticker |
| `--enable-cross-sectional` | active les features cross-sectionnelles |
| `--cross-sectional-min-universe` | taille minimale d'univers par date |
| `--feature-set v1|expert` | set de features |
| `--benchmark-symbol` | benchmark pour features expert / cross-sectionnelles |

### 4.5 Options target et décision

| Option | Rôle |
|---|---|
| `--target-mode binary|swing_cash` | sémantique de target |
| `--target-up-threshold` | seuil de hausse tradeable |
| `--target-down-threshold` | seuil de baisse / no-trade |
| `--decision-threshold` | seuil par défaut pour classer `long` vs `no_trade` |
| `--optimize-target` | recherche du meilleur horizon / seuils swing |
| `--optimize-thresholds` | recherche du meilleur seuil de décision |

### 4.6 Options calibration et évaluation

| Option | Rôle |
|---|---|
| `--calibration-method none|platt` | calibration des probabilités |
| `--calibration-min-samples` | taille mini pour calibrer |
| `--calibration-max-iter` | itérations max du calibrateur |
| `--walkforward` | active la validation walk-forward |
| `--wf-min-train-size`, `--wf-val-size`, `--wf-test-size`, `--wf-step-size`, `--wf-max-splits` | paramètres walk-forward |

### 4.7 Options challengers / gouvernance

| Option | Rôle |
|---|---|
| `--compare-lightgbm` | entraîne le challenger local LightGBM |
| `--enable-catboost` | entraîne le challenger local CatBoost |
| `--enable-global-model` | entraîne aussi un modèle global multi-symboles |
| `--global-model-name catboost|lightgbm` | backend du modèle global |
| `--global-artifact-symbol` | dossier d'artefacts du modèle global |
| `--select-champion` | active la sélection automatique du modèle servi |
| `--default-champion` | fallback explicite si pas d'auto-sélection |
| `--champion-selection-metric` | métrique de sélection (`selection_score`, `business_score`, `auc`) |

### 4.8 Options hyperparamètres challengers tabulaires

| Option | Rôle |
|---|---|
| `--lgbm-max-depth` | profondeur LightGBM |
| `--lgbm-n-estimators` | nombre d'arbres LightGBM |
| `--lgbm-learning-rate` | LR LightGBM |
| `--catboost-depth` | profondeur CatBoost |
| `--catboost-iterations` | itérations CatBoost |
| `--catboost-learning-rate` | LR CatBoost |

---

## 5. Commandes recommandées

### 5.1 Entraînement minimal

```powershell
python -m modelFactory --mode train --accelerator auto --training-start-date 2020-01-01
```

`--training-start-date` remplace l'ancienne logique de fenêtre exprimée en années.
Le training charge désormais les barres à partir d'une date absolue, ce qui rend
le contrat plus explicite côté IHM, CLI et artefacts persistés.

### 5.2 Entraînement orienté production locale multi-modèles

```powershell
python -m modelFactory --mode train --include-sentiment --compare-lightgbm --enable-catboost --select-champion --optimize-thresholds --accelerator auto --max-workers 1
```

### 5.3 Entraînement avec modèle global et features cross-sectionnelles

```powershell
python -m modelFactory --mode train --include-sentiment --enable-cross-sectional --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --select-champion --optimize-thresholds --accelerator auto --max-workers 1
```

### 5.4 Entraînement ciblé sur quelques symboles

```powershell
python -m modelFactory --mode train --symbols AAPL MSFT NVDA --include-sentiment --compare-lightgbm --enable-catboost --select-champion --accelerator cpu --max-epochs 20 --batch-size 32
```

### 5.5 Prédiction quotidienne batch

```powershell
python -m modelFactory --mode predict --accelerator auto
```

### 5.6 Prédiction ciblée

```powershell
python -m modelFactory --mode predict --symbols AAPL MSFT NVDA --accelerator cpu
```

### 5.7 Lanceurs dédiés

```powershell
python -m modelFactory.run_train --include-sentiment --compare-lightgbm --enable-catboost --select-champion --accelerator gpu --max-workers 1
python -m modelFactory.run_predict --accelerator auto
```

---

## 6. Déroulé réel de l'entraînement

### 6.1 Résolution de l'univers

Si `--symbols` est absent, `load_candidate_symbols()` lit `stock_scores.is_candidate = 1`.

### 6.2 Orchestration batch

`run_training_batch()` :

1. résout l'univers ;
2. choisit le parallélisme effectif ;
3. force `effective_workers = 1` si le GPU est demandé ou détecté en mode `auto` ;
4. entraîne chaque symbole ;
5. entraîne éventuellement le modèle global ;
6. réinjecte les routes et la gouvernance du `global_model` dans les artefacts symbole.

### 6.3 `train_symbol()` — détail par symbole

Pour chaque symbole :

1. vérifie `min_history_days` ;
2. prépare le `SymbolDataModule` ;
3. saute le symbole si les séquences deviennent insuffisantes après split ;
4. exécute éventuellement l'optimisation de target ;
5. exécute éventuellement le walk-forward ;
6. entraîne le `LSTMAttentionModule` ;
7. recharge le meilleur checkpoint ;
8. calcule métriques `val` / `test` ;
9. calibre les probabilités si demandé ;
10. optimise éventuellement le `decision_threshold` ;
11. entraîne éventuellement `lightgbm` ;
12. entraîne éventuellement `catboost` ;
13. construit les routes d'inférence ;
14. évalue l'éligibilité de chaque challenger ;
15. sélectionne le champion servi ;
16. persiste `config.json`, `metrics.json`, scaler, checkpoint et calibrateurs ;
17. écrit les résumés DB et le snapshot de gouvernance du champion/challengers.

### 6.5 Invariants temporels P0 (anti-fuite)

Les splits chronologiques sont désormais **purgés** aux frontières pour empêcher
qu'une target à horizon `forecast_horizon` traverse le split suivant :

- les `forecast_horizon` dernières lignes du train sont retirées avant la validation ;
- les `forecast_horizon` dernières lignes de la validation sont retirées avant le test ;
- la même règle s'applique au walk-forward ;
- pour le `global_model`, la purge est appliquée sur les **dates uniques** (pas seulement sur les lignes) ;
- pour les challengers tabulaires, la purge est identique au chemin séquentiel.

Conséquence : une observation utilisée pour l'entraînement ou la validation ne
peut plus avoir une `future_return` ou une `target` dépendant d'une barre située
dans le split suivant.

### 6.4 Ce qui est écrit en base

#### `model_training_run`

Contient un historique **résumé** du run :

- `run_id`
- `symbol`
- `status`
- `skip_reason`
- `started_at`, `finished_at`
- `checkpoint_path`
- `scaler_path`
- `config_path`

#### `model_metrics`

Contient des métriques **résumées** par split :

- `loss`
- `directional_accuracy`
- `precision`
- `recall`
- `auc`

Important : la DB **ne contient pas toute la richesse** de `metrics.json`.
Les détails challengers, rankings, champion et métriques business avancées vivent surtout sur disque.

#### `model_governance`

Contient un snapshot **par `run_id` / `symbol` / `model_name`** de la gouvernance multi-modèles :

- `rank`
- `is_selected_model`
- `selection_mode`
- `selection_metric`
- `selection_score`
- `selection_eligible`
- `eligibility_reason`
- `reason`
- `inference_backend`
- `backend_model_name`
- `calibration_method`
- `decision_threshold`
- `artifact_symbol`
- chemins d'artefacts utiles à l'audit
- métriques résumées (`val_auc`, `test_auc`, `wf_auc`, scores business)

Cette table sert de **snapshot SQL de justification** du champion retenu et des challengers présents au moment du run.

---

## 7. Contrat des artefacts

### 7.1 Artefacts communs symbole

Chaque symbole complété possède a minima :

- `config.json`
- `metrics.json`

Suivant le backend :

- `best.ckpt` + `scaler.pkl` pour le LSTM ;
- `lightgbm_model.pkl` pour LightGBM ;
- `catboost_model.pkl` pour CatBoost.

### 7.2 `config.json` — rôle stratégique

`config.json` est le **manifeste de serving** du symbole.

Il contient notamment :

- la config data / model / calibration ;
- les features utilisées ;
- `selected_decision_threshold` ;
- `architecture_selected` ;
- `selection_mode` ;
- `artifact_routes.selected_model` ;
- `artifact_routes.models.*`.

### 7.3 Routes d'inférence actuellement supportées

#### `lstm_attention`

```json
{
  "checkpoint_path": ".../best.ckpt",
  "scaler_path": ".../scaler.pkl",
  "config_path": ".../config.json",
  "calibrator_path": ".../calibrator.pkl",
  "inference_backend": "lstm_attention"
}
```

#### `lightgbm`

```json
{
  "status": "completed",
  "model_path": ".../lightgbm_model.pkl",
  "calibrator_path": ".../lightgbm_calibrator.pkl",
  "config_path": ".../config.json",
  "feature_columns": ["..."],
  "selected_decision_threshold": 0.61,
  "inference_backend": "lightgbm_tabular"
}
```

#### `catboost`

```json
{
  "status": "completed",
  "model_path": ".../catboost_model.pkl",
  "calibrator_path": ".../catboost_calibrator.pkl",
  "config_path": ".../config.json",
  "feature_columns": ["..."],
  "selected_decision_threshold": 0.59,
  "inference_backend": "catboost_tabular"
}
```

#### `global_model`

```json
{
  "status": "completed",
  "artifact_symbol": "__GLOBAL__",
  "model_path": ".../__GLOBAL__/global_model.pkl",
  "config_path": ".../__GLOBAL__/config.json",
  "calibrator_path": ".../__GLOBAL__/calibrator.pkl",
  "inference_backend": "global_tabular"
}
```

---

## 8. Gouvernance multi-modèles

### 8.1 Principe

Un modèle ne peut pas être champion seulement parce qu'il score bien.
Il doit aussi être **servable**.

### 8.2 Éligibilité actuelle

#### `lstm_attention`

Éligible si :

- status `completed`
- backend `lstm_attention`
- `checkpoint_path` présent
- `scaler_path` présent

#### `lightgbm`

Éligible si :

- status `completed`
- backend `lightgbm_tabular`
- `config_path` présent
- `model_path` présent

#### `catboost`

Éligible si :

- status `completed`
- backend `catboost_tabular`
- `config_path` présent
- `model_path` présent

#### `global_model`

Éligible si :

- status `completed`
- backend `global_tabular`
- `config_path` présent
- `model_path` présent

### 8.3 Modes de sélection

- `default_champion` : l'auto-sélection est désactivée
- `fallback_default_champion` : aucun challenger éligible, on revient au défaut
- `auto_selected_champion` : meilleur modèle éligible retenu

### 8.4 Où lire le résultat de gouvernance

#### Dans `config.json`

- `architecture_selected`
- `selection_mode`
- `artifact_routes.selected_model`

#### Dans `metrics.json`

- `champion`
- `challengers.ranking`
- détail de chaque challenger

---

## 9. Déroulé réel de la prédiction

### 9.1 Résolution des artefacts

`predict_symbol()` :

1. essaie d'abord `load_training_run()` via la DB ;
2. retombe sinon sur le dossier canonique `artifacts/models/<SYMBOL>/`.

### 9.2 Résolution du backend servi

Le prédicteur lit `config.json`, puis `_resolve_selected_model_route()` choisit :

- `global_tabular` si `selected_model = global_model` ;
- `lightgbm_tabular` ou `catboost_tabular` si `selected_model` vaut l'un de ces challengers ;
- sinon fallback sur `lstm_attention`.

### 9.3 Préparation des données

Le prédicteur recharge les données **bornées à la date de coupe** :

- `cutoff_date = as_of_date or prediction_date`
- chargement des bars jusqu'à cette date
- chargement du sentiment si nécessaire
- chargement benchmark / univers si features expertes ou cross-sectionnelles

Cette logique est essentielle pour la compatibilité backtesting / replay sans look-ahead trivial.

En complément, le contrat de features live est désormais durci :

- si `config.json` contient un `feature_fingerprint`, toute dérive du contrat
  courant provoque un **refus de serving** ;
- pour les routes tabulaires, l'absence d'une colonne requise provoque un
  **fail-fast explicite** en log ;
- une route champion incomplète peut retomber sur `lstm_attention`, mais ce
  fallback est désormais loggé explicitement avec la raison.

### 9.4 Chemin LSTM

Le prédicteur :

1. recharge `scaler.pkl` ;
2. transforme les `sequence_length` dernières lignes ;
3. recharge `best.ckpt` ;
4. applique éventuellement `calibrator.pkl` ;
5. compare la proba au `decision_threshold`.

### 9.5 Chemin tabulaire local ou global

Le prédicteur :

1. recharge le modèle picklé ;
2. reconstruit le dernier `DataFrame` de features ;
3. contrôle la présence des `feature_columns` ;
4. appelle `predict_proba()` ;
5. applique le calibrateur tabulaire si présent ;
6. compare la proba au `selected_decision_threshold` de la route ou au `decision_threshold` de config.

### 9.6 Ce qui est écrit dans `model_predictions`

La persistance DB de prédiction conserve désormais à la fois le résultat et le contexte de serving minimal :

- `symbol`
- `prediction_date`
- `predicted_proba`
- `predicted_class`
- `run_id`
- `selected_model`
- `decision_threshold`
- `signal_label`
- `calibration_method`

Important : certains champs restent **uniquement en mémoire** ou dans les artefacts, notamment `raw_proba` et le détail complet de la gouvernance challengers/champion.

Conséquence :

- `model_predictions` suffit pour l'audit quotidien du backend réellement servi ;
- `model_governance` apporte la justification SQL du champion ;
- les artefacts restent la source la plus riche pour le manifeste brut complet.

Important P0 : la CLI `predict` calcule désormais le **drift gate avant
persistance finale**. Si le kill-switch ML est activé, les prédictions du batch
ne sont pas écrites dans `model_predictions` ; le fallback côté risk devient
donc explicite (`quant` pur) et cohérent avec l'état du gate.

---

## 10. Intégration avec l'IHM

### 10.1 Étape `ML Train`

L'IHM (`ihm/services/pipeline_runner.py`) lance désormais une commande `modelFactory` cohérente avec la gouvernance multi-modèles :

- accélérateur `auto|cpu|gpu`
- sentiment optionnel
- challengers LightGBM / CatBoost optionnels
- modèle global optionnel
- features cross-sectionnelles optionnelles
- sélection champion optionnelle
- optimisation de seuil optionnelle
- optimisation target optionnelle

### 10.2 Étape `ML Predict`

L'IHM ne décide pas du backend au moment du predict.
Elle déclenche simplement :

```powershell
python -m modelFactory --mode predict --accelerator auto
```

Le backend réellement servi dépend des artefacts symbole existants.

### 10.3 Page `ML`

La page `ihm/pages/ml.py` combine désormais trois niveaux de lecture :

1. **artefacts disque** (`config.json`, `metrics.json`) pour le manifeste complet ;
2. **tables DB de synthèse** (`model_training_run`, `model_metrics`, `model_governance`, `model_predictions`) ;
3. **vue jointe serving ↔ gouvernance** qui relie une ligne de `model_predictions` au snapshot `model_governance` du même `run_id` / `symbol`.

Cette vue jointe permet de vérifier rapidement :

- quel modèle a été servi ;
- quel champion était déclaré par la gouvernance ;
- si le serving et la gouvernance sont alignés ;
- quel backend, quelle calibration et quel seuil étaient attendus côté snapshot.

---

## 11. Causes fréquentes de skip / échec

### 11.1 Skip en entraînement

Causes typiques :

1. `history_too_short`
2. `insufficient_sequences_after_split`
3. aucun split walk-forward valide
4. challenger indisponible (`lightgbm` ou `catboost` non installés)

### 11.2 Prédiction impossible

Causes typiques :

1. `config.json` absent
2. artefact ciblé absent (`best.ckpt`, `lightgbm_model.pkl`, etc.)
3. features manquantes au moment du predict
4. historique insuffisant pour reconstruire la dernière fenêtre
5. route `selected_model` invalide ou incomplète
6. dérive du `feature_fingerprint` entre entraînement et serving

### 11.4 Drift gate ML → risk_management

Le drift monitor publie une décision `drift_policy_decision` dans
`ml_drift_runs.payload`.

La consommation côté `risk_management` suit alors la règle suivante :

1. si `ALPHA_TRADE_DISABLE_ML=1`, le ML est désactivé manuellement ;
2. sinon, si la dernière décision drift porte `gate=disabled` ou
   `gate_action=kill_switch_ml`, `risk_management` **ignore totalement**
   `model_predictions` ;
3. le run summary risk expose `ml_gate_enabled`, `ml_gate_reason`,
   `ml_gate_decision_id`, `ml_gate_drift_status` et `ml_gate_action`.

Le comportement attendu en incident drift est donc : **pas de consommation ML,
pas de persistance du batch predict sous kill-switch, repli quant pur traçable**.

### 11.3 GPU non utilisé

Causes typiques :

1. `--accelerator cpu`
2. `--accelerator gpu` demandé sans CUDA disponible
3. fallback automatique vers CPU en prédiction

---

## 12. Vérifications opérationnelles utiles

### Vérifier les derniers runs d'entraînement

```powershell
python -c "from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text('SELECT run_id, symbol, status, started_at, finished_at, checkpoint_path, config_path FROM model_training_run ORDER BY started_at DESC LIMIT 10')).mappings().all();
    print([dict(r) for r in rows])"
```

### Vérifier les dernières métriques DB

```powershell
python -c "from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text('SELECT run_id, symbol, split_name, loss, directional_accuracy, auc FROM model_metrics ORDER BY created_at DESC LIMIT 20')).mappings().all();
    print([dict(r) for r in rows])"
```

### Vérifier les dernières prédictions persistées

```powershell
python -c "from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text('SELECT symbol, prediction_date, predicted_proba, predicted_class, run_id, selected_model, decision_threshold, signal_label, calibration_method FROM model_predictions ORDER BY prediction_date DESC, symbol LIMIT 20')).mappings().all();
    print([dict(r) for r in rows])"
```

### Vérifier la cohérence serving ↔ gouvernance

```powershell
python -c "from database.connection import get_sqlalchemy_engine; from sqlalchemy import text; engine = get_sqlalchemy_engine();
with engine.connect() as conn:
    rows = conn.execute(text('SELECT p.symbol, p.prediction_date, p.run_id, p.selected_model, g.model_name AS governance_champion, g.selection_mode FROM model_predictions p LEFT JOIN model_governance g ON g.run_id = p.run_id AND g.symbol = p.symbol AND g.is_selected_model = 1 ORDER BY p.prediction_date DESC, p.symbol LIMIT 20')).mappings().all();
    print([dict(r) for r in rows])"
```

### Vérifier les artefacts d'un symbole

```powershell
Get-ChildItem "C:\Users\MLI\PycharmProjects\alpha_trade\artifacts\models\AAPL"
Get-Content "C:\Users\MLI\PycharmProjects\alpha_trade\artifacts\models\AAPL\config.json"
Get-Content "C:\Users\MLI\PycharmProjects\alpha_trade\artifacts\models\AAPL\metrics.json"
```

---

## 13. Tests utiles

### Suite ciblée modèle / entraînement / prédiction

```powershell
python -m pytest tests/test_model_factory_config.py tests/test_model_factory_dataset.py tests/test_model_factory_trainer.py tests/test_model_factory_predictor.py tests/test_model_factory_orchestrator.py tests/test_model_factory_cli.py -q --no-cov
```

### Suite challengers tabulaires et gouvernance

```powershell
python -m pytest tests/test_model_factory_lightgbm_baseline.py tests/test_model_factory_catboost_baseline.py tests/test_model_factory_trainer.py tests/test_model_factory_predictor.py tests/test_model_factory_orchestrator.py -q --no-cov
```

### Suite complète `modelFactory`

```powershell
$files = Get-ChildItem "tests\test_model_factory*.py" | ForEach-Object { $_.FullName }
python -m pytest $files -q --no-cov
```

---

## 14. Recommandation opérateur

### Cadence recommandée

#### Hebdomadaire ou événementielle

- `train`

#### Quotidienne

- `predict`

### Séquence conseillée en production locale

```powershell
python -m modelFactory --mode train --include-sentiment --compare-lightgbm --enable-catboost --select-champion --optimize-thresholds --accelerator auto --max-workers 1
python -m modelFactory --mode predict --accelerator auto
```

### Quand activer le modèle global

Activer `--enable-global-model` si :

- l'univers est suffisamment large ;
- les features cross-sectionnelles sont stables ;
- on veut comparer un backend mutualisé à la logique purement locale par symbole.

Le laisser désactivé si l'objectif est de rester sur une gouvernance locale légère et robuste.

---

## 15. Limites connues

1. `model_metrics`, `model_governance` et `model_predictions` restent des tables **résumées**, pas des manifestes complets de gouvernance.
2. Le routage complet du champion et certains détails challengers vivent toujours surtout dans les artefacts disque.
3. Les modèles tabulaires locaux sont persistés via `pickle` ; c'est pratique et rapide, mais pas le format le plus strict à long terme.
4. L'IHM expose les options principales de gouvernance, mais pas encore l'intégralité de la CLI `modelFactory`.
5. Le chemin `predict` est PIT-safe côté chargement de données, mais toute nouvelle feature devra conserver cette discipline.

---

## 16. Priorités d'évolution si reprise du projet

1. ajouter des filtres IHM plus fins sur les statuts d'alignement serving ↔ gouvernance ;
2. versionner plus finement les artefacts tabulaires ;
3. ajouter des contrôles de compatibilité de features encore plus explicites au chargement ;
4. éventuellement migrer les persistences tabulaires vers des formats natifs (`LightGBM`, `CatBoost`) si le besoin d'interopérabilité augmente ;
5. enrichir encore la navigation IHM par `run_id` pour passer d'une prédiction au manifeste artefact exact qui l'a produite.

