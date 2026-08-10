# Diagnostic ML — Batch `model-factory-20260810052226-5de365`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260810052226-5de365`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : B9 Short + SPY + Fondamentaux
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0157
- **📈 IC IR (Stabilité)** : 0.98  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0169 H5=0.0145 H10=0.0197 H15=0.0121 H20=0.0131
- **🏆 Champion Global** : catboost (H3=lightgbm, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — score composite 55% IC + 30% IR + 15% positifs
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-10 05:22:27
- **Terminé le** : 2026-08-10 06:38:24
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-short-score --include-fundamentals --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B9 Short + SPY + Fondamentaux"
```

## 🌐 Global Ranking — Détails par Horizon

Modèle 🏆 Champion: catboost (détail: H3=lightgbm, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symboles, 6 splits walk-forward, 265689 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |    IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits | 🏆 Champion   |   Score |   IC catboost |   IR catboost |   IC lightgbm |   IR lightgbm |
|:----------|-----------:|--------:|----------------:|--------------:|------------:|:--------------|--------:|--------------:|--------------:|--------------:|--------------:|
| H3        | 0.00977354 |    0.68 |       0.0169122 |           144 |           6 | lightgbm      |   0.95  |        0.0045 |          0.43 |        0.0098 |          0.68 |
| H5        | 0.0133231  |    0.86 |       0.0145176 |           156 |           6 | catboost      |   0.975 |        0.0133 |          0.86 |        0.0095 |          0.54 |
| H10       | 0.0210275  |    1.25 |       0.0196642 |           156 |           6 | catboost      |   0.975 |        0.021  |          1.25 |       -0.0005 |         -0.02 |
| H15       | 0.0163132  |    1.17 |       0.0120506 |           156 |           6 | catboost      |   0.975 |        0.0163 |          1.17 |        0.0047 |          0.22 |
| H20       | 0.017876   |    1.07 |       0.013139  |           156 |           6 | catboost      |   0.975 |        0.0179 |          1.07 |        0.0081 |          0.34 |


🏆 **Meilleur horizon : H10** — sélectionné par score composite 55% IC + 30% IR + 15% Positive Split  |  H3=0.5187  H5=0.6794  H10=0.9750  H15=0.8307  H20=0.8496
### Horizon H3 — 🏆 lightgbm

- 🏆 **Champion : lightgbm** | IC = 0.0098 | IR = 0.68 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0098
- **Decile Spread** : 0.0169
- **Nb Features** : 144

#### 🔝 Feature Importance — Top 10 / Bottom 10

| # | Top Feature | Top Imp. | Bottom Feature | Bottom Imp. |
|---:|:---|---:|:---|---:|
| 1 | `momentum_250_xs_rank` | 43.9 | `momentum_3` | 0.0 |
| 2 | `momentum_250` | 20.3 | `sma10_distance` | 0.0 |
| 3 | `sma50_minus_sma200` | 8.7 | `zscore_close_vs_ma10` | 0.0 |
| 4 | `atr_14_norm` | 5.5 | `momentum_20_div_vol_20` | 0.0 |
| 5 | `rolling_volatility_20_xs_rank` | 5.5 | `rsi_14_times_volume_ratio_20` | 0.0 |
| 6 | `sma250_distance_zscore` | 5.3 | `momentum_20_xs_rank` | 0.0 |
| 7 | `rolling_volatility_60` | 5.0 | `rsi_3_xs_rank` | 0.0 |
| 8 | `sma250_distance` | 5.0 | `volume_ratio_5_xs_rank` | 0.0 |
| 9 | `rolling_volatility_60_zscore` | 4.3 | `relative_strength_20_xs_rank` | 0.0 |
| 10 | `sma20_minus_sma50` | 4.2 | `relative_strength_60_xs_rank` | 0.0 |

#### 📅 Détail par split — 🏆 lightgbm

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (lightgbm) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |          0.0171881   |   0.0171881   |   -0.00277731 |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |          0.0328924   |   0.0328924   |    0.0152216  |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |         -0.000468545 |  -0.000468545 |    0.0210954  |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |         -0.0116634   |  -0.0116634   |   -0.00868261 |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |          0.00396841  |   0.00396841  |    0.00474443 |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |          0.0167243   |   0.0167243   |   -0.0023142  |

- IC Moyen = 0.0098  |  IC Std = 0.0144  |  IC Min = -0.0117  |  IC Max = 0.0329

### Horizon H5 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0133 | IR = 0.86 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0133
- **Decile Spread** : 0.0145
- **Nb Features** : 156

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |           0.00618186 |    0.00480752 |    0.00618186 |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |           0.0302854  |    0.0483918  |    0.0302854  |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |           0.0272974  |   -0.00382306 |    0.0272974  |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |          -0.0163543  |    0.00562423 |   -0.0163543  |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |           0.014138   |   -0.00234295 |    0.014138   |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |           0.0183905  |    0.00446037 |    0.0183905  |

- IC Moyen = 0.0133  |  IC Std = 0.0155  |  IC Min = -0.0164  |  IC Max = 0.0303

### Horizon H10 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0210 | IR = 1.25 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0210
- **Decile Spread** : 0.0197
- **Nb Features** : 156

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |            0.0161729 |    0.0314655  |     0.0161729 |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |            0.0135848 |    0.0273357  |     0.0135848 |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |            0.0343372 |    0.00409085 |     0.0343372 |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |           -0.0086431 |   -0.00820275 |    -0.0086431 |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |            0.0438282 |   -0.0263824  |     0.0438282 |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |            0.0268853 |   -0.0314395  |     0.0268853 |

- IC Moyen = 0.0210  |  IC Std = 0.0168  |  IC Min = -0.0086  |  IC Max = 0.0438

### Horizon H15 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0163 | IR = 1.17 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0163
- **Decile Spread** : 0.0121
- **Nb Features** : 156

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |            0.0177987 |   0.0127431   |     0.0177987 |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |            0.0105475 |   0.0443041   |     0.0105475 |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |            0.0279145 |  -0.0128377   |     0.0279145 |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |           -0.0114345 |  -0.0209113   |    -0.0114345 |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |            0.0302343 |   0.00423556  |     0.0302343 |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |            0.0228187 |   0.000405954 |     0.0228187 |

- IC Moyen = 0.0163  |  IC Std = 0.0140  |  IC Min = -0.0114  |  IC Max = 0.0302

### Horizon H20 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0179 | IR = 1.07 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0179
- **Decile Spread** : 0.0131
- **Nb Features** : 156

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |           0.01072    |    0.0457006  |    0.01072    |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |           0.00259186 |    0.0338084  |    0.00259186 |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |           0.0413939  |   -0.0224236  |    0.0413939  |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |          -0.00583906 |   -0.00192759 |   -0.00583906 |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |           0.0312208  |   -0.00106102 |    0.0312208  |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |           0.0271684  |   -0.00524104 |    0.0271684  |

- IC Moyen = 0.0179  |  IC Std = 0.0167  |  IC Min = -0.0058  |  IC Max = 0.0414


## 🧪 Backtest Stratégies — Global Rank (H10 + H5)

| Variante | Score relatif |
|----------|---------------|
| V1 — H10 seul | 🏆 référence |
| V2 — H10 + H5 rising | -10.3% |
| V3 — H10 + H5 < 0.35 | -42.2% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H10 seul, V2 = H10 + H5 rising, V3 = H10 + H5 < 0.35 (contrarian).

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
|         3 |      0.331 |      0.494 |     0.498 |    0.5012 |
|         5 |      0.33  |      0.483 |     0.507 |    0.5013 |
|        10 |      0.328 |      0.482 |     0.501 |    0.5007 |
|        15 |      0.327 |      0.48  |     0.502 |    0.502  |
|        20 |      0.327 |      0.481 |     0.5   |    0.5012 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.332 |          0.507 |             0 |         0.487 |
| catboost     | test         |           11 |          0.33  |          0.519 |             0 |         0.469 |
| catboost     | wf           |           11 |          0.328 |          0.482 |             0 |         0.501 |
| lightgbm     | val          |           11 |          0.333 |          0.509 |             0 |         0.49  |
| lightgbm     | test         |           11 |          0.33  |          0.513 |             0 |         0.478 |
| lightgbm     | wf           |           11 |          0.329 |          0.486 |             0 |         0.502 |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| catboost     | test         |           11 |               51.925 |                   0 |              48.075 |               53.026 |               0     |              46.974 |
| catboost     | wf           |           11 |               51.407 |                   0 |              48.593 |               46.867 |               0     |              53.133 |
| lightgbm     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.006 |              49.997 |
| lightgbm     | test         |           11 |               51.925 |                   0 |              48.075 |               51.547 |               0     |              48.453 |
| lightgbm     | wf           |           11 |               51.407 |                   0 |              48.593 |               47.116 |               0     |              52.884 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol           |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples |      0.348 |     0.536 |      0.508 |         0 |
| Consumer Staples |      0.347 |     0.532 |      0.51  |         0 |
| Industrials      |      0.345 |     0.508 |      0.527 |         0 |
| Consumer Staples |      0.344 |     0.533 |      0.5   |         0 |
| Industrials      |      0.344 |     0.51  |      0.521 |         0 |
| Industrials      |      0.34  |     0.5   |      0.52  |         0 |
| Industrials      |      0.338 |     0.497 |      0.517 |         0 |
| Industrials      |      0.338 |     0.5   |      0.514 |         0 |
| Consumer Staples |      0.337 |     0.526 |      0.485 |         0 |
| Consumer Staples |      0.336 |     0.518 |      0.491 |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Energy                 |      0.31  |     0.472 |      0.457 |         0 |
| Energy                 |      0.31  |     0.471 |      0.461 |         0 |
| Materials              |      0.311 |     0.456 |      0.478 |         0 |
| Utilities              |      0.312 |     0.496 |      0.44  |         0 |
| Materials              |      0.312 |     0.446 |      0.49  |         0 |
| Materials              |      0.313 |     0.465 |      0.473 |         0 |
| Utilities              |      0.315 |     0.499 |      0.445 |         0 |
| Communication Services |      0.318 |     0.518 |      0.435 |         0 |
| Communication Services |      0.318 |     0.507 |      0.447 |         0 |
| Energy                 |      0.318 |     0.49  |      0.465 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    1.0685 |        0.4976 |
| catboost     | test         |           11 |    1.0934 |        0.497  |
| catboost     | wf           |           11 |    1.0435 |        0.5003 |
| lightgbm     | val          |           11 |    1.0849 |        0.4997 |
| lightgbm     | test         |           11 |    1.1113 |        0.4976 |
| lightgbm     | wf           |           11 |    1.0641 |        0.5022 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol           |   dir_acc |    mse |
|:-------------|:-----------------|----------:|-------:|
| catboost     | Consumer Staples |    0.5299 | 0.9138 |
| lightgbm     | Consumer Staples |    0.5266 | 0.9261 |
| catboost     | Consumer Staples |    0.5259 | 0.9128 |
| lightgbm     | Consumer Staples |    0.5249 | 0.9411 |
| lightgbm     | Consumer Staples |    0.5219 | 0.9424 |
| lightgbm     | Industrials      |    0.5189 | 1.0381 |
| lightgbm     | Utilities        |    0.5181 | 1.2757 |
| catboost     | Consumer Staples |    0.518  | 0.9355 |
| lightgbm     | Utilities        |    0.5168 | 1.0384 |
| lightgbm     | Industrials      |    0.5163 | 1.0049 |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| catboost     | Materials              |    0.4681 | 1.099  |
| lightgbm     | Materials              |    0.4733 | 1.1401 |
| lightgbm     | Materials              |    0.4786 | 1.0469 |
| catboost     | Materials              |    0.4794 | 1.0982 |
| lightgbm     | Materials              |    0.4805 | 1.1227 |
| lightgbm     | Communication Services |    0.483  | 1.0661 |
| lightgbm     | Communication Services |    0.4834 | 1.0438 |
| catboost     | Materials              |    0.484  | 1.0326 |
| lightgbm     | Information Technology |    0.489  | 1.13   |
| catboost     | Materials              |    0.4899 | 0.933  |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.321 |      0.467 |         0 |     0.496 | —           |     7.7 |      15   |            11 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.337 |      0.509 |         0 |     0.502 | —           |    19.1 |      25.7 |            11 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.329 |      0.493 |         0 |     0.493 | —           |     9.8 |      18.8 |            11 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.329 |      0.458 |         0 |     0.53  | —           |     0.1 |      24.9 |            11 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.317 |      0.465 |         0 |     0.486 | —           |     9   |      15.1 |            11 |
|       5 | 2024-09-03  | 2025-03-05 | 🟢 Bull           |      0.325 |      0.484 |         0 |     0.492 | —           |     5.6 |      17.4 |            11 |
