# Diagnostic ML — Batch `model-factory-20260809211556-6f94d8`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260809211556-6f94d8`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : B7 Short + SPY + Vix3m
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0202
- **📈 IC IR (Stabilité)** : 1.03  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0098 H5=0.0190 H10=0.0297 H15=0.0303 H20=0.0301
- **🏆 Champion Global** : catboost (H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — score composite 55% IC + 30% IR + 15% positifs
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-09 21:15:56
- **Terminé le** : 2026-08-09 22:22:53
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-short-score --include-macro-vix3m --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B7 Short + SPY + Vix3m"
```

## 🌐 Global Ranking — Détails par Horizon

Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symboles, 6 splits walk-forward, 259239 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |   IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits | 🏆 Champion   |   Score |   IC catboost |   IR catboost |   IC lightgbm |   IR lightgbm |
|:----------|----------:|--------:|----------------:|--------------:|------------:|:--------------|--------:|--------------:|--------------:|--------------:|--------------:|
| H3        | 0.0104145 |    0.88 |      0.00980416 |           144 |           6 | catboost      |   0.975 |        0.0104 |          0.88 |        0.0029 |          0.28 |
| H5        | 0.0183156 |    0.98 |      0.0189859  |           144 |           6 | catboost      |   0.975 |        0.0183 |          0.98 |        0.0087 |          0.62 |
| H10       | 0.0253768 |    1.47 |      0.0297113  |           144 |           6 | catboost      |   0.975 |        0.0254 |          1.47 |        0.0105 |          0.4  |
| H15       | 0.0233001 |    1.22 |      0.0303409  |           144 |           6 | catboost      |   0.95  |        0.0233 |          1.22 |        0.0207 |          0.76 |
| H20       | 0.023367  |    0.93 |      0.0301065  |           144 |           6 | catboost      |   0.975 |        0.0234 |          0.93 |        0.0084 |          0.3  |


🏆 **Meilleur horizon : H10** — sélectionné par score composite 55% IC + 30% IR + 15% Positive Split  |  H3=0.5303  H5=0.7220  H10=0.9750  H15=0.8533  H20=0.8217
### Horizon H3 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0104 | IR = 0.88 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0104
- **Decile Spread** : 0.0098
- **Nb Features** : 144

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-24 | 2019-01-02 → 2019-06-26  |         149065 |        38302 |           0.00157555 |   0.0219116   |    0.00157555 |
|       2 | 2016-12-29 → 2019-12-24 | 2020-01-02 → 2020-06-25  |         229215 |        40109 |           0.0234234  |   0.0107596   |    0.0234234  |
|       3 | 2016-12-29 → 2020-12-23 | 2020-12-31 → 2021-06-25  |         313075 |        41725 |           0.0264337  |  -0.00638592  |    0.0264337  |
|       4 | 2016-12-29 → 2021-12-23 | 2021-12-31 → 2022-06-27  |         400519 |        44291 |          -0.00750201 |  -0.0070142   |   -0.00750201 |
|       5 | 2016-12-29 → 2022-12-23 | 2023-01-03 → 2023-06-28  |         494250 |        47206 |           0.0116332  |   7.41997e-05 |    0.0116332  |
|       6 | 2016-12-29 → 2023-12-27 | 2024-01-04 → 2024-06-28  |         591911 |        47606 |           0.00692321 |  -0.00203443  |    0.00692321 |

- IC Moyen = 0.0104  |  IC Std = 0.0118  |  IC Min = -0.0075  |  IC Max = 0.0264

### Horizon H5 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0183 | IR = 0.98 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0183
- **Decile Spread** : 0.0190
- **Nb Features** : 144

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-20 | 2019-01-02 → 2019-06-24  |         148443 |        37670 |           0.00571957 |    0.0307047  |    0.00571957 |
|       2 | 2016-12-29 → 2019-12-20 | 2020-01-02 → 2020-06-23  |         228561 |        39443 |           0.0547265  |    0.0235988  |    0.0547265  |
|       3 | 2016-12-29 → 2020-12-21 | 2020-12-31 → 2021-06-23  |         312395 |        41033 |           0.0163789  |    0.00302142 |    0.0163789  |
|       4 | 2016-12-29 → 2021-12-21 | 2021-12-31 → 2022-06-23  |         399803 |        43543 |          -0.00556458 |   -0.00813908 |   -0.00556458 |
|       5 | 2016-12-29 → 2022-12-21 | 2023-01-03 → 2023-06-26  |         493478 |        46432 |           0.0232117  |    0.00757082 |    0.0232117  |
|       6 | 2016-12-29 → 2023-12-22 | 2024-01-04 → 2024-06-26  |         591131 |        46822 |           0.0154217  |   -0.00430498 |    0.0154217  |

- IC Moyen = 0.0183  |  IC Std = 0.0187  |  IC Min = -0.0056  |  IC Max = 0.0547

### Horizon H10 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0254 | IR = 1.47 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0254
- **Decile Spread** : 0.0297
- **Nb Features** : 144

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |           0.0103822  |    0.0157906  |    0.0103822  |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |           0.0439643  |    0.0657406  |    0.0439643  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |           0.0374853  |   -0.0082035  |    0.0374853  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |          -0.00389279 |   -0.00543953 |   -0.00389279 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |           0.0398446  |    0.00272926 |    0.0398446  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |           0.0244769  |   -0.00742048 |    0.0244769  |

- IC Moyen = 0.0254  |  IC Std = 0.0172  |  IC Min = -0.0039  |  IC Max = 0.0440

### Horizon H15 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0233 | IR = 1.22 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0233
- **Decile Spread** : 0.0303
- **Nb Features** : 144

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |          -0.00024891 |    0.0103086  |   -0.00024891 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |           0.0356343  |    0.0764362  |    0.0356343  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |           0.0467588  |    0.0323214  |    0.0467588  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |          -0.00229897 |    0.00286629 |   -0.00229897 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |           0.0398167  |   -0.00114411 |    0.0398167  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |           0.0201389  |    0.00363809 |    0.0201389  |

- IC Moyen = 0.0233  |  IC Std = 0.0191  |  IC Min = -0.0023  |  IC Max = 0.0468

### Horizon H20 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0234 | IR = 0.93 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0234
- **Decile Spread** : 0.0301
- **Nb Features** : 144

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |         -0.00983447  |    0.00510909 |  -0.00983447  |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |          0.030544    |    0.0636843  |   0.030544    |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |          0.0645406   |   -0.0249155  |   0.0645406   |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |          0.000626622 |   -0.00773836 |   0.000626622 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |          0.0406581   |   -0.00176406 |   0.0406581   |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |          0.0136671   |    0.0159656  |   0.0136671   |

- IC Moyen = 0.0234  |  IC Std = 0.0250  |  IC Min = -0.0098  |  IC Max = 0.0645


## 🧪 Backtest Stratégies — Global Rank (H10 + H5)

| Variante | Score relatif |
|----------|---------------|
| V1 — H10 seul | 🏆 référence |
| V2 — H10 + H5 rising | -7.1% |
| V3 — H10 + H5 < 0.35 | -24.8% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H10 seul, V2 = H10 + H5 rising, V3 = H10 + H5 < 0.35 (contrarian).

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
|         3 |      0.331 |      0.493 |     0.499 |    0.5021 |
|         5 |      0.329 |      0.476 |     0.511 |    0.5012 |
|        10 |      0.328 |      0.472 |     0.511 |    0.5011 |
|        15 |      0.328 |      0.475 |     0.508 |    0.5008 |
|        20 |      0.327 |      0.474 |     0.507 |    0.5001 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.332 |          0.507 |             0 |         0.488 |
| catboost     | test         |           11 |          0.329 |          0.524 |             0 |         0.464 |
| catboost     | wf           |           11 |          0.328 |          0.477 |             0 |         0.507 |
| lightgbm     | val          |           11 |          0.331 |          0.506 |             0 |         0.487 |
| lightgbm     | test         |           11 |          0.329 |          0.514 |             0 |         0.474 |
| lightgbm     | wf           |           11 |          0.329 |          0.479 |             0 |         0.507 |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| catboost     | test         |           11 |               51.925 |                   0 |              48.075 |               53.901 |               0     |              46.099 |
| catboost     | wf           |           11 |               51.407 |                   0 |              48.593 |               45.665 |               0     |              54.335 |
| lightgbm     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| lightgbm     | test         |           11 |               51.925 |                   0 |              48.075 |               52.037 |               0     |              47.963 |
| lightgbm     | wf           |           11 |               51.407 |                   0 |              48.593 |               45.878 |               0     |              54.122 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.20-0.29            |            1 |
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol           |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples |      0.358 |     0.552 |      0.521 |         0 |
| Consumer Staples |      0.352 |     0.555 |      0.502 |         0 |
| Consumer Staples |      0.352 |     0.55  |      0.505 |         0 |
| Consumer Staples |      0.339 |     0.543 |      0.475 |         0 |
| Consumer Staples |      0.338 |     0.524 |      0.491 |         0 |
| Health Care      |      0.337 |     0.523 |      0.488 |         0 |
| Industrials      |      0.337 |     0.504 |      0.506 |         0 |
| Financials       |      0.336 |     0.495 |      0.513 |         0 |
| Financials       |      0.335 |     0.521 |      0.485 |         0 |
| Industrials      |      0.335 |     0.494 |      0.512 |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol    |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:----------|-----------:|----------:|-----------:|----------:|
| Energy    |      0.292 |     0.443 |      0.434 |         0 |
| Energy    |      0.298 |     0.452 |      0.442 |         0 |
| Materials |      0.306 |     0.461 |      0.458 |         0 |
| Energy    |      0.306 |     0.458 |      0.462 |         0 |
| Utilities |      0.308 |     0.568 |      0.356 |         0 |
| Utilities |      0.311 |     0.549 |      0.384 |         0 |
| Utilities |      0.314 |     0.539 |      0.402 |         0 |
| Materials |      0.314 |     0.462 |      0.481 |         0 |
| Materials |      0.318 |     0.468 |      0.484 |         0 |
| Energy    |      0.319 |     0.477 |      0.479 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    1.0666 |        0.498  |
| catboost     | test         |           11 |    1.0875 |        0.4978 |
| catboost     | wf           |           11 |    1.0438 |        0.5014 |
| lightgbm     | val          |           11 |    1.0793 |        0.4966 |
| lightgbm     | test         |           11 |    1.1073 |        0.4971 |
| lightgbm     | wf           |           11 |    1.0647 |        0.5007 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol           |   dir_acc |    mse |
|:-------------|:-----------------|----------:|-------:|
| lightgbm     | Consumer Staples |    0.5456 | 0.9191 |
| catboost     | Consumer Staples |    0.5397 | 0.8959 |
| lightgbm     | Consumer Staples |    0.5322 | 0.9171 |
| catboost     | Consumer Staples |    0.5315 | 0.9202 |
| catboost     | Consumer Staples |    0.531  | 0.8931 |
| lightgbm     | Consumer Staples |    0.5233 | 0.9318 |
| lightgbm     | Industrials      |    0.5175 | 1.0498 |
| catboost     | Health Care      |    0.5168 | 1.0503 |
| lightgbm     | Industrials      |    0.5157 | 1.0135 |
| catboost     | Financials       |    0.5147 | 1.1261 |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Materials              |    0.4632 | 1.1132 |
| catboost     | Communication Services |    0.4802 | 1.0187 |
| catboost     | Communication Services |    0.4806 | 1.0073 |
| lightgbm     | Energy                 |    0.481  | 1.0225 |
| catboost     | Communication Services |    0.4819 | 1.0371 |
| lightgbm     | Materials              |    0.4829 | 1.0884 |
| lightgbm     | Materials              |    0.4835 | 1.0357 |
| lightgbm     | Communication Services |    0.4837 | 1.0656 |
| catboost     | Materials              |    0.4849 | 1.0458 |
| catboost     | Information Technology |    0.4854 | 1.1062 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.318 |      0.437 |         0 |     0.517 | —           |     7.7 |      15   |            11 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.329 |      0.44  |         0 |     0.549 | —           |    19.1 |      25.7 |            11 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.321 |      0.45  |         0 |     0.514 | —           |     9.8 |      18.8 |            11 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.338 |      0.502 |         0 |     0.512 | —           |     0.1 |      24.9 |            11 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.322 |      0.494 |         0 |     0.472 | —           |     9   |      15.1 |            11 |
|       5 | 2024-09-03  | 2025-03-05 | 🟢 Bull           |      0.329 |      0.51  |         0 |     0.478 | —           |     5.6 |      17.4 |            11 |
