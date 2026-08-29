# Diagnostic ML — Batch `model-factory-20260811184205-100f0a`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260811184205-100f0a`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : B19 Short + SPY + from 2011 + max 16 slits
- **Date début training** : 2011-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0157
- **📈 IC IR (Stabilité)** : 0.68  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0095 H5=0.0152 H10=0.0213 H15=0.0196 H20=0.0207
- **🏆 Champion Global** : catboost (H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — score composite 55% IC + 30% IR + 15% positifs
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-11 18:42:06
- **Terminé le** : 2026-08-11 21:12:45
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2011-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-short-score --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 16 --comment "B19 Short + SPY + from 2011 + max 16 slits"
```

## 🌐 Global Ranking — Détails par Horizon

Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symboles, 11 splits walk-forward, 428759 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |   IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits | 🏆 Champion   |   Score |   IC catboost |   IR catboost |   IC lightgbm |   IR lightgbm |
|:----------|----------:|--------:|----------------:|--------------:|------------:|:--------------|--------:|--------------:|--------------:|--------------:|--------------:|
| H3        | 0.0112057 |    1    |      0.00945509 |           144 |          11 | catboost      |   0.973 |        0.0112 |          1    |        0.009  |          0.72 |
| H5        | 0.0161356 |    0.88 |      0.0151958  |           144 |          11 | catboost      |   0.959 |        0.0161 |          0.88 |        0.0042 |          0.92 |
| H10       | 0.0171142 |    0.67 |      0.0213062  |           144 |          11 | catboost      |   0.945 |        0.0171 |          0.67 |        0.0045 |          0.26 |
| H15       | 0.0168108 |    0.65 |      0.0196452  |           144 |          11 | catboost      |   0.945 |        0.0168 |          0.65 |        0.0012 |          0.08 |
| H20       | 0.0172549 |    0.59 |      0.0207209  |           144 |          11 | catboost      |   0.959 |        0.0173 |          0.59 |        0.0048 |          0.18 |


🏆 **Meilleur horizon : H5** — sélectionné par score composite 55% IC + 30% IR + 15% Positive Split  |  H3=0.7799  H5=0.9006  H10=0.8420  H15=0.8251  H20=0.8373
### Horizon H3 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0112 | IR = 1.00 | Score composite = 0.973 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0112
- **Decile Spread** : 0.0095
- **Nb Features** : 144

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2011-12-29 → 2013-12-24 | 2014-01-02 → 2014-06-26  |         117327 |        30120 |           0.0197243  |  -0.000868694 |    0.0197243  |
|       2 | 2011-12-29 → 2014-12-24 | 2015-01-02 → 2015-06-26  |         181361 |        33179 |           0.016555   |  -0.0129417   |    0.016555   |
|       3 | 2011-12-29 → 2015-12-24 | 2016-01-04 → 2016-06-27  |         250300 |        34065 |          -0.00115852 |   0.0047448   |   -0.00115852 |
|       4 | 2011-12-29 → 2016-12-23 | 2017-01-03 → 2017-06-27  |         321571 |        35223 |           0.00647158 |   0.024893    |    0.00647158 |
|       5 | 2011-12-29 → 2017-12-26 | 2018-01-03 → 2018-06-27  |         394966 |        36857 |           0.010663   |   0.00464378  |    0.010663   |
|       6 | 2011-12-29 → 2018-12-27 | 2019-01-04 → 2019-06-28  |         471834 |        38314 |           0.00745086 |   0.00725818  |    0.00745086 |
|       7 | 2011-12-29 → 2019-12-27 | 2020-01-06 → 2020-06-29  |         552016 |        40121 |           0.0378689  |   0.0373775   |    0.0378689  |
|       8 | 2011-12-29 → 2020-12-28 | 2021-01-05 → 2021-06-29  |         635902 |        41737 |           0.0136152  |   0.0115593   |    0.0136152  |
|       9 | 2011-12-29 → 2021-12-28 | 2022-01-04 → 2022-06-29  |         723382 |        44325 |          -0.00664915 |   0.00378229  |   -0.00664915 |
|      10 | 2011-12-29 → 2022-12-28 | 2023-01-05 → 2023-06-30  |         817169 |        47208 |           0.0143407  |   0.00932412  |    0.0143407  |
|      11 | 2011-12-29 → 2023-12-29 | 2024-01-08 → 2024-07-02  |         914838 |        47610 |           0.00438125 |   0.00938296  |    0.00438125 |

- IC Moyen = 0.0112  |  IC Std = 0.0112  |  IC Min = -0.0066  |  IC Max = 0.0379

### Horizon H5 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0161 | IR = 0.88 | Score composite = 0.959 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0161
- **Decile Spread** : 0.0152
- **Nb Features** : 144

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2011-12-29 → 2013-12-20 | 2014-01-02 → 2014-06-24  |         116839 |        29612 |           0.0114027  |   0.00514667  |    0.0114027  |
|       2 | 2011-12-29 → 2014-12-22 | 2015-01-02 → 2015-06-24  |         180825 |        32629 |           0.0184078  |   0.00497652  |    0.0184078  |
|       3 | 2011-12-29 → 2015-12-22 | 2016-01-04 → 2016-06-23  |         249748 |        33499 |           0.010898   |   0.0090493   |    0.010898   |
|       4 | 2011-12-29 → 2016-12-21 | 2017-01-03 → 2017-06-23  |         320995 |        34641 |          -0.00982245 |   0.00352986  |   -0.00982245 |
|       5 | 2011-12-29 → 2017-12-21 | 2018-01-03 → 2018-06-25  |         394368 |        36246 |           0.0112288  |   0.00952657  |    0.0112288  |
|       6 | 2011-12-29 → 2018-12-24 | 2019-01-04 → 2019-06-26  |         471212 |        37680 |           0.0113039  |   0.00532991  |    0.0113039  |
|       7 | 2011-12-29 → 2019-12-24 | 2020-01-06 → 2020-06-25  |         551362 |        39455 |           0.064493   |   0.0113017   |    0.064493   |
|       8 | 2011-12-29 → 2020-12-23 | 2021-01-05 → 2021-06-25  |         635222 |        41045 |           0.02244    |  -0.00201213  |    0.02244    |
|       9 | 2011-12-29 → 2021-12-23 | 2022-01-04 → 2022-06-27  |         722666 |        43575 |          -0.00614856 |  -0.00435966  |   -0.00614856 |
|      10 | 2011-12-29 → 2022-12-23 | 2023-01-05 → 2023-06-28  |         816397 |        46434 |           0.0226472  |   0.00296161  |    0.0226472  |
|      11 | 2011-12-29 → 2023-12-27 | 2024-01-08 → 2024-06-28  |         914058 |        46826 |           0.0206413  |   0.000860973 |    0.0206413  |

- IC Moyen = 0.0161  |  IC Std = 0.0184  |  IC Min = -0.0098  |  IC Max = 0.0645

### Horizon H10 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0171 | IR = 0.67 | Score composite = 0.945 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0171
- **Decile Spread** : 0.0213
- **Nb Features** : 144

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2011-12-29 → 2013-12-13 | 2014-01-02 → 2014-06-17  |         115619 |        28347 |           0.0144235  |    0.00588405 |    0.0144235  |
|       2 | 2011-12-29 → 2014-12-15 | 2015-01-02 → 2015-06-17  |         179485 |        31254 |           0.0539402  |   -0.00904911 |    0.0539402  |
|       3 | 2011-12-29 → 2015-12-15 | 2016-01-04 → 2016-06-16  |         248368 |        32087 |           0.0163367  |   -0.0150944  |    0.0163367  |
|       4 | 2011-12-29 → 2016-12-14 | 2017-01-03 → 2017-06-16  |         319555 |        33186 |          -0.0334042  |    0.0205376  |   -0.0334042  |
|       5 | 2011-12-29 → 2017-12-14 | 2018-01-03 → 2018-06-18  |         392873 |        34721 |          -0.00270265 |    0.0401431  |   -0.00270265 |
|       6 | 2011-12-29 → 2018-12-17 | 2019-01-04 → 2019-06-19  |         469657 |        36100 |          -0.00158889 |    0.0198732  |   -0.00158889 |
|       7 | 2011-12-29 → 2019-12-17 | 2020-01-06 → 2020-06-18  |         549727 |        37790 |           0.0527435  |    0.0109989  |    0.0527435  |
|       8 | 2011-12-29 → 2020-12-16 | 2021-01-05 → 2021-06-18  |         633522 |        39318 |           0.0339088  |   -0.00820359 |    0.0339088  |
|       9 | 2011-12-29 → 2021-12-16 | 2022-01-04 → 2022-06-17  |         720876 |        41705 |          -0.0050172  |   -0.0171661  |   -0.0050172  |
|      10 | 2011-12-29 → 2022-12-16 | 2023-01-05 → 2023-06-21  |         814467 |        44499 |           0.0387494  |    0.0122144  |    0.0387494  |
|      11 | 2011-12-29 → 2023-12-19 | 2024-01-08 → 2024-06-21  |         912108 |        44869 |           0.0208673  |   -0.0103852  |    0.0208673  |

- IC Moyen = 0.0171  |  IC Std = 0.0256  |  IC Min = -0.0334  |  IC Max = 0.0539

### Horizon H15 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0168 | IR = 0.65 | Score composite = 0.945 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0168
- **Decile Spread** : 0.0196
- **Nb Features** : 144

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2011-12-29 → 2013-12-13 | 2014-01-02 → 2014-06-17  |         115619 |        28347 |           0.0238118  |   -0.00208782 |    0.0238118  |
|       2 | 2011-12-29 → 2014-12-15 | 2015-01-02 → 2015-06-17  |         179485 |        31254 |           0.0476714  |    0.00550502 |    0.0476714  |
|       3 | 2011-12-29 → 2015-12-15 | 2016-01-04 → 2016-06-16  |         248368 |        32087 |           0.022155   |    0.00336823 |    0.022155   |
|       4 | 2011-12-29 → 2016-12-14 | 2017-01-03 → 2017-06-16  |         319555 |        33186 |          -0.034615   |   -0.0149947  |   -0.034615   |
|       5 | 2011-12-29 → 2017-12-14 | 2018-01-03 → 2018-06-18  |         392873 |        34721 |          -0.00125036 |    0.0276185  |   -0.00125036 |
|       6 | 2011-12-29 → 2018-12-17 | 2019-01-04 → 2019-06-19  |         469657 |        36100 |          -0.0118381  |    0.0106779  |   -0.0118381  |
|       7 | 2011-12-29 → 2019-12-17 | 2020-01-06 → 2020-06-18  |         549727 |        37790 |           0.0438653  |    0.0013723  |    0.0438653  |
|       8 | 2011-12-29 → 2020-12-16 | 2021-01-05 → 2021-06-18  |         633522 |        39318 |           0.0471608  |   -0.0195113  |    0.0471608  |
|       9 | 2011-12-29 → 2021-12-16 | 2022-01-04 → 2022-06-17  |         720876 |        41705 |          -0.00438306 |    0.0162048  |   -0.00438306 |
|      10 | 2011-12-29 → 2022-12-16 | 2023-01-05 → 2023-06-21  |         814467 |        44499 |           0.0396135  |    0.0104751  |    0.0396135  |
|      11 | 2011-12-29 → 2023-12-19 | 2024-01-08 → 2024-06-21  |         912108 |        44869 |           0.0127274  |   -0.0256991  |    0.0127274  |

- IC Moyen = 0.0168  |  IC Std = 0.0260  |  IC Min = -0.0346  |  IC Max = 0.0477

### Horizon H20 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0173 | IR = 0.59 | Score composite = 0.959 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0173
- **Decile Spread** : 0.0207
- **Nb Features** : 144

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2011-12-29 → 2013-12-13 | 2014-01-02 → 2014-06-17  |         115619 |        28347 |           0.0179961  |    0.0192949  |    0.0179961  |
|       2 | 2011-12-29 → 2014-12-15 | 2015-01-02 → 2015-06-17  |         179485 |        31254 |           0.0599267  |    0.00380834 |    0.0599267  |
|       3 | 2011-12-29 → 2015-12-15 | 2016-01-04 → 2016-06-16  |         248368 |        32087 |           0.0112169  |   -0.0100214  |    0.0112169  |
|       4 | 2011-12-29 → 2016-12-14 | 2017-01-03 → 2017-06-16  |         319555 |        33186 |          -0.0407794  |    0.0407842  |   -0.0407794  |
|       5 | 2011-12-29 → 2017-12-14 | 2018-01-03 → 2018-06-18  |         392873 |        34721 |           0.003262   |    0.0486163  |    0.003262   |
|       6 | 2011-12-29 → 2018-12-17 | 2019-01-04 → 2019-06-19  |         469657 |        36100 |          -0.00923163 |    0.0416705  |   -0.00923163 |
|       7 | 2011-12-29 → 2019-12-17 | 2020-01-06 → 2020-06-18  |         549727 |        37790 |           0.0423432  |   -0.0171915  |    0.0423432  |
|       8 | 2011-12-29 → 2020-12-16 | 2021-01-05 → 2021-06-18  |         633522 |        39318 |           0.0528414  |   -0.0177111  |    0.0528414  |
|       9 | 2011-12-29 → 2021-12-16 | 2022-01-04 → 2022-06-17  |         720876 |        41705 |          -0.00691807 |    0.00213186 |   -0.00691807 |
|      10 | 2011-12-29 → 2022-12-16 | 2023-01-05 → 2023-06-21  |         814467 |        44499 |           0.0434743  |   -0.0237285  |    0.0434743  |
|      11 | 2011-12-29 → 2023-12-19 | 2024-01-08 → 2024-06-21  |         912108 |        44869 |           0.0156722  |   -0.03447    |    0.0156722  |

- IC Moyen = 0.0173  |  IC Std = 0.0291  |  IC Min = -0.0408  |  IC Max = 0.0599


## 🧪 Backtest Stratégies — Global Rank (H5 seul)

| Variante | Score relatif |
|----------|---------------|
| V1 — H5 seul | 🏆 référence |
| V4 — H5 + top 3 horizons ↑ (H5,H10,H20) | -15.3% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H5 seul (V2/V3 non calculés — H5 est déjà le meilleur horizon). V4 = H5 + top 3 horizons ↑ (H5,H10,H20).

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
|         3 |      0.33  |      0.498 |     0.494 |    0.4998 |
|         5 |      0.329 |      0.49  |     0.496 |    0.4979 |
|        10 |      0.328 |      0.488 |     0.497 |    0.4975 |
|        15 |      0.328 |      0.485 |     0.499 |    0.4981 |
|        20 |      0.329 |      0.486 |     0.5   |    0.4991 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.332 |          0.508 |             0 |         0.487 |
| catboost     | test         |           11 |          0.335 |          0.516 |             0 |         0.488 |
| catboost     | wf           |           11 |          0.328 |          0.489 |             0 |         0.496 |
| lightgbm     | val          |           11 |          0.331 |          0.507 |             0 |         0.485 |
| lightgbm     | test         |           11 |          0.332 |          0.515 |             0 |         0.481 |
| lightgbm     | wf           |           11 |          0.329 |          0.489 |             0 |         0.499 |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               52.107 |                   0 |              47.893 |               49.999 |               0.002 |              49.999 |
| catboost     | test         |           11 |               51.899 |                   0 |              48.101 |               50.767 |               0     |              49.233 |
| catboost     | wf           |           11 |               51.856 |                   0 |              48.144 |               47.548 |               0     |              52.452 |
| lightgbm     | val          |           11 |               52.107 |                   0 |              47.893 |               49.999 |               0.003 |              49.999 |
| lightgbm     | test         |           11 |               51.899 |                   0 |              48.101 |               51.327 |               0     |              48.673 |
| lightgbm     | wf           |           11 |               51.856 |                   0 |              48.144 |               47.227 |               0     |              52.773 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Information Technology |      0.337 |     0.512 |      0.499 |         0 |
| Information Technology |      0.336 |     0.507 |      0.502 |         0 |
| Industrials            |      0.335 |     0.507 |      0.499 |         0 |
| Industrials            |      0.335 |     0.506 |      0.499 |         0 |
| Health Care            |      0.335 |     0.507 |      0.498 |         0 |
| Information Technology |      0.335 |     0.506 |      0.499 |         0 |
| Real Estate            |      0.335 |     0.535 |      0.47  |         0 |
| Real Estate            |      0.334 |     0.532 |      0.471 |         0 |
| Real Estate            |      0.334 |     0.527 |      0.475 |         0 |
| Consumer Discretionary |      0.334 |     0.521 |      0.481 |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples       |      0.322 |     0.494 |      0.47  |         0 |
| Materials              |      0.322 |     0.445 |      0.521 |         0 |
| Utilities              |      0.323 |     0.488 |      0.483 |         0 |
| Communication Services |      0.325 |     0.493 |      0.48  |         0 |
| Health Care            |      0.325 |     0.507 |      0.468 |         0 |
| Utilities              |      0.325 |     0.513 |      0.463 |         0 |
| Utilities              |      0.325 |     0.487 |      0.489 |         0 |
| Consumer Staples       |      0.326 |     0.479 |      0.498 |         0 |
| Materials              |      0.326 |     0.455 |      0.523 |         0 |
| Materials              |      0.326 |     0.466 |      0.512 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    0.9845 |        0.4981 |
| catboost     | test         |           11 |    1.1088 |        0.5065 |
| catboost     | wf           |           11 |    1.1212 |        0.4983 |
| lightgbm     | val          |           11 |    1.0017 |        0.4963 |
| lightgbm     | test         |           11 |    1.1294 |        0.5027 |
| lightgbm     | wf           |           11 |    1.1461 |        0.4986 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| catboost     | Energy                 |    0.512  | 1.029  |
| catboost     | Information Technology |    0.5093 | 1.0556 |
| lightgbm     | Consumer Staples       |    0.5088 | 1.1299 |
| catboost     | Energy                 |    0.5086 | 1.0138 |
| catboost     | Information Technology |    0.5077 | 1.0253 |
| lightgbm     | Real Estate            |    0.5075 | 1.0269 |
| catboost     | Energy                 |    0.5075 | 1.0019 |
| lightgbm     | Real Estate            |    0.5074 | 1.086  |
| lightgbm     | Industrials            |    0.5072 | 1.1744 |
| lightgbm     | Industrials            |    0.5072 | 1.1417 |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| catboost     | Communication Services |    0.4785 | 1.1473 |
| catboost     | Communication Services |    0.4803 | 1.115  |
| lightgbm     | Materials              |    0.4816 | 1.064  |
| catboost     | Communication Services |    0.4818 | 1.1915 |
| catboost     | Utilities              |    0.485  | 1.2078 |
| lightgbm     | Materials              |    0.487  | 1.2343 |
| catboost     | Consumer Staples       |    0.4873 | 1.088  |
| lightgbm     | Materials              |    0.4874 | 1.194  |
| catboost     | Utilities              |    0.4891 | 1.1738 |
| lightgbm     | Materials              |    0.4894 | 1.1271 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % | VIX moy   |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|:----------|--------------:|
|       0 | 2014-07-03  | 2014-12-31 | —                 |      0.341 |      0.495 |         0 |     0.528 | —           |     3.7 | —         |            11 |
|       1 | 2015-07-06  | 2015-12-31 | —                 |      0.328 |      0.508 |         0 |     0.475 | —           |    -1.4 | —         |            11 |
|       2 | 2016-07-05  | 2016-12-30 | —                 |      0.329 |      0.498 |         0 |     0.489 | —           |     7.3 | —         |            11 |
|       3 | 2017-07-05  | 2018-01-02 | 🟢 Bull           |      0.332 |      0.522 |         0 |     0.473 | —           |    10.7 | 9.8       |            11 |
|       4 | 2018-07-05  | 2019-01-03 | 🔵 Range low vol  |      0.326 |      0.487 |         0 |     0.491 | —           |   -10.6 | 17.1      |            11 |
|       5 | 2019-07-08  | 2020-01-03 | 🟢 Bull           |      0.322 |      0.466 |         0 |     0.501 | —           |     8.6 | 15.0      |            11 |
|       6 | 2020-07-07  | 2021-01-04 | 🔵 Range low vol  |      0.327 |      0.453 |         0 |     0.528 | —           |    17.5 | 25.7      |            11 |
|       7 | 2021-07-07  | 2022-02-01 | 🔵 Range low vol  |      0.316 |      0.425 |         0 |     0.523 | —           |     4.3 | 19.5      |            11 |
|       8 | 2022-08-04  | 2023-02-02 | 🟠 Range high vol |      0.342 |      0.5   |         0 |     0.526 | —           |     0.6 | 24.1      |            11 |
|       9 | 2023-08-07  | 2024-03-05 | 🟢 Bull           |      0.314 |      0.487 |         0 |     0.455 | —           |    12.5 | 14.9      |            11 |
|      10 | 2024-09-05  | 2025-03-07 | 🔵 Range low vol  |      0.335 |      0.5   |         0 |     0.506 | —           |     4.8 | 17.5      |            11 |
