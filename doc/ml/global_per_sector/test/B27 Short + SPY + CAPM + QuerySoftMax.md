# Diagnostic ML — Batch `model-factory-20260812064355-7faa02`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260812064355-7faa02`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : B27 Short + SPY + CAPM + QuerySoftMax
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0161
- **📈 IC IR (Stabilité)** : 0.95  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0077 H5=0.0201 H10=0.0195 H15=0.0229 H20=0.0245
- **🏆 Champion Global** : catboost (H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — score composite 55% IC + 30% IR + 15% positifs
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-12 06:43:55
- **Terminé le** : 2026-08-12 14:11:39
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --include-factors --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --catboost-loss-function QuerySoftMax --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-short-score --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B27 Short + SPY + CAPM + QuerySoftMax"
```

## 🌐 Global Ranking — Détails par Horizon

Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symboles, 6 splits walk-forward, 259239 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |   IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits | 🏆 Champion   |   Score |   IC catboost |   IR catboost |   IC lightgbm |   IR lightgbm |
|:----------|----------:|--------:|----------------:|--------------:|------------:|:--------------|--------:|--------------:|--------------:|--------------:|--------------:|
| H3        | 0.010697  |    0.86 |      0.00771706 |           145 |           6 | catboost      |   0.95  |        0.0107 |          0.86 |        0.0075 |          0.62 |
| H5        | 0.020801  |    1.23 |      0.0200793  |           145 |           6 | catboost      |   0.975 |        0.0208 |          1.23 |        0.015  |          0.71 |
| H10       | 0.014183  |    0.85 |      0.0194709  |           145 |           6 | catboost      |   0.95  |        0.0142 |          0.85 |        0.0127 |          0.62 |
| H15       | 0.0175183 |    1    |      0.0228825  |           145 |           6 | catboost      |   0.95  |        0.0175 |          1    |        0.0152 |          0.48 |
| H20       | 0.0172108 |    0.91 |      0.0244688  |           145 |           6 | catboost      |   0.95  |        0.0172 |          0.91 |        0.0074 |          0.28 |


🏆 **Meilleur horizon : H5** — sélectionné par score composite 55% IC + 30% IR + 15% Positive Split  |  H3=0.5933  H5=0.9750  H10=0.6823  H15=0.8080  H20=0.7770
### Horizon H3 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0107 | IR = 0.86 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0107
- **Decile Spread** : 0.0077
- **Nb Features** : 145

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-24 | 2019-01-02 → 2019-06-26  |         149065 |        38302 |         -0.000741772 |    0.028066   |  -0.000741772 |
|       2 | 2016-12-29 → 2019-12-24 | 2020-01-02 → 2020-06-25  |         229215 |        40109 |          0.0328672   |    0.0104055  |   0.0328672   |
|       3 | 2016-12-29 → 2020-12-23 | 2020-12-31 → 2021-06-25  |         313075 |        41725 |          0.0195469   |    0.0055532  |   0.0195469   |
|       4 | 2016-12-29 → 2021-12-23 | 2021-12-31 → 2022-06-27  |         400519 |        44291 |         -0.00382777  |   -0.00794717 |  -0.00382777  |
|       5 | 2016-12-29 → 2022-12-23 | 2023-01-03 → 2023-06-28  |         494250 |        47206 |          0.00776639  |   -0.00501517 |   0.00776639  |
|       6 | 2016-12-29 → 2023-12-27 | 2024-01-04 → 2024-06-28  |         591911 |        47606 |          0.00857081  |    0.014175   |   0.00857081  |

- IC Moyen = 0.0107  |  IC Std = 0.0124  |  IC Min = -0.0038  |  IC Max = 0.0329

### Horizon H5 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0208 | IR = 1.23 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0208
- **Decile Spread** : 0.0201
- **Nb Features** : 145

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-20 | 2019-01-02 → 2019-06-24  |         148443 |        37670 |           0.00517898 |    0.0357161  |    0.00517898 |
|       2 | 2016-12-29 → 2019-12-20 | 2020-01-02 → 2020-06-23  |         228561 |        39443 |           0.0507055  |    0.050776   |    0.0507055  |
|       3 | 2016-12-29 → 2020-12-21 | 2020-12-31 → 2021-06-23  |         312395 |        41033 |           0.0249597  |   -0.00990998 |    0.0249597  |
|       4 | 2016-12-29 → 2021-12-21 | 2021-12-31 → 2022-06-23  |         399803 |        43543 |          -0.00224071 |    0.00710375 |   -0.00224071 |
|       5 | 2016-12-29 → 2022-12-21 | 2023-01-03 → 2023-06-26  |         493478 |        46432 |           0.0265784  |    0.00430302 |    0.0265784  |
|       6 | 2016-12-29 → 2023-12-22 | 2024-01-04 → 2024-06-26  |         591131 |        46822 |           0.0196244  |    0.00226005 |    0.0196244  |

- IC Moyen = 0.0208  |  IC Std = 0.0169  |  IC Min = -0.0022  |  IC Max = 0.0507

### Horizon H10 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0142 | IR = 0.85 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0142
- **Decile Spread** : 0.0195
- **Nb Features** : 145

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |          -0.00460959 |    0.0422951  |   -0.00460959 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |           0.0318279  |    0.0360421  |    0.0318279  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |           0.0288414  |   -0.00367099 |    0.0288414  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |          -0.0115371  |   -0.00686627 |   -0.0115371  |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |           0.0257968  |    0.0152528  |    0.0257968  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |           0.0147788  |   -0.00710861 |    0.0147788  |

- IC Moyen = 0.0142  |  IC Std = 0.0167  |  IC Min = -0.0115  |  IC Max = 0.0318

### Horizon H15 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0175 | IR = 1.00 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0175
- **Decile Spread** : 0.0229
- **Nb Features** : 145

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |          -0.00941121 |     0.0339458 |   -0.00941121 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |           0.0310959  |     0.072658  |    0.0310959  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |           0.0367402  |    -0.0201304 |    0.0367402  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |          -0.00133144 |     0.0115276 |   -0.00133144 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |           0.031602   |     0.0113804 |    0.031602   |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |           0.0164142  |    -0.0180392 |    0.0164142  |

- IC Moyen = 0.0175  |  IC Std = 0.0175  |  IC Min = -0.0094  |  IC Max = 0.0367

### Horizon H20 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0172 | IR = 0.91 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0172
- **Decile Spread** : 0.0245
- **Nb Features** : 145

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |          -0.00532992 |    0.0447478  |   -0.00532992 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |           0.0213799  |    0.039221   |    0.0213799  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |           0.0442429  |   -0.0120206  |    0.0442429  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |          -0.00545018 |    0.00706035 |   -0.00545018 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |           0.0361779  |   -0.0236287  |    0.0361779  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |           0.0122443  |   -0.0110977  |    0.0122443  |

- IC Moyen = 0.0172  |  IC Std = 0.0189  |  IC Min = -0.0055  |  IC Max = 0.0442


## 🧪 Backtest Stratégies — Global Rank (H5 seul)

| Variante | Score relatif |
|----------|---------------|
| V1 — H5 seul | 🏆 référence |
| V4 — H5 + top 3 horizons ↑ (H5,H15,H20) | -19.1% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H5 seul (V2/V3 non calculés — H5 est déjà le meilleur horizon). V4 = H5 + top 3 horizons ↑ (H5,H15,H20).

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
|         3 |      0.33  |      0.49  |     0.5   |    0.5011 |
|         5 |      0.329 |      0.475 |     0.512 |    0.5014 |
|        10 |      0.328 |      0.473 |     0.511 |    0.5013 |
|        15 |      0.328 |      0.473 |     0.511 |    0.5015 |
|        20 |      0.328 |      0.475 |     0.508 |    0.5009 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.333 |          0.509 |             0 |         0.49  |
| catboost     | test         |           11 |          0.329 |          0.519 |             0 |         0.468 |
| catboost     | wf           |           11 |          0.328 |          0.475 |             0 |         0.51  |
| lightgbm     | val          |           11 |          0.332 |          0.507 |             0 |         0.488 |
| lightgbm     | test         |           11 |          0.329 |          0.51  |             0 |         0.476 |
| lightgbm     | wf           |           11 |          0.329 |          0.48  |             0 |         0.507 |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| catboost     | test         |           11 |               51.925 |                   0 |              48.075 |               53.089 |               0     |              46.911 |
| catboost     | wf           |           11 |               51.407 |                   0 |              48.593 |               45.195 |               0     |              54.805 |
| lightgbm     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.005 |              49.998 |
| lightgbm     | test         |           11 |               51.925 |                   0 |              48.075 |               51.391 |               0     |              48.609 |
| lightgbm     | wf           |           11 |               51.407 |                   0 |              48.593 |               45.913 |               0     |              54.087 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.20-0.29            |            1 |
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol           |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples |      0.361 |     0.551 |      0.532 |         0 |
| Consumer Staples |      0.357 |     0.547 |      0.523 |         0 |
| Consumer Staples |      0.347 |     0.533 |      0.507 |         0 |
| Industrials      |      0.345 |     0.51  |      0.526 |         0 |
| Health Care      |      0.344 |     0.533 |      0.5   |         0 |
| Industrials      |      0.344 |     0.507 |      0.524 |         0 |
| Health Care      |      0.343 |     0.541 |      0.487 |         0 |
| Health Care      |      0.342 |     0.535 |      0.49  |         0 |
| Industrials      |      0.34  |     0.501 |      0.52  |         0 |
| Industrials      |      0.339 |     0.497 |      0.521 |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Energy                 |      0.293 |     0.422 |      0.458 |         0 |
| Energy                 |      0.297 |     0.441 |      0.449 |         0 |
| Energy                 |      0.308 |     0.454 |      0.469 |         0 |
| Utilities              |      0.31  |     0.571 |      0.358 |         0 |
| Utilities              |      0.311 |     0.563 |      0.368 |         0 |
| Utilities              |      0.312 |     0.539 |      0.397 |         0 |
| Energy                 |      0.313 |     0.466 |      0.474 |         0 |
| Communication Services |      0.317 |     0.51  |      0.442 |         0 |
| Communication Services |      0.319 |     0.51  |      0.445 |         0 |
| Information Technology |      0.322 |     0.505 |      0.459 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    1.0662 |        0.4997 |
| catboost     | test         |           11 |    1.0878 |        0.4965 |
| catboost     | wf           |           11 |    1.0446 |        0.5014 |
| lightgbm     | val          |           11 |    1.08   |        0.498  |
| lightgbm     | test         |           11 |    1.1097 |        0.4954 |
| lightgbm     | wf           |           11 |    1.0624 |        0.5011 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol           |   dir_acc |    mse |
|:-------------|:-----------------|----------:|-------:|
| catboost     | Consumer Staples |    0.5436 | 0.8926 |
| lightgbm     | Consumer Staples |    0.5424 | 0.9282 |
| lightgbm     | Consumer Staples |    0.5375 | 0.9129 |
| catboost     | Consumer Staples |    0.5269 | 0.9032 |
| catboost     | Consumer Staples |    0.5269 | 0.9222 |
| lightgbm     | Consumer Staples |    0.523  | 0.933  |
| lightgbm     | Industrials      |    0.5193 | 1.0506 |
| catboost     | Health Care      |    0.5179 | 1.0557 |
| lightgbm     | Industrials      |    0.5166 | 1.0146 |
| catboost     | Health Care      |    0.5162 | 1.0661 |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Materials              |    0.4634 | 1.1101 |
| catboost     | Utilities              |    0.4687 | 1.1528 |
| catboost     | Communication Services |    0.4716 | 1.0446 |
| catboost     | Communication Services |    0.4805 | 1.0092 |
| catboost     | Communication Services |    0.4811 | 1.0256 |
| lightgbm     | Materials              |    0.4812 | 1.0789 |
| lightgbm     | Communication Services |    0.4824 | 1.0622 |
| lightgbm     | Communication Services |    0.4824 | 1.0779 |
| lightgbm     | Energy                 |    0.4828 | 0.9772 |
| lightgbm     | Materials              |    0.4847 | 0.9481 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.32  |      0.435 |         0 |     0.524 | —           |     7.7 |      15   |            11 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.33  |      0.453 |         0 |     0.537 | —           |    19.1 |      25.7 |            11 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.326 |      0.465 |         0 |     0.513 | —           |     9.8 |      18.8 |            11 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.335 |      0.485 |         0 |     0.521 | —           |     0.1 |      24.9 |            11 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.32  |      0.492 |         0 |     0.469 | —           |     9   |      15.1 |            11 |
|       5 | 2024-09-03  | 2025-03-05 | 🟢 Bull           |      0.332 |      0.509 |         0 |     0.486 | —           |     5.6 |      17.4 |            11 |
