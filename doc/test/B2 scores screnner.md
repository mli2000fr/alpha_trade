# Diagnostic ML — Batch `model-factory-20260809115339-404c90`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260809115339-404c90`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : B2 scores screnner
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0186
- **📈 IC IR (Stabilité)** : 0.97  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0096 H5=0.0202 H10=0.0264 H15=0.0238 H20=0.0320
- **🏆 Champion Global** : catboost (H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — score composite 55% IC + 30% IR + 15% positifs
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-09 11:53:39
- **Terminé le** : 2026-08-09 13:13:56
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-screener-scores --no-include-score-components --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B2 scores screnner"
```

## 🌐 Global Ranking — Détails par Horizon

Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symboles, 6 splits walk-forward, 259239 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |   IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits | 🏆 Champion   |   Score |   IC catboost |   IR catboost |   IC lightgbm |   IR lightgbm |
|:----------|----------:|--------:|----------------:|--------------:|------------:|:--------------|--------:|--------------:|--------------:|--------------:|--------------:|
| H3        | 0.0108827 |    0.89 |      0.00958443 |           166 |           6 | catboost      |   0.975 |        0.0109 |          0.89 |        0.0046 |          0.22 |
| H5        | 0.0179683 |    1.05 |      0.0202416  |           166 |           6 | catboost      |   0.975 |        0.018  |          1.05 |        0.0081 |          0.35 |
| H10       | 0.020616  |    1.03 |      0.0264444  |           166 |           6 | catboost      |   0.975 |        0.0206 |          1.03 |        0.0025 |          0.1  |
| H15       | 0.0201118 |    1.03 |      0.0238417  |           166 |           6 | catboost      |   0.95  |        0.0201 |          1.03 |        0.0168 |          0.5  |
| H20       | 0.0236302 |    1.01 |      0.0320378  |           166 |           6 | catboost      |   0.95  |        0.0236 |          1.01 |        0.0203 |          0.63 |


🏆 **Meilleur horizon : H20** — sélectionné par score composite 55% IC + 30% IR + 15% Positive Split  |  H3=0.6326  H5=0.8432  H10=0.8991  H15=0.8638  H20=0.9384
### Horizon H3 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0109 | IR = 0.89 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0109
- **Decile Spread** : 0.0096
- **Nb Features** : 166

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-24 | 2019-01-02 → 2019-06-26  |         149065 |        38302 |           0.00278071 |    0.0198998  |    0.00278071 |
|       2 | 2016-12-29 → 2019-12-24 | 2020-01-02 → 2020-06-25  |         229215 |        40109 |           0.0309155  |    0.0416855  |    0.0309155  |
|       3 | 2016-12-29 → 2020-12-23 | 2020-12-31 → 2021-06-25  |         313075 |        41725 |           0.0231044  |   -0.0114844  |    0.0231044  |
|       4 | 2016-12-29 → 2021-12-23 | 2021-12-31 → 2022-06-27  |         400519 |        44291 |          -0.0045519  |   -0.0140303  |   -0.0045519  |
|       5 | 2016-12-29 → 2022-12-23 | 2023-01-03 → 2023-06-28  |         494250 |        47206 |           0.00813742 |   -0.0149546  |    0.00813742 |
|       6 | 2016-12-29 → 2023-12-27 | 2024-01-04 → 2024-06-28  |         591911 |        47606 |           0.00491034 |    0.00661543 |    0.00491034 |

- IC Moyen = 0.0109  |  IC Std = 0.0122  |  IC Min = -0.0046  |  IC Max = 0.0309

### Horizon H5 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0180 | IR = 1.05 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0180
- **Decile Spread** : 0.0202
- **Nb Features** : 166

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-20 | 2019-01-02 → 2019-06-24  |         148443 |        37670 |           0.00136326 |    0.00798927 |    0.00136326 |
|       2 | 2016-12-29 → 2019-12-20 | 2020-01-02 → 2020-06-23  |         228561 |        39443 |           0.0491444  |    0.0551293  |    0.0491444  |
|       3 | 2016-12-29 → 2020-12-21 | 2020-12-31 → 2021-06-23  |         312395 |        41033 |           0.0219612  |   -0.0187853  |    0.0219612  |
|       4 | 2016-12-29 → 2021-12-21 | 2021-12-31 → 2022-06-23  |         399803 |        43543 |          -0.0039832  |   -0.00347908 |   -0.0039832  |
|       5 | 2016-12-29 → 2022-12-21 | 2023-01-03 → 2023-06-26  |         493478 |        46432 |           0.0178181  |    0.0112177  |    0.0178181  |
|       6 | 2016-12-29 → 2023-12-22 | 2024-01-04 → 2024-06-26  |         591131 |        46822 |           0.0215063  |   -0.00359935 |    0.0215063  |

- IC Moyen = 0.0180  |  IC Std = 0.0171  |  IC Min = -0.0040  |  IC Max = 0.0491

### Horizon H10 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0206 | IR = 1.03 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0206
- **Decile Spread** : 0.0264
- **Nb Features** : 166

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |           0.00120261 |    0.0205349  |    0.00120261 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |           0.0474885  |    0.0375921  |    0.0474885  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |           0.0380825  |   -0.0376356  |    0.0380825  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |          -0.00746365 |    0.006035   |   -0.00746365 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |           0.0324056  |    0.00491858 |    0.0324056  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |           0.0119804  |   -0.0162876  |    0.0119804  |

- IC Moyen = 0.0206  |  IC Std = 0.0200  |  IC Min = -0.0075  |  IC Max = 0.0475

### Horizon H15 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0201 | IR = 1.03 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0201
- **Decile Spread** : 0.0238
- **Nb Features** : 166

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |          -0.00155066 |    0.0664033  |   -0.00155066 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |           0.0359595  |    0.0559596  |    0.0359595  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |           0.0413393  |    0.00674906 |    0.0413393  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |          -0.00532073 |   -0.00836192 |   -0.00532073 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |           0.0392569  |    0.00736129 |    0.0392569  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |           0.0109865  |   -0.0271203  |    0.0109865  |

- IC Moyen = 0.0201  |  IC Std = 0.0194  |  IC Min = -0.0053  |  IC Max = 0.0413

### Horizon H20 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0236 | IR = 1.01 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0236
- **Decile Spread** : 0.0320
- **Nb Features** : 166

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |          -0.00811871 |   0.052687    |   -0.00811871 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |           0.0371838  |   0.0756695   |    0.0371838  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |           0.0503624  |  -0.000435845 |    0.0503624  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |          -0.00614197 |   9.45793e-05 |   -0.00614197 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |           0.0459225  |   0.00662835  |    0.0459225  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |           0.0225732  |  -0.0128885   |    0.0225732  |

- IC Moyen = 0.0236  |  IC Std = 0.0234  |  IC Min = -0.0081  |  IC Max = 0.0504


## 🧪 Backtest Stratégies — Global Rank (H20 + H5)

| Variante | Score relatif |
|----------|---------------|
| V1 — H20 seul | 🏆 référence |
| V2 — H20 + H5 rising | -8.2% |
| V3 — H20 + H5 < 0.35 | -36.1% |
| V4 — H20 + top 3 horizons ↑ (H20,H10,H15) | -26.9% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H20 seul, V2 = H20 + H5 rising, V3 = H20 + H5 < 0.35 (contrarian). V4 = H20 + top 3 horizons ↑ (H20,H10,H15).

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
|         3 |      0.33  |      0.49  |     0.5   |    0.501  |
|         5 |      0.329 |      0.478 |     0.509 |    0.5005 |
|        10 |      0.329 |      0.478 |     0.51  |    0.5023 |
|        15 |      0.328 |      0.475 |     0.51  |    0.5013 |
|        20 |      0.326 |      0.474 |     0.506 |    0.4983 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.331 |          0.506 |             0 |         0.487 |
| catboost     | test         |           11 |          0.329 |          0.524 |             0 |         0.462 |
| catboost     | wf           |           11 |          0.328 |          0.477 |             0 |         0.507 |
| lightgbm     | val          |           11 |          0.331 |          0.506 |             0 |         0.487 |
| lightgbm     | test         |           11 |          0.329 |          0.513 |             0 |         0.473 |
| lightgbm     | wf           |           11 |          0.329 |          0.48  |             0 |         0.506 |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               51.914 |                   0 |              48.086 |               49.998 |               0.004 |              49.998 |
| catboost     | test         |           11 |               51.941 |                   0 |              48.059 |               54.104 |               0     |              45.896 |
| catboost     | wf           |           11 |               51.566 |                   0 |              48.434 |               45.405 |               0     |              54.595 |
| lightgbm     | val          |           11 |               51.914 |                   0 |              48.086 |               49.998 |               0.005 |              49.998 |
| lightgbm     | test         |           11 |               51.941 |                   0 |              48.059 |               51.988 |               0     |              48.012 |
| lightgbm     | wf           |           11 |               51.566 |                   0 |              48.434 |               45.9   |               0     |              54.1   |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.20-0.29            |            1 |
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol           |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples |      0.358 |     0.559 |      0.516 |         0 |
| Consumer Staples |      0.358 |     0.553 |      0.521 |         0 |
| Industrials      |      0.345 |     0.509 |      0.526 |         0 |
| Consumer Staples |      0.345 |     0.542 |      0.492 |         0 |
| Health Care      |      0.34  |     0.519 |      0.5   |         0 |
| Industrials      |      0.339 |     0.501 |      0.516 |         0 |
| Industrials      |      0.339 |     0.497 |      0.52  |         0 |
| Health Care      |      0.338 |     0.519 |      0.496 |         0 |
| Financials       |      0.338 |     0.516 |      0.499 |         0 |
| Industrials      |      0.338 |     0.501 |      0.513 |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Energy                 |      0.296 |     0.431 |      0.458 |         0 |
| Energy                 |      0.297 |     0.448 |      0.443 |         0 |
| Energy                 |      0.308 |     0.443 |      0.481 |         0 |
| Materials              |      0.317 |     0.477 |      0.475 |         0 |
| Information Technology |      0.318 |     0.497 |      0.456 |         0 |
| Energy                 |      0.318 |     0.473 |      0.48  |         0 |
| Communication Services |      0.32  |     0.506 |      0.454 |         0 |
| Communication Services |      0.32  |     0.507 |      0.454 |         0 |
| Utilities              |      0.321 |     0.548 |      0.414 |         0 |
| Materials              |      0.321 |     0.466 |      0.498 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    1.0617 |        0.4966 |
| catboost     | test         |           11 |    1.0715 |        0.4972 |
| catboost     | wf           |           11 |    1.0337 |        0.5009 |
| lightgbm     | val          |           11 |    1.0753 |        0.4969 |
| lightgbm     | test         |           11 |    1.0909 |        0.4963 |
| lightgbm     | wf           |           11 |    1.0522 |        0.5004 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol           |   dir_acc |    mse |
|:-------------|:-----------------|----------:|-------:|
| lightgbm     | Consumer Staples |    0.539  | 0.9078 |
| lightgbm     | Consumer Staples |    0.5385 | 0.9356 |
| catboost     | Consumer Staples |    0.5287 | 0.9034 |
| lightgbm     | Consumer Staples |    0.5202 | 0.9262 |
| catboost     | Consumer Staples |    0.5193 | 0.898  |
| lightgbm     | Industrials      |    0.5189 | 1.0421 |
| catboost     | Health Care      |    0.5173 | 1.04   |
| catboost     | Real Estate      |    0.5135 | 0.9551 |
| catboost     | Health Care      |    0.5125 | 1.037  |
| catboost     | Consumer Staples |    0.5124 | 0.9188 |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Materials              |    0.4681 | 1.0814 |
| catboost     | Communication Services |    0.4729 | 1.0512 |
| catboost     | Communication Services |    0.4751 | 1.033  |
| catboost     | Information Technology |    0.4803 | 1.0855 |
| lightgbm     | Energy                 |    0.4822 | 0.985  |
| lightgbm     | Materials              |    0.4824 | 1.0599 |
| lightgbm     | Information Technology |    0.4829 | 1.135  |
| lightgbm     | Energy                 |    0.4837 | 0.9705 |
| catboost     | Communication Services |    0.4846 | 1.0221 |
| lightgbm     | Communication Services |    0.4846 | 1.0929 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.317 |      0.441 |         0 |     0.511 | —           |     7.7 |      15   |            11 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.335 |      0.491 |         0 |     0.515 | —           |    19.1 |      25.7 |            11 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.327 |      0.464 |         0 |     0.516 | —           |     9.8 |      18.8 |            11 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.333 |      0.456 |         0 |     0.542 | —           |     0.1 |      24.9 |            11 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.315 |      0.482 |         0 |     0.462 | —           |     9   |      15.1 |            11 |
|       5 | 2024-09-03  | 2025-03-05 | 🟢 Bull           |      0.333 |      0.504 |         0 |     0.495 | —           |     5.6 |      17.4 |            11 |
