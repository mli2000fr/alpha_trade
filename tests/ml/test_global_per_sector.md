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
| **F3**     | `model-factory-20260808110218-8907b3` | F1 + `--include-screener-scores` | 2026-08-08 | Catboost (400 symb., 6 splits WF, 166 feat., catboost 7/lightgbm 4) | 11 secteurs | 11 | ⚠️ 0.0176 |
| **F4**     | `model-factory-20260808130525-0a3695` | F1 + `--include-short-score` | 2026-08-08 | Catboost (400 symb., 6 splits WF, 144 feat., catboost 7/lightgbm 4) | 11 secteurs | 11 | 🏆 0.0197 |

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
| F3   | H3      | 0.0092  | 1.08  | 0.0082        | 166         | 6         |
| F3   | H5      | 0.0184  | 1.09  | 0.0187        | 166         | 6         |
| F3   | H10     | 0.0186  | 0.92  | 0.0250        | 166         | 6         |
| F3   | H15     | 0.0224  | 1.03  | 0.0264        | 166         | 6         |
| F3   | H20     | 0.0191  | 0.88  | 0.0239        | 166         | 6         |
| F4   | H3      | 0.0125  | 0.99  | 0.0104        | 144         | 6         |
| F4   | H5      | 0.0187  | 1.14  | 0.0191        | 144         | 6         |
| F4   | H10     | 0.0228  | 1.36  | 0.0246        | 144         | 6         |
| F4   | H15     | 0.0236  | 1.34  | 0.0313        | 144         | 6         |
| F4   | H20     | 0.0208  | 0.84  | 0.0319        | 144         | 6         |

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
| F3   | H3      | 0.0035  | 0.0228  | 0.0184  | -0.0008 | 0.0070  | 0.0043  | 0.0085 | -0.0008| 0.0228 |
| F3   | H5      | 0.0113  | 0.0497  | 0.0206  | -0.0057 | 0.0239  | 0.0107  | 0.0169 | -0.0057| 0.0497 |
| F3   | H10     | -0.0006 | 0.0372  | 0.0366  | -0.0161 | 0.0324  | 0.0224  | 0.0202 | -0.0161| 0.0372 |
| F3   | H15     | 0.0007  | 0.0379  | 0.0484  | -0.0111 | 0.0403  | 0.0185  | 0.0218 | -0.0111| 0.0484 |
| F3   | H20     | -0.0038 | 0.0218  | 0.0504  | -0.0056 | 0.0430  | 0.0088  | 0.0216 | -0.0056| 0.0504 |
| F4   | H3      | 0.0070  | 0.0315  | 0.0249  | -0.0070 | 0.0104  | 0.0080  | 0.0126 | -0.0070| 0.0315 |
| F4   | H5      | 0.0085  | 0.0483  | 0.0190  | -0.0056 | 0.0246  | 0.0174  | 0.0163 | -0.0056| 0.0483 |
| F4   | H10     | -0.0001 | 0.0407  | 0.0411  | 0.0039  | 0.0339  | 0.0172  | 0.0168 | -0.0001| 0.0411 |
| F4   | H15     | 0.0007  | 0.0350  | 0.0472  | 0.0045  | 0.0381  | 0.0159  | 0.0175 | 0.0007 | 0.0472 |
| F4   | H20     | -0.0121 | 0.0273  | 0.0554  | -0.0001 | 0.0478  | 0.0068  | 0.0248 | -0.0121| 0.0554 |

## 1.2 Comparatif Backtest Stratégies — Global Rank

| Test | V1 — H20 seul | V2 — H20 + H5 rising | V3 — H20 + H5 < 0.35 |
|:-----|:--------------|:---------------------|:----------------------|
| P0   | 🏆 référence  | -9.3%                | -28.8%                |
| F1   | 🏆 référence  | -9.3%                | -28.8%                |
| F2   | 🏆 référence  | -9.3%                | -28.8%                |
| F3   | 🏆 référence  | -9.3%                | -23.3% ⬆️             |
| F4   | 🏆 référence  | -4.4% ⬆️⬆️           | -34.5% ⬇️             |

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
| F3   | H3      | 0.330    | 0.488    | 0.503   | 0.5015  |
| F3   | H5      | 0.329    | 0.474    | 0.512   | 0.5007  |
| F3   | H10     | 0.329    | 0.475    | 0.512   | 0.5026  |
| F3   | H15     | 0.329    | 0.473    | 0.513   | 0.5021  |
| F3   | H20     | 0.328    | 0.476    | 0.510   | 0.5015  |
| F4   | H3      | 0.331    | 0.489    | 0.504   | 0.5016  |
| F4   | H5      | 0.329    | 0.474    | 0.513   | 0.5011  |
| F4   | H10     | 0.328    | 0.474    | 0.511   | 0.5014  |
| F4   | H15     | 0.329    | 0.474    | 0.512   | 0.5022  |
| F4   | H20     | 0.328    | 0.474    | 0.509   | 0.5011  |

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
| F3   | catboost   | val   | 0.332    | 0.508    | 0.489   |
| F3   | catboost   | test  | 0.330    | 0.521    | 0.470   |
| F3   | catboost   | wf    | 0.329    | 0.475    | 0.510   |
| F3   | lightgbm   | val   | 0.331    | 0.506    | 0.487   |
| F3   | lightgbm   | test  | 0.329    | 0.512    | 0.474   |
| F3   | lightgbm   | wf    | 0.330    | 0.479    | 0.510   |
| F4   | catboost   | val   | 0.332    | 0.508    | 0.489   |
| F4   | catboost   | test  | 0.331    | 0.524    | 0.468   |
| F4   | catboost   | wf    | 0.328    | 0.475    | 0.510   |
| F4   | lightgbm   | val   | 0.331    | 0.507    | 0.487   |
| F4   | lightgbm   | test  | 0.329    | 0.512    | 0.475   |
| F4   | lightgbm   | wf    | 0.330    | 0.479    | 0.510   |

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
| F3   | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| F3   | catboost   | test  | 51.93       | 48.08      | 53.10       | 46.90      |
| F3   | catboost   | wf    | 51.41       | 48.59      | 45.18       | 54.82      |
| F3   | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| F3   | lightgbm   | test  | 51.93       | 48.08      | 51.73       | 48.27      |
| F3   | lightgbm   | wf    | 51.41       | 48.59      | 45.59       | 54.41      |
| F4   | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| F4   | catboost   | test  | 51.93       | 48.08      | 53.67       | 46.33      |
| F4   | catboost   | wf    | 51.41       | 48.59      | 45.17       | 54.83      |
| F4   | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| F4   | lightgbm   | test  | 51.93       | 48.08      | 51.63       | 48.37      |
| F4   | lightgbm   | wf    | 51.41       | 48.59      | 45.61       | 54.39      |

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
| F3   | catboost   | val   | 1.0662  | 0.4989      |
| F3   | catboost   | test  | 1.0872  | 0.4983      |
| F3   | catboost   | wf    | 1.0440  | 0.5015      |
| F3   | lightgbm   | val   | 1.0796  | 0.4971      |
| F3   | lightgbm   | test  | 1.1087  | 0.4957      |
| F3   | lightgbm   | wf    | 1.0618  | 0.5018      |
| F4   | catboost   | val   | 1.0655  | 0.4989      |
| F4   | catboost   | test  | 1.0872  | 0.4993      |
| F4   | catboost   | wf    | 1.0437  | 0.5008      |
| F4   | lightgbm   | val   | 1.0808  | 0.4972      |
| F4   | lightgbm   | test  | 1.1091  | 0.4959      |
| F4   | lightgbm   | wf    | 1.0621  | 0.5022      |

## 2.5 Distribution F1 macro — Walk-Forward

| Test | Bucket      | Nb symboles |
|:-----|:------------|------------:|
| P0   | 0.20–0.29   | 1           |
| P0   | 0.30–0.39   | 11          |
| F1   | 0.20–0.29   | 1           |
| F1   | 0.30–0.39   | 11          |
| F2   | 0.20–0.29   | 1           |
| F2   | 0.30–0.39   | 11          |
| F3   | 0.20–0.29   | 1           |
| F3   | 0.30–0.39   | 11          |
| F4   | 0.20–0.29   | 1           |
| F4   | 0.30–0.39   | 11          |

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
| F3   | Consumer Staples       | 0.366    | 0.561   | 0.537    |
| F3   | Consumer Staples       | 0.358    | 0.554   | 0.520    |
| F3   | Consumer Staples       | 0.350    | 0.534   | 0.516    |
| F3   | Health Care            | 0.342    | 0.531   | 0.496    |
| F3   | Health Care            | 0.341    | 0.531   | 0.490    |
| F3   | Consumer Staples       | 0.340    | 0.537   | 0.482    |
| F3   | Industrials            | 0.338    | 0.509   | 0.506    |
| F3   | Health Care            | 0.338    | 0.532   | 0.482    |
| F3   | Health Care            | 0.337    | 0.526   | 0.485    |
| F3   | Industrials            | 0.336    | 0.509   | 0.500    |
| F4   | Consumer Staples       | 0.366    | 0.561   | 0.537    |
| F4   | Consumer Staples       | 0.358    | 0.554   | 0.520    |
| F4   | Consumer Staples       | 0.350    | 0.534   | 0.516    |
| F4   | Health Care            | 0.342    | 0.537   | 0.488    |
| F4   | Health Care            | 0.340    | 0.526   | 0.494    |
| F4   | Consumer Staples       | 0.340    | 0.537   | 0.482    |
| F4   | Health Care            | 0.339    | 0.526   | 0.492    |
| F4   | Health Care            | 0.336    | 0.530   | 0.478    |
| F4   | Industrials            | 0.336    | 0.510   | 0.498    |
| F4   | Industrials            | 0.336    | 0.501   | 0.507    |

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
| F3   | Energy                  | 0.296    | 0.444   | 0.444    |
| F3   | Energy                  | 0.300    | 0.446   | 0.453    |
| F3   | Energy                  | 0.307    | 0.441   | 0.479    |
| F3   | Energy                  | 0.315    | 0.469   | 0.476    |
| F3   | Materials               | 0.319    | 0.490   | 0.468    |
| F3   | Utilities               | 0.319    | 0.550   | 0.407    |
| F3   | Communication Services  | 0.321    | 0.512   | 0.450    |
| F3   | Materials               | 0.321    | 0.470   | 0.495    |
| F3   | Materials               | 0.322    | 0.477   | 0.489    |
| F3   | Information Technology  | 0.323    | 0.508   | 0.460    |
| F4   | Energy                  | 0.296    | 0.444   | 0.444    |
| F4   | Energy                  | 0.300    | 0.446   | 0.453    |
| F4   | Energy                  | 0.307    | 0.441   | 0.479    |
| F4   | Utilities               | 0.315    | 0.575   | 0.369    |
| F4   | Energy                  | 0.315    | 0.469   | 0.476    |
| F4   | Real Estate             | 0.315    | 0.498   | 0.448    |
| F4   | Utilities               | 0.316    | 0.551   | 0.397    |
| F4   | Utilities               | 0.317    | 0.562   | 0.389    |
| F4   | Utilities               | 0.317    | 0.583   | 0.369    |
| F4   | Information Technology  | 0.319    | 0.509   | 0.449    |

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
| F3   | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.321    | 0.439    | 0.526   | 7.7   | 15.0    | 11       |
| F3   | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.331    | 0.450    | 0.544   | 19.1  | 25.7    | 11       |
| F3   | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.324    | 0.459    | 0.512   | 9.8   | 18.8    | 11       |
| F3   | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.342    | 0.504    | 0.523   | 0.1   | 24.9    | 11       |
| F3   | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.321    | 0.492    | 0.469   | 9.0   | 15.1    | 11       |
| F3   | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.327    | 0.502    | 0.479   | 5.6   | 17.4    | 11       |
| F4   | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.320    | 0.439    | 0.523   | 7.7   | 15.0    | 11       |
| F4   | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.330    | 0.439    | 0.551   | 19.1  | 25.7    | 11       |
| F4   | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.325    | 0.459    | 0.515   | 9.8   | 18.8    | 11       |
| F4   | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.338    | 0.500    | 0.515   | 0.1   | 24.9    | 11       |
| F4   | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.317    | 0.491    | 0.460   | 9.0   | 15.1    | 11       |
| F4   | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.327    | 0.502    | 0.480   | 5.6   | 17.4    | 11       |

---

## 📝 Notes & Observations

- **P0 (F0)** : Baseline. Batch `93d159`. Catboost champion (7/11), LightGBM (4/11). IC Rank Global = 0.0186, IC IR = 1.02.
- **F1** : F0 + `--target-excess-vs-spy`. Batch `6509b5`. Global Model inchangé (déterministe). Catboost 6/11, LightGBM 5/11.
- **F2** : F1 + `--include-sentiment`. Batch `b8325d`. Global Model inchangé. Catboost 8/11, LightGBM 3/11.
- **F3** : F1 + `--include-screener-scores`. Batch `8907b3`. ⚠️ 166 feat. IC Rank 0.0176 (−5.4%). Catboost 7/11.
- **F4** : F1 + `--include-short-score`. Batch `0a3695`. 🏆 **MEILLEUR Global Model** — IC Rank 0.0197 (+5.9% vs P0), IC IR 1.07 (+4.9%), Decile Spread H15=0.0313 (+14%), H20=0.0319 (+7%). Catboost 7/11, LightGBM 4/11.
- **Impact `--target-excess-vs-spy` (F1 vs P0)** : Améliore F1 long, Dir Acc, top F1 macro. Dégrade MSE.
- **Impact `--include-sentiment` (F2 vs F1)** : Catboost +2 secteurs. Léger recul directionnel. Utilities domine les pires secteurs.
- **Impact `--include-screener-scores` (F3 vs F1)** : ⚠️ DÉGRADE le Global Model. Seul point positif : V3 backtest −23.3%.
- **Impact `--include-short-score` (F4 vs F1)** : 🏆 **AMÉLIORE le Global Model** — IC Rank 0.0197 vs 0.0186, IC IR H10=1.36 vs 1.20, IC IR H15=1.34 vs 0.99. Backtest V2 passe de −9.3% à −4.4%. Per-Sector comparable à F1 (top F1 macro 0.366 identique). Utilities et Real Estate explosent dans les pires secteurs (short score pénalise). **F4 est le meilleur batch Global à ce stade.**
- Global Model : déterministe P0/F1/F2 (143 feat.), F3 (166 feat.), F4 (144 feat. avec `--include-short-score`).
- Déciles spreads H20 : F4=0.0319 (max), F1=0.0297, F3=0.0239 (min).
- Backtest V2 (H20 + H5 rising) : F4=−4.4% (meilleur), F1=−9.3%, F3=−9.3%.
