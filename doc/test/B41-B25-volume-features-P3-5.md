# Diagnostic ML — Batch `model-factory-20260813231851-bb2e76`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260813231851-bb2e76`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : B41-B25-volume-features-P3-5
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0260
- **📈 IC IR (Stabilité)** : 1.55  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0198 H5=0.0288 H10=0.0313 H15=0.0359 H20=0.0312
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-13 23:18:52
- **Terminé le** : 2026-08-14 03:07:45
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-short-score --include-factors --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --include-volume-features --comment B41-B25-volume-features-P3-5
```

## 🌐 Global Ranking — Détails par Horizon

Modèle CatBoost — 400 symboles, 6 splits walk-forward, 259235 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |   IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits |
|:----------|----------:|--------:|----------------:|--------------:|------------:|
| H3        | 0.0220032 |    1.36 |       0.0198055 |           155 |           6 |
| H5        | 0.0241618 |    1.22 |       0.0287828 |           155 |           6 |
| H10       | 0.0265003 |    1.61 |       0.0313278 |           155 |           6 |
| H15       | 0.0293707 |    1.94 |       0.0358904 |           155 |           6 |
| H20       | 0.0279161 |    1.89 |       0.0312075 |           155 |           6 |


🏆 **Meilleur horizon : H15** — sélectionné par score composite 55% IC + 30% IR + 15% Positive Split  |  H3=0.7466  H5=0.7652  H10=0.8953  H15=1.0000  H20=0.9638
### Horizon H3

- **IC Rank** : 0.0220
- **Decile Spread** : 0.0198
- **Nb Features** : 155

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |     IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|------------:|
|       1 | 2016-12-29 → 2018-12-24 | 2019-01-02 → 2019-06-26  |         149065 |        38302 |  0.014536   |
|       2 | 2016-12-29 → 2019-12-24 | 2020-01-02 → 2020-06-25  |         229215 |        40105 |  0.0402745  |
|       3 | 2016-12-29 → 2020-12-23 | 2020-12-31 → 2021-06-25  |         313071 |        41725 |  0.0176662  |
|       4 | 2016-12-29 → 2021-12-23 | 2021-12-31 → 2022-06-27  |         400515 |        44291 | -0.00513642 |
|       5 | 2016-12-29 → 2022-12-23 | 2023-01-03 → 2023-06-28  |         494246 |        47206 |  0.0219481  |
|       6 | 2016-12-29 → 2023-12-27 | 2024-01-04 → 2024-06-28  |         591907 |        47606 |  0.0427305  |

- IC Moyen = 0.0220  |  IC Std = 0.0162  |  IC Min = -0.0051  |  IC Max = 0.0427

### Horizon H5

- **IC Rank** : 0.0242
- **Decile Spread** : 0.0288
- **Nb Features** : 155

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |     IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|------------:|
|       1 | 2016-12-29 → 2018-12-20 | 2019-01-02 → 2019-06-24  |         148443 |        37670 |  0.0314971  |
|       2 | 2016-12-29 → 2019-12-20 | 2020-01-02 → 2020-06-23  |         228561 |        39439 |  0.0459173  |
|       3 | 2016-12-29 → 2020-12-21 | 2020-12-31 → 2021-06-23  |         312391 |        41033 |  0.00545264 |
|       4 | 2016-12-29 → 2021-12-21 | 2021-12-31 → 2022-06-23  |         399799 |        43543 | -0.00967342 |
|       5 | 2016-12-29 → 2022-12-21 | 2023-01-03 → 2023-06-26  |         493474 |        46432 |  0.0300587  |
|       6 | 2016-12-29 → 2023-12-22 | 2024-01-04 → 2024-06-26  |         591127 |        46822 |  0.0417186  |

- IC Moyen = 0.0242  |  IC Std = 0.0199  |  IC Min = -0.0097  |  IC Max = 0.0459

### Horizon H10

- **IC Rank** : 0.0265
- **Decile Spread** : 0.0313
- **Nb Features** : 155

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |    IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|-----------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 | 0.034044   |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37774 | 0.0329281  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310691 |        39308 | 0.00310825 |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398009 |        41676 | 0.00465262 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491544 |        44497 | 0.0405776  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589177 |        44867 | 0.0436911  |

- IC Moyen = 0.0265  |  IC Std = 0.0164  |  IC Min = 0.0031  |  IC Max = 0.0437

### Horizon H15

- **IC Rank** : 0.0294
- **Decile Spread** : 0.0359
- **Nb Features** : 155

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |    IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|-----------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 | 0.0306056  |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37774 | 0.031866   |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310691 |        39308 | 0.00492026 |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398009 |        41676 | 0.0159675  |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491544 |        44497 | 0.0456613  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589177 |        44867 | 0.0472034  |

- IC Moyen = 0.0294  |  IC Std = 0.0151  |  IC Min = 0.0049  |  IC Max = 0.0472

### Horizon H20

- **IC Rank** : 0.0279
- **Decile Spread** : 0.0312
- **Nb Features** : 155

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |    IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|-----------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 | 0.0254683  |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37774 | 0.0243031  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310691 |        39308 | 0.00236031 |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398009 |        41676 | 0.0241997  |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491544 |        44497 | 0.0468888  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589177 |        44867 | 0.0442764  |

- IC Moyen = 0.0279  |  IC Std = 0.0148  |  IC Min = 0.0024  |  IC Max = 0.0469


## 🧪 Backtest Stratégies — Global Rank (H15 + H5)

| Variante | Score relatif |
|----------|---------------|
| V1 — H15 seul | 🏆 référence |
| V2 — H15 + H5 rising | -11.6% |
| V3 — H15 + H5 < 0.35 | -55.3% |
| V4 — H15 + top 3 horizons ↑ (H15,H20,H10) | -26.7% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H15 seul, V2 = H15 + H5 rising, V3 = H15 + H5 < 0.35 (contrarian). V4 = H15 + top 3 horizons ↑ (H15,H20,H10).

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
|         3 |      0.33  |      0.491 |     0.499 |    0.5013 |
|         5 |      0.329 |      0.48  |     0.508 |    0.5012 |
|        10 |      0.329 |      0.48  |     0.506 |    0.5023 |
|        15 |      0.329 |      0.481 |     0.506 |    0.5035 |
|        20 |      0.326 |      0.477 |     0.502 |    0.4996 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.332 |          0.508 |             0 |         0.488 |
| catboost     | test         |           11 |          0.33  |          0.53  |             0 |         0.46  |
| catboost     | wf           |           11 |          0.328 |          0.48  |             0 |         0.505 |
| lightgbm     | val          |           11 |          0.333 |          0.509 |             0 |         0.489 |
| lightgbm     | test         |           11 |          0.33  |          0.52  |             0 |         0.471 |
| lightgbm     | wf           |           11 |          0.329 |          0.484 |             0 |         0.503 |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| catboost     | test         |           11 |               51.925 |                   0 |              48.075 |               55.052 |               0     |              44.948 |
| catboost     | wf           |           11 |               51.407 |                   0 |              48.593 |               46.184 |               0     |              53.816 |
| lightgbm     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| lightgbm     | test         |           11 |               51.925 |                   0 |              48.075 |               52.869 |               0     |              47.131 |
| lightgbm     | wf           |           11 |               51.407 |                   0 |              48.593 |               46.732 |               0     |              53.268 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.20-0.29            |            1 |
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol           |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples |      0.354 |     0.547 |      0.515 |         0 |
| Consumer Staples |      0.351 |     0.544 |      0.51  |         0 |
| Industrials      |      0.345 |     0.503 |      0.532 |         0 |
| Industrials      |      0.345 |     0.506 |      0.529 |         0 |
| Consumer Staples |      0.344 |     0.526 |      0.505 |         0 |
| Industrials      |      0.34  |     0.498 |      0.521 |         0 |
| Industrials      |      0.339 |     0.494 |      0.522 |         0 |
| Health Care      |      0.339 |     0.516 |      0.5   |         0 |
| Consumer Staples |      0.338 |     0.529 |      0.484 |         0 |
| Industrials      |      0.337 |     0.499 |      0.513 |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Energy                 |      0.291 |     0.42  |      0.453 |         0 |
| Energy                 |      0.296 |     0.436 |      0.451 |         0 |
| Materials              |      0.308 |     0.454 |      0.471 |         0 |
| Energy                 |      0.311 |     0.438 |      0.494 |         0 |
| Communication Services |      0.311 |     0.49  |      0.443 |         0 |
| Materials              |      0.313 |     0.456 |      0.482 |         0 |
| Energy                 |      0.313 |     0.457 |      0.483 |         0 |
| Utilities              |      0.313 |     0.555 |      0.385 |         0 |
| Materials              |      0.319 |     0.46  |      0.496 |         0 |
| Materials              |      0.32  |     0.456 |      0.503 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    1.061  |        0.4985 |
| catboost     | test         |           11 |    1.0852 |        0.4991 |
| catboost     | wf           |           11 |    1.0406 |        0.5013 |
| lightgbm     | val          |           11 |    1.0725 |        0.4994 |
| lightgbm     | test         |           11 |    1.1016 |        0.4994 |
| lightgbm     | wf           |           11 |    1.0615 |        0.5018 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol           |   dir_acc |    mse |
|:-------------|:-----------------|----------:|-------:|
| lightgbm     | Consumer Staples |    0.5326 | 0.933  |
| catboost     | Consumer Staples |    0.5293 | 0.9046 |
| lightgbm     | Consumer Staples |    0.5291 | 0.923  |
| catboost     | Consumer Staples |    0.5266 | 0.909  |
| lightgbm     | Utilities        |    0.5234 | 1.2699 |
| lightgbm     | Industrials      |    0.5192 | 1.0082 |
| lightgbm     | Industrials      |    0.5189 | 1.0493 |
| lightgbm     | Consumer Staples |    0.518  | 0.9421 |
| catboost     | Consumer Staples |    0.5134 | 0.9417 |
| catboost     | Health Care      |    0.5123 | 1.0579 |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Materials              |    0.4693 | 1.0943 |
| catboost     | Communication Services |    0.4728 | 1.0318 |
| lightgbm     | Materials              |    0.477  | 1.0836 |
| lightgbm     | Communication Services |    0.481  | 1.0722 |
| lightgbm     | Materials              |    0.4861 | 0.9517 |
| lightgbm     | Energy                 |    0.4862 | 0.9062 |
| lightgbm     | Energy                 |    0.4868 | 0.9978 |
| lightgbm     | Information Technology |    0.4869 | 1.1374 |
| lightgbm     | Materials              |    0.4869 | 1.0324 |
| catboost     | Communication Services |    0.4872 | 1.0084 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.325 |      0.444 |         0 |     0.53  | —           |     7.7 |      15   |            11 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.329 |      0.445 |         0 |     0.54  | —           |    19.1 |      25.7 |            11 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.322 |      0.473 |         0 |     0.492 | —           |     9.8 |      18.8 |            11 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.339 |      0.49  |         0 |     0.528 | —           |     0.1 |      24.9 |            11 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.324 |      0.512 |         0 |     0.461 | —           |     9   |      15.1 |            11 |
|       5 | 2024-09-03  | 2025-03-05 | 🟢 Bull           |      0.326 |      0.506 |         0 |     0.472 | —           |     5.6 |      17.4 |            11 |
