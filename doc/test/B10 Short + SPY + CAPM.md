# Diagnostic ML — Batch `model-factory-20260810160939-927f00`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260810160939-927f00`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : B10 Short + SPY + CAPM
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0195
- **📈 IC IR (Stabilité)** : 1.09  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0103 H5=0.0186 H10=0.0274 H15=0.0267 H20=0.0294
- **🏆 Champion Global** : catboost (H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — score composite 55% IC + 30% IR + 15% positifs
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-10 16:09:40
- **Terminé le** : 2026-08-10 17:23:06
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-short-score --include-factors --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B10 Short + SPY + CAPM"
```

## 🌐 Global Ranking — Détails par Horizon

Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symboles, 6 splits walk-forward, 259239 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |   IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits | 🏆 Champion   |   Score |   IC catboost |   IR catboost |   IC lightgbm |   IR lightgbm |
|:----------|----------:|--------:|----------------:|--------------:|------------:|:--------------|--------:|--------------:|--------------:|--------------:|--------------:|
| H3        | 0.0127642 |    1.35 |       0.0103289 |           145 |           6 | catboost      |   1     |        0.0128 |          1.35 |        0.0078 |          0.66 |
| H5        | 0.0200855 |    1.32 |       0.0186322 |           145 |           6 | catboost      |   0.975 |        0.0201 |          1.32 |        0.0152 |          0.72 |
| H10       | 0.0230522 |    1.28 |       0.0274217 |           145 |           6 | catboost      |   0.95  |        0.0231 |          1.28 |        0.0127 |          0.62 |
| H15       | 0.018765  |    0.92 |       0.0267244 |           145 |           6 | catboost      |   0.95  |        0.0188 |          0.92 |        0.0152 |          0.48 |
| H20       | 0.0230013 |    1.05 |       0.0293552 |           145 |           6 | catboost      |   0.95  |        0.023  |          1.05 |        0.0074 |          0.28 |


🏆 **Meilleur horizon : H10** — sélectionné par score composite 55% IC + 30% IR + 15% Positive Split  |  H3=0.7545  H5=0.8972  H10=0.9343  H15=0.7521  H20=0.8811
### Horizon H3 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0128 | IR = 1.35 | Score composite = 1.000 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0128
- **Decile Spread** : 0.0103
- **Nb Features** : 145

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-24 | 2019-01-02 → 2019-06-26  |         149065 |        38302 |          0.00767075  |    0.028066   |   0.00767075  |
|       2 | 2016-12-29 → 2019-12-24 | 2020-01-02 → 2020-06-25  |         229215 |        40109 |          0.0286011   |    0.0104055  |   0.0286011   |
|       3 | 2016-12-29 → 2020-12-23 | 2020-12-31 → 2021-06-25  |         313075 |        41725 |          0.0204826   |    0.0055532  |   0.0204826   |
|       4 | 2016-12-29 → 2021-12-23 | 2021-12-31 → 2022-06-27  |         400519 |        44291 |          0.000812467 |   -0.0065426  |   0.000812467 |
|       5 | 2016-12-29 → 2022-12-23 | 2023-01-03 → 2023-06-28  |         494250 |        47206 |          0.0136466   |   -0.00501517 |   0.0136466   |
|       6 | 2016-12-29 → 2023-12-27 | 2024-01-04 → 2024-06-28  |         591911 |        47606 |          0.00537155  |    0.014175   |   0.00537155  |

- IC Moyen = 0.0128  |  IC Std = 0.0094  |  IC Min = 0.0008  |  IC Max = 0.0286

### Horizon H5 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0201 | IR = 1.32 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0201
- **Decile Spread** : 0.0186
- **Nb Features** : 145

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-20 | 2019-01-02 → 2019-06-24  |         148443 |        37670 |          0.00785989  |    0.0357161  |   0.00785989  |
|       2 | 2016-12-29 → 2019-12-20 | 2020-01-02 → 2020-06-23  |         228561 |        39443 |          0.0481992   |    0.050776   |   0.0481992   |
|       3 | 2016-12-29 → 2020-12-21 | 2020-12-31 → 2021-06-23  |         312395 |        41033 |          0.023088    |   -0.00990998 |   0.023088    |
|       4 | 2016-12-29 → 2021-12-21 | 2021-12-31 → 2022-06-23  |         399803 |        43543 |         -0.000257248 |    0.00822306 |  -0.000257248 |
|       5 | 2016-12-29 → 2022-12-21 | 2023-01-03 → 2023-06-26  |         493478 |        46432 |          0.0243102   |    0.00430302 |   0.0243102   |
|       6 | 2016-12-29 → 2023-12-22 | 2024-01-04 → 2024-06-26  |         591131 |        46822 |          0.017313    |    0.00226005 |   0.017313    |

- IC Moyen = 0.0201  |  IC Std = 0.0152  |  IC Min = -0.0003  |  IC Max = 0.0482

### Horizon H10 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0231 | IR = 1.28 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0231
- **Decile Spread** : 0.0274
- **Nb Features** : 145

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |         -0.000441538 |    0.0422951  |  -0.000441538 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |          0.0405755   |    0.0360421  |   0.0405755   |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |          0.0386296   |   -0.00367099 |   0.0386296   |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |         -0.00261803  |   -0.00686627 |  -0.00261803  |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |          0.036186    |    0.0152528  |   0.036186    |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |          0.0259815   |   -0.00710861 |   0.0259815   |

- IC Moyen = 0.0231  |  IC Std = 0.0180  |  IC Min = -0.0026  |  IC Max = 0.0406

### Horizon H15 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0188 | IR = 0.92 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0188
- **Decile Spread** : 0.0267
- **Nb Features** : 145

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |          -0.0143692  |     0.0339458 |   -0.0143692  |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |           0.0385241  |     0.072658  |    0.0385241  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |           0.0384593  |    -0.0201304 |    0.0384593  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |          -0.00029458 |     0.0115276 |   -0.00029458 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |           0.0342895  |     0.0113804 |    0.0342895  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |           0.0159809  |    -0.0180392 |    0.0159809  |

- IC Moyen = 0.0188  |  IC Std = 0.0204  |  IC Min = -0.0144  |  IC Max = 0.0385

### Horizon H20 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0230 | IR = 1.05 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0230
- **Decile Spread** : 0.0294
- **Nb Features** : 145

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |          -0.00159124 |    0.0447478  |   -0.00159124 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |           0.0393981  |    0.039221   |    0.0393981  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |           0.0497713  |   -0.0120206  |    0.0497713  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |          -0.00445938 |    0.00706035 |   -0.00445938 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |           0.0434438  |   -0.0236287  |    0.0434438  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |           0.011445   |   -0.0110977  |    0.011445   |

- IC Moyen = 0.0230  |  IC Std = 0.0220  |  IC Min = -0.0045  |  IC Max = 0.0498


## 🧪 Backtest Stratégies — Global Rank (H10 + H5)

| Variante | Score relatif |
|----------|---------------|
| V1 — H10 seul | 🏆 référence |
| V2 — H10 + H5 rising | -1.9% |
| V3 — H10 + H5 < 0.35 | -25.1% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H10 seul, V2 = H10 + H5 rising, V3 = H10 + H5 < 0.35 (contrarian).

---

## 🔵 Per-Symbol / Per-Sector — Métriques d'entraînement

### 🏆 Sélection du champion

✅ **Tout va bien** — 11 champions sélectionnés automatiquement sur 11 symboles.

### 📊 Champions par modèle

| model_name   |   nb_symbols |
|:-------------|-------------:|
| lightgbm     |            9 |
| catboost     |            2 |

## 📊 Métriques par Horizon (WF)

|   Horizon |   F1 macro |   F1 short |   F1 long |   Dir Acc |
|----------:|-----------:|-----------:|----------:|----------:|
|         3 |      0.33  |      0.49  |     0.501 |    0.5018 |
|         5 |      0.329 |      0.475 |     0.513 |    0.5018 |
|        10 |      0.328 |      0.473 |     0.511 |    0.501  |
|        15 |      0.328 |      0.473 |     0.51  |    0.5012 |
|        20 |      0.327 |      0.475 |     0.507 |    0.5001 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.332 |          0.508 |             0 |         0.488 |
| catboost     | test         |           11 |          0.329 |          0.519 |             0 |         0.466 |
| catboost     | wf           |           11 |          0.328 |          0.475 |             0 |         0.51  |
| lightgbm     | val          |           11 |          0.331 |          0.506 |             0 |         0.487 |
| lightgbm     | test         |           11 |          0.328 |          0.51  |             0 |         0.475 |
| lightgbm     | wf           |           11 |          0.329 |          0.479 |             0 |         0.507 |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| catboost     | test         |           11 |               51.925 |                   0 |              48.075 |               53.233 |               0     |              46.767 |
| catboost     | wf           |           11 |               51.407 |                   0 |              48.593 |               45.177 |               0     |              54.823 |
| lightgbm     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| lightgbm     | test         |           11 |               51.925 |                   0 |              48.075 |               51.405 |               0     |              48.595 |
| lightgbm     | wf           |           11 |               51.407 |                   0 |              48.593 |               45.908 |               0     |              54.091 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.20-0.29            |            1 |
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples       |      0.361 |     0.551 |      0.531 |         0 |
| Consumer Staples       |      0.356 |     0.546 |      0.523 |         0 |
| Industrials            |      0.346 |     0.512 |      0.526 |         0 |
| Consumer Staples       |      0.345 |     0.532 |      0.504 |         0 |
| Industrials            |      0.344 |     0.509 |      0.522 |         0 |
| Industrials            |      0.339 |     0.501 |      0.517 |         0 |
| Industrials            |      0.339 |     0.501 |      0.517 |         0 |
| Industrials            |      0.339 |     0.496 |      0.52  |         0 |
| Health Care            |      0.338 |     0.524 |      0.49  |         0 |
| Information Technology |      0.337 |     0.521 |      0.489 |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Energy                 |      0.293 |     0.423 |      0.455 |         0 |
| Energy                 |      0.295 |     0.435 |      0.45  |         0 |
| Energy                 |      0.305 |     0.452 |      0.463 |         0 |
| Materials              |      0.306 |     0.462 |      0.457 |         0 |
| Utilities              |      0.31  |     0.569 |      0.361 |         0 |
| Utilities              |      0.311 |     0.563 |      0.368 |         0 |
| Utilities              |      0.312 |     0.54  |      0.396 |         0 |
| Energy                 |      0.314 |     0.467 |      0.476 |         0 |
| Materials              |      0.317 |     0.463 |      0.488 |         0 |
| Communication Services |      0.319 |     0.51  |      0.447 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    1.0664 |        0.4982 |
| catboost     | test         |           11 |    1.0883 |        0.4963 |
| catboost     | wf           |           11 |    1.0445 |        0.5013 |
| lightgbm     | val          |           11 |    1.0804 |        0.4967 |
| lightgbm     | test         |           11 |    1.1098 |        0.4951 |
| lightgbm     | wf           |           11 |    1.0624 |        0.5011 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol           |   dir_acc |    mse |
|:-------------|:-----------------|----------:|-------:|
| lightgbm     | Consumer Staples |    0.5423 | 0.9273 |
| catboost     | Consumer Staples |    0.541  | 0.895  |
| lightgbm     | Consumer Staples |    0.5371 | 0.9148 |
| catboost     | Consumer Staples |    0.5286 | 0.9214 |
| catboost     | Consumer Staples |    0.5266 | 0.9025 |
| lightgbm     | Consumer Staples |    0.5214 | 0.9326 |
| lightgbm     | Industrials      |    0.5204 | 1.0496 |
| lightgbm     | Industrials      |    0.5169 | 1.0151 |
| catboost     | Health Care      |    0.5151 | 1.0541 |
| catboost     | Consumer Staples |    0.5135 | 0.941  |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Materials              |    0.4627 | 1.1108 |
| catboost     | Communication Services |    0.4723 | 1.0417 |
| catboost     | Utilities              |    0.4749 | 1.1509 |
| catboost     | Communication Services |    0.4781 | 1.0245 |
| catboost     | Communication Services |    0.4805 | 1.0081 |
| lightgbm     | Energy                 |    0.4805 | 0.9762 |
| lightgbm     | Materials              |    0.4812 | 1.0853 |
| lightgbm     | Energy                 |    0.4839 | 1.0125 |
| lightgbm     | Communication Services |    0.4841 | 1.0602 |
| lightgbm     | Communication Services |    0.4846 | 1.0744 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.32  |      0.435 |         0 |     0.524 | —           |     7.7 |      15   |            11 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.33  |      0.453 |         0 |     0.537 | —           |    19.1 |      25.7 |            11 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.325 |      0.462 |         0 |     0.512 | —           |     9.8 |      18.8 |            11 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.336 |      0.488 |         0 |     0.521 | —           |     0.1 |      24.9 |            11 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.32  |      0.492 |         0 |     0.468 | —           |     9   |      15.1 |            11 |
|       5 | 2024-09-03  | 2025-03-05 | 🟢 Bull           |      0.326 |      0.501 |         0 |     0.477 | —           |     5.6 |      17.4 |            11 |
