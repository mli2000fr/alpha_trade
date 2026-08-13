# Diagnostic ML — Batch `model-factory-20260812235655-c993b3`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260812235655-c993b3`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : B36 B20 + symbols 196
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0148
- **📈 IC IR (Stabilité)** : 0.45  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0256 H5=0.0156 H10=0.0037 H15=0.0014 H20=0.0022
- **🏆 Champion Global** : catboost (H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=lightgbm) — score composite 55% IC + 30% IR + 15% positifs
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-12 23:56:56
- **Terminé le** : 2026-08-13 01:33:31
- **Complétés / Skippés / Échecs** : 9 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-short-score --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B36 B20 + symbols 196"
```

## 🌐 Global Ranking — Détails par Horizon

Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=lightgbm) — sélection par IC IR — 196 symboles, 6 splits walk-forward, 106817 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |    IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits | 🏆 Champion   |   Score |   IC catboost |   IR catboost |   IC lightgbm |   IR lightgbm |
|:----------|-----------:|--------:|----------------:|--------------:|------------:|:--------------|--------:|--------------:|--------------:|--------------:|--------------:|
| H3        | 0.0276818  |    1.57 |      0.0255756  |           144 |           6 | catboost      |   1     |        0.0277 |          1.57 |        0.0108 |          0.95 |
| H5        | 0.0246374  |    1.23 |      0.0156019  |           144 |           6 | catboost      |   1     |        0.0246 |          1.23 |        0.0139 |          0.62 |
| H10       | 0.00783    |    0.25 |      0.00365097 |           144 |           6 | catboost      |   0.95  |        0.0078 |          0.25 |       -0.0018 |         -0.06 |
| H15       | 0.00724057 |    0.2  |      0.00139024 |           144 |           6 | catboost      |   0.95  |        0.0072 |          0.2  |        0.0031 |          0.08 |
| H20       | 0.0068455  |    0.16 |      0.00222246 |           144 |           6 | lightgbm      |   0.923 |        0.0062 |          0.16 |        0.0068 |          0.16 |


🏆 **Meilleur horizon : H3** — sélectionné par score composite 55% IC + 30% IR + 15% Positive Split  |  H3=1.0000  H5=0.8747  H10=0.3023  H15=0.2825  H20=0.2407
### Horizon H3 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0277 | IR = 1.57 | Score composite = 1.000 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0277
- **Decile Spread** : 0.0256
- **Nb Features** : 144

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-24 | 2019-01-02 → 2019-06-26  |          46520 |        12813 |            0.0627243 |    0.0264447  |     0.0627243 |
|       2 | 2016-12-29 → 2019-12-24 | 2020-01-02 → 2020-06-25  |          73894 |        14264 |            0.0355366 |    0.0134948  |     0.0355366 |
|       3 | 2016-12-29 → 2020-12-23 | 2020-12-31 → 2021-06-25  |         104120 |        15615 |            0.0121516 |    0.0203562  |     0.0121516 |
|       4 | 2016-12-29 → 2021-12-23 | 2021-12-31 → 2022-06-27  |         137787 |        19205 |            0.0176898 |    0.0112714  |     0.0176898 |
|       5 | 2016-12-29 → 2022-12-23 | 2023-01-03 → 2023-06-28  |         179401 |        22350 |            0.0129436 |   -0.00757909 |     0.0129436 |
|       6 | 2016-12-29 → 2023-12-27 | 2024-01-04 → 2024-06-28  |         225726 |        22570 |            0.0250448 |    0.00100537 |     0.0250448 |

- IC Moyen = 0.0277  |  IC Std = 0.0176  |  IC Min = 0.0122  |  IC Max = 0.0627

### Horizon H5 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0246 | IR = 1.23 | Score composite = 1.000 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0246
- **Decile Spread** : 0.0156
- **Nb Features** : 144

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-20 | 2019-01-02 → 2019-06-24  |          46316 |        12595 |          0.0508826   |     0.0100718 |   0.0508826   |
|       2 | 2016-12-29 → 2019-12-20 | 2020-01-02 → 2020-06-23  |          73662 |        14024 |          0.0510503   |     0.0456843 |   0.0510503   |
|       3 | 2016-12-29 → 2020-12-21 | 2020-12-31 → 2021-06-23  |         103866 |        15355 |          0.00687805  |     0.0307953 |   0.00687805  |
|       4 | 2016-12-29 → 2021-12-21 | 2021-12-31 → 2022-06-23  |         137485 |        18875 |          0.000615483 |    -0.0163479 |   0.000615483 |
|       5 | 2016-12-29 → 2022-12-21 | 2023-01-03 → 2023-06-26  |         179039 |        21982 |          0.0140645   |    -0.0123315 |   0.0140645   |
|       6 | 2016-12-29 → 2023-12-22 | 2024-01-04 → 2024-06-26  |         225356 |        22200 |          0.0243334   |     0.025507  |   0.0243334   |

- IC Moyen = 0.0246  |  IC Std = 0.0200  |  IC Min = 0.0006  |  IC Max = 0.0511

### Horizon H10 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0078 | IR = 0.25 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0078
- **Decile Spread** : 0.0037
- **Nb Features** : 144

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |          45806 |        12054 |            0.0469352 |    0.0170301  |     0.0469352 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |          73082 |        13424 |            0.0288279 |    0.00173911 |     0.0288279 |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         103231 |        14705 |           -0.0283956 |   -0.0239367  |    -0.0283956 |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         136731 |        18050 |           -0.0417547 |   -0.0537578  |    -0.0417547 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         178134 |        21062 |            0.0256887 |    0.0152831  |     0.0256887 |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         224431 |        21275 |            0.0156785 |    0.0328353  |     0.0156785 |

- IC Moyen = 0.0078  |  IC Std = 0.0319  |  IC Min = -0.0418  |  IC Max = 0.0469

### Horizon H15 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0072 | IR = 0.20 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0072
- **Decile Spread** : 0.0014
- **Nb Features** : 144

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |          45806 |        12054 |           0.0478663  |    0.00693506 |    0.0478663  |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |          73082 |        13424 |           0.0398113  |    0.0669703  |    0.0398113  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         103231 |        14705 |          -0.0245433  |   -0.0292361  |   -0.0245433  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         136731 |        18050 |          -0.0528981  |   -0.0599482  |   -0.0528981  |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         178134 |        21062 |           0.0252297  |    0.00364295 |    0.0252297  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         224431 |        21275 |           0.00797752 |    0.0301997  |    0.00797752 |

- IC Moyen = 0.0072  |  IC Std = 0.0357  |  IC Min = -0.0529  |  IC Max = 0.0479

### Horizon H20 — 🏆 lightgbm

- 🏆 **Champion : lightgbm** | IC = 0.0068 | IR = 0.16 | Score composite = 0.923 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0068
- **Decile Spread** : 0.0022
- **Nb Features** : 144

#### 🔝 Feature Importance — Top 10 / Bottom 10

| # | Top Feature | Top Imp. | Bottom Feature | Bottom Imp. |
|---:|:---|---:|:---|---:|
| 1 | `rolling_volatility_60` | 101.1 | `intraday_range_zscore` | 0.0 |
| 2 | `momentum_250_zscore` | 99.5 | `momentum_3_xs_rank` | 0.0 |
| 3 | `sma50_minus_sma200` | 93.3 | `momentum_5_xs_rank` | 0.0 |
| 4 | `momentum_60_xs_rank` | 82.6 | `rsi_2_xs_rank` | 0.0 |
| 5 | `rolling_volatility_60_zscore` | 79.7 | `rsi_3_xs_rank` | 0.0 |
| 6 | `momentum_250` | 73.0 | `volume_ratio_5_xs_rank` | 0.0 |
| 7 | `rolling_volatility_20_zscore` | 71.1 | `overnight_gap_xs_rank` | 0.0 |
| 8 | `momentum_250_xs_rank` | 69.3 | `close_to_vwap_xs_rank` | 0.0 |
| 9 | `rolling_volatility_60_xs_rank` | 62.8 | `decay_5_10_xs_rank` | 0.0 |
| 10 | `sma200_distance_zscore` | 62.5 | `gap_fade_xs_rank` | 0.0 |

#### 📅 Détail par split — 🏆 lightgbm

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (lightgbm) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |          45806 |        12054 |            0.0178637 |     0.0178637 |     0.0314458 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |          73082 |        13424 |            0.0796682 |     0.0796682 |     0.0330262 |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         103231 |        14705 |           -0.0372291 |    -0.0372291 |    -0.0363317 |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         136731 |        18050 |           -0.0408214 |    -0.0408214 |    -0.0560296 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         178134 |        21062 |            0.0419538 |     0.0419538 |     0.0541085 |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         224431 |        21275 |           -0.0203621 |    -0.0203621 |     0.010957  |

- IC Moyen = 0.0068  |  IC Std = 0.0440  |  IC Min = -0.0408  |  IC Max = 0.0797


## 🧪 Backtest Stratégies — Global Rank (H3 + H5)

| Variante | Score relatif |
|----------|---------------|
| V1 — H3 seul | 🏆 référence |
| V2 — H3 + H5 rising | -15.0% |
| V3 — H3 + H5 < 0.35 | -73.1% |
| V4 — H3 + top 3 horizons ↑ (H3,H5,H10) | -18.4% |

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
|         3 |      0.329 |      0.509 |     0.477 |    0.4994 |
|         5 |      0.323 |      0.502 |     0.466 |    0.4946 |
|        10 |      0.318 |      0.495 |     0.46  |    0.4931 |
|        15 |      0.321 |      0.491 |     0.471 |    0.4957 |
|        20 |      0.317 |      0.495 |     0.457 |    0.4927 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |            8 |          0.334 |          0.523 |             0 |         0.479 |
| catboost     | test         |            8 |          0.321 |          0.5   |             0 |         0.464 |
| catboost     | wf           |            8 |          0.321 |          0.493 |             0 |         0.469 |
| lightgbm     | val          |            8 |          0.333 |          0.522 |             0 |         0.478 |
| lightgbm     | test         |            8 |          0.325 |          0.511 |             0 |         0.463 |
| lightgbm     | wf           |            8 |          0.322 |          0.503 |             0 |         0.463 |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |            8 |               54.444 |                   0 |              45.556 |               49.993 |               0.014 |              49.993 |
| catboost     | test         |            8 |               53.893 |                   0 |              46.107 |               49.811 |               0     |              50.189 |
| catboost     | wf           |            8 |               53.778 |                   0 |              46.222 |               48.867 |               0     |              51.133 |
| lightgbm     | val          |            8 |               54.444 |                   0 |              45.556 |               49.993 |               0.015 |              49.993 |
| lightgbm     | test         |            8 |               53.893 |                   0 |              46.107 |               50.976 |               0     |              49.024 |
| lightgbm     | wf           |            8 |               53.778 |                   0 |              46.222 |               50.322 |               0     |              49.678 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.20-0.29            |            2 |
| 0.30-0.39            |            8 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Financials             |      0.356 |     0.463 |      0.604 |         0 |
| Financials             |      0.339 |     0.398 |      0.62  |         0 |
| Consumer Discretionary |      0.337 |     0.475 |      0.536 |         0 |
| Industrials            |      0.336 |     0.487 |      0.523 |         0 |
| Financials             |      0.334 |     0.411 |      0.593 |         0 |
| Industrials            |      0.334 |     0.497 |      0.504 |         0 |
| Consumer Discretionary |      0.333 |     0.488 |      0.512 |         0 |
| Financials             |      0.333 |     0.394 |      0.605 |         0 |
| Information Technology |      0.333 |     0.494 |      0.504 |         0 |
| Industrials            |      0.333 |     0.493 |      0.505 |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples       |      0.292 |     0.341 |      0.535 |         0 |
| Consumer Staples       |      0.299 |     0.347 |      0.548 |         0 |
| Consumer Staples       |      0.299 |     0.36  |      0.536 |         0 |
| Energy                 |      0.299 |     0.528 |      0.371 |         0 |
| Communication Services |      0.304 |     0.401 |      0.51  |         0 |
| Energy                 |      0.304 |     0.521 |      0.39  |         0 |
| Communication Services |      0.305 |     0.423 |      0.492 |         0 |
| Energy                 |      0.308 |     0.515 |      0.408 |         0 |
| Communication Services |      0.31  |     0.442 |      0.487 |         0 |
| Consumer Staples       |      0.312 |     0.441 |      0.495 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |            8 |    1.2961 |        0.5029 |
| catboost     | test         |            8 |    1.4113 |        0.4848 |
| catboost     | wf           |            8 |    1.3132 |        0.4939 |
| lightgbm     | val          |            8 |    1.3401 |        0.5013 |
| lightgbm     | test         |            8 |    1.4417 |        0.4907 |
| lightgbm     | wf           |            8 |    1.3578 |        0.4963 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Financials             |    0.5442 | 1.5926 |
| lightgbm     | Financials             |    0.5345 | 1.6211 |
| lightgbm     | Financials             |    0.5257 | 1.4334 |
| lightgbm     | Consumer Staples       |    0.5238 | 2.7733 |
| catboost     | Financials             |    0.5233 | 1.573  |
| catboost     | Financials             |    0.5227 | 1.5152 |
| lightgbm     | Financials             |    0.5214 | 1.6314 |
| lightgbm     | Consumer Discretionary |    0.519  | 1.0872 |
| catboost     | Consumer Discretionary |    0.5169 | 1.2212 |
| lightgbm     | Consumer Staples       |    0.5169 | 2.4357 |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Communication Services |    0.4587 | 1.473  |
| lightgbm     | Consumer Staples       |    0.4593 | 2.6689 |
| lightgbm     | Communication Services |    0.4632 | 1.6263 |
| lightgbm     | Communication Services |    0.4668 | 1.2496 |
| catboost     | Communication Services |    0.4682 | 1.4146 |
| catboost     | Consumer Staples       |    0.4702 | 2.544  |
| lightgbm     | Consumer Staples       |    0.4712 | 2.3564 |
| catboost     | Energy                 |    0.4719 | 1.002  |
| catboost     | Communication Services |    0.4724 | 1.2436 |
| catboost     | Consumer Staples       |    0.4732 | 2.2986 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.329 |      0.44  |         0 |     0.546 | —           |     7.7 |      15   |             6 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.331 |      0.518 |         0 |     0.475 | —           |    19.1 |      25.7 |             6 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.292 |      0.389 |         0 |     0.487 | —           |     9.8 |      18.8 |             6 |
|       2 | 2022-03-23  | 2022-09-21 | 🔴 Bear high vol  |      0.281 |      0.486 |         0 |     0.357 | —           |   -15   |      25.5 |             1 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.294 |      0.364 |         0 |     0.517 | —           |     0.1 |      24.9 |             6 |
|       3 | 2023-03-24  | 2023-10-20 | 🟢 Bull           |      0.386 |      0.579 |         0 |     0.579 | —           |     6.4 |      16.2 |             1 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.339 |      0.557 |         0 |     0.458 | —           |     9   |      15.1 |             6 |
|       0 | 2023-12-04  | 2024-06-04 | 🟢 Bull           |      0.361 |      0.65  |         0 |     0.433 | —           |    15.7 |      13.9 |             1 |
|       4 | 2024-04-24  | 2024-11-19 | 🟢 Bull           |      0.284 |      0.467 |         0 |     0.385 | —           |    16.8 |      16.3 |             1 |
|       5 | 2024-09-03  | 2025-03-05 | 🔵 Range low vol  |      0.331 |      0.548 |         0 |     0.443 | —           |     5.6 |      17.4 |             6 |
|       1 | 2025-01-03  | 2025-08-05 | 🔵 Range low vol  |      0.32  |      0.496 |         0 |     0.463 | —           |     6.1 |      20.4 |             1 |
|       5 | 2025-05-27  | 2025-11-21 | 🟢 Bull           |      0.217 |      0.609 |         0 |     0.041 | —           |    11.5 |      17.3 |             1 |
