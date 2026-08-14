# Diagnostic ML — Batch `model-factory-20260813092928-9f906f`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260813092928-9f906f`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : B37 B25 + symbols 393
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0123
- **📈 IC IR (Stabilité)** : 0.89  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0205 H5=0.0182 H10=0.0113 H15=0.0058 H20=-0.0003
- **🏆 Champion Global** : catboost (H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — score composite 55% IC + 30% IR + 15% positifs
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-13 09:29:28
- **Terminé le** : 2026-08-13 12:06:00
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-short-score --include-factors --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B37 B25 + symbols 393"
```

## 🌐 Global Ranking — Détails par Horizon

Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 393 symboles, 6 splits walk-forward, 231598 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |    IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits | 🏆 Champion   |   Score |   IC catboost |   IR catboost |   IC lightgbm |   IR lightgbm |
|:----------|-----------:|--------:|----------------:|--------------:|------------:|:--------------|--------:|--------------:|--------------:|--------------:|--------------:|
| H3        | 0.0198786  |    1.43 |     0.020452    |           145 |           6 | catboost      |   1     |        0.0199 |          1.43 |        0.0018 |          0.1  |
| H5        | 0.0180067  |    1.43 |     0.0182291   |           145 |           6 | catboost      |   1     |        0.018  |          1.43 |        0.0041 |          0.28 |
| H10       | 0.0115958  |    0.83 |     0.0113361   |           145 |           6 | catboost      |   0.975 |        0.0116 |          0.83 |        0.0001 |          0    |
| H15       | 0.00853044 |    0.83 |     0.00579772  |           145 |           6 | catboost      |   0.836 |        0.0085 |          0.83 |        0.0108 |          0.46 |
| H20       | 0.00354171 |    0.33 |    -0.000291437 |           145 |           6 | catboost      |   0.95  |        0.0035 |          0.33 |       -0.0027 |         -0.12 |


🏆 **Meilleur horizon : H3** — sélectionné par score composite 55% IC + 30% IR + 15% Positive Split  |  H3=0.9997  H5=0.9482  H10=0.6201  H15=0.5108  H20=0.2671
### Horizon H3 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0199 | IR = 1.43 | Score composite = 1.000 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0199
- **Decile Spread** : 0.0205
- **Nb Features** : 145

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-24 | 2019-01-02 → 2019-06-26  |         118090 |        31036 |           0.0225584  |    0.0161057  |    0.0225584  |
|       2 | 2016-12-29 → 2019-12-24 | 2020-01-02 → 2020-06-25  |         183472 |        33075 |           0.0431987  |    0.0172875  |    0.0431987  |
|       3 | 2016-12-29 → 2020-12-23 | 2020-12-31 → 2021-06-25  |         253273 |        35906 |           0.00338632 |    0.0132049  |    0.00338632 |
|       4 | 2016-12-29 → 2021-12-23 | 2021-12-31 → 2022-06-27  |         329402 |        40997 |           0.0112012  |   -0.0332226  |    0.0112012  |
|       5 | 2016-12-29 → 2022-12-23 | 2023-01-03 → 2023-06-28  |         416826 |        45047 |           0.00797341 |    0.00511264 |    0.00797341 |
|       6 | 2016-12-29 → 2023-12-27 | 2024-01-04 → 2024-06-28  |         510198 |        45537 |           0.0309535  |   -0.00744549 |    0.0309535  |

- IC Moyen = 0.0199  |  IC Std = 0.0139  |  IC Min = 0.0034  |  IC Max = 0.0432

### Horizon H5 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0180 | IR = 1.43 | Score composite = 1.000 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0180
- **Decile Spread** : 0.0182
- **Nb Features** : 145

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-20 | 2019-01-02 → 2019-06-24  |         117588 |        30516 |           0.0191529  |   0.00652385  |    0.0191529  |
|       2 | 2016-12-29 → 2019-12-20 | 2020-01-02 → 2020-06-23  |         182934 |        32519 |           0.0394519  |   0.0157025   |    0.0394519  |
|       3 | 2016-12-29 → 2020-12-21 | 2020-12-31 → 2021-06-23  |         252693 |        35310 |           0.00605972 |  -0.0203195   |    0.00605972 |
|       4 | 2016-12-29 → 2021-12-21 | 2021-12-31 → 2022-06-23  |         328750 |        40301 |           0.0041684  |  -0.000825695 |    0.0041684  |
|       5 | 2016-12-29 → 2022-12-21 | 2023-01-03 → 2023-06-26  |         416090 |        44305 |           0.0109015  |  -0.00259671  |    0.0109015  |
|       6 | 2016-12-29 → 2023-12-22 | 2024-01-04 → 2024-06-26  |         509450 |        44787 |           0.0283055  |   0.0262321   |    0.0283055  |

- IC Moyen = 0.0180  |  IC Std = 0.0126  |  IC Min = 0.0042  |  IC Max = 0.0395

### Horizon H10 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0116 | IR = 0.83 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0116
- **Decile Spread** : 0.0113
- **Nb Features** : 145

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         116333 |        29222 |           0.0214714  |    0.0266918  |    0.0214714  |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         181589 |        31134 |           0.0240163  |    0.0102751  |    0.0240163  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         251243 |        33820 |          -0.0144489  |   -0.00256262 |   -0.0144489  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         327120 |        38561 |           0.00120665 |   -0.0340449  |    0.00120665 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         414250 |        42452 |           0.0146909  |   -0.006103   |    0.0146909  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         507580 |        42912 |           0.0226383  |    0.00610627 |    0.0226383  |

- IC Moyen = 0.0116  |  IC Std = 0.0140  |  IC Min = -0.0144  |  IC Max = 0.0240

### Horizon H15 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0085 | IR = 0.83 | Score composite = 0.836 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0085
- **Decile Spread** : 0.0058
- **Nb Features** : 145

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         116333 |        29222 |           0.0114793  |     0.0313502 |    0.0114793  |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         181589 |        31134 |           0.018863   |     0.0334381 |    0.018863   |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         251243 |        33820 |          -0.00698759 |    -0.0192342 |   -0.00698759 |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         327120 |        38561 |          -0.00191562 |    -0.0175502 |   -0.00191562 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         414250 |        42452 |           0.008399   |     0.0024961 |    0.008399   |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         507580 |        42912 |           0.0213445  |     0.0341086 |    0.0213445  |

- IC Moyen = 0.0085  |  IC Std = 0.0102  |  IC Min = -0.0070  |  IC Max = 0.0213

### Horizon H20 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0035 | IR = 0.33 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0035
- **Decile Spread** : -0.0003
- **Nb Features** : 145

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         116333 |        29222 |           0.008598   |   -0.00413387 |    0.008598   |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         181589 |        31134 |           0.0163233  |    0.0362832  |    0.0163233  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         251243 |        33820 |          -0.00882113 |   -0.0235248  |   -0.00882113 |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         327120 |        38561 |          -0.0126464  |   -0.0295957  |   -0.0126464  |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         414250 |        42452 |           0.00480723 |   -0.0030054  |    0.00480723 |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         507580 |        42912 |           0.0129894  |    0.00805472 |    0.0129894  |

- IC Moyen = 0.0035  |  IC Std = 0.0108  |  IC Min = -0.0126  |  IC Max = 0.0163


## 🧪 Backtest Stratégies — Global Rank (H3 + H5)

| Variante | Score relatif |
|----------|---------------|
| V1 — H3 seul | 🏆 référence |
| V2 — H3 + H5 rising | -13.3% |
| V3 — H3 + H5 < 0.35 | -74.3% |
| V4 — H3 + top 3 horizons ↑ (H3,H5,H10) | -26.3% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H3 seul, V2 = H3 + H5 rising, V3 = H3 + H5 < 0.35 (contrarian). V4 = H3 + top 3 horizons ↑ (H3,H5,H10).

---

## 🔵 Per-Symbol / Per-Sector — Métriques d'entraînement

### 🏆 Sélection du champion

✅ **Tout va bien** — 11 champions sélectionnés automatiquement sur 11 symboles.

### 📊 Champions par modèle

| model_name   |   nb_symbols |
|:-------------|-------------:|
| catboost     |            7 |
| lightgbm     |            4 |

## 📊 Métriques par Horizon (WF)

|   Horizon |   F1 macro |   F1 short |   F1 long |   Dir Acc |
|----------:|-----------:|-----------:|----------:|----------:|
|         3 |      0.327 |      0.495 |     0.485 |    0.4942 |
|         5 |      0.327 |      0.498 |     0.483 |    0.5008 |
|        10 |      0.321 |      0.484 |     0.479 |    0.4891 |
|        15 |      0.323 |      0.479 |     0.491 |    0.493  |
|        20 |      0.316 |      0.459 |     0.489 |    0.4848 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.33  |          0.507 |             0 |         0.485 |
| catboost     | test         |           11 |          0.327 |          0.499 |             0 |         0.483 |
| catboost     | wf           |           11 |          0.323 |          0.482 |             0 |         0.488 |
| lightgbm     | val          |           11 |          0.335 |          0.513 |             0 |         0.491 |
| lightgbm     | test         |           11 |          0.332 |          0.504 |             0 |         0.493 |
| lightgbm     | wf           |           11 |          0.322 |          0.484 |             0 |         0.483 |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               52.18  |                   0 |              47.82  |               49.994 |               0.012 |              49.994 |
| catboost     | test         |           11 |               52.239 |                   0 |              47.761 |               49.388 |               0     |              50.612 |
| catboost     | wf           |           11 |               52.343 |                   0 |              47.657 |               47.219 |               0     |              52.781 |
| lightgbm     | val          |           11 |               52.18  |                   0 |              47.82  |               49.994 |               0.013 |              49.993 |
| lightgbm     | test         |           11 |               52.239 |                   0 |              47.761 |               48.811 |               0     |              51.189 |
| lightgbm     | wf           |           11 |               52.343 |                   0 |              47.657 |               47.786 |               0.001 |              52.213 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.20-0.29            |            3 |
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Energy                 |      0.343 |     0.531 |      0.497 |         0 |
| Communication Services |      0.337 |     0.478 |      0.532 |         0 |
| Industrials            |      0.336 |     0.511 |      0.497 |         0 |
| Industrials            |      0.336 |     0.523 |      0.484 |         0 |
| Health Care            |      0.335 |     0.509 |      0.496 |         0 |
| Information Technology |      0.334 |     0.495 |      0.508 |         0 |
| Industrials            |      0.333 |     0.512 |      0.488 |         0 |
| Industrials            |      0.333 |     0.509 |      0.491 |         0 |
| Industrials            |      0.333 |     0.497 |      0.502 |         0 |
| Utilities              |      0.333 |     0.494 |      0.504 |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol      |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:------------|-----------:|----------:|-----------:|----------:|
| Real Estate |      0.247 |     0.301 |      0.44  |         0 |
| Real Estate |      0.277 |     0.393 |      0.438 |         0 |
| Utilities   |      0.281 |     0.433 |      0.409 |         0 |
| Real Estate |      0.291 |     0.445 |      0.43  |         0 |
| Utilities   |      0.293 |     0.508 |      0.371 |         0 |
| Energy      |      0.299 |     0.516 |      0.381 |         0 |
| Real Estate |      0.303 |     0.364 |      0.545 |         0 |
| Energy      |      0.306 |     0.508 |      0.41  |         0 |
| Utilities   |      0.308 |     0.444 |      0.482 |         0 |
| Utilities   |      0.311 |     0.336 |      0.598 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    1.6019 |        0.4961 |
| catboost     | test         |           11 |    1.6332 |        0.4956 |
| catboost     | wf           |           11 |    1.7878 |        0.4926 |
| lightgbm     | val          |           11 |    1.6345 |        0.5026 |
| lightgbm     | test         |           11 |    1.6597 |        0.502  |
| lightgbm     | wf           |           11 |    1.897  |        0.4921 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Utilities              |    0.5335 | 6.7698 |
| catboost     | Utilities              |    0.5324 | 3.3449 |
| lightgbm     | Energy                 |    0.5172 | 1.1708 |
| catboost     | Energy                 |    0.5146 | 1.172  |
| catboost     | Utilities              |    0.514  | 5.579  |
| lightgbm     | Consumer Staples       |    0.5138 | 1.0429 |
| lightgbm     | Consumer Staples       |    0.5137 | 1.0253 |
| catboost     | Energy                 |    0.5129 | 1.0547 |
| lightgbm     | Industrials            |    0.5125 | 1.0294 |
| lightgbm     | Consumer Discretionary |    0.512  | 1.138  |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol      |   dir_acc |    mse |
|:-------------|:------------|----------:|-------:|
| lightgbm     | Real Estate |    0.379  | 5.2899 |
| catboost     | Real Estate |    0.381  | 6.2511 |
| catboost     | Real Estate |    0.4187 | 5.0521 |
| catboost     | Utilities   |    0.4229 | 6.4762 |
| lightgbm     | Real Estate |    0.4444 | 5.5799 |
| lightgbm     | Real Estate |    0.4504 | 6.2046 |
| catboost     | Utilities   |    0.4562 | 6.2531 |
| catboost     | Real Estate |    0.4583 | 2.114  |
| lightgbm     | Energy      |    0.4583 | 1.2149 |
| lightgbm     | Utilities   |    0.4625 | 6.8096 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.341 |      0.506 |         0 |     0.516 | —           |     7.7 |      15   |             9 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.328 |      0.494 |         0 |     0.491 | —           |    19.1 |      25.7 |             9 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.323 |      0.46  |         0 |     0.507 | —           |     9.8 |      18.8 |             9 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.305 |      0.38  |         0 |     0.535 | —           |     0.1 |      24.9 |             9 |
|       3 | 2023-04-06  | 2023-11-02 | 🟢 Bull           |      0.268 |      0.26  |         0 |     0.545 | —           |     5.3 |      16.2 |             1 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.32  |      0.501 |         0 |     0.46  | —           |     9   |      15.1 |            10 |
|       4 | 2024-05-07  | 2024-12-03 | 🟢 Bull           |      0.322 |      0.396 |         0 |     0.571 | —           |    16.8 |      16.3 |             1 |
|       5 | 2024-09-03  | 2025-03-05 | 🔵 Range low vol  |      0.312 |      0.488 |         0 |     0.448 | —           |     5.6 |      17.4 |            10 |
|       5 | 2025-06-09  | 2025-12-02 | 🟢 Bull           |      0.288 |      0.457 |         0 |     0.408 | —           |    13.6 |      17.3 |             1 |
