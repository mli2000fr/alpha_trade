# Diagnostic ML — Batch `model-factory-20260812190010-748dd9`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260812190010-748dd9`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : B34 scores screnner + YetiRank
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0151
- **📈 IC IR (Stabilité)** : 0.78  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0133 H5=0.0128 H10=0.0110 H15=0.0044 H20=0.0093
- **🏆 Champion Global** : catboost (H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — score composite 55% IC + 30% IR + 15% positifs
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-12 19:00:11
- **Terminé le** : 2026-08-13 01:03:34
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-screener-scores --no-include-score-components --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --enable-cross-sectional --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B34 scores screnner + YetiRank"
```

## 🌐 Global Ranking — Détails par Horizon

Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symboles, 6 splits walk-forward, 265689 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |   IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits | 🏆 Champion   |   Score |   IC catboost |   IR catboost |   IC lightgbm |   IR lightgbm |
|:----------|----------:|--------:|----------------:|--------------:|------------:|:--------------|--------:|--------------:|--------------:|--------------:|--------------:|
| H3        | 0.0150382 |    0.78 |      0.0132711  |           181 |           6 | catboost      |   0.95  |        0.015  |          0.78 |        0.0005 |          0.02 |
| H5        | 0.0171709 |    0.98 |      0.0127606  |           199 |           6 | catboost      |   0.975 |        0.0172 |          0.98 |        0.0017 |          0.21 |
| H10       | 0.0186625 |    1.01 |      0.0110492  |           199 |           6 | catboost      |   0.975 |        0.0187 |          1.01 |        0.0046 |          0.29 |
| H15       | 0.0146422 |    0.78 |      0.00436374 |           199 |           6 | catboost      |   0.975 |        0.0146 |          0.78 |        0.0068 |          0.28 |
| H20       | 0.0102226 |    0.46 |      0.00925735 |           199 |           6 | catboost      |   0.95  |        0.0102 |          0.46 |       -0.0041 |         -0.17 |


🏆 **Meilleur horizon : H10** — sélectionné par score composite 55% IC + 30% IR + 15% Positive Split  |  H3=0.7745  H5=0.9209  H10=0.9750  H15=0.7888  H20=0.5379
### Horizon H3 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0150 | IR = 0.78 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0150
- **Decile Spread** : 0.0133
- **Nb Features** : 181

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |          -0.00220644 |    0.0057355  |   -0.00220644 |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |           0.0404893  |    0.0406157  |    0.0404893  |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |           0.0237988  |   -0.00453764 |    0.0237988  |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |          -0.0160614  |   -0.0235359  |   -0.0160614  |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |           0.0134809  |   -0.00257868 |    0.0134809  |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |           0.0307277  |   -0.0128193  |    0.0307277  |

- IC Moyen = 0.0150  |  IC Std = 0.0193  |  IC Min = -0.0161  |  IC Max = 0.0405

### Horizon H5 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0172 | IR = 0.98 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0172
- **Decile Spread** : 0.0128
- **Nb Features** : 199

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |            0.0171112 |    0.0139296  |     0.0171112 |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |            0.0346742 |    0.011149   |     0.0346742 |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |            0.0197855 |    0.00197863 |     0.0197855 |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |           -0.0185588 |   -0.00342222 |    -0.0185588 |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |            0.0165034 |   -0.00705074 |     0.0165034 |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |            0.03351   |   -0.00630442 |     0.03351   |

- IC Moyen = 0.0172  |  IC Std = 0.0176  |  IC Min = -0.0186  |  IC Max = 0.0347

### Horizon H10 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0187 | IR = 1.01 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0187
- **Decile Spread** : 0.0110
- **Nb Features** : 199

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |           0.0310043  |    0.0177434  |    0.0310043  |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |           0.0253936  |    0.0273259  |    0.0253936  |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |           0.00565546 |   -0.0190108  |    0.00565546 |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |          -0.0167095  |   -0.0024438  |   -0.0167095  |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |           0.0340485  |    0.0112259  |    0.0340485  |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |           0.0325824  |   -0.00747753 |    0.0325824  |

- IC Moyen = 0.0187  |  IC Std = 0.0185  |  IC Min = -0.0167  |  IC Max = 0.0340

### Horizon H15 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0146 | IR = 0.78 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0146
- **Decile Spread** : 0.0044
- **Nb Features** : 199

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |          0.0344433   |    0.00930478 |   0.0344433   |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |          0.00900447  |    0.0582601  |   0.00900447  |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |          0.000200996 |   -0.00619331 |   0.000200996 |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |         -0.0163803   |   -0.00772495 |  -0.0163803   |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |          0.0272753   |    0.0018587  |   0.0272753   |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |          0.0333097   |   -0.0146354  |   0.0333097   |

- IC Moyen = 0.0146  |  IC Std = 0.0187  |  IC Min = -0.0164  |  IC Max = 0.0344

### Horizon H20 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0102 | IR = 0.46 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0102
- **Decile Spread** : 0.0093
- **Nb Features** : 199

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |          0.0145327   |   -0.0316154  |   0.0145327   |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |          8.13058e-05 |    0.0427649  |   8.13058e-05 |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |         -0.000156491 |   -0.0271875  |  -0.000156491 |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |         -0.0260782   |   -0.0040784  |  -0.0260782   |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |          0.0408998   |   -0.00222277 |   0.0408998   |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |          0.0320565   |   -0.00244623 |   0.0320565   |

- IC Moyen = 0.0102  |  IC Std = 0.0222  |  IC Min = -0.0261  |  IC Max = 0.0409


## 🧪 Backtest Stratégies — Global Rank (H10 + H5)

| Variante | Score relatif |
|----------|---------------|
| V1 — H10 seul | 🏆 référence |
| V2 — H10 + H5 rising | -13.4% |
| V3 — H10 + H5 < 0.35 | -28.8% |
| V4 — H10 + top 3 horizons ↑ (H10,H5,H15) | -21.6% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H10 seul, V2 = H10 + H5 rising, V3 = H10 + H5 < 0.35 (contrarian). V4 = H10 + top 3 horizons ↑ (H10,H5,H15).

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
|         3 |      0.332 |      0.496 |     0.499 |    0.5029 |
|         5 |      0.329 |      0.484 |     0.503 |    0.5009 |
|        10 |      0.328 |      0.489 |     0.496 |    0.5007 |
|        15 |      0.328 |      0.488 |     0.498 |    0.5012 |
|        20 |      0.326 |      0.485 |     0.494 |    0.4985 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.331 |          0.506 |             0 |         0.487 |
| catboost     | test         |           11 |          0.333 |          0.52  |             0 |         0.478 |
| catboost     | wf           |           11 |          0.328 |          0.486 |             0 |         0.498 |
| lightgbm     | val          |           11 |          0.333 |          0.509 |             0 |         0.489 |
| lightgbm     | test         |           11 |          0.33  |          0.507 |             0 |         0.482 |
| lightgbm     | wf           |           11 |          0.33  |          0.491 |             0 |         0.498 |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               51.914 |                   0 |              48.086 |               49.998 |               0.004 |              49.998 |
| catboost     | test         |           11 |               51.941 |                   0 |              48.059 |               52.098 |               0     |              47.902 |
| catboost     | wf           |           11 |               51.566 |                   0 |              48.434 |               47.434 |               0     |              52.566 |
| lightgbm     | val          |           11 |               51.914 |                   0 |              48.086 |               49.998 |               0.004 |              49.998 |
| lightgbm     | test         |           11 |               51.941 |                   0 |              48.059 |               50.404 |               0     |              49.596 |
| lightgbm     | wf           |           11 |               51.566 |                   0 |              48.434 |               47.782 |               0     |              52.218 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol           |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples |      0.349 |     0.533 |      0.514 |         0 |
| Financials       |      0.341 |     0.481 |      0.541 |         0 |
| Industrials      |      0.341 |     0.495 |      0.527 |         0 |
| Industrials      |      0.341 |     0.498 |      0.524 |         0 |
| Health Care      |      0.34  |     0.488 |      0.532 |         0 |
| Industrials      |      0.34  |     0.492 |      0.528 |         0 |
| Consumer Staples |      0.34  |     0.542 |      0.478 |         0 |
| Health Care      |      0.34  |     0.49  |      0.529 |         0 |
| Industrials      |      0.339 |     0.5   |      0.517 |         0 |
| Financials       |      0.339 |     0.505 |      0.51  |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol      |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:------------|-----------:|----------:|-----------:|----------:|
| Materials   |      0.304 |     0.464 |      0.448 |         0 |
| Energy      |      0.309 |     0.494 |      0.434 |         0 |
| Energy      |      0.31  |     0.501 |      0.43  |         0 |
| Energy      |      0.315 |     0.496 |      0.448 |         0 |
| Energy      |      0.316 |     0.496 |      0.451 |         0 |
| Materials   |      0.317 |     0.472 |      0.478 |         0 |
| Real Estate |      0.32  |     0.439 |      0.521 |         0 |
| Utilities   |      0.32  |     0.568 |      0.392 |         0 |
| Utilities   |      0.321 |     0.562 |      0.401 |         0 |
| Materials   |      0.321 |     0.472 |      0.492 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    1.0573 |        0.4968 |
| catboost     | test         |           11 |    1.0616 |        0.5037 |
| catboost     | wf           |           11 |    1.0375 |        0.5003 |
| lightgbm     | val          |           11 |    1.0689 |        0.4994 |
| lightgbm     | test         |           11 |    1.0879 |        0.4981 |
| lightgbm     | wf           |           11 |    1.0592 |        0.5014 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Consumer Staples       |    0.5298 | 0.917  |
| catboost     | Consumer Staples       |    0.5267 | 0.9198 |
| lightgbm     | Consumer Staples       |    0.5241 | 0.9483 |
| catboost     | Consumer Staples       |    0.5164 | 0.9105 |
| lightgbm     | Financials             |    0.5148 | 0.9962 |
| catboost     | Industrials            |    0.5141 | 1      |
| lightgbm     | Industrials            |    0.5133 | 1.0383 |
| catboost     | Industrials            |    0.5131 | 0.9742 |
| lightgbm     | Industrials            |    0.513  | 0.9764 |
| catboost     | Information Technology |    0.5129 | 0.9929 |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Materials              |    0.4601 | 1.0731 |
| lightgbm     | Energy                 |    0.4726 | 1.0541 |
| catboost     | Materials              |    0.4737 | 1.0255 |
| lightgbm     | Materials              |    0.4804 | 1.0477 |
| catboost     | Materials              |    0.4822 | 1.0209 |
| catboost     | Materials              |    0.4834 | 0.9795 |
| catboost     | Utilities              |    0.4839 | 1.1661 |
| catboost     | Communication Services |    0.4843 | 1.0306 |
| catboost     | Consumer Discretionary |    0.4849 | 0.9607 |
| lightgbm     | Energy                 |    0.4865 | 1.0238 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.324 |      0.451 |         0 |     0.521 | —           |     7.7 |      15   |            11 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.335 |      0.5   |         0 |     0.505 | —           |    19.1 |      25.7 |            11 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.32  |      0.494 |         0 |     0.465 | —           |     9.8 |      18.8 |            11 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.335 |      0.487 |         0 |     0.519 | —           |     0.1 |      24.9 |            11 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.322 |      0.514 |         0 |     0.454 | —           |     9   |      15.1 |            11 |
|       5 | 2024-09-03  | 2025-03-05 | 🟢 Bull           |      0.328 |      0.475 |         0 |     0.508 | —           |     5.6 |      17.4 |            11 |
