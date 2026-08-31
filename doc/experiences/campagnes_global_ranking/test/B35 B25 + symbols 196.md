# Diagnostic ML — Batch `model-factory-20260812232931-792070`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260812232931-792070`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : B35 B25 + symbols 196
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0154
- **📈 IC IR (Stabilité)** : 0.51  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0301 H5=0.0226 H10=0.0061 H15=0.0071 H20=0.0100
- **🏆 Champion Global** : catboost (H3=catboost, H5=catboost, H10=lightgbm, H15=catboost, H20=lightgbm) — score composite 55% IC + 30% IR + 15% positifs
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-12 23:29:31
- **Terminé le** : 2026-08-13 01:24:59
- **Complétés / Skippés / Échecs** : 9 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-short-score --include-factors --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B35 B25 + symbols 196"
```

## 🌐 Global Ranking — Détails par Horizon

Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=lightgbm, H15=catboost, H20=lightgbm) — sélection par IC IR — 196 symboles, 6 splits walk-forward, 106817 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |    IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits | 🏆 Champion   |   Score |   IC catboost |   IR catboost |   IC lightgbm |   IR lightgbm |
|:----------|-----------:|--------:|----------------:|--------------:|------------:|:--------------|--------:|--------------:|--------------:|--------------:|--------------:|
| H3        | 0.0282919  |    1.46 |      0.0300859  |           145 |           6 | catboost      |   1     |        0.0283 |          1.46 |        0.017  |          0.97 |
| H5        | 0.0228838  |    0.89 |      0.0225834  |           145 |           6 | catboost      |   0.95  |        0.0229 |          0.89 |        0.0079 |          0.7  |
| H10       | 0.0123328  |    0.4  |      0.00612109 |           145 |           6 | lightgbm      |   0.9   |        0.0071 |          0.22 |        0.0123 |          0.4  |
| H15       | 0.00820413 |    0.23 |      0.00707844 |           145 |           6 | catboost      |   0.95  |        0.0082 |          0.23 |       -0.0065 |         -0.22 |
| H20       | 0.00550317 |    0.17 |      0.0100404  |           145 |           6 | lightgbm      |   0.925 |        0.0024 |          0.06 |        0.0055 |          0.17 |


🏆 **Meilleur horizon : H3** — sélectionné par score composite 55% IC + 30% IR + 15% Positive Split  |  H3=1.0000  H5=0.7277  H10=0.3717  H15=0.3069  H20=0.2171
### Horizon H3 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0283 | IR = 1.46 | Score composite = 1.000 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0283
- **Decile Spread** : 0.0301
- **Nb Features** : 145

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-24 | 2019-01-02 → 2019-06-26  |          46520 |        12813 |           0.0662911  |    0.0452141  |    0.0662911  |
|       2 | 2016-12-29 → 2019-12-24 | 2020-01-02 → 2020-06-25  |          73894 |        14264 |           0.0392915  |    0.017433   |    0.0392915  |
|       3 | 2016-12-29 → 2020-12-23 | 2020-12-31 → 2021-06-25  |         104120 |        15615 |           0.00926412 |    0.0315178  |    0.00926412 |
|       4 | 2016-12-29 → 2021-12-23 | 2021-12-31 → 2022-06-27  |         137787 |        19205 |           0.0180324  |    0.00653882 |    0.0180324  |
|       5 | 2016-12-29 → 2022-12-23 | 2023-01-03 → 2023-06-28  |         179401 |        22350 |           0.0158694  |   -0.00832142 |    0.0158694  |
|       6 | 2016-12-29 → 2023-12-27 | 2024-01-04 → 2024-06-28  |         225726 |        22570 |           0.0210027  |    0.00936293 |    0.0210027  |

- IC Moyen = 0.0283  |  IC Std = 0.0193  |  IC Min = 0.0093  |  IC Max = 0.0663

### Horizon H5 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0229 | IR = 0.89 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0229
- **Decile Spread** : 0.0226
- **Nb Features** : 145

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-20 | 2019-01-02 → 2019-06-24  |          46316 |        12595 |           0.0605139  |    0.0137215  |    0.0605139  |
|       2 | 2016-12-29 → 2019-12-20 | 2020-01-02 → 2020-06-23  |          73662 |        14024 |           0.0492759  |    0.0247019  |    0.0492759  |
|       3 | 2016-12-29 → 2020-12-21 | 2020-12-31 → 2021-06-23  |         103866 |        15355 |          -0.00840308 |    0.00535896 |   -0.00840308 |
|       4 | 2016-12-29 → 2021-12-21 | 2021-12-31 → 2022-06-23  |         137485 |        18875 |          -0.00412445 |   -0.00275503 |   -0.00412445 |
|       5 | 2016-12-29 → 2022-12-21 | 2023-01-03 → 2023-06-26  |         179039 |        21982 |           0.0127346  |   -0.00868842 |    0.0127346  |
|       6 | 2016-12-29 → 2023-12-22 | 2024-01-04 → 2024-06-26  |         225356 |        22200 |           0.0273061  |    0.0153234  |    0.0273061  |

- IC Moyen = 0.0229  |  IC Std = 0.0256  |  IC Min = -0.0084  |  IC Max = 0.0605

### Horizon H10 — 🏆 lightgbm

- 🏆 **Champion : lightgbm** | IC = 0.0123 | IR = 0.40 | Score composite = 0.900 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0123
- **Decile Spread** : 0.0061
- **Nb Features** : 145

#### 🔝 Feature Importance — Top 10 / Bottom 10

| # | Top Feature | Top Imp. | Bottom Feature | Bottom Imp. |
|---:|:---|---:|:---|---:|
| 1 | `rolling_volatility_60_xs_rank` | 79.3 | `rsi_2_xs_rank` | 0.0 |
| 2 | `momentum_120` | 70.2 | `rsi_3_xs_rank` | 0.0 |
| 3 | `rolling_volatility_60` | 51.6 | `dist_to_sma_5d_xs_rank` | 0.0 |
| 4 | `momentum_120_xs_rank` | 46.8 | `volume_ratio_5_xs_rank` | 0.0 |
| 5 | `sma200_distance` | 44.9 | `rolling_mean_return_5_xs_rank` | 0.0 |
| 6 | `rolling_volatility_60_zscore` | 40.6 | `overnight_gap_xs_rank` | 0.0 |
| 7 | `momentum_60_xs_rank` | 32.9 | `close_to_vwap_xs_rank` | 0.0 |
| 8 | `vol_ratio_20_60_x_bull` | 31.9 | `decay_5_10_xs_rank` | 0.0 |
| 9 | `rolling_volatility_20_xs_rank` | 28.8 | `rsi_slope_xs_rank` | 0.0 |
| 10 | `rolling_volatility_20` | 28.0 | `gap_fade_xs_rank` | 0.0 |

#### 📅 Détail par split — 🏆 lightgbm

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (lightgbm) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |          45806 |        12054 |          -0.0110354  |   -0.0110354  |     0.0471832 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |          73082 |        13424 |           0.0629196  |    0.0629196  |     0.0313879 |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         103231 |        14705 |          -0.00243604 |   -0.00243604 |    -0.0317108 |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         136731 |        18050 |          -0.0181069  |   -0.0181069  |    -0.0417785 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         178134 |        21062 |          -0.00402643 |   -0.00402643 |     0.0171425 |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         224431 |        21275 |           0.0466821  |    0.0466821  |     0.0205901 |

- IC Moyen = 0.0123  |  IC Std = 0.0308  |  IC Min = -0.0181  |  IC Max = 0.0629

### Horizon H15 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0082 | IR = 0.23 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0082
- **Decile Spread** : 0.0071
- **Nb Features** : 145

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |          45806 |        12054 |           0.0571149  |   -0.00728018 |    0.0571149  |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |          73082 |        13424 |           0.0330033  |   -0.006344   |    0.0330033  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         103231 |        14705 |          -0.0369788  |   -0.0622648  |   -0.0369788  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         136731 |        18050 |          -0.0386533  |   -0.0128834  |   -0.0386533  |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         178134 |        21062 |           0.0249748  |    0.0170141  |    0.0249748  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         224431 |        21275 |           0.00976384 |    0.0325429  |    0.00976384 |

- IC Moyen = 0.0082  |  IC Std = 0.0354  |  IC Min = -0.0387  |  IC Max = 0.0571

### Horizon H20 — 🏆 lightgbm

- 🏆 **Champion : lightgbm** | IC = 0.0055 | IR = 0.17 | Score composite = 0.925 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0055
- **Decile Spread** : 0.0100
- **Nb Features** : 145

#### 🔝 Feature Importance — Top 10 / Bottom 10

| # | Top Feature | Top Imp. | Bottom Feature | Bottom Imp. |
|---:|:---|---:|:---|---:|
| 1 | `rolling_volatility_60` | 40.2 | `rolling_mean_return_5_xs_rank` | 0.0 |
| 2 | `momentum_250_xs_rank` | 38.6 | `intraday_range_xs_rank` | 0.0 |
| 3 | `rolling_volatility_20` | 30.5 | `overnight_gap_xs_rank` | 0.0 |
| 4 | `rolling_volatility_60_xs_rank` | 28.0 | `close_to_vwap_xs_rank` | 0.0 |
| 5 | `sma50_minus_sma200` | 27.8 | `relative_strength_20_xs_rank` | 0.0 |
| 6 | `momentum_252_vs_market` | 27.5 | `decay_5_10_xs_rank` | 0.0 |
| 7 | `rsi_14_div_volatility_20` | 20.8 | `rsi_slope_xs_rank` | 0.0 |
| 8 | `rolling_volatility_60_zscore` | 14.4 | `vol_expansion_xs_rank` | 0.0 |
| 9 | `sma250_distance` | 13.3 | `meanrev_signal_xs_rank` | 0.0 |
| 10 | `momentum_60` | 13.3 | `gap_fade_xs_rank` | 0.0 |

#### 📅 Détail par split — 🏆 lightgbm

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (lightgbm) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |          45806 |        12054 |           0.0148977  |    0.0148977  |    0.0312705  |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |          73082 |        13424 |           0.0631735  |    0.0631735  |    0.0258114  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         103231 |        14705 |          -0.0343496  |   -0.0343496  |   -0.0325883  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         136731 |        18050 |          -0.0254461  |   -0.0254461  |   -0.0627142  |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         178134 |        21062 |          -0.00272153 |   -0.00272153 |    0.0497228  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         224431 |        21275 |           0.017465   |    0.017465   |    0.00307116 |

- IC Moyen = 0.0055  |  IC Std = 0.0321  |  IC Min = -0.0343  |  IC Max = 0.0632


## 🧪 Backtest Stratégies — Global Rank (H3 + H5)

| Variante | Score relatif |
|----------|---------------|
| V1 — H3 seul | 🏆 référence |
| V2 — H3 + H5 rising | -9.7% |
| V3 — H3 + H5 < 0.35 | -79.9% |
| V4 — H3 + top 3 horizons ↑ (H3,H5,H10) | -37.3% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H3 seul, V2 = H3 + H5 rising, V3 = H3 + H5 < 0.35 (contrarian). V4 = H3 + top 3 horizons ↑ (H3,H5,H10).

---

## 🔵 Per-Symbol / Per-Sector — Métriques d'entraînement

### 🏆 Sélection du champion

✅ **Tout va bien** — 9 champions sélectionnés automatiquement sur 9 symboles.

### 📊 Champions par modèle

| model_name   |   nb_symbols |
|:-------------|-------------:|
| lightgbm     |            7 |
| catboost     |            2 |

## 📊 Métriques par Horizon (WF)

|   Horizon |   F1 macro |   F1 short |   F1 long |   Dir Acc |
|----------:|-----------:|-----------:|----------:|----------:|
|         3 |      0.326 |      0.505 |     0.472 |    0.4957 |
|         5 |      0.322 |      0.502 |     0.465 |    0.4944 |
|        10 |      0.317 |      0.492 |     0.459 |    0.4917 |
|        15 |      0.321 |      0.493 |     0.47  |    0.4956 |
|        20 |      0.314 |      0.486 |     0.454 |    0.488  |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |            8 |          0.335 |          0.524 |             0 |         0.48  |
| catboost     | test         |            8 |          0.322 |          0.504 |             0 |         0.461 |
| catboost     | wf           |            8 |          0.32  |          0.493 |             0 |         0.469 |
| lightgbm     | val          |            8 |          0.332 |          0.52  |             0 |         0.476 |
| lightgbm     | test         |            8 |          0.326 |          0.512 |             0 |         0.467 |
| lightgbm     | wf           |            8 |          0.319 |          0.499 |             0 |         0.459 |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |            8 |               54.444 |                   0 |              45.556 |               49.993 |               0.014 |              49.993 |
| catboost     | test         |            8 |               53.893 |                   0 |              46.107 |               50.399 |               0     |              49.601 |
| catboost     | wf           |            8 |               53.778 |                   0 |              46.222 |               48.949 |               0     |              51.051 |
| lightgbm     | val          |            8 |               54.444 |                   0 |              45.556 |               49.992 |               0.016 |              49.992 |
| lightgbm     | test         |            8 |               53.893 |                   0 |              46.107 |               50.728 |               0     |              49.272 |
| lightgbm     | wf           |            8 |               53.778 |                   0 |              46.222 |               50.275 |               0.002 |              49.723 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.20-0.29            |            2 |
| 0.30-0.39            |            8 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Financials             |      0.349 |     0.441 |      0.607 |         0 |
| Financials             |      0.341 |     0.415 |      0.608 |         0 |
| Consumer Discretionary |      0.337 |     0.489 |      0.522 |         0 |
| Industrials            |      0.336 |     0.484 |      0.523 |         0 |
| Consumer Discretionary |      0.335 |     0.465 |      0.54  |         0 |
| Financials             |      0.333 |     0.387 |      0.613 |         0 |
| Industrials            |      0.333 |     0.497 |      0.502 |         0 |
| Health Care            |      0.331 |     0.496 |      0.499 |         0 |
| Health Care            |      0.331 |     0.502 |      0.492 |         0 |
| Financials             |      0.331 |     0.38  |      0.612 |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples       |      0.286 |     0.332 |      0.527 |         0 |
| Consumer Staples       |      0.29  |     0.34  |      0.529 |         0 |
| Energy                 |      0.293 |     0.528 |      0.351 |         0 |
| Energy                 |      0.304 |     0.521 |      0.39  |         0 |
| Communication Services |      0.304 |     0.437 |      0.476 |         0 |
| Communication Services |      0.307 |     0.457 |      0.465 |         0 |
| Energy                 |      0.309 |     0.479 |      0.447 |         0 |
| Energy                 |      0.309 |     0.492 |      0.435 |         0 |
| Energy                 |      0.309 |     0.521 |      0.407 |         0 |
| Communication Services |      0.309 |     0.413 |      0.515 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |            8 |    1.2967 |        0.5038 |
| catboost     | test         |            8 |    1.4063 |        0.4853 |
| catboost     | wf           |            8 |    1.314  |        0.4937 |
| lightgbm     | val          |            8 |    1.3405 |        0.4996 |
| lightgbm     | test         |            8 |    1.4439 |        0.4929 |
| lightgbm     | wf           |            8 |    1.3576 |        0.4924 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Financials             |    0.5389 | 1.5856 |
| lightgbm     | Financials             |    0.5318 | 1.6241 |
| lightgbm     | Financials             |    0.5284 | 1.4494 |
| catboost     | Financials             |    0.5276 | 1.5389 |
| lightgbm     | Financials             |    0.5262 | 1.6184 |
| catboost     | Financials             |    0.5235 | 1.4762 |
| catboost     | Consumer Discretionary |    0.5205 | 0.9916 |
| lightgbm     | Consumer Discretionary |    0.5155 | 1.0306 |
| catboost     | Consumer Discretionary |    0.5154 | 0.9968 |
| catboost     | Financials             |    0.515  | 1.5108 |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Consumer Staples       |    0.4345 | 2.6688 |
| lightgbm     | Communication Services |    0.4492 | 1.4954 |
| lightgbm     | Consumer Staples       |    0.4554 | 2.3363 |
| lightgbm     | Communication Services |    0.462  | 1.612  |
| catboost     | Communication Services |    0.4623 | 1.2492 |
| catboost     | Consumer Staples       |    0.4643 | 2.285  |
| lightgbm     | Communication Services |    0.4667 | 1.373  |
| catboost     | Communication Services |    0.4668 | 1.2261 |
| catboost     | Consumer Staples       |    0.4683 | 2.5454 |
| lightgbm     | Communication Services |    0.4693 | 1.2443 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.324 |      0.433 |         0 |     0.54  | —           |     7.7 |      15   |             6 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.318 |      0.49  |         0 |     0.464 | —           |    19.1 |      25.7 |             6 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.285 |      0.362 |         0 |     0.492 | —           |     9.8 |      18.8 |             6 |
|       2 | 2022-03-23  | 2022-09-21 | 🔴 Bear high vol  |      0.275 |      0.426 |         0 |     0.398 | —           |   -15   |      25.5 |             1 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.288 |      0.349 |         0 |     0.516 | —           |     0.1 |      24.9 |             6 |
|       3 | 2023-03-24  | 2023-10-20 | 🟢 Bull           |      0.416 |      0.654 |         0 |     0.595 | —           |     6.4 |      16.2 |             1 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.345 |      0.563 |         0 |     0.471 | —           |     9   |      15.1 |             6 |
|       0 | 2023-12-04  | 2024-06-04 | 🟢 Bull           |      0.36  |      0.665 |         0 |     0.415 | —           |    15.7 |      13.9 |             1 |
|       4 | 2024-04-24  | 2024-11-19 | 🟢 Bull           |      0.258 |      0.421 |         0 |     0.353 | —           |    16.8 |      16.3 |             1 |
|       5 | 2024-09-03  | 2025-03-05 | 🔵 Range low vol  |      0.334 |      0.552 |         0 |     0.451 | —           |     5.6 |      17.4 |             6 |
|       1 | 2025-01-03  | 2025-08-05 | 🔵 Range low vol  |      0.32  |      0.5   |         0 |     0.461 | —           |     6.1 |      20.4 |             1 |
|       5 | 2025-05-27  | 2025-11-21 | 🟢 Bull           |      0.209 |      0.613 |         0 |     0.014 | —           |    11.5 |      17.3 |             1 |
