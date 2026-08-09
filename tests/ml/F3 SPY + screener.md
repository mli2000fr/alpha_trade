# Diagnostic ML — Batch `model-factory-20260808110218-8907b3`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260808110218-8907b3`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : F3 SPY + screener
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0176
- **📈 IC IR (Stabilité)** : 0.92  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0082 H5=0.0187 H10=0.0250 H15=0.0264 H20=0.0239
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-08 11:02:18
- **Terminé le** : 2026-08-08 12:53:01
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-screener-scores --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "F3 SPY + screener"
```

## 🏆 Sélection du champion

✅ **Tout va bien** — 11 champions sélectionnés automatiquement sur 11 symboles.

### 📊 Champions par modèle

| model_name   |   nb_symbols |
|:-------------|-------------:|
| catboost     |            7 |
| lightgbm     |            4 |

## 🌐 Global Ranking — Détails par Horizon

Modèle Catboost — 400 symboles, 6 splits walk-forward, 259239 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |    IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits |
|:----------|-----------:|--------:|----------------:|--------------:|------------:|
| H3        | 0.00918371 |    1.08 |      0.00822789 |           166 |           6 |
| H5        | 0.0184219  |    1.09 |      0.0186743  |           166 |           6 |
| H10       | 0.0186441  |    0.92 |      0.0250373  |           166 |           6 |
| H15       | 0.0224377  |    1.03 |      0.0263869  |           166 |           6 |
| H20       | 0.0191107  |    0.88 |      0.023867   |           166 |           6 |

### Horizon H3

- **IC Rank** : 0.0092
- **Decile Spread** : 0.0082
- **Nb Features** : 166

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |      IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|-------------:|
|       1 | 2016-12-29 → 2018-12-24 | 2019-01-02 → 2019-06-26  |         149065 |        38302 |  0.00345301  |
|       2 | 2016-12-29 → 2019-12-24 | 2020-01-02 → 2020-06-25  |         229215 |        40109 |  0.022753    |
|       3 | 2016-12-29 → 2020-12-23 | 2020-12-31 → 2021-06-25  |         313075 |        41725 |  0.0184233   |
|       4 | 2016-12-29 → 2021-12-23 | 2021-12-31 → 2022-06-27  |         400519 |        44291 | -0.000807919 |
|       5 | 2016-12-29 → 2022-12-23 | 2023-01-03 → 2023-06-28  |         494250 |        47206 |  0.00699863  |
|       6 | 2016-12-29 → 2023-12-27 | 2024-01-04 → 2024-06-28  |         591911 |        47606 |  0.00428227  |

- IC Moyen = 0.0092  |  IC Std = 0.0085  |  IC Min = -0.0008  |  IC Max = 0.0228

### Horizon H5

- **IC Rank** : 0.0184
- **Decile Spread** : 0.0187
- **Nb Features** : 166

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |     IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|------------:|
|       1 | 2016-12-29 → 2018-12-20 | 2019-01-02 → 2019-06-24  |         148443 |        37670 |  0.0113232  |
|       2 | 2016-12-29 → 2019-12-20 | 2020-01-02 → 2020-06-23  |         228561 |        39443 |  0.0496726  |
|       3 | 2016-12-29 → 2020-12-21 | 2020-12-31 → 2021-06-23  |         312395 |        41033 |  0.0206426  |
|       4 | 2016-12-29 → 2021-12-21 | 2021-12-31 → 2022-06-23  |         399803 |        43543 | -0.00570615 |
|       5 | 2016-12-29 → 2022-12-21 | 2023-01-03 → 2023-06-26  |         493478 |        46432 |  0.0238982  |
|       6 | 2016-12-29 → 2023-12-22 | 2024-01-04 → 2024-06-26  |         591131 |        46822 |  0.010701   |

- IC Moyen = 0.0184  |  IC Std = 0.0169  |  IC Min = -0.0057  |  IC Max = 0.0497

### Horizon H10

- **IC Rank** : 0.0186
- **Decile Spread** : 0.0250
- **Nb Features** : 166

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |      IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|-------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 | -0.000631177 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |  0.0371765   |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |  0.0365594   |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 | -0.0160666   |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |  0.0324313   |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |  0.0223953   |

- IC Moyen = 0.0186  |  IC Std = 0.0202  |  IC Min = -0.0161  |  IC Max = 0.0372

### Horizon H15

- **IC Rank** : 0.0224
- **Decile Spread** : 0.0264
- **Nb Features** : 166

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |      IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|-------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |  0.000658808 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |  0.037861    |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |  0.0484463   |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 | -0.0110837   |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |  0.0402509   |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |  0.0184928   |

- IC Moyen = 0.0224  |  IC Std = 0.0218  |  IC Min = -0.0111  |  IC Max = 0.0484

### Horizon H20

- **IC Rank** : 0.0191
- **Decile Spread** : 0.0239
- **Nb Features** : 166

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |     IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 | -0.00380948 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |  0.0218429  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |  0.0504383  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 | -0.00559251 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |  0.042995   |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |  0.00878991 |

- IC Moyen = 0.0191  |  IC Std = 0.0216  |  IC Min = -0.0056  |  IC Max = 0.0504


## 🧪 Backtest Stratégies — Global Rank

| Variante | Score relatif |
|----------|---------------|
| V1 — H20 seul | 🏆 référence |
| V2 — H20 + H5 rising | -9.3% |
| V3 — H20 + H5 < 0.35 | -23.3% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H20 seul, V2 = H20 + H5 rising, V3 = H20 + H5 < 0.35 (contrarian).

---

## 🔵 Per-Symbol / Per-Sector — Métriques d'entraînement

## 📊 Métriques par Horizon (WF)

|   Horizon |   F1 macro |   F1 short |   F1 long |   Dir Acc |
|----------:|-----------:|-----------:|----------:|----------:|
|         3 |      0.33  |      0.488 |     0.503 |    0.5015 |
|         5 |      0.329 |      0.474 |     0.512 |    0.5007 |
|        10 |      0.329 |      0.475 |     0.512 |    0.5026 |
|        15 |      0.329 |      0.473 |     0.513 |    0.5021 |
|        20 |      0.328 |      0.476 |     0.51  |    0.5015 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.332 |          0.508 |             0 |         0.489 |
| catboost     | test         |           11 |          0.33  |          0.521 |             0 |         0.47  |
| catboost     | wf           |           11 |          0.329 |          0.475 |             0 |         0.51  |
| lightgbm     | val          |           11 |          0.331 |          0.506 |             0 |         0.487 |
| lightgbm     | test         |           11 |          0.329 |          0.512 |             0 |         0.474 |
| lightgbm     | wf           |           11 |          0.33  |          0.479 |             0 |         0.51  |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| catboost     | test         |           11 |               51.925 |                   0 |              48.075 |               53.102 |               0     |              46.898 |
| catboost     | wf           |           11 |               51.407 |                   0 |              48.593 |               45.178 |               0     |              54.822 |
| lightgbm     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.005 |              49.998 |
| lightgbm     | test         |           11 |               51.925 |                   0 |              48.075 |               51.734 |               0     |              48.266 |
| lightgbm     | wf           |           11 |               51.407 |                   0 |              48.593 |               45.591 |               0     |              54.409 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.20-0.29            |            1 |
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol           |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples |      0.366 |     0.561 |      0.537 |         0 |
| Consumer Staples |      0.358 |     0.554 |      0.52  |         0 |
| Consumer Staples |      0.35  |     0.534 |      0.516 |         0 |
| Health Care      |      0.342 |     0.531 |      0.496 |         0 |
| Health Care      |      0.341 |     0.531 |      0.49  |         0 |
| Consumer Staples |      0.34  |     0.537 |      0.482 |         0 |
| Industrials      |      0.338 |     0.509 |      0.506 |         0 |
| Health Care      |      0.338 |     0.532 |      0.482 |         0 |
| Health Care      |      0.337 |     0.526 |      0.485 |         0 |
| Industrials      |      0.336 |     0.509 |      0.5   |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Energy                 |      0.296 |     0.444 |      0.444 |         0 |
| Energy                 |      0.3   |     0.446 |      0.453 |         0 |
| Energy                 |      0.307 |     0.441 |      0.479 |         0 |
| Energy                 |      0.315 |     0.469 |      0.476 |         0 |
| Materials              |      0.319 |     0.49  |      0.468 |         0 |
| Utilities              |      0.319 |     0.55  |      0.407 |         0 |
| Communication Services |      0.321 |     0.512 |      0.45  |         0 |
| Materials              |      0.321 |     0.47  |      0.495 |         0 |
| Materials              |      0.322 |     0.477 |      0.489 |         0 |
| Information Technology |      0.323 |     0.508 |      0.46  |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    1.0662 |        0.4989 |
| catboost     | test         |           11 |    1.0872 |        0.4983 |
| catboost     | wf           |           11 |    1.044  |        0.5015 |
| lightgbm     | val          |           11 |    1.0796 |        0.4971 |
| lightgbm     | test         |           11 |    1.1087 |        0.4957 |
| lightgbm     | wf           |           11 |    1.0618 |        0.5018 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol           |   dir_acc |    mse |
|:-------------|:-----------------|----------:|-------:|
| lightgbm     | Consumer Staples |    0.5499 | 0.914  |
| lightgbm     | Consumer Staples |    0.5409 | 0.9097 |
| catboost     | Consumer Staples |    0.5399 | 0.8907 |
| catboost     | Consumer Staples |    0.5313 | 0.8961 |
| catboost     | Consumer Staples |    0.5296 | 0.9206 |
| lightgbm     | Consumer Staples |    0.5278 | 0.9249 |
| lightgbm     | Industrials      |    0.5161 | 1.0435 |
| lightgbm     | Financials       |    0.516  | 1.1336 |
| catboost     | Health Care      |    0.5151 | 1.0517 |
| lightgbm     | Financials       |    0.5143 | 1.0953 |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Materials              |    0.4713 | 1.0995 |
| lightgbm     | Materials              |    0.4779 | 1.0877 |
| catboost     | Communication Services |    0.4806 | 1.0426 |
| catboost     | Materials              |    0.4816 | 1.0505 |
| catboost     | Communication Services |    0.4833 | 1.0248 |
| lightgbm     | Energy                 |    0.4846 | 1.016  |
| lightgbm     | Communication Services |    0.4865 | 1.0795 |
| lightgbm     | Materials              |    0.4868 | 1.0283 |
| lightgbm     | Energy                 |    0.4872 | 0.9793 |
| lightgbm     | Energy                 |    0.4881 | 0.9386 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.321 |      0.439 |         0 |     0.526 | —           |     7.7 |      15   |            11 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.331 |      0.45  |         0 |     0.544 | —           |    19.1 |      25.7 |            11 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.324 |      0.459 |         0 |     0.512 | —           |     9.8 |      18.8 |            11 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.342 |      0.504 |         0 |     0.523 | —           |     0.1 |      24.9 |            11 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.321 |      0.492 |         0 |     0.469 | —           |     9   |      15.1 |            11 |
|       5 | 2024-09-03  | 2025-03-05 | 🟢 Bull           |      0.327 |      0.502 |         0 |     0.479 | —           |     5.6 |      17.4 |            11 |
