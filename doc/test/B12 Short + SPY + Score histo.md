# Diagnostic ML — Batch `model-factory-20260810200031-9755c6`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260810200031-9755c6`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : B12 Short + SPY + Score histo
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0188
- **📈 IC IR (Stabilité)** : 0.92  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0097 H5=0.0173 H10=0.0250 H15=0.0257 H20=0.0268
- **🏆 Champion Global** : catboost (H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — score composite 55% IC + 30% IR + 15% positifs
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-10 20:00:31
- **Terminé le** : 2026-08-10 21:20:26
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-short-score --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B12 Short + SPY + Score histo"
```

## 🌐 Global Ranking — Détails par Horizon

Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symboles, 6 splits walk-forward, 259239 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |   IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits | 🏆 Champion   |   Score |   IC catboost |   IR catboost |   IC lightgbm |   IR lightgbm |
|:----------|----------:|--------:|----------------:|--------------:|------------:|:--------------|--------:|--------------:|--------------:|--------------:|--------------:|
| H3        | 0.0109845 |    0.87 |      0.00970259 |           153 |           6 | catboost      |   0.975 |        0.011  |          0.87 |        0.0043 |          0.3  |
| H5        | 0.0193895 |    1.06 |      0.0173108  |           153 |           6 | catboost      |   0.975 |        0.0194 |          1.06 |        0.0118 |          0.53 |
| H10       | 0.0220558 |    0.94 |      0.0249712  |           153 |           6 | catboost      |   0.95  |        0.0221 |          0.94 |        0.0127 |          0.41 |
| H15       | 0.0222678 |    1.08 |      0.0257205  |           153 |           6 | catboost      |   0.95  |        0.0223 |          1.08 |        0.0005 |          0.03 |
| H20       | 0.019373  |    0.86 |      0.0268224  |           153 |           6 | catboost      |   0.95  |        0.0194 |          0.86 |        0.0021 |          0.11 |


🏆 **Meilleur horizon : H15** — sélectionné par score composite 55% IC + 30% IR + 15% Positive Split  |  H3=0.6385  H5=0.8978  H10=0.9043  H15=0.9500  H20=0.8165
### Horizon H3 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0110 | IR = 0.87 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0110
- **Decile Spread** : 0.0097
- **Nb Features** : 153

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-24 | 2019-01-02 → 2019-06-26  |         149065 |        38302 |         -0.00314343  |   0.0283122   |  -0.00314343  |
|       2 | 2016-12-29 → 2019-12-24 | 2020-01-02 → 2020-06-25  |         229215 |        40109 |          0.0346917   |   0.0128502   |   0.0346917   |
|       3 | 2016-12-29 → 2020-12-23 | 2020-12-31 → 2021-06-25  |         313075 |        41725 |          0.0170362   |  -0.00305836  |   0.0170362   |
|       4 | 2016-12-29 → 2021-12-23 | 2021-12-31 → 2022-06-27  |         400519 |        44291 |          0.000580547 |  -0.0172877   |   0.000580547 |
|       5 | 2016-12-29 → 2022-12-23 | 2023-01-03 → 2023-06-28  |         494250 |        47206 |          0.00447058  |  -0.000547187 |   0.00447058  |
|       6 | 2016-12-29 → 2023-12-27 | 2024-01-04 → 2024-06-28  |         591911 |        47606 |          0.0122713   |   0.00537065  |   0.0122713   |

- IC Moyen = 0.0110  |  IC Std = 0.0126  |  IC Min = -0.0031  |  IC Max = 0.0347

### Horizon H5 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0194 | IR = 1.06 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0194
- **Decile Spread** : 0.0173
- **Nb Features** : 153

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-20 | 2019-01-02 → 2019-06-24  |         148443 |        37670 |           0.00443915 |   0.0184185   |    0.00443915 |
|       2 | 2016-12-29 → 2019-12-20 | 2020-01-02 → 2020-06-23  |         228561 |        39443 |           0.0472885  |   0.0581443   |    0.0472885  |
|       3 | 2016-12-29 → 2020-12-21 | 2020-12-31 → 2021-06-23  |         312395 |        41033 |           0.0298904  |   0.000617813 |    0.0298904  |
|       4 | 2016-12-29 → 2021-12-21 | 2021-12-31 → 2022-06-23  |         399803 |        43543 |          -0.0101589  |   0.00273245  |   -0.0101589  |
|       5 | 2016-12-29 → 2022-12-21 | 2023-01-03 → 2023-06-26  |         493478 |        46432 |           0.0244246  |  -0.0061252   |    0.0244246  |
|       6 | 2016-12-29 → 2023-12-22 | 2024-01-04 → 2024-06-26  |         591131 |        46822 |           0.0204534  |  -0.003043    |    0.0204534  |

- IC Moyen = 0.0194  |  IC Std = 0.0183  |  IC Min = -0.0102  |  IC Max = 0.0473

### Horizon H10 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0221 | IR = 0.94 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0221
- **Decile Spread** : 0.0250
- **Nb Features** : 153

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |          -0.00567375 |    0.032332   |   -0.00567375 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |           0.058431   |    0.0721883  |    0.058431   |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |           0.0315972  |   -0.0168846  |    0.0315972  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |          -0.00864075 |   -0.00289274 |   -0.00864075 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |           0.0364656  |    0.00720019 |    0.0364656  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |           0.0201556  |   -0.0155881  |    0.0201556  |

- IC Moyen = 0.0221  |  IC Std = 0.0236  |  IC Min = -0.0086  |  IC Max = 0.0584

### Horizon H15 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0223 | IR = 1.08 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0223
- **Decile Spread** : 0.0257
- **Nb Features** : 153

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |         -0.00564224  |   -0.0137083  |  -0.00564224  |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |          0.044127    |    0.034912   |   0.044127    |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |          0.0454497   |   -0.0288518  |   0.0454497   |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |         -0.000103417 |    0.00221374 |  -0.000103417 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |          0.0357813   |    0.0165582  |   0.0357813   |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |          0.0139945   |   -0.00792065 |   0.0139945   |

- IC Moyen = 0.0223  |  IC Std = 0.0206  |  IC Min = -0.0056  |  IC Max = 0.0454

### Horizon H20 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0194 | IR = 0.86 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0194
- **Decile Spread** : 0.0268
- **Nb Features** : 153

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |          -0.00587797 |   -0.00980127 |   -0.00587797 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |           0.0229169  |    0.0362844  |    0.0229169  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |           0.0520899  |    0.0147699  |    0.0520899  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |          -0.00427152 |   -0.0165114  |   -0.00427152 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |           0.0444374  |    0.00149334 |    0.0444374  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |           0.00694316 |   -0.0134737  |    0.00694316 |

- IC Moyen = 0.0194  |  IC Std = 0.0226  |  IC Min = -0.0059  |  IC Max = 0.0521


## 🧪 Backtest Stratégies — Global Rank (H15 + H5)

| Variante | Score relatif |
|----------|---------------|
| V1 — H15 seul | 🏆 référence |
| V2 — H15 + H5 rising | -2.5% |
| V3 — H15 + H5 < 0.35 | -30.4% |
| V4 — H15 + top 3 horizons ↑ (H15,H10,H5) | -19.0% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H15 seul, V2 = H15 + H5 rising, V3 = H15 + H5 < 0.35 (contrarian). V4 = H15 + top 3 horizons ↑ (H15,H10,H5).

---

## 🔵 Per-Symbol / Per-Sector — Métriques d'entraînement

### 🏆 Sélection du champion

✅ **Tout va bien** — 11 champions sélectionnés automatiquement sur 11 symboles.

### 📊 Champions par modèle

| model_name   |   nb_symbols |
|:-------------|-------------:|
| lightgbm     |           10 |
| catboost     |            1 |

## 📊 Métriques par Horizon (WF)

|   Horizon |   F1 macro |   F1 short |   F1 long |   Dir Acc |
|----------:|-----------:|-----------:|----------:|----------:|
|         3 |      0.33  |      0.49  |     0.5   |    0.501  |
|         5 |      0.329 |      0.475 |     0.512 |    0.5009 |
|        10 |      0.329 |      0.476 |     0.51  |    0.5018 |
|        15 |      0.329 |      0.475 |     0.513 |    0.5026 |
|        20 |      0.327 |      0.473 |     0.508 |    0.5001 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.333 |          0.509 |             0 |         0.49  |
| catboost     | test         |           11 |          0.33  |          0.521 |             0 |         0.468 |
| catboost     | wf           |           11 |          0.329 |          0.476 |             0 |         0.51  |
| lightgbm     | val          |           11 |          0.331 |          0.507 |             0 |         0.487 |
| lightgbm     | test         |           11 |          0.329 |          0.511 |             0 |         0.476 |
| lightgbm     | wf           |           11 |          0.329 |          0.479 |             0 |         0.508 |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| catboost     | test         |           11 |               51.925 |                   0 |              48.075 |               53.244 |               0     |              46.756 |
| catboost     | wf           |           11 |               51.407 |                   0 |              48.593 |               45.285 |               0     |              54.715 |
| lightgbm     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| lightgbm     | test         |           11 |               51.925 |                   0 |              48.075 |               51.431 |               0     |              48.569 |
| lightgbm     | wf           |           11 |               51.407 |                   0 |              48.593 |               45.838 |               0     |              54.162 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol           |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples |      0.358 |     0.551 |      0.521 |         0 |
| Consumer Staples |      0.357 |     0.55  |      0.522 |         0 |
| Consumer Staples |      0.349 |     0.539 |      0.508 |         0 |
| Industrials      |      0.345 |     0.508 |      0.527 |         0 |
| Industrials      |      0.343 |     0.509 |      0.521 |         0 |
| Industrials      |      0.343 |     0.504 |      0.525 |         0 |
| Industrials      |      0.34  |     0.498 |      0.523 |         0 |
| Health Care      |      0.338 |     0.524 |      0.489 |         0 |
| Consumer Staples |      0.337 |     0.534 |      0.477 |         0 |
| Industrials      |      0.337 |     0.498 |      0.512 |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Energy                 |      0.306 |     0.46  |      0.457 |         0 |
| Energy                 |      0.307 |     0.442 |      0.479 |         0 |
| Materials              |      0.308 |     0.467 |      0.457 |         0 |
| Utilities              |      0.309 |     0.558 |      0.37  |         0 |
| Utilities              |      0.313 |     0.567 |      0.371 |         0 |
| Utilities              |      0.313 |     0.546 |      0.395 |         0 |
| Energy                 |      0.314 |     0.464 |      0.478 |         0 |
| Materials              |      0.316 |     0.462 |      0.486 |         0 |
| Communication Services |      0.317 |     0.502 |      0.448 |         0 |
| Energy                 |      0.317 |     0.482 |      0.469 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    1.0654 |        0.4997 |
| catboost     | test         |           11 |    1.0866 |        0.4977 |
| catboost     | wf           |           11 |    1.0432 |        0.5017 |
| lightgbm     | val          |           11 |    1.08   |        0.4972 |
| lightgbm     | test         |           11 |    1.1078 |        0.496  |
| lightgbm     | wf           |           11 |    1.0621 |        0.5009 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol           |   dir_acc |    mse |
|:-------------|:-----------------|----------:|-------:|
| catboost     | Consumer Staples |    0.5447 | 0.8867 |
| lightgbm     | Consumer Staples |    0.5384 | 0.9147 |
| lightgbm     | Consumer Staples |    0.5378 | 0.918  |
| catboost     | Consumer Staples |    0.5336 | 0.8939 |
| lightgbm     | Consumer Staples |    0.5269 | 0.9244 |
| catboost     | Consumer Staples |    0.5253 | 0.9204 |
| lightgbm     | Industrials      |    0.5184 | 1.045  |
| lightgbm     | Industrials      |    0.5161 | 1.015  |
| lightgbm     | Industrials      |    0.5157 | 0.9828 |
| catboost     | Health Care      |    0.5155 | 1.0585 |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Materials              |    0.4652 | 1.0982 |
| catboost     | Communication Services |    0.4746 | 1.0421 |
| lightgbm     | Materials              |    0.4787 | 1.0824 |
| lightgbm     | Communication Services |    0.4793 | 1.0746 |
| lightgbm     | Energy                 |    0.4812 | 1.0273 |
| catboost     | Communication Services |    0.4815 | 1.022  |
| lightgbm     | Materials              |    0.4849 | 1.0299 |
| catboost     | Utilities              |    0.4852 | 1.1594 |
| lightgbm     | Materials              |    0.4862 | 0.9503 |
| lightgbm     | Energy                 |    0.488  | 0.9765 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.321 |      0.438 |         0 |     0.525 | —           |     7.7 |      15   |            11 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.331 |      0.447 |         0 |     0.546 | —           |    19.1 |      25.7 |            11 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.324 |      0.459 |         0 |     0.512 | —           |     9.8 |      18.8 |            11 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.343 |      0.5   |         0 |     0.529 | —           |     0.1 |      24.9 |            11 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.319 |      0.493 |         0 |     0.464 | —           |     9   |      15.1 |            11 |
|       5 | 2024-09-03  | 2025-03-05 | 🟢 Bull           |      0.329 |      0.507 |         0 |     0.481 | —           |     5.6 |      17.4 |            11 |
