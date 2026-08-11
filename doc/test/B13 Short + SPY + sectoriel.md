# Diagnostic ML — Batch `model-factory-20260810213112-95c7d0`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260810213112-95c7d0`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : B13 Short + SPY + sectoriel
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0144
- **📈 IC IR (Stabilité)** : 0.84  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0065 H5=0.0158 H10=0.0225 H15=0.0181 H20=0.0191
- **🏆 Champion Global** : catboost (H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — score composite 55% IC + 30% IR + 15% positifs
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-10 21:31:12
- **Terminé le** : 2026-08-10 23:01:20
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-short-score --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --enable-cross-sectional --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B13 Short + SPY + sectoriel"
```

## 🌐 Global Ranking — Détails par Horizon

Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symboles, 6 splits walk-forward, 265689 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |    IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits | 🏆 Champion   |   Score |   IC catboost |   IR catboost |   IC lightgbm |   IR lightgbm |
|:----------|-----------:|--------:|----------------:|--------------:|------------:|:--------------|--------:|--------------:|--------------:|--------------:|--------------:|
| H3        | 0.00994872 |    0.93 |      0.00645903 |           159 |           6 | catboost      |   0.95  |        0.0099 |          0.93 |        0.0045 |          0.23 |
| H5        | 0.017585   |    1    |      0.0158469  |           177 |           6 | catboost      |   0.975 |        0.0176 |          1    |        0.0076 |          0.51 |
| H10       | 0.0189451  |    1.26 |      0.0225112  |           177 |           6 | catboost      |   0.975 |        0.0189 |          1.26 |        0.0114 |          0.62 |
| H15       | 0.0119271  |    0.66 |      0.0180935  |           177 |           6 | catboost      |   0.95  |        0.0119 |          0.66 |        0.0066 |          0.48 |
| H20       | 0.0135715  |    0.66 |      0.019131   |           177 |           6 | catboost      |   0.925 |        0.0136 |          0.66 |       -0.0044 |         -0.52 |


🏆 **Meilleur horizon : H10** — sélectionné par score composite 55% IC + 30% IR + 15% Positive Split  |  H3=0.6108  H5=0.8733  H10=0.9750  H15=0.6037  H20=0.6256
### Horizon H3 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0099 | IR = 0.93 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0099
- **Decile Spread** : 0.0065
- **Nb Features** : 159

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |          -0.00153104 |    0.00496924 |   -0.00153104 |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |           0.0247603  |    0.040668   |    0.0247603  |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |           0.0228947  |    0.0108173  |    0.0228947  |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |          -0.0023406  |   -0.0201666  |   -0.0023406  |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |           0.0100146  |   -0.0139209  |    0.0100146  |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |           0.0058945  |    0.00477547 |    0.0058945  |

- IC Moyen = 0.0099  |  IC Std = 0.0107  |  IC Min = -0.0023  |  IC Max = 0.0248

### Horizon H5 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0176 | IR = 1.00 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0176
- **Decile Spread** : 0.0158
- **Nb Features** : 177

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |           0.00302654 |   0.0204932   |    0.00302654 |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |           0.046806   |   0.0326556   |    0.046806   |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |           0.0245999  |  -0.00454859  |    0.0245999  |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |          -0.00872391 |  -0.0105298   |   -0.00872391 |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |           0.0249517  |   0.00722058  |    0.0249517  |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |           0.01485    |   0.000119249 |    0.01485    |

- IC Moyen = 0.0176  |  IC Std = 0.0176  |  IC Min = -0.0087  |  IC Max = 0.0468

### Horizon H10 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0189 | IR = 1.26 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0189
- **Decile Spread** : 0.0225
- **Nb Features** : 177

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |           0.00521759 |    0.0333491  |    0.00521759 |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |           0.0374619  |    0.0287713  |    0.0374619  |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |           0.0314146  |    0.0209696  |    0.0314146  |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |          -0.00518662 |   -0.00267764 |   -0.00518662 |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |           0.0283     |    0.00648985 |    0.0283     |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |           0.0164633  |   -0.0187258  |    0.0164633  |

- IC Moyen = 0.0189  |  IC Std = 0.0151  |  IC Min = -0.0052  |  IC Max = 0.0375

### Horizon H15 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0119 | IR = 0.66 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0119
- **Decile Spread** : 0.0181
- **Nb Features** : 177

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |         -0.00409271  |     0.0175412 |  -0.00409271  |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |          0.0185173   |     0.016326  |   0.0185173   |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |          0.0390033   |     0.0179382 |   0.0390033   |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |         -0.0112282   |     0.013786  |  -0.0112282   |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |          0.0283847   |    -0.0154564 |   0.0283847   |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |          0.000978349 |    -0.010329  |   0.000978349 |

- IC Moyen = 0.0119  |  IC Std = 0.0181  |  IC Min = -0.0112  |  IC Max = 0.0390

### Horizon H20 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0136 | IR = 0.66 | Score composite = 0.925 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0136
- **Decile Spread** : 0.0191
- **Nb Features** : 177

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |          -0.00913489 |   -0.00223828 |   -0.00913489 |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |           0.017919   |   -0.00275068 |    0.017919   |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |           0.0432527  |    0.00186273 |    0.0432527  |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |          -0.00634561 |   -0.0131391  |   -0.00634561 |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |           0.0368106  |    0.00720676 |    0.0368106  |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |          -0.00107282 |   -0.0175243  |   -0.00107282 |

- IC Moyen = 0.0136  |  IC Std = 0.0207  |  IC Min = -0.0091  |  IC Max = 0.0433


## 🧪 Backtest Stratégies — Global Rank (H10 + H5)

| Variante | Score relatif |
|----------|---------------|
| V1 — H10 seul | 🏆 référence |
| V2 — H10 + H5 rising | -16.9% |
| V3 — H10 + H5 < 0.35 | -47.1% |
| V4 — H10 + top 3 horizons ↑ (H10,H5,H20) | -17.7% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H10 seul, V2 = H10 + H5 rising, V3 = H10 + H5 < 0.35 (contrarian). V4 = H10 + top 3 horizons ↑ (H10,H5,H20).

---

## 🔵 Per-Symbol / Per-Sector — Métriques d'entraînement

### 🏆 Sélection du champion

✅ **Tout va bien** — 11 champions sélectionnés automatiquement sur 11 symboles.

### 📊 Champions par modèle

| model_name   |   nb_symbols |
|:-------------|-------------:|
| lightgbm     |            7 |
| catboost     |            4 |

## 📊 Métriques par Horizon (WF)

|   Horizon |   F1 macro |   F1 short |   F1 long |   Dir Acc |
|----------:|-----------:|-----------:|----------:|----------:|
|         3 |      0.331 |      0.494 |     0.499 |    0.5021 |
|         5 |      0.329 |      0.481 |     0.505 |    0.5004 |
|        10 |      0.329 |      0.489 |     0.499 |    0.5027 |
|        15 |      0.329 |      0.488 |     0.5   |    0.5033 |
|        20 |      0.329 |      0.487 |     0.499 |    0.5027 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.332 |          0.508 |             0 |         0.489 |
| catboost     | test         |           11 |          0.333 |          0.518 |             0 |         0.481 |
| catboost     | wf           |           11 |          0.329 |          0.485 |             0 |         0.5   |
| lightgbm     | val          |           11 |          0.332 |          0.508 |             0 |         0.489 |
| lightgbm     | test         |           11 |          0.33  |          0.506 |             0 |         0.485 |
| lightgbm     | wf           |           11 |          0.33  |          0.49  |             0 |         0.501 |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| catboost     | test         |           11 |               51.925 |                   0 |              48.075 |               51.728 |               0     |              48.272 |
| catboost     | wf           |           11 |               51.407 |                   0 |              48.593 |               47.235 |               0     |              52.765 |
| lightgbm     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| lightgbm     | test         |           11 |               51.925 |                   0 |              48.075 |               50.079 |               0     |              49.921 |
| lightgbm     | wf           |           11 |               51.407 |                   0 |              48.593 |               47.642 |               0     |              52.358 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.20-0.29            |            1 |
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol           |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples |      0.358 |     0.543 |      0.531 |         0 |
| Consumer Staples |      0.354 |     0.534 |      0.529 |         0 |
| Health Care      |      0.346 |     0.505 |      0.534 |         0 |
| Industrials      |      0.346 |     0.509 |      0.529 |         0 |
| Consumer Staples |      0.346 |     0.519 |      0.519 |         0 |
| Industrials      |      0.344 |     0.5   |      0.532 |         0 |
| Industrials      |      0.342 |     0.503 |      0.523 |         0 |
| Health Care      |      0.341 |     0.511 |      0.512 |         0 |
| Health Care      |      0.341 |     0.494 |      0.527 |         0 |
| Financials       |      0.339 |     0.496 |      0.522 |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Energy                 |      0.296 |     0.453 |      0.435 |         0 |
| Energy                 |      0.303 |     0.48  |      0.429 |         0 |
| Materials              |      0.304 |     0.468 |      0.445 |         0 |
| Energy                 |      0.313 |     0.467 |      0.471 |         0 |
| Energy                 |      0.315 |     0.46  |      0.484 |         0 |
| Communication Services |      0.316 |     0.495 |      0.452 |         0 |
| Utilities              |      0.316 |     0.535 |      0.412 |         0 |
| Materials              |      0.317 |     0.465 |      0.487 |         0 |
| Materials              |      0.319 |     0.462 |      0.494 |         0 |
| Utilities              |      0.32  |     0.562 |      0.397 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    1.0618 |        0.4988 |
| catboost     | test         |           11 |    1.0811 |        0.5034 |
| catboost     | wf           |           11 |    1.0471 |        0.5017 |
| lightgbm     | val          |           11 |    1.0751 |        0.4989 |
| lightgbm     | test         |           11 |    1.1071 |        0.4977 |
| lightgbm     | wf           |           11 |    1.0682 |        0.5027 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol           |   dir_acc |    mse |
|:-------------|:-----------------|----------:|-------:|
| lightgbm     | Consumer Staples |    0.5405 | 0.9197 |
| lightgbm     | Consumer Staples |    0.5333 | 0.9137 |
| catboost     | Consumer Staples |    0.5318 | 0.8997 |
| catboost     | Consumer Staples |    0.5228 | 0.8969 |
| catboost     | Consumer Staples |    0.5211 | 0.9296 |
| lightgbm     | Industrials      |    0.5205 | 1.034  |
| lightgbm     | Consumer Staples |    0.5205 | 0.9412 |
| lightgbm     | Utilities        |    0.5203 | 1.348  |
| catboost     | Health Care      |    0.5202 | 1.0527 |
| lightgbm     | Industrials      |    0.5181 | 1.0145 |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Materials              |    0.4625 | 1.1046 |
| catboost     | Materials              |    0.4774 | 1.0476 |
| catboost     | Materials              |    0.4778 | 1.0088 |
| lightgbm     | Materials              |    0.4799 | 1.0755 |
| catboost     | Communication Services |    0.483  | 1.0355 |
| lightgbm     | Energy                 |    0.4834 | 1.0664 |
| lightgbm     | Materials              |    0.4847 | 1.0216 |
| lightgbm     | Energy                 |    0.4848 | 1.0744 |
| catboost     | Utilities              |    0.4852 | 1.1722 |
| catboost     | Materials              |    0.4857 | 1.0418 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.324 |      0.444 |         0 |     0.528 | —           |     7.7 |      15   |            11 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.336 |      0.47  |         0 |     0.537 | —           |    19.1 |      25.7 |            11 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.326 |      0.51  |         0 |     0.467 | —           |     9.8 |      18.8 |            11 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.342 |      0.516 |         0 |     0.511 | —           |     0.1 |      24.9 |            11 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.322 |      0.517 |         0 |     0.449 | —           |     9   |      15.1 |            11 |
|       5 | 2024-09-03  | 2025-03-05 | 🟢 Bull           |      0.326 |      0.478 |         0 |     0.499 | —           |     5.6 |      17.4 |            11 |
