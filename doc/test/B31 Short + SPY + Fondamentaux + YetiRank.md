# Diagnostic ML — Batch `model-factory-20260812185524-904666`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260812185524-904666`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : B31 Short + SPY + Fondamentaux + YetiRank
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0146
- **📈 IC IR (Stabilité)** : 0.66  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0155 H5=0.0152 H10=0.0080 H15=0.0147 H20=0.0117
- **🏆 Champion Global** : catboost (H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — score composite 55% IC + 30% IR + 15% positifs
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-12 18:55:25
- **Terminé le** : 2026-08-13 00:54:02
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function YetiRank --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-short-score --include-fundamentals --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B31 Short + SPY + Fondamentaux + YetiRank"
```

## 🌐 Global Ranking — Détails par Horizon

Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symboles, 6 splits walk-forward, 265689 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |   IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits | 🏆 Champion   |   Score |   IC catboost |   IR catboost |   IC lightgbm |   IR lightgbm |
|:----------|----------:|--------:|----------------:|--------------:|------------:|:--------------|--------:|--------------:|--------------:|--------------:|--------------:|
| H3        | 0.0156982 |    0.86 |      0.0154816  |           144 |           6 | catboost      |   0.975 |        0.0157 |          0.86 |        0.0098 |          0.68 |
| H5        | 0.016777  |    0.86 |      0.0151727  |           156 |           6 | catboost      |   0.975 |        0.0168 |          0.86 |        0.0095 |          0.54 |
| H10       | 0.0134813 |    0.64 |      0.00799578 |           156 |           6 | catboost      |   0.975 |        0.0135 |          0.64 |       -0.0005 |         -0.02 |
| H15       | 0.01384   |    0.57 |      0.014659   |           156 |           6 | catboost      |   0.975 |        0.0138 |          0.57 |        0.0047 |          0.22 |
| H20       | 0.0130242 |    0.51 |      0.0117243  |           156 |           6 | catboost      |   0.975 |        0.013  |          0.51 |        0.0081 |          0.34 |


🏆 **Meilleur horizon : H5** — sélectionné par score composite 55% IC + 30% IR + 15% Positive Split  |  H3=0.9377  H5=0.9750  H10=0.7896  H15=0.7786  H20=0.7279
### Horizon H3 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0157 | IR = 0.86 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0157
- **Decile Spread** : 0.0155
- **Nb Features** : 144

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |           0.00076576 |   0.0171881   |    0.00076576 |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |           0.0408374  |   0.0328924   |    0.0408374  |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |           0.0200235  |  -0.000468545 |    0.0200235  |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |          -0.014385   |  -0.0116634   |   -0.014385   |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |           0.0157682  |   0.00396841  |    0.0157682  |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |           0.0311796  |   0.0167243   |    0.0311796  |

- IC Moyen = 0.0157  |  IC Std = 0.0183  |  IC Min = -0.0144  |  IC Max = 0.0408

### Horizon H5 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0168 | IR = 0.86 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0168
- **Decile Spread** : 0.0152
- **Nb Features** : 156

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |            0.0229468 |    0.00480752 |     0.0229468 |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |            0.0347943 |    0.0483918  |     0.0347943 |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |            0.0230185 |   -0.00382306 |     0.0230185 |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |           -0.0256724 |    0.00562423 |    -0.0256724 |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |            0.0229551 |   -0.00234295 |     0.0229551 |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |            0.0226198 |    0.00446037 |     0.0226198 |

- IC Moyen = 0.0168  |  IC Std = 0.0195  |  IC Min = -0.0257  |  IC Max = 0.0348

### Horizon H10 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0135 | IR = 0.64 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0135
- **Decile Spread** : 0.0080
- **Nb Features** : 156

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |            0.0341966 |    0.0314655  |     0.0341966 |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |            0.0199664 |    0.0273357  |     0.0199664 |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |            0.0205465 |    0.00409085 |     0.0205465 |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |           -0.0321099 |   -0.00820275 |    -0.0321099 |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |            0.0178524 |   -0.0263824  |     0.0178524 |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |            0.0204359 |   -0.0314395  |     0.0204359 |

- IC Moyen = 0.0135  |  IC Std = 0.0211  |  IC Min = -0.0321  |  IC Max = 0.0342

### Horizon H15 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0138 | IR = 0.57 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0138
- **Decile Spread** : 0.0147
- **Nb Features** : 156

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |            0.0327443 |   0.0127431   |     0.0327443 |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |            0.023448  |   0.0443041   |     0.023448  |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |            0.0173135 |  -0.0128377   |     0.0173135 |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |           -0.039107  |  -0.0209113   |    -0.039107  |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |            0.0229089 |   0.00423556  |     0.0229089 |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |            0.0257325 |   0.000405954 |     0.0257325 |

- IC Moyen = 0.0138  |  IC Std = 0.0241  |  IC Min = -0.0391  |  IC Max = 0.0327

### Horizon H20 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0130 | IR = 0.51 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0130
- **Decile Spread** : 0.0117
- **Nb Features** : 156

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-28 | 2019-01-02 → 2019-07-01  |         149998 |        39253 |            0.0456049 |    0.0457006  |     0.0456049 |
|       2 | 2016-12-29 → 2019-12-30 | 2020-01-02 → 2020-06-30  |         230196 |        41108 |            0.0064012 |    0.0338084  |     0.0064012 |
|       3 | 2016-12-29 → 2020-12-29 | 2020-12-31 → 2021-06-30  |         314095 |        42763 |            0.0213768 |   -0.0224236  |     0.0213768 |
|       4 | 2016-12-29 → 2021-12-29 | 2021-12-31 → 2022-06-30  |         401593 |        45416 |           -0.0377532 |   -0.00192759 |    -0.0377532 |
|       5 | 2016-12-29 → 2022-12-29 | 2023-01-03 → 2023-07-03  |         495408 |        48367 |            0.0282348 |   -0.00106102 |     0.0282348 |
|       6 | 2016-12-29 → 2024-01-02 | 2024-01-04 → 2024-07-03  |         593081 |        48782 |            0.014281  |   -0.00524104 |     0.014281  |

- IC Moyen = 0.0130  |  IC Std = 0.0258  |  IC Min = -0.0378  |  IC Max = 0.0456


## 🧪 Backtest Stratégies — Global Rank (H5 seul)

| Variante | Score relatif |
|----------|---------------|
| V1 — H5 seul | 🏆 référence |
| V4 — H5 + top 3 horizons ↑ (H5,H3,H10) | -32.4% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H5 seul (V2/V3 non calculés — H5 est déjà le meilleur horizon). V4 = H5 + top 3 horizons ↑ (H5,H3,H10).

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
|         5 |      0.33  |      0.482 |     0.507 |    0.5012 |
|        10 |      0.328 |      0.483 |     0.501 |    0.501  |
|        15 |      0.327 |      0.48  |     0.502 |    0.502  |
|        20 |      0.326 |      0.481 |     0.498 |    0.5005 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.332 |          0.508 |             0 |         0.488 |
| catboost     | test         |           11 |          0.33  |          0.522 |             0 |         0.466 |
| catboost     | wf           |           11 |          0.328 |          0.482 |             0 |         0.501 |
| lightgbm     | val          |           11 |          0.333 |          0.509 |             0 |         0.489 |
| lightgbm     | test         |           11 |          0.33  |          0.513 |             0 |         0.477 |
| lightgbm     | wf           |           11 |          0.329 |          0.486 |             0 |         0.501 |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| catboost     | test         |           11 |               51.925 |                   0 |              48.075 |               53.636 |               0     |              46.364 |
| catboost     | wf           |           11 |               51.407 |                   0 |              48.593 |               46.849 |               0     |              53.151 |
| lightgbm     | val          |           11 |               51.936 |                   0 |              48.064 |               49.997 |               0.006 |              49.997 |
| lightgbm     | test         |           11 |               51.925 |                   0 |              48.075 |               51.676 |               0     |              48.324 |
| lightgbm     | wf           |           11 |               51.407 |                   0 |              48.593 |               47.117 |               0     |              52.883 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol           |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples |      0.347 |     0.535 |      0.506 |         0 |
| Consumer Staples |      0.346 |     0.529 |      0.508 |         0 |
| Industrials      |      0.345 |     0.511 |      0.525 |         0 |
| Consumer Staples |      0.345 |     0.533 |      0.501 |         0 |
| Industrials      |      0.344 |     0.507 |      0.526 |         0 |
| Industrials      |      0.339 |     0.5   |      0.518 |         0 |
| Industrials      |      0.339 |     0.498 |      0.518 |         0 |
| Industrials      |      0.338 |     0.5   |      0.514 |         0 |
| Health Care      |      0.337 |     0.513 |      0.498 |         0 |
| Consumer Staples |      0.336 |     0.527 |      0.481 |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Energy                 |      0.309 |     0.469 |      0.459 |         0 |
| Energy                 |      0.311 |     0.471 |      0.461 |         0 |
| Materials              |      0.311 |     0.446 |      0.489 |         0 |
| Materials              |      0.312 |     0.464 |      0.471 |         0 |
| Materials              |      0.313 |     0.459 |      0.48  |         0 |
| Utilities              |      0.313 |     0.498 |      0.44  |         0 |
| Utilities              |      0.315 |     0.499 |      0.445 |         0 |
| Energy                 |      0.319 |     0.487 |      0.468 |         0 |
| Communication Services |      0.319 |     0.51  |      0.449 |         0 |
| Utilities              |      0.32  |     0.48  |      0.479 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    1.0682 |        0.4985 |
| catboost     | test         |           11 |    1.0938 |        0.4971 |
| catboost     | wf           |           11 |    1.0437 |        0.5004 |
| lightgbm     | val          |           11 |    1.0856 |        0.4994 |
| lightgbm     | test         |           11 |    1.1118 |        0.4973 |
| lightgbm     | wf           |           11 |    1.0643 |        0.502  |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol           |   dir_acc |    mse |
|:-------------|:-----------------|----------:|-------:|
| catboost     | Consumer Staples |    0.5277 | 0.9169 |
| lightgbm     | Consumer Staples |    0.5244 | 0.929  |
| lightgbm     | Consumer Staples |    0.5238 | 0.9433 |
| catboost     | Consumer Staples |    0.5237 | 0.9118 |
| lightgbm     | Consumer Staples |    0.5225 | 0.9418 |
| lightgbm     | Industrials      |    0.5191 | 1.0041 |
| catboost     | Consumer Staples |    0.5186 | 0.9351 |
| lightgbm     | Utilities        |    0.5181 | 1.2757 |
| lightgbm     | Industrials      |    0.5176 | 1.038  |
| lightgbm     | Utilities        |    0.5168 | 1.0384 |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| catboost     | Materials              |    0.4649 | 1.1039 |
| lightgbm     | Materials              |    0.4756 | 1.1382 |
| catboost     | Materials              |    0.4772 | 1.1008 |
| lightgbm     | Materials              |    0.4775 | 1.0503 |
| lightgbm     | Materials              |    0.4793 | 1.1218 |
| catboost     | Materials              |    0.483  | 1.0295 |
| lightgbm     | Communication Services |    0.4844 | 1.066  |
| catboost     | Materials              |    0.4851 | 0.9328 |
| lightgbm     | Communication Services |    0.4863 | 1.0432 |
| lightgbm     | Information Technology |    0.4891 | 1.1302 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.321 |      0.467 |         0 |     0.496 | —           |     7.7 |      15   |            11 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.337 |      0.509 |         0 |     0.502 | —           |    19.1 |      25.7 |            11 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.329 |      0.493 |         0 |     0.494 | —           |     9.8 |      18.8 |            11 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.329 |      0.459 |         0 |     0.528 | —           |     0.1 |      24.9 |            11 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.317 |      0.464 |         0 |     0.487 | —           |     9   |      15.1 |            11 |
|       5 | 2024-09-03  | 2025-03-05 | 🟢 Bull           |      0.322 |      0.482 |         0 |     0.484 | —           |     5.6 |      17.4 |            11 |
