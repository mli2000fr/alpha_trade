# Diagnostic ML — Batch `model-factory-20260808075734-b8325d`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260808075734-b8325d`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : F2 SPY + Sentiment
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0186
- **📈 IC IR (Stabilité)** : 1.02  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0086 H5=0.0184 H10=0.0234 H15=0.0275 H20=0.0297
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-08 07:57:35
- **Terminé le** : 2026-08-08 09:33:55
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-sentiment --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "F2 SPY + Sentiment"
```

## 🏆 Sélection du champion

✅ **Tout va bien** — 11 champions sélectionnés automatiquement sur 11 symboles.

### 📊 Champions par modèle

| model_name   |   nb_symbols |
|:-------------|-------------:|
| catboost     |            8 |
| lightgbm     |            3 |

## 🌐 Global Ranking — Détails par Horizon

Modèle Catboost — 400 symboles, 6 splits walk-forward, 259239 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |   IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits |
|:----------|----------:|--------:|----------------:|--------------:|------------:|
| H3        | 0.0102789 |    1.25 |      0.00863555 |           143 |           6 |
| H5        | 0.0191216 |    1.27 |      0.0183503  |           143 |           6 |
| H10       | 0.0229683 |    1.2  |      0.023405   |           143 |           6 |
| H15       | 0.0184623 |    0.99 |      0.0275267  |           143 |           6 |
| H20       | 0.0220407 |    0.95 |      0.0296987  |           143 |           6 |

### Horizon H3

- **IC Rank** : 0.0103
- **Decile Spread** : 0.0086
- **Nb Features** : 143

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
- **Nb Features** : 143

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
- **Nb Features** : 143

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
- **Nb Features** : 143

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
- **Nb Features** : 143

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
|         3 |      0.33  |      0.489 |     0.503 |    0.5019 |
|         5 |      0.329 |      0.475 |     0.512 |    0.5008 |
|        10 |      0.329 |      0.474 |     0.512 |    0.5019 |
|        15 |      0.329 |      0.475 |     0.512 |    0.5022 |
|        20 |      0.327 |      0.473 |     0.509 |    0.4998 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.332 |          0.508 |             0 |         0.489 |
| catboost     | test         |           11 |          0.331 |          0.523 |             0 |         0.47  |
| catboost     | wf           |           11 |          0.328 |          0.475 |             0 |         0.51  |
| lightgbm     | val          |           11 |          0.331 |          0.506 |             0 |         0.487 |
| lightgbm     | test         |           11 |          0.329 |          0.512 |             0 |         0.475 |
| lightgbm     | wf           |           11 |          0.329 |          0.479 |             0 |         0.509 |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| catboost     | test         |           11 |               51.925 |                   0 |              48.075 |               53.414 |               0     |              46.586 |
| catboost     | wf           |           11 |               51.407 |                   0 |              48.593 |               45.205 |               0     |              54.795 |
| lightgbm     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| lightgbm     | test         |           11 |               51.925 |                   0 |              48.075 |               51.693 |               0     |              48.307 |
| lightgbm     | wf           |           11 |               51.407 |                   0 |              48.593 |               45.702 |               0     |              54.298 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.20-0.29            |            1 |
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol           |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples |      0.356 |     0.556 |      0.512 |         0 |
| Consumer Staples |      0.353 |     0.558 |      0.501 |         0 |
| Consumer Staples |      0.351 |     0.556 |      0.496 |         0 |
| Health Care      |      0.343 |     0.529 |      0.499 |         0 |
| Consumer Staples |      0.341 |     0.559 |      0.463 |         0 |
| Health Care      |      0.34  |     0.522 |      0.499 |         0 |
| Health Care      |      0.338 |     0.525 |      0.489 |         0 |
| Industrials      |      0.337 |     0.508 |      0.503 |         0 |
| Industrials      |      0.337 |     0.514 |      0.496 |         0 |
| Industrials      |      0.336 |     0.502 |      0.506 |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Energy                 |      0.298 |     0.443 |      0.45  |         0 |
| Energy                 |      0.299 |     0.45  |      0.449 |         0 |
| Energy                 |      0.311 |     0.441 |      0.492 |         0 |
| Utilities              |      0.314 |     0.538 |      0.405 |         0 |
| Energy                 |      0.314 |     0.478 |      0.465 |         0 |
| Utilities              |      0.317 |     0.555 |      0.397 |         0 |
| Utilities              |      0.319 |     0.529 |      0.426 |         0 |
| Utilities              |      0.321 |     0.554 |      0.409 |         0 |
| Materials              |      0.321 |     0.474 |      0.489 |         0 |
| Communication Services |      0.321 |     0.512 |      0.452 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    1.0655 |        0.4988 |
| catboost     | test         |           11 |    1.0873 |        0.4993 |
| catboost     | wf           |           11 |    1.0436 |        0.5011 |
| lightgbm     | val          |           11 |    1.0799 |        0.4968 |
| lightgbm     | test         |           11 |    1.1078 |        0.4959 |
| lightgbm     | wf           |           11 |    1.062  |        0.5015 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol           |   dir_acc |    mse |
|:-------------|:-----------------|----------:|-------:|
| lightgbm     | Consumer Staples |    0.5453 | 0.909  |
| catboost     | Consumer Staples |    0.5377 | 0.8914 |
| lightgbm     | Consumer Staples |    0.5351 | 0.9144 |
| catboost     | Consumer Staples |    0.5344 | 0.8952 |
| catboost     | Consumer Staples |    0.5298 | 0.9145 |
| lightgbm     | Consumer Staples |    0.5257 | 0.9304 |
| lightgbm     | Industrials      |    0.5172 | 1.0451 |
| catboost     | Consumer Staples |    0.5166 | 0.9386 |
| catboost     | Health Care      |    0.5156 | 1.0554 |
| lightgbm     | Industrials      |    0.515  | 1.0123 |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Materials              |    0.4682 | 1.1084 |
| catboost     | Communication Services |    0.4705 | 1.0542 |
| catboost     | Communication Services |    0.4812 | 1.0213 |
| lightgbm     | Materials              |    0.4833 | 1.0238 |
| catboost     | Communication Services |    0.4835 | 1.008  |
| lightgbm     | Materials              |    0.4849 | 1.0819 |
| catboost     | Utilities              |    0.485  | 1.3262 |
| lightgbm     | Energy                 |    0.4856 | 1.0211 |
| lightgbm     | Communication Services |    0.4862 | 1.0779 |
| lightgbm     | Materials              |    0.4866 | 0.9438 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.32  |      0.439 |         0 |     0.522 | —           |     7.7 |      15   |            11 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.332 |      0.45  |         0 |     0.544 | —           |    19.1 |      25.7 |            11 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.324 |      0.459 |         0 |     0.513 | —           |     9.8 |      18.8 |            11 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.334 |      0.483 |         0 |     0.519 | —           |     0.1 |      24.9 |            11 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.321 |      0.495 |         0 |     0.467 | —           |     9   |      15.1 |            11 |
|       5 | 2024-09-03  | 2025-03-05 | 🟢 Bull           |      0.328 |      0.504 |         0 |     0.481 | —           |     5.6 |      17.4 |            11 |
