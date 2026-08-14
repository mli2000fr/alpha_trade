# Diagnostic ML — Batch `model-factory-20260814123609-02f5c9`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260814123609-02f5c9`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : B43-B41-config-train-end-2024-12-31
- **Date début training** : 2016-01-01
- **Date fin training** : 2024-12-31
- **Date univers** : 2024-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0224
- **📈 IC IR (Stabilité)** : 1.39  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0145 H5=0.0243 H10=0.0255 H15=0.0302 H20=0.0257
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-14 12:36:09
- **Terminé le** : 2026-08-14 14:42:57
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2024-12-31 --include-short-score --include-factors --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --include-volume-features --comment B43-B41-config-train-end-2024-12-31
```

## 🌐 Global Ranking — Détails par Horizon

Modèle catboost — 400 symboles, 5 splits walk-forward, 211629 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |   IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits |
|:----------|----------:|--------:|----------------:|--------------:|------------:|
| H3        | 0.0178577 |    1.23 |       0.0144561 |           155 |           5 |
| H5        | 0.0206505 |    1.03 |       0.0243303 |           155 |           5 |
| H10       | 0.0230621 |    1.45 |       0.0254787 |           155 |           5 |
| H15       | 0.0258041 |    1.84 |       0.0302374 |           155 |           5 |
| H20       | 0.024644  |    1.75 |       0.0256956 |           155 |           5 |


🏆 **Meilleur horizon : H15** — sélectionné par score composite 55% IC + 30% IR + 15% Positive Split  |  H3=0.7011  H5=0.7290  H10=0.8787  H15=1.0000  H20=0.9610
### Horizon H3

- **IC Rank** : 0.0179
- **Decile Spread** : 0.0145
- **Nb Features** : 155

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |     IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|------------:|
|       1 | 2016-12-29 → 2018-12-24 | 2019-01-02 → 2019-06-26  |         149065 |        38302 |  0.014536   |
|       2 | 2016-12-29 → 2019-12-24 | 2020-01-02 → 2020-06-25  |         229215 |        40105 |  0.0402745  |
|       3 | 2016-12-29 → 2020-12-23 | 2020-12-31 → 2021-06-25  |         313071 |        41725 |  0.0176662  |
|       4 | 2016-12-29 → 2021-12-23 | 2021-12-31 → 2022-06-27  |         400515 |        44291 | -0.00513642 |
|       5 | 2016-12-29 → 2022-12-23 | 2023-01-03 → 2023-06-28  |         494246 |        47206 |  0.0219481  |

- IC Moyen = 0.0179  |  IC Std = 0.0146  |  IC Min = -0.0051  |  IC Max = 0.0403

### Horizon H5

- **IC Rank** : 0.0207
- **Decile Spread** : 0.0243
- **Nb Features** : 155

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |     IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|------------:|
|       1 | 2016-12-29 → 2018-12-20 | 2019-01-02 → 2019-06-24  |         148443 |        37670 |  0.0314971  |
|       2 | 2016-12-29 → 2019-12-20 | 2020-01-02 → 2020-06-23  |         228561 |        39439 |  0.0459173  |
|       3 | 2016-12-29 → 2020-12-21 | 2020-12-31 → 2021-06-23  |         312391 |        41033 |  0.00545264 |
|       4 | 2016-12-29 → 2021-12-21 | 2021-12-31 → 2022-06-23  |         399799 |        43543 | -0.00967342 |
|       5 | 2016-12-29 → 2022-12-21 | 2023-01-03 → 2023-06-26  |         493474 |        46432 |  0.0300587  |

- IC Moyen = 0.0207  |  IC Std = 0.0200  |  IC Min = -0.0097  |  IC Max = 0.0459

### Horizon H10

- **IC Rank** : 0.0231
- **Decile Spread** : 0.0255
- **Nb Features** : 155

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |    IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|-----------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 | 0.034044   |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37774 | 0.0329281  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310691 |        39308 | 0.00310825 |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398009 |        41676 | 0.00465262 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491544 |        44497 | 0.0405776  |

- IC Moyen = 0.0231  |  IC Std = 0.0159  |  IC Min = 0.0031  |  IC Max = 0.0406

### Horizon H15

- **IC Rank** : 0.0258
- **Decile Spread** : 0.0302
- **Nb Features** : 155

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |    IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|-----------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 | 0.0306056  |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37774 | 0.031866   |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310691 |        39308 | 0.00492026 |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398009 |        41676 | 0.0159675  |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491544 |        44497 | 0.0456613  |

- IC Moyen = 0.0258  |  IC Std = 0.0140  |  IC Min = 0.0049  |  IC Max = 0.0457

### Horizon H20

- **IC Rank** : 0.0246
- **Decile Spread** : 0.0257
- **Nb Features** : 155

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |    IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|-----------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 | 0.0254683  |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37774 | 0.0243031  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310691 |        39308 | 0.00236031 |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398009 |        41676 | 0.0241997  |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491544 |        44497 | 0.0468888  |

- IC Moyen = 0.0246  |  IC Std = 0.0141  |  IC Min = 0.0024  |  IC Max = 0.0469


## 🧪 Backtest Stratégies — Global Rank (H15 + H5)

| Variante | Score relatif |
|----------|---------------|
| V1 — H15 seul | 🏆 référence |
| V2 — H15 + H5 rising | -12.3% |
| V3 — H15 + H5 < 0.35 | -57.1% |
| V4 — H15 + top 3 horizons ↑ (H15,H20,H10) | -29.2% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H15 seul, V2 = H15 + H5 rising, V3 = H15 + H5 < 0.35 (contrarian). V4 = H15 + top 3 horizons ↑ (H15,H20,H10).

---

## 🔵 Per-Symbol / Per-Sector — Métriques d'entraînement

### 🏆 Sélection du champion

✅ **Tout va bien** — 11 champions sélectionnés automatiquement sur 11 symboles.

### 📊 Champions par modèle

| model_name   |   nb_symbols |
|:-------------|-------------:|
| catboost     |            6 |
| lightgbm     |            5 |

## 📊 Métriques par Horizon (WF)

|   Horizon |   F1 macro |   F1 short |   F1 long |   Dir Acc |
|----------:|-----------:|-----------:|----------:|----------:|
|         3 |      0.33  |      0.488 |     0.502 |    0.5014 |
|         5 |      0.329 |      0.476 |     0.512 |    0.5013 |
|        10 |      0.329 |      0.478 |     0.51  |    0.5037 |
|        15 |      0.328 |      0.476 |     0.507 |    0.5021 |
|        20 |      0.326 |      0.472 |     0.505 |    0.4998 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.333 |          0.511 |             0 |         0.488 |
| catboost     | test         |           11 |          0.328 |          0.538 |             0 |         0.445 |
| catboost     | wf           |           11 |          0.328 |          0.476 |             0 |         0.508 |
| lightgbm     | val          |           11 |          0.331 |          0.509 |             0 |         0.485 |
| lightgbm     | test         |           11 |          0.328 |          0.532 |             0 |         0.453 |
| lightgbm     | wf           |           11 |          0.329 |          0.481 |             0 |         0.506 |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               52.335 |                   0 |              47.665 |               49.997 |               0.006 |              49.997 |
| catboost     | test         |           11 |               52.139 |                   0 |              47.861 |               56.63  |               0     |              43.37  |
| catboost     | wf           |           11 |               51.361 |                   0 |              48.639 |               45.528 |               0     |              54.472 |
| lightgbm     | val          |           11 |               52.335 |                   0 |              47.665 |               49.997 |               0.006 |              49.997 |
| lightgbm     | test         |           11 |               52.139 |                   0 |              47.861 |               55.463 |               0     |              44.537 |
| lightgbm     | wf           |           11 |               51.361 |                   0 |              48.639 |               46.204 |               0     |              53.796 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.20-0.29            |            1 |
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples       |      0.357 |     0.541 |      0.528 |         0 |
| Consumer Staples       |      0.351 |     0.537 |      0.516 |         0 |
| Consumer Staples       |      0.345 |     0.522 |      0.512 |         0 |
| Industrials            |      0.342 |     0.5   |      0.526 |         0 |
| Real Estate            |      0.339 |     0.534 |      0.483 |         0 |
| Industrials            |      0.339 |     0.504 |      0.513 |         0 |
| Industrials            |      0.338 |     0.506 |      0.508 |         0 |
| Health Care            |      0.338 |     0.518 |      0.495 |         0 |
| Consumer Staples       |      0.338 |     0.511 |      0.502 |         0 |
| Consumer Discretionary |      0.336 |     0.508 |      0.5   |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Energy                 |      0.293 |     0.424 |      0.454 |         0 |
| Energy                 |      0.301 |     0.459 |      0.443 |         0 |
| Communication Services |      0.312 |     0.503 |      0.432 |         0 |
| Utilities              |      0.312 |     0.556 |      0.38  |         0 |
| Energy                 |      0.313 |     0.448 |      0.492 |         0 |
| Utilities              |      0.315 |     0.578 |      0.366 |         0 |
| Energy                 |      0.318 |     0.468 |      0.485 |         0 |
| Materials              |      0.318 |     0.471 |      0.483 |         0 |
| Materials              |      0.32  |     0.46  |      0.499 |         0 |
| Materials              |      0.32  |     0.47  |      0.49  |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    0.8959 |        0.5002 |
| catboost     | test         |           11 |    1.0885 |        0.5018 |
| catboost     | wf           |           11 |    0.9981 |        0.5015 |
| lightgbm     | val          |           11 |    0.9156 |        0.4975 |
| lightgbm     | test         |           11 |    1.1079 |        0.5003 |
| lightgbm     | wf           |           11 |    1.0171 |        0.5018 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol           |   dir_acc |    mse |
|:-------------|:-----------------|----------:|-------:|
| lightgbm     | Consumer Staples |    0.5378 | 0.8921 |
| catboost     | Consumer Staples |    0.5335 | 0.8649 |
| lightgbm     | Consumer Staples |    0.5286 | 0.8953 |
| catboost     | Consumer Staples |    0.5239 | 0.8707 |
| lightgbm     | Utilities        |    0.5214 | 1.2291 |
| lightgbm     | Industrials      |    0.5193 | 0.9594 |
| lightgbm     | Consumer Staples |    0.5189 | 0.9136 |
| lightgbm     | Utilities        |    0.518  | 1.105  |
| lightgbm     | Industrials      |    0.5179 | 0.9187 |
| catboost     | Industrials      |    0.517  | 0.9328 |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Materials              |    0.4628 | 1.0135 |
| lightgbm     | Materials              |    0.4723 | 0.9889 |
| catboost     | Communication Services |    0.4742 | 0.9803 |
| lightgbm     | Information Technology |    0.4751 | 1.0781 |
| lightgbm     | Communication Services |    0.48   | 1.011  |
| lightgbm     | Materials              |    0.4835 | 0.9033 |
| catboost     | Materials              |    0.4842 | 0.8877 |
| catboost     | Information Technology |    0.486  | 1.0354 |
| lightgbm     | Information Technology |    0.4865 | 1.0493 |
| catboost     | Materials              |    0.4866 | 0.9469 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime           |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:-----------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull          |      0.325 |      0.444 |         0 |     0.53  | —           |     7.7 |      15   |            11 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol |      0.329 |      0.445 |         0 |     0.54  | —           |    19.1 |      25.7 |            11 |
|       2 | 2021-07-02  | 2021-12-30 | 🟢 Bull          |      0.322 |      0.473 |         0 |     0.492 | —           |     9.8 |      18.8 |            11 |
|       3 | 2022-07-05  | 2023-01-31 | 🔵 Range low vol |      0.337 |      0.488 |         0 |     0.524 | —           |     6.4 |      24.2 |            11 |
|       4 | 2023-08-03  | 2024-03-01 | 🟢 Bull          |      0.323 |      0.515 |         0 |     0.454 | —           |    14.3 |      14.9 |            11 |
