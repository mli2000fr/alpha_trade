# 🧪 Comparaison des Tests — Global & Per-Sector

> Fichier de suivi et comparaison des différents batches (P0/F0, F1, F2, …).
> Chaque batch documente ses résultats en deux parties : **Global Model** et **Per-Sector**.
> Les tableaux comparatifs sont mis à jour au fur et à mesure.

---

## 📋 Résumé des batches

| Batch | ID | Commentaire | Date | Global Model | Per-Sector | Symboles | IC Rank Global |
|:------|:---|:------------|:-----|:-------------|:-----------|:---------|---------------:|
| **P0 (F0)** | `model-factory-20260808055913-93d159` | F0 Baseline | 2026-08-08 | Catboost (400 symb., 6 splits WF, catboost 7/lightgbm 4) | 11 secteurs | 11 | 0.0186 |
| **F1**     | `model-factory-20260807213057-6509b5` | F0 + `--target-excess-vs-spy` | 2026-08-07 | Catboost (400 symb., 6 splits WF, catboost 6/lightgbm 5) | 11 secteurs | 11 | 0.0186 |
| **F2**     | `model-factory-20260808075734-b8325d` | F1 + `--include-sentiment` | 2026-08-08 | Catboost (400 symb., 6 splits WF, catboost 8/lightgbm 3) | 11 secteurs | 11 | 0.0186 |

---

# PARTIE 1 — 🌐 Global Model

## 1.1 Comparatif Global — Tous Horizons

| Test | Horizon | IC Mean | IC IR | Decile Spread | Nb Features | Nb Splits |
|:-----|:--------|--------:|------:|--------------:|------------:|----------:|
| P0   | H3      | 0.0103  | 1.25  | 0.0086        | 143         | 6         |
| P0   | H5      | 0.0191  | 1.27  | 0.0184        | 143         | 6         |
| P0   | H10     | 0.0230  | 1.20  | 0.0234        | 143         | 6         |
| P0   | H15     | 0.0185  | 0.99  | 0.0275        | 143         | 6         |
| P0   | H20     | 0.0220  | 0.95  | 0.0297        | 143         | 6         |
| F1   | H3      | 0.0103  | 1.25  | 0.0086        | 143         | 6         |
| F1   | H5      | 0.0191  | 1.27  | 0.0184        | 143         | 6         |
| F1   | H10     | 0.0230  | 1.20  | 0.0234        | 143         | 6         |
| F1   | H15     | 0.0185  | 0.99  | 0.0275        | 143         | 6         |
| F1   | H20     | 0.0220  | 0.95  | 0.0297        | 143         | 6         |
| F2   | H3      | 0.0103  | 1.25  | 0.0086        | 143         | 6         |
| F2   | H5      | 0.0191  | 1.27  | 0.0184        | 143         | 6         |
| F2   | H10     | 0.0230  | 1.20  | 0.0234        | 143         | 6         |
| F2   | H15     | 0.0185  | 0.99  | 0.0275        | 143         | 6         |
| F2   | H20     | 0.0220  | 0.95  | 0.0297        | 143         | 6         |

### 1.1bis Détail IC par split (Global)

| Test | Horizon | Split 1 | Split 2 | Split 3 | Split 4 | Split 5 | Split 6 | IC Std | IC Min | IC Max |
|:-----|:--------|--------:|--------:|--------:|--------:|--------:|--------:|-------:|-------:|-------:|
| P0   | H3      | 0.0056  | 0.0230  | 0.0199  | 0.0008  | 0.0082  | 0.0043  | 0.0082 | 0.0008 | 0.0230 |
| P0   | H5      | 0.0088  | 0.0439  | 0.0282  | -0.0041 | 0.0156  | 0.0224  | 0.0151 | -0.0041| 0.0439 |
| P0   | H10     | 0.0038  | 0.0513  | 0.0338  | -0.0057 | 0.0326  | 0.0221  | 0.0192 | -0.0057| 0.0513 |
| P0   | H15     | -0.0077 | 0.0284  | 0.0378  | -0.0030 | 0.0395  | 0.0158  | 0.0186 | -0.0077| 0.0395 |
| P0   | H20     | -0.0038 | 0.0318  | 0.0582  | -0.0011 | 0.0412  | 0.0061  | 0.0232 | -0.0038| 0.0582 |
| F1   | H3      | 0.0056  | 0.0230  | 0.0199  | 0.0008  | 0.0082  | 0.0043  | 0.0082 | 0.0008 | 0.0230 |
| F1   | H5      | 0.0088  | 0.0439  | 0.0282  | -0.0041 | 0.0156  | 0.0224  | 0.0151 | -0.0041| 0.0439 |
| F1   | H10     | 0.0038  | 0.0513  | 0.0338  | -0.0057 | 0.0326  | 0.0221  | 0.0192 | -0.0057| 0.0513 |
| F1   | H15     | -0.0077 | 0.0284  | 0.0378  | -0.0030 | 0.0395  | 0.0158  | 0.0186 | -0.0077| 0.0395 |
| F1   | H20     | -0.0038 | 0.0318  | 0.0582  | -0.0011 | 0.0412  | 0.0061  | 0.0232 | -0.0038| 0.0582 |
| F2   | H3      | 0.0056  | 0.0230  | 0.0199  | 0.0008  | 0.0082  | 0.0043  | 0.0082 | 0.0008 | 0.0230 |
| F2   | H5      | 0.0088  | 0.0439  | 0.0282  | -0.0041 | 0.0156  | 0.0224  | 0.0151 | -0.0041| 0.0439 |
| F2   | H10     | 0.0038  | 0.0513  | 0.0338  | -0.0057 | 0.0326  | 0.0221  | 0.0192 | -0.0057| 0.0513 |
| F2   | H15     | -0.0077 | 0.0284  | 0.0378  | -0.0030 | 0.0395  | 0.0158  | 0.0186 | -0.0077| 0.0395 |
| F2   | H20     | -0.0038 | 0.0318  | 0.0582  | -0.0011 | 0.0412  | 0.0061  | 0.0232 | -0.0038| 0.0582 |

## 1.2 Comparatif Backtest Stratégies — Global Rank

| Test | V1 — H20 seul | V2 — H20 + H5 rising | V3 — H20 + H5 < 0.35 |
|:-----|:--------------|:---------------------|:----------------------|
| P0   | 🏆 référence  | -9.3%                | -28.8%                |
| F1   | 🏆 référence  | -9.3%                | -28.8%                |
| F2   | 🏆 référence  | -9.3%                | -28.8%                |

---

# PARTIE 2 — 🔵 Per-Sector

## 2.1 Comparatif Métriques par Horizon (WF)

| Test | Horizon | F1 macro | F1 short | F1 long | Dir Acc |
|:-----|:--------|---------:|---------:|--------:|--------:|
| P0   | H3      | 0.331    | 0.490    | 0.504   | 0.5023  |
| P0   | H5      | 0.329    | 0.476    | 0.511   | 0.5005  |
| P0   | H10     | 0.329    | 0.477    | 0.510   | 0.5025  |
| P0   | H15     | 0.328    | 0.474    | 0.510   | 0.5004  |
| P0   | H20     | 0.327    | 0.474    | 0.506   | 0.4986  |
| F1   | H3      | 0.331    | 0.491    | 0.503   | 0.5024  |
| F1   | H5      | 0.329    | 0.474    | 0.514   | 0.5015  |
| F1   | H10     | 0.329    | 0.475    | 0.512   | 0.5023  |
| F1   | H15     | 0.330    | 0.476    | 0.513   | 0.5039  |
| F1   | H20     | 0.329    | 0.475    | 0.511   | 0.5019  |
| F2   | H3      | 0.330    | 0.489    | 0.503   | 0.5019  |
| F2   | H5      | 0.329    | 0.475    | 0.512   | 0.5008  |
| F2   | H10     | 0.329    | 0.474    | 0.512   | 0.5019  |
| F2   | H15     | 0.329    | 0.475    | 0.512   | 0.5022  |
| F2   | H20     | 0.327    | 0.473    | 0.509   | 0.4998  |

## 2.2 Comparatif F1 par split (WF)

| Test | model_name | split | F1 macro | F1 short | F1 long |
|:-----|:-----------|:------|---------:|---------:|--------:|
| P0   | catboost   | val   | 0.331    | 0.505    | 0.486   |
| P0   | catboost   | test  | 0.328    | 0.523    | 0.461   |
| P0   | catboost   | wf    | 0.328    | 0.477    | 0.509   |
| P0   | lightgbm   | val   | 0.331    | 0.506    | 0.486   |
| P0   | lightgbm   | test  | 0.329    | 0.515    | 0.470   |
| P0   | lightgbm   | wf    | 0.329    | 0.480    | 0.507   |
| F1   | catboost   | val   | 0.332    | 0.508    | 0.489   |
| F1   | catboost   | test  | 0.330    | 0.522    | 0.469   |
| F1   | catboost   | wf    | 0.329    | 0.477    | 0.511   |
| F1   | lightgbm   | val   | 0.331    | 0.507    | 0.487   |
| F1   | lightgbm   | test  | 0.329    | 0.512    | 0.475   |
| F1   | lightgbm   | wf    | 0.330    | 0.479    | 0.510   |
| F2   | catboost   | val   | 0.332    | 0.508    | 0.489   |
| F2   | catboost   | test  | 0.331    | 0.523    | 0.470   |
| F2   | catboost   | wf    | 0.328    | 0.475    | 0.510   |
| F2   | lightgbm   | val   | 0.331    | 0.506    | 0.487   |
| F2   | lightgbm   | test  | 0.329    | 0.512    | 0.475   |
| F2   | lightgbm   | wf    | 0.329    | 0.479    | 0.509   |

## 2.3 Comparatif Distribution true/pred par split (WF)

| Test | model_name | split | true_short% | true_long% | pred_short% | pred_long% |
|:-----|:-----------|:------|------------:|-----------:|------------:|-----------:|
| P0   | catboost   | val   | 51.91       | 48.09      | 50.00       | 50.00      |
| P0   | catboost   | test  | 51.94       | 48.06      | 54.08       | 45.92      |
| P0   | catboost   | wf    | 51.57       | 48.43      | 45.23       | 54.77      |
| P0   | lightgbm   | val   | 51.91       | 48.09      | 50.00       | 50.00      |
| P0   | lightgbm   | test  | 51.94       | 48.06      | 52.39       | 47.61      |
| P0   | lightgbm   | wf    | 51.57       | 48.43      | 45.77       | 54.23      |
| F1   | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| F1   | catboost   | test  | 51.93       | 48.08      | 53.22       | 46.78      |
| F1   | catboost   | wf    | 51.41       | 48.59      | 45.19       | 54.81      |
| F1   | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| F1   | lightgbm   | test  | 51.93       | 48.08      | 51.70       | 48.30      |
| F1   | lightgbm   | wf    | 51.41       | 48.59      | 45.63       | 54.37      |
| F2   | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| F2   | catboost   | test  | 51.93       | 48.08      | 53.41       | 46.59      |
| F2   | catboost   | wf    | 51.41       | 48.59      | 45.21       | 54.80      |
| F2   | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| F2   | lightgbm   | test  | 51.93       | 48.08      | 51.69       | 48.31      |
| F2   | lightgbm   | wf    | 51.41       | 48.59      | 45.70       | 54.30      |

## 2.4 Comparatif Métriques Régression par split (WF)

| Test | model_name | split | avg_mse | avg_dir_acc |
|:-----|:-----------|:------|--------:|------------:|
| P0   | catboost   | val   | 1.0627  | 0.4963      |
| P0   | catboost   | test  | 1.0720  | 0.4968      |
| P0   | catboost   | wf    | 1.0347  | 0.5010      |
| P0   | lightgbm   | val   | 1.0749  | 0.4964      |
| P0   | lightgbm   | test  | 1.0924  | 0.4967      |
| P0   | lightgbm   | wf    | 1.0537  | 0.5007      |
| F1   | catboost   | val   | 1.0662  | 0.4987      |
| F1   | catboost   | test  | 1.0886  | 0.4983      |
| F1   | catboost   | wf    | 1.0432  | 0.5026      |
| F1   | lightgbm   | val   | 1.0798  | 0.4972      |
| F1   | lightgbm   | test  | 1.1086  | 0.4959      |
| F1   | lightgbm   | wf    | 1.0621  | 0.5022      |
| F2   | catboost   | val   | 1.0655  | 0.4988      |
| F2   | catboost   | test  | 1.0873  | 0.4993      |
| F2   | catboost   | wf    | 1.0436  | 0.5011      |
| F2   | lightgbm   | val   | 1.0799  | 0.4968      |
| F2   | lightgbm   | test  | 1.1078  | 0.4959      |
| F2   | lightgbm   | wf    | 1.0620  | 0.5015      |

## 2.5 Distribution F1 macro — Walk-Forward

| Test | Bucket      | Nb symboles |
|:-----|:------------|------------:|
| P0   | 0.20–0.29   | 1           |
| P0   | 0.30–0.39   | 11          |
| F1   | 0.20–0.29   | 1           |
| F1   | 0.30–0.39   | 11          |
| F2   | 0.20–0.29   | 1           |
| F2   | 0.30–0.39   | 11          |

## 2.6 Top 10 F1 macro (WF) — Meilleurs secteurs

| Test | Secteur                | F1 macro | F1 long | F1 short |
|:-----|:-----------------------|---------:|--------:|---------:|
| P0   | Consumer Staples       | 0.348    | 0.549   | 0.495    |
| P0   | Consumer Staples       | 0.344    | 0.550   | 0.482    |
| P0   | Health Care            | 0.343    | 0.532   | 0.496    |
| P0   | Consumer Staples       | 0.341    | 0.551   | 0.471    |
| P0   | Health Care            | 0.339    | 0.523   | 0.496    |
| P0   | Real Estate            | 0.338    | 0.519   | 0.496    |
| P0   | Industrials            | 0.338    | 0.517   | 0.497    |
| P0   | Financials             | 0.338    | 0.507   | 0.506    |
| P0   | Financials             | 0.337    | 0.500   | 0.512    |
| P0   | Consumer Staples       | 0.336    | 0.527   | 0.482    |
| F1   | Consumer Staples       | 0.366    | 0.561   | 0.537    |
| F1   | Consumer Staples       | 0.358    | 0.554   | 0.520    |
| F1   | Consumer Staples       | 0.350    | 0.534   | 0.516    |
| F1   | Health Care            | 0.345    | 0.535   | 0.498    |
| F1   | Health Care            | 0.341    | 0.528   | 0.494    |
| F1   | Health Care            | 0.340    | 0.532   | 0.489    |
| F1   | Consumer Staples       | 0.340    | 0.537   | 0.482    |
| F1   | Financials             | 0.337    | 0.500   | 0.512    |
| F1   | Financials             | 0.336    | 0.528   | 0.480    |
| F1   | Industrials            | 0.336    | 0.507   | 0.501    |
| F2   | Consumer Staples       | 0.356    | 0.556   | 0.512    |
| F2   | Consumer Staples       | 0.353    | 0.558   | 0.501    |
| F2   | Consumer Staples       | 0.351    | 0.556   | 0.496    |
| F2   | Health Care            | 0.343    | 0.529   | 0.499    |
| F2   | Consumer Staples       | 0.341    | 0.559   | 0.463    |
| F2   | Health Care            | 0.340    | 0.522   | 0.499    |
| F2   | Health Care            | 0.338    | 0.525   | 0.489    |
| F2   | Industrials            | 0.337    | 0.508   | 0.503    |
| F2   | Industrials            | 0.337    | 0.514   | 0.496    |
| F2   | Industrials            | 0.336    | 0.502   | 0.506    |

## 2.7 Top 10 F1 macro (WF) — Pires secteurs

| Test | Secteur                 | F1 macro | F1 long | F1 short |
|:-----|:------------------------|---------:|--------:|---------:|
| P0   | Energy                  | 0.297    | 0.450   | 0.440    |
| P0   | Energy                  | 0.298    | 0.428   | 0.466    |
| P0   | Energy                  | 0.302    | 0.442   | 0.466    |
| P0   | Energy                  | 0.317    | 0.484   | 0.466    |
| P0   | Communication Services  | 0.318    | 0.509   | 0.447    |
| P0   | Materials               | 0.319    | 0.480   | 0.476    |
| P0   | Materials               | 0.320    | 0.484   | 0.476    |
| P0   | Information Technology  | 0.321    | 0.506   | 0.458    |
| P0   | Communication Services  | 0.322    | 0.513   | 0.454    |
| P0   | Communication Services  | 0.324    | 0.513   | 0.459    |
| F1   | Energy                  | 0.296    | 0.444   | 0.444    |
| F1   | Energy                  | 0.300    | 0.446   | 0.453    |
| F1   | Energy                  | 0.307    | 0.441   | 0.479    |
| F1   | Energy                  | 0.315    | 0.469   | 0.476    |
| F1   | Materials               | 0.318    | 0.464   | 0.491    |
| F1   | Information Technology  | 0.319    | 0.513   | 0.444    |
| F1   | Materials               | 0.320    | 0.484   | 0.476    |
| F1   | Communication Services  | 0.321    | 0.512   | 0.450    |
| F1   | Utilities               | 0.323    | 0.553   | 0.417    |
| F1   | Materials               | 0.324    | 0.477   | 0.494    |
| F2   | Energy                  | 0.298    | 0.443   | 0.450    |
| F2   | Energy                  | 0.299    | 0.450   | 0.449    |
| F2   | Energy                  | 0.311    | 0.441   | 0.492    |
| F2   | Utilities               | 0.314    | 0.538   | 0.405    |
| F2   | Energy                  | 0.314    | 0.478   | 0.465    |
| F2   | Utilities               | 0.317    | 0.555   | 0.397    |
| F2   | Utilities               | 0.319    | 0.529   | 0.426    |
| F2   | Utilities               | 0.321    | 0.554   | 0.409    |
| F2   | Materials               | 0.321    | 0.474   | 0.489    |
| F2   | Communication Services  | 0.321    | 0.512   | 0.452    |

## 2.8 Diagnostic par régime de marché — Walk-Forward

| Test | Split | Début OOS  | Fin OOS    | Régime            | F1 macro | F1 short | F1 long | SPY % | VIX moy | Nb symb. |
|:-----|:------|:-----------|:-----------|:------------------|---------:|---------:|--------:|------:|--------:|---------:|
| P0   | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.315    | 0.438    | 0.508   | 7.7   | 15.0    | 11       |
| P0   | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.337    | 0.486    | 0.524   | 19.1  | 25.7    | 11       |
| P0   | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.325    | 0.464    | 0.511   | 9.8   | 18.8    | 11       |
| P0   | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.336    | 0.464    | 0.545   | 0.1   | 24.9    | 11       |
| P0   | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.316    | 0.487    | 0.461   | 9.0   | 15.1    | 11       |
| P0   | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.335    | 0.505    | 0.501   | 5.6   | 17.4    | 11       |
| F1   | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.321    | 0.440    | 0.523   | 7.7   | 15.0    | 11       |
| F1   | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.331    | 0.446    | 0.547   | 19.1  | 25.7    | 11       |
| F1   | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.323    | 0.449    | 0.521   | 9.8   | 18.8    | 11       |
| F1   | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.341    | 0.501    | 0.522   | 0.1   | 24.9    | 11       |
| F1   | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.321    | 0.491    | 0.471   | 9.0   | 15.1    | 11       |
| F1   | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.330    | 0.507    | 0.483   | 5.6   | 17.4    | 11       |
| F2   | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.320    | 0.439    | 0.522   | 7.7   | 15.0    | 11       |
| F2   | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.332    | 0.450    | 0.544   | 19.1  | 25.7    | 11       |
| F2   | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.324    | 0.459    | 0.513   | 9.8   | 18.8    | 11       |
| F2   | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.334    | 0.483    | 0.519   | 0.1   | 24.9    | 11       |
| F2   | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.321    | 0.495    | 0.467   | 9.0   | 15.1    | 11       |
| F2   | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.328    | 0.504    | 0.481   | 5.6   | 17.4    | 11       |

---

## 📝 Notes & Observations

- **P0 (F0)** : Baseline. Batch `93d159`. Catboost champion (7/11), LightGBM (4/11). IC Rank Global = 0.0186, IC IR = 1.02.
- **F1** : F0 + `--target-excess-vs-spy`. Batch `6509b5`. Global Model inchangé (déterministe). Catboost 6/11, LightGBM 5/11.
- **F2** : F1 + `--include-sentiment`. Batch `b8325d`. Global Model inchangé. Catboost 8/11, LightGBM 3/11 (Catboost gagne +2 secteurs vs F1).
- **Impact `--target-excess-vs-spy` (F1 vs P0)** : Améliore F1 long (+0.003 à +0.005), Dir Acc (+0.001 à +0.003), top F1 macro (0.366 vs 0.348). Dégrade MSE.
- **Impact `--include-sentiment` (F2 vs F1)** : Catboost domine plus (8/11 vs 6/11). F1 long H5 passe de 0.514→0.512, Dir Acc H15 de 0.5039→0.5022 — léger recul directionnel. Utilities apparaît massivement dans les pires secteurs (4/10). Le sentiment ne semble pas améliorer les métriques brutes mais renforce Catboost comme champion.
- Global Model : les prédictions globales sont déterministes (identiques P0/F1/F2).
- Les déciles spreads augmentent avec l'horizon (H3=0.0086 → H20=0.0297).
- Le backtest V3 (H20 + H5 < 0.35 contrarian) détériore fortement le Sharpe (-28.8% vs V1).
