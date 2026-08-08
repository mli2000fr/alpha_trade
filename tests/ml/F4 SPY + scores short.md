# Diagnostic ML — Batch `model-factory-20260808130525-0a3695`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260808130525-0a3695`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : F4 SPY + scores short
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0197
- **📈 IC IR (Stabilité)** : 1.07  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0104 H5=0.0191 H10=0.0246 H15=0.0313 H20=0.0319
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-08 13:05:25
- **Terminé le** : 2026-08-08 15:02:30
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-short-score --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "F4 SPY + scores short"
```

## 🏆 Sélection du champion

✅ **Tout va bien** — 11 champions sélectionnés automatiquement sur 11 symboles.

### 📊 Champions par modèle

| model_name   |   nb_symbols |
|:-------------|-------------:|
| catboost     |            7 |
| lightgbm     |            4 |

## 🌐 Global Ranking — Détails par Horizon

Modèle Catboost — 400 symboles, 6 splits walk-forward, 259239 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |   IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits |
|:----------|----------:|--------:|----------------:|--------------:|------------:|
| H3        | 0.012492  |    0.99 |       0.0104378 |           144 |           6 |
| H5        | 0.0187099 |    1.14 |       0.0190906 |           144 |           6 |
| H10       | 0.0227906 |    1.36 |       0.0245611 |           144 |           6 |
| H15       | 0.0235654 |    1.34 |       0.0313003 |           144 |           6 |
| H20       | 0.020847  |    0.84 |       0.0319404 |           144 |           6 |

### Horizon H3

- **IC Rank** : 0.0125
- **Decile Spread** : 0.0104
- **Nb Features** : 144

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |     IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|------------:|
|       1 | 2016-12-29 → 2018-12-24 | 2019-01-02 → 2019-06-26  |         149065 |        38302 |  0.00698735 |
|       2 | 2016-12-29 → 2019-12-24 | 2020-01-02 → 2020-06-25  |         229215 |        40109 |  0.0315175  |
|       3 | 2016-12-29 → 2020-12-23 | 2020-12-31 → 2021-06-25  |         313075 |        41725 |  0.0249394  |
|       4 | 2016-12-29 → 2021-12-23 | 2021-12-31 → 2022-06-27  |         400519 |        44291 | -0.00695602 |
|       5 | 2016-12-29 → 2022-12-23 | 2023-01-03 → 2023-06-28  |         494250 |        47206 |  0.0104178  |
|       6 | 2016-12-29 → 2023-12-27 | 2024-01-04 → 2024-06-28  |         591911 |        47606 |  0.00804597 |

- IC Moyen = 0.0125  |  IC Std = 0.0126  |  IC Min = -0.0070  |  IC Max = 0.0315

### Horizon H5

- **IC Rank** : 0.0187
- **Decile Spread** : 0.0191
- **Nb Features** : 144

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |     IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|------------:|
|       1 | 2016-12-29 → 2018-12-20 | 2019-01-02 → 2019-06-24  |         148443 |        37670 |  0.00853898 |
|       2 | 2016-12-29 → 2019-12-20 | 2020-01-02 → 2020-06-23  |         228561 |        39443 |  0.0482733  |
|       3 | 2016-12-29 → 2020-12-21 | 2020-12-31 → 2021-06-23  |         312395 |        41033 |  0.0189526  |
|       4 | 2016-12-29 → 2021-12-21 | 2021-12-31 → 2022-06-23  |         399803 |        43543 | -0.00556458 |
|       5 | 2016-12-29 → 2022-12-21 | 2023-01-03 → 2023-06-26  |         493478 |        46432 |  0.0246181  |
|       6 | 2016-12-29 → 2023-12-22 | 2024-01-04 → 2024-06-26  |         591131 |        46822 |  0.0174411  |

- IC Moyen = 0.0187  |  IC Std = 0.0163  |  IC Min = -0.0056  |  IC Max = 0.0483

### Horizon H10

- **IC Rank** : 0.0228
- **Decile Spread** : 0.0246
- **Nb Features** : 144

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |      IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|-------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 | -5.48477e-05 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |  0.0407364   |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |  0.0410689   |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |  0.00385568  |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |  0.0339034   |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |  0.017234    |

- IC Moyen = 0.0228  |  IC Std = 0.0168  |  IC Min = -0.0001  |  IC Max = 0.0411

### Horizon H15

- **IC Rank** : 0.0236
- **Decile Spread** : 0.0313
- **Nb Features** : 144

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |     IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 | 0.000695107 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 | 0.0350043   |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 | 0.0471697   |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 | 0.00447796  |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 | 0.0381476   |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 | 0.0158976   |

- IC Moyen = 0.0236  |  IC Std = 0.0175  |  IC Min = 0.0007  |  IC Max = 0.0472

### Horizon H20

- **IC Rank** : 0.0208
- **Decile Spread** : 0.0319
- **Nb Features** : 144

#### 📅 Détail par split

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |      IC Rank |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|-------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 | -0.0121295   |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |  0.0272817   |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |  0.0553934   |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 | -8.40832e-05 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |  0.0477765   |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |  0.00684377  |

- IC Moyen = 0.0208  |  IC Std = 0.0248  |  IC Min = -0.0121  |  IC Max = 0.0554


## 🧪 Backtest Stratégies — Global Rank

| Variante | Score relatif |
|----------|---------------|
| V1 — H20 seul | 🏆 référence |
| V2 — H20 + H5 rising | -4.4% |
| V3 — H20 + H5 < 0.35 | -34.5% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H20 seul, V2 = H20 + H5 rising, V3 = H20 + H5 < 0.35 (contrarian).

---

## 🔵 Per-Symbol / Per-Sector — Métriques d'entraînement

## 📊 Métriques par Horizon (WF)

|   Horizon |   F1 macro |   F1 short |   F1 long |   Dir Acc |
|----------:|-----------:|-----------:|----------:|----------:|
|         3 |      0.331 |      0.489 |     0.504 |    0.5016 |
|         5 |      0.329 |      0.474 |     0.513 |    0.5011 |
|        10 |      0.328 |      0.474 |     0.511 |    0.5014 |
|        15 |      0.329 |      0.474 |     0.512 |    0.5022 |
|        20 |      0.328 |      0.474 |     0.509 |    0.5011 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.332 |          0.508 |             0 |         0.489 |
| catboost     | test         |           11 |          0.331 |          0.524 |             0 |         0.468 |
| catboost     | wf           |           11 |          0.328 |          0.475 |             0 |         0.51  |
| lightgbm     | val          |           11 |          0.331 |          0.507 |             0 |         0.487 |
| lightgbm     | test         |           11 |          0.329 |          0.512 |             0 |         0.475 |
| lightgbm     | wf           |           11 |          0.33  |          0.479 |             0 |         0.51  |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| catboost     | test         |           11 |               51.925 |                   0 |              48.075 |               53.672 |               0     |              46.328 |
| catboost     | wf           |           11 |               51.407 |                   0 |              48.593 |               45.173 |               0     |              54.827 |
| lightgbm     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.005 |              49.998 |
| lightgbm     | test         |           11 |               51.925 |                   0 |              48.075 |               51.631 |               0     |              48.369 |
| lightgbm     | wf           |           11 |               51.407 |                   0 |              48.593 |               45.609 |               0     |              54.391 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.20-0.29            |            1 |
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol           |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples |      0.366 |     0.561 |      0.537 |         0 |
| Consumer Staples |      0.358 |     0.554 |      0.52  |         0 |
| Consumer Staples |      0.35  |     0.534 |      0.516 |         0 |
| Health Care      |      0.342 |     0.537 |      0.488 |         0 |
| Health Care      |      0.34  |     0.526 |      0.494 |         0 |
| Consumer Staples |      0.34  |     0.537 |      0.482 |         0 |
| Health Care      |      0.339 |     0.526 |      0.492 |         0 |
| Health Care      |      0.336 |     0.53  |      0.478 |         0 |
| Industrials      |      0.336 |     0.51  |      0.498 |         0 |
| Industrials      |      0.336 |     0.501 |      0.507 |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Energy                 |      0.296 |     0.444 |      0.444 |         0 |
| Energy                 |      0.3   |     0.446 |      0.453 |         0 |
| Energy                 |      0.307 |     0.441 |      0.479 |         0 |
| Utilities              |      0.315 |     0.575 |      0.369 |         0 |
| Energy                 |      0.315 |     0.469 |      0.476 |         0 |
| Real Estate            |      0.315 |     0.498 |      0.448 |         0 |
| Utilities              |      0.316 |     0.551 |      0.397 |         0 |
| Utilities              |      0.317 |     0.562 |      0.389 |         0 |
| Utilities              |      0.317 |     0.583 |      0.369 |         0 |
| Information Technology |      0.319 |     0.509 |      0.449 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    1.0655 |        0.4989 |
| catboost     | test         |           11 |    1.0872 |        0.4993 |
| catboost     | wf           |           11 |    1.0437 |        0.5008 |
| lightgbm     | val          |           11 |    1.0808 |        0.4972 |
| lightgbm     | test         |           11 |    1.1091 |        0.4959 |
| lightgbm     | wf           |           11 |    1.0621 |        0.5022 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol           |   dir_acc |    mse |
|:-------------|:-----------------|----------:|-------:|
| lightgbm     | Consumer Staples |    0.5499 | 0.914  |
| lightgbm     | Consumer Staples |    0.5409 | 0.9097 |
| catboost     | Consumer Staples |    0.5389 | 0.8849 |
| catboost     | Consumer Staples |    0.5317 | 0.8987 |
| lightgbm     | Consumer Staples |    0.5278 | 0.9249 |
| catboost     | Consumer Staples |    0.5259 | 0.9165 |
| catboost     | Consumer Staples |    0.5177 | 0.9393 |
| lightgbm     | Industrials      |    0.5172 | 1.0453 |
| lightgbm     | Industrials      |    0.5166 | 1.0131 |
| lightgbm     | Financials       |    0.5157 | 1.1359 |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| catboost     | Communication Services |    0.4705 | 1.0535 |
| lightgbm     | Materials              |    0.4713 | 1.0995 |
| lightgbm     | Materials              |    0.4779 | 1.0877 |
| catboost     | Communication Services |    0.4798 | 1.0289 |
| catboost     | Communication Services |    0.4817 | 1.0089 |
| lightgbm     | Energy                 |    0.4846 | 1.016  |
| catboost     | Materials              |    0.4854 | 1.0411 |
| catboost     | Information Technology |    0.486  | 1.1028 |
| lightgbm     | Communication Services |    0.4865 | 1.0795 |
| lightgbm     | Materials              |    0.4868 | 1.0283 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.32  |      0.439 |         0 |     0.523 | —           |     7.7 |      15   |            11 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.33  |      0.439 |         0 |     0.551 | —           |    19.1 |      25.7 |            11 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.325 |      0.459 |         0 |     0.515 | —           |     9.8 |      18.8 |            11 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.338 |      0.5   |         0 |     0.515 | —           |     0.1 |      24.9 |            11 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.317 |      0.491 |         0 |     0.46  | —           |     9   |      15.1 |            11 |
|       5 | 2024-09-03  | 2025-03-05 | 🟢 Bull           |      0.327 |      0.502 |         0 |     0.48  | —           |     5.6 |      17.4 |            11 |
