# Diagnostic ML — Batch `model-factory-20260812151652-9aaddb`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260812151652-9aaddb`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : B30 Short + SPY + YetiRank +  P1-3
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0153
- **📈 IC IR (Stabilité)** : 0.49  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0172 H5=0.0123 H10=0.0295 H15=0.0114 H20=0.0009
- **🏆 Champion Global** : lightgbm (H3=catboost, H5=catboost, H10=lightgbm, H15=lightgbm, H20=lightgbm) — score composite 55% IC + 30% IR + 15% positifs
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-12 15:16:52
- **Terminé le** : 2026-08-12 17:40:37
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-short-score --no-include-score-components --target-excess-vs-spy --ranking-raw-target --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B30 Short + SPY + YetiRank +  P1-3"
```

## 🌐 Global Ranking — Détails par Horizon

Modèle 🏆 Champion: lightgbm (détail: H3=catboost, H5=catboost, H10=lightgbm, H15=lightgbm, H20=lightgbm) — sélection par IC IR — 400 symboles, 6 splits walk-forward, 259239 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |    IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits | 🏆 Champion   |   Score |   IC catboost |   IR catboost |   IC lightgbm |   IR lightgbm |
|:----------|-----------:|--------:|----------------:|--------------:|------------:|:--------------|--------:|--------------:|--------------:|--------------:|--------------:|
| H3        | 0.0209123  |    1.1  |     0.0172097   |           144 |           6 | catboost      |   1     |        0.0209 |          1.1  |        0.0039 |          0.54 |
| H5        | 0.0132366  |    0.62 |     0.0122797   |           144 |           6 | catboost      |   0.95  |        0.0132 |          0.62 |        0.0083 |          0.36 |
| H10       | 0.0268082  |    0.71 |     0.0295431   |           144 |           6 | lightgbm      |   0.975 |        0.0074 |          0.36 |        0.0268 |          0.71 |
| H15       | 0.0102017  |    0.33 |     0.0113919   |           144 |           6 | lightgbm      |   0.925 |       -0.0006 |         -0.02 |        0.0102 |          0.33 |
| H20       | 0.00541265 |    0.15 |     0.000866602 |           144 |           6 | lightgbm      |   0.925 |       -0.0043 |         -0.12 |        0.0054 |          0.15 |


🏆 **Meilleur horizon : H10** — sélectionné par score composite 55% IC + 30% IR + 15% Positive Split  |  H3=0.8790  H5=0.5412  H10=0.8680  H15=0.3736  H20=0.2257
### Horizon H3 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0209 | IR = 1.10 | Score composite = 1.000 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0209
- **Decile Spread** : 0.0172
- **Nb Features** : 144

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-24 | 2019-01-02 → 2019-06-26  |         149065 |        38302 |           0.0132895  |   -0.00518149 |    0.0132895  |
|       2 | 2016-12-29 → 2019-12-24 | 2020-01-02 → 2020-06-25  |         229215 |        40109 |           0.0066537  |    0.0128106  |    0.0066537  |
|       3 | 2016-12-29 → 2020-12-23 | 2020-12-31 → 2021-06-25  |         313075 |        41725 |           0.0154958  |    0.0107207  |    0.0154958  |
|       4 | 2016-12-29 → 2021-12-23 | 2021-12-31 → 2022-06-27  |         400519 |        44291 |           0.00960865 |   -0.00461207 |    0.00960865 |
|       5 | 2016-12-29 → 2022-12-23 | 2023-01-03 → 2023-06-28  |         494250 |        47206 |           0.0178302  |    0.00118005 |    0.0178302  |
|       6 | 2016-12-29 → 2023-12-27 | 2024-01-04 → 2024-06-28  |         591911 |        47606 |           0.0625958  |    0.00852941 |    0.0625958  |

- IC Moyen = 0.0209  |  IC Std = 0.0190  |  IC Min = 0.0067  |  IC Max = 0.0626

### Horizon H5 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0132 | IR = 0.62 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0132
- **Decile Spread** : 0.0123
- **Nb Features** : 144

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-20 | 2019-01-02 → 2019-06-24  |         148443 |        37670 |          0.00312395  |   -0.00456932 |   0.00312395  |
|       2 | 2016-12-29 → 2019-12-20 | 2020-01-02 → 2020-06-23  |         228561 |        39443 |          0.0151459   |    0.0500914  |   0.0151459   |
|       3 | 2016-12-29 → 2020-12-21 | 2020-12-31 → 2021-06-23  |         312395 |        41033 |         -0.000582904 |   -0.0200532  |  -0.000582904 |
|       4 | 2016-12-29 → 2021-12-21 | 2021-12-31 → 2022-06-23  |         399803 |        43543 |         -0.00695394  |   -0.00770567 |  -0.00695394  |
|       5 | 2016-12-29 → 2022-12-21 | 2023-01-03 → 2023-06-26  |         493478 |        46432 |          0.010689    |    0.00911198 |   0.010689    |
|       6 | 2016-12-29 → 2023-12-22 | 2024-01-04 → 2024-06-26  |         591131 |        46822 |          0.0579976   |    0.022835   |   0.0579976   |

- IC Moyen = 0.0132  |  IC Std = 0.0213  |  IC Min = -0.0070  |  IC Max = 0.0580

### Horizon H10 — 🏆 lightgbm

- 🏆 **Champion : lightgbm** | IC = 0.0268 | IR = 0.71 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0268
- **Decile Spread** : 0.0295
- **Nb Features** : 144

#### 🔝 Feature Importance — Top 10 / Bottom 10

| # | Top Feature | Top Imp. | Bottom Feature | Bottom Imp. |
|---:|:---|---:|:---|---:|
| 1 | `sma250_distance_xs_rank` | 112.2 | `regime_bull_market` | 0.0 |
| 2 | `rolling_volatility_20_xs_rank` | 105.9 | `regime_risk_off` | 0.0 |
| 3 | `momentum_250_xs_rank` | 93.5 | `rsi_5` | 0.0 |
| 4 | `momentum_250` | 83.4 | `log_return_div_intraday_range` | 0.0 |
| 5 | `rolling_volatility_20` | 75.3 | `decay_5_10` | 0.0 |
| 6 | `sma250_distance_zscore` | 56.0 | `gap_fade` | 0.0 |
| 7 | `momentum_60_xs_rank` | 49.9 | `overnight_gap_xs_rank` | 0.0 |
| 8 | `momentum_250_zscore` | 49.6 | `close_to_vwap_xs_rank` | 0.0 |
| 9 | `sma50_minus_sma200` | 47.3 | `decay_5_10_xs_rank` | 0.0 |
| 10 | `vol_ratio_20_60` | 46.8 | `gap_fade_xs_rank` | 0.0 |

#### 📅 Détail par split — 🏆 lightgbm

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (lightgbm) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |           0.0559218  |    0.0559218  |   -0.00327047 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |           0.0933178  |    0.0933178  |   -0.0144585  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |          -0.0241217  |   -0.0241217  |   -0.00333062 |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |           0.00949941 |    0.00949941 |    0.00308082 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |           0.00769105 |    0.00769105 |    0.0135892  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |           0.0185409  |    0.0185409  |    0.0488072  |

- IC Moyen = 0.0268  |  IC Std = 0.0379  |  IC Min = -0.0241  |  IC Max = 0.0933

### Horizon H15 — 🏆 lightgbm

- 🏆 **Champion : lightgbm** | IC = 0.0102 | IR = 0.33 | Score composite = 0.925 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0102
- **Decile Spread** : 0.0114
- **Nb Features** : 144

#### 🔝 Feature Importance — Top 10 / Bottom 10

| # | Top Feature | Top Imp. | Bottom Feature | Bottom Imp. |
|---:|:---|---:|:---|---:|
| 1 | `rolling_volatility_60_zscore` | 143.8 | `market_trend_strength_50` | 0.0 |
| 2 | `momentum_250_xs_rank` | 134.8 | `regime_bull_market` | 0.0 |
| 3 | `sma50_minus_sma200` | 133.6 | `regime_risk_off` | 0.0 |
| 4 | `sma250_distance_xs_rank` | 132.0 | `rsi_3` | 0.0 |
| 5 | `atr_14_norm_xs_rank` | 123.6 | `volume_ratio_5` | 0.0 |
| 6 | `momentum_250_zscore` | 115.4 | `intraday_range_div_atr_14` | 0.0 |
| 7 | `momentum_250` | 109.8 | `volume_ratio_5_xs_rank` | 0.0 |
| 8 | `sma250_distance` | 109.5 | `overnight_gap_xs_rank` | 0.0 |
| 9 | `rolling_volatility_20` | 89.7 | `close_to_vwap_xs_rank` | 0.0 |
| 10 | `sma250_distance_zscore` | 84.6 | `gap_fade_xs_rank` | 0.0 |

#### 📅 Détail par split — 🏆 lightgbm

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (lightgbm) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-06 | 2019-01-02 → 2019-06-10  |         145338 |        34510 |           0.00130296 |    0.00130296 |    -0.0257971 |
|       2 | 2016-12-29 → 2019-12-06 | 2020-01-02 → 2020-06-09  |         225294 |        36113 |           0.0787393  |    0.0787393  |    -0.0253907 |
|       3 | 2016-12-29 → 2020-12-07 | 2020-12-31 → 2021-06-09  |         308996 |        37583 |          -0.0146283  |   -0.0146283  |    -0.0207558 |
|       4 | 2016-12-29 → 2021-12-07 | 2021-12-31 → 2022-06-08  |         396225 |        39816 |          -0.00341133 |   -0.00341133 |     0.0136404 |
|       5 | 2016-12-29 → 2022-12-07 | 2023-01-03 → 2023-06-09  |         489621 |        42562 |          -0.00235862 |   -0.00235862 |     0.0113094 |
|       6 | 2016-12-29 → 2023-12-08 | 2024-01-04 → 2024-06-11  |         587231 |        42912 |           0.00156647 |    0.00156647 |     0.043655  |

- IC Moyen = 0.0102  |  IC Std = 0.0311  |  IC Min = -0.0146  |  IC Max = 0.0787

### Horizon H20 — 🏆 lightgbm

- 🏆 **Champion : lightgbm** | IC = 0.0054 | IR = 0.15 | Score composite = 0.925 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0054
- **Decile Spread** : 0.0009
- **Nb Features** : 144

#### 🔝 Feature Importance — Top 10 / Bottom 10

| # | Top Feature | Top Imp. | Bottom Feature | Bottom Imp. |
|---:|:---|---:|:---|---:|
| 1 | `momentum_250` | 204.9 | `momentum_5_xs_rank` | 0.0 |
| 2 | `rolling_volatility_60` | 145.2 | `rsi_2_xs_rank` | 0.0 |
| 3 | `vol_ratio_20_60_xs_rank` | 120.8 | `dist_to_sma_5d_xs_rank` | 0.0 |
| 4 | `vol_ratio_20_60` | 114.6 | `volume_ratio_5_xs_rank` | 0.0 |
| 5 | `sma250_distance_xs_rank` | 113.6 | `volume_ratio_20_xs_rank` | 0.0 |
| 6 | `rolling_volatility_60_xs_rank` | 82.5 | `intraday_range_xs_rank` | 0.0 |
| 7 | `momentum_250_xs_rank` | 77.2 | `overnight_gap_xs_rank` | 0.0 |
| 8 | `rolling_volatility_60_zscore` | 59.1 | `close_to_vwap_xs_rank` | 0.0 |
| 9 | `sma50_minus_sma200` | 56.9 | `decay_5_10_xs_rank` | 0.0 |
| 10 | `rolling_volatility_20_xs_rank` | 52.6 | `gap_fade_xs_rank` | 0.0 |

#### 📅 Détail par split — 🏆 lightgbm

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (lightgbm) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-11-28 | 2019-01-02 → 2019-06-03  |         143788 |        32930 |           -0.0356924 |    -0.0356924 |   -0.0333711  |
|       2 | 2016-12-29 → 2019-11-29 | 2020-01-02 → 2020-06-02  |         223664 |        34449 |            0.0507668 |     0.0507668 |   -0.0574639  |
|       3 | 2016-12-29 → 2020-11-30 | 2020-12-31 → 2021-06-02  |         307301 |        35858 |           -0.0379745 |    -0.0379745 |   -0.0163336  |
|       4 | 2016-12-29 → 2021-11-30 | 2021-12-31 → 2022-06-01  |         394440 |        37965 |            0.0421778 |     0.0421778 |    0.00841171 |
|       5 | 2016-12-29 → 2022-11-30 | 2023-01-03 → 2023-06-02  |         487696 |        40627 |           -0.0192111 |    -0.0192111 |    0.0331616  |
|       6 | 2016-12-29 → 2023-12-01 | 2024-01-04 → 2024-06-04  |         585281 |        40957 |            0.0324093 |     0.0324093 |    0.0397852  |

- IC Moyen = 0.0054  |  IC Std = 0.0372  |  IC Min = -0.0380  |  IC Max = 0.0508


## 🧪 Backtest Stratégies — Global Rank (H10 + H5)

| Variante | Score relatif |
|----------|---------------|
| V1 — H10 seul | 🏆 référence |
| V2 — H10 + H5 rising | -1.1% |
| V3 — H10 + H5 < 0.35 | -31.1% |
| V4 — H10 + top 3 horizons ↑ (H3,H10,H5) | -15.2% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H10 seul, V2 = H10 + H5 rising, V3 = H10 + H5 < 0.35 (contrarian). V4 = H10 + top 3 horizons ↑ (H3,H10,H5).

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
|         3 |      0.331 |      0.489 |     0.503 |    0.502  |
|         5 |      0.33  |      0.475 |     0.514 |    0.5017 |
|        10 |      0.328 |      0.473 |     0.511 |    0.5014 |
|        15 |      0.329 |      0.474 |     0.512 |    0.5019 |
|        20 |      0.327 |      0.474 |     0.508 |    0.5003 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.332 |          0.508 |             0 |         0.489 |
| catboost     | test         |           11 |          0.331 |          0.523 |             0 |         0.468 |
| catboost     | wf           |           11 |          0.328 |          0.475 |             0 |         0.51  |
| lightgbm     | val          |           11 |          0.331 |          0.506 |             0 |         0.486 |
| lightgbm     | test         |           11 |          0.328 |          0.511 |             0 |         0.474 |
| lightgbm     | wf           |           11 |          0.329 |          0.478 |             0 |         0.51  |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| catboost     | test         |           11 |               51.925 |                   0 |              48.075 |               53.54  |               0     |              46.46  |
| catboost     | wf           |           11 |               51.407 |                   0 |              48.593 |               45.196 |               0     |              54.804 |
| lightgbm     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| lightgbm     | test         |           11 |               51.925 |                   0 |              48.075 |               51.593 |               0     |              48.407 |
| lightgbm     | wf           |           11 |               51.407 |                   0 |              48.593 |               45.536 |               0     |              54.464 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.20-0.29            |            1 |
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol           |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples |      0.352 |     0.553 |      0.504 |         0 |
| Consumer Staples |      0.349 |     0.55  |      0.498 |         0 |
| Consumer Staples |      0.348 |     0.553 |      0.491 |         0 |
| Consumer Staples |      0.343 |     0.56  |      0.468 |         0 |
| Health Care      |      0.341 |     0.53  |      0.493 |         0 |
| Health Care      |      0.34  |     0.536 |      0.484 |         0 |
| Health Care      |      0.339 |     0.528 |      0.49  |         0 |
| Real Estate      |      0.337 |     0.518 |      0.492 |         0 |
| Industrials      |      0.336 |     0.505 |      0.504 |         0 |
| Industrials      |      0.336 |     0.507 |      0.502 |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol    |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:----------|-----------:|----------:|-----------:|----------:|
| Energy    |      0.297 |     0.428 |      0.464 |         0 |
| Energy    |      0.3   |     0.45  |      0.45  |         0 |
| Energy    |      0.308 |     0.441 |      0.482 |         0 |
| Utilities |      0.309 |     0.57  |      0.357 |         0 |
| Materials |      0.311 |     0.467 |      0.467 |         0 |
| Utilities |      0.314 |     0.561 |      0.38  |         0 |
| Utilities |      0.316 |     0.545 |      0.403 |         0 |
| Energy    |      0.317 |     0.473 |      0.477 |         0 |
| Materials |      0.317 |     0.47  |      0.48  |         0 |
| Materials |      0.32  |     0.473 |      0.486 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    1.0648 |        0.4991 |
| catboost     | test         |           11 |    1.0868 |        0.4988 |
| catboost     | wf           |           11 |    1.0436 |        0.5011 |
| lightgbm     | val          |           11 |    1.082  |        0.4964 |
| lightgbm     | test         |           11 |    1.1086 |        0.4953 |
| lightgbm     | wf           |           11 |    1.0626 |        0.5019 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol           |   dir_acc |    mse |
|:-------------|:-----------------|----------:|-------:|
| lightgbm     | Consumer Staples |    0.5454 | 0.9128 |
| lightgbm     | Consumer Staples |    0.5385 | 0.9093 |
| catboost     | Consumer Staples |    0.5329 | 0.8886 |
| catboost     | Consumer Staples |    0.5273 | 0.8962 |
| catboost     | Consumer Staples |    0.5263 | 0.9152 |
| lightgbm     | Consumer Staples |    0.521  | 0.9306 |
| catboost     | Consumer Staples |    0.5194 | 0.9398 |
| lightgbm     | Industrials      |    0.5172 | 1.0121 |
| lightgbm     | Industrials      |    0.5166 | 1.0436 |
| lightgbm     | Industrials      |    0.514  | 0.9834 |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Materials              |    0.4707 | 1.0979 |
| catboost     | Communication Services |    0.473  | 1.0529 |
| catboost     | Communication Services |    0.4793 | 1.0247 |
| lightgbm     | Materials              |    0.4799 | 1.0874 |
| lightgbm     | Communication Services |    0.4844 | 1.0798 |
| catboost     | Materials              |    0.486  | 1.0433 |
| catboost     | Communication Services |    0.4861 | 1.01   |
| lightgbm     | Energy                 |    0.4869 | 0.9802 |
| catboost     | Utilities              |    0.487  | 1.3268 |
| lightgbm     | Materials              |    0.4874 | 0.9513 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.319 |      0.437 |         0 |     0.52  | —           |     7.7 |      15   |            11 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.332 |      0.454 |         0 |     0.542 | —           |    19.1 |      25.7 |            11 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.321 |      0.447 |         0 |     0.516 | —           |     9.8 |      18.8 |            11 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.34  |      0.497 |         0 |     0.524 | —           |     0.1 |      24.9 |            11 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.316 |      0.489 |         0 |     0.46  | —           |     9   |      15.1 |            11 |
|       5 | 2024-09-03  | 2025-03-05 | 🟢 Bull           |      0.327 |      0.502 |         0 |     0.48  | —           |     5.6 |      17.4 |            11 |
