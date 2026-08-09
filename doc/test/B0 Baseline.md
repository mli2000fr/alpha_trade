# Diagnostic ML — Batch `model-factory-20260809091632-a574c7`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260809091632-a574c7`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : B0 Baseline
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0186
- **📈 IC IR (Stabilité)** : 1.02  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0086 H5=0.0184 H10=0.0234 H15=0.0275 H20=0.0297
- **🏆 Champion Global** : catboost (H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — score composite 55% IC + 30% IR + 15% positifs
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-09 09:16:32
- **Terminé le** : 2026-08-09 10:22:42
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --no-include-score-components --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B0 Baseline"
```

## 🌐 Global Ranking — Détails par Horizon

Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symboles, 6 splits walk-forward, 259239 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |   IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits | 🏆 Champion   |   Score |   IC catboost |   IR catboost |   IC lightgbm |   IR lightgbm |
|:----------|----------:|--------:|----------------:|--------------:|------------:|:--------------|--------:|--------------:|--------------:|--------------:|--------------:|
| H3        | 0.0102789 |    1.25 |      0.00863555 |           143 |           6 | catboost      |   1     |        0.0103 |          1.25 |        0.0086 |          0.55 |
| H5        | 0.0191216 |    1.27 |      0.0183503  |           143 |           6 | catboost      |   0.975 |        0.0191 |          1.27 |        0.0113 |          0.82 |
| H10       | 0.0229683 |    1.2  |      0.023405   |           143 |           6 | catboost      |   0.975 |        0.023  |          1.2  |        0.0041 |          0.18 |
| H15       | 0.0184623 |    0.99 |      0.0275267  |           143 |           6 | catboost      |   0.95  |        0.0185 |          0.99 |        0.0139 |          0.37 |
| H20       | 0.0220407 |    0.95 |      0.0296987  |           143 |           6 | catboost      |   0.95  |        0.022  |          0.95 |        0.009  |          0.25 |


🏆 **Meilleur horizon : H10** — sélectionné par score composite 55% IC + 30% IR + 15% Positive Split
### Horizon H3 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0103 | IR = 1.25 | Score composite = 1.000 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0103
- **Decile Spread** : 0.0086
- **Nb Features** : 143

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-24 | 2019-01-02 → 2019-06-26  |         149065 |        38302 |          0.00558812  |    0.014983   |   0.00558812  |
|       2 | 2016-12-29 → 2019-12-24 | 2020-01-02 → 2020-06-25  |         229215 |        40109 |          0.0229955   |    0.030124   |   0.0229955   |
|       3 | 2016-12-29 → 2020-12-23 | 2020-12-31 → 2021-06-25  |         313075 |        41725 |          0.0199036   |    0.00336977 |   0.0199036   |
|       4 | 2016-12-29 → 2021-12-23 | 2021-12-31 → 2022-06-27  |         400519 |        44291 |          0.000761176 |   -0.0215768  |   0.000761176 |
|       5 | 2016-12-29 → 2022-12-23 | 2023-01-03 → 2023-06-28  |         494250 |        47206 |          0.00815045  |    0.0101298  |   0.00815045  |
|       6 | 2016-12-29 → 2023-12-27 | 2024-01-04 → 2024-06-28  |         591911 |        47606 |          0.00427445  |    0.0147199  |   0.00427445  |

- IC Moyen = 0.0103  |  IC Std = 0.0082  |  IC Min = 0.0008  |  IC Max = 0.0230

### Horizon H5 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0191 | IR = 1.27 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0191
- **Decile Spread** : 0.0184
- **Nb Features** : 143

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-20 | 2019-01-02 → 2019-06-24  |         148443 |        37670 |           0.00879692 |    0.0228208  |    0.00879692 |
|       2 | 2016-12-29 → 2019-12-20 | 2020-01-02 → 2020-06-23  |         228561 |        39443 |           0.0438674  |    0.0356974  |    0.0438674  |
|       3 | 2016-12-29 → 2020-12-21 | 2020-12-31 → 2021-06-23  |         312395 |        41033 |           0.0281558  |    0.00253557 |    0.0281558  |
|       4 | 2016-12-29 → 2021-12-21 | 2021-12-31 → 2022-06-23  |         399803 |        43543 |          -0.00406059 |    0.00655876 |   -0.00406059 |
|       5 | 2016-12-29 → 2022-12-21 | 2023-01-03 → 2023-06-26  |         493478 |        46432 |           0.0155898  |    0.0062351  |    0.0155898  |
|       6 | 2016-12-29 → 2023-12-22 | 2024-01-04 → 2024-06-26  |         591131 |        46822 |           0.0223803  |   -0.00601925 |    0.0223803  |

- IC Moyen = 0.0191  |  IC Std = 0.0151  |  IC Min = -0.0041  |  IC Max = 0.0439

### Horizon H10 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0230 | IR = 1.20 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0230
- **Decile Spread** : 0.0234
- **Nb Features** : 143

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |           0.00375207 |    0.00834472 |    0.00375207 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |           0.0512631  |    0.0534126  |    0.0512631  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |           0.0338033  |   -0.0108208  |    0.0338033  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |          -0.00571104 |   -0.0118119  |   -0.00571104 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |           0.0325956  |   -0.00733258 |    0.0325956  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |           0.0221069  |   -0.00690954 |    0.0221069  |

- IC Moyen = 0.0230  |  IC Std = 0.0192  |  IC Min = -0.0057  |  IC Max = 0.0513

### Horizon H15 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0185 | IR = 0.99 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0185
- **Decile Spread** : 0.0275
- **Nb Features** : 143

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |          -0.00773098 |    0.0299015  |   -0.00773098 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |           0.0284241  |    0.0697309  |    0.0284241  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |           0.0377571  |    0.0210557  |    0.0377571  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |          -0.00295491 |    0.025089   |   -0.00295491 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |           0.039512   |   -0.00899758 |    0.039512   |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |           0.0157667  |   -0.0530822  |    0.0157667  |

- IC Moyen = 0.0185  |  IC Std = 0.0186  |  IC Min = -0.0077  |  IC Max = 0.0395

### Horizon H20 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0220 | IR = 0.95 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0220
- **Decile Spread** : 0.0297
- **Nb Features** : 143

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |          -0.00381792 |    0.0372622  |   -0.00381792 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |           0.0317539  |    0.0719797  |    0.0317539  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |           0.0581624  |   -0.0308151  |    0.0581624  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |          -0.00114221 |    0.00177681 |   -0.00114221 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |           0.0412373  |   -0.00123987 |    0.0412373  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |           0.00605075 |   -0.0252401  |    0.00605075 |

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
|         3 |      0.331 |      0.49  |     0.504 |    0.5023 |
|         5 |      0.329 |      0.476 |     0.511 |    0.5005 |
|        10 |      0.329 |      0.477 |     0.51  |    0.5025 |
|        15 |      0.328 |      0.474 |     0.51  |    0.5004 |
|        20 |      0.327 |      0.474 |     0.506 |    0.4986 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.331 |          0.505 |             0 |         0.486 |
| catboost     | test         |           11 |          0.328 |          0.523 |             0 |         0.461 |
| catboost     | wf           |           11 |          0.328 |          0.477 |             0 |         0.509 |
| lightgbm     | val          |           11 |          0.331 |          0.506 |             0 |         0.486 |
| lightgbm     | test         |           11 |          0.329 |          0.515 |             0 |         0.47  |
| lightgbm     | wf           |           11 |          0.329 |          0.48  |             0 |         0.507 |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               51.914 |                   0 |              48.086 |               49.998 |               0.004 |              49.998 |
| catboost     | test         |           11 |               51.941 |                   0 |              48.059 |               54.08  |               0     |              45.92  |
| catboost     | wf           |           11 |               51.566 |                   0 |              48.434 |               45.23  |               0     |              54.77  |
| lightgbm     | val          |           11 |               51.914 |                   0 |              48.086 |               49.998 |               0.005 |              49.998 |
| lightgbm     | test         |           11 |               51.941 |                   0 |              48.059 |               52.388 |               0     |              47.612 |
| lightgbm     | wf           |           11 |               51.566 |                   0 |              48.434 |               45.769 |               0     |              54.231 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.20-0.29            |            1 |
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol           |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples |      0.357 |     0.552 |      0.518 |         0 |
| Consumer Staples |      0.351 |     0.545 |      0.508 |         0 |
| Consumer Staples |      0.346 |     0.542 |      0.497 |         0 |
| Industrials      |      0.343 |     0.504 |      0.525 |         0 |
| Industrials      |      0.342 |     0.501 |      0.527 |         0 |
| Industrials      |      0.34  |     0.501 |      0.519 |         0 |
| Industrials      |      0.339 |     0.496 |      0.522 |         0 |
| Industrials      |      0.338 |     0.502 |      0.512 |         0 |
| Health Care      |      0.338 |     0.516 |      0.497 |         0 |
| Health Care      |      0.336 |     0.517 |      0.491 |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Energy                 |      0.297 |     0.45  |      0.44  |         0 |
| Energy                 |      0.298 |     0.428 |      0.466 |         0 |
| Energy                 |      0.302 |     0.442 |      0.466 |         0 |
| Energy                 |      0.317 |     0.484 |      0.466 |         0 |
| Communication Services |      0.318 |     0.509 |      0.447 |         0 |
| Materials              |      0.319 |     0.48  |      0.476 |         0 |
| Materials              |      0.32  |     0.484 |      0.476 |         0 |
| Information Technology |      0.321 |     0.506 |      0.458 |         0 |
| Communication Services |      0.322 |     0.513 |      0.454 |         0 |
| Communication Services |      0.324 |     0.513 |      0.459 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    1.0627 |        0.4963 |
| catboost     | test         |           11 |    1.072  |        0.4968 |
| catboost     | wf           |           11 |    1.0347 |        0.501  |
| lightgbm     | val          |           11 |    1.0749 |        0.4964 |
| lightgbm     | test         |           11 |    1.0924 |        0.4967 |
| lightgbm     | wf           |           11 |    1.0537 |        0.5007 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol           |   dir_acc |    mse |
|:-------------|:-----------------|----------:|-------:|
| lightgbm     | Consumer Staples |    0.5362 | 0.9381 |
| lightgbm     | Consumer Staples |    0.5284 | 0.9171 |
| catboost     | Consumer Staples |    0.5243 | 0.9142 |
| lightgbm     | Consumer Staples |    0.522  | 0.9287 |
| catboost     | Consumer Staples |    0.519  | 0.8995 |
| lightgbm     | Industrials      |    0.5162 | 1.0444 |
| catboost     | Health Care      |    0.5161 | 1.0429 |
| catboost     | Consumer Staples |    0.5153 | 0.9192 |
| lightgbm     | Industrials      |    0.5152 | 1.0121 |
| catboost     | Real Estate      |    0.5131 | 0.9009 |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Materials              |    0.4687 | 1.0938 |
| catboost     | Communication Services |    0.4704 | 1.0362 |
| catboost     | Communication Services |    0.4748 | 1.0612 |
| lightgbm     | Materials              |    0.4767 | 1.064  |
| catboost     | Materials              |    0.4808 | 1.0287 |
| catboost     | Communication Services |    0.4808 | 1.0219 |
| lightgbm     | Information Technology |    0.4813 | 1.1428 |
| lightgbm     | Communication Services |    0.4829 | 1.0909 |
| lightgbm     | Energy                 |    0.4842 | 0.9687 |
| catboost     | Information Technology |    0.4862 | 1.0913 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.315 |      0.438 |         0 |     0.508 | —           |     7.7 |      15   |            11 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.337 |      0.486 |         0 |     0.524 | —           |    19.1 |      25.7 |            11 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.325 |      0.464 |         0 |     0.511 | —           |     9.8 |      18.8 |            11 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.336 |      0.464 |         0 |     0.545 | —           |     0.1 |      24.9 |            11 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.316 |      0.487 |         0 |     0.461 | —           |     9   |      15.1 |            11 |
|       5 | 2024-09-03  | 2025-03-05 | 🟢 Bull           |      0.335 |      0.505 |         0 |     0.501 | —           |     5.6 |      17.4 |            11 |
