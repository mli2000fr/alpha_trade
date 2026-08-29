# Diagnostic ML — Batch `model-factory-20260814204243-9535a3`

## 📋 Détail du batch

- **Batch ID** : `model-factory-20260814204243-9535a3`
- **Statut** : completed
- **Source symboles** : ticket-recherche
- **Commentaire** : B44-B41-config-global-only-train-end-2024-12-31
- **Date début training** : 2016-01-01
- **Date fin training** : 2024-12-31
- **Date univers** : 2024-12-31
- **Nb symboles demandés** : None
- **🎯 IC Rank Global** : 0.0199
- **📈 IC IR (Stabilité)** : 1.55  (IC Mean / IC Std)
- **📊 Decile Spread (Top−Bottom)** : H3=0.0168 H5=0.0231 H10=0.0212 H15=0.0269 H20=0.0224
- **🏆 Champion Global** : catboost (H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — score composite 55% IC + 30% IR + 15% positifs
- **📥 Stacking Global Rank** : Non
- **Démarré le** : 2026-08-14 20:42:44
- **Terminé le** : 2026-08-14 22:45:22
- **Complétés / Skippés / Échecs** : 1 / 0 / 0

### Commande exécutée
```powershell
python -m modelFactory --mode train --global-model-only --training-mode per_sector --target-mode regression --forecast-horizons 3,5,10,15,20 --feature-set expert --benchmark-symbol SPY --training-start-date 2016-01-01 --training-end-date 2024-12-31 --symbol-source ticket-recherche --catboost-loss-function YetiRank --include-short-score --target-excess-vs-spy --include-factors --include-volume-features --no-include-score-components --enable-global-model --global-model-name catboost --global-champion --select-champion --walkforward --wf-max-splits 8 --comment B44-B41-config-global-only-train-end-2024-12-31
```

## 🌐 Global Ranking — Détails par Horizon

Modèle 🏆 Champion: catboost (détail: H3=catboost, H5=catboost, H10=catboost, H15=catboost, H20=catboost) — sélection par IC IR — 400 symboles, 8 splits walk-forward, 334353 lignes de prédiction

### 📋 Récapitulatif tous horizons

| Horizon   |   IC Mean |   IC IR |   Decile Spread |   Nb Features |   Nb Splits | 🏆 Champion   |   Score |   IC catboost |   IR catboost |   IC lightgbm |   IR lightgbm |   IC xgboost |   IR xgboost |
|:----------|----------:|--------:|----------------:|--------------:|------------:|:--------------|--------:|--------------:|--------------:|--------------:|--------------:|-------------:|-------------:|
| H3        | 0.017401  |    1.37 |       0.0168311 |           155 |           8 | catboost      |   0.981 |        0.0174 |          1.37 |        0.0058 |          0.33 |       0.0054 |         0.28 |
| H5        | 0.0189751 |    1.15 |       0.0231269 |           155 |           8 | catboost      |   0.981 |        0.019  |          1.15 |        0.0051 |          0.66 |       0.0144 |         1.03 |
| H10       | 0.0225574 |    1.81 |       0.0212443 |           155 |           8 | catboost      |   1     |        0.0226 |          1.81 |        0.0156 |          0.59 |       0.0158 |         0.54 |
| H15       | 0.0216951 |    2    |       0.026946  |           155 |           8 | catboost      |   1     |        0.0217 |          2    |        0.0147 |          0.46 |       0.0104 |         0.44 |
| H20       | 0.0190346 |    1.85 |       0.0223957 |           155 |           8 | catboost      |   0.975 |        0.019  |          1.85 |        0.0193 |          0.74 |       0.0174 |         0.69 |


🏆 **Meilleur horizon : H15** — sélectionné par score composite 55% IC + 30% IR + 15% Positive Split  |  H3=0.7608  H5=0.7665  H10=0.9720  H15=0.9790  H20=0.8734
### Horizon H3 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0174 | IR = 1.37 | Score composite = 0.981 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0174
- **Decile Spread** : 0.0168
- **Nb Features** : 155

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-24 | 2019-01-02 → 2019-06-26  |         149065 |        38302 |           0.0156246  |    0.0313326  |    0.0156246  |
|       2 | 2016-12-29 → 2019-06-26 | 2019-07-03 → 2019-12-24  |         188611 |        39336 |           0.0197781  |   -0.00158109 |    0.0197781  |
|       3 | 2016-12-29 → 2019-12-24 | 2020-01-02 → 2020-06-25  |         229215 |        40105 |           0.0413746  |    0.0346925  |    0.0413746  |
|       4 | 2016-12-29 → 2020-06-25 | 2020-07-02 → 2020-12-23  |         270628 |        41111 |           0.0221478  |    0.00745792 |    0.0221478  |
|       5 | 2016-12-29 → 2020-12-23 | 2020-12-31 → 2021-06-25  |         313071 |        41725 |           0.0181434  |   -0.00804445 |    0.0181434  |
|       6 | 2016-12-29 → 2021-06-25 | 2021-07-02 → 2021-12-23  |         356156 |        42975 |           0.012411   |   -0.0123246  |    0.012411   |
|       7 | 2016-12-29 → 2021-12-23 | 2021-12-31 → 2022-06-27  |         400515 |        44291 |          -0.00834967 |   -0.014655   |   -0.00834967 |
|       8 | 2016-12-29 → 2022-06-27 | 2022-07-05 → 2022-12-23  |         446238 |        46508 |           0.0180785  |    0.00940748 |    0.0180785  |

- IC Moyen = 0.0174  |  IC Std = 0.0127  |  IC Min = -0.0083  |  IC Max = 0.0414

### Horizon H5 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0190 | IR = 1.15 | Score composite = 0.981 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0190
- **Decile Spread** : 0.0231
- **Nb Features** : 155

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-20 | 2019-01-02 → 2019-06-24  |         148443 |        37670 |           0.0315525  |   0.00259729  |    0.0315525  |
|       2 | 2016-12-29 → 2019-06-24 | 2019-07-03 → 2019-12-20  |         187979 |        38682 |           0.0337216  |   0.0147169   |    0.0337216  |
|       3 | 2016-12-29 → 2019-12-20 | 2020-01-02 → 2020-06-23  |         228561 |        39439 |           0.0467568  |   0.00644921  |    0.0467568  |
|       4 | 2016-12-29 → 2020-06-23 | 2020-07-02 → 2020-12-21  |         269962 |        40431 |           0.0105324  |  -0.000675335 |    0.0105324  |
|       5 | 2016-12-29 → 2020-12-21 | 2020-12-31 → 2021-06-23  |         312391 |        41033 |           0.00631624 |   0.0182316   |    0.00631624 |
|       6 | 2016-12-29 → 2021-06-23 | 2021-07-02 → 2021-12-21  |         355464 |        42259 |           0.0144481  |   0.00732828  |    0.0144481  |
|       7 | 2016-12-29 → 2021-12-21 | 2021-12-31 → 2022-06-23  |         399799 |        43543 |          -0.00887379 |  -0.000152182 |   -0.00887379 |
|       8 | 2016-12-29 → 2022-06-23 | 2022-07-05 → 2022-12-21  |         445490 |        45736 |           0.0173469  |  -0.00730285  |    0.0173469  |

- IC Moyen = 0.0190  |  IC Std = 0.0165  |  IC Min = -0.0089  |  IC Max = 0.0468

### Horizon H10 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0226 | IR = 1.81 | Score composite = 1.000 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0226
- **Decile Spread** : 0.0212
- **Nb Features** : 155

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |            0.038166  |   0.0204486   |     0.038166  |
|       2 | 2016-12-29 → 2019-06-17 | 2019-07-03 → 2019-12-13  |         186399 |        37047 |            0.0214003 |   0.027692    |     0.0214003 |
|       3 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37774 |            0.0356921 |   0.0773857   |     0.0356921 |
|       4 | 2016-12-29 → 2020-06-16 | 2020-07-02 → 2020-12-14  |         268297 |        38731 |            0.0124845 |   0.0121163   |     0.0124845 |
|       5 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310691 |        39308 |            0.0062073 |  -0.00674471  |     0.0062073 |
|       6 | 2016-12-29 → 2021-06-16 | 2021-07-02 → 2021-12-14  |         353739 |        40469 |            0.0146103 |   0.00862725  |     0.0146103 |
|       7 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398009 |        41676 |            0.0124147 |  -0.000667507 |     0.0124147 |
|       8 | 2016-12-29 → 2022-06-15 | 2022-07-05 → 2022-12-14  |         443623 |        43806 |            0.0394842 |  -0.0138492   |     0.0394842 |

- IC Moyen = 0.0226  |  IC Std = 0.0124  |  IC Min = 0.0062  |  IC Max = 0.0395

### Horizon H15 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0217 | IR = 2.00 | Score composite = 1.000 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0217
- **Decile Spread** : 0.0269
- **Nb Features** : 155

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |          0.030643    |    0.0147713  |   0.030643    |
|       2 | 2016-12-29 → 2019-06-17 | 2019-07-03 → 2019-12-13  |         186399 |        37047 |          0.0166646   |    0.0298763  |   0.0166646   |
|       3 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37774 |          0.0274288   |    0.0837961  |   0.0274288   |
|       4 | 2016-12-29 → 2020-06-16 | 2020-07-02 → 2020-12-14  |         268297 |        38731 |          0.0203126   |    0.0169083  |   0.0203126   |
|       5 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310691 |        39308 |          0.000509771 |    0.00782242 |   0.000509771 |
|       6 | 2016-12-29 → 2021-06-16 | 2021-07-02 → 2021-12-14  |         353739 |        40469 |          0.019029    |   -0.00295549 |   0.019029    |
|       7 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398009 |        41676 |          0.0188872   |    0.00191781 |   0.0188872   |
|       8 | 2016-12-29 → 2022-06-15 | 2022-07-05 → 2022-12-14  |         443623 |        43806 |          0.0400857   |   -0.0348402  |   0.0400857   |

- IC Moyen = 0.0217  |  IC Std = 0.0109  |  IC Min = 0.0005  |  IC Max = 0.0401

### Horizon H20 — 🏆 catboost

- 🏆 **Champion : catboost** | IC = 0.0190 | IR = 1.85 | Score composite = 0.975 | Métrique : composite_55ic_30ir_15pos

- **IC Rank** : 0.0190
- **Decile Spread** : 0.0224
- **Nb Features** : 155

#### 📅 Détail par split — 🏆 catboost

|   Split | Train (début→fin)       | Validation (début→fin)   |   Lignes Train |   Lignes Val |   IC Rank (catboost) |   IC LightGBM |   IC CatBoost |
|--------:|:------------------------|:-------------------------|---------------:|-------------:|---------------------:|--------------:|--------------:|
|       1 | 2016-12-29 → 2018-12-13 | 2019-01-02 → 2019-06-17  |         146888 |        36090 |          0.0266535   |   0.0494667   |   0.0266535   |
|       2 | 2016-12-29 → 2019-06-17 | 2019-07-03 → 2019-12-13  |         186399 |        37047 |          0.0150813   |   0.0152633   |   0.0150813   |
|       3 | 2016-12-29 → 2019-12-13 | 2020-01-02 → 2020-06-16  |         226926 |        37774 |          0.0200905   |   0.0742635   |   0.0200905   |
|       4 | 2016-12-29 → 2020-06-16 | 2020-07-02 → 2020-12-14  |         268297 |        38731 |          0.0163442   |  -0.000233696 |   0.0163442   |
|       5 | 2016-12-29 → 2020-12-14 | 2020-12-31 → 2021-06-16  |         310691 |        39308 |         -0.000342599 |   0.00903671  |  -0.000342599 |
|       6 | 2016-12-29 → 2021-06-16 | 2021-07-02 → 2021-12-14  |         353739 |        40469 |          0.0145476   |   0.00439369  |   0.0145476   |
|       7 | 2016-12-29 → 2021-12-14 | 2021-12-31 → 2022-06-15  |         398009 |        41676 |          0.0219358   |   0.0071613   |   0.0219358   |
|       8 | 2016-12-29 → 2022-06-15 | 2022-07-05 → 2022-12-14  |         443623 |        43806 |          0.0379668   |  -0.00531965  |   0.0379668   |

- IC Moyen = 0.0190  |  IC Std = 0.0103  |  IC Min = -0.0003  |  IC Max = 0.0380


## 🧪 Backtest Stratégies — Global Rank (H15 + H5)

| Variante | Score relatif |
|----------|---------------|
| V1 — H15 seul | 🏆 référence |
| V2 — H15 + H5 rising | -8.4% |
| V3 — H15 + H5 < 0.35 | -36.5% |
| V4 — H15 + top 3 horizons ↑ (H15,H10,H20) | -25.1% |

> Le score relatif indique l'écart de Sharpe par rapport à la meilleure variante. Les Sharpes absolus ne sont pas interprétables en PnL réel (simulation en unités de rang). Frais 0.25% A/R inclus. V1 = H15 seul, V2 = H15 + H5 rising, V3 = H15 + H5 < 0.35 (contrarian). V4 = H15 + top 3 horizons ↑ (H15,H10,H20).

---

## 🔵 Per-Symbol / Per-Sector — Métriques d'entraînement

### 🏆 Sélection du champion

⚠️ **0 symboles en fallback** sur 1 :

| Mode | Nb symboles |
|---|---|

### 📊 Champions par modèle

| model_name   |   nb_symbols |
|:-------------|-------------:|
| global_model |            1 |

## 📊 Métriques F1 par split

_Aucune donnée._

## 📊 Distribution true / pred par split

_Aucune donnée._

## 📈 Distribution F1 macro — Walk-Forward

_Aucune donnée._

## 🏆 Top 10 meilleurs `f1_macro` (WF)

_Aucune donnée._

## 🥉 Top 10 plus mauvais `f1_macro` (WF)

_Aucune donnée._

## ⚪ `f1_short = 0` (WF)

_Aucune donnée._

## 📊 Métriques Régression par split

_Aucune métrique de régression disponible._

## 🏆 Top 10 meilleurs `directional_accuracy` (WF)

_Aucune donnée._

## 🥉 Top 10 plus mauvais `directional_accuracy` (WF)

_Aucune donnée._
