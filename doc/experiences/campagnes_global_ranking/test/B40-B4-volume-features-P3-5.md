# Diagnostic ML — Batch `model-factory-20260813230529-ca6dd8`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260813230529-ca6dd8`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : B40-B4-volume-features-P3-5
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0178
- **📈 IC IR (Stabilité)** : 1.13  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0127 H5=0.0150 H10=0.0302 H15=0.0220 H20=0.0258
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-13 23:05:29
- **Terminé le** : 2026-08-14 01:45:13
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function RMSE --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-short-score --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --include-volume-features --comment B40-B4-volume-features-P3-5
```

## 🌐 Global Ranking — Détails par Horizon

Modèle CatBoost — 400 symboles, 6 splits walk-forward, 259235 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |   IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits |
|:----------|----------:|--------:|----------------:|--------------:|------------:|
| H3        | 0.0146486 |    1.77 |       0.0126948 |           154 |           6 |
| H5        | 0.0178986 |    1.18 |       0.0150341 |           154 |           6 |
| H10       | 0.022004  |    1.26 |       0.0301992 |           154 |           6 |
| H15       | 0.017196  |    0.98 |       0.0219866 |           154 |           6 |
| H20       | 0.0170819 |    0.99 |       0.0258432 |           154 |           6 |


🏆 **Meilleur horizon : H10** — sélectionné par score composite 55% IC + 30% IR + 15% Positive Split  |  H3=0.8161  H5=0.7721  H10=0.8881  H15=0.7197  H20=0.7189
### Horizon H3

- **IC Rank** : 0.0146
- **Decile Spread** : 0.0127
- **Nb Features** : 154

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |    IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|-----------:|
|       1 | 2016-12-29 → 2018-12-24 | 2019-01-02 → 2019-06-26  |         149065 |        38302 | 0.00621748 |
|       2 | 2016-12-29 → 2019-12-24 | 2020-01-02 → 2020-06-25  |         229215 |        40105 | 0.025624   |
|       3 | 2016-12-29 → 2020-12-23 | 2020-12-31 → 2021-06-25  |         313071 |        41725 | 0.022912   |
|       4 | 2016-12-29 → 2021-12-23 | 2021-12-31 → 2022-06-27  |         400515 |        44291 | 0.0024816  |
|       5 | 2016-12-29 → 2022-12-23 | 2023-01-03 → 2023-06-28  |         494246 |        47206 | 0.0157597  |
|       6 | 2016-12-29 → 2023-12-27 | 2024-01-04 → 2024-06-28  |         591907 |        47606 | 0.0148967  |

- IC Moyen = 0.0146  |  IC Std = 0.0083  |  IC Min = 0.0025  |  IC Max = 0.0256

### Horizon H5

- **IC Rank** : 0.0179
- **Decile Spread** : 0.0150
- **Nb Features** : 154

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |     IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|------------:|
|       1 | 2016-12-29 → 2018-12-20 | 2019-01-02 → 2019-06-24  |         148443 |        37670 |  0.0103661  |
|       2 | 2016-12-29 → 2019-12-20 | 2020-01-02 → 2020-06-23  |         228561 |        39439 |  0.0452994  |
|       3 | 2016-12-29 → 2020-12-21 | 2020-12-31 → 2021-06-23  |         312391 |        41033 |  0.0151689  |
|       4 | 2016-12-29 → 2021-12-21 | 2021-12-31 → 2022-06-23  |         399799 |        43543 | -0.00473176 |
|       5 | 2016-12-29 → 2022-12-21 | 2023-01-03 → 2023-06-26  |         493474 |        46432 |  0.0163937  |
|       6 | 2016-12-29 → 2023-12-22 | 2024-01-04 → 2024-06-26  |         591127 |        46822 |  0.0248951  |

- IC Moyen = 0.0179  |  IC Std = 0.0152  |  IC Min = -0.0047  |  IC Max = 0.0453

### Horizon H10

- **IC Rank** : 0.0220
- **Decile Spread** : 0.0302
- **Nb Features** : 154

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |     IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 | -0.0069632  |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37774 |  0.0391243  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310691 |        39308 |  0.0362282  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398009 |        41676 |  0.00364647 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491544 |        44497 |  0.0261002  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589177 |        44867 |  0.033888   |

- IC Moyen = 0.0220  |  IC Std = 0.0175  |  IC Min = -0.0070  |  IC Max = 0.0391

### Horizon H15

- **IC Rank** : 0.0172
- **Decile Spread** : 0.0220
- **Nb Features** : 154

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |    IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|-----------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 | -0.0133276 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37774 |  0.0269139 |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310691 |        39308 |  0.044908  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398009 |        41676 |  0.0114842 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491544 |        44497 |  0.0209737 |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589177 |        44867 |  0.0122235 |

- IC Moyen = 0.0172  |  IC Std = 0.0176  |  IC Min = -0.0133  |  IC Max = 0.0449

### Horizon H20

- **IC Rank** : 0.0171
- **Decile Spread** : 0.0258
- **Nb Features** : 154

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |     IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 | -0.0111652  |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37774 |  0.0149055  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310691 |        39308 |  0.0431158  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398009 |        41676 |  0.00608169 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491544 |        44497 |  0.0309783  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589177 |        44867 |  0.0185754  |

- IC Moyen = 0.0171  |  IC Std = 0.0173  |  IC Min = -0.0112  |  IC Max = 0.0431


## 🧪 Backtest Stratégies — Global Rank (H10 + H5)

| Variante | Score relatif |
|----------|---------------|
| V1 — H10 seul | 🏆 référence |
| V2 — H10 + H5 rising | -10.6% |
| V3 — H10 + H5 < 0.35 | -34.4% |
| V4 — H10 + top 3 horizons ↑ (H10,H3,H5) | -20.6% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H10 seul, V2 = H10 + H5 rising, V3 = H10 + H5 < 0.35 (contrarian). V4 = H10 + top 3 horizons ↑ (H10,H3,H5).

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
|         3 |      0.331 |      0.495 |     0.497 |    0.5019 |
|         5 |      0.329 |      0.479 |     0.508 |    0.5009 |
|        10 |      0.328 |      0.477 |     0.508 |    0.5014 |
|        15 |      0.329 |      0.48  |     0.506 |    0.5031 |
|        20 |      0.328 |      0.478 |     0.505 |    0.5017 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.331 |          0.507 |             0 |         0.487 |
| catboost     | test         |           11 |          0.33  |          0.53  |             0 |         0.461 |
| catboost     | wf           |           11 |          0.329 |          0.481 |             0 |         0.505 |
| lightgbm     | val          |           11 |          0.333 |          0.509 |             0 |         0.489 |
| lightgbm     | test         |           11 |          0.331 |          0.522 |             0 |         0.471 |
| lightgbm     | wf           |           11 |          0.329 |          0.483 |             0 |         0.504 |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| catboost     | test         |           11 |               51.925 |                   0 |              48.075 |               54.914 |               0     |              45.086 |
| catboost     | wf           |           11 |               51.407 |                   0 |              48.593 |               46.197 |               0     |              53.803 |
| lightgbm     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| lightgbm     | test         |           11 |               51.925 |                   0 |              48.075 |               53.059 |               0     |              46.941 |
| lightgbm     | wf           |           11 |               51.407 |                   0 |              48.593 |               46.494 |               0     |              53.506 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol           |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples |      0.356 |     0.558 |      0.51  |         0 |
| Consumer Staples |      0.347 |     0.539 |      0.503 |         0 |
| Industrials      |      0.346 |     0.507 |      0.53  |         0 |
| Industrials      |      0.344 |     0.507 |      0.525 |         0 |
| Industrials      |      0.342 |     0.501 |      0.525 |         0 |
| Industrials      |      0.342 |     0.502 |      0.524 |         0 |
| Consumer Staples |      0.341 |     0.523 |      0.499 |         0 |
| Consumer Staples |      0.338 |     0.535 |      0.479 |         0 |
| Health Care      |      0.338 |     0.515 |      0.497 |         0 |
| Industrials      |      0.337 |     0.497 |      0.514 |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Energy                 |      0.307 |     0.449 |      0.473 |         0 |
| Energy                 |      0.309 |     0.458 |      0.47  |         0 |
| Materials              |      0.31  |     0.436 |      0.495 |         0 |
| Energy                 |      0.311 |     0.441 |      0.492 |         0 |
| Materials              |      0.312 |     0.461 |      0.474 |         0 |
| Communication Services |      0.314 |     0.503 |      0.439 |         0 |
| Materials              |      0.315 |     0.449 |      0.495 |         0 |
| Utilities              |      0.316 |     0.576 |      0.372 |         0 |
| Utilities              |      0.316 |     0.543 |      0.406 |         0 |
| Energy                 |      0.317 |     0.486 |      0.464 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    1.0607 |        0.4975 |
| catboost     | test         |           11 |    1.0841 |        0.4995 |
| catboost     | wf           |           11 |    1.0406 |        0.5019 |
| lightgbm     | val          |           11 |    1.0743 |        0.4994 |
| lightgbm     | test         |           11 |    1.1    |        0.5003 |
| lightgbm     | wf           |           11 |    1.0614 |        0.5017 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol           |   dir_acc |    mse |
|:-------------|:-----------------|----------:|-------:|
| lightgbm     | Consumer Staples |    0.5371 | 0.9264 |
| catboost     | Consumer Staples |    0.5355 | 0.906  |
| catboost     | Consumer Staples |    0.5268 | 0.9067 |
| lightgbm     | Consumer Staples |    0.5241 | 0.9249 |
| lightgbm     | Industrials      |    0.5199 | 1.0444 |
| lightgbm     | Utilities        |    0.5194 | 1.2817 |
| catboost     | Health Care      |    0.5183 | 1.0646 |
| lightgbm     | Industrials      |    0.5175 | 1.0069 |
| catboost     | Consumer Staples |    0.5157 | 0.9441 |
| lightgbm     | Industrials      |    0.5148 | 0.9788 |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Materials              |    0.4735 | 1.0982 |
| lightgbm     | Materials              |    0.474  | 1.0805 |
| catboost     | Communication Services |    0.4775 | 1.0273 |
| lightgbm     | Materials              |    0.4789 | 1.0391 |
| lightgbm     | Materials              |    0.4813 | 0.9478 |
| lightgbm     | Communication Services |    0.4828 | 1.0663 |
| lightgbm     | Information Technology |    0.4829 | 1.1465 |
| catboost     | Utilities              |    0.483  | 1.1585 |
| lightgbm     | Energy                 |    0.4839 | 0.9084 |
| catboost     | Communication Services |    0.4851 | 1.0188 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.324 |      0.442 |         0 |     0.53  | —           |     7.7 |      15   |            11 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.327 |      0.443 |         0 |     0.538 | —           |    19.1 |      25.7 |            11 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.326 |      0.478 |         0 |     0.499 | —           |     9.8 |      18.8 |            11 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.344 |      0.502 |         0 |     0.53  | —           |     0.1 |      24.9 |            11 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.328 |      0.515 |         0 |     0.47  | —           |     9   |      15.1 |            11 |
|       5 | 2024-09-03  | 2025-03-05 | 🟢 Bull           |      0.324 |      0.504 |         0 |     0.468 | —           |     5.6 |      17.4 |            11 |
