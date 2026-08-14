# Diagnostic ML — Batch `model-factory-20260812185814-da184f`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260812185814-da184f`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : B33 Short + SPY + sectoriel + YetiRank
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0138
- **📈 IC IR (Stabilité)** : 0.72  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0128 H5=0.0156 H10=0.0102 H15=0.0046 H20=0.0101
- **🏆 Champion Global** : catboost (H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — score composite 55% IC + 30% IR + 15% positifs
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-12 18:58:14
- **Terminé le** : 2026-08-13 01:00:48
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-short-score --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --enable-cross-sectional --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B33 Short + SPY + sectoriel + YetiRank"
```

## 🌐 Global Ranking — Détails par Horizon

Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symboles, 6 splits walk-forward, 265689 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |   IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits | 🏆 Champion   |   Score |   IC catboost |   IR catboost |   IC lightgbm |   IR lightgbm |
|:----------|----------:|--------:|----------------:|--------------:|------------:|:--------------|--------:|--------------:|--------------:|--------------:|--------------:|
| H3        | 0.0139031 |    0.76 |       0.0128483 |           159 |           6 | catboost      |   0.975 |        0.0139 |          0.76 |        0.0045 |          0.23 |
| H5        | 0.0184455 |    0.96 |       0.0155554 |           177 |           6 | catboost      |   0.975 |        0.0184 |          0.96 |        0.0076 |          0.51 |
| H10       | 0.0144811 |    0.84 |       0.0101606 |           177 |           6 | catboost      |   0.975 |        0.0145 |          0.84 |        0.0114 |          0.62 |
| H15       | 0.0115033 |    0.59 |       0.0046474 |           177 |           6 | catboost      |   0.975 |        0.0115 |          0.59 |        0.0066 |          0.48 |
| H20       | 0.0107453 |    0.52 |       0.0101361 |           177 |           6 | catboost      |   0.975 |        0.0107 |          0.52 |       -0.0044 |         -0.52 |


🏆 **Meilleur horizon : H5** — sélectionné par score composite 55% IC + 30% IR + 15% Positive Split  |  H3=0.7769  H5=0.9750  H10=0.8175  H15=0.6528  H20=0.6071
### Horizon H3 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0139 | IR = 0.76 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0139
- **Decile Spread** : 0.0128
- **Nb Features** : 159

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |          0.000725567 |    0.00496924 |   0.000725567 |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |          0.0341256   |    0.040668   |   0.0341256   |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |          0.0203052   |    0.0108173  |   0.0203052   |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |         -0.0161777   |   -0.0201666  |  -0.0161777   |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |          0.00927906  |   -0.0139209  |   0.00927906  |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |          0.0351606   |    0.00477547 |   0.0351606   |

- IC Moyen = 0.0139  |  IC Std = 0.0183  |  IC Min = -0.0162  |  IC Max = 0.0352

### Horizon H5 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0184 | IR = 0.96 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0184
- **Decile Spread** : 0.0156
- **Nb Features** : 177

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |            0.0170823 |   0.0204932   |     0.0170823 |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |            0.0349465 |   0.0326556   |     0.0349465 |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |            0.0216187 |  -0.00454859  |     0.0216187 |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |           -0.021845  |  -0.0105298   |    -0.021845  |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |            0.0241208 |   0.00722058  |     0.0241208 |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |            0.0347496 |   0.000119249 |     0.0347496 |

- IC Moyen = 0.0184  |  IC Std = 0.0192  |  IC Min = -0.0218  |  IC Max = 0.0349

### Horizon H10 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0145 | IR = 0.84 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0145
- **Decile Spread** : 0.0102
- **Nb Features** : 177

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |            0.0199381 |    0.0333491  |     0.0199381 |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |            0.023054  |    0.0287713  |     0.023054  |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |            0.0112596 |    0.0209696  |     0.0112596 |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |           -0.0220256 |   -0.00267764 |    -0.0220256 |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |            0.0238598 |    0.00648985 |     0.0238598 |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |            0.0308009 |   -0.0187258  |     0.0308009 |

- IC Moyen = 0.0145  |  IC Std = 0.0173  |  IC Min = -0.0220  |  IC Max = 0.0308

### Horizon H15 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0115 | IR = 0.59 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0115
- **Decile Spread** : 0.0046
- **Nb Features** : 177

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |           0.0262878  |     0.0175412 |    0.0262878  |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |           0.00892371 |     0.016326  |    0.00892371 |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |           0.00756302 |     0.0179382 |    0.00756302 |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |          -0.027732   |     0.013786  |   -0.027732   |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |           0.0271618  |    -0.0154564 |    0.0271618  |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |           0.0268155  |    -0.010329  |    0.0268155  |

- IC Moyen = 0.0115  |  IC Std = 0.0194  |  IC Min = -0.0277  |  IC Max = 0.0272

### Horizon H20 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0107 | IR = 0.52 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0107
- **Decile Spread** : 0.0101
- **Nb Features** : 177

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |           0.0172902  |   -0.00223828 |    0.0172902  |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |           0.00101747 |   -0.00275068 |    0.00101747 |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |           0.00963954 |    0.00186273 |    0.00963954 |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |          -0.0280162  |   -0.0131391  |   -0.0280162  |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |           0.034297   |    0.00720676 |    0.034297   |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |           0.0302436  |   -0.0175243  |    0.0302436  |

- IC Moyen = 0.0107  |  IC Std = 0.0207  |  IC Min = -0.0280  |  IC Max = 0.0343


## 🧪 Backtest Stratégies — Global Rank (H5 seul)

| Variante | Score relatif |
|----------|---------------|
| V1 — H5 seul | 🏆 référence |
| V4 — H5 + top 3 horizons ↑ (H5,H10,H3) | -24.6% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H5 seul (V2/V3 non calculés — H5 est déjà le meilleur horizon). V4 = H5 + top 3 horizons ↑ (H5,H10,H3).

---

## 🔵 Per-Symbol / Per-Sector — Métriques d'entraînement

### 🏆 Sélection du champion

✅ **Tout va bien** — 11 champions sélectionnés automatiquement sur 11 symboles.

### 📊 Champions par modèle

| model_name   |   nb_symbols |
|:-------------|-------------:|
| lightgbm     |            7 |
| catboost     |            4 |

## 📊 Métriques par Horizon (WF)

|   Horizon |   F1 macro |   F1 short |   F1 long |   Dir Acc |
|----------:|-----------:|-----------:|----------:|----------:|
|         3 |      0.331 |      0.493 |     0.499 |    0.5019 |
|         5 |      0.329 |      0.481 |     0.505 |    0.5005 |
|        10 |      0.33  |      0.489 |     0.499 |    0.5031 |
|        15 |      0.33  |      0.488 |     0.502 |    0.5034 |
|        20 |      0.328 |      0.486 |     0.499 |    0.5019 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.332 |          0.508 |             0 |         0.489 |
| catboost     | test         |           11 |          0.333 |          0.519 |             0 |         0.479 |
| catboost     | wf           |           11 |          0.329 |          0.485 |             0 |         0.501 |
| lightgbm     | val          |           11 |          0.332 |          0.508 |             0 |         0.489 |
| lightgbm     | test         |           11 |          0.331 |          0.507 |             0 |         0.485 |
| lightgbm     | wf           |           11 |          0.33  |          0.49  |             0 |         0.501 |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| catboost     | test         |           11 |               51.925 |                   0 |              48.075 |               51.915 |               0     |              48.085 |
| catboost     | wf           |           11 |               51.407 |                   0 |              48.593 |               47.166 |               0     |              52.834 |
| lightgbm     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| lightgbm     | test         |           11 |               51.925 |                   0 |              48.075 |               50.223 |               0     |              49.777 |
| lightgbm     | wf           |           11 |               51.407 |                   0 |              48.593 |               47.658 |               0     |              52.342 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.20-0.29            |            1 |
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol           |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples |      0.357 |     0.541 |      0.531 |         0 |
| Consumer Staples |      0.354 |     0.534 |      0.529 |         0 |
| Industrials      |      0.347 |     0.511 |      0.53  |         0 |
| Health Care      |      0.346 |     0.508 |      0.531 |         0 |
| Consumer Staples |      0.346 |     0.519 |      0.518 |         0 |
| Industrials      |      0.344 |     0.502 |      0.532 |         0 |
| Industrials      |      0.342 |     0.504 |      0.523 |         0 |
| Health Care      |      0.34  |     0.5   |      0.521 |         0 |
| Financials       |      0.339 |     0.496 |      0.522 |         0 |
| Financials       |      0.339 |     0.495 |      0.523 |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Energy                 |      0.297 |     0.458 |      0.432 |         0 |
| Materials              |      0.304 |     0.464 |      0.446 |         0 |
| Energy                 |      0.305 |     0.484 |      0.431 |         0 |
| Energy                 |      0.312 |     0.454 |      0.483 |         0 |
| Energy                 |      0.312 |     0.471 |      0.466 |         0 |
| Communication Services |      0.314 |     0.498 |      0.443 |         0 |
| Utilities              |      0.315 |     0.539 |      0.407 |         0 |
| Materials              |      0.317 |     0.462 |      0.488 |         0 |
| Materials              |      0.319 |     0.463 |      0.492 |         0 |
| Utilities              |      0.32  |     0.562 |      0.398 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    1.0626 |        0.4988 |
| catboost     | test         |           11 |    1.0816 |        0.5029 |
| catboost     | wf           |           11 |    1.0471 |        0.5016 |
| lightgbm     | val          |           11 |    1.0754 |        0.4991 |
| lightgbm     | test         |           11 |    1.107  |        0.4985 |
| lightgbm     | wf           |           11 |    1.0681 |        0.5027 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol           |   dir_acc |    mse |
|:-------------|:-----------------|----------:|-------:|
| lightgbm     | Consumer Staples |    0.5398 | 0.9219 |
| lightgbm     | Consumer Staples |    0.5333 | 0.9137 |
| catboost     | Consumer Staples |    0.5294 | 0.8993 |
| catboost     | Consumer Staples |    0.5224 | 0.898  |
| lightgbm     | Industrials      |    0.5217 | 1.0321 |
| catboost     | Consumer Staples |    0.5211 | 0.9297 |
| lightgbm     | Consumer Staples |    0.5199 | 0.9433 |
| catboost     | Health Care      |    0.5198 | 1.0567 |
| lightgbm     | Industrials      |    0.5188 | 1.0124 |
| lightgbm     | Utilities        |    0.5168 | 1.3525 |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Materials              |    0.4616 | 1.1054 |
| catboost     | Materials              |    0.4776 | 1.0089 |
| lightgbm     | Materials              |    0.4793 | 1.0776 |
| catboost     | Materials              |    0.4807 | 1.0435 |
| catboost     | Communication Services |    0.4808 | 1.041  |
| lightgbm     | Energy                 |    0.4836 | 1.0728 |
| lightgbm     | Materials              |    0.4841 | 1.0193 |
| catboost     | Materials              |    0.4849 | 1.0416 |
| lightgbm     | Energy                 |    0.485  | 1.0636 |
| lightgbm     | Energy                 |    0.4853 | 0.9386 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.324 |      0.444 |         0 |     0.528 | —           |     7.7 |      15   |            11 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.336 |      0.471 |         0 |     0.537 | —           |    19.1 |      25.7 |            11 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.324 |      0.507 |         0 |     0.465 | —           |     9.8 |      18.8 |            11 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.343 |      0.517 |         0 |     0.511 | —           |     0.1 |      24.9 |            11 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.323 |      0.52  |         0 |     0.45  | —           |     9   |      15.1 |            11 |
|       5 | 2024-09-03  | 2025-03-05 | 🟢 Bull           |      0.322 |      0.471 |         0 |     0.496 | —           |     5.6 |      17.4 |            11 |
