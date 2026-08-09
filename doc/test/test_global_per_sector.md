# 🧪 Comparaison des Tests — Global & Per-Sector

> Fichier de suivi et comparaison des batches (B0, B1, B2, …).
> Les tableaux comparatifs sont mis à jour au fur et à mesure.
> **Nouveauté** : `--global-champion` activé — champion automatique CatBoost vs LightGBM par horizon.

---

## 📋 Résumé des batches

| Batch | ID | Commentaire | Global Champion | Per-Sector Champions | IC Rank Global | IC IR |
|:------|:---|:------------|:----------------|:---------------------|---------------:|------:|
| **B0** | `model-factory-20260809091632-a574c7` | Baseline | catboost (5/5 horizons) | lightgbm 6 / catboost 5 | 0.0186 | 1.02 |

---

# PARTIE 1 — 🌐 Global Model

## 1.1 Comparatif Global — Tous Horizons

| Test | Horizon | IC Mean | IC IR | Decile Spread | Nb Features | 🏆 Champion | Score Composite |
|:-----|:--------|--------:|------:|--------------:|------------:|:-----------|:---------------:|
| B0   | H3      | 0.0103  | 1.25  | 0.0086        | 143         | catboost   | 1.000           |
| B0   | H5      | 0.0191  | 1.27  | 0.0184        | 143         | catboost   | 0.975           |
| B0   | H10     | 0.0230  | 1.20  | 0.0234        | 143         | catboost   | 0.975           |
| B0   | H15     | 0.0185  | 0.99  | 0.0275        | 143         | catboost   | 0.950           |
| B0   | H20     | 0.0220  | 0.95  | 0.0297        | 143         | catboost   | 0.950           |

> 🏆 **Meilleur horizon B0 : H10**

## 1.2 Champion Global — IC/IR CatBoost vs LightGBM

| Test | Horizon | IC catboost | IR catboost | IC lightgbm | IR lightgbm | 🏆 Vainqueur |
|:-----|:--------|------------:|------------:|------------:|------------:|:-----------|
| B0   | H3      | 0.0103      | 1.25        | 0.0086      | 0.55        | catboost   |
| B0   | H5      | 0.0191      | 1.27        | 0.0113      | 0.82        | catboost   |
| B0   | H10     | 0.0230      | 1.20        | 0.0041      | 0.18        | catboost   |
| B0   | H15     | 0.0185      | 0.99        | 0.0139      | 0.37        | catboost   |
| B0   | H20     | 0.0220      | 0.95        | 0.0090      | 0.25        | catboost   |

## 1.3 Détail IC par split — Champion (Global)

| Test | Horizon | Split 1 | Split 2 | Split 3 | Split 4 | Split 5 | Split 6 | IC Std | IC Min | IC Max |
|:-----|:--------|--------:|--------:|--------:|--------:|--------:|--------:|-------:|-------:|-------:|
| B0   | H3      | 0.0056  | 0.0230  | 0.0199  | 0.0008  | 0.0082  | 0.0043  | 0.0082 | 0.0008 | 0.0230 |
| B0   | H5      | 0.0088  | 0.0439  | 0.0282  | -0.0041 | 0.0156  | 0.0224  | 0.0151 | -0.0041| 0.0439 |
| B0   | H10     | 0.0038  | 0.0513  | 0.0338  | -0.0057 | 0.0326  | 0.0221  | 0.0192 | -0.0057| 0.0513 |
| B0   | H15     | -0.0077 | 0.0284  | 0.0378  | -0.0030 | 0.0395  | 0.0158  | 0.0186 | -0.0077| 0.0395 |
| B0   | H20     | -0.0038 | 0.0318  | 0.0582  | -0.0011 | 0.0412  | 0.0061  | 0.0232 | -0.0038| 0.0582 |

## 1.4 Comparatif Backtest Stratégies — Global Rank

| Test | V1 — H20 seul | V2 — H20 + H5 rising | V3 — H20 + H5 < 0.35 |
|:-----|:--------------|:---------------------|:----------------------|
| B0   | 🏆 référence  | -9.3%                | -28.8%                |

---

# PARTIE 2 — 🔵 Per-Sector

## 2.1 Comparatif Métriques par Horizon (WF)

| Test | Horizon | F1 macro | F1 short | F1 long | Dir Acc |
|:-----|:--------|---------:|---------:|--------:|--------:|
| B0   | H3      | 0.331    | 0.490    | 0.504   | 0.5023  |
| B0   | H5      | 0.329    | 0.476    | 0.511   | 0.5005  |
| B0   | H10     | 0.329    | 0.477    | 0.510   | 0.5025  |
| B0   | H15     | 0.328    | 0.474    | 0.510   | 0.5004  |
| B0   | H20     | 0.327    | 0.474    | 0.506   | 0.4986  |

## 2.2 Champions Per-Sector par modèle

| Test | catboost | lightgbm |
|:-----|---------:|---------:|
| B0   | 5        | 6        |

## 2.3 Comparatif F1 par split (WF)

| Test | model_name | split | F1 macro | F1 short | F1 long |
|:-----|:-----------|:------|---------:|---------:|--------:|
| B0   | catboost   | val   | 0.331    | 0.505    | 0.486   |
| B0   | catboost   | test  | 0.328    | 0.523    | 0.461   |
| B0   | catboost   | wf    | 0.328    | 0.477    | 0.509   |
| B0   | lightgbm   | val   | 0.331    | 0.506    | 0.486   |
| B0   | lightgbm   | test  | 0.329    | 0.515    | 0.470   |
| B0   | lightgbm   | wf    | 0.329    | 0.480    | 0.507   |

## 2.4 Comparatif Distribution true/pred par split (WF)

| Test | model_name | split | true_short% | true_long% | pred_short% | pred_long% |
|:-----|:-----------|:------|------------:|-----------:|------------:|-----------:|
| B0   | catboost   | val   | 51.91       | 48.09      | 50.00       | 50.00      |
| B0   | catboost   | test  | 51.94       | 48.06      | 54.08       | 45.92      |
| B0   | catboost   | wf    | 51.57       | 48.43      | 45.23       | 54.77      |
| B0   | lightgbm   | val   | 51.91       | 48.09      | 50.00       | 50.00      |
| B0   | lightgbm   | test  | 51.94       | 48.06      | 52.39       | 47.61      |
| B0   | lightgbm   | wf    | 51.57       | 48.43      | 45.77       | 54.23      |

## 2.5 Comparatif Métriques Régression par split (WF)

| Test | model_name | split | avg_mse | avg_dir_acc |
|:-----|:-----------|:------|--------:|------------:|
| B0   | catboost   | val   | 1.0627  | 0.4963      |
| B0   | catboost   | test  | 1.0720  | 0.4968      |
| B0   | catboost   | wf    | 1.0347  | 0.5010      |
| B0   | lightgbm   | val   | 1.0749  | 0.4964      |
| B0   | lightgbm   | test  | 1.0924  | 0.4967      |
| B0   | lightgbm   | wf    | 1.0537  | 0.5007      |

## 2.6 Distribution F1 macro — Walk-Forward

| Test | Bucket      | Nb symboles |
|:-----|:------------|------------:|
| B0   | 0.20–0.29   | 1           |
| B0   | 0.30–0.39   | 11          |

## 2.7 Top 10 F1 macro (WF) — Meilleurs secteurs

| Test | Secteur           | F1 macro | F1 long | F1 short |
|:-----|:------------------|---------:|--------:|---------:|
| B0   | Consumer Staples  | 0.357    | 0.552   | 0.518    |
| B0   | Consumer Staples  | 0.351    | 0.545   | 0.508    |
| B0   | Consumer Staples  | 0.346    | 0.542   | 0.497    |
| B0   | Industrials       | 0.343    | 0.504   | 0.525    |
| B0   | Industrials       | 0.342    | 0.501   | 0.527    |
| B0   | Industrials       | 0.340    | 0.501   | 0.519    |
| B0   | Industrials       | 0.339    | 0.496   | 0.522    |
| B0   | Industrials       | 0.338    | 0.502   | 0.512    |
| B0   | Health Care       | 0.338    | 0.516   | 0.497    |
| B0   | Health Care       | 0.336    | 0.517   | 0.491    |

## 2.8 Top 10 F1 macro (WF) — Pires secteurs

| Test | Secteur                 | F1 macro | F1 long | F1 short |
|:-----|:------------------------|---------:|--------:|---------:|
| B0   | Energy                  | 0.297    | 0.450   | 0.440    |
| B0   | Energy                  | 0.298    | 0.428   | 0.466    |
| B0   | Energy                  | 0.302    | 0.442   | 0.466    |
| B0   | Energy                  | 0.317    | 0.484   | 0.466    |
| B0   | Communication Services  | 0.318    | 0.509   | 0.447    |
| B0   | Materials               | 0.319    | 0.480   | 0.476    |
| B0   | Materials               | 0.320    | 0.484   | 0.476    |
| B0   | Information Technology  | 0.321    | 0.506   | 0.458    |
| B0   | Communication Services  | 0.322    | 0.513   | 0.454    |
| B0   | Communication Services  | 0.324    | 0.513   | 0.459    |

## 2.9 Diagnostic par régime de marché — Walk-Forward

| Test | Split | Début OOS  | Fin OOS    | Régime            | F1 macro | F1 short | F1 long | SPY % | VIX moy | Nb symb. |
|:-----|:------|:-----------|:-----------|:------------------|---------:|---------:|--------:|------:|--------:|---------:|
| B0   | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.315    | 0.438    | 0.508   | 7.7   | 15.0    | 11       |
| B0   | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.337    | 0.486    | 0.524   | 19.1  | 25.7    | 11       |
| B0   | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.325    | 0.464    | 0.511   | 9.8   | 18.8    | 11       |
| B0   | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.336    | 0.464    | 0.545   | 0.1   | 24.9    | 11       |
| B0   | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.316    | 0.487    | 0.461   | 9.0   | 15.1    | 11       |
| B0   | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.335    | 0.505    | 0.501   | 5.6   | 17.4    | 11       |

---

## 📝 Notes & Observations

- **B0 (Baseline)** : Premier batch avec `--global-champion` activé. Catboost champion sur 5/5 horizons. LightGBM dominé (IC IR H10 = 0.18 vs catboost 1.20). LightGBM meilleur que Catboost seulement en per-sector (6/11 vs 5/11).
- IC Rank Global = 0.0186, IC IR = 1.02. Meilleur horizon = H10 (IC 0.0230, IR 1.20).
- Per-Sector : F1 macro stable ~0.33. Industrials domine le top 10 (5/10), Energy domine les pires.
- LightGBM per-sector montre un F1 short plus élevé que Catboost en WF (0.480 vs 0.477).
