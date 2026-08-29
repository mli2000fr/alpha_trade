# Diagnostic ML — Batch `model-factory-20260813132105-a8aadc`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260813132105-a8aadc`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : B38 B25 avec 300 symblos (parmi les 400)
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0229
- **📈 IC IR (Stabilité)** : 1.14  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0127 H5=0.0226 H10=0.0195 H15=0.0231 H20=0.0210
- **🏆 Champion Global** : catboost (H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — score composite 55% IC + 30% IR + 15% positifs
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-13 13:21:05
- **Terminé le** : 2026-08-13 15:27:24
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-short-score --include-factors --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "Test 300"
```

## 🌐 Global Ranking — Détails par Horizon

Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 300 symboles, 6 splits walk-forward, 193402 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |   IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits | 🏆 Champion   |   Score |   IC catboost |   IR catboost |   IC lightgbm |   IR lightgbm |
|:----------|----------:|--------:|----------------:|--------------:|------------:|:--------------|--------:|--------------:|--------------:|--------------:|--------------:|
| H3        | 0.015721  |    1.23 |       0.0126681 |           145 |           6 | catboost      |   0.975 |        0.0157 |          1.23 |        0.0092 |          0.99 |
| H5        | 0.0228763 |    0.92 |       0.022644  |           145 |           6 | catboost      |   0.975 |        0.0229 |          0.92 |        0.0055 |          0.37 |
| H10       | 0.0252639 |    1.28 |       0.0195388 |           145 |           6 | catboost      |   0.975 |        0.0253 |          1.28 |        0.0047 |          0.16 |
| H15       | 0.025494  |    1.54 |       0.0231331 |           145 |           6 | catboost      |   0.929 |        0.0255 |          1.54 |        0.0293 |          0.72 |
| H20       | 0.0252129 |    1.11 |       0.0210457 |           145 |           6 | catboost      |   0.975 |        0.0252 |          1.11 |        0.0033 |          0.14 |


🏆 **Meilleur horizon : H15** — sélectionné par score composite 55% IC + 30% IR + 15% Positive Split  |  H3=0.7040  H5=0.7983  H10=0.9196  H15=1.0000  H20=0.8853
### Horizon H3 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0157 | IR = 1.23 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0157
- **Decile Spread** : 0.0127
- **Nb Features** : 145

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-24 | 2019-01-02 → 2019-06-26  |         111089 |        28392 |           0.00567533 |    0.0174197  |    0.00567533 |
|       2 | 2016-12-29 → 2019-12-24 | 2020-01-02 → 2020-06-25  |         170343 |        29617 |           0.0308269  |    0.0129251  |    0.0308269  |
|       3 | 2016-12-29 → 2020-12-23 | 2020-12-31 → 2021-06-25  |         232450 |        30933 |           0.0112194  |    0.00811637 |    0.0112194  |
|       4 | 2016-12-29 → 2021-12-23 | 2021-12-31 → 2022-06-27  |         297536 |        33220 |          -0.00455613 |   -0.00935991 |   -0.00455613 |
|       5 | 2016-12-29 → 2022-12-23 | 2023-01-03 → 2023-06-28  |         367818 |        35494 |           0.0220623  |    0.00774192 |    0.0220623  |
|       6 | 2016-12-29 → 2023-12-27 | 2024-01-04 → 2024-06-28  |         441255 |        35746 |           0.0290982  |    0.018349   |    0.0290982  |

- IC Moyen = 0.0157  |  IC Std = 0.0128  |  IC Min = -0.0046  |  IC Max = 0.0308

### Horizon H5 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0229 | IR = 0.92 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0229
- **Decile Spread** : 0.0226
- **Nb Features** : 145

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-20 | 2019-01-02 → 2019-06-24  |         110629 |        27924 |           0.022411   |    0.0074192  |    0.022411   |
|       2 | 2016-12-29 → 2019-12-20 | 2020-01-02 → 2020-06-23  |         169861 |        29123 |           0.0575986  |    0.0158599  |    0.0575986  |
|       3 | 2016-12-29 → 2020-12-21 | 2020-12-31 → 2021-06-23  |         231946 |        30419 |           0.00352488 |   -0.0220421  |    0.00352488 |
|       4 | 2016-12-29 → 2021-12-21 | 2021-12-31 → 2022-06-23  |         296998 |        32658 |          -0.0184276  |   -0.00470531 |   -0.0184276  |
|       5 | 2016-12-29 → 2022-12-21 | 2023-01-03 → 2023-06-26  |         367238 |        34912 |           0.0307814  |    0.0130142  |    0.0307814  |
|       6 | 2016-12-29 → 2023-12-22 | 2024-01-04 → 2024-06-26  |         440669 |        35160 |           0.0413696  |    0.02344    |    0.0413696  |

- IC Moyen = 0.0229  |  IC Std = 0.0248  |  IC Min = -0.0184  |  IC Max = 0.0576

### Horizon H10 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0253 | IR = 1.28 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0253
- **Decile Spread** : 0.0195
- **Nb Features** : 145

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         109479 |        26754 |           0.0214016  |   -0.025058   |    0.0214016  |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         168656 |        27888 |           0.0432704  |    0.0600598  |    0.0432704  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         230686 |        29139 |           0.00514799 |   -0.0265353  |    0.00514799 |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         295653 |        31256 |          -0.00519448 |    0.00356044 |   -0.00519448 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         365788 |        33457 |           0.0440436  |    0.0221749  |    0.0440436  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         439204 |        33695 |           0.0429144  |   -0.00628544 |    0.0429144  |

- IC Moyen = 0.0253  |  IC Std = 0.0197  |  IC Min = -0.0052  |  IC Max = 0.0440

### Horizon H15 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0255 | IR = 1.54 | Score composite = 0.929 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0255
- **Decile Spread** : 0.0231
- **Nb Features** : 145

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         109479 |        26754 |          0.0308529   |    0.0442469  |   0.0308529   |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         168656 |        27888 |          0.0331419   |    0.108717   |   0.0331419   |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         230686 |        29139 |          0.00672336  |   -0.018253   |   0.00672336  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         295653 |        31256 |          0.000404378 |    0.00625164 |   0.000404378 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         365788 |        33457 |          0.0480475   |    0.00285196 |   0.0480475   |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         439204 |        33695 |          0.0337943   |    0.0316994  |   0.0337943   |

- IC Moyen = 0.0255  |  IC Std = 0.0166  |  IC Min = 0.0004  |  IC Max = 0.0480

### Horizon H20 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0252 | IR = 1.11 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0252
- **Decile Spread** : 0.0210
- **Nb Features** : 145

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         109479 |        26754 |            0.0300017 |    0.0268724  |     0.0300017 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         168656 |        27888 |            0.0230924 |    0.0159935  |     0.0230924 |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         230686 |        29139 |            0.0106367 |    0.00306646 |     0.0106367 |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         295653 |        31256 |           -0.0105024 |    0.00845473 |    -0.0105024 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         365788 |        33457 |            0.0639922 |    0.0132154  |     0.0639922 |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         439204 |        33695 |            0.034057  |   -0.0475353  |     0.034057  |

- IC Moyen = 0.0252  |  IC Std = 0.0227  |  IC Min = -0.0105  |  IC Max = 0.0640


## 🧪 Backtest Stratégies — Global Rank (H15 + H5)

| Variante | Score relatif |
|----------|---------------|
| V1 — H15 seul | 🏆 référence |
| V2 — H15 + H5 rising | -10.8% |
| V3 — H15 + H5 < 0.35 | -42.3% |
| V4 — H15 + top 3 horizons ↑ (H15,H10,H20) | -25.2% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H15 seul, V2 = H15 + H5 rising, V3 = H15 + H5 < 0.35 (contrarian). V4 = H15 + top 3 horizons ↑ (H15,H10,H20).

---

## 🔵 Per-Symbol / Per-Sector — Métriques d'entraînement

### 🏆 Sélection du champion

✅ **Tout va bien** — 11 champions sélectionnés automatiquement sur 11 symboles.

### 📊 Champions par modèle

| model_name   |   nb_symbols |
|:-------------|-------------:|
| lightgbm     |            6 |
| catboost     |            5 |

## 📊 Métriques par Horizon (WF)

|   Horizon |   F1 macro |   F1 short |   F1 long |   Dir Acc |
|----------:|-----------:|-----------:|----------:|----------:|
|         3 |      0.33  |      0.489 |     0.502 |    0.5012 |
|         5 |      0.331 |      0.473 |     0.519 |    0.5042 |
|        10 |      0.33  |      0.475 |     0.514 |    0.5037 |
|        15 |      0.329 |      0.474 |     0.515 |    0.504  |
|        20 |      0.326 |      0.473 |     0.507 |    0.5016 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.333 |          0.505 |             0 |         0.494 |
| catboost     | test         |           11 |          0.328 |          0.511 |             0 |         0.473 |
| catboost     | wf           |           11 |          0.329 |          0.473 |             0 |         0.513 |
| lightgbm     | val          |           11 |          0.332 |          0.503 |             0 |         0.492 |
| lightgbm     | test         |           11 |          0.327 |          0.5   |             0 |         0.481 |
| lightgbm     | wf           |           11 |          0.33  |          0.481 |             0 |         0.51  |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               51.154 |                   0 |              48.846 |               49.995 |               0.01  |              49.995 |
| catboost     | test         |           11 |               51.072 |                   0 |              48.928 |               52.761 |               0     |              47.239 |
| catboost     | wf           |           11 |               50.442 |                   0 |              49.558 |               45.642 |               0     |              54.358 |
| lightgbm     | val          |           11 |               51.154 |                   0 |              48.846 |               49.995 |               0.013 |              49.992 |
| lightgbm     | test         |           11 |               51.072 |                   0 |              48.928 |               50.775 |               0.002 |              49.224 |
| lightgbm     | wf           |           11 |               50.442 |                   0 |              49.558 |               46.757 |               0.001 |              53.242 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.20-0.29            |            1 |
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples       |      0.354 |     0.519 |      0.544 |         0 |
| Consumer Staples       |      0.347 |     0.526 |      0.514 |         0 |
| Consumer Staples       |      0.343 |     0.524 |      0.506 |         0 |
| Financials             |      0.341 |     0.536 |      0.488 |         0 |
| Financials             |      0.341 |     0.538 |      0.485 |         0 |
| Financials             |      0.34  |     0.54  |      0.481 |         0 |
| Health Care            |      0.34  |     0.53  |      0.49  |         0 |
| Consumer Staples       |      0.336 |     0.514 |      0.496 |         0 |
| Health Care            |      0.336 |     0.545 |      0.463 |         0 |
| Information Technology |      0.335 |     0.532 |      0.473 |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Energy                 |      0.287 |     0.417 |      0.445 |         0 |
| Energy                 |      0.301 |     0.444 |      0.458 |         0 |
| Energy                 |      0.307 |     0.449 |      0.471 |         0 |
| Materials              |      0.318 |     0.458 |      0.496 |         0 |
| Energy                 |      0.319 |     0.47  |      0.485 |         0 |
| Materials              |      0.32  |     0.468 |      0.491 |         0 |
| Communication Services |      0.32  |     0.505 |      0.454 |         0 |
| Information Technology |      0.32  |     0.521 |      0.439 |         0 |
| Health Care            |      0.321 |     0.503 |      0.46  |         0 |
| Communication Services |      0.322 |     0.52  |      0.445 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    1.0908 |        0.5004 |
| catboost     | test         |           11 |    1.1064 |        0.4953 |
| catboost     | wf           |           11 |    1.0535 |        0.5025 |
| lightgbm     | val          |           11 |    1.1059 |        0.4984 |
| lightgbm     | test         |           11 |    1.1261 |        0.4926 |
| lightgbm     | wf           |           11 |    1.0709 |        0.5034 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol           |   dir_acc |    mse |
|:-------------|:-----------------|----------:|-------:|
| lightgbm     | Utilities        |    0.5423 | 1.299  |
| lightgbm     | Utilities        |    0.5378 | 1.1411 |
| lightgbm     | Consumer Staples |    0.5346 | 0.923  |
| catboost     | Consumer Staples |    0.5341 | 0.9114 |
| catboost     | Consumer Staples |    0.5287 | 0.9322 |
| catboost     | Utilities        |    0.5257 | 1.1512 |
| lightgbm     | Consumer Staples |    0.5253 | 0.9297 |
| lightgbm     | Utilities        |    0.5246 | 1.0349 |
| catboost     | Consumer Staples |    0.5243 | 0.9043 |
| catboost     | Utilities        |    0.5241 | 1.0406 |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| catboost     | Communication Services |    0.4752 | 0.9853 |
| lightgbm     | Materials              |    0.4799 | 1.0229 |
| lightgbm     | Energy                 |    0.4815 | 0.9553 |
| lightgbm     | Materials              |    0.4818 | 1.0646 |
| catboost     | Communication Services |    0.4835 | 0.9665 |
| lightgbm     | Energy                 |    0.4836 | 1.0294 |
| lightgbm     | Communication Services |    0.4838 | 1.0134 |
| catboost     | Materials              |    0.485  | 1.0084 |
| catboost     | Health Care            |    0.4856 | 1.0704 |
| lightgbm     | Communication Services |    0.4861 | 1.0408 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.317 |      0.445 |         0 |     0.507 | —           |     7.7 |      15   |            11 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.334 |      0.459 |         0 |     0.542 | —           |    19.1 |      25.7 |            11 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.312 |      0.441 |         0 |     0.496 | —           |     9.8 |      18.8 |            11 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.332 |      0.453 |         0 |     0.543 | —           |     0.1 |      24.9 |            11 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.317 |      0.497 |         0 |     0.455 | —           |     9   |      15.1 |            11 |
|       5 | 2024-09-03  | 2025-03-05 | 🟢 Bull           |      0.341 |      0.511 |         0 |     0.511 | —           |     5.6 |      17.4 |            11 |
