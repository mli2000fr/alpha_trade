# Diagnostic ML — Batch `model-factory-20260812185649-98d980`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260812185649-98d980`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : B32 Short + SPY + Score histo + YetiRank
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0224
- **📈 IC IR (Stabilité)** : 0.95  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0133 H5=0.0217 H10=0.0225 H15=0.0220 H20=0.0231
- **🏆 Champion Global** : catboost (H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — score composite 55% IC + 30% IR + 15% positifs
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-12 18:56:50
- **Terminé le** : 2026-08-13 00:50:40
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-short-score --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B32 Short + SPY + Score histo + YetiRank"
```

## 🌐 Global Ranking — Détails par Horizon

Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symboles, 6 splits walk-forward, 259239 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |   IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits | 🏆 Champion   |   Score |   IC catboost |   IR catboost |   IC lightgbm |   IR lightgbm |
|:----------|----------:|--------:|----------------:|--------------:|------------:|:--------------|--------:|--------------:|--------------:|--------------:|--------------:|
| H3        | 0.0149784 |    0.91 |       0.0132675 |           153 |           6 | catboost      |   0.975 |        0.015  |          0.91 |        0.0046 |          0.34 |
| H5        | 0.021344  |    0.97 |       0.0217118 |           153 |           6 | catboost      |   0.975 |        0.0213 |          0.97 |        0.0114 |          0.51 |
| H10       | 0.0252428 |    0.98 |       0.0224817 |           153 |           6 | catboost      |   0.95  |        0.0252 |          0.98 |        0.0129 |          0.41 |
| H15       | 0.0255019 |    0.96 |       0.0219925 |           153 |           6 | catboost      |   0.95  |        0.0255 |          0.96 |        0.0009 |          0.04 |
| H20       | 0.0249972 |    1.01 |       0.0230622 |           153 |           6 | catboost      |   0.95  |        0.025  |          1.01 |        0.0021 |          0.11 |


🏆 **Meilleur horizon : H10** — sélectionné par score composite 55% IC + 30% IR + 15% Positive Split  |  H3=0.7192  H5=0.8736  H10=0.9360  H15=0.9357  H20=0.9391
### Horizon H3 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0150 | IR = 0.91 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0150
- **Decile Spread** : 0.0133
- **Nb Features** : 153

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-24 | 2019-01-02 → 2019-06-26  |         149065 |        38302 |           0.00552919 |    0.0283122  |    0.00552919 |
|       2 | 2016-12-29 → 2019-12-24 | 2020-01-02 → 2020-06-25  |         229215 |        40109 |           0.0347782  |    0.0128502  |    0.0347782  |
|       3 | 2016-12-29 → 2020-12-23 | 2020-12-31 → 2021-06-25  |         313075 |        41725 |           0.0124898  |   -0.00305836 |    0.0124898  |
|       4 | 2016-12-29 → 2021-12-23 | 2021-12-31 → 2022-06-27  |         400519 |        44291 |          -0.0119112  |   -0.0149268  |   -0.0119112  |
|       5 | 2016-12-29 → 2022-12-23 | 2023-01-03 → 2023-06-28  |         494250 |        47206 |           0.0139064  |   -0.00077111 |    0.0139064  |
|       6 | 2016-12-29 → 2023-12-27 | 2024-01-04 → 2024-06-28  |         591911 |        47606 |           0.035078   |    0.00537065 |    0.035078   |

- IC Moyen = 0.0150  |  IC Std = 0.0164  |  IC Min = -0.0119  |  IC Max = 0.0351

### Horizon H5 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0213 | IR = 0.97 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0213
- **Decile Spread** : 0.0217
- **Nb Features** : 153

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-20 | 2019-01-02 → 2019-06-24  |         148443 |        37670 |           0.0250042  |   0.0184185   |    0.0250042  |
|       2 | 2016-12-29 → 2019-12-20 | 2020-01-02 → 2020-06-23  |         228561 |        39443 |           0.048535   |   0.0581443   |    0.048535   |
|       3 | 2016-12-29 → 2020-12-21 | 2020-12-31 → 2021-06-23  |         312395 |        41033 |           0.00831455 |   0.000617813 |    0.00831455 |
|       4 | 2016-12-29 → 2021-12-21 | 2021-12-31 → 2022-06-23  |         399803 |        43543 |          -0.0194666  |  -0.000171297 |   -0.0194666  |
|       5 | 2016-12-29 → 2022-12-21 | 2023-01-03 → 2023-06-26  |         493478 |        46432 |           0.0278216  |  -0.00528263  |    0.0278216  |
|       6 | 2016-12-29 → 2023-12-22 | 2024-01-04 → 2024-06-26  |         591131 |        46822 |           0.037855   |  -0.003043    |    0.037855   |

- IC Moyen = 0.0213  |  IC Std = 0.0220  |  IC Min = -0.0195  |  IC Max = 0.0485

### Horizon H10 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0252 | IR = 0.98 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0252
- **Decile Spread** : 0.0225
- **Nb Features** : 153

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |           0.0451911  |    0.032332   |    0.0451911  |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |           0.0434079  |    0.0721883  |    0.0434079  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |          -0.00864526 |   -0.0168846  |   -0.00864526 |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |          -0.0121444  |   -0.00280774 |   -0.0121444  |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |           0.0333145  |    0.00820074 |    0.0333145  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |           0.0503331  |   -0.0155881  |    0.0503331  |

- IC Moyen = 0.0252  |  IC Std = 0.0257  |  IC Min = -0.0121  |  IC Max = 0.0503

### Horizon H15 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0255 | IR = 0.96 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0255
- **Decile Spread** : 0.0220
- **Nb Features** : 153

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |           0.0448199  |   -0.0137083  |    0.0448199  |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |           0.0435768  |    0.034912   |    0.0435768  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |          -0.00702306 |   -0.0288518  |   -0.00702306 |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |          -0.0151403  |    0.00249746 |   -0.0151403  |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |           0.0342028  |    0.0186508  |    0.0342028  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |           0.0525753  |   -0.00792065 |    0.0525753  |

- IC Moyen = 0.0255  |  IC Std = 0.0265  |  IC Min = -0.0151  |  IC Max = 0.0526

### Horizon H20 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0250 | IR = 1.01 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0250
- **Decile Spread** : 0.0231
- **Nb Features** : 153

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |          0.0466834   |   -0.00980127 |   0.0466834   |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |          0.0378789   |    0.0362844  |   0.0378789   |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |         -0.000325343 |    0.0147699  |  -0.000325343 |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |         -0.0175647   |   -0.0165101  |  -0.0175647   |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |          0.0456456   |    0.00149334 |   0.0456456   |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |          0.0376655   |   -0.0134737  |   0.0376655   |

- IC Moyen = 0.0250  |  IC Std = 0.0248  |  IC Min = -0.0176  |  IC Max = 0.0467


## 🧪 Backtest Stratégies — Global Rank (H10 + H5)

| Variante | Score relatif |
|----------|---------------|
| V1 — H10 seul | 🏆 référence |
| V2 — H10 + H5 rising | -8.0% |
| V3 — H10 + H5 < 0.35 | -52.5% |
| V4 — H10 + top 3 horizons ↑ (H20,H10,H15) | -17.7% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H10 seul, V2 = H10 + H5 rising, V3 = H10 + H5 < 0.35 (contrarian). V4 = H10 + top 3 horizons ↑ (H20,H10,H15).

---

## 🔵 Per-Symbol / Per-Sector — Métriques d'entraînement

### 🏆 Sélection du champion

✅ **Tout va bien** — 11 champions sélectionnés automatiquement sur 11 symboles.

### 📊 Champions par modèle

| model_name   |   nb_symbols |
|:-------------|-------------:|
| lightgbm     |            8 |
| catboost     |            3 |

## 📊 Métriques par Horizon (WF)

|   Horizon |   F1 macro |   F1 short |   F1 long |   Dir Acc |
|----------:|-----------:|-----------:|----------:|----------:|
|         3 |      0.331 |      0.491 |     0.501 |    0.5016 |
|         5 |      0.329 |      0.475 |     0.513 |    0.5012 |
|        10 |      0.329 |      0.477 |     0.51  |    0.5024 |
|        15 |      0.329 |      0.474 |     0.512 |    0.5019 |
|        20 |      0.327 |      0.474 |     0.508 |    0.5    |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.333 |          0.509 |             0 |         0.489 |
| catboost     | test         |           11 |          0.33  |          0.523 |             0 |         0.467 |
| catboost     | wf           |           11 |          0.329 |          0.477 |             0 |         0.51  |
| lightgbm     | val          |           11 |          0.331 |          0.506 |             0 |         0.486 |
| lightgbm     | test         |           11 |          0.328 |          0.511 |             0 |         0.474 |
| lightgbm     | wf           |           11 |          0.329 |          0.479 |             0 |         0.508 |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| catboost     | test         |           11 |               51.925 |                   0 |              48.075 |               53.557 |               0     |              46.443 |
| catboost     | wf           |           11 |               51.407 |                   0 |              48.593 |               45.321 |               0     |              54.679 |
| lightgbm     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| lightgbm     | test         |           11 |               51.925 |                   0 |              48.075 |               51.703 |               0     |              48.297 |
| lightgbm     | wf           |           11 |               51.407 |                   0 |              48.593 |               45.788 |               0     |              54.212 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.20-0.29            |            1 |
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples       |      0.36  |     0.551 |      0.527 |         0 |
| Consumer Staples       |      0.358 |     0.553 |      0.523 |         0 |
| Consumer Staples       |      0.345 |     0.536 |      0.499 |         0 |
| Industrials            |      0.344 |     0.506 |      0.525 |         0 |
| Industrials            |      0.343 |     0.511 |      0.519 |         0 |
| Industrials            |      0.343 |     0.506 |      0.523 |         0 |
| Consumer Staples       |      0.339 |     0.54  |      0.478 |         0 |
| Industrials            |      0.339 |     0.499 |      0.518 |         0 |
| Communication Services |      0.338 |     0.507 |      0.506 |         0 |
| Industrials            |      0.337 |     0.499 |      0.512 |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Energy                 |      0.293 |     0.428 |      0.452 |         0 |
| Energy                 |      0.3   |     0.457 |      0.442 |         0 |
| Utilities              |      0.31  |     0.559 |      0.372 |         0 |
| Energy                 |      0.31  |     0.446 |      0.485 |         0 |
| Utilities              |      0.315 |     0.548 |      0.396 |         0 |
| Energy                 |      0.315 |     0.466 |      0.479 |         0 |
| Utilities              |      0.315 |     0.569 |      0.376 |         0 |
| Information Technology |      0.319 |     0.514 |      0.443 |         0 |
| Utilities              |      0.319 |     0.556 |      0.401 |         0 |
| Materials              |      0.319 |     0.482 |      0.476 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    1.0651 |        0.4994 |
| catboost     | test         |           11 |    1.0879 |        0.4982 |
| catboost     | wf           |           11 |    1.0433 |        0.5017 |
| lightgbm     | val          |           11 |    1.0811 |        0.4964 |
| lightgbm     | test         |           11 |    1.1081 |        0.4954 |
| lightgbm     | wf           |           11 |    1.0624 |        0.5011 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol           |   dir_acc |    mse |
|:-------------|:-----------------|----------:|-------:|
| catboost     | Consumer Staples |    0.5452 | 0.8896 |
| lightgbm     | Consumer Staples |    0.5406 | 0.9142 |
| lightgbm     | Consumer Staples |    0.54   | 0.91   |
| catboost     | Consumer Staples |    0.5301 | 0.9193 |
| catboost     | Consumer Staples |    0.53   | 0.8968 |
| lightgbm     | Consumer Staples |    0.5211 | 0.9284 |
| lightgbm     | Industrials      |    0.5171 | 1.0444 |
| lightgbm     | Industrials      |    0.5162 | 1.0155 |
| lightgbm     | Industrials      |    0.5156 | 0.9842 |
| catboost     | Consumer Staples |    0.515  | 0.9361 |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Materials              |    0.466  | 1.0992 |
| catboost     | Communication Services |    0.4745 | 1.0391 |
| catboost     | Communication Services |    0.4814 | 1.023  |
| lightgbm     | Materials              |    0.4826 | 1.0809 |
| lightgbm     | Energy                 |    0.4831 | 1.0278 |
| lightgbm     | Communication Services |    0.4835 | 1.0749 |
| catboost     | Materials              |    0.4838 | 1.0551 |
| lightgbm     | Energy                 |    0.4852 | 0.974  |
| catboost     | Information Technology |    0.4855 | 1.1044 |
| lightgbm     | Communication Services |    0.487  | 1.0618 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.321 |      0.438 |         0 |     0.525 | —           |     7.7 |      15   |            11 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.331 |      0.447 |         0 |     0.546 | —           |    19.1 |      25.7 |            11 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.324 |      0.457 |         0 |     0.514 | —           |     9.8 |      18.8 |            11 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.343 |      0.503 |         0 |     0.526 | —           |     0.1 |      24.9 |            11 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.318 |      0.49  |         0 |     0.465 | —           |     9   |      15.1 |            11 |
|       5 | 2024-09-03  | 2025-03-05 | 🟢 Bull           |      0.327 |      0.503 |         0 |     0.478 | —           |     5.6 |      17.4 |            11 |
