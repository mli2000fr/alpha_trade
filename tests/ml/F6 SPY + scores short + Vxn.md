# Diagnostic ML — Batch `model-factory-20260808175132-2ebf25`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260808175132-2ebf25`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : F6 SPY + scores short + Vxn
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0186
- **📈 IC IR (Stabilité)** : 1.02  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0086 H5=0.0184 H10=0.0234 H15=0.0275 H20=0.0297
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-08 17:51:32
- **Terminé le** : 2026-08-08 19:24:42
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-short-score --include-macro-vxn --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "F6 SPY + scores short + Vxn"
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

| Horizon   |   IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits |
|:----------|----------:|--------:|----------------:|--------------:|------------:|
| H3        | 0.0102789 |    1.25 |      0.00863555 |           144 |           6 |
| H5        | 0.0191216 |    1.27 |      0.0183503  |           144 |           6 |
| H10       | 0.0229683 |    1.2  |      0.023405   |           144 |           6 |
| H15       | 0.0184623 |    0.99 |      0.0275267  |           144 |           6 |
| H20       | 0.0220407 |    0.95 |      0.0296987  |           144 |           6 |

### Horizon H3

- **IC Rank** : 0.0103
- **Decile Spread** : 0.0086
- **Nb Features** : 144

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |     IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|------------:|
|       1 | 2016-12-29 → 2018-12-24 | 2019-01-02 → 2019-06-26  |         149065 |        38302 | 0.00558812  |
|       2 | 2016-12-29 → 2019-12-24 | 2020-01-02 → 2020-06-25  |         229215 |        40109 | 0.0229955   |
|       3 | 2016-12-29 → 2020-12-23 | 2020-12-31 → 2021-06-25  |         313075 |        41725 | 0.0199036   |
|       4 | 2016-12-29 → 2021-12-23 | 2021-12-31 → 2022-06-27  |         400519 |        44291 | 0.000761176 |
|       5 | 2016-12-29 → 2022-12-23 | 2023-01-03 → 2023-06-28  |         494250 |        47206 | 0.00815045  |
|       6 | 2016-12-29 → 2023-12-27 | 2024-01-04 → 2024-06-28  |         591911 |        47606 | 0.00427445  |

- IC Moyen = 0.0103  |  IC Std = 0.0082  |  IC Min = 0.0008  |  IC Max = 0.0230

### Horizon H5

- **IC Rank** : 0.0191
- **Decile Spread** : 0.0184
- **Nb Features** : 144

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |     IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|------------:|
|       1 | 2016-12-29 → 2018-12-20 | 2019-01-02 → 2019-06-24  |         148443 |        37670 |  0.00879692 |
|       2 | 2016-12-29 → 2019-12-20 | 2020-01-02 → 2020-06-23  |         228561 |        39443 |  0.0438674  |
|       3 | 2016-12-29 → 2020-12-21 | 2020-12-31 → 2021-06-23  |         312395 |        41033 |  0.0281558  |
|       4 | 2016-12-29 → 2021-12-21 | 2021-12-31 → 2022-06-23  |         399803 |        43543 | -0.00406059 |
|       5 | 2016-12-29 → 2022-12-21 | 2023-01-03 → 2023-06-26  |         493478 |        46432 |  0.0155898  |
|       6 | 2016-12-29 → 2023-12-22 | 2024-01-04 → 2024-06-26  |         591131 |        46822 |  0.0223803  |

- IC Moyen = 0.0191  |  IC Std = 0.0151  |  IC Min = -0.0041  |  IC Max = 0.0439

### Horizon H10

- **IC Rank** : 0.0230
- **Decile Spread** : 0.0234
- **Nb Features** : 144

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |     IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |  0.00375207 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |  0.0512631  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |  0.0338033  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 | -0.00571104 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |  0.0325956  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |  0.0221069  |

- IC Moyen = 0.0230  |  IC Std = 0.0192  |  IC Min = -0.0057  |  IC Max = 0.0513

### Horizon H15

- **IC Rank** : 0.0185
- **Decile Spread** : 0.0275
- **Nb Features** : 144

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |     IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 | -0.00773098 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |  0.0284241  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |  0.0377571  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 | -0.00295491 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |  0.039512   |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |  0.0157667  |

- IC Moyen = 0.0185  |  IC Std = 0.0186  |  IC Min = -0.0077  |  IC Max = 0.0395

### Horizon H20

- **IC Rank** : 0.0220
- **Decile Spread** : 0.0297
- **Nb Features** : 144

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |     IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 | -0.00381792 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |  0.0317539  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |  0.0581624  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 | -0.00114221 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |  0.0412373  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |  0.00605075 |

- IC Moyen = 0.0220  |  IC Std = 0.0232  |  IC Min = -0.0038  |  IC Max = 0.0582


## 🧪 Backtest Stratégies — Global Rank

| Variante | Score relatif |
|----------|---------------|
| V1 — H20 seul | 🏆 référence |
| V2 — H20 + H5 rising | -9.3% |
| V3 — H20 + H5 < 0.35 | -28.8% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H20 seul, V2 = H20 + H5 rising, V3 = H20 + H5 < 0.35 (contrarian).

---

## 🔵 Per-Symbol / Per-Sector — Métriques d'entraînement

## 📊 Métriques par Horizon (WF)

|   Horizon |   F1 macro |   F1 short |   F1 long |   Dir Acc |
|----------:|-----------:|-----------:|----------:|----------:|
|         3 |      0.331 |      0.491 |     0.502 |    0.5021 |
|         5 |      0.329 |      0.477 |     0.511 |    0.501  |
|        10 |      0.328 |      0.473 |     0.512 |    0.5017 |
|        15 |      0.329 |      0.475 |     0.512 |    0.5026 |
|        20 |      0.328 |      0.474 |     0.51  |    0.5012 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.331 |          0.507 |             0 |         0.487 |
| catboost     | test         |           11 |          0.33  |          0.52  |             0 |         0.47  |
| catboost     | wf           |           11 |          0.329 |          0.477 |             0 |         0.51  |
| lightgbm     | val          |           11 |          0.331 |          0.506 |             0 |         0.486 |
| lightgbm     | test         |           11 |          0.329 |          0.512 |             0 |         0.474 |
| lightgbm     | wf           |           11 |          0.329 |          0.479 |             0 |         0.509 |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| catboost     | test         |           11 |               51.925 |                   0 |              48.075 |               53.044 |               0     |              46.956 |
| catboost     | wf           |           11 |               51.407 |                   0 |              48.593 |               45.426 |               0     |              54.574 |
| lightgbm     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.005 |              49.998 |
| lightgbm     | test         |           11 |               51.925 |                   0 |              48.075 |               51.727 |               0     |              48.273 |
| lightgbm     | wf           |           11 |               51.407 |                   0 |              48.593 |               45.709 |               0     |              54.291 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.20-0.29            |            1 |
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol           |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples |      0.361 |     0.546 |      0.536 |         0 |
| Consumer Staples |      0.357 |     0.549 |      0.523 |         0 |
| Consumer Staples |      0.346 |     0.531 |      0.506 |         0 |
| Health Care      |      0.341 |     0.529 |      0.495 |         0 |
| Health Care      |      0.339 |     0.531 |      0.485 |         0 |
| Industrials      |      0.338 |     0.508 |      0.506 |         0 |
| Consumer Staples |      0.338 |     0.524 |      0.49  |         0 |
| Health Care      |      0.338 |     0.531 |      0.482 |         0 |
| Financials       |      0.337 |     0.514 |      0.496 |         0 |
| Financials       |      0.336 |     0.526 |      0.482 |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol      |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:------------|-----------:|----------:|-----------:|----------:|
| Energy      |      0.298 |     0.456 |      0.437 |         0 |
| Energy      |      0.303 |     0.44  |      0.468 |         0 |
| Materials   |      0.307 |     0.465 |      0.455 |         0 |
| Energy      |      0.314 |     0.461 |      0.481 |         0 |
| Materials   |      0.315 |     0.464 |      0.48  |         0 |
| Energy      |      0.316 |     0.469 |      0.478 |         0 |
| Utilities   |      0.317 |     0.548 |      0.403 |         0 |
| Materials   |      0.319 |     0.474 |      0.481 |         0 |
| Real Estate |      0.319 |     0.505 |      0.452 |         0 |
| Utilities   |      0.32  |     0.525 |      0.435 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    1.0676 |        0.4975 |
| catboost     | test         |           11 |    1.087  |        0.4977 |
| catboost     | wf           |           11 |    1.0425 |        0.5019 |
| lightgbm     | val          |           11 |    1.0817 |        0.4962 |
| lightgbm     | test         |           11 |    1.1076 |        0.496  |
| lightgbm     | wf           |           11 |    1.063  |        0.5015 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol           |   dir_acc |    mse |
|:-------------|:-----------------|----------:|-------:|
| catboost     | Consumer Staples |    0.5443 | 0.8903 |
| lightgbm     | Consumer Staples |    0.5421 | 0.9194 |
| lightgbm     | Consumer Staples |    0.5387 | 0.91   |
| catboost     | Consumer Staples |    0.5347 | 0.8962 |
| catboost     | Consumer Staples |    0.5303 | 0.9185 |
| lightgbm     | Consumer Staples |    0.5218 | 0.9306 |
| catboost     | Consumer Staples |    0.5212 | 0.9391 |
| lightgbm     | Industrials      |    0.5161 | 1.0445 |
| lightgbm     | Industrials      |    0.5153 | 1.0153 |
| catboost     | Health Care      |    0.5133 | 1.056  |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Materials              |    0.4629 | 1.1109 |
| catboost     | Communication Services |    0.4715 | 1.0519 |
| catboost     | Communication Services |    0.4758 | 1.0247 |
| lightgbm     | Materials              |    0.4782 | 1.0876 |
| catboost     | Communication Services |    0.4846 | 1.0058 |
| lightgbm     | Energy                 |    0.4851 | 0.9752 |
| lightgbm     | Communication Services |    0.4854 | 1.0783 |
| lightgbm     | Materials              |    0.4859 | 0.9465 |
| lightgbm     | Materials              |    0.4879 | 1.0279 |
| lightgbm     | Energy                 |    0.4887 | 0.9064 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.32  |      0.44  |         0 |     0.519 | —           |     7.7 |      15   |            11 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.331 |      0.449 |         0 |     0.544 | —           |    19.1 |      25.7 |            11 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.33  |      0.462 |         0 |     0.528 | —           |     9.8 |      18.8 |            11 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.338 |      0.497 |         0 |     0.517 | —           |     0.1 |      24.9 |            11 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.321 |      0.493 |         0 |     0.471 | —           |     9   |      15.1 |            11 |
|       5 | 2024-09-03  | 2025-03-05 | 🟢 Bull           |      0.328 |      0.504 |         0 |     0.481 | —           |     5.6 |      17.4 |            11 |
