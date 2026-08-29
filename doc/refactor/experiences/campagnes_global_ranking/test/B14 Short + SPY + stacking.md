# Diagnostic ML — Batch `model-factory-20260811073138-0a0b4f`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260811073138-0a0b4f`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : B14 Short + SPY + stacking
- **Date début training** : 2016-01-01
- **Date fin training** : 2025-12-31
- **Date univers** : 2025-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0196
- **📈 IC IR (Stabilité)** : 1.03  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0094 H5=0.0211 H10=0.0269 H15=0.0275 H20=0.0305
- **🏆 Champion Global** : catboost (H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — score composite 55% IC + 30% IR + 15% positifs
- **📥 Stacking Global Rank** : Oui
- **Démarré le** : 2026-08-11 07:31:38
- **Terminé le** : 2026-08-11 08:38:42
- **Complétés / Skippés / Échecs** : 11 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --accelerator auto --target-mode regression --num-classes 1 --training-mode per_sector --forecast-horizons 3,5,10,15,20 --target-up-threshold 0.03 --target-down-threshold -0.03 --decision-threshold 0.55 --calibration-method platt --calibration-min-samples 64 --calibration-max-iter 100 --feature-set expert --benchmark-symbol SPY --sequence-length 40 --batch-size 32 --hidden-size 256 --ml-mode rebuild-all --training-start-date 2016-01-01 --symbol-source ticket-recherche --artifacts-dir artifacts/models --max-workers 6 --max-epochs 50 --patience 5 --cross-sectional-min-universe 20 --lgbm-max-depth 5 --lgbm-n-estimators 200 --lgbm-learning-rate 0.03 --catboost-depth 6 --catboost-iterations 300 --catboost-learning-rate 0.03 --lgbm-reg-alpha 0.1 --lgbm-reg-lambda 0.1 --lgbm-min-child-samples 150 --lgbm-subsample 0.8 --lgbm-colsample-bytree 0.7 --catboost-l2-leaf-reg 3.0 --catboost-border-count 128 --catboost-random-strength 1.0 --catboost-bagging-temperature 1.0 --catboost-od-type IncToDec --catboost-od-wait 20 --default-champion lstm_attention --heartbeat-interval-seconds 60.0 --log-level INFO --training-end-date 2025-12-31 --include-short-score --no-include-score-components --target-excess-vs-spy --compare-lightgbm --enable-catboost --enable-global-model --global-model-name catboost --global-champion --enable-global-stacking --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 252 --wf-max-splits 8 --comment "B14 Short + SPY + stacking"
```

## 🌐 Global Ranking — Détails par Horizon

Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symboles, 6 splits walk-forward, 259239 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |    IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits | 🏆 Champion   |   Score |   IC catboost |   IR catboost |   IC lightgbm |   IR lightgbm |
|:----------|-----------:|--------:|----------------:|--------------:|------------:|:--------------|--------:|--------------:|--------------:|--------------:|--------------:|
| H3        | 0.00984114 |    0.86 |      0.00936302 |           144 |           6 | catboost      |   0.975 |        0.0098 |          0.86 |        0.0022 |          0.2  |
| H5        | 0.020253   |    1.08 |      0.0210671  |           144 |           6 | catboost      |   0.975 |        0.0203 |          1.08 |        0.0089 |          0.64 |
| H10       | 0.0238284  |    1.37 |      0.0269238  |           144 |           6 | catboost      |   0.975 |        0.0238 |          1.37 |        0.0105 |          0.4  |
| H15       | 0.0212565  |    1.18 |      0.0274783  |           144 |           6 | catboost      |   0.95  |        0.0213 |          1.18 |        0.0207 |          0.76 |
| H20       | 0.0228482  |    0.95 |      0.0304885  |           144 |           6 | catboost      |   0.975 |        0.0228 |          0.95 |        0.0084 |          0.3  |


🏆 **Meilleur horizon : H10** — sélectionné par score composite 55% IC + 30% IR + 15% Positive Split  |  H3=0.5407  H5=0.8295  H10=0.9750  H15=0.8490  H20=0.8620
### Horizon H3 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0098 | IR = 0.86 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0098
- **Decile Spread** : 0.0094
- **Nb Features** : 144

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-24 | 2019-01-02 → 2019-06-26  |         149065 |        38302 |           0.00157555 |   0.0219116   |    0.00157555 |
|       2 | 2016-12-29 → 2019-12-24 | 2020-01-02 → 2020-06-25  |         229215 |        40109 |           0.0234234  |   0.0107596   |    0.0234234  |
|       3 | 2016-12-29 → 2020-12-23 | 2020-12-31 → 2021-06-25  |         313075 |        41725 |           0.0235403  |  -0.00638592  |    0.0235403  |
|       4 | 2016-12-29 → 2021-12-23 | 2021-12-31 → 2022-06-27  |         400519 |        44291 |          -0.00881742 |  -0.0112203   |   -0.00881742 |
|       5 | 2016-12-29 → 2022-12-23 | 2023-01-03 → 2023-06-28  |         494250 |        47206 |           0.0101264  |   7.41997e-05 |    0.0101264  |
|       6 | 2016-12-29 → 2023-12-27 | 2024-01-04 → 2024-06-28  |         591911 |        47606 |           0.00919857 |  -0.00203443  |    0.00919857 |

- IC Moyen = 0.0098  |  IC Std = 0.0115  |  IC Min = -0.0088  |  IC Max = 0.0235

### Horizon H5 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0203 | IR = 1.08 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0203
- **Decile Spread** : 0.0211
- **Nb Features** : 144

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-20 | 2019-01-02 → 2019-06-24  |         148443 |        37670 |           0.00571957 |    0.0307047  |    0.00571957 |
|       2 | 2016-12-29 → 2019-12-20 | 2020-01-02 → 2020-06-23  |         228561 |        39443 |           0.0547265  |    0.0235988  |    0.0547265  |
|       3 | 2016-12-29 → 2020-12-21 | 2020-12-31 → 2021-06-23  |         312395 |        41033 |           0.0232875  |    0.00302142 |    0.0232875  |
|       4 | 2016-12-29 → 2021-12-21 | 2021-12-31 → 2022-06-23  |         399803 |        43543 |          -0.00556458 |   -0.00717133 |   -0.00556458 |
|       5 | 2016-12-29 → 2022-12-21 | 2023-01-03 → 2023-06-26  |         493478 |        46432 |           0.025908   |    0.00779681 |    0.025908   |
|       6 | 2016-12-29 → 2023-12-22 | 2024-01-04 → 2024-06-26  |         591131 |        46822 |           0.0174411  |   -0.00430498 |    0.0174411  |

- IC Moyen = 0.0203  |  IC Std = 0.0188  |  IC Min = -0.0056  |  IC Max = 0.0547

### Horizon H10 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0238 | IR = 1.37 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0238
- **Decile Spread** : 0.0269
- **Nb Features** : 144

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |           0.0103822  |    0.0157906  |    0.0103822  |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |           0.0439643  |    0.0657406  |    0.0439643  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |           0.0416025  |   -0.0082035  |    0.0416025  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |          -0.00411599 |   -0.00543953 |   -0.00411599 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |           0.0339034  |    0.00272926 |    0.0339034  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |           0.017234   |   -0.00742048 |    0.017234   |

- IC Moyen = 0.0238  |  IC Std = 0.0175  |  IC Min = -0.0041  |  IC Max = 0.0440

### Horizon H15 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0213 | IR = 1.18 | Score composite = 0.950 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0213
- **Decile Spread** : 0.0275
- **Nb Features** : 144

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |          -0.00024891 |    0.0103086  |   -0.00024891 |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |           0.0356343  |    0.0764362  |    0.0356343  |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |           0.0410564  |    0.0323214  |    0.0410564  |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |          -0.00294804 |    0.00286629 |   -0.00294804 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |           0.0381476  |   -0.00114411 |    0.0381476  |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |           0.0158976  |    0.00363809 |    0.0158976  |

- IC Moyen = 0.0213  |  IC Std = 0.0181  |  IC Min = -0.0029  |  IC Max = 0.0411

### Horizon H20 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0228 | IR = 0.95 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0228
- **Decile Spread** : 0.0305
- **Nb Features** : 144

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |         -0.00983447  |    0.00510909 |  -0.00983447  |
|       2 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37778 |          0.030544    |    0.0636843  |   0.030544    |
|       3 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310695 |        39308 |          0.0557932   |   -0.0249155  |   0.0557932   |
|       4 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398013 |        41676 |          0.000615244 |   -0.00773836 |   0.000615244 |
|       5 | 2016-12-29 → 2022-12-14 | 2023-01-03 → 2023-06-16  |         491548 |        44497 |          0.0477765   |   -0.00176406 |   0.0477765   |
|       6 | 2016-12-29 → 2023-12-15 | 2024-01-04 → 2024-06-18  |         589181 |        44867 |          0.012195    |    0.0159656  |   0.012195    |

- IC Moyen = 0.0228  |  IC Std = 0.0240  |  IC Min = -0.0098  |  IC Max = 0.0558


## 🧪 Backtest Stratégies — Global Rank (H10 + H5)

| Variante | Score relatif |
|----------|---------------|
| V1 — H10 seul | 🏆 référence |
| V2 — H10 + H5 rising | -0.1% |
| V3 — H10 + H5 < 0.35 | -25.8% |
| V4 — H10 + top 3 horizons ↑ (H10,H20,H15) | -12.4% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H10 seul, V2 = H10 + H5 rising, V3 = H10 + H5 < 0.35 (contrarian). V4 = H10 + top 3 horizons ↑ (H10,H20,H15).

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
|         3 |      0.33  |      0.488 |     0.503 |    0.5014 |
|         5 |      0.329 |      0.472 |     0.514 |    0.5007 |
|        10 |      0.328 |      0.473 |     0.512 |    0.502  |
|        15 |      0.329 |      0.474 |     0.513 |    0.5027 |
|        20 |      0.327 |      0.473 |     0.509 |    0.5002 |

## 📊 Métriques F1 par split

| model_name   | split_name   |   nb_symbols |   avg_f1_macro |   avg_f1_short |   avg_f1_flat |   avg_f1_long |
|:-------------|:-------------|-------------:|---------------:|---------------:|--------------:|--------------:|
| catboost     | val          |           11 |          0.332 |          0.508 |             0 |         0.489 |
| catboost     | test         |           11 |          0.329 |          0.522 |             0 |         0.466 |
| catboost     | wf           |           11 |          0.328 |          0.473 |             0 |         0.511 |
| lightgbm     | val          |           11 |          0.332 |          0.507 |             0 |         0.488 |
| lightgbm     | test         |           11 |          0.328 |          0.509 |             0 |         0.474 |
| lightgbm     | wf           |           11 |          0.33  |          0.479 |             0 |         0.51  |

## 📊 Distribution true / pred par split

| model_name   | split_name   |   nb_symbols |   avg_true_short_pct |   avg_true_flat_pct |   avg_true_long_pct |   avg_pred_short_pct |   avg_pred_flat_pct |   avg_pred_long_pct |
|:-------------|:-------------|-------------:|---------------------:|--------------------:|--------------------:|---------------------:|--------------------:|--------------------:|
| catboost     | val          |           11 |               51.936 |                   0 |              48.064 |               49.998 |               0.004 |              49.998 |
| catboost     | test         |           11 |               51.925 |                   0 |              48.075 |               53.579 |               0     |              46.421 |
| catboost     | wf           |           11 |               51.407 |                   0 |              48.593 |               44.956 |               0     |              55.044 |
| lightgbm     | val          |           11 |               51.936 |                   0 |              48.064 |               49.997 |               0.005 |              49.998 |
| lightgbm     | test         |           11 |               51.925 |                   0 |              48.075 |               51.447 |               0     |              48.553 |
| lightgbm     | wf           |           11 |               51.407 |                   0 |              48.593 |               45.606 |               0     |              54.394 |

## 📈 Distribution F1 macro — Walk-Forward

| wf_f1_macro_bucket   |   nb_symbols |
|:---------------------|-------------:|
| 0.20-0.29            |            1 |
| 0.30-0.39            |           11 |

## 🏆 Top 10 meilleurs `f1_macro` (WF)

| symbol           |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------|-----------:|----------:|-----------:|----------:|
| Consumer Staples |      0.356 |     0.558 |      0.511 |         0 |
| Consumer Staples |      0.354 |     0.56  |      0.501 |         0 |
| Industrials      |      0.345 |     0.509 |      0.525 |         0 |
| Consumer Staples |      0.344 |     0.547 |      0.486 |         0 |
| Industrials      |      0.343 |     0.506 |      0.523 |         0 |
| Industrials      |      0.342 |     0.499 |      0.527 |         0 |
| Industrials      |      0.342 |     0.507 |      0.519 |         0 |
| Consumer Staples |      0.338 |     0.554 |      0.461 |         0 |
| Health Care      |      0.338 |     0.532 |      0.482 |         0 |
| Industrials      |      0.337 |     0.497 |      0.515 |         0 |

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

| symbol                 |   f1_macro |   f1_long |   f1_short |   f1_flat |
|:-----------------------|-----------:|----------:|-----------:|----------:|
| Energy                 |      0.294 |     0.422 |      0.46  |         0 |
| Energy                 |      0.304 |     0.461 |      0.451 |         0 |
| Energy                 |      0.308 |     0.452 |      0.473 |         0 |
| Utilities              |      0.31  |     0.534 |      0.396 |         0 |
| Utilities              |      0.311 |     0.574 |      0.36  |         0 |
| Utilities              |      0.313 |     0.567 |      0.373 |         0 |
| Energy                 |      0.317 |     0.476 |      0.474 |         0 |
| Utilities              |      0.319 |     0.554 |      0.402 |         0 |
| Communication Services |      0.32  |     0.519 |      0.441 |         0 |
| Information Technology |      0.321 |     0.516 |      0.445 |         0 |

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

| model_name   | split_name   |   nb_symbols |   avg_mse |   avg_dir_acc |
|:-------------|:-------------|-------------:|----------:|--------------:|
| catboost     | val          |           11 |    1.0667 |        0.4989 |
| catboost     | test         |           11 |    1.088  |        0.4973 |
| catboost     | wf           |           11 |    1.0442 |        0.501  |
| lightgbm     | val          |           11 |    1.08   |        0.4977 |
| lightgbm     | test         |           11 |    1.1085 |        0.4941 |
| lightgbm     | wf           |           11 |    1.0618 |        0.5018 |

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

| model_name   | symbol           |   dir_acc |    mse |
|:-------------|:-----------------|----------:|-------:|
| lightgbm     | Consumer Staples |    0.5476 | 0.913  |
| catboost     | Consumer Staples |    0.5391 | 0.8989 |
| lightgbm     | Consumer Staples |    0.5364 | 0.9142 |
| catboost     | Consumer Staples |    0.5343 | 0.8923 |
| lightgbm     | Consumer Staples |    0.5265 | 0.9271 |
| catboost     | Health Care      |    0.5214 | 1.0577 |
| catboost     | Consumer Staples |    0.5201 | 0.9252 |
| lightgbm     | Consumer Staples |    0.5184 | 0.9384 |
| lightgbm     | Financials       |    0.5182 | 1.1256 |
| lightgbm     | Industrials      |    0.5181 | 1.0442 |

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

| model_name   | symbol                 |   dir_acc |    mse |
|:-------------|:-----------------------|----------:|-------:|
| lightgbm     | Materials              |    0.4635 | 1.1047 |
| catboost     | Communication Services |    0.4741 | 1.0412 |
| catboost     | Communication Services |    0.4775 | 1.0282 |
| lightgbm     | Materials              |    0.4788 | 1.0852 |
| catboost     | Communication Services |    0.4823 | 1.007  |
| lightgbm     | Utilities              |    0.4835 | 1.4325 |
| lightgbm     | Communication Services |    0.4864 | 1.0798 |
| lightgbm     | Energy                 |    0.4866 | 1.0146 |
| catboost     | Materials              |    0.4871 | 1.048  |
| lightgbm     | Materials              |    0.4876 | 0.9485 |

## 📅 Diagnostic par régime de marché — Walk-Forward

|   Split | Début OOS   | Fin OOS    | Régime            |   F1 macro |   F1 short |   F1 flat |   F1 long | Tx action   |   SPY % |   VIX moy |   Nb symboles |
|--------:|:------------|:-----------|:------------------|-----------:|-----------:|----------:|----------:|:------------|--------:|----------:|--------------:|
|       0 | 2019-07-03  | 2019-12-31 | 🟢 Bull           |      0.32  |      0.438 |         0 |     0.521 | —           |     7.7 |      15   |            11 |
|       1 | 2020-07-02  | 2020-12-30 | 🔵 Range low vol  |      0.331 |      0.442 |         0 |     0.55  | —           |    19.1 |      25.7 |            11 |
|       2 | 2021-07-02  | 2021-12-30 | 🔵 Range low vol  |      0.322 |      0.454 |         0 |     0.512 | —           |     9.8 |      18.8 |            11 |
|       3 | 2022-07-05  | 2022-12-30 | 🟠 Range high vol |      0.337 |      0.496 |         0 |     0.514 | —           |     0.1 |      24.9 |            11 |
|       4 | 2023-08-03  | 2024-02-01 | 🟢 Bull           |      0.321 |      0.495 |         0 |     0.467 | —           |     9   |      15.1 |            11 |
|       5 | 2024-09-03  | 2025-03-05 | 🟢 Bull           |      0.33  |      0.502 |         0 |     0.488 | —           |     5.6 |      17.4 |            11 |
