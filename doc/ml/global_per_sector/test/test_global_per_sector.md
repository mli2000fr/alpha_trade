# 🧪 Comparaison des Tests — Global & Per-Sector

> Fichier de suivi et comparaison des batches (B0, B1, B2, …).
> Les tableaux comparatifs sont mis à jour au fur et à mesure.
> **Nouveauté** : `--global-champion` activé — champion automatique CatBoost vs LightGBM par horizon.

---

## 📋 Résumé des batches

| Batch | ID | Commentaire | Global Champion | Per-Sector Champions | IC Rank Global | IC IR | Meilleur horizon |
|:------|:---|:------------|:----------------|:---------------------|---------------:|------:|:-----------------|
| **B0** | `model-factory-20260809091632-a574c7` | Baseline | catboost (5/5 horizons) | lightgbm 6 / catboost 5 | 0.0186 | 1.02 | H10 |
| **B1** | `model-factory-20260809104004-44d3a8` | B0 + `--include-sentiment` | catboost (5/5 horizons) | lightgbm 6 / catboost 5 | 0.0186 | 1.02 | H10 |
| **B2** | `model-factory-20260809115339-404c90` | B0 + `--include-screener-scores` | catboost (5/5 horizons, 166 feat.) | lightgbm 6 / catboost 5 | 0.0186 | ⚠️ 0.97 | H20 |
| **B3** | `model-factory-20260809132408-4d40c5` | B0 + `--include-short-score` | catboost (5/5 horizons, 144 feat.) | catboost 6 / lightgbm 5 | 🏆 0.0202 | 🏆 1.03 | H10 |
| **B4** | `model-factory-20260809153352-2b4647` | B3 + `--target-excess-vs-spy` | catboost (5/5 horizons, 144 feat.) | lightgbm 8 / catboost 3 | 🏆 0.0202 | 🏆 1.03 | H10 |
| **B5** | `model-factory-20260809173405-730267` | B4 + `--include-macro-vix` | catboost (5/5 horizons, 144 feat.) | lightgbm 8 / catboost 3 | 🏆 0.0202 | 🏆 1.03 | H10 |
| **B6** | `model-factory-20260809191125-23cc62` | B4 + `--include-macro-vxn` | catboost (5/5 horizons, 144 feat.) | lightgbm 8 / catboost 3 | 🏆 0.0202 | 🏆 1.03 | H10 |
| **B7** | `model-factory-20260809211556-6f94d8` | B4 + `--include-macro-vix3m` | catboost (5/5 horizons, 144 feat.) | lightgbm 8 / catboost 3 | 🏆 0.0202 | 🏆 1.03 | H10 |
| **B8** | `model-factory-20260809234022-4de46f` | B4 + `--include-macro-move` | catboost (5/5 horizons, 144 feat.) | lightgbm 8 / catboost 3 | 🏆 0.0202 | 🏆 1.03 | H10 |
| **B9** | `model-factory-20260810052226-5de365` | B4 + `--include-fundamentals` | ⚠️ lightgbm H3, catboost 4/5 (156 feat.) | catboost 6 / lightgbm 5 | ❌ 0.0157 | ❌ 0.98 | H10 |
| **B10** | `model-factory-20260810160939-927f00` | B4 + `--include-factors` (CAPM) | catboost 5/5 (145 feat.) | lightgbm 9 / catboost 2 | 0.0195 | 🏆 1.09 | H10 |
| **B11** | `model-factory-20260810175924-7bd4ac` | B4 + `--include-macro-regime` | catboost 5/5 (144 feat.) | lightgbm 7 / catboost 4 | 🏆 0.0202 | 🏆 1.03 | H10 |
| **B12** | `model-factory-20260810200031-9755c6` | B4 + score components (153 feat.) | catboost 5/5 (153 feat.) | lightgbm 10 / catboost 1 | ⚠️ 0.0188 | ⚠️ 0.92 | H15 |
| **B13** | `model-factory-20260810213112-95c7d0` | B4 + `--enable-cross-sectional` (177 feat.) | catboost 5/5 (159-177 feat.) | lightgbm 7 / catboost 4 | ❌ 0.0144 | ❌ 0.84 | H10 |
| **B14** | `model-factory-20260811073138-0a0b4f` | B4 + `--enable-global-stacking` | catboost 5/5 (144 feat.) | lightgbm 7 / catboost 4 | 0.0196 | 1.03 | H10 |
| **B15** | `model-factory-20260811095231-7b4179` | B4 + `--target-skip-vol-scaling` (T1) | catboost 5/5 (144 feat.) | catboost 7 / lightgbm 4 | 0.0196 | 1.03 | H10 |
| **B16** | `model-factory-20260811110707-5029e9` | B4 + `--target-intra-sector-rank` (T2) | catboost 5/5 (144 feat.) | lightgbm 8 / catboost 3 | 0.0196 | 1.03 | H10 |
| **B17** | `model-factory-20260811144842-bd6976` | B4 + `--target-ternary-intra-sector` (T3) | catboost 5/5 (144 feat.) | lightgbm 9 / catboost 2 | 0.0196 | 1.03 | H10 |
| **B18** | `model-factory-20260811165544-d4d6af` | B4 + from 2011 + 8 splits | catboost 5/5 (144 feat.) | catboost 7 / lightgbm 4 | ⚠️ 0.0165 | ❌ 0.66 | H5 |
| **B19** | `model-factory-20260811184205-100f0a` | B4 + from 2011 + 16 splits | catboost 5/5 (144 feat.) | catboost 6 / lightgbm 5 | ❌ 0.0157 | ❌ 0.68 | H5 |
| **B20** | `model-factory-20260811213821-1bce18` | **B4 + YetiRank** 🔥 | catboost 5/5 (144 feat.) | — | 🏆 **0.0238** | 1.03 | H15 |
| **B21** | `model-factory-20260812001008-1ce659` | B4 + QueryRMSE | ⚠️ catboost 4/5, lightgbm H15 | lightgbm 6 / catboost 5 | 0.0188 | 0.92 | H10 |
| **B22** | `model-factory-20260812001051-e2f0db` | B4 + QuerySoftMax | ⚠️ catboost 4/5, lightgbm H15 | lightgbm 6 / catboost 5 | 0.0185 | 0.89 | H5 |
| **B25** | `model-factory-20260811223551-ef2cd0` | **B10 + YetiRank** 🔥🔥 | catboost 5/5 (145 feat.) | lightgbm 6 / catboost 5 | 🏆 **0.0241** | **1.07** | H10 |
| **B26** | `model-factory-20260812064302-8843cf` | B10 + QueryRMSE | catboost 5/5 (145 feat.) | lightgbm 6 / catboost 5 | 0.0172 | 0.97 | H5 |
| **B27** | `model-factory-20260812064355-7faa02` | B10 + QuerySoftMax | catboost 5/5 (145 feat.) | lightgbm 6 / catboost 5 | 0.0161 | 0.95 | H5 |
| **B30** | `model-factory-20260812151652-9aaddb` | B20 + P1-3 raw rank target | ⚠️ lightgbm 3/5 (145 feat.) | lightgbm 6 / catboost 5 | ❌ 0.0153 | ❌ 0.49 | H10 |
| **B31** | `model-factory-20260812185524-904666` | B4 + fondamentaux + YetiRank | catboost 5/5 (144-156 feat.) | catboost 6 / lightgbm 5 | ❌ 0.0146 | ❌ 0.66 | H5 |
| **B32** | `model-factory-20260812185649-98d980` | B4 + score components + YetiRank | catboost 5/5 (153 feat.) | lightgbm 8 / catboost 3 | ⚠️ 0.0224 | 0.95 | H10 |
| **B33** | `model-factory-20260812185814-da184f` | B4 + cross-sectional + YetiRank | catboost 5/5 (159-177 feat.) | lightgbm 7 / catboost 4 | ❌ 0.0138 | ❌ 0.72 | H5 |
| **B34** | `model-factory-20260812190010-748dd9` | B4 + screener + YetiRank | catboost 5/5 (181-199 feat.) | lightgbm 6 / catboost 5 | ❌ 0.0151 | ❌ 0.78 | H10 |
| **B35** | `model-factory-20260812232931-792070` | B25 + symbols 196 | ⚠️ cb 3/5 + lgbm 2/5 (145 feat.) | lightgbm 7 / catboost 2 (9 sect.) | ❌ 0.0154 | ❌ 0.51 | H3 |
| **B36** | `model-factory-20260812235655-c993b3` | B20 + symbols 196 | ⚠️ cb 4/5 + lgbm 1/5 (144 feat.) | lightgbm 7 / catboost 2 (9 sect.) | ❌ 0.0148 | ❌ 0.45 | H3 |
| **B37** | `model-factory-20260813092928-9f906f` | B25 + symbols 393 (swing score) | catboost 5/5 (145 feat.) | catboost 7 / lightgbm 4 | ❌ 0.0123 | ❌ 0.89 | H3 |
| **B38** | `model-factory-20260813132105-a8aadc` | **B25 + 300 symboles (parmi les 400)** | catboost 5/5 (145 feat.) | lightgbm 6 / catboost 5 | ⚠️ **0.0229** | 🏆 **1.14** | H15 |
| **B39** | `model-factory-20260813222929-c15ad8` | B25 + XGBoost rank:ndcg (P3-3) | xgboost (candidat unique) | lightgbm 6 / catboost 5 | ❌ 0.0129 | ❌ 0.57 | H15 |
| **B40** | `model-factory-20260813230529-ca6dd8` | B4 + volume features (P3-5) | catboost (candidat unique) | lightgbm 6 / catboost 5 | ❌ 0.0178 | 1.13 | H10 |
| **B41** | `model-factory-20260813231851-bb2e76` | **B25 + volume features (P3-5)** 🔥🔥 | catboost (candidat unique) | lightgbm 7 / catboost 4 | 🏆 **0.0260** | 🏆 **1.55** | H15 |
| **B42** | `model-factory-20260814003436-7d8e60` | **B20 + volume features (P3-5, sans CAPM)** 🔥 | catboost (candidat unique) | lightgbm 6 / catboost 5 | ⚠️ **0.0250** | 1.46 | H20 |

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
| B1   | H3      | 0.0103  | 1.25  | 0.0086        | 143         | catboost   | 1.000           |
| B1   | H5      | 0.0191  | 1.27  | 0.0184        | 143         | catboost   | 0.975           |
| B1   | H10     | 0.0230  | 1.20  | 0.0234        | 143         | catboost   | 0.975           |
| B1   | H15     | 0.0185  | 0.99  | 0.0275        | 143         | catboost   | 0.950           |
| B1   | H20     | 0.0220  | 0.95  | 0.0297        | 143         | catboost   | 0.950           |
| B2   | H3      | 0.0109  | 0.89  | 0.0096        | 166         | catboost   | 0.975           |
| B2   | H5      | 0.0180  | 1.05  | 0.0202        | 166         | catboost   | 0.975           |
| B2   | H10     | 0.0206  | 1.03  | 0.0264        | 166         | catboost   | 0.975           |
| B2   | H15     | 0.0201  | 1.03  | 0.0238        | 166         | catboost   | 0.950           |
| B2   | H20     | 0.0236  | 1.01  | 0.0320        | 166         | catboost   | 0.950           |
| B3   | H3      | 0.0104  | 0.88  | 0.0098        | 144         | catboost   | 0.975           |
| B3   | H5      | 0.0183  | 0.98  | 0.0190        | 144         | catboost   | 0.975           |
| B3   | H10     | 0.0254  | 1.47  | 0.0297        | 144         | catboost   | 0.975           |
| B3   | H15     | 0.0233  | 1.22  | 0.0303        | 144         | catboost   | 0.950           |
| B3   | H20     | 0.0234  | 0.93  | 0.0301        | 144         | catboost   | 0.975           |
| B4   | H3      | 0.0104  | 0.88  | 0.0098        | 144         | catboost   | 0.975           |
| B4   | H5      | 0.0183  | 0.98  | 0.0190        | 144         | catboost   | 0.975           |
| B4   | H10     | 0.0254  | 1.47  | 0.0297        | 144         | catboost   | 0.975           |
| B4   | H15     | 0.0233  | 1.22  | 0.0303        | 144         | catboost   | 0.950           |
| B4   | H20     | 0.0234  | 0.93  | 0.0301        | 144         | catboost   | 0.975           |
| B5   | H3      | 0.0104  | 0.88  | 0.0098        | 144         | catboost   | 0.975           |
| B5   | H5      | 0.0183  | 0.98  | 0.0190        | 144         | catboost   | 0.975           |
| B5   | H10     | 0.0254  | 1.47  | 0.0297        | 144         | catboost   | 0.975           |
| B5   | H15     | 0.0233  | 1.22  | 0.0303        | 144         | catboost   | 0.950           |
| B5   | H20     | 0.0234  | 0.93  | 0.0301        | 144         | catboost   | 0.975           |
| B6   | H3      | 0.0104  | 0.88  | 0.0098        | 144         | catboost   | 0.975           |
| B6   | H5      | 0.0183  | 0.98  | 0.0190        | 144         | catboost   | 0.975           |
| B6   | H10     | 0.0254  | 1.47  | 0.0297        | 144         | catboost   | 0.975           |
| B6   | H15     | 0.0233  | 1.22  | 0.0303        | 144         | catboost   | 0.950           |
| B6   | H20     | 0.0234  | 0.93  | 0.0301        | 144         | catboost   | 0.975           |
| B7   | H3      | 0.0104  | 0.88  | 0.0098        | 144         | catboost   | 0.975           |
| B7   | H5      | 0.0183  | 0.98  | 0.0190        | 144         | catboost   | 0.975           |
| B7   | H10     | 0.0254  | 1.47  | 0.0297        | 144         | catboost   | 0.975           |
| B7   | H15     | 0.0233  | 1.22  | 0.0303        | 144         | catboost   | 0.950           |
| B7   | H20     | 0.0234  | 0.93  | 0.0301        | 144         | catboost   | 0.975           |
| B8   | H3      | 0.0104  | 0.88  | 0.0098        | 144         | catboost   | 0.975           |
| B8   | H5      | 0.0183  | 0.98  | 0.0190        | 144         | catboost   | 0.975           |
| B8   | H10     | 0.0254  | 1.47  | 0.0297        | 144         | catboost   | 0.975           |
| B8   | H15     | 0.0233  | 1.22  | 0.0303        | 144         | catboost   | 0.950           |
| B8   | H20     | 0.0234  | 0.93  | 0.0301        | 144         | catboost   | 0.975           |
| B9   | H3      | 0.0098  | 0.68  | 0.0169        | 144         | ⚠️ lightgbm | 0.950           |
| B9   | H5      | 0.0133  | 0.86  | 0.0145        | 156         | catboost   | 0.975           |
| B9   | H10     | 0.0210  | 1.25  | 0.0197        | 156         | catboost   | 0.975           |
| B9   | H15     | 0.0163  | 1.17  | 0.0121        | 156         | catboost   | 0.975           |
| B9   | H20     | 0.0179  | 1.07  | 0.0131        | 156         | catboost   | 0.975           |
| B10  | H3      | 0.0128  | 1.35  | 0.0103        | 145         | catboost   | 1.000           |
| B10  | H5      | 0.0201  | 1.32  | 0.0186        | 145         | catboost   | 0.975           |
| B10  | H10     | 0.0231  | 1.28  | 0.0274        | 145         | catboost   | 0.950           |
| B10  | H15     | 0.0188  | 0.92  | 0.0267        | 145         | catboost   | 0.950           |
| B10  | H20     | 0.0230  | 1.05  | 0.0294        | 145         | catboost   | 0.950           |
| B11  | H3      | 0.0104  | 0.88  | 0.0098        | 144         | catboost   | 0.975           |
| B11  | H5      | 0.0183  | 0.98  | 0.0190        | 144         | catboost   | 0.975           |
| B11  | H10     | 0.0254  | 1.47  | 0.0297        | 144         | catboost   | 0.975           |
| B11  | H15     | 0.0233  | 1.22  | 0.0303        | 144         | catboost   | 0.950           |
| B11  | H20     | 0.0234  | 0.93  | 0.0301        | 144         | catboost   | 0.975           |
| B12  | H3      | 0.0110  | 0.87  | 0.0097        | 153         | catboost   | 0.975           |
| B12  | H5      | 0.0194  | 1.06  | 0.0173        | 153         | catboost   | 0.975           |
| B12  | H10     | 0.0221  | 0.94  | 0.0250        | 153         | catboost   | 0.950           |
| B12  | H15     | 0.0223  | 1.08  | 0.0257        | 153         | catboost   | 0.950           |
| B12  | H20     | 0.0194  | 0.86  | 0.0268        | 153         | catboost   | 0.950           |
| B13  | H3      | 0.0099  | 0.93  | 0.0065        | 159         | catboost   | 0.950           |
| B13  | H5      | 0.0176  | 1.00  | 0.0158        | 177         | catboost   | 0.975           |
| B13  | H10     | 0.0189  | 1.26  | 0.0225        | 177         | catboost   | 0.975           |
| B13  | H15     | 0.0119  | 0.66  | 0.0181        | 177         | catboost   | 0.950           |
| B13  | H20     | 0.0136  | 0.66  | 0.0191        | 177         | catboost   | 0.925           |
| B14  | H3      | 0.0098  | 0.86  | 0.0094        | 144         | catboost   | 0.975           |
| B14  | H5      | 0.0203  | 1.08  | 0.0211        | 144         | catboost   | 0.975           |
| B14  | H10     | 0.0238  | 1.37  | 0.0269        | 144         | catboost   | 0.975           |
| B14  | H15     | 0.0213  | 1.18  | 0.0275        | 144         | catboost   | 0.950           |
| B14  | H20     | 0.0228  | 0.95  | 0.0305        | 144         | catboost   | 0.975           |
| B15  | H3      | 0.0098  | 0.86  | 0.0094        | 144         | catboost   | 0.975           |
| B15  | H5      | 0.0203  | 1.08  | 0.0211        | 144         | catboost   | 0.975           |
| B15  | H10     | 0.0238  | 1.37  | 0.0269        | 144         | catboost   | 0.975           |
| B15  | H15     | 0.0213  | 1.18  | 0.0275        | 144         | catboost   | 0.950           |
| B15  | H20     | 0.0228  | 0.95  | 0.0305        | 144         | catboost   | 0.975           |
| B16  | H3      | 0.0098  | 0.86  | 0.0094        | 144         | catboost   | 0.975           |
| B16  | H5      | 0.0203  | 1.08  | 0.0211        | 144         | catboost   | 0.975           |
| B16  | H10     | 0.0238  | 1.37  | 0.0269        | 144         | catboost   | 0.975           |
| B16  | H15     | 0.0213  | 1.18  | 0.0275        | 144         | catboost   | 0.950           |
| B16  | H20     | 0.0228  | 0.95  | 0.0305        | 144         | catboost   | 0.975           |
| B17  | H3      | 0.0098  | 0.86  | 0.0094        | 144         | catboost   | 0.975           |
| B17  | H5      | 0.0203  | 1.08  | 0.0211        | 144         | catboost   | 0.975           |
| B17  | H10     | 0.0238  | 1.37  | 0.0269        | 144         | catboost   | 0.975           |
| B17  | H15     | 0.0213  | 1.18  | 0.0275        | 144         | catboost   | 0.950           |
| B17  | H20     | 0.0228  | 0.95  | 0.0305        | 144         | catboost   | 0.975           |
| B18  | H3      | 0.0139  | 1.28  | 0.0113        | 144         | catboost   | 0.981           |
| B18  | H5      | 0.0175  | 0.89  | 0.0170        | 144         | catboost   | 0.859           |
| B18  | H10     | 0.0167  | 0.60  | 0.0164        | 144         | catboost   | 0.944           |
| B18  | H15     | 0.0171  | 0.60  | 0.0131        | 144         | catboost   | 0.944           |
| B18  | H20     | 0.0172  | 0.54  | 0.0160        | 144         | catboost   | 0.963           |
| B19  | H3      | 0.0112  | 1.00  | 0.0095        | 144         | catboost   | 0.973           |
| B19  | H5      | 0.0161  | 0.88  | 0.0152        | 144         | catboost   | 0.959           |
| B19  | H10     | 0.0171  | 0.67  | 0.0213        | 144         | catboost   | 0.945           |
| B19  | H15     | 0.0168  | 0.65  | 0.0196        | 144         | catboost   | 0.945           |
| B19  | H20     | 0.0173  | 0.59  | 0.0207        | 144         | catboost   | 0.959           |
| B20  | H3      | 0.0171  | 1.07  | 0.0149        | 144         | catboost   | 0.975           |
| B20  | H5      | 0.0212  | 0.99  | 0.0196        | 144         | catboost   | 0.975           |
| B20  | H10     | 0.0252  | 1.05  | 0.0170        | 144         | catboost   | 0.975           |
| B20  | H15     | 0.0278  | 1.16  | 0.0270        | 144         | catboost   | 0.975           |
| B20  | H20     | 0.0275  | 1.02  | 0.0262        | 144         | catboost   | 0.950           |
| B21  | H3      | 0.0122  | 1.00  | 0.0111        | 144         | catboost   | 0.975           |
| B21  | H5      | 0.0192  | 1.09  | 0.0211        | 144         | catboost   | 0.975           |
| B21  | H10     | 0.0222  | 1.13  | 0.0297        | 144         | catboost   | 0.975           |
| B21  | H15     | 0.0207  | 0.76  | 0.0208        | 144         | ⚠️ lightgbm | 0.900           |
| B21  | H20     | 0.0197  | 0.93  | 0.0310        | 144         | catboost   | 0.950           |
| B22  | H3      | 0.0119  | 1.08  | 0.0101        | 144         | catboost   | 0.975           |
| B22  | H5      | 0.0199  | 1.22  | 0.0196        | 144         | catboost   | 0.975           |
| B22  | H10     | 0.0194  | 0.95  | 0.0282        | 144         | catboost   | 0.950           |
| B22  | H15     | 0.0207  | 0.76  | 0.0208        | 144         | ⚠️ lightgbm | 0.926           |
| B22  | H20     | 0.0206  | 0.86  | 0.0255        | 144         | catboost   | 0.950           |
| B25  | H3      | 0.0170  | 0.98  | 0.0145        | 145         | catboost   | 0.975           |
| B25  | H5      | 0.0223  | 0.95  | 0.0182        | 145         | catboost   | 0.975           |
| B25  | H10     | 0.0279  | 1.18  | 0.0207        | 145         | catboost   | 0.975           |
| B25  | H15     | 0.0260  | 1.12  | 0.0199        | 145         | catboost   | 0.975           |
| B25  | H20     | 0.0274  | 1.21  | 0.0235        | 145         | catboost   | 0.975           |
| B26  | H3      | 0.0099  | 1.41  | 0.0083        | 145         | catboost   | 0.975           |
| B26  | H5      | 0.0189  | 1.12  | 0.0178        | 145         | catboost   | 0.975           |
| B26  | H10     | 0.0192  | 1.12  | 0.0273        | 145         | catboost   | 0.950           |
| B26  | H15     | 0.0197  | 0.83  | 0.0259        | 145         | catboost   | 0.950           |
| B26  | H20     | 0.0184  | 1.00  | 0.0285        | 145         | catboost   | 0.975           |
| B27  | H3      | 0.0107  | 0.86  | 0.0077        | 145         | catboost   | 0.950           |
| B27  | H5      | 0.0208  | 1.23  | 0.0201        | 145         | catboost   | 0.975           |
| B27  | H10     | 0.0142  | 0.85  | 0.0195        | 145         | catboost   | 0.950           |
| B27  | H15     | 0.0175  | 1.00  | 0.0229        | 145         | catboost   | 0.950           |
| B27  | H20     | 0.0172  | 0.91  | 0.0245        | 145         | catboost   | 0.950           |
| B30  | H3      | 0.0209  | 1.10  | 0.0172        | 144         | catboost   | 1.000           |
| B30  | H5      | 0.0132  | 0.62  | 0.0123        | 144         | catboost   | 0.950           |
| B30  | H10     | 0.0268  | 0.71  | 0.0295        | 144         | ⚠️ lightgbm | 0.975           |
| B30  | H15     | 0.0102  | 0.33  | 0.0114        | 144         | ⚠️ lightgbm | 0.925           |
| B30  | H20     | 0.0054  | 0.15  | 0.0009        | 144         | ⚠️ lightgbm | 0.925           |
| B31  | H3      | 0.0157  | 0.86  | 0.0155        | 144         | catboost   | 0.975           |
| B31  | H5      | 0.0168  | 0.86  | 0.0152        | 156         | catboost   | 0.975           |
| B31  | H10     | 0.0135  | 0.64  | 0.0080        | 156         | catboost   | 0.975           |
| B31  | H15     | 0.0138  | 0.57  | 0.0147        | 156         | catboost   | 0.975           |
| B31  | H20     | 0.0130  | 0.51  | 0.0117        | 156         | catboost   | 0.975           |
| B32  | H3      | 0.0150  | 0.91  | 0.0133        | 153         | catboost   | 0.975           |
| B32  | H5      | 0.0213  | 0.97  | 0.0217        | 153         | catboost   | 0.975           |
| B32  | H10     | 0.0252  | 0.98  | 0.0225        | 153         | catboost   | 0.950           |
| B32  | H15     | 0.0255  | 0.96  | 0.0220        | 153         | catboost   | 0.950           |
| B32  | H20     | 0.0250  | 1.01  | 0.0231        | 153         | catboost   | 0.950           |
| B33  | H3      | 0.0139  | 0.76  | 0.0128        | 159         | catboost   | 0.975           |
| B33  | H5      | 0.0184  | 0.96  | 0.0156        | 177         | catboost   | 0.975           |
| B33  | H10     | 0.0145  | 0.84  | 0.0102        | 177         | catboost   | 0.975           |
| B33  | H15     | 0.0115  | 0.59  | 0.0046        | 177         | catboost   | 0.975           |
| B33  | H20     | 0.0107  | 0.52  | 0.0101        | 177         | catboost   | 0.975           |
| B34  | H3      | 0.0150  | 0.78  | 0.0133        | 181         | catboost   | 0.950           |
| B34  | H5      | 0.0172  | 0.98  | 0.0128        | 199         | catboost   | 0.975           |
| B34  | H10     | 0.0187  | 1.01  | 0.0110        | 199         | catboost   | 0.975           |
| B34  | H15     | 0.0146  | 0.78  | 0.0044        | 199         | catboost   | 0.975           |
| B34  | H20     | 0.0102  | 0.46  | 0.0093        | 199         | catboost   | 0.950           |
| B35  | H3      | 0.0283  | 1.46  | 0.0301        | 145         | catboost   | 1.000           |
| B35  | H5      | 0.0229  | 0.89  | 0.0226        | 145         | catboost   | 0.950           |
| B35  | H10     | 0.0123  | 0.40  | 0.0061        | 145         | ⚠️ lightgbm | 0.900           |
| B35  | H15     | 0.0082  | 0.23  | 0.0071        | 145         | catboost   | 0.950           |
| B35  | H20     | 0.0055  | 0.17  | 0.0100        | 145         | ⚠️ lightgbm | 0.925           |
| B36  | H3      | 0.0277  | 1.57  | 0.0256        | 144         | catboost   | 1.000           |
| B36  | H5      | 0.0246  | 1.23  | 0.0156        | 144         | catboost   | 1.000           |
| B36  | H10     | 0.0078  | 0.25  | 0.0037        | 144         | catboost   | 0.950           |
| B36  | H15     | 0.0072  | 0.20  | 0.0014        | 144         | catboost   | 0.950           |
| B36  | H20     | 0.0068  | 0.16  | 0.0022        | 144         | ⚠️ lightgbm | 0.923           |
| B37  | H3      | 0.0199  | 1.43  | 0.0205        | 145         | catboost   | 1.000           |
| B37  | H5      | 0.0180  | 1.43  | 0.0182        | 145         | catboost   | 0.950           |
| B37  | H10     | 0.0116  | 0.83  | 0.0113        | 145         | catboost   | 0.620           |
| B37  | H15     | 0.0085  | 0.83  | 0.0058        | 145         | catboost   | 0.511           |
| B37  | H20     | 0.0035  | 0.33  | -0.0003       | 145         | catboost   | 0.267           |
| B38  | H3      | 0.0157  | 1.23  | 0.0127        | 145         | catboost   | 0.975           |
| B38  | H5      | 0.0229  | 0.92  | 0.0226        | 145         | catboost   | 0.975           |
| B38  | H10     | 0.0253  | 1.28  | 0.0195        | 145         | catboost   | 0.975           |
| B38  | H15     | 0.0255  | 1.54  | 0.0231        | 145         | catboost   | 0.929           |
| B38  | H20     | 0.0252  | 1.11  | 0.0210        | 145         | catboost   | 0.975           |
| B39  | H3      | 0.0014  | 0.10  | 0.0027        | 145         | xgboost    | 0.177           |
| B39  | H5      | 0.0108  | 0.82  | 0.0110        | 145         | xgboost    | 0.727           |
| B39  | H10     | 0.0145  | 0.66  | 0.0177        | 145         | xgboost    | 0.772           |
| B39  | H15     | 0.0197  | 0.75  | 0.0259        | 145         | xgboost    | 0.951           |
| B39  | H20     | 0.0178  | 0.66  | 0.0232        | 145         | xgboost    | 0.865           |
| B40  | H3      | 0.0146  | 1.77  | 0.0127        | 154         | catboost   | 0.816           |
| B40  | H5      | 0.0179  | 1.18  | 0.0150        | 154         | catboost   | 0.772           |
| B40  | H10     | 0.0220  | 1.26  | 0.0302        | 154         | catboost   | 0.888           |
| B40  | H15     | 0.0172  | 0.98  | 0.0220        | 154         | catboost   | 0.720           |
| B40  | H20     | 0.0171  | 0.99  | 0.0258        | 154         | catboost   | 0.719           |
| B41  | H3      | 0.0220  | 1.36  | 0.0198        | 155         | catboost   | 0.747           |
| B41  | H5      | 0.0242  | 1.22  | 0.0288        | 155         | catboost   | 0.765           |
| B41  | H10     | 0.0265  | 1.61  | 0.0313        | 155         | catboost   | 0.895           |
| B41  | H15     | 0.0294  | 1.94  | 0.0359        | 155         | catboost   | 1.000           |
| B41  | H20     | 0.0279  | 1.89  | 0.0312        | 155         | catboost   | 0.964           |
| B42  | H3      | 0.0207  | 1.20  | 0.0182        | 154         | catboost   | 0.729           |
| B42  | H5      | 0.0232  | 1.24  | 0.0249        | 154         | catboost   | 0.783           |
| B42  | H10     | 0.0282  | 1.60  | 0.0307        | 154         | catboost   | 0.967           |
| B42  | H15     | 0.0258  | 1.62  | 0.0320        | 154         | catboost   | 0.898           |
| B42  | H20     | 0.0271  | 1.80  | 0.0321        | 154         | catboost   | 0.979           |

> 🏆 **Meilleur horizon : H3 pour B37/B36/B35, H10 pour B40/B34/B32/B30/B25/B4/B10, H15 pour B41/B39/B20/B38, H20 pour B42, H5 pour B33/B31/B18/B19/B22/B26/B27** | **B25 = CAPM+YetiRank IC 0.0241. B30 = P1-3 raw rank ❌ (0.0153, −36% vs B20). B31 = fondamentaux+YetiRank ❌ (0.0146, −39% vs B25). B32 = score components+YetiRank ⚠️ (0.0224, 3ᵉ, +11% vs B4, −7% vs B25). B33 = cross-sectional+YetiRank ❌ (0.0138, −43% vs B25). B34 = screener+YetiRank ❌ (0.0151, −37% vs B25). B35/B36 = B25/B20 sur 196 symboles ❌ (0.0154/0.0148, −36%/−38% — le petit univers tue H10-H20). B37 = B25 sur 393 symboles swing ❌ (0.0123, −49% — la composition swing est toxique, pire que B35). **B38 = B25 sur 300 symboles (parmi les 400) ⚠️ 0.0229 (−5% vs B25), IR record 1.14 (+7%) — la réduction 400→300 à composition égale est quasi indolore et conforte le garde-fou breadth 75 % (= 300).**

## 1.2 Champion Global — IC/IR CatBoost vs LightGBM

> **B39 (candidat unique XGBoost rank:ndcg — pas de duel CB/LGBM)** : IC xgboost H3 0.0014 (IR 0.10), H5 0.0108 (0.82), H10 0.0145 (0.66), H15 0.0197 (0.75), H20 0.0178 (0.66) → battu par catboost B25 sur les 5 horizons.
> **B40 (B4 + volume features, candidat unique catboost)** : IC 0.0178 (−12% vs B4 0.0202), IR 1.13. H3 +40% (0.0146, IR 1.77 record) mais H5 −2%, H10 −13%, H15 −26%, H20 −27% vs B4.
> **B41 (B25 + volume features, candidat unique catboost YetiRank)** : 🔥 IC 0.0260 (+7.9% vs B25 0.0241), IR 1.55 (record). H3 +29%, H5 +8%, H15 +13%, H20 +2% vs B25 catboost ; H10 IC 0.0265 (−5%) mais IR 1.61 vs 1.18 (+36%) → B41 prend H10 aussi (5/5). Decile spreads +36 à +80%.
> **B42 (B20 + volume features, candidat unique catboost YetiRank — sans CAPM ni include-factors)** : 🔥 IC 0.0250 (+5.0% vs B20 0.0238), IR 1.46 (+42% vs 1.03). H3 +21%, H5 +9%, H10 +12%, H15 −7%, H20 −1% vs B20. **Ablation pure du volume (B42 vs B20, seule variable) : +5% d'IC, +42% d'IR. H10 = 0.0282 (IR 1.60) = record H10 de la série.**

| Test | Horizon | IC catboost | IR catboost | IC lightgbm | IR lightgbm | 🏆 Vainqueur |
|:-----|:--------|------------:|------------:|------------:|------------:|:-----------|
| B0   | H3      | 0.0103      | 1.25        | 0.0086      | 0.55        | catboost   |
| B0   | H5      | 0.0191      | 1.27        | 0.0113      | 0.82        | catboost   |
| B0   | H10     | 0.0230      | 1.20        | 0.0041      | 0.18        | catboost   |
| B0   | H15     | 0.0185      | 0.99        | 0.0139      | 0.37        | catboost   |
| B0   | H20     | 0.0220      | 0.95        | 0.0090      | 0.25        | catboost   |
| B1   | H3      | 0.0103      | 1.25        | 0.0086      | 0.55        | catboost   |
| B1   | H5      | 0.0191      | 1.27        | 0.0113      | 0.82        | catboost   |
| B1   | H10     | 0.0230      | 1.20        | 0.0041      | 0.18        | catboost   |
| B1   | H15     | 0.0185      | 0.99        | 0.0139      | 0.37        | catboost   |
| B1   | H20     | 0.0220      | 0.95        | 0.0090      | 0.25        | catboost   |
| B2   | H3      | 0.0109      | 0.89        | 0.0046      | 0.22        | catboost   |
| B2   | H5      | 0.0180      | 1.05        | 0.0081      | 0.35        | catboost   |
| B2   | H10     | 0.0206      | 1.03        | 0.0025      | 0.10        | catboost   |
| B2   | H15     | 0.0201      | 1.03        | 0.0168      | 0.50        | catboost   |
| B2   | H20     | 0.0236      | 1.01        | 0.0203      | 0.63        | catboost   |
| B3   | H3      | 0.0104      | 0.88        | 0.0029      | 0.28        | catboost   |
| B3   | H5      | 0.0183      | 0.98        | 0.0087      | 0.62        | catboost   |
| B3   | H10     | 0.0254      | 1.47        | 0.0105      | 0.40        | catboost   |
| B3   | H15     | 0.0233      | 1.22        | 0.0207      | 0.76        | catboost   |
| B3   | H20     | 0.0234      | 0.93        | 0.0084      | 0.30        | catboost   |
| B4   | H3      | 0.0104      | 0.88        | 0.0029      | 0.28        | catboost   |
| B4   | H5      | 0.0183      | 0.98        | 0.0087      | 0.62        | catboost   |
| B4   | H10     | 0.0254      | 1.47        | 0.0105      | 0.40        | catboost   |
| B4   | H15     | 0.0233      | 1.22        | 0.0207      | 0.76        | catboost   |
| B4   | H20     | 0.0234      | 0.93        | 0.0084      | 0.30        | catboost   |
| B5   | H3      | 0.0104      | 0.88        | 0.0029      | 0.28        | catboost   |
| B5   | H5      | 0.0183      | 0.98        | 0.0087      | 0.62        | catboost   |
| B5   | H10     | 0.0254      | 1.47        | 0.0105      | 0.40        | catboost   |
| B5   | H15     | 0.0233      | 1.22        | 0.0207      | 0.76        | catboost   |
| B5   | H20     | 0.0234      | 0.93        | 0.0084      | 0.30        | catboost   |
| B6   | H3      | 0.0104      | 0.88        | 0.0029      | 0.28        | catboost   |
| B6   | H5      | 0.0183      | 0.98        | 0.0087      | 0.62        | catboost   |
| B6   | H10     | 0.0254      | 1.47        | 0.0105      | 0.40        | catboost   |
| B6   | H15     | 0.0233      | 1.22        | 0.0207      | 0.76        | catboost   |
| B6   | H20     | 0.0234      | 0.93        | 0.0084      | 0.30        | catboost   |
| B7   | H3      | 0.0104      | 0.88        | 0.0029      | 0.28        | catboost   |
| B7   | H5      | 0.0183      | 0.98        | 0.0087      | 0.62        | catboost   |
| B7   | H10     | 0.0254      | 1.47        | 0.0105      | 0.40        | catboost   |
| B7   | H15     | 0.0233      | 1.22        | 0.0207      | 0.76        | catboost   |
| B7   | H20     | 0.0234      | 0.93        | 0.0084      | 0.30        | catboost   |
| B8   | H3      | 0.0104      | 0.88        | 0.0029      | 0.28        | catboost   |
| B8   | H5      | 0.0183      | 0.98        | 0.0087      | 0.62        | catboost   |
| B8   | H10     | 0.0254      | 1.47        | 0.0105      | 0.40        | catboost   |
| B8   | H15     | 0.0233      | 1.22        | 0.0207      | 0.76        | catboost   |
| B8   | H20     | 0.0234      | 0.93        | 0.0084      | 0.30        | catboost   |
| B9   | H3      | 0.0045      | 0.43        | 0.0098      | 0.68        | ⚠️ lightgbm |
| B9   | H5      | 0.0133      | 0.86        | 0.0095      | 0.54        | catboost   |
| B9   | H10     | 0.0210      | 1.25        | −0.0005     | −0.02       | catboost   |
| B9   | H15     | 0.0163      | 1.17        | 0.0047      | 0.22        | catboost   |
| B9   | H20     | 0.0179      | 1.07        | 0.0081      | 0.34        | catboost   |
| B10  | H3      | 0.0128      | 1.35        | 0.0078      | 0.66        | catboost   |
| B10  | H5      | 0.0201      | 1.32        | 0.0152      | 0.72        | catboost   |
| B10  | H10     | 0.0231      | 1.28        | 0.0127      | 0.62        | catboost   |
| B10  | H15     | 0.0188      | 0.92        | 0.0152      | 0.48        | catboost   |
| B10  | H20     | 0.0230      | 1.05        | 0.0074      | 0.28        | catboost   |
| B11  | H3      | 0.0104      | 0.88        | 0.0029      | 0.28        | catboost   |
| B11  | H5      | 0.0183      | 0.98        | 0.0087      | 0.62        | catboost   |
| B11  | H10     | 0.0254      | 1.47        | 0.0105      | 0.40        | catboost   |
| B11  | H15     | 0.0233      | 1.22        | 0.0207      | 0.76        | catboost   |
| B11  | H20     | 0.0234      | 0.93        | 0.0084      | 0.30        | catboost   |
| B12  | H3      | 0.0110      | 0.87        | 0.0043      | 0.30        | catboost   |
| B12  | H5      | 0.0194      | 1.06        | 0.0118      | 0.53        | catboost   |
| B12  | H10     | 0.0221      | 0.94        | 0.0127      | 0.41        | catboost   |
| B12  | H15     | 0.0223      | 1.08        | 0.0005      | 0.03        | catboost   |
| B12  | H20     | 0.0194      | 0.86        | 0.0021      | 0.11        | catboost   |
| B13  | H3      | 0.0099      | 0.93        | 0.0045      | 0.23        | catboost   |
| B13  | H5      | 0.0176      | 1.00        | 0.0076      | 0.51        | catboost   |
| B13  | H10     | 0.0189      | 1.26        | 0.0114      | 0.62        | catboost   |
| B13  | H15     | 0.0119      | 0.66        | 0.0066      | 0.48        | catboost   |
| B13  | H20     | 0.0136      | 0.66        | −0.0044     | −0.52       | catboost   |
| B14  | H3      | 0.0098      | 0.86        | 0.0022      | 0.20        | catboost   |
| B14  | H5      | 0.0203      | 1.08        | 0.0089      | 0.64        | catboost   |
| B14  | H10     | 0.0238      | 1.37        | 0.0105      | 0.40        | catboost   |
| B14  | H15     | 0.0213      | 1.18        | 0.0207      | 0.76        | catboost   |
| B14  | H20     | 0.0228      | 0.95        | 0.0084      | 0.30        | catboost   |
| B15  | H3      | 0.0098      | 0.86        | 0.0022      | 0.20        | catboost   |
| B15  | H5      | 0.0203      | 1.08        | 0.0089      | 0.64        | catboost   |
| B15  | H10     | 0.0238      | 1.37        | 0.0105      | 0.40        | catboost   |
| B15  | H15     | 0.0213      | 1.18        | 0.0207      | 0.76        | catboost   |
| B15  | H20     | 0.0228      | 0.95        | 0.0084      | 0.30        | catboost   |
| B16  | H3      | 0.0098      | 0.86        | 0.0022      | 0.20        | catboost   |
| B16  | H5      | 0.0203      | 1.08        | 0.0089      | 0.64        | catboost   |
| B16  | H10     | 0.0238      | 1.37        | 0.0105      | 0.40        | catboost   |
| B16  | H15     | 0.0213      | 1.18        | 0.0207      | 0.76        | catboost   |
| B16  | H20     | 0.0228      | 0.95        | 0.0084      | 0.30        | catboost   |
| B17  | H3      | 0.0098      | 0.86        | 0.0022      | 0.20        | catboost   |
| B17  | H5      | 0.0203      | 1.08        | 0.0089      | 0.64        | catboost   |
| B17  | H10     | 0.0238      | 1.37        | 0.0105      | 0.40        | catboost   |
| B17  | H15     | 0.0213      | 1.18        | 0.0207      | 0.76        | catboost   |
| B17  | H20     | 0.0228      | 0.95        | 0.0084      | 0.30        | catboost   |
| B18  | H3      | 0.0139      | 1.28        | 0.0096      | 0.66        | catboost   |
| B18  | H5      | 0.0175      | 0.89        | 0.0059      | 1.50        | ⚠️ lightgbm IR |
| B18  | H10     | 0.0167      | 0.60        | 0.0081      | 0.47        | catboost   |
| B18  | H15     | 0.0171      | 0.60        | 0.0015      | 0.11        | catboost   |
| B18  | H20     | 0.0172      | 0.54        | 0.0137      | 0.53        | catboost   |
| B19  | H3      | 0.0112      | 1.00        | 0.0090      | 0.72        | catboost   |
| B19  | H5      | 0.0161      | 0.88        | 0.0042      | 0.92        | catboost   |
| B19  | H10     | 0.0171      | 0.67        | 0.0045      | 0.26        | catboost   |
| B19  | H15     | 0.0168      | 0.65        | 0.0012      | 0.08        | catboost   |
| B19  | H20     | 0.0173      | 0.59        | 0.0048      | 0.18        | catboost   |
| B20  | H3      | 0.0171      | 1.07        | 0.0022      | 0.20        | catboost   |
| B20  | H5      | 0.0212      | 0.99        | 0.0089      | 0.64        | catboost   |
| B20  | H10     | 0.0252      | 1.05        | 0.0105      | 0.40        | catboost   |
| B20  | H15     | 0.0278      | 1.16        | 0.0207      | 0.76        | catboost   |
| B20  | H20     | 0.0275      | 1.02        | 0.0084      | 0.30        | catboost   |
| B21  | H3      | 0.0122      | 1.00        | 0.0022      | 0.20        | catboost   |
| B21  | H5      | 0.0192      | 1.09        | 0.0089      | 0.64        | catboost   |
| B21  | H10     | 0.0222      | 1.13        | 0.0105      | 0.40        | catboost   |
| B21  | H15     | 0.0173      | 1.02        | 0.0207      | 0.76        | ⚠️ lightgbm |
| B21  | H20     | 0.0197      | 0.93        | 0.0084      | 0.30        | catboost   |
| B22  | H3      | 0.0119      | 1.08        | 0.0022      | 0.20        | catboost   |
| B22  | H5      | 0.0199      | 1.22        | 0.0089      | 0.64        | catboost   |
| B22  | H10     | 0.0194      | 0.95        | 0.0105      | 0.40        | catboost   |
| B22  | H15     | 0.0158      | 0.91        | 0.0207      | 0.76        | ⚠️ lightgbm |
| B22  | H20     | 0.0206      | 0.86        | 0.0084      | 0.30        | catboost   |
| B25  | H3      | 0.0170      | 0.98        | 0.0075      | 0.62        | catboost   |
| B25  | H5      | 0.0223      | 0.95        | 0.0150      | 0.71        | catboost   |
| B25  | H10     | 0.0279      | 1.18        | 0.0127      | 0.62        | catboost   |
| B25  | H15     | 0.0260      | 1.12        | 0.0152      | 0.48        | catboost   |
| B25  | H20     | 0.0274      | 1.21        | 0.0074      | 0.28        | catboost   |
| B26  | H3      | 0.0099      | 1.41        | 0.0075      | 0.62        | catboost   |
| B26  | H5      | 0.0189      | 1.12        | 0.0150      | 0.71        | catboost   |
| B26  | H10     | 0.0192      | 1.12        | 0.0127      | 0.62        | catboost   |
| B26  | H15     | 0.0197      | 0.83        | 0.0152      | 0.48        | catboost   |
| B26  | H20     | 0.0184      | 1.00        | 0.0074      | 0.28        | catboost   |
| B27  | H3      | 0.0107      | 0.86        | 0.0075      | 0.62        | catboost   |
| B27  | H5      | 0.0208      | 1.23        | 0.0150      | 0.71        | catboost   |
| B27  | H10     | 0.0142      | 0.85        | 0.0127      | 0.62        | catboost   |
| B27  | H15     | 0.0175      | 1.00        | 0.0152      | 0.48        | catboost   |
| B27  | H20     | 0.0172      | 0.91        | 0.0074      | 0.28        | catboost   |
| B30  | H3      | 0.0209      | 1.10        | 0.0039      | 0.54        | catboost   |
| B30  | H5      | 0.0132      | 0.62        | 0.0083      | 0.36        | catboost   |
| B30  | H10     | 0.0074      | 0.36        | 0.0268      | 0.71        | ⚠️ lightgbm |
| B30  | H15     | -0.0006     | -0.02       | 0.0102      | 0.33        | ⚠️ lightgbm |
| B30  | H20     | -0.0043     | -0.12       | 0.0054      | 0.15        | ⚠️ lightgbm |
| B31  | H3      | 0.0157      | 0.86        | 0.0098      | 0.68        | catboost   |
| B31  | H5      | 0.0168      | 0.86        | 0.0095      | 0.54        | catboost   |
| B31  | H10     | 0.0135      | 0.64        | -0.0005     | -0.02       | catboost   |
| B31  | H15     | 0.0138      | 0.57        | 0.0047      | 0.22        | catboost   |
| B31  | H20     | 0.0130      | 0.51        | 0.0081      | 0.34        | catboost   |
| B32  | H3      | 0.0150      | 0.91        | 0.0046      | 0.34        | catboost   |
| B32  | H5      | 0.0213      | 0.97        | 0.0114      | 0.51        | catboost   |
| B32  | H10     | 0.0252      | 0.98        | 0.0129      | 0.41        | catboost   |
| B32  | H15     | 0.0255      | 0.96        | 0.0009      | 0.04        | catboost   |
| B32  | H20     | 0.0250      | 1.01        | 0.0021      | 0.11        | catboost   |
| B33  | H3      | 0.0139      | 0.76        | 0.0045      | 0.23        | catboost   |
| B33  | H5      | 0.0184      | 0.96        | 0.0076      | 0.51        | catboost   |
| B33  | H10     | 0.0145      | 0.84        | 0.0114      | 0.62        | catboost   |
| B33  | H15     | 0.0115      | 0.59        | 0.0066      | 0.48        | catboost   |
| B33  | H20     | 0.0107      | 0.52        | -0.0044     | -0.52       | catboost   |
| B34  | H3      | 0.0150      | 0.78        | 0.0005      | 0.02        | catboost   |
| B34  | H5      | 0.0172      | 0.98        | 0.0017      | 0.21        | catboost   |
| B34  | H10     | 0.0187      | 1.01        | 0.0046      | 0.29        | catboost   |
| B34  | H15     | 0.0146      | 0.78        | 0.0068      | 0.28        | catboost   |
| B34  | H20     | 0.0102      | 0.46        | -0.0041     | -0.17       | catboost   |
| B35  | H3      | 0.0283      | 1.46        | 0.0170      | 0.97        | catboost   |
| B35  | H5      | 0.0229      | 0.89        | 0.0079      | 0.70        | catboost   |
| B35  | H10     | 0.0071      | 0.22        | 0.0123      | 0.40        | ⚠️ lightgbm |
| B35  | H15     | 0.0082      | 0.23        | -0.0065     | -0.22       | catboost   |
| B35  | H20     | 0.0024      | 0.06        | 0.0055      | 0.17        | ⚠️ lightgbm |
| B36  | H3      | 0.0277      | 1.57        | 0.0108      | 0.95        | catboost   |
| B36  | H5      | 0.0246      | 1.23        | 0.0139      | 0.62        | catboost   |
| B36  | H10     | 0.0078      | 0.25        | -0.0018     | -0.06       | catboost   |
| B36  | H15     | 0.0072      | 0.20        | 0.0031      | 0.08        | catboost   |
| B36  | H20     | 0.0062      | 0.16        | 0.0068      | 0.16        | ⚠️ lightgbm |
| B37  | H3      | 0.0199      | 1.43        | 0.0018      | 0.10        | catboost   |
| B37  | H5      | 0.0180      | 1.43        | 0.0041      | 0.28        | catboost   |
| B37  | H10     | 0.0116      | 0.83        | 0.0001      | 0.00        | catboost   |
| B37  | H15     | 0.0085      | 0.83        | 0.0108      | 0.46        | catboost   |
| B37  | H20     | 0.0035      | 0.33        | -0.0027     | -0.12       | catboost   |
| B38  | H3      | 0.0157      | 1.23        | 0.0092      | 0.99        | catboost   |
| B38  | H5      | 0.0229      | 0.92        | 0.0055      | 0.37        | catboost   |
| B38  | H10     | 0.0253      | 1.28        | 0.0047      | 0.16        | catboost   |
| B38  | H15     | 0.0255      | 1.54        | 0.0293      | 0.72        | catboost   |
| B38  | H20     | 0.0252      | 1.11        | 0.0033      | 0.14        | catboost   |

## 1.3 Détail IC par split — Champion (Global)

| Test | Horizon | Split 1 | Split 2 | Split 3 | Split 4 | Split 5 | Split 6 | IC Std | IC Min | IC Max |
|:-----|:--------|--------:|--------:|--------:|--------:|--------:|--------:|-------:|-------:|-------:|
| B0   | H3      | 0.0056  | 0.0230  | 0.0199  | 0.0008  | 0.0082  | 0.0043  | 0.0082 | 0.0008 | 0.0230 |
| B0   | H5      | 0.0088  | 0.0439  | 0.0282  | -0.0041 | 0.0156  | 0.0224  | 0.0151 |-0.0041 | 0.0439 |
| B0   | H10     | 0.0038  | 0.0513  | 0.0338  | -0.0057 | 0.0326  | 0.0221  | 0.0192 |-0.0057 | 0.0513 |
| B0   | H15     | -0.0077 | 0.0284  | 0.0378  | -0.0030 | 0.0395  | 0.0158  | 0.0186 |-0.0077 | 0.0395 |
| B0   | H20     | -0.0038 | 0.0318  | 0.0582  | -0.0011 | 0.0412  | 0.0061  | 0.0232 |-0.0038 | 0.0582 |
| B1   | H3      | 0.0056  | 0.0230  | 0.0199  | 0.0008  | 0.0082  | 0.0043  | 0.0082 | 0.0008 | 0.0230 |
| B1   | H5      | 0.0088  | 0.0439  | 0.0282  | -0.0041 | 0.0156  | 0.0224  | 0.0151 |-0.0041 | 0.0439 |
| B1   | H10     | 0.0038  | 0.0513  | 0.0338  | -0.0057 | 0.0326  | 0.0221  | 0.0192 |-0.0057 | 0.0513 |
| B1   | H15     | -0.0077 | 0.0284  | 0.0378  | -0.0030 | 0.0395  | 0.0158  | 0.0186 |-0.0077 | 0.0395 |
| B1   | H20     | -0.0038 | 0.0318  | 0.0582  | -0.0011 | 0.0412  | 0.0061  | 0.0232 |-0.0038 | 0.0582 |
| B2   | H3      | 0.0028  | 0.0309  | 0.0231  | -0.0046 | 0.0081  | 0.0049  | 0.0122 |-0.0046 | 0.0309 |
| B2   | H5      | 0.0014  | 0.0491  | 0.0220  | -0.0040 | 0.0178  | 0.0215  | 0.0171 |-0.0040 | 0.0491 |
| B2   | H10     | 0.0012  | 0.0475  | 0.0381  | -0.0075 | 0.0324  | 0.0120  | 0.0200 |-0.0075 | 0.0475 |
| B2   | H15     | -0.0016 | 0.0360  | 0.0413  | -0.0053 | 0.0393  | 0.0110  | 0.0194 |-0.0053 | 0.0413 |
| B2   | H20     | -0.0081 | 0.0372  | 0.0504  | -0.0061 | 0.0459  | 0.0226  | 0.0234 |-0.0081 | 0.0504 |
| B3   | H3      | 0.0016  | 0.0234  | 0.0264  | -0.0075 | 0.0116  | 0.0069  | 0.0118 |-0.0075 | 0.0264 |
| B3   | H5      | 0.0057  | 0.0547  | 0.0164  | -0.0056 | 0.0232  | 0.0154  | 0.0187 |-0.0056 | 0.0547 |
| B3   | H10     | 0.0104  | 0.0440  | 0.0375  | -0.0039 | 0.0398  | 0.0245  | 0.0172 |-0.0039 | 0.0440 |
| B3   | H15     | -0.0002 | 0.0356  | 0.0468  | -0.0023 | 0.0398  | 0.0201  | 0.0191 |-0.0023 | 0.0468 |
| B3   | H20     | -0.0098 | 0.0305  | 0.0645  | 0.0006  | 0.0407  | 0.0137  | 0.0250 |-0.0098 | 0.0645 |
| B4   | H3      | 0.0016  | 0.0234  | 0.0264  | -0.0075 | 0.0116  | 0.0069  | 0.0118 |-0.0075 | 0.0264 |
| B4   | H5      | 0.0057  | 0.0547  | 0.0164  | -0.0056 | 0.0232  | 0.0154  | 0.0187 |-0.0056 | 0.0547 |
| B4   | H10     | 0.0104  | 0.0440  | 0.0375  | -0.0039 | 0.0398  | 0.0245  | 0.0172 |-0.0039 | 0.0440 |
| B4   | H15     | -0.0002 | 0.0356  | 0.0468  | -0.0023 | 0.0398  | 0.0201  | 0.0191 |-0.0023 | 0.0468 |
| B4   | H20     | -0.0098 | 0.0305  | 0.0645  | 0.0006  | 0.0407  | 0.0137  | 0.0250 |-0.0098 | 0.0645 |
| B5   | H3      | 0.0016  | 0.0234  | 0.0264  | -0.0075 | 0.0116  | 0.0069  | 0.0118 |-0.0075 | 0.0264 |
| B5   | H5      | 0.0057  | 0.0547  | 0.0164  | -0.0056 | 0.0232  | 0.0154  | 0.0187 |-0.0056 | 0.0547 |
| B5   | H10     | 0.0104  | 0.0440  | 0.0375  | -0.0039 | 0.0398  | 0.0245  | 0.0172 |-0.0039 | 0.0440 |
| B5   | H15     | -0.0002 | 0.0356  | 0.0468  | -0.0023 | 0.0398  | 0.0201  | 0.0191 |-0.0023 | 0.0468 |
| B5   | H20     | -0.0098 | 0.0305  | 0.0645  | 0.0006  | 0.0407  | 0.0137  | 0.0250 |-0.0098 | 0.0645 |
| B6   | H3      | 0.0016  | 0.0234  | 0.0264  | -0.0075 | 0.0116  | 0.0069  | 0.0118 |-0.0075 | 0.0264 |
| B6   | H5      | 0.0057  | 0.0547  | 0.0164  | -0.0056 | 0.0232  | 0.0154  | 0.0187 |-0.0056 | 0.0547 |
| B6   | H10     | 0.0104  | 0.0440  | 0.0375  | -0.0039 | 0.0398  | 0.0245  | 0.0172 |-0.0039 | 0.0440 |
| B6   | H15     | -0.0002 | 0.0356  | 0.0468  | -0.0023 | 0.0398  | 0.0201  | 0.0191 |-0.0023 | 0.0468 |
| B6   | H20     | -0.0098 | 0.0305  | 0.0645  | 0.0006  | 0.0407  | 0.0137  | 0.0250 |-0.0098 | 0.0645 |
| B7   | H3      | 0.0016  | 0.0234  | 0.0264  | -0.0075 | 0.0116  | 0.0069  | 0.0118 |-0.0075 | 0.0264 |
| B7   | H5      | 0.0057  | 0.0547  | 0.0164  | -0.0056 | 0.0232  | 0.0154  | 0.0187 |-0.0056 | 0.0547 |
| B7   | H10     | 0.0104  | 0.0440  | 0.0375  | -0.0039 | 0.0398  | 0.0245  | 0.0172 |-0.0039 | 0.0440 |
| B7   | H15     | -0.0002 | 0.0356  | 0.0468  | -0.0023 | 0.0398  | 0.0201  | 0.0191 |-0.0023 | 0.0468 |
| B7   | H20     | -0.0098 | 0.0305  | 0.0645  | 0.0006  | 0.0407  | 0.0137  | 0.0250 |-0.0098 | 0.0645 |
| B8   | H3      | 0.0016  | 0.0234  | 0.0264  | -0.0075 | 0.0116  | 0.0069  | 0.0118 |-0.0075 | 0.0264 |
| B8   | H5      | 0.0057  | 0.0547  | 0.0164  | -0.0056 | 0.0232  | 0.0154  | 0.0187 |-0.0056 | 0.0547 |
| B8   | H10     | 0.0104  | 0.0440  | 0.0375  | -0.0039 | 0.0398  | 0.0245  | 0.0172 |-0.0039 | 0.0440 |
| B8   | H15     | -0.0002 | 0.0356  | 0.0468  | -0.0023 | 0.0398  | 0.0201  | 0.0191 |-0.0023 | 0.0468 |
| B8   | H20     | -0.0098 | 0.0305  | 0.0645  | 0.0006  | 0.0407  | 0.0137  | 0.0250 |-0.0098 | 0.0645 |
| B9   | H3      | 0.0172  | 0.0329  | −0.0005 | −0.0117 | 0.0040  | 0.0167  | 0.0144 |−0.0117 | 0.0329 |
| B9   | H5      | 0.0062  | 0.0303  | 0.0273  | −0.0164 | 0.0141  | 0.0184  | 0.0155 |−0.0164 | 0.0303 |
| B9   | H10     | 0.0162  | 0.0136  | 0.0343  | −0.0086 | 0.0438  | 0.0269  | 0.0168 |−0.0086 | 0.0438 |
| B9   | H15     | 0.0178  | 0.0105  | 0.0279  | −0.0114 | 0.0302  | 0.0228  | 0.0140 |−0.0114 | 0.0302 |
| B9   | H20     | 0.0107  | 0.0026  | 0.0414  | −0.0058 | 0.0312  | 0.0272  | 0.0167 |−0.0058 | 0.0414 |
| B10  | H3      | 0.0077  | 0.0286  | 0.0205  | 0.0008  | 0.0136  | 0.0054  | 0.0094 | 0.0008 | 0.0286 |
| B10  | H5      | 0.0079  | 0.0482  | 0.0231  | −0.0003 | 0.0243  | 0.0173  | 0.0152 |−0.0003 | 0.0482 |
| B10  | H10     | −0.0004 | 0.0406  | 0.0386  | −0.0026 | 0.0362  | 0.0260  | 0.0180 |−0.0026 | 0.0406 |
| B10  | H15     | −0.0144 | 0.0385  | 0.0385  | −0.0003 | 0.0343  | 0.0160  | 0.0204 |−0.0144 | 0.0385 |
| B10  | H20     | −0.0016 | 0.0394  | 0.0498  | −0.0045 | 0.0434  | 0.0114  | 0.0220 |−0.0045 | 0.0498 |
| B11  | H3      | 0.0016  | 0.0234  | 0.0264  | -0.0075 | 0.0116  | 0.0069  | 0.0118 |-0.0075 | 0.0264 |
| B11  | H5      | 0.0057  | 0.0547  | 0.0164  | -0.0056 | 0.0232  | 0.0154  | 0.0187 |-0.0056 | 0.0547 |
| B11  | H10     | 0.0104  | 0.0440  | 0.0375  | -0.0039 | 0.0398  | 0.0245  | 0.0172 |-0.0039 | 0.0440 |
| B11  | H15     | -0.0002 | 0.0356  | 0.0468  | -0.0023 | 0.0398  | 0.0201  | 0.0191 |-0.0023 | 0.0468 |
| B11  | H20     | -0.0098 | 0.0305  | 0.0645  | 0.0006  | 0.0407  | 0.0137  | 0.0250 |-0.0098 | 0.0645 |
| B12  | H3      | -0.0031 | 0.0347  | 0.0170  | 0.0006  | 0.0045  | 0.0123  | 0.0126 |-0.0031 | 0.0347 |
| B12  | H5      | 0.0044  | 0.0473  | 0.0299  | -0.0102 | 0.0244  | 0.0205  | 0.0183 |-0.0102 | 0.0473 |
| B12  | H10     | -0.0057 | 0.0584  | 0.0316  | -0.0086 | 0.0365  | 0.0202  | 0.0236 |-0.0086 | 0.0584 |
| B12  | H15     | -0.0056 | 0.0441  | 0.0454  | -0.0001 | 0.0358  | 0.0140  | 0.0206 |-0.0056 | 0.0454 |
| B12  | H20     | -0.0059 | 0.0229  | 0.0521  | -0.0043 | 0.0444  | 0.0069  | 0.0226 |-0.0059 | 0.0521 |
| B13  | H3      | -0.0015 | 0.0248  | 0.0229  | -0.0023 | 0.0100  | 0.0059  | 0.0107 |-0.0023 | 0.0248 |
| B13  | H5      | 0.0030  | 0.0468  | 0.0246  | -0.0087 | 0.0250  | 0.0149  | 0.0176 |-0.0087 | 0.0468 |
| B13  | H10     | 0.0052  | 0.0375  | 0.0314  | -0.0052 | 0.0283  | 0.0165  | 0.0151 |-0.0052 | 0.0375 |
| B13  | H15     | -0.0041 | 0.0185  | 0.0390  | -0.0112 | 0.0284  | 0.0010  | 0.0181 |-0.0112 | 0.0390 |
| B13  | H20     | -0.0091 | 0.0179  | 0.0433  | -0.0063 | 0.0368  | -0.0011 | 0.0207 |-0.0091 | 0.0433 |
| B14  | H3      | 0.0016  | 0.0234  | 0.0235  | -0.0088 | 0.0101  | 0.0092  | 0.0115 |-0.0088 | 0.0235 |
| B14  | H5      | 0.0057  | 0.0547  | 0.0233  | -0.0056 | 0.0259  | 0.0174  | 0.0188 |-0.0056 | 0.0547 |
| B14  | H10     | 0.0104  | 0.0440  | 0.0416  | -0.0041 | 0.0339  | 0.0172  | 0.0175 |-0.0041 | 0.0440 |
| B14  | H15     | -0.0002 | 0.0356  | 0.0411  | -0.0029 | 0.0381  | 0.0159  | 0.0181 |-0.0029 | 0.0411 |
| B14  | H20     | -0.0098 | 0.0305  | 0.0558  | 0.0006  | 0.0478  | 0.0122  | 0.0240 |-0.0098 | 0.0558 |
| B15  | H3      | 0.0016  | 0.0234  | 0.0235  | -0.0088 | 0.0101  | 0.0092  | 0.0115 |-0.0088 | 0.0235 |
| B15  | H5      | 0.0057  | 0.0547  | 0.0233  | -0.0056 | 0.0259  | 0.0174  | 0.0188 |-0.0056 | 0.0547 |
| B15  | H10     | 0.0104  | 0.0440  | 0.0416  | -0.0041 | 0.0339  | 0.0172  | 0.0175 |-0.0041 | 0.0440 |
| B15  | H15     | -0.0002 | 0.0356  | 0.0411  | -0.0029 | 0.0381  | 0.0159  | 0.0181 |-0.0029 | 0.0411 |
| B15  | H20     | -0.0098 | 0.0305  | 0.0558  | 0.0006  | 0.0478  | 0.0122  | 0.0240 |-0.0098 | 0.0558 |
| B16  | H3      | 0.0016  | 0.0234  | 0.0235  | -0.0088 | 0.0101  | 0.0092  | 0.0115 |-0.0088 | 0.0235 |
| B16  | H5      | 0.0057  | 0.0547  | 0.0233  | -0.0056 | 0.0259  | 0.0174  | 0.0188 |-0.0056 | 0.0547 |
| B16  | H10     | 0.0104  | 0.0440  | 0.0416  | -0.0041 | 0.0339  | 0.0172  | 0.0175 |-0.0041 | 0.0440 |
| B16  | H15     | -0.0002 | 0.0356  | 0.0411  | -0.0029 | 0.0381  | 0.0159  | 0.0181 |-0.0029 | 0.0411 |
| B16  | H20     | -0.0098 | 0.0305  | 0.0558  | 0.0006  | 0.0478  | 0.0122  | 0.0240 |-0.0098 | 0.0558 |
| B17  | H3      | 0.0016  | 0.0234  | 0.0235  | -0.0088 | 0.0101  | 0.0092  | 0.0115 |-0.0088 | 0.0235 |
| B17  | H5      | 0.0057  | 0.0547  | 0.0233  | -0.0056 | 0.0259  | 0.0174  | 0.0188 |-0.0056 | 0.0547 |
| B17  | H10     | 0.0104  | 0.0440  | 0.0416  | -0.0041 | 0.0339  | 0.0172  | 0.0175 |-0.0041 | 0.0440 |
| B17  | H15     | -0.0002 | 0.0356  | 0.0411  | -0.0029 | 0.0381  | 0.0159  | 0.0181 |-0.0029 | 0.0411 |
| B17  | H20     | -0.0098 | 0.0305  | 0.0558  | 0.0006  | 0.0478  | 0.0122  | 0.0240 |-0.0098 | 0.0558 |
| B18  | H3      | 0.0197  | 0.0166  | -0.0012 | 0.0065  | 0.0107  | 0.0075  | 0.0379 | 0.0136 | 0.0109 | -0.0012| 0.0379 |
| B18  | H5      | 0.0114  | 0.0184  | 0.0109  | -0.0098 | 0.0112  | 0.0113  | 0.0645 | 0.0224 | 0.0198 | -0.0098| 0.0645 |
| B18  | H10     | 0.0144  | 0.0539  | 0.0163  | -0.0334 | -0.0027 | -0.0016 | 0.0527 | 0.0339 | 0.0279 | -0.0334| 0.0539 |
| B18  | H15     | 0.0238  | 0.0477  | 0.0222  | -0.0346 | -0.0013 | -0.0118 | 0.0439 | 0.0472 | 0.0284 | -0.0346| 0.0477 |
| B18  | H20     | 0.0180  | 0.0599  | 0.0112  | -0.0408 | 0.0033  | -0.0092 | 0.0423 | 0.0528 | 0.0317 | -0.0408| 0.0599 |
| B19  | H3      | 0.0197  | 0.0166  | -0.0012 | 0.0065  | 0.0107  | 0.0075  | 0.0379 | 0.0136 | 0.0112 | -0.0066| 0.0379 |
| B19  | H5      | 0.0114  | 0.0184  | 0.0109  | -0.0098 | 0.0112  | 0.0113  | 0.0645 | 0.0224 | 0.0184 | -0.0098| 0.0645 |
| B19  | H10     | 0.0144  | 0.0539  | 0.0163  | -0.0334 | -0.0027 | -0.0016 | 0.0527 | 0.0339 | 0.0256 | -0.0334| 0.0539 |
| B19  | H15     | 0.0238  | 0.0477  | 0.0222  | -0.0346 | -0.0013 | -0.0118 | 0.0439 | 0.0472 | 0.0260 | -0.0346| 0.0477 |
| B19  | H20     | 0.0180  | 0.0599  | 0.0112  | -0.0408 | 0.0033  | -0.0092 | 0.0423 | 0.0528 | 0.0291 | -0.0408| 0.0599 |
| B20  | H3      | 0.0114  | 0.0371  | 0.0154  | -0.0108 | 0.0146  | 0.0349  | 0.0160 |-0.0108 | 0.0371 |
| B20  | H5      | 0.0300  | 0.0448  | 0.0063  | -0.0189 | 0.0273  | 0.0379  | 0.0215 |-0.0189 | 0.0448 |
| B20  | H10     | 0.0390  | 0.0491  | 0.0019  | -0.0166 | 0.0411  | 0.0364  | 0.0239 |-0.0166 | 0.0491 |
| B20  | H15     | 0.0411  | 0.0445  | 0.0001  | -0.0091 | 0.0340  | 0.0559  | 0.0238 |-0.0091 | 0.0559 |
| B20  | H20     | 0.0406  | 0.0409  | -0.0019 | -0.0171 | 0.0460  | 0.0565  | 0.0270 |-0.0171 | 0.0565 |
| B21  | H3      | 0.0015  | 0.0338  | 0.0223  | -0.0010 | 0.0096  | 0.0067  | 0.0122 |-0.0010 | 0.0338 |
| B21  | H5      | 0.0021  | 0.0486  | 0.0228  | -0.0059 | 0.0267  | 0.0208  | 0.0176 |-0.0059 | 0.0486 |
| B21  | H10     | 0.0009  | 0.0478  | 0.0299  | -0.0083 | 0.0372  | 0.0260  | 0.0197 |-0.0083 | 0.0478 |
| B21  | H15     | 0.0103  | 0.0764  | 0.0323  | 0.0029  | -0.0011 | 0.0036  | 0.0272 |-0.0011 | 0.0764 |
| B21  | H20     | -0.0054 | 0.0330  | 0.0392  | -0.0064 | 0.0468  | 0.0111  | 0.0211 |-0.0064 | 0.0468 |
| B22  | H3      | 0.0069  | 0.0337  | 0.0160  | -0.0016 | 0.0098  | 0.0067  | 0.0110 |-0.0016 | 0.0337 |
| B22  | H5      | 0.0113  | 0.0450  | 0.0289  | -0.0080 | 0.0180  | 0.0240  | 0.0162 |-0.0080 | 0.0450 |
| B22  | H10     | -0.0072 | 0.0492  | 0.0272  | -0.0069 | 0.0316  | 0.0224  | 0.0204 |-0.0072 | 0.0492 |
| B22  | H15     | 0.0103  | 0.0764  | 0.0323  | 0.0029  | -0.0011 | 0.0036  | 0.0272 |-0.0011 | 0.0764 |
| B22  | H20     | -0.0030 | 0.0192  | 0.0586  | -0.0066 | 0.0456  | 0.0101  | 0.0241 |-0.0066 | 0.0586 |
| B25  | H3      | 0.0095  | 0.0349  | 0.0168  | -0.0130 | 0.0139  | 0.0402  | 0.0174 |-0.0130 | 0.0402 |
| B25  | H5      | 0.0287  | 0.0508  | 0.0093  | -0.0218 | 0.0275  | 0.0395  | 0.0234 |-0.0218 | 0.0508 |
| B25  | H10     | 0.0398  | 0.0493  | 0.0026  | -0.0119 | 0.0383  | 0.0490  | 0.0237 |-0.0119 | 0.0493 |
| B25  | H15     | 0.0440  | 0.0404  | 0.0027  | -0.0139 | 0.0348  | 0.0479  | 0.0232 |-0.0139 | 0.0479 |
| B25  | H20     | 0.0357  | 0.0312  | 0.0076  | -0.0114 | 0.0485  | 0.0526  | 0.0226 |-0.0114 | 0.0526 |
| B26  | H3      | 0.0085  | 0.0194  | 0.0164  | -0.0021 | 0.0117  | 0.0056  | 0.0071 |-0.0021 | 0.0194 |
| B26  | H5      | 0.0050  | 0.0490  | 0.0276  | -0.0041 | 0.0190  | 0.0168  | 0.0169 |-0.0041 | 0.0490 |
| B26  | H10     | -0.0070 | 0.0316  | 0.0373  | -0.0019 | 0.0291  | 0.0264  | 0.0171 |-0.0070 | 0.0373 |
| B26  | H15     | -0.0132 | 0.0395  | 0.0499  | -0.0039 | 0.0368  | 0.0090  | 0.0236 |-0.0132 | 0.0499 |
| B26  | H20     | -0.0067 | 0.0212  | 0.0437  | 0.0011  | 0.0384  | 0.0124  | 0.0183 |-0.0067 | 0.0437 |
| B27  | H3      | -0.0007 | 0.0329  | 0.0195  | -0.0038 | 0.0078  | 0.0086  | 0.0124 |-0.0038 | 0.0329 |
| B27  | H5      | 0.0052  | 0.0507  | 0.0250  | -0.0022 | 0.0266  | 0.0196  | 0.0169 |-0.0022 | 0.0507 |
| B27  | H10     | -0.0046 | 0.0318  | 0.0288  | -0.0115 | 0.0258  | 0.0148  | 0.0167 |-0.0115 | 0.0318 |
| B27  | H15     | -0.0094 | 0.0311  | 0.0367  | -0.0013 | 0.0316  | 0.0164  | 0.0175 |-0.0094 | 0.0367 |
| B27  | H20     | -0.0053 | 0.0214  | 0.0442  | -0.0055 | 0.0362  | 0.0122  | 0.0189 |-0.0055 | 0.0442 |
| B30  | H3      | 0.0133  | 0.0067  | 0.0155  | 0.0096  | 0.0178  | 0.0626  | 0.0190 | 0.0067 | 0.0626 |
| B30  | H5      | 0.0031  | 0.0151  | -0.0006 | -0.0070 | 0.0107  | 0.0580  | 0.0213 |-0.0070 | 0.0580 |
| B30  | H10     | 0.0559  | 0.0933  | -0.0241 | 0.0095  | 0.0077  | 0.0185  | 0.0379 |-0.0241 | 0.0933 |
| B30  | H15     | 0.0013  | 0.0787  | -0.0146 | -0.0034 | -0.0024 | 0.0016  | 0.0311 |-0.0146 | 0.0787 |
| B30  | H20     | -0.0357 | 0.0508  | -0.0380 | 0.0422  | -0.0192 | 0.0324  | 0.0372 |-0.0380 | 0.0508 |
| B31  | H3      | 0.0008  | 0.0408  | 0.0200  | -0.0144 | 0.0158  | 0.0312  | 0.0183 |-0.0144 | 0.0408 |
| B31  | H5      | 0.0229  | 0.0348  | 0.0230  | -0.0257 | 0.0230  | 0.0226  | 0.0195 |-0.0257 | 0.0348 |
| B31  | H10     | 0.0342  | 0.0200  | 0.0205  | -0.0321 | 0.0179  | 0.0204  | 0.0211 |-0.0321 | 0.0342 |
| B31  | H15     | 0.0327  | 0.0234  | 0.0173  | -0.0391 | 0.0229  | 0.0257  | 0.0241 |-0.0391 | 0.0327 |
| B31  | H20     | 0.0456  | 0.0064  | 0.0214  | -0.0378 | 0.0282  | 0.0143  | 0.0258 |-0.0378 | 0.0456 |
| B32  | H3      | 0.0055  | 0.0348  | 0.0125  | -0.0119 | 0.0139  | 0.0351  | 0.0164 |-0.0119 | 0.0351 |
| B32  | H5      | 0.0250  | 0.0485  | 0.0083  | -0.0195 | 0.0278  | 0.0379  | 0.0220 |-0.0195 | 0.0485 |
| B32  | H10     | 0.0452  | 0.0434  | -0.0086 | -0.0121 | 0.0333  | 0.0503  | 0.0257 |-0.0121 | 0.0503 |
| B32  | H15     | 0.0448  | 0.0436  | -0.0070 | -0.0151 | 0.0342  | 0.0526  | 0.0265 |-0.0151 | 0.0526 |
| B32  | H20     | 0.0467  | 0.0379  | -0.0003 | -0.0176 | 0.0456  | 0.0377  | 0.0248 |-0.0176 | 0.0467 |
| B33  | H3      | 0.0007  | 0.0341  | 0.0203  | -0.0162 | 0.0093  | 0.0352  | 0.0183 |-0.0162 | 0.0352 |
| B33  | H5      | 0.0171  | 0.0349  | 0.0216  | -0.0218 | 0.0241  | 0.0347  | 0.0192 |-0.0218 | 0.0349 |
| B33  | H10     | 0.0199  | 0.0231  | 0.0113  | -0.0220 | 0.0239  | 0.0308  | 0.0173 |-0.0220 | 0.0308 |
| B33  | H15     | 0.0263  | 0.0089  | 0.0076  | -0.0277 | 0.0272  | 0.0268  | 0.0194 |-0.0277 | 0.0272 |
| B33  | H20     | 0.0173  | 0.0010  | 0.0096  | -0.0280 | 0.0343  | 0.0302  | 0.0207 |-0.0280 | 0.0343 |
| B34  | H3      | -0.0022 | 0.0405  | 0.0238  | -0.0161 | 0.0135  | 0.0307  | 0.0193 |-0.0161 | 0.0405 |
| B34  | H5      | 0.0171  | 0.0347  | 0.0198  | -0.0186 | 0.0165  | 0.0335  | 0.0176 |-0.0186 | 0.0347 |
| B34  | H10     | 0.0310  | 0.0254  | 0.0057  | -0.0167 | 0.0340  | 0.0326  | 0.0185 |-0.0167 | 0.0340 |
| B34  | H15     | 0.0344  | 0.0090  | 0.0002  | -0.0164 | 0.0273  | 0.0333  | 0.0187 |-0.0164 | 0.0344 |
| B34  | H20     | 0.0145  | 0.0001  | -0.0002 | -0.0261 | 0.0409  | 0.0321  | 0.0222 |-0.0261 | 0.0409 |
| B35  | H3      | 0.0663  | 0.0393  | 0.0093  | 0.0180  | 0.0159  | 0.0210  | 0.0193 | 0.0093 | 0.0663 |
| B35  | H5      | 0.0605  | 0.0493  | -0.0084 | -0.0041 | 0.0127  | 0.0273  | 0.0256 |-0.0084 | 0.0605 |
| B35  | H10     | -0.0110 | 0.0629  | -0.0024 | -0.0181 | -0.0040 | 0.0467  | 0.0308 |-0.0181 | 0.0629 |
| B35  | H15     | 0.0571  | 0.0330  | -0.0370 | -0.0387 | 0.0250  | 0.0098  | 0.0354 |-0.0387 | 0.0571 |
| B35  | H20     | 0.0149  | 0.0632  | -0.0343 | -0.0254 | -0.0027 | 0.0175  | 0.0321 |-0.0343 | 0.0632 |
| B36  | H3      | 0.0627  | 0.0355  | 0.0122  | 0.0177  | 0.0129  | 0.0250  | 0.0176 | 0.0122 | 0.0627 |
| B36  | H5      | 0.0509  | 0.0511  | 0.0069  | 0.0006  | 0.0141  | 0.0243  | 0.0200 | 0.0006 | 0.0511 |
| B36  | H10     | 0.0469  | 0.0288  | -0.0284 | -0.0418 | 0.0257  | 0.0157  | 0.0319 |-0.0418 | 0.0469 |
| B36  | H15     | 0.0479  | 0.0398  | -0.0245 | -0.0529 | 0.0252  | 0.0080  | 0.0357 |-0.0529 | 0.0479 |
| B36  | H20     | 0.0179  | 0.0797  | -0.0372 | -0.0408 | 0.0420  | -0.0204 | 0.0440 |-0.0408 | 0.0797 |
| B37  | H3      | 0.0226  | 0.0432  | 0.0034  | 0.0112  | 0.0080  | 0.0310  | 0.0199 | 0.0034 | 0.0432 |
| B37  | H5      | 0.0192  | 0.0395  | 0.0061  | 0.0042  | 0.0109  | 0.0283  | 0.0180 | 0.0042 | 0.0395 |
| B37  | H10     | 0.0215  | 0.0240  | -0.0144 | 0.0012  | 0.0147  | 0.0226  | 0.0116 |-0.0144 | 0.0240 |
| B37  | H15     | 0.0115  | 0.0189  | -0.0070 | -0.0019 | 0.0084  | 0.0213  | 0.0085 |-0.0070 | 0.0213 |
| B37  | H20     | 0.0086  | 0.0163  | -0.0088 | -0.0126 | 0.0048  | 0.0130  | 0.0035 |-0.0126 | 0.0163 |
| B38  | H3      | 0.0057  | 0.0308  | 0.0112  | -0.0046 | 0.0221  | 0.0291  | 0.0128 |-0.0046 | 0.0308 |
| B38  | H5      | 0.0224  | 0.0576  | 0.0035  | -0.0184 | 0.0308  | 0.0414  | 0.0248 |-0.0184 | 0.0576 |
| B38  | H10     | 0.0214  | 0.0433  | 0.0051  | -0.0052 | 0.0440  | 0.0429  | 0.0197 |-0.0052 | 0.0440 |
| B38  | H15     | 0.0309  | 0.0331  | 0.0067  | 0.0004  | 0.0480  | 0.0338  | 0.0166 | 0.0004 | 0.0480 |
| B38  | H20     | 0.0300  | 0.0231  | 0.0106  | -0.0105 | 0.0640  | 0.0341  | 0.0227 |-0.0105 | 0.0640 |
| B39  | H3      | 0.0124  | 0.0067  | 0.0174  | -0.0272 | 0.0044  | -0.0051 | 0.0146 |-0.0272 | 0.0174 |
| B39  | H5      | 0.0142  | 0.0257  | 0.0251  | -0.0125 | 0.0098  | 0.0026  | 0.0132 |-0.0125 | 0.0257 |
| B39  | H10     | 0.0248  | 0.0373  | 0.0346  | -0.0284 | 0.0113  | 0.0075  | 0.0221 |-0.0284 | 0.0373 |
| B39  | H15     | 0.0148  | 0.0466  | 0.0560  | -0.0230 | 0.0183  | 0.0052  | 0.0262 |-0.0230 | 0.0560 |
| B39  | H20     | 0.0255  | 0.0387  | 0.0506  | -0.0350 | 0.0176  | 0.0096  | 0.0272 |-0.0350 | 0.0506 |
| B40  | H3      | 0.0062  | 0.0256  | 0.0229  | 0.0025  | 0.0158  | 0.0149  | 0.0083 | 0.0025 | 0.0256 |
| B40  | H5      | 0.0104  | 0.0453  | 0.0152  | -0.0047 | 0.0164  | 0.0249  | 0.0152 |-0.0047 | 0.0453 |
| B40  | H10     | -0.0070 | 0.0391  | 0.0362  | 0.0036  | 0.0261  | 0.0339  | 0.0175 |-0.0070 | 0.0391 |
| B40  | H15     | -0.0133 | 0.0269  | 0.0449  | 0.0115  | 0.0210  | 0.0122  | 0.0176 |-0.0133 | 0.0449 |
| B40  | H20     | -0.0112 | 0.0149  | 0.0431  | 0.0061  | 0.0310  | 0.0186  | 0.0173 |-0.0112 | 0.0431 |
| B41  | H3      | 0.0145  | 0.0403  | 0.0177  | -0.0051 | 0.0219  | 0.0427  | 0.0162 |-0.0051 | 0.0427 |
| B41  | H5      | 0.0315  | 0.0459  | 0.0055  | -0.0097 | 0.0301  | 0.0417  | 0.0199 |-0.0097 | 0.0459 |
| B41  | H10     | 0.0340  | 0.0329  | 0.0031  | 0.0047  | 0.0406  | 0.0437  | 0.0164 | 0.0031 | 0.0437 |
| B41  | H15     | 0.0306  | 0.0319  | 0.0049  | 0.0160  | 0.0457  | 0.0472  | 0.0151 | 0.0049 | 0.0472 |
| B41  | H20     | 0.0255  | 0.0243  | 0.0024  | 0.0242  | 0.0469  | 0.0443  | 0.0148 | 0.0024 | 0.0469 |
| B42  | H3      | 0.0175  | 0.0448  | 0.0156  | -0.0093 | 0.0188  | 0.0366  | 0.0172 |-0.0093 | 0.0448 |
| B42  | H5      | 0.0338  | 0.0435  | 0.0095  | -0.0119 | 0.0313  | 0.0327  | 0.0187 |-0.0119 | 0.0435 |
| B42  | H10     | 0.0360  | 0.0379  | 0.0028  | 0.0049  | 0.0404  | 0.0472  | 0.0176 | 0.0028 | 0.0472 |
| B42  | H15     | 0.0297  | 0.0220  | -0.0032 | 0.0203  | 0.0391  | 0.0467  | 0.0159 |-0.0032 | 0.0467 |
| B42  | H20     | 0.0327  | 0.0328  | 0.0009  | 0.0136  | 0.0383  | 0.0442  | 0.0150 | 0.0009 | 0.0442 |

## 1.4 Comparatif Backtest Stratégies — Global Rank

> ✅ **Régénéré avec le meilleur horizon** — tous les batches utilisent leur propre meilleur horizon (H10 pour 10/11, H20 pour B2).
> V1 = meilleur horizon seul, V2 = +H5 rising, V3 = +H5 < 0.35, V4 = top N horizons par score composite (config: `backtest.min_rising_horizons`, défaut 2, rapports générés avec N=3).

| Test | Meilleur H | V1 | V2 (+H5 rising) | V3 (+H5 < 0.35) | V4 (top 3 ↑) | Horizons V4 |
|:-----|:-----------|:---|:----------------|:-----------------|:-------------|:------------|
| B0   | H10        | 🏆 | -7.7%           | -29.4%           | -20.7%       | H10,H5,H20 |
| B1   | H10        | 🏆 | -7.7%           | -29.4%           | -20.7%       | H10,H5,H20 |
| B2   | H20        | 🏆 | -8.2%           | -36.1%           | -26.9%       | H20,H10,H15 |
| B3   | H10        | 🏆 | -7.1%           | -24.8%           | -21.0%       | H10,H15,H20 |
| B4   | H10        | 🏆 | -7.1%           | -24.8%           | -21.0%       | H10,H15,H20 |
| B5   | H10        | 🏆 | -7.1%           | -24.8%           | -21.0%       | H10,H15,H20 |
| B6   | H10        | 🏆 | -7.1%           | -24.8%           | -21.0%       | H10,H15,H20 |
| B7   | H10        | 🏆 | -7.1%           | -24.8%           | -21.0%       | H10,H15,H20 |
| B8   | H10        | 🏆 | -7.1%           | -24.8%           | -21.0%       | H10,H15,H20 |
| B9   | H10        | 🏆 | -10.3%          | -42.2%           | -22.0%       | H10,H20,H15 |
| B10  | H10        | 🏆 | -1.9% 🔥        | -25.1%           | -20.1%       | H10,H5,H20 |
| B11  | H10        | 🏆 | -7.1%           | -24.8%           | -21.0%       | H10,H15,H20 |
| B12  | H15        | 🏆 | -2.5% 🔥        | -30.4%           | -19.0%       | H15,H10,H5 |
| B13  | H10        | 🏆 | -16.9% ❌       | -47.1%           | -17.7%       | H10,H5,H20 |
| B14  | H10        | 🏆 | **-0.1%** 🔥🔥  | -25.8%           | -12.4%       | H10,H20,H15 |
| B15  | H10        | 🏆 | **-0.1%** 🔥🔥  | -25.8%           | -12.4%       | H10,H20,H15 |
| B16  | H10        | 🏆 | **-0.1%** 🔥🔥  | -25.8%           | -12.4%       | H10,H20,H15 |
| B17  | H10        | 🏆 | **-0.1%** 🔥🔥  | -25.8%           | -12.4%       | H10,H20,H15 |
| B18  | H5         | 🏆 | N/A (best=H5)    | N/A              | -3.8%        | H5,H3,H20   |
| B19  | H5         | 🏆 | N/A (best=H5)    | N/A              | -15.3%       | H5,H10,H20  |
| **B20** | **H15** | 🏆 | **N/A (YetiRank)** | N/A              | **-10.1%**   | H15,H5,H10  |
| B21  | H10        | 🏆 | -3.0%           | -19.6%           | -15.8%       | H10,H5,H15  |
| B22  | H5         | 🏆 | N/A (H5 seul)    | N/A              | -17.0%       | H5,H15,H20  |
| **B25** | **H10** | 🏆 | **-2.6%** 🔥     | -46.4%           | -18.4%       | H10,H20,H15 |
| B26  | H5         | 🏆 | N/A (H5 seul)    | N/A              | -17.3%       | H5,H10,H20  |
| B27  | H5         | 🏆 | N/A (H5 seul)    | N/A              | -19.1%       | H5,H15,H20  |
| B30  | H10        | 🏆 | -1.1%           | -31.1%           | -15.2%       | H3,H10,H5   |
| B31  | H5         | 🏆 | N/A (H5 seul)    | N/A              | -32.4%       | H5,H3,H10   |
| B32  | H10        | 🏆 | -8.0%           | -52.5%           | -17.7%       | H20,H10,H15 |
| B33  | H5         | 🏆 | N/A (H5 seul)    | N/A              | -24.6%       | H5,H10,H3   |
| B34  | H10        | 🏆 | -13.4%          | -28.8%           | -21.6%       | H10,H5,H15  |
| B35  | H3         | 🏆 | -9.7%           | -79.9%           | -37.3%       | H3,H5,H10   |
| B36  | H3         | 🏆 | -15.0%          | -73.1%           | -18.4%       | H3,H5,H10   |
| B37  | H3         | 🏆 | -13.3%          | -74.3%           | -26.3%       | H3,H5,H10   |
| B38  | H15        | 🏆 | -10.8%          | -42.3%           | -25.2%       | H15,H10,H20 |
| B39  | H15        | 🏆 | -8.8%           | -40.8%           | -23.9%       | H15,H20,H10 |
| B40  | H10        | 🏆 | -10.6%          | -34.4%           | -20.6%       | H10,H3,H5   |
| B41  | H15        | 🏆 | -11.6%          | -55.3%           | -26.7%       | H15,H20,H10 |
| B42  | H20        | 🏆 | -9.7%           | -29.6%           | -24.8%       | H20,H10,H15 |

## 1.5 🏆 Champion par horizon — Meilleur IC (B0-B41)

| Horizon | 🥇 Batch | IC Rank | IR | Flags | Config |
|:--------|:--------|:----:|:--:|:------|:-------|
| **H3** | **B41** | **0.0220** | 1.36 | short + SPY + CAPM + volume | YetiRank + vol |
| **H5** | **B41** | **0.0242** | 1.22 | short + SPY + CAPM + volume | YetiRank + vol |
| **H10** | **B42** | **0.0282** | 1.60 | short + SPY + volume | YetiRank + vol (sans CAPM) |
| **H15** | **B41** | **0.0294** | 1.94 | short + SPY + CAPM + volume | YetiRank + vol |
| **H20** | **B41** | **0.0279** | 1.89 | short + SPY + CAPM + volume | YetiRank + vol |

> 🏆 **B41 (B25 + volume features) = champion H3/H5/H15/H20 (IC 0.0260, IR 1.55).** Sur H10, B42 IC 0.0282 > B41 0.0265 à IR quasi égal (1.60 vs 1.61) → B42 (B20 + volume, sans CAPM) prend H10.
> Stratégie optimale : YetiRank + volume everywhere ; CAPM sur H3/H5/H15/H20, pas sur H10.
> **B31 (fondamentaux + YetiRank) n'améliore aucun horizon** (max H5 = 0.0168, loin de B25 0.0223).
> **B32 (score components + YetiRank) n'améliore aucun horizon** (max H15 = 0.0255 < B20 0.0278).
> **B33 (cross-sectional + YetiRank) n'améliore aucun horizon** (max H5 = 0.0184).
> **B34 (screener + YetiRank) n'améliore aucun horizon** (max H10 = 0.0187).
> **B35 (B25 sur 196 symboles) : H3 = 0.0283 (IR 1.46) mais sur univers réduit — non comparable aux champions 400 symboles.** Sur les horizons comparables, aucun gain.
> **B36 (B20 sur 196 symboles) : H3/H5 records sur petit univers (0.0277/0.0246, IR 1.57/1.23), non comparables. Aucun horizon 400 symboles amélioré.**
> **B37 (B25 sur 393 symboles swing score) : H3 = 0.0199 > B20 (0.0171) mais sur univers non-liquide — non comparable. Aucun horizon 400 symboles amélioré. H20 mort (0.0035, decile spread −0.0003). L'univers « swing score » est toxique pour le Global Ranking.**
> **B38 (B25 sur 300 symboles parmi les 400) : aucun horizon champion — H15 0.0255 < B20 0.0278, H10 0.0253 < B25 0.0279. Mais IC IR 1.54 sur H15 (record H15). Non comparable en championnat (univers 300 ≠ 400).**
> **B39 (XGBoost rank:ndcg) n'améliore aucun horizon** — max H15 0.0197 < B20 0.0278 ; H10 0.0145 < B25 0.0279. Verdict P3-3 : ❌ clos.
> **B40 (B4 + volume features) n'améliore aucun horizon** — H10 0.0220 < B25 0.0279 ; H3 0.0146 < B20 0.0171. Mais IR H3 1.77 = record. Verdict P3-5 (B40) : ❌ vs B4 (−12 %), le décisif attend B41.
> **B41 (B25 + volume features) = NOUVEAU CHAMPION 4/5 horizons** (H3/H5/H15/H20). ⚠️ In-sample : OOS 2025 + backtest obligatoires avant promotion.
> **B42 (B20 + volume features, sans CAPM ni include-factors) = champion H10** — IC 0.0282 (record H10 historique, +1% vs B25 0.0279, +6.4% vs B41 0.0265) à IR quasi égal (1.60 vs 1.61). Sur H10, le CAPM n'aide pas quand le volume est présent.

---

# PARTIE 2 — 🔵 Per-Sector

> **B39** : per-sector = même config que B25 (lgbm + catboost, flags identiques) — le backend xgboost ne concerne que le Global Ranking. Toutes les sections 2.1-2.9 sont renseignées.
> **B40** : per-sector renseigné (2.1-2.9) — le flag volume n'est pas propagé au per-sector de ce run (identique au pattern B4).
> **B41** : per-sector AVEC volume features (flag propagé à `trainer_sector`) → léger changement vs B25 (lightgbm 7 / catboost 4), sections 2.1-2.9 renseignées.

## 2.1 Comparatif Métriques par Horizon (WF)

| Test | Horizon | F1 macro | F1 short | F1 long | Dir Acc |
|:-----|:--------|---------:|---------:|--------:|--------:|
| B0   | H3      | 0.331    | 0.490    | 0.504   | 0.5023  |
| B0   | H5      | 0.329    | 0.476    | 0.511   | 0.5005  |
| B0   | H10     | 0.329    | 0.477    | 0.510   | 0.5025  |
| B0   | H15     | 0.328    | 0.474    | 0.510   | 0.5004  |
| B0   | H20     | 0.327    | 0.474    | 0.506   | 0.4986  |
| B1   | H3      | 0.330    | 0.489    | 0.503   | 0.5019  |
| B1   | H5      | 0.329    | 0.478    | 0.509   | 0.5007  |
| B1   | H10     | 0.328    | 0.477    | 0.508   | 0.5011  |
| B1   | H15     | 0.327    | 0.476    | 0.506   | 0.4995  |
| B1   | H20     | 0.327    | 0.473    | 0.508   | 0.4993  |
| B2   | H3      | 0.330    | 0.490    | 0.500   | 0.5010  |
| B2   | H5      | 0.329    | 0.478    | 0.509   | 0.5005  |
| B2   | H10     | 0.329    | 0.478    | 0.510   | 0.5023  |
| B2   | H15     | 0.328    | 0.475    | 0.510   | 0.5013  |
| B2   | H20     | 0.326    | 0.474    | 0.506   | 0.4983  |
| B3   | H3      | 0.331    | 0.489    | 0.504   | 0.5020  |
| B3   | H5      | 0.329    | 0.478    | 0.509   | 0.5007  |
| B3   | H10     | 0.328    | 0.474    | 0.510   | 0.5007  |
| B3   | H15     | 0.327    | 0.475    | 0.506   | 0.4990  |
| B3   | H20     | 0.326    | 0.471    | 0.507   | 0.4978  |
| B4   | H3      | 0.331    | 0.489    | 0.503   | 0.5020  |
| B4   | H5      | 0.330    | 0.475    | 0.514   | 0.5015  |
| B4   | H10     | 0.328    | 0.473    | 0.512   | 0.5018  |
| B4   | H15     | 0.329    | 0.474    | 0.512   | 0.5022  |
| B4   | H20     | 0.328    | 0.476    | 0.508   | 0.5010  |
| B5   | H3      | 0.331    | 0.491    | 0.501   | 0.5019  |
| B5   | H5      | 0.328    | 0.475    | 0.510   | 0.5000  |
| B5   | H10     | 0.328    | 0.475    | 0.510   | 0.5015  |
| B5   | H15     | 0.329    | 0.475    | 0.510   | 0.5022  |
| B5   | H20     | 0.328    | 0.477    | 0.506   | 0.5005  |
| B6   | H3      | 0.331    | 0.494    | 0.500   | 0.5029  |
| B6   | H5      | 0.329    | 0.475    | 0.512   | 0.5011  |
| B6   | H10     | 0.329    | 0.475    | 0.511   | 0.5021  |
| B6   | H15     | 0.329    | 0.475    | 0.512   | 0.5029  |
| B6   | H20     | 0.327    | 0.475    | 0.507   | 0.4999  |
| B7   | H3      | 0.331    | 0.493    | 0.499   | 0.5021  |
| B7   | H5      | 0.329    | 0.476    | 0.511   | 0.5012  |
| B7   | H10     | 0.328    | 0.472    | 0.511   | 0.5011  |
| B7   | H15     | 0.328    | 0.475    | 0.508   | 0.5008  |
| B7   | H20     | 0.327    | 0.474    | 0.507   | 0.5001  |
| B8   | H3      | 0.328    | 0.484    | 0.501   | 0.5011  |
| B8   | H5      | 0.328    | 0.472    | 0.511   | 0.5010  |
| B8   | H10     | 0.328    | 0.474    | 0.509   | 0.5006  |
| B8   | H15     | 0.328    | 0.476    | 0.508   | 0.5025  |
| B8   | H20     | 0.326    | 0.477    | 0.502   | 0.4996  |
| B9   | H3      | 0.331    | 0.494    | 0.498   | 0.5012  |
| B9   | H5      | 0.330    | 0.483    | 0.507   | 0.5013  |
| B9   | H10     | 0.328    | 0.482    | 0.501   | 0.5007  |
| B9   | H15     | 0.327    | 0.480    | 0.502   | 0.5020  |
| B9   | H20     | 0.327    | 0.481    | 0.500   | 0.5012  |
| B10  | H3      | 0.330    | 0.490    | 0.501   | 0.5018  |
| B10  | H5      | 0.329    | 0.475    | 0.513   | 0.5018  |
| B10  | H10     | 0.328    | 0.473    | 0.511   | 0.5010  |
| B10  | H15     | 0.328    | 0.473    | 0.510   | 0.5012  |
| B10  | H20     | 0.327    | 0.475    | 0.507   | 0.5001  |
| B11  | H3      | 0.331    | 0.494    | 0.498   | 0.5018  |
| B11  | H5      | 0.328    | 0.473    | 0.510   | 0.4993  |
| B11  | H10     | 0.328    | 0.472    | 0.513   | 0.5018  |
| B11  | H15     | 0.329    | 0.479    | 0.510   | 0.5039  |
| B11  | H20     | 0.327    | 0.472    | 0.507   | 0.4992  |
| B12  | H3      | 0.330    | 0.490    | 0.500   | 0.5010  |
| B12  | H5      | 0.329    | 0.475    | 0.512   | 0.5009  |
| B12  | H10     | 0.329    | 0.476    | 0.510   | 0.5018  |
| B12  | H15     | 0.329    | 0.475    | 0.513   | 0.5026  |
| B12  | H20     | 0.327    | 0.473    | 0.508   | 0.5001  |
| B13  | H3      | 0.331    | 0.494    | 0.499   | 0.5021  |
| B13  | H5      | 0.329    | 0.481    | 0.505   | 0.5004  |
| B13  | H10     | 0.329    | 0.489    | 0.499   | 0.5027  |
| B13  | H15     | 0.329    | 0.488    | 0.500   | 0.5033  |
| B13  | H20     | 0.329    | 0.487    | 0.499   | 0.5027  |
| B14  | H3      | 0.330    | 0.488    | 0.503   | 0.5014  |
| B14  | H5      | 0.329    | 0.472    | 0.514   | 0.5007  |
| B14  | H10     | 0.328    | 0.473    | 0.512   | 0.5020  |
| B14  | H15     | 0.329    | 0.474    | 0.513   | 0.5027  |
| B14  | H20     | 0.327    | 0.473    | 0.509   | 0.5002  |
| B15  | H3      | 0.331    | 0.489    | 0.503   | 0.5020  |
| B15  | H5      | 0.329    | 0.484    | 0.503   | 0.5002  |
| B15  | H10     | 0.329    | 0.484    | 0.502   | 0.5002  |
| B15  | H15     | 0.327    | 0.479    | 0.501   | 0.4984  |
| B15  | H20     | 0.327    | 0.480    | 0.500   | 0.4975  |
| B16  | H3      | 0.330    | 0.490    | 0.500   | 0.4978  |
| B16  | H5      | 0.329    | 0.484    | 0.504   | 0.4977  |
| B16  | H10     | 0.328    | 0.477    | 0.507   | 0.4964  |
| B16  | H15     | 0.328    | 0.476    | 0.507   | 0.4974  |
| B16  | H20     | 0.327    | 0.474    | 0.506   | 0.4959  |
| B17  | H3      | 0.000    | 0.000    | 0.000   | 0.0002  |
| B17  | H5      | 0.348    | 0.143    | 0.140   | 0.6093  |
| B17  | H10     | 0.338    | 0.193    | 0.181   | 0.4824  |
| B17  | H15     | 0.328    | 0.216    | 0.208   | 0.4178  |
| B17  | H20     | 0.327    | 0.241    | 0.231   | 0.3874  |
| B18  | H3      | 0.330    | 0.496    | 0.493   | 0.4996  |
| B18  | H5      | 0.328    | 0.490    | 0.493   | 0.4965  |
| B18  | H10     | 0.327    | 0.484    | 0.498   | 0.4958  |
| B18  | H15     | 0.327    | 0.483    | 0.498   | 0.4961  |
| B18  | H20     | 0.328    | 0.481    | 0.502   | 0.4973  |
| B19  | H3      | 0.330    | 0.498    | 0.494   | 0.4998  |
| B19  | H5      | 0.329    | 0.490    | 0.496   | 0.4979  |
| B19  | H10     | 0.328    | 0.488    | 0.497   | 0.4975  |
| B19  | H15     | 0.328    | 0.485    | 0.499   | 0.4981  |
| B19  | H20     | 0.329    | 0.486    | 0.500   | 0.4991  |
| B20  | H3      | 0.331    | 0.489    | 0.503   | 0.5020  |
| B20  | H5      | 0.330    | 0.475    | 0.514   | 0.5017  |
| B20  | H10     | 0.328    | 0.473    | 0.511   | 0.5014  |
| B20  | H15     | 0.329    | 0.474    | 0.512   | 0.5019  |
| B20  | H20     | 0.327    | 0.474    | 0.508   | 0.5003  |
| B21  | H3      | 0.331    | 0.489    | 0.503   | 0.5020  |
| B21  | H5      | 0.330    | 0.475    | 0.514   | 0.5017  |
| B21  | H10     | 0.328    | 0.473    | 0.511   | 0.5014  |
| B21  | H15     | 0.329    | 0.474    | 0.512   | 0.5019  |
| B21  | H20     | 0.327    | 0.474    | 0.508   | 0.5003  |
| B22  | H3      | 0.331    | 0.489    | 0.503   | 0.5020  |
| B22  | H5      | 0.330    | 0.475    | 0.514   | 0.5017  |
| B22  | H10     | 0.328    | 0.473    | 0.511   | 0.5014  |
| B22  | H15     | 0.329    | 0.474    | 0.512   | 0.5019  |
| B22  | H20     | 0.327    | 0.474    | 0.508   | 0.5003  |
| B25  | H3      | 0.330    | 0.490    | 0.500   | 0.5011  |
| B25  | H5      | 0.329    | 0.475    | 0.512   | 0.5014  |
| B25  | H10     | 0.328    | 0.473    | 0.511   | 0.5013  |
| B25  | H15     | 0.328    | 0.473    | 0.511   | 0.5015  |
| B25  | H20     | 0.328    | 0.475    | 0.508   | 0.5009  |
| B26  | H3      | 0.330    | 0.490    | 0.500   | 0.5011  |
| B26  | H5      | 0.329    | 0.475    | 0.512   | 0.5014  |
| B26  | H10     | 0.328    | 0.473    | 0.511   | 0.5013  |
| B26  | H15     | 0.328    | 0.473    | 0.511   | 0.5015  |
| B26  | H20     | 0.328    | 0.475    | 0.508   | 0.5009  |
| B27  | H3      | 0.330    | 0.490    | 0.500   | 0.5011  |
| B27  | H5      | 0.329    | 0.475    | 0.512   | 0.5014  |
| B27  | H10     | 0.328    | 0.473    | 0.511   | 0.5013  |
| B27  | H15     | 0.328    | 0.473    | 0.511   | 0.5015  |
| B27  | H20     | 0.328    | 0.475    | 0.508   | 0.5009  |
| B30  | H3      | 0.331    | 0.489    | 0.503   | 0.5020  |
| B30  | H5      | 0.330    | 0.475    | 0.514   | 0.5017  |
| B30  | H10     | 0.328    | 0.473    | 0.511   | 0.5014  |
| B30  | H15     | 0.329    | 0.474    | 0.512   | 0.5019  |
| B30  | H20     | 0.327    | 0.474    | 0.508   | 0.5003  |
| B31  | H3      | 0.331    | 0.494    | 0.498   | 0.5012  |
| B31  | H5      | 0.330    | 0.482    | 0.507   | 0.5012  |
| B31  | H10     | 0.328    | 0.483    | 0.501   | 0.5010  |
| B31  | H15     | 0.327    | 0.480    | 0.502   | 0.5020  |
| B31  | H20     | 0.326    | 0.481    | 0.498   | 0.5005  |
| B32  | H3      | 0.331    | 0.491    | 0.501   | 0.5016  |
| B32  | H5      | 0.329    | 0.475    | 0.513   | 0.5012  |
| B32  | H10     | 0.329    | 0.477    | 0.510   | 0.5024  |
| B32  | H15     | 0.329    | 0.474    | 0.512   | 0.5019  |
| B32  | H20     | 0.327    | 0.474    | 0.508   | 0.5000  |
| B33  | H3      | 0.331    | 0.493    | 0.499   | 0.5019  |
| B33  | H5      | 0.329    | 0.481    | 0.505   | 0.5005  |
| B33  | H10     | 0.330    | 0.489    | 0.499   | 0.5031  |
| B33  | H15     | 0.330    | 0.488    | 0.502   | 0.5034  |
| B33  | H20     | 0.328    | 0.486    | 0.499   | 0.5019  |
| B34  | H3      | 0.332    | 0.496    | 0.499   | 0.5029  |
| B34  | H5      | 0.329    | 0.484    | 0.503   | 0.5009  |
| B34  | H10     | 0.328    | 0.489    | 0.496   | 0.5007  |
| B34  | H15     | 0.328    | 0.488    | 0.498   | 0.5012  |
| B34  | H20     | 0.326    | 0.485    | 0.494   | 0.4985  |
| B35  | H3      | 0.326    | 0.505    | 0.472   | 0.4957  |
| B35  | H5      | 0.322    | 0.502    | 0.465   | 0.4944  |
| B35  | H10     | 0.317    | 0.492    | 0.459   | 0.4917  |
| B35  | H15     | 0.321    | 0.493    | 0.470   | 0.4956  |
| B35  | H20     | 0.314    | 0.486    | 0.454   | 0.4880  |
| B36  | H3      | 0.329    | 0.509    | 0.477   | 0.4994  |
| B36  | H5      | 0.323    | 0.502    | 0.466   | 0.4946  |
| B36  | H10     | 0.318    | 0.495    | 0.460   | 0.4931  |
| B36  | H15     | 0.321    | 0.491    | 0.471   | 0.4957  |
| B36  | H20     | 0.317    | 0.495    | 0.457   | 0.4927  |
| B37  | H3      | 0.327    | 0.495    | 0.485   | 0.4942  |
| B37  | H5      | 0.327    | 0.498    | 0.483   | 0.5008  |
| B37  | H10     | 0.321    | 0.484    | 0.479   | 0.4891  |
| B37  | H15     | 0.323    | 0.479    | 0.491   | 0.4930  |
| B37  | H20     | 0.316    | 0.459    | 0.489   | 0.4848  |
| B38  | H3      | 0.330    | 0.489    | 0.502   | 0.5012  |
| B38  | H5      | 0.331    | 0.473    | 0.519   | 0.5042  |
| B38  | H10     | 0.330    | 0.475    | 0.514   | 0.5037  |
| B38  | H15     | 0.329    | 0.474    | 0.515   | 0.5040  |
| B38  | H20     | 0.326    | 0.473    | 0.507   | 0.5016  |
| B39  | H3      | 0.330    | 0.490    | 0.500   | 0.5011  |
| B39  | H5      | 0.329    | 0.475    | 0.512   | 0.5014  |
| B39  | H10     | 0.328    | 0.473    | 0.511   | 0.5013  |
| B39  | H15     | 0.328    | 0.473    | 0.511   | 0.5015  |
| B39  | H20     | 0.328    | 0.475    | 0.508   | 0.5009  |
| B40  | H3      | 0.331    | 0.495    | 0.497   | 0.5019  |
| B40  | H5      | 0.329    | 0.479    | 0.508   | 0.5009  |
| B40  | H10     | 0.328    | 0.477    | 0.508   | 0.5014  |
| B40  | H15     | 0.329    | 0.480    | 0.506   | 0.5031  |
| B40  | H20     | 0.328    | 0.478    | 0.505   | 0.5017  |
| B41  | H3      | 0.330    | 0.491    | 0.499   | 0.5013  |
| B41  | H5      | 0.329    | 0.480    | 0.508   | 0.5012  |
| B41  | H10     | 0.329    | 0.480    | 0.506   | 0.5023  |
| B41  | H15     | 0.329    | 0.481    | 0.506   | 0.5035  |
| B41  | H20     | 0.326    | 0.477    | 0.502   | 0.4996  |
| B42  | H3      | 0.331    | 0.495    | 0.497   | 0.5019  |
| B42  | H5      | 0.329    | 0.479    | 0.508   | 0.5009  |
| B42  | H10     | 0.328    | 0.477    | 0.508   | 0.5014  |
| B42  | H15     | 0.329    | 0.480    | 0.506   | 0.5031  |
| B42  | H20     | 0.328    | 0.478    | 0.505   | 0.5017  |

## 2.2 Champions Per-Sector par modèle

| Test | catboost | lightgbm |
|:-----|---------:|---------:|
| B0   | 5        | 6        |
| B1   | 5        | 6        |
| B2   | 5        | 6        |
| B3   | 6        | 5        |
| B4   | 3        | 8        |
| B5   | 3        | 8        |
| B6   | 3        | 8        |
| B7   | 3        | 8        |
| B8   | 3        | 8        |
| B9   | 6        | 5        |
| B10  | 2        | 9        |
| B11  | 4        | 7        |
| B12  | 1        | 10       |
| B13  | 4        | 7        |
| B14  | 4        | 7        |
| B15  | 7        | 4        |
| B16  | 3        | 8        |
| B17  | 2        | 9        |
| B18  | 7        | 4        |
| B19  | 6        | 5        |
| B20  | 5        | 6        |
| B21  | 5        | 6        |
| B22  | 5        | 6        |
| B25  | 5        | 6        |
| B26  | 5        | 6        |
| B27  | 5        | 6        |
| B30  | 5        | 6        |
| B31  | 6        | 5        |
| B32  | 3        | 8        |
| B33  | 4        | 7        |
| B34  | 5        | 6        |
| B35  | 2        | 7        |
| B36  | 2        | 7        |
| B37  | 7        | 4        |
| B38  | 6        | 5        |
| B39  | 5        | 6        |
| B40  | 5        | 6        |
| B41  | 4        | 7        |
| B42  | 5        | 6        |

## 2.3 Comparatif F1 par split (WF)

| Test | model_name | split | F1 macro | F1 short | F1 long |
|:-----|:-----------|:------|---------:|---------:|--------:|
| B0   | catboost   | val   | 0.331    | 0.505    | 0.486   |
| B0   | catboost   | test  | 0.328    | 0.523    | 0.461   |
| B0   | catboost   | wf    | 0.328    | 0.477    | 0.509   |
| B0   | lightgbm   | val   | 0.331    | 0.506    | 0.486   |
| B0   | lightgbm   | test  | 0.329    | 0.515    | 0.470   |
| B0   | lightgbm   | wf    | 0.329    | 0.480    | 0.507   |
| B1   | catboost   | val   | 0.330    | 0.505    | 0.486   |
| B1   | catboost   | test  | 0.329    | 0.523    | 0.464   |
| B1   | catboost   | wf    | 0.328    | 0.476    | 0.507   |
| B1   | lightgbm   | val   | 0.331    | 0.505    | 0.486   |
| B1   | lightgbm   | test  | 0.328    | 0.514    | 0.470   |
| B1   | lightgbm   | wf    | 0.329    | 0.481    | 0.507   |
| B2   | catboost   | val   | 0.331    | 0.506    | 0.487   |
| B2   | catboost   | test  | 0.329    | 0.524    | 0.462   |
| B2   | catboost   | wf    | 0.328    | 0.477    | 0.507   |
| B2   | lightgbm   | val   | 0.331    | 0.506    | 0.487   |
| B2   | lightgbm   | test  | 0.329    | 0.513    | 0.473   |
| B2   | lightgbm   | wf    | 0.329    | 0.480    | 0.506   |
| B3   | catboost   | val   | 0.331    | 0.505    | 0.486   |
| B3   | catboost   | test  | 0.329    | 0.523    | 0.465   |
| B3   | catboost   | wf    | 0.328    | 0.476    | 0.508   |
| B3   | lightgbm   | val   | 0.331    | 0.506    | 0.487   |
| B3   | lightgbm   | test  | 0.328    | 0.515    | 0.470   |
| B3   | lightgbm   | wf    | 0.329    | 0.479    | 0.507   |
| B4   | catboost   | val   | 0.332    | 0.508    | 0.488   |
| B4   | catboost   | test  | 0.331    | 0.525    | 0.467   |
| B4   | catboost   | wf    | 0.329    | 0.476    | 0.510   |
| B4   | lightgbm   | val   | 0.330    | 0.505    | 0.485   |
| B4   | lightgbm   | test  | 0.329    | 0.513    | 0.474   |
| B4   | lightgbm   | wf    | 0.330    | 0.479    | 0.510   |
| B5   | catboost   | val   | 0.332    | 0.508    | 0.488   |
| B5   | catboost   | test  | 0.329    | 0.523    | 0.465   |
| B5   | catboost   | wf    | 0.328    | 0.477    | 0.508   |
| B5   | lightgbm   | val   | 0.332    | 0.507    | 0.488   |
| B5   | lightgbm   | test  | 0.329    | 0.513    | 0.474   |
| B5   | lightgbm   | wf    | 0.329    | 0.480    | 0.507   |
| B6   | catboost   | val   | 0.332    | 0.508    | 0.488   |
| B6   | catboost   | test  | 0.330    | 0.521    | 0.468   |
| B6   | catboost   | wf    | 0.329    | 0.477    | 0.510   |
| B6   | lightgbm   | val   | 0.331    | 0.507    | 0.487   |
| B6   | lightgbm   | test  | 0.329    | 0.510    | 0.477   |
| B6   | lightgbm   | wf    | 0.329    | 0.480    | 0.507   |
| B7   | catboost   | val   | 0.332    | 0.507    | 0.488   |
| B7   | catboost   | test  | 0.329    | 0.524    | 0.464   |
| B7   | catboost   | wf    | 0.328    | 0.477    | 0.507   |
| B7   | lightgbm   | val   | 0.331    | 0.506    | 0.487   |
| B7   | lightgbm   | test  | 0.329    | 0.514    | 0.474   |
| B7   | lightgbm   | wf    | 0.329    | 0.479    | 0.507   |
| B8   | catboost   | val   | 0.331    | 0.507    | 0.487   |
| B8   | catboost   | test  | 0.329    | 0.512    | 0.474   |
| B8   | catboost   | wf    | 0.327    | 0.471    | 0.509   |
| B8   | lightgbm   | val   | 0.331    | 0.506    | 0.487   |
| B8   | lightgbm   | test  | 0.327    | 0.495    | 0.485   |
| B8   | lightgbm   | wf    | 0.328    | 0.482    | 0.503   |
| B9   | catboost   | val   | 0.332    | 0.507    | 0.487   |
| B9   | catboost   | test  | 0.330    | 0.519    | 0.469   |
| B9   | catboost   | wf    | 0.328    | 0.482    | 0.501   |
| B9   | lightgbm   | val   | 0.333    | 0.509    | 0.490   |
| B9   | lightgbm   | test  | 0.330    | 0.513    | 0.478   |
| B9   | lightgbm   | wf    | 0.329    | 0.486    | 0.502   |
| B10  | catboost   | val   | 0.332    | 0.508    | 0.488   |
| B10  | catboost   | test  | 0.329    | 0.519    | 0.466   |
| B10  | catboost   | wf    | 0.328    | 0.475    | 0.510   |
| B10  | lightgbm   | val   | 0.331    | 0.506    | 0.487   |
| B10  | lightgbm   | test  | 0.328    | 0.510    | 0.475   |
| B10  | lightgbm   | wf    | 0.329    | 0.479    | 0.507   |
| B11  | catboost   | val   | 0.331    | 0.506    | 0.486   |
| B11  | catboost   | test  | 0.330    | 0.517    | 0.472   |
| B11  | catboost   | wf    | 0.328    | 0.476    | 0.509   |
| B11  | lightgbm   | val   | 0.330    | 0.505    | 0.486   |
| B11  | lightgbm   | test  | 0.328    | 0.507    | 0.476   |
| B11  | lightgbm   | wf    | 0.329    | 0.480    | 0.507   |
| B12  | catboost   | val   | 0.333    | 0.509    | 0.490   |
| B12  | catboost   | test  | 0.330    | 0.521    | 0.468   |
| B12  | catboost   | wf    | 0.329    | 0.476    | 0.510   |
| B12  | lightgbm   | val   | 0.331    | 0.507    | 0.487   |
| B12  | lightgbm   | test  | 0.329    | 0.511    | 0.476   |
| B12  | lightgbm   | wf    | 0.329    | 0.479    | 0.508   |
| B13  | catboost   | val   | 0.332    | 0.508    | 0.489   |
| B13  | catboost   | test  | 0.333    | 0.518    | 0.481   |
| B13  | catboost   | wf    | 0.329    | 0.485    | 0.500   |
| B13  | lightgbm   | val   | 0.332    | 0.508    | 0.489   |
| B13  | lightgbm   | test  | 0.330    | 0.506    | 0.485   |
| B13  | lightgbm   | wf    | 0.330    | 0.490    | 0.501   |
| B14  | catboost   | val   | 0.332    | 0.508    | 0.489   |
| B14  | catboost   | test  | 0.329    | 0.522    | 0.466   |
| B14  | catboost   | wf    | 0.328    | 0.473    | 0.511   |
| B14  | lightgbm   | val   | 0.332    | 0.507    | 0.488   |
| B14  | lightgbm   | test  | 0.328    | 0.509    | 0.474   |
| B14  | lightgbm   | wf    | 0.330    | 0.479    | 0.510   |
| B15  | catboost   | val   | 0.329    | 0.508    | 0.479   |
| B15  | catboost   | test  | 0.332    | 0.523    | 0.472   |
| B15  | catboost   | wf    | 0.328    | 0.483    | 0.501   |
| B15  | lightgbm   | val   | 0.330    | 0.509    | 0.480   |
| B15  | lightgbm   | test  | 0.331    | 0.515    | 0.477   |
| B15  | lightgbm   | wf    | 0.329    | 0.483    | 0.502   |
| B16  | catboost   | val   | 0.331    | 0.499    | 0.493   |
| B16  | catboost   | test  | 0.327    | 0.503    | 0.477   |
| B16  | catboost   | wf    | 0.328    | 0.479    | 0.505   |
| B16  | lightgbm   | val   | 0.330    | 0.498    | 0.492   |
| B16  | lightgbm   | test  | 0.327    | 0.497    | 0.485   |
| B16  | lightgbm   | wf    | 0.329    | 0.481    | 0.505   |
| B17  | catboost   | val   | 0.334    | 0.201    | 0.191   |
| B17  | catboost   | test  | 0.325    | 0.178    | 0.157   |
| B17  | catboost   | wf    | 0.316    | 0.166    | 0.149   |
| B17  | lightgbm   | val   | 0.335    | 0.219    | 0.225   |
| B17  | lightgbm   | test  | 0.348    | 0.206    | 0.198   |
| B17  | lightgbm   | wf    | 0.347    | 0.205    | 0.206   |
| B18  | catboost   | val   | 0.332    | 0.508    | 0.487   |
| B18  | catboost   | test  | 0.335    | 0.516    | 0.488   |
| B18  | catboost   | wf    | 0.328    | 0.488    | 0.495   |
| B18  | lightgbm   | val   | 0.331    | 0.507    | 0.485   |
| B18  | lightgbm   | test  | 0.332    | 0.515    | 0.481   |
| B18  | lightgbm   | wf    | 0.328    | 0.485    | 0.499   |
| B19  | catboost   | val   | 0.332    | 0.508    | 0.487   |
| B19  | catboost   | test  | 0.335    | 0.516    | 0.488   |
| B19  | catboost   | wf    | 0.328    | 0.489    | 0.496   |
| B19  | lightgbm   | val   | 0.331    | 0.507    | 0.485   |
| B19  | lightgbm   | test  | 0.332    | 0.515    | 0.481   |
| B19  | lightgbm   | wf    | 0.329    | 0.489    | 0.499   |
| B20  | catboost   | val   | 0.332    | 0.508    | 0.489   |
| B20  | catboost   | test  | 0.331    | 0.523    | 0.468   |
| B20  | catboost   | wf    | 0.328    | 0.475    | 0.510   |
| B20  | lightgbm   | val   | 0.331    | 0.506    | 0.486   |
| B20  | lightgbm   | test  | 0.328    | 0.511    | 0.474   |
| B20  | lightgbm   | wf    | 0.329    | 0.478    | 0.510   |
| B21  | catboost   | val   | 0.332    | 0.508    | 0.489   |
| B21  | catboost   | test  | 0.331    | 0.523    | 0.468   |
| B21  | catboost   | wf    | 0.328    | 0.475    | 0.510   |
| B21  | lightgbm   | val   | 0.331    | 0.506    | 0.486   |
| B21  | lightgbm   | test  | 0.328    | 0.511    | 0.474   |
| B21  | lightgbm   | wf    | 0.329    | 0.478    | 0.510   |
| B22  | catboost   | val   | 0.332    | 0.508    | 0.489   |
| B22  | catboost   | test  | 0.331    | 0.523    | 0.468   |
| B22  | catboost   | wf    | 0.328    | 0.475    | 0.510   |
| B22  | lightgbm   | val   | 0.331    | 0.506    | 0.486   |
| B22  | lightgbm   | test  | 0.328    | 0.511    | 0.474   |
| B22  | lightgbm   | wf    | 0.329    | 0.478    | 0.510   |
| B25  | catboost   | val   | 0.333    | 0.509    | 0.490   |
| B25  | catboost   | test  | 0.329    | 0.519    | 0.468   |
| B25  | catboost   | wf    | 0.328    | 0.475    | 0.510   |
| B25  | lightgbm   | val   | 0.332    | 0.507    | 0.488   |
| B25  | lightgbm   | test  | 0.329    | 0.510    | 0.476   |
| B25  | lightgbm   | wf    | 0.329    | 0.480    | 0.507   |
| B26  | catboost   | val   | 0.333    | 0.509    | 0.490   |
| B26  | catboost   | test  | 0.329    | 0.519    | 0.468   |
| B26  | catboost   | wf    | 0.328    | 0.475    | 0.510   |
| B26  | lightgbm   | val   | 0.332    | 0.507    | 0.488   |
| B26  | lightgbm   | test  | 0.329    | 0.510    | 0.476   |
| B26  | lightgbm   | wf    | 0.329    | 0.480    | 0.507   |
| B27  | catboost   | val   | 0.333    | 0.509    | 0.490   |
| B27  | catboost   | test  | 0.329    | 0.519    | 0.468   |
| B27  | catboost   | wf    | 0.328    | 0.475    | 0.510   |
| B27  | lightgbm   | val   | 0.332    | 0.507    | 0.488   |
| B27  | lightgbm   | test  | 0.329    | 0.510    | 0.476   |
| B27  | lightgbm   | wf    | 0.329    | 0.480    | 0.507   |
| B30  | catboost   | val   | 0.332    | 0.508    | 0.489   |
| B30  | catboost   | test  | 0.331    | 0.523    | 0.468   |
| B30  | catboost   | wf    | 0.328    | 0.475    | 0.510   |
| B30  | lightgbm   | val   | 0.331    | 0.506    | 0.486   |
| B30  | lightgbm   | test  | 0.328    | 0.511    | 0.474   |
| B30  | lightgbm   | wf    | 0.329    | 0.478    | 0.510   |
| B31  | catboost   | val   | 0.332    | 0.508    | 0.488   |
| B31  | catboost   | test  | 0.330    | 0.522    | 0.466   |
| B31  | catboost   | wf    | 0.328    | 0.482    | 0.501   |
| B31  | lightgbm   | val   | 0.333    | 0.509    | 0.489   |
| B31  | lightgbm   | test  | 0.330    | 0.513    | 0.477   |
| B31  | lightgbm   | wf    | 0.329    | 0.486    | 0.501   |
| B32  | catboost   | val   | 0.333    | 0.509    | 0.489   |
| B32  | catboost   | test  | 0.330    | 0.523    | 0.467   |
| B32  | catboost   | wf    | 0.329    | 0.477    | 0.510   |
| B32  | lightgbm   | val   | 0.331    | 0.506    | 0.486   |
| B32  | lightgbm   | test  | 0.328    | 0.511    | 0.474   |
| B32  | lightgbm   | wf    | 0.329    | 0.479    | 0.508   |
| B33  | catboost   | val   | 0.332    | 0.508    | 0.489   |
| B33  | catboost   | test  | 0.333    | 0.519    | 0.479   |
| B33  | catboost   | wf    | 0.329    | 0.485    | 0.501   |
| B33  | lightgbm   | val   | 0.332    | 0.508    | 0.489   |
| B33  | lightgbm   | test  | 0.331    | 0.507    | 0.485   |
| B33  | lightgbm   | wf    | 0.330    | 0.490    | 0.501   |
| B34  | catboost   | val   | 0.331    | 0.506    | 0.487   |
| B34  | catboost   | test  | 0.333    | 0.520    | 0.478   |
| B34  | catboost   | wf    | 0.328    | 0.486    | 0.498   |
| B34  | lightgbm   | val   | 0.333    | 0.509    | 0.489   |
| B34  | lightgbm   | test  | 0.330    | 0.507    | 0.482   |
| B34  | lightgbm   | wf    | 0.330    | 0.491    | 0.498   |
| B35  | catboost   | val   | 0.335    | 0.524    | 0.480   |
| B35  | catboost   | test  | 0.322    | 0.504    | 0.461   |
| B35  | catboost   | wf    | 0.320    | 0.493    | 0.469   |
| B35  | lightgbm   | val   | 0.332    | 0.520    | 0.476   |
| B35  | lightgbm   | test  | 0.326    | 0.512    | 0.467   |
| B35  | lightgbm   | wf    | 0.319    | 0.499    | 0.459   |
| B36  | catboost   | val   | 0.334    | 0.523    | 0.479   |
| B36  | catboost   | test  | 0.321    | 0.500    | 0.464   |
| B36  | catboost   | wf    | 0.321    | 0.493    | 0.469   |
| B36  | lightgbm   | val   | 0.333    | 0.522    | 0.478   |
| B36  | lightgbm   | test  | 0.325    | 0.511    | 0.463   |
| B36  | lightgbm   | wf    | 0.322    | 0.503    | 0.463   |
| B37  | catboost   | val   | 0.330    | 0.507    | 0.485   |
| B37  | catboost   | test  | 0.327    | 0.499    | 0.483   |
| B37  | catboost   | wf    | 0.323    | 0.482    | 0.488   |
| B37  | lightgbm   | val   | 0.335    | 0.513    | 0.491   |
| B37  | lightgbm   | test  | 0.332    | 0.504    | 0.493   |
| B37  | lightgbm   | wf    | 0.322    | 0.484    | 0.483   |
| B38  | catboost   | val   | 0.333    | 0.505    | 0.494   |
| B38  | catboost   | test  | 0.328    | 0.511    | 0.473   |
| B38  | catboost   | wf    | 0.329    | 0.473    | 0.513   |
| B38  | lightgbm   | val   | 0.332    | 0.503    | 0.492   |
| B38  | lightgbm   | test  | 0.327    | 0.500    | 0.481   |
| B38  | lightgbm   | wf    | 0.330    | 0.481    | 0.510   |
| B39  | catboost   | val   | 0.333    | 0.509    | 0.490   |
| B39  | catboost   | test  | 0.329    | 0.519    | 0.468   |
| B39  | catboost   | wf    | 0.328    | 0.475    | 0.510   |
| B39  | lightgbm   | val   | 0.332    | 0.507    | 0.488   |
| B39  | lightgbm   | test  | 0.329    | 0.510    | 0.476   |
| B39  | lightgbm   | wf    | 0.329    | 0.480    | 0.507   |
| B40  | catboost   | val   | 0.331    | 0.507    | 0.487   |
| B40  | catboost   | test  | 0.330    | 0.530    | 0.461   |
| B40  | catboost   | wf    | 0.329    | 0.481    | 0.505   |
| B40  | lightgbm   | val   | 0.333    | 0.509    | 0.489   |
| B40  | lightgbm   | test  | 0.331    | 0.522    | 0.471   |
| B40  | lightgbm   | wf    | 0.329    | 0.483    | 0.504   |
| B41  | catboost   | val   | 0.332    | 0.508    | 0.488   |
| B41  | catboost   | test  | 0.330    | 0.530    | 0.460   |
| B41  | catboost   | wf    | 0.328    | 0.480    | 0.505   |
| B41  | lightgbm   | val   | 0.333    | 0.509    | 0.489   |
| B41  | lightgbm   | test  | 0.330    | 0.520    | 0.471   |
| B41  | lightgbm   | wf    | 0.329    | 0.484    | 0.503   |
| B42  | catboost   | val   | 0.331    | 0.507    | 0.487   |
| B42  | catboost   | test  | 0.330    | 0.530    | 0.461   |
| B42  | catboost   | wf    | 0.329    | 0.481    | 0.505   |
| B42  | lightgbm   | val   | 0.333    | 0.509    | 0.489   |
| B42  | lightgbm   | test  | 0.331    | 0.522    | 0.471   |
| B42  | lightgbm   | wf    | 0.329    | 0.483    | 0.504   |

## 2.4 Comparatif Distribution true/pred par split (WF)

| Test | model_name | split | true_short% | true_long% | pred_short% | pred_long% |
|:-----|:-----------|:------|------------:|-----------:|------------:|-----------:|
| B0   | catboost   | val   | 51.91       | 48.09      | 50.00       | 50.00      |
| B0   | catboost   | test  | 51.94       | 48.06      | 54.08       | 45.92      |
| B0   | catboost   | wf    | 51.57       | 48.43      | 45.23       | 54.77      |
| B0   | lightgbm   | val   | 51.91       | 48.09      | 50.00       | 50.00      |
| B0   | lightgbm   | test  | 51.94       | 48.06      | 52.39       | 47.61      |
| B0   | lightgbm   | wf    | 51.57       | 48.43      | 45.77       | 54.23      |
| B1   | catboost   | val   | 51.91       | 48.09      | 50.00       | 50.00      |
| B1   | catboost   | test  | 51.94       | 48.06      | 53.89       | 46.11      |
| B1   | catboost   | wf    | 51.57       | 48.43      | 45.44       | 54.56      |
| B1   | lightgbm   | val   | 51.91       | 48.09      | 50.00       | 50.00      |
| B1   | lightgbm   | test  | 51.94       | 48.06      | 52.36       | 47.64      |
| B1   | lightgbm   | wf    | 51.57       | 48.43      | 45.91       | 54.09      |
| B2   | catboost   | val   | 51.91       | 48.09      | 50.00       | 50.00      |
| B2   | catboost   | test  | 51.94       | 48.06      | 54.10       | 45.90      |
| B2   | catboost   | wf    | 51.57       | 48.43      | 45.41       | 54.60      |
| B2   | lightgbm   | val   | 51.91       | 48.09      | 50.00       | 50.00      |
| B2   | lightgbm   | test  | 51.94       | 48.06      | 51.99       | 48.01      |
| B2   | lightgbm   | wf    | 51.57       | 48.43      | 45.90       | 54.10      |
| B3   | catboost   | val   | 51.91       | 48.09      | 50.00       | 50.00      |
| B3   | catboost   | test  | 51.94       | 48.06      | 53.74       | 46.26      |
| B3   | catboost   | wf    | 51.57       | 48.43      | 45.28       | 54.73      |
| B3   | lightgbm   | val   | 51.91       | 48.09      | 50.00       | 50.00      |
| B3   | lightgbm   | test  | 51.94       | 48.06      | 52.40       | 47.60      |
| B3   | lightgbm   | wf    | 51.57       | 48.43      | 45.74       | 54.26      |
| B4   | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B4   | catboost   | test  | 51.93       | 48.08      | 53.83       | 46.17      |
| B4   | catboost   | wf    | 51.41       | 48.59      | 45.25       | 54.75      |
| B4   | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B4   | lightgbm   | test  | 51.93       | 48.08      | 51.88       | 48.12      |
| B4   | lightgbm   | wf    | 51.41       | 48.59      | 45.62       | 54.38      |
| B5   | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B5   | catboost   | test  | 51.93       | 48.08      | 53.73       | 46.27      |
| B5   | catboost   | wf    | 51.41       | 48.59      | 45.54       | 54.47      |
| B5   | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B5   | lightgbm   | test  | 51.93       | 48.08      | 51.82       | 48.18      |
| B5   | lightgbm   | wf    | 51.41       | 48.59      | 46.01       | 53.99      |
| B6   | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B6   | catboost   | test  | 51.93       | 48.08      | 53.25       | 46.75      |
| B6   | catboost   | wf    | 51.41       | 48.59      | 45.42       | 54.58      |
| B6   | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B6   | lightgbm   | test  | 51.93       | 48.08      | 51.29       | 48.72      |
| B6   | lightgbm   | wf    | 51.41       | 48.59      | 45.94       | 54.06      |
| B7   | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B7   | catboost   | test  | 51.93       | 48.08      | 53.90       | 46.10      |
| B7   | catboost   | wf    | 51.41       | 48.59      | 45.67       | 54.34      |
| B7   | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B7   | lightgbm   | test  | 51.93       | 48.08      | 52.04       | 47.96      |
| B7   | lightgbm   | wf    | 51.41       | 48.59      | 45.88       | 54.12      |
| B8   | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B8   | catboost   | test  | 51.93       | 48.08      | 51.86       | 48.15      |
| B8   | catboost   | wf    | 51.41       | 48.59      | 44.90       | 55.10      |
| B8   | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B8   | lightgbm   | test  | 51.93       | 48.08      | 49.06       | 50.94      |
| B8   | lightgbm   | wf    | 51.41       | 48.59      | 46.62       | 53.38      |
| B9   | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B9   | catboost   | test  | 51.93       | 48.08      | 53.03       | 46.97      |
| B9   | catboost   | wf    | 51.41       | 48.59      | 46.87       | 53.13      |
| B9   | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B9   | lightgbm   | test  | 51.93       | 48.08      | 51.55       | 48.45      |
| B9   | lightgbm   | wf    | 51.41       | 48.59      | 47.12       | 52.88      |
| B10  | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B10  | catboost   | test  | 51.93       | 48.08      | 53.23       | 46.77      |
| B10  | catboost   | wf    | 51.41       | 48.59      | 45.18       | 54.82      |
| B10  | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B10  | lightgbm   | test  | 51.93       | 48.08      | 51.41       | 48.60      |
| B10  | lightgbm   | wf    | 51.41       | 48.59      | 45.91       | 54.09      |
| B11  | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B11  | catboost   | test  | 51.93       | 48.08      | 52.55       | 47.45      |
| B11  | catboost   | wf    | 51.41       | 48.59      | 45.46       | 54.54      |
| B11  | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B11  | lightgbm   | test  | 51.93       | 48.08      | 51.02       | 48.98      |
| B11  | lightgbm   | wf    | 51.41       | 48.59      | 46.00       | 54.01      |
| B12  | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B12  | catboost   | test  | 51.93       | 48.08      | 53.24       | 46.76      |
| B12  | catboost   | wf    | 51.41       | 48.59      | 45.29       | 54.72      |
| B12  | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B12  | lightgbm   | test  | 51.93       | 48.08      | 51.43       | 48.57      |
| B12  | lightgbm   | wf    | 51.41       | 48.59      | 45.84       | 54.16      |
| B13  | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B13  | catboost   | test  | 51.93       | 48.08      | 51.73       | 48.27      |
| B13  | catboost   | wf    | 51.41       | 48.59      | 47.24       | 52.77      |
| B13  | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B13  | lightgbm   | test  | 51.93       | 48.08      | 50.08       | 49.92      |
| B13  | lightgbm   | wf    | 51.41       | 48.59      | 47.64       | 52.36      |
| B14  | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B14  | catboost   | test  | 51.93       | 48.08      | 53.58       | 46.42      |
| B14  | catboost   | wf    | 51.41       | 48.59      | 44.96       | 55.04      |
| B14  | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B14  | lightgbm   | test  | 51.93       | 48.08      | 51.45       | 48.55      |
| B14  | lightgbm   | wf    | 51.41       | 48.59      | 45.61       | 54.39      |
| B15  | catboost   | val   | 52.90       | 47.11      | 50.00       | 50.00      |
| B15  | catboost   | test  | 52.63       | 47.37      | 52.52       | 47.48      |
| B15  | catboost   | wf    | 52.14       | 47.86      | 46.23       | 53.77      |
| B15  | lightgbm   | val   | 52.90       | 47.11      | 50.00       | 50.00      |
| B15  | lightgbm   | test  | 52.63       | 47.37      | 51.20       | 48.80      |
| B15  | lightgbm   | wf    | 52.14       | 47.86      | 46.15       | 53.85      |
| B16  | catboost   | val   | 50.28       | 49.02      | 50.00       | 50.00      |
| B16  | catboost   | test  | 50.29       | 49.01      | 51.95       | 48.05      |
| B16  | catboost   | wf    | 50.35       | 48.91      | 46.76       | 53.24      |
| B16  | lightgbm   | val   | 50.28       | 49.02      | 50.00       | 50.00      |
| B16  | lightgbm   | test  | 50.29       | 49.01      | 50.49       | 49.51      |
| B16  | lightgbm   | wf    | 50.35       | 48.91      | 47.05       | 52.95      |
| B17  | catboost   | val   | 25.14       | 25.18      | 13.28       | 15.06      |
| B17  | catboost   | test  | 23.94       | 23.94      | 12.41       | 11.08      |
| B17  | catboost   | wf    | 22.85       | 22.93      | 10.97       | 16.99      |
| B17  | lightgbm   | val   | 23.54       | 23.58      | 22.52       | 20.84      |
| B17  | lightgbm   | test  | 22.41       | 22.42      | 22.52       | 16.26      |
| B17  | lightgbm   | wf    | 22.85       | 22.93      | 21.86       | 17.08      |
| B18  | catboost   | val   | 52.11       | 47.89      | 50.00       | 50.00      |
| B18  | catboost   | test  | 51.90       | 48.10      | 50.77       | 49.23      |
| B18  | catboost   | wf    | 51.83       | 48.17      | 47.59       | 52.41      |
| B18  | lightgbm   | val   | 52.11       | 47.89      | 50.00       | 50.00      |
| B18  | lightgbm   | test  | 51.90       | 48.10      | 51.33       | 48.67      |
| B18  | lightgbm   | wf    | 51.83       | 48.17      | 46.92       | 53.09      |
| B19  | catboost   | val   | 52.11       | 47.89      | 50.00       | 50.00      |
| B19  | catboost   | test  | 51.90       | 48.10      | 50.77       | 49.23      |
| B19  | catboost   | wf    | 51.86       | 48.14      | 47.55       | 52.45      |
| B19  | lightgbm   | val   | 52.11       | 47.89      | 50.00       | 50.00      |
| B19  | lightgbm   | test  | 51.90       | 48.10      | 51.33       | 48.67      |
| B19  | lightgbm   | wf    | 51.86       | 48.14      | 47.23       | 52.77      |
| B20  | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B20  | catboost   | test  | 51.93       | 48.08      | 53.54       | 46.46      |
| B20  | catboost   | wf    | 51.41       | 48.59      | 45.20       | 54.80      |
| B20  | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B20  | lightgbm   | test  | 51.93       | 48.08      | 51.59       | 48.41      |
| B20  | lightgbm   | wf    | 51.41       | 48.59      | 45.54       | 54.46      |
| B21  | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B21  | catboost   | test  | 51.93       | 48.08      | 53.54       | 46.46      |
| B21  | catboost   | wf    | 51.41       | 48.59      | 45.20       | 54.80      |
| B21  | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B21  | lightgbm   | test  | 51.93       | 48.08      | 51.59       | 48.41      |
| B21  | lightgbm   | wf    | 51.41       | 48.59      | 45.54       | 54.46      |
| B22  | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B22  | catboost   | test  | 51.93       | 48.08      | 53.54       | 46.46      |
| B22  | catboost   | wf    | 51.41       | 48.59      | 45.20       | 54.80      |
| B22  | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B22  | lightgbm   | test  | 51.93       | 48.08      | 51.59       | 48.41      |
| B22  | lightgbm   | wf    | 51.41       | 48.59      | 45.54       | 54.46      |
| B25  | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B25  | catboost   | test  | 51.93       | 48.08      | 53.54       | 46.46      |
| B25  | catboost   | wf    | 51.41       | 48.59      | 45.20       | 54.80      |
| B25  | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B25  | lightgbm   | test  | 51.93       | 48.08      | 51.59       | 48.41      |
| B25  | lightgbm   | wf    | 51.41       | 48.59      | 45.54       | 54.46      |
| B26  | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B26  | catboost   | test  | 51.93       | 48.08      | 53.09       | 46.91      |
| B26  | catboost   | wf    | 51.41       | 48.59      | 45.20       | 54.81      |
| B26  | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B26  | lightgbm   | test  | 51.93       | 48.08      | 51.39       | 48.61      |
| B26  | lightgbm   | wf    | 51.41       | 48.59      | 45.91       | 54.09      |
| B27  | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B27  | catboost   | test  | 51.93       | 48.08      | 53.09       | 46.91      |
| B27  | catboost   | wf    | 51.41       | 48.59      | 45.20       | 54.81      |
| B27  | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B27  | lightgbm   | test  | 51.93       | 48.08      | 51.39       | 48.61      |
| B27  | lightgbm   | wf    | 51.41       | 48.59      | 45.91       | 54.09      |
| B30  | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B30  | catboost   | test  | 51.93       | 48.08      | 53.54       | 46.46      |
| B30  | catboost   | wf    | 51.41       | 48.59      | 45.20       | 54.80      |
| B30  | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B30  | lightgbm   | test  | 51.93       | 48.08      | 51.59       | 48.41      |
| B30  | lightgbm   | wf    | 51.41       | 48.59      | 45.54       | 54.46      |
| B31  | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B31  | catboost   | test  | 51.93       | 48.08      | 53.64       | 46.36      |
| B31  | catboost   | wf    | 51.41       | 48.59      | 46.85       | 53.15      |
| B31  | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B31  | lightgbm   | test  | 51.93       | 48.08      | 51.68       | 48.32      |
| B31  | lightgbm   | wf    | 51.41       | 48.59      | 47.12       | 52.88      |
| B32  | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B32  | catboost   | test  | 51.93       | 48.08      | 53.56       | 46.44      |
| B32  | catboost   | wf    | 51.41       | 48.59      | 45.32       | 54.68      |
| B32  | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B32  | lightgbm   | test  | 51.93       | 48.08      | 51.70       | 48.30      |
| B32  | lightgbm   | wf    | 51.41       | 48.59      | 45.79       | 54.21      |
| B33  | catboost   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B33  | catboost   | test  | 51.93       | 48.08      | 51.92       | 48.08      |
| B33  | catboost   | wf    | 51.41       | 48.59      | 47.17       | 52.83      |
| B33  | lightgbm   | val   | 51.94       | 48.06      | 50.00       | 50.00      |
| B33  | lightgbm   | test  | 51.93       | 48.08      | 50.22       | 49.78      |
| B33  | lightgbm   | wf    | 51.41       | 48.59      | 47.66       | 52.34      |
| B34  | catboost   | val   | 51.91       | 48.09      | 50.00       | 50.00      |
| B34  | catboost   | test  | 51.94       | 48.06      | 52.10       | 47.90      |
| B34  | catboost   | wf    | 51.57       | 48.43      | 47.43       | 52.57      |
| B34  | lightgbm   | val   | 51.91       | 48.09      | 50.00       | 50.00      |
| B34  | lightgbm   | test  | 51.94       | 48.06      | 50.40       | 49.60      |
| B34  | lightgbm   | wf    | 51.57       | 48.43      | 47.78       | 52.22      |
| B35  | catboost   | val   | 54.44       | 45.56      | 49.99       | 49.99      |
| B35  | catboost   | test  | 53.89       | 46.11      | 50.40       | 49.60      |
| B35  | catboost   | wf    | 53.78       | 46.22      | 48.95       | 51.05      |
| B35  | lightgbm   | val   | 54.44       | 45.56      | 49.99       | 49.99      |
| B35  | lightgbm   | test  | 53.89       | 46.11      | 50.73       | 49.27      |
| B35  | lightgbm   | wf    | 53.78       | 46.22      | 50.28       | 49.72      |
| B36  | catboost   | val   | 54.44       | 45.56      | 49.99       | 49.99      |
| B36  | catboost   | test  | 53.89       | 46.11      | 49.81       | 50.19      |
| B36  | catboost   | wf    | 53.78       | 46.22      | 48.87       | 51.13      |
| B36  | lightgbm   | val   | 54.44       | 45.56      | 49.99       | 49.99      |
| B36  | lightgbm   | test  | 53.89       | 46.11      | 50.98       | 49.02      |
| B36  | lightgbm   | wf    | 53.78       | 46.22      | 50.32       | 49.68      |
| B37  | catboost   | val   | 52.18       | 47.82      | 49.994      | 49.994     |
| B37  | catboost   | test  | 52.239      | 47.761     | 49.388      | 50.612     |
| B37  | catboost   | wf    | 52.343      | 47.657     | 47.219      | 52.781     |
| B37  | lightgbm   | val   | 52.18       | 47.82      | 49.994      | 49.993     |
| B37  | lightgbm   | test  | 52.239      | 47.761     | 48.811      | 51.189     |
| B37  | lightgbm   | wf    | 52.343      | 47.657     | 47.786      | 52.213     |
| B38  | catboost   | val   | 51.154      | 48.846     | 49.995      | 49.995     |
| B38  | catboost   | test  | 51.072      | 48.928     | 52.761      | 47.239     |
| B38  | catboost   | wf    | 50.442      | 49.558     | 45.642      | 54.358     |
| B38  | lightgbm   | val   | 51.154      | 48.846     | 49.995      | 49.992     |
| B38  | lightgbm   | test  | 51.072      | 48.928     | 50.775      | 49.224     |
| B38  | lightgbm   | wf    | 50.442      | 49.558     | 46.757      | 53.242     |
| B39  | catboost   | val   | 51.936      | 48.064     | 49.998      | 49.998    |
| B39  | catboost   | test  | 51.925      | 48.075     | 53.089      | 46.911    |
| B39  | catboost   | wf    | 51.407      | 48.593     | 45.195      | 54.805    |
| B39  | lightgbm   | val   | 51.936      | 48.064     | 49.998      | 49.998    |
| B39  | lightgbm   | test  | 51.925      | 48.075     | 51.391      | 48.609    |
| B39  | lightgbm   | wf    | 51.407      | 48.593     | 45.913      | 54.087    |
| B40  | catboost   | val   | 51.936      | 48.064     | 49.998      | 49.998    |
| B40  | catboost   | test  | 51.925      | 48.075     | 54.914      | 45.086    |
| B40  | catboost   | wf    | 51.407      | 48.593     | 46.197      | 53.803    |
| B40  | lightgbm   | val   | 51.936      | 48.064     | 49.998      | 49.998    |
| B40  | lightgbm   | test  | 51.925      | 48.075     | 53.059      | 46.941    |
| B40  | lightgbm   | wf    | 51.407      | 48.593     | 46.494      | 53.506    |
| B41  | catboost   | val   | 51.936      | 48.064     | 49.998      | 49.998    |
| B41  | catboost   | test  | 51.925      | 48.075     | 55.052      | 44.948    |
| B41  | catboost   | wf    | 51.407      | 48.593     | 46.184      | 53.816    |
| B41  | lightgbm   | val   | 51.936      | 48.064     | 49.998      | 49.998    |
| B41  | lightgbm   | test  | 51.925      | 48.075     | 52.869      | 47.131    |
| B41  | lightgbm   | wf    | 51.407      | 48.593     | 46.732      | 53.268    |
| B42  | catboost   | val   | 51.936      | 48.064     | 49.998      | 49.998    |
| B42  | catboost   | test  | 51.925      | 48.075     | 54.914      | 45.086    |
| B42  | catboost   | wf    | 51.407      | 48.593     | 46.197      | 53.803    |
| B42  | lightgbm   | val   | 51.936      | 48.064     | 49.998      | 49.998    |
| B42  | lightgbm   | test  | 51.925      | 48.075     | 53.059      | 46.941    |
| B42  | lightgbm   | wf    | 51.407      | 48.593     | 46.494      | 53.506    |

## 2.5 Comparatif Métriques Régression par split (WF)

| Test | model_name | split | avg_mse | avg_dir_acc |
|:-----|:-----------|:------|--------:|------------:|
| B0   | catboost   | val   | 1.0627  | 0.4963      |
| B0   | catboost   | test  | 1.0720  | 0.4968      |
| B0   | catboost   | wf    | 1.0347  | 0.5010      |
| B0   | lightgbm   | val   | 1.0749  | 0.4964      |
| B0   | lightgbm   | test  | 1.0924  | 0.4967      |
| B0   | lightgbm   | wf    | 1.0537  | 0.5007      |
| B1   | catboost   | val   | 1.0621  | 0.4961      |
| B1   | catboost   | test  | 1.0709  | 0.4972      |
| B1   | catboost   | wf    | 1.0351  | 0.5001      |
| B1   | lightgbm   | val   | 1.0741  | 0.4963      |
| B1   | lightgbm   | test  | 1.0904  | 0.4959      |
| B1   | lightgbm   | wf    | 1.0540  | 0.5009      |
| B2   | catboost   | val   | 1.0617  | 0.4966      |
| B2   | catboost   | test  | 1.0715  | 0.4972      |
| B2   | catboost   | wf    | 1.0337  | 0.5009      |
| B2   | lightgbm   | val   | 1.0753  | 0.4969      |
| B2   | lightgbm   | test  | 1.0909  | 0.4963      |
| B2   | lightgbm   | wf    | 1.0522  | 0.5004      |
| B3   | catboost   | val   | 1.0620  | 0.4962      |
| B3   | catboost   | test  | 1.0720  | 0.4978      |
| B3   | catboost   | wf    | 1.0363  | 0.4999      |
| B3   | lightgbm   | val   | 1.0772  | 0.4969      |
| B3   | lightgbm   | test  | 1.0924  | 0.4962      |
| B3   | lightgbm   | wf    | 1.0549  | 0.5002      |
| B4   | catboost   | val   | 1.0657  | 0.4985      |
| B4   | catboost   | test  | 1.0868  | 0.4995      |
| B4   | catboost   | wf    | 1.0436  | 0.5015      |
| B4   | lightgbm   | val   | 1.0822  | 0.4956      |
| B4   | lightgbm   | test  | 1.1076  | 0.4961      |
| B4   | lightgbm   | wf    | 1.0623  | 0.5019      |
| B5   | catboost   | val   | 1.0662  | 0.4985      |
| B5   | catboost   | test  | 1.0866  | 0.4976      |
| B5   | catboost   | wf    | 1.0436  | 0.5015      |
| B5   | lightgbm   | val   | 1.0819  | 0.4978      |
| B5   | lightgbm   | test  | 1.1068  | 0.4962      |
| B5   | lightgbm   | wf    | 1.0637  | 0.5010      |
| B6   | catboost   | val   | 1.0674  | 0.4986      |
| B6   | catboost   | test  | 1.0867  | 0.4981      |
| B6   | catboost   | wf    | 1.0427  | 0.5023      |
| B6   | lightgbm   | val   | 1.0816  | 0.4971      |
| B6   | lightgbm   | test  | 1.1081  | 0.4957      |
| B6   | lightgbm   | wf    | 1.0646  | 0.5013      |
| B7   | catboost   | val   | 1.0666  | 0.4980      |
| B7   | catboost   | test  | 1.0875  | 0.4978      |
| B7   | catboost   | wf    | 1.0438  | 0.5014      |
| B7   | lightgbm   | val   | 1.0793  | 0.4966      |
| B7   | lightgbm   | test  | 1.1073  | 0.4971      |
| B7   | lightgbm   | wf    | 1.0647  | 0.5007      |
| B8   | catboost   | val   | 1.0740  | 0.4975      |
| B8   | catboost   | test  | 1.0893  | 0.4979      |
| B8   | catboost   | wf    | 1.0448  | 0.5010      |
| B8   | lightgbm   | val   | 1.0923  | 0.4967      |
| B8   | lightgbm   | test  | 1.1116  | 0.4939      |
| B8   | lightgbm   | wf    | 1.0647  | 0.5009      |
| B9   | catboost   | val   | 1.0685  | 0.4976      |
| B9   | catboost   | test  | 1.0934  | 0.4970      |
| B9   | catboost   | wf    | 1.0435  | 0.5003      |
| B9   | lightgbm   | val   | 1.0849  | 0.4997      |
| B9   | lightgbm   | test  | 1.1113  | 0.4976      |
| B9   | lightgbm   | wf    | 1.0641  | 0.5022      |
| B10  | catboost   | val   | 1.0664  | 0.4982      |
| B10  | catboost   | test  | 1.0883  | 0.4963      |
| B10  | catboost   | wf    | 1.0445  | 0.5013      |
| B10  | lightgbm   | val   | 1.0804  | 0.4967      |
| B10  | lightgbm   | test  | 1.1098  | 0.4951      |
| B10  | lightgbm   | wf    | 1.0624  | 0.5011      |
| B11  | catboost   | val   | 1.0626  | 0.4965      |
| B11  | catboost   | test  | 1.0838  | 0.4976      |
| B11  | catboost   | wf    | 1.0437  | 0.5011      |
| B11  | lightgbm   | val   | 1.0763  | 0.4957      |
| B11  | lightgbm   | test  | 1.1062  | 0.4942      |
| B11  | lightgbm   | wf    | 1.0638  | 0.5013      |
| B12  | catboost   | val   | 1.0654  | 0.4997      |
| B12  | catboost   | test  | 1.0866  | 0.4977      |
| B12  | catboost   | wf    | 1.0432  | 0.5017      |
| B12  | lightgbm   | val   | 1.0800  | 0.4972      |
| B12  | lightgbm   | test  | 1.1078  | 0.4960      |
| B12  | lightgbm   | wf    | 1.0621  | 0.5009      |
| B13  | catboost   | val   | 1.0618  | 0.4988      |
| B13  | catboost   | test  | 1.0811  | 0.5034      |
| B13  | catboost   | wf    | 1.0471  | 0.5017      |
| B13  | lightgbm   | val   | 1.0751  | 0.4989      |
| B13  | lightgbm   | test  | 1.1071  | 0.4977      |
| B13  | lightgbm   | wf    | 1.0682  | 0.5027      |
| B14  | catboost   | val   | 1.0667  | 0.4989      |
| B14  | catboost   | test  | 1.0880  | 0.4973      |
| B14  | catboost   | wf    | 1.0442  | 0.5010      |
| B14  | lightgbm   | val   | 1.0800  | 0.4977      |
| B14  | lightgbm   | test  | 1.1085  | 0.4941      |
| B14  | lightgbm   | wf    | 1.0618  | 0.5018      |
| B15  | catboost   | val   | 0.9883  | 0.4940      |
| B15  | catboost   | test  | 1.0729  | 0.5005      |
| B15  | catboost   | wf    | 1.2404  | 0.4997      |
| B15  | lightgbm   | val   | 0.9975  | 0.4953      |
| B15  | lightgbm   | test  | 1.0939  | 0.4979      |
| B15  | lightgbm   | wf    | 1.2671  | 0.4996      |
| B16  | catboost   | val   | 1.0421  | 0.4942      |
| B16  | catboost   | test  | 1.0425  | 0.4914      |
| B16  | catboost   | wf    | 1.0496  | 0.4969      |
| B16  | lightgbm   | val   | 1.0573  | 0.4930      |
| B16  | lightgbm   | test  | 1.0596  | 0.4919      |
| B16  | lightgbm   | wf    | 1.0683  | 0.4972      |
| B17  | catboost   | val   | 0.1734  | 0.7642      |
| B17  | catboost   | test  | 0.1678  | 0.7758      |
| B17  | catboost   | wf    | 0.2502  | 0.4751      |
| B17  | lightgbm   | val   | 0.1734  | 0.7642      |
| B17  | lightgbm   | test  | 0.1679  | 0.7758      |
| B17  | lightgbm   | wf    | 0.2530  | 0.4625      |
| B18  | catboost   | val   | 0.9845  | 0.4981      |
| B18  | catboost   | test  | 1.1088  | 0.5065      |
| B18  | catboost   | wf    | 1.1432  | 0.4971      |
| B18  | lightgbm   | val   | 1.0017  | 0.4963      |
| B18  | lightgbm   | test  | 1.1294  | 0.5027      |
| B18  | lightgbm   | wf    | 1.1714  | 0.4970      |
| B19  | catboost   | val   | 0.9845  | 0.4981      |
| B19  | catboost   | test  | 1.1088  | 0.5065      |
| B19  | catboost   | wf    | 1.1212  | 0.4983      |
| B19  | lightgbm   | val   | 1.0017  | 0.4963      |
| B19  | lightgbm   | test  | 1.1294  | 0.5027      |
| B19  | lightgbm   | wf    | 1.1461  | 0.4986      |
| B20  | catboost   | val   | 1.0648  | 0.4991      |
| B20  | catboost   | test  | 1.0868  | 0.4988      |
| B20  | catboost   | wf    | 1.0436  | 0.5011      |
| B20  | lightgbm   | val   | 1.0820  | 0.4964      |
| B20  | lightgbm   | test  | 1.1086  | 0.4953      |
| B20  | lightgbm   | wf    | 1.0626  | 0.5019      |
| B21  | catboost   | val   | 1.0648  | 0.4991      |
| B21  | catboost   | test  | 1.0868  | 0.4988      |
| B21  | catboost   | wf    | 1.0436  | 0.5011      |
| B21  | lightgbm   | val   | 1.0820  | 0.4964      |
| B21  | lightgbm   | test  | 1.1086  | 0.4953      |
| B21  | lightgbm   | wf    | 1.0626  | 0.5019      |
| B22  | catboost   | val   | 1.0648  | 0.4991      |
| B22  | catboost   | test  | 1.0868  | 0.4988      |
| B22  | catboost   | wf    | 1.0436  | 0.5011      |
| B22  | lightgbm   | val   | 1.0820  | 0.4964      |
| B22  | lightgbm   | test  | 1.1086  | 0.4953      |
| B22  | lightgbm   | wf    | 1.0626  | 0.5019      |
| B25  | catboost   | val   | 1.0662  | 0.4997      |
| B25  | catboost   | test  | 1.0878  | 0.4965      |
| B25  | catboost   | wf    | 1.0446  | 0.5014      |
| B25  | lightgbm   | val   | 1.0800  | 0.4980      |
| B25  | lightgbm   | test  | 1.1097  | 0.4954      |
| B25  | lightgbm   | wf    | 1.0624  | 0.5011      |
| B26  | catboost   | val   | 1.0662  | 0.4997      |
| B26  | catboost   | test  | 1.0878  | 0.4965      |
| B26  | catboost   | wf    | 1.0446  | 0.5014      |
| B26  | lightgbm   | val   | 1.0800  | 0.4980      |
| B26  | lightgbm   | test  | 1.1097  | 0.4954      |
| B26  | lightgbm   | wf    | 1.0624  | 0.5011      |
| B27  | catboost   | val   | 1.0662  | 0.4997      |
| B27  | catboost   | test  | 1.0878  | 0.4965      |
| B27  | catboost   | wf    | 1.0446  | 0.5014      |
| B27  | lightgbm   | val   | 1.0800  | 0.4980      |
| B27  | lightgbm   | test  | 1.1097  | 0.4954      |
| B27  | lightgbm   | wf    | 1.0624  | 0.5011      |
| B30  | catboost   | val   | 1.0648  | 0.4991      |
| B30  | catboost   | test  | 1.0868  | 0.4988      |
| B30  | catboost   | wf    | 1.0436  | 0.5011      |
| B30  | lightgbm   | val   | 1.0820  | 0.4964      |
| B30  | lightgbm   | test  | 1.1086  | 0.4953      |
| B30  | lightgbm   | wf    | 1.0626  | 0.5019      |
| B31  | catboost   | val   | 1.0682  | 0.4985      |
| B31  | catboost   | test  | 1.0938  | 0.4971      |
| B31  | catboost   | wf    | 1.0437  | 0.5004      |
| B31  | lightgbm   | val   | 1.0856  | 0.4994      |
| B31  | lightgbm   | test  | 1.1118  | 0.4973      |
| B31  | lightgbm   | wf    | 1.0643  | 0.5020      |
| B32  | catboost   | val   | 1.0651  | 0.4994      |
| B32  | catboost   | test  | 1.0879  | 0.4982      |
| B32  | catboost   | wf    | 1.0433  | 0.5017      |
| B32  | lightgbm   | val   | 1.0811  | 0.4964      |
| B32  | lightgbm   | test  | 1.1081  | 0.4954      |
| B32  | lightgbm   | wf    | 1.0624  | 0.5011      |
| B33  | catboost   | val   | 1.0626  | 0.4988      |
| B33  | catboost   | test  | 1.0816  | 0.5029      |
| B33  | catboost   | wf    | 1.0471  | 0.5016      |
| B33  | lightgbm   | val   | 1.0754  | 0.4991      |
| B33  | lightgbm   | test  | 1.1070  | 0.4985      |
| B33  | lightgbm   | wf    | 1.0681  | 0.5027      |
| B34  | catboost   | val   | 1.0573  | 0.4968      |
| B34  | catboost   | test  | 1.0616  | 0.5037      |
| B34  | catboost   | wf    | 1.0375  | 0.5003      |
| B34  | lightgbm   | val   | 1.0689  | 0.4994      |
| B34  | lightgbm   | test  | 1.0879  | 0.4981      |
| B34  | lightgbm   | wf    | 1.0592  | 0.5014      |
| B35  | catboost   | val   | 1.2967  | 0.5038      |
| B35  | catboost   | test  | 1.4063  | 0.4853      |
| B35  | catboost   | wf    | 1.3140  | 0.4937      |
| B35  | lightgbm   | val   | 1.3405  | 0.4996      |
| B35  | lightgbm   | test  | 1.4439  | 0.4929      |
| B35  | lightgbm   | wf    | 1.3576  | 0.4924      |
| B36  | catboost   | val   | 1.2961  | 0.5029      |
| B36  | catboost   | test  | 1.4113  | 0.4848      |
| B36  | catboost   | wf    | 1.3132  | 0.4939      |
| B36  | lightgbm   | val   | 1.3401  | 0.5013      |
| B36  | lightgbm   | test  | 1.4417  | 0.4907      |
| B36  | lightgbm   | wf    | 1.3578  | 0.4963      |
| B37  | catboost   | val   | 1.6019  | 0.4961      |
| B37  | catboost   | test  | 1.6332  | 0.4956      |
| B37  | catboost   | wf    | 1.7878  | 0.4926      |
| B37  | lightgbm   | val   | 1.6345  | 0.5026      |
| B37  | lightgbm   | test  | 1.6597  | 0.5020      |
| B37  | lightgbm   | wf    | 1.8970  | 0.4921      |
| B38  | catboost   | val   | 1.0908  | 0.5004      |
| B38  | catboost   | test  | 1.1064  | 0.4953      |
| B38  | catboost   | wf    | 1.0535  | 0.5025      |
| B38  | lightgbm   | val   | 1.1059  | 0.4984      |
| B38  | lightgbm   | test  | 1.1261  | 0.4926      |
| B38  | lightgbm   | wf    | 1.0709  | 0.5034      |
| B39  | catboost   | val   | 1.0662  | 0.4997      |
| B39  | catboost   | test  | 1.0878  | 0.4965      |
| B39  | catboost   | wf    | 1.0446  | 0.5014      |
| B39  | lightgbm   | val   | 1.0800  | 0.4980      |
| B39  | lightgbm   | test  | 1.1097  | 0.4954      |
| B39  | lightgbm   | wf    | 1.0624  | 0.5011      |
| B40  | catboost   | val   | 1.0607  | 0.4975      |
| B40  | catboost   | test  | 1.0841  | 0.4995      |
| B40  | catboost   | wf    | 1.0406  | 0.5019      |
| B40  | lightgbm   | val   | 1.0743  | 0.4994      |
| B40  | lightgbm   | test  | 1.1000  | 0.5003      |
| B40  | lightgbm   | wf    | 1.0614  | 0.5017      |
| B41  | catboost   | val   | 1.0610  | 0.4985      |
| B41  | catboost   | test  | 1.0852  | 0.4991      |
| B41  | catboost   | wf    | 1.0406  | 0.5013      |
| B41  | lightgbm   | val   | 1.0725  | 0.4994      |
| B41  | lightgbm   | test  | 1.1016  | 0.4994      |
| B41  | lightgbm   | wf    | 1.0615  | 0.5018      |
| B42  | catboost   | val   | 1.0607  | 0.4975      |
| B42  | catboost   | test  | 1.0841  | 0.4995      |
| B42  | catboost   | wf    | 1.0406  | 0.5019      |
| B42  | lightgbm   | val   | 1.0743  | 0.4994      |
| B42  | lightgbm   | test  | 1.1000  | 0.5003      |
| B42  | lightgbm   | wf    | 1.0614  | 0.5017      |

## 2.6 Distribution F1 macro — Walk-Forward

| Test | Bucket      | Nb symboles |
|:-----|:------------|------------:|
| B0   | 0.20–0.29   | 1           |
| B0   | 0.30–0.39   | 11          |
| B1   | 0.20–0.29   | 1           |
| B1   | 0.30–0.39   | 11          |
| B2   | 0.20–0.29   | 1           |
| B2   | 0.30–0.39   | 11          |
| B3   | 0.30–0.39   | 11          |
| B4   | 0.20–0.29   | 1           |
| B4   | 0.30–0.39   | 11          |
| B5   | 0.20–0.29   | 1           |
| B5   | 0.30–0.39   | 11          |
| B6   | 0.20–0.29   | 1           |
| B6   | 0.30–0.39   | 11          |
| B7   | 0.20–0.29   | 1           |
| B7   | 0.30–0.39   | 11          |
| B8   | 0.20–0.29   | 1           |
| B8   | 0.30–0.39   | 11          |
| B9   | 0.30–0.39   | 11          |
| B10  | 0.20–0.29   | 1           |
| B10  | 0.30–0.39   | 11          |
| B11  | 0.20–0.29   | 1           |
| B11  | 0.30–0.39   | 11          |
| B12  | 0.30–0.39   | 11          |
| B13  | 0.20–0.29   | 1           |
| B13  | 0.30–0.39   | 11          |
| B14  | 0.20–0.29   | 1           |
| B14  | 0.30–0.39   | 11          |
| B15  | 0.30–0.39   | 11          |
| B16  | 0.20–0.29   | 1           |
| B16  | 0.30–0.39   | 11          |
| B17  | 0.00–0.09   | 1           |
| B17  | 0.20–0.29   | 3           |
| B17  | 0.30–0.39   | 11          |
| B17  | 0.40+       | 2           |
| B18  | 0.30–0.39   | 11          |
| B19  | 0.30–0.39   | 11          |
| B20  | 0.20–0.29   | 1           |
| B20  | 0.30–0.39   | 11          |
| B21  | 0.20–0.29   | 1           |
| B21  | 0.30–0.39   | 11          |
| B22  | 0.20–0.29   | 1           |
| B22  | 0.30–0.39   | 11          |
| B25  | 0.20–0.29   | 1           |
| B25  | 0.30–0.39   | 11          |
| B26  | 0.20–0.29   | 1           |
| B26  | 0.30–0.39   | 11          |
| B27  | 0.20–0.29   | 1           |
| B27  | 0.30–0.39   | 11          |
| B30  | 0.20–0.29   | 1           |
| B30  | 0.30–0.39   | 11          |
| B31  | 0.30–0.39   | 11          |
| B32  | 0.20–0.29   | 1           |
| B32  | 0.30–0.39   | 11          |
| B33  | 0.20–0.29   | 1           |
| B33  | 0.30–0.39   | 11          |
| B34  | 0.30–0.39   | 11          |
| B35  | 0.20–0.29   | 2           |
| B35  | 0.30–0.39   | 8           |
| B36  | 0.20–0.29   | 2           |
| B36  | 0.30–0.39   | 8           |
| B37  | 0.20–0.29   | 3           |
| B37  | 0.30–0.39   | 11          |
| B38  | 0.20–0.29   | 1           |
| B38  | 0.30–0.39   | 11          |
| B39  | 0.20–0.29   | 1           |
| B39  | 0.30–0.39   | 11          |
| B40  | 0.30–0.39   | 11          |
| B41  | 0.20–0.29   | 1           |
| B41  | 0.30–0.39   | 11          |
| B42  | 0.30–0.39   | 11          |

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
| B1   | Consumer Staples  | 0.355    | 0.548   | 0.519    |
| B1   | Consumer Staples  | 0.355    | 0.553   | 0.512    |
| B1   | Consumer Staples  | 0.344    | 0.537   | 0.496    |
| B1   | Industrials       | 0.344    | 0.504   | 0.528    |
| B1   | Industrials       | 0.340    | 0.499   | 0.521    |
| B1   | Health Care       | 0.340    | 0.520   | 0.500    |
| B1   | Industrials       | 0.340    | 0.501   | 0.518    |
| B1   | Industrials       | 0.339    | 0.494   | 0.524    |
| B1   | Industrials       | 0.338    | 0.501   | 0.513    |
| B1   | Health Care       | 0.337    | 0.517   | 0.493    |
| B2   | Consumer Staples  | 0.358    | 0.559   | 0.516    |
| B2   | Consumer Staples  | 0.358    | 0.553   | 0.521    |
| B2   | Industrials       | 0.345    | 0.509   | 0.526    |
| B2   | Consumer Staples  | 0.345    | 0.542   | 0.492    |
| B2   | Health Care       | 0.340    | 0.519   | 0.500    |
| B2   | Industrials       | 0.339    | 0.501   | 0.516    |
| B2   | Industrials       | 0.339    | 0.497   | 0.520    |
| B2   | Health Care       | 0.338    | 0.519   | 0.496    |
| B2   | Financials        | 0.338    | 0.516   | 0.499    |
| B2   | Industrials       | 0.338    | 0.501   | 0.513    |
| B3   | Consumer Staples  | 0.361    | 0.555   | 0.527    |
| B3   | Consumer Staples  | 0.354    | 0.548   | 0.514    |
| B3   | Consumer Staples  | 0.344    | 0.536   | 0.495    |
| B3   | Industrials       | 0.342    | 0.502   | 0.525    |
| B3   | Industrials       | 0.341    | 0.502   | 0.522    |
| B3   | Industrials       | 0.339    | 0.500   | 0.517    |
| B3   | Industrials       | 0.339    | 0.497   | 0.519    |
| B3   | Industrials       | 0.337    | 0.502   | 0.509    |
| B3   | Financials        | 0.337    | 0.511   | 0.499    |
| B3   | Health Care       | 0.335    | 0.519   | 0.486    |
| B4   | Consumer Staples  | 0.354    | 0.552   | 0.509    |
| B4   | Consumer Staples  | 0.349    | 0.548   | 0.499    |
| B4   | Consumer Staples  | 0.349    | 0.553   | 0.492    |
| B4   | Consumer Staples  | 0.344    | 0.561   | 0.471    |
| B4   | Industrials       | 0.344    | 0.510   | 0.521    |
| B4   | Industrials       | 0.344    | 0.509   | 0.522    |
| B4   | Industrials       | 0.342    | 0.508   | 0.518    |
| B4   | Industrials       | 0.340    | 0.497   | 0.523    |
| B4   | Health Care       | 0.337    | 0.525   | 0.486    |
| B4   | Industrials       | 0.337    | 0.502   | 0.509    |
| B5   | Consumer Staples  | 0.360    | 0.548   | 0.532    |
| B5   | Consumer Staples  | 0.349    | 0.535   | 0.512    |
| B5   | Consumer Staples  | 0.345    | 0.529   | 0.505    |
| B5   | Financials        | 0.339    | 0.518   | 0.498    |
| B5   | Health Care       | 0.338    | 0.527   | 0.489    |
| B5   | Consumer Staples  | 0.338    | 0.532   | 0.482    |
| B5   | Industrials       | 0.338    | 0.505   | 0.508    |
| B5   | Industrials       | 0.337    | 0.507   | 0.503    |
| B5   | Industrials       | 0.336    | 0.504   | 0.505    |
| B5   | Financials        | 0.336    | 0.516   | 0.493    |
| B6   | Consumer Staples       | 0.360    | 0.550   | 0.529    |
| B6   | Consumer Staples       | 0.355    | 0.546   | 0.519    |
| B6   | Industrials            | 0.345    | 0.506   | 0.529    |
| B6   | Consumer Staples       | 0.345    | 0.524   | 0.511    |
| B6   | Industrials            | 0.345    | 0.509   | 0.526    |
| B6   | Industrials            | 0.339    | 0.492   | 0.525    |
| B6   | Industrials            | 0.339    | 0.499   | 0.517    |
| B6   | Industrials            | 0.338    | 0.499   | 0.516    |
| B6   | Consumer Staples       | 0.337    | 0.527   | 0.484    |
| B6   | Information Technology | 0.336    | 0.522   | 0.486    |
| B7   | Consumer Staples  | 0.358    | 0.552   | 0.521    |
| B7   | Consumer Staples  | 0.352    | 0.555   | 0.502    |
| B7   | Consumer Staples  | 0.352    | 0.550   | 0.505    |
| B7   | Consumer Staples  | 0.339    | 0.543   | 0.475    |
| B7   | Consumer Staples  | 0.338    | 0.524   | 0.491    |
| B7   | Health Care       | 0.337    | 0.523   | 0.488    |
| B7   | Industrials       | 0.337    | 0.504   | 0.506    |
| B7   | Financials        | 0.336    | 0.495   | 0.513    |
| B7   | Financials        | 0.335    | 0.521   | 0.485    |
| B7   | Industrials       | 0.335    | 0.494   | 0.512    |
| B8   | Consumer Staples  | 0.356    | 0.550   | 0.517    |
| B8   | Consumer Staples  | 0.347    | 0.542   | 0.499    |
| B8   | Health Care       | 0.342    | 0.520   | 0.506    |
| B8   | Consumer Staples  | 0.342    | 0.530   | 0.495    |
| B8   | Health Care       | 0.341    | 0.524   | 0.499    |
| B8   | Health Care       | 0.340    | 0.522   | 0.497    |
| B8   | Health Care       | 0.337    | 0.523   | 0.490    |
| B8   | Industrials       | 0.337    | 0.495   | 0.515    |
| B8   | Financials        | 0.337    | 0.527   | 0.483    |
| B8   | Financials        | 0.336    | 0.489   | 0.520    |
| B9   | Consumer Staples  | 0.348    | 0.536   | 0.508    |
| B9   | Consumer Staples  | 0.347    | 0.532   | 0.510    |
| B9   | Industrials       | 0.345    | 0.508   | 0.527    |
| B9   | Consumer Staples  | 0.344    | 0.533   | 0.500    |
| B9   | Industrials       | 0.344    | 0.510   | 0.521    |
| B9   | Industrials       | 0.340    | 0.500   | 0.520    |
| B9   | Industrials       | 0.338    | 0.497   | 0.517    |
| B9   | Industrials       | 0.338    | 0.500   | 0.514    |
| B9   | Consumer Staples  | 0.337    | 0.526   | 0.485    |
| B9   | Consumer Staples  | 0.336    | 0.518   | 0.491    |
| B10  | Consumer Staples       | 0.361    | 0.551   | 0.531    |
| B10  | Consumer Staples       | 0.356    | 0.546   | 0.523    |
| B10  | Industrials            | 0.346    | 0.512   | 0.526    |
| B10  | Consumer Staples       | 0.345    | 0.532   | 0.504    |
| B10  | Industrials            | 0.344    | 0.509   | 0.522    |
| B10  | Industrials            | 0.339    | 0.501   | 0.517    |
| B10  | Industrials            | 0.339    | 0.501   | 0.517    |
| B10  | Industrials            | 0.339    | 0.496   | 0.520    |
| B10  | Health Care            | 0.338    | 0.524   | 0.490    |
| B10  | Information Technology | 0.337    | 0.521   | 0.489    |
| B11  | Consumer Staples       | 0.353    | 0.540   | 0.519    |
| B11  | Consumer Staples       | 0.352    | 0.534   | 0.523    |
| B11  | Consumer Staples       | 0.339    | 0.524   | 0.494    |
| B11  | Industrials            | 0.338    | 0.503   | 0.512    |
| B11  | Health Care            | 0.337    | 0.532   | 0.477    |
| B11  | Health Care            | 0.337    | 0.531   | 0.478    |
| B11  | Consumer Staples       | 0.336    | 0.530   | 0.478    |
| B11  | Industrials            | 0.336    | 0.504   | 0.503    |
| B11  | Consumer Discretionary | 0.335    | 0.511   | 0.494    |
| B11  | Health Care            | 0.335    | 0.514   | 0.491    |
| B12  | Consumer Staples       | 0.358    | 0.551   | 0.521    |
| B12  | Consumer Staples       | 0.357    | 0.550   | 0.522    |
| B12  | Consumer Staples       | 0.349    | 0.539   | 0.508    |
| B12  | Industrials            | 0.345    | 0.508   | 0.527    |
| B12  | Industrials            | 0.343    | 0.509   | 0.521    |
| B12  | Industrials            | 0.343    | 0.504   | 0.525    |
| B12  | Industrials            | 0.340    | 0.498   | 0.523    |
| B12  | Health Care            | 0.338    | 0.524   | 0.489    |
| B12  | Consumer Staples       | 0.337    | 0.534   | 0.477    |
| B12  | Industrials            | 0.337    | 0.498   | 0.512    |
| B13  | Consumer Staples       | 0.358    | 0.543   | 0.531    |
| B13  | Consumer Staples       | 0.354    | 0.534   | 0.529    |
| B13  | Health Care            | 0.346    | 0.505   | 0.534    |
| B13  | Industrials            | 0.346    | 0.509   | 0.529    |
| B13  | Consumer Staples       | 0.346    | 0.519   | 0.519    |
| B13  | Industrials            | 0.344    | 0.500   | 0.532    |
| B13  | Industrials            | 0.342    | 0.503   | 0.523    |
| B13  | Health Care            | 0.341    | 0.511   | 0.512    |
| B13  | Health Care            | 0.341    | 0.494   | 0.527    |
| B13  | Financials             | 0.339    | 0.496   | 0.522    |
| B14  | Consumer Staples       | 0.356    | 0.558   | 0.511    |
| B14  | Consumer Staples       | 0.354    | 0.560   | 0.501    |
| B14  | Industrials            | 0.345    | 0.509   | 0.525    |
| B14  | Consumer Staples       | 0.344    | 0.547   | 0.486    |
| B14  | Industrials            | 0.343    | 0.506   | 0.523    |
| B14  | Industrials            | 0.342    | 0.499   | 0.527    |
| B14  | Industrials            | 0.342    | 0.507   | 0.519    |
| B14  | Consumer Staples       | 0.338    | 0.554   | 0.461    |
| B14  | Health Care            | 0.338    | 0.532   | 0.482    |
| B14  | Industrials            | 0.337    | 0.497   | 0.515    |
| B15  | Consumer Staples       | 0.354    | 0.526   | 0.535    |
| B15  | Consumer Staples       | 0.347    | 0.523   | 0.517    |
| B15  | Health Care            | 0.345    | 0.535   | 0.500    |
| B15  | Health Care            | 0.344    | 0.543   | 0.489    |
| B15  | Health Care            | 0.343    | 0.538   | 0.491    |
| B15  | Industrials            | 0.342    | 0.498   | 0.527    |
| B15  | Consumer Staples       | 0.340    | 0.508   | 0.512    |
| B15  | Health Care            | 0.338    | 0.530   | 0.484    |
| B15  | Financials             | 0.338    | 0.510   | 0.504    |
| B15  | Industrials            | 0.338    | 0.481   | 0.532    |
| B16  | Consumer Staples       | 0.357    | 0.534   | 0.536    |
| B16  | Consumer Staples       | 0.354    | 0.522   | 0.540    |
| B16  | Industrials            | 0.348    | 0.518   | 0.526    |
| B16  | Industrials            | 0.344    | 0.517   | 0.514    |
| B16  | Industrials            | 0.343    | 0.512   | 0.517    |
| B16  | Consumer Staples       | 0.342    | 0.506   | 0.520    |
| B16  | Industrials            | 0.341    | 0.503   | 0.520    |
| B16  | Industrials            | 0.340    | 0.494   | 0.527    |
| B16  | Financials             | 0.337    | 0.521   | 0.492    |
| B16  | Consumer Discretionary | 0.337    | 0.499   | 0.513    |
| B17  | Health Care            | 0.380    | 0.192   | 0.194    |
| B17  | Consumer Staples       | 0.378    | 0.177   | 0.215    |
| B17  | Industrials            | 0.375    | 0.171   | 0.197    |
| B17  | Consumer Staples       | 0.375    | 0.237   | 0.277    |
| B17  | Financials             | 0.374    | 0.162   | 0.198    |
| B17  | Information Technology | 0.373    | 0.239   | 0.251    |
| B17  | Industrials            | 0.372    | 0.232   | 0.250    |
| B17  | Consumer Staples       | 0.372    | 0.264   | 0.313    |
| B17  | Consumer Staples       | 0.369    | 0.301   | 0.337    |
| B17  | Information Technology | 0.367    | 0.175   | 0.184    |
| B18  | Information Technology | 0.340    | 0.508   | 0.511    |
| B18  | Energy                 | 0.338    | 0.513   | 0.502    |
| B18  | Industrials            | 0.338    | 0.518   | 0.495    |
| B18  | Information Technology | 0.337    | 0.506   | 0.504    |
| B18  | Industrials            | 0.336    | 0.514   | 0.494    |
| B18  | Information Technology | 0.336    | 0.498   | 0.509    |
| B18  | Real Estate            | 0.336    | 0.545   | 0.462    |
| B18  | Information Technology | 0.335    | 0.503   | 0.503    |
| B18  | Health Care            | 0.335    | 0.506   | 0.499    |
| B18  | Real Estate            | 0.335    | 0.535   | 0.469    |
| B19  | Information Technology | 0.337    | 0.512   | 0.499    |
| B19  | Information Technology | 0.336    | 0.507   | 0.502    |
| B19  | Industrials            | 0.335    | 0.507   | 0.499    |
| B19  | Industrials            | 0.335    | 0.506   | 0.499    |
| B19  | Health Care            | 0.335    | 0.507   | 0.498    |
| B19  | Information Technology | 0.335    | 0.506   | 0.499    |
| B19  | Real Estate            | 0.335    | 0.535   | 0.470    |
| B19  | Real Estate            | 0.334    | 0.532   | 0.471    |
| B19  | Real Estate            | 0.334    | 0.527   | 0.475    |
| B19  | Consumer Discretionary | 0.334    | 0.521   | 0.481    |
| B20  | Consumer Staples       | 0.352    | 0.553   | 0.504    |
| B20  | Consumer Staples       | 0.349    | 0.550   | 0.498    |
| B20  | Consumer Staples       | 0.348    | 0.553   | 0.491    |
| B20  | Consumer Staples       | 0.343    | 0.560   | 0.468    |
| B20  | Health Care            | 0.341    | 0.530   | 0.493    |
| B20  | Health Care            | 0.340    | 0.536   | 0.484    |
| B20  | Health Care            | 0.339    | 0.528   | 0.490    |
| B20  | Real Estate            | 0.337    | 0.518   | 0.492    |
| B20  | Industrials            | 0.336    | 0.505   | 0.504    |
| B20  | Industrials            | 0.336    | 0.507   | 0.502    |
| B21  | Consumer Staples       | 0.352    | 0.553   | 0.504    |
| B21  | Consumer Staples       | 0.349    | 0.550   | 0.498    |
| B21  | Consumer Staples       | 0.348    | 0.553   | 0.491    |
| B21  | Consumer Staples       | 0.343    | 0.560   | 0.468    |
| B21  | Health Care            | 0.341    | 0.530   | 0.493    |
| B21  | Health Care            | 0.340    | 0.536   | 0.484    |
| B21  | Health Care            | 0.339    | 0.528   | 0.490    |
| B21  | Real Estate            | 0.337    | 0.518   | 0.492    |
| B21  | Industrials            | 0.336    | 0.505   | 0.504    |
| B21  | Industrials            | 0.336    | 0.507   | 0.502    |
| B22  | Consumer Staples       | 0.352    | 0.553   | 0.504    |
| B22  | Consumer Staples       | 0.349    | 0.550   | 0.498    |
| B22  | Consumer Staples       | 0.348    | 0.553   | 0.491    |
| B22  | Consumer Staples       | 0.343    | 0.560   | 0.468    |
| B22  | Health Care            | 0.341    | 0.530   | 0.493    |
| B22  | Health Care            | 0.340    | 0.536   | 0.484    |
| B22  | Health Care            | 0.339    | 0.528   | 0.490    |
| B22  | Real Estate            | 0.337    | 0.518   | 0.492    |
| B22  | Industrials            | 0.336    | 0.505   | 0.504    |
| B22  | Industrials            | 0.336    | 0.507   | 0.502    |
| B25  | Consumer Staples       | 0.352    | 0.553   | 0.504    |
| B25  | Consumer Staples       | 0.349    | 0.550   | 0.498    |
| B25  | Consumer Staples       | 0.348    | 0.553   | 0.491    |
| B25  | Consumer Staples       | 0.343    | 0.560   | 0.468    |
| B25  | Health Care            | 0.341    | 0.530   | 0.493    |
| B25  | Health Care            | 0.340    | 0.536   | 0.484    |
| B25  | Health Care            | 0.339    | 0.528   | 0.490    |
| B25  | Real Estate            | 0.337    | 0.518   | 0.492    |
| B25  | Industrials            | 0.336    | 0.505   | 0.504    |
| B25  | Industrials            | 0.336    | 0.507   | 0.502    |
| B26  | Consumer Staples       | 0.361    | 0.551   | 0.532    |
| B26  | Consumer Staples       | 0.357    | 0.547   | 0.523    |
| B26  | Consumer Staples       | 0.347    | 0.533   | 0.507    |
| B26  | Industrials            | 0.345    | 0.510   | 0.526    |
| B26  | Health Care            | 0.344    | 0.533   | 0.500    |
| B26  | Industrials            | 0.344    | 0.507   | 0.524    |
| B26  | Health Care            | 0.343    | 0.541   | 0.487    |
| B26  | Health Care            | 0.342    | 0.535   | 0.490    |
| B26  | Industrials            | 0.340    | 0.501   | 0.520    |
| B26  | Industrials            | 0.339    | 0.497   | 0.521    |
| B27  | Consumer Staples       | 0.361    | 0.551   | 0.532    |
| B27  | Consumer Staples       | 0.357    | 0.547   | 0.523    |
| B27  | Consumer Staples       | 0.347    | 0.533   | 0.507    |
| B27  | Industrials            | 0.345    | 0.510   | 0.526    |
| B27  | Health Care            | 0.344    | 0.533   | 0.500    |
| B27  | Industrials            | 0.344    | 0.507   | 0.524    |
| B27  | Health Care            | 0.343    | 0.541   | 0.487    |
| B27  | Health Care            | 0.342    | 0.535   | 0.490    |
| B27  | Industrials            | 0.340    | 0.501   | 0.520    |
| B27  | Industrials            | 0.339    | 0.497   | 0.521    |
| B30  | Consumer Staples       | 0.352    | 0.553   | 0.504    |
| B30  | Consumer Staples       | 0.349    | 0.550   | 0.498    |
| B30  | Consumer Staples       | 0.348    | 0.553   | 0.491    |
| B30  | Consumer Staples       | 0.343    | 0.560   | 0.468    |
| B30  | Health Care            | 0.341    | 0.530   | 0.493    |
| B30  | Health Care            | 0.340    | 0.536   | 0.484    |
| B30  | Health Care            | 0.339    | 0.528   | 0.490    |
| B30  | Real Estate            | 0.337    | 0.518   | 0.492    |
| B30  | Industrials            | 0.336    | 0.505   | 0.504    |
| B30  | Industrials            | 0.336    | 0.507   | 0.502    |
| B31  | Consumer Staples       | 0.347    | 0.535   | 0.506    |
| B31  | Consumer Staples       | 0.346    | 0.529   | 0.508    |
| B31  | Industrials            | 0.345    | 0.511   | 0.525    |
| B31  | Consumer Staples       | 0.345    | 0.533   | 0.501    |
| B31  | Industrials            | 0.344    | 0.507   | 0.526    |
| B31  | Industrials            | 0.339    | 0.500   | 0.518    |
| B31  | Industrials            | 0.339    | 0.498   | 0.518    |
| B31  | Industrials            | 0.338    | 0.500   | 0.514    |
| B31  | Health Care            | 0.337    | 0.513   | 0.498    |
| B31  | Consumer Staples       | 0.336    | 0.527   | 0.481    |
| B32  | Consumer Staples       | 0.360    | 0.551   | 0.527    |
| B32  | Consumer Staples       | 0.358    | 0.553   | 0.523    |
| B32  | Consumer Staples       | 0.345    | 0.536   | 0.499    |
| B32  | Industrials            | 0.344    | 0.506   | 0.525    |
| B32  | Industrials            | 0.343    | 0.511   | 0.519    |
| B32  | Industrials            | 0.343    | 0.506   | 0.523    |
| B32  | Consumer Staples       | 0.339    | 0.540   | 0.478    |
| B32  | Industrials            | 0.339    | 0.499   | 0.518    |
| B32  | Communication Services | 0.338    | 0.507   | 0.506    |
| B32  | Industrials            | 0.337    | 0.499   | 0.512    |
| B33  | Consumer Staples       | 0.357    | 0.541   | 0.531    |
| B33  | Consumer Staples       | 0.354    | 0.534   | 0.529    |
| B33  | Industrials            | 0.347    | 0.511   | 0.530    |
| B33  | Health Care            | 0.346    | 0.508   | 0.531    |
| B33  | Consumer Staples       | 0.346    | 0.519   | 0.518    |
| B33  | Industrials            | 0.344    | 0.502   | 0.532    |
| B33  | Industrials            | 0.342    | 0.504   | 0.523    |
| B33  | Health Care            | 0.340    | 0.500   | 0.521    |
| B33  | Financials             | 0.339    | 0.496   | 0.522    |
| B33  | Financials             | 0.339    | 0.495   | 0.523    |
| B34  | Consumer Staples       | 0.349    | 0.533   | 0.514    |
| B34  | Financials             | 0.341    | 0.481   | 0.541    |
| B34  | Industrials            | 0.341    | 0.495   | 0.527    |
| B34  | Industrials            | 0.341    | 0.498   | 0.524    |
| B34  | Health Care            | 0.340    | 0.488   | 0.532    |
| B34  | Industrials            | 0.340    | 0.492   | 0.528    |
| B34  | Consumer Staples       | 0.340    | 0.542   | 0.478    |
| B34  | Health Care            | 0.340    | 0.490   | 0.529    |
| B34  | Industrials            | 0.339    | 0.500   | 0.517    |
| B34  | Financials             | 0.339    | 0.505   | 0.510    |
| B35  | Financials             | 0.349    | 0.441   | 0.607    |
| B35  | Financials             | 0.341    | 0.415   | 0.608    |
| B35  | Consumer Discretionary | 0.337    | 0.489   | 0.522    |
| B35  | Industrials            | 0.336    | 0.484   | 0.523    |
| B35  | Consumer Discretionary | 0.335    | 0.465   | 0.540    |
| B35  | Financials             | 0.333    | 0.387   | 0.613    |
| B35  | Industrials            | 0.333    | 0.497   | 0.502    |
| B35  | Health Care            | 0.331    | 0.496   | 0.499    |
| B35  | Health Care            | 0.331    | 0.502   | 0.492    |
| B35  | Financials             | 0.331    | 0.380   | 0.612    |
| B36  | Financials             | 0.356    | 0.463   | 0.604    |
| B36  | Financials             | 0.339    | 0.398   | 0.620    |
| B36  | Consumer Discretionary | 0.337    | 0.475   | 0.536    |
| B36  | Industrials            | 0.336    | 0.487   | 0.523    |
| B36  | Financials             | 0.334    | 0.411   | 0.593    |
| B36  | Industrials            | 0.334    | 0.497   | 0.504    |
| B36  | Consumer Discretionary | 0.333    | 0.488   | 0.512    |
| B36  | Financials             | 0.333    | 0.394   | 0.605    |
| B36  | Information Technology | 0.333    | 0.494   | 0.504    |
| B36  | Industrials            | 0.333    | 0.493   | 0.505    |
| B37  | Energy                 | 0.343    | 0.531   | 0.497    |
| B37  | Communication Services | 0.337    | 0.478   | 0.532    |
| B37  | Industrials            | 0.336    | 0.511   | 0.497    |
| B37  | Industrials            | 0.336    | 0.523   | 0.484    |
| B37  | Health Care            | 0.335    | 0.509   | 0.496    |
| B37  | Information Technology | 0.334    | 0.495   | 0.508    |
| B37  | Industrials            | 0.333    | 0.512   | 0.488    |
| B37  | Industrials            | 0.333    | 0.509   | 0.491    |
| B37  | Industrials            | 0.333    | 0.497   | 0.502    |
| B37  | Utilities              | 0.333    | 0.494   | 0.504    |
| B38  | Consumer Staples       | 0.354    | 0.519   | 0.544    |
| B38  | Consumer Staples       | 0.347    | 0.526   | 0.514    |
| B38  | Consumer Staples       | 0.343    | 0.524   | 0.506    |
| B38  | Financials             | 0.341    | 0.536   | 0.488    |
| B38  | Financials             | 0.341    | 0.538   | 0.485    |
| B38  | Financials             | 0.340    | 0.540   | 0.481    |
| B38  | Health Care            | 0.340    | 0.530   | 0.490    |
| B38  | Consumer Staples       | 0.336    | 0.514   | 0.496    |
| B38  | Health Care            | 0.336    | 0.545   | 0.463    |
| B38  | Information Technology | 0.335    | 0.532   | 0.473    |
| B39  | Consumer Staples       | 0.361    | 0.551   | 0.532    |
| B39  | Consumer Staples       | 0.357    | 0.547   | 0.523    |
| B39  | Consumer Staples       | 0.347    | 0.533   | 0.507    |
| B39  | Industrials            | 0.345    | 0.510   | 0.526    |
| B39  | Health Care            | 0.344    | 0.533   | 0.500    |
| B39  | Industrials            | 0.344    | 0.507   | 0.524    |
| B39  | Health Care            | 0.343    | 0.541   | 0.487    |
| B39  | Health Care            | 0.342    | 0.535   | 0.490    |
| B39  | Industrials            | 0.340    | 0.501   | 0.520    |
| B39  | Industrials            | 0.339    | 0.497   | 0.521    |
| B40  | Consumer Staples       | 0.356    | 0.558   | 0.510    |
| B40  | Consumer Staples       | 0.347    | 0.539   | 0.503    |
| B40  | Industrials            | 0.346    | 0.507   | 0.530    |
| B40  | Industrials            | 0.344    | 0.507   | 0.525    |
| B40  | Industrials            | 0.342    | 0.501   | 0.525    |
| B40  | Industrials            | 0.342    | 0.502   | 0.524    |
| B40  | Consumer Staples       | 0.341    | 0.523   | 0.499    |
| B40  | Consumer Staples       | 0.338    | 0.535   | 0.479    |
| B40  | Health Care            | 0.338    | 0.515   | 0.497    |
| B40  | Industrials            | 0.337    | 0.497   | 0.514    |
| B41  | Consumer Staples       | 0.354    | 0.547   | 0.515    |
| B41  | Consumer Staples       | 0.351    | 0.544   | 0.510    |
| B41  | Industrials            | 0.345    | 0.503   | 0.532    |
| B41  | Industrials            | 0.345    | 0.506   | 0.529    |
| B41  | Consumer Staples       | 0.344    | 0.526   | 0.505    |
| B41  | Industrials            | 0.340    | 0.498   | 0.521    |
| B41  | Industrials            | 0.339    | 0.494   | 0.522    |
| B41  | Health Care            | 0.339    | 0.516   | 0.500    |
| B41  | Consumer Staples       | 0.338    | 0.529   | 0.484    |
| B41  | Industrials            | 0.337    | 0.499   | 0.513    |
| B42  | Consumer Staples       | 0.356    | 0.558   | 0.510    |
| B42  | Consumer Staples       | 0.347    | 0.539   | 0.503    |
| B42  | Industrials            | 0.346    | 0.507   | 0.530    |
| B42  | Industrials            | 0.344    | 0.507   | 0.525    |
| B42  | Industrials            | 0.342    | 0.501   | 0.525    |
| B42  | Industrials            | 0.342    | 0.502   | 0.524    |
| B42  | Consumer Staples       | 0.341    | 0.523   | 0.499    |
| B42  | Consumer Staples       | 0.338    | 0.535   | 0.479    |
| B42  | Health Care            | 0.338    | 0.515   | 0.497    |
| B42  | Industrials            | 0.337    | 0.497   | 0.514    |

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
| B1   | Energy                  | 0.297    | 0.428   | 0.464    |
| B1   | Energy                  | 0.298    | 0.447   | 0.448    |
| B1   | Energy                  | 0.310    | 0.452   | 0.478    |
| B1   | Information Technology  | 0.316    | 0.499   | 0.451    |
| B1   | Communication Services  | 0.317    | 0.506   | 0.446    |
| B1   | Utilities               | 0.319    | 0.524   | 0.434    |
| B1   | Energy                  | 0.319    | 0.476   | 0.482    |
| B1   | Utilities               | 0.320    | 0.540   | 0.421    |
| B1   | Materials               | 0.320    | 0.492   | 0.469    |
| B1   | Materials               | 0.321    | 0.463   | 0.501    |
| B2   | Energy                  | 0.296    | 0.431   | 0.458    |
| B2   | Energy                  | 0.297    | 0.448   | 0.443    |
| B2   | Energy                  | 0.308    | 0.443   | 0.481    |
| B2   | Materials               | 0.317    | 0.477   | 0.475    |
| B2   | Information Technology  | 0.318    | 0.497   | 0.456    |
| B2   | Energy                  | 0.318    | 0.473   | 0.480    |
| B2   | Communication Services  | 0.320    | 0.506   | 0.454    |
| B2   | Communication Services  | 0.320    | 0.507   | 0.454    |
| B2   | Utilities               | 0.321    | 0.548   | 0.414    |
| B2   | Materials               | 0.321    | 0.466   | 0.498    |
| B3   | Energy                  | 0.305    | 0.458   | 0.457    |
| B3   | Energy                  | 0.306    | 0.456   | 0.462    |
| B3   | Energy                  | 0.308    | 0.452   | 0.473    |
| B3   | Materials               | 0.317    | 0.496   | 0.456    |
| B3   | Energy                  | 0.318    | 0.481   | 0.473    |
| B3   | Information Technology  | 0.318    | 0.495   | 0.460    |
| B3   | Communication Services  | 0.320    | 0.512   | 0.447    |
| B3   | Utilities               | 0.320    | 0.547   | 0.414    |
| B3   | Materials               | 0.322    | 0.469   | 0.497    |
| B3   | Utilities               | 0.322    | 0.534   | 0.433    |
| B4   | Energy                  | 0.298    | 0.444   | 0.451    |
| B4   | Energy                  | 0.300    | 0.438   | 0.462    |
| B4   | Energy                  | 0.309    | 0.446   | 0.482    |
| B4   | Utilities               | 0.309    | 0.570   | 0.357    |
| B4   | Materials               | 0.312    | 0.468   | 0.468    |
| B4   | Utilities               | 0.316    | 0.563   | 0.384    |
| B4   | Utilities               | 0.316    | 0.545   | 0.403    |
| B4   | Materials               | 0.317    | 0.472   | 0.479    |
| B4   | Energy                  | 0.318    | 0.478   | 0.477    |
| B4   | Communication Services  | 0.320    | 0.511   | 0.448    |
| B5   | Energy                  | 0.292    | 0.433   | 0.442    |
| B5   | Energy                  | 0.298    | 0.459   | 0.436    |
| B5   | Energy                  | 0.310    | 0.466   | 0.464    |
| B5   | Utilities               | 0.312    | 0.553   | 0.382    |
| B5   | Materials               | 0.312    | 0.454   | 0.483    |
| B5   | Utilities               | 0.312    | 0.562   | 0.375    |
| B5   | Utilities               | 0.315    | 0.569   | 0.375    |
| B5   | Energy                  | 0.316    | 0.471   | 0.477    |
| B5   | Materials               | 0.317    | 0.465   | 0.486    |
| B5   | Materials               | 0.317    | 0.464   | 0.487    |
| B6   | Energy                  | 0.296    | 0.436   | 0.452    |
| B6   | Energy                  | 0.299    | 0.455   | 0.442    |
| B6   | Energy                  | 0.311    | 0.449   | 0.484    |
| B6   | Utilities               | 0.313    | 0.529   | 0.410    |
| B6   | Communication Services  | 0.317    | 0.505   | 0.447    |
| B6   | Energy                  | 0.318    | 0.479   | 0.476    |
| B6   | Communication Services  | 0.319    | 0.508   | 0.449    |
| B6   | Utilities               | 0.319    | 0.557   | 0.401    |
| B6   | Materials               | 0.322    | 0.466   | 0.499    |
| B6   | Information Technology  | 0.322    | 0.517   | 0.448    |
| B7   | Energy                  | 0.292    | 0.443   | 0.434    |
| B7   | Energy                  | 0.298    | 0.452   | 0.442    |
| B7   | Materials               | 0.306    | 0.461   | 0.458    |
| B7   | Energy                  | 0.306    | 0.458   | 0.462    |
| B7   | Utilities               | 0.308    | 0.568   | 0.356    |
| B7   | Utilities               | 0.311    | 0.549   | 0.384    |
| B7   | Utilities               | 0.314    | 0.539   | 0.402    |
| B7   | Materials               | 0.314    | 0.462   | 0.481    |
| B7   | Materials               | 0.318    | 0.468   | 0.484    |
| B7   | Energy                  | 0.319    | 0.477   | 0.479    |
| B8   | Energy                  | 0.292    | 0.420   | 0.455    |
| B8   | Energy                  | 0.301    | 0.449   | 0.454    |
| B8   | Utilities               | 0.307    | 0.564   | 0.358    |
| B8   | Utilities               | 0.308    | 0.570   | 0.354    |
| B8   | Materials               | 0.309    | 0.453   | 0.476    |
| B8   | Energy                  | 0.310    | 0.443   | 0.487    |
| B8   | Utilities               | 0.312    | 0.584   | 0.352    |
| B8   | Energy                  | 0.313    | 0.459   | 0.482    |
| B8   | Utilities               | 0.314    | 0.557   | 0.384    |
| B8   | Materials               | 0.317    | 0.459   | 0.491    |
| B9   | Energy                  | 0.310    | 0.472   | 0.457    |
| B9   | Energy                  | 0.310    | 0.471   | 0.461    |
| B9   | Materials               | 0.311    | 0.456   | 0.478    |
| B9   | Utilities               | 0.312    | 0.496   | 0.440    |
| B9   | Materials               | 0.312    | 0.446   | 0.490    |
| B9   | Materials               | 0.313    | 0.465   | 0.473    |
| B9   | Utilities               | 0.315    | 0.499   | 0.445    |
| B9   | Communication Services  | 0.318    | 0.518   | 0.435    |
| B9   | Communication Services  | 0.318    | 0.507   | 0.447    |
| B9   | Energy                  | 0.318    | 0.490   | 0.465    |
| B10  | Energy                  | 0.293    | 0.423   | 0.455    |
| B10  | Energy                  | 0.295    | 0.435   | 0.450    |
| B10  | Energy                  | 0.305    | 0.452   | 0.463    |
| B10  | Materials               | 0.306    | 0.462   | 0.457    |
| B10  | Utilities               | 0.310    | 0.569   | 0.361    |
| B10  | Utilities               | 0.311    | 0.563   | 0.368    |
| B10  | Utilities               | 0.312    | 0.540   | 0.396    |
| B10  | Energy                  | 0.314    | 0.467   | 0.476    |
| B10  | Materials               | 0.317    | 0.463   | 0.488    |
| B10  | Communication Services  | 0.319    | 0.510   | 0.447    |
| B11  | Energy                  | 0.295    | 0.413   | 0.471    |
| B11  | Energy                  | 0.301    | 0.428   | 0.474    |
| B11  | Energy                  | 0.310    | 0.444   | 0.485    |
| B11  | Utilities               | 0.314    | 0.565   | 0.376    |
| B11  | Utilities               | 0.314    | 0.561   | 0.380    |
| B11  | Utilities               | 0.315    | 0.543   | 0.403    |
| B11  | Energy                  | 0.316    | 0.473   | 0.474    |
| B11  | Materials               | 0.317    | 0.477   | 0.474    |
| B11  | Utilities               | 0.318    | 0.581   | 0.373    |
| B11  | Communication Services  | 0.320    | 0.506   | 0.455    |
| B12  | Energy                  | 0.306    | 0.460   | 0.457    |
| B12  | Energy                  | 0.307    | 0.442   | 0.479    |
| B12  | Materials               | 0.308    | 0.467   | 0.457    |
| B12  | Utilities               | 0.309    | 0.558   | 0.370    |
| B12  | Utilities               | 0.313    | 0.567   | 0.371    |
| B12  | Utilities               | 0.313    | 0.546   | 0.395    |
| B12  | Energy                  | 0.314    | 0.464   | 0.478    |
| B12  | Materials               | 0.316    | 0.462   | 0.486    |
| B12  | Communication Services  | 0.317    | 0.502   | 0.448    |
| B12  | Energy                  | 0.317    | 0.482   | 0.469    |
| B13  | Energy                  | 0.296    | 0.453   | 0.435    |
| B13  | Energy                  | 0.303    | 0.480   | 0.429    |
| B13  | Materials               | 0.304    | 0.468   | 0.445    |
| B13  | Energy                  | 0.313    | 0.467   | 0.471    |
| B13  | Energy                  | 0.315    | 0.460   | 0.484    |
| B13  | Communication Services  | 0.316    | 0.495   | 0.452    |
| B13  | Utilities               | 0.316    | 0.535   | 0.412    |
| B13  | Materials               | 0.317    | 0.465   | 0.487    |
| B13  | Materials               | 0.319    | 0.462   | 0.494    |
| B13  | Utilities               | 0.320    | 0.562   | 0.397    |
| B14  | Energy                  | 0.294    | 0.422   | 0.460    |
| B14  | Energy                  | 0.304    | 0.461   | 0.451    |
| B14  | Energy                  | 0.308    | 0.452   | 0.473    |
| B14  | Utilities               | 0.310    | 0.534   | 0.396    |
| B14  | Utilities               | 0.311    | 0.574   | 0.360    |
| B14  | Utilities               | 0.313    | 0.567   | 0.373    |
| B14  | Energy                  | 0.317    | 0.476   | 0.474    |
| B14  | Utilities               | 0.319    | 0.554   | 0.402    |
| B14  | Communication Services  | 0.320    | 0.519   | 0.441    |
| B14  | Information Technology  | 0.321    | 0.516   | 0.445    |
| B15  | Utilities               | 0.303    | 0.552   | 0.358    |
| B15  | Energy                  | 0.306    | 0.425   | 0.492    |
| B15  | Utilities               | 0.307    | 0.572   | 0.350    |
| B15  | Utilities               | 0.307    | 0.566   | 0.356    |
| B15  | Utilities               | 0.311    | 0.528   | 0.406    |
| B15  | Energy                  | 0.312    | 0.436   | 0.500    |
| B15  | Communication Services  | 0.313    | 0.504   | 0.435    |
| B15  | Communication Services  | 0.315    | 0.507   | 0.437    |
| B15  | Information Technology  | 0.316    | 0.516   | 0.431    |
| B15  | Utilities               | 0.316    | 0.545   | 0.403    |
| B16  | Energy                  | 0.288    | 0.434   | 0.429    |
| B16  | Energy                  | 0.291    | 0.442   | 0.431    |
| B16  | Energy                  | 0.305    | 0.465   | 0.449    |
| B16  | Materials               | 0.309    | 0.452   | 0.476    |
| B16  | Materials               | 0.310    | 0.469   | 0.460    |
| B16  | Utilities               | 0.310    | 0.541   | 0.389    |
| B16  | Materials               | 0.313    | 0.509   | 0.429    |
| B16  | Energy                  | 0.313    | 0.473   | 0.467    |
| B16  | Real Estate             | 0.314    | 0.477   | 0.464    |
| B16  | Utilities               | 0.318    | 0.545   | 0.409    |
| B17  | Consumer Discretionary  | NaN      | 0.000   | 0.000    |
| B17  | Health Care             | NaN      | 0.000   | 0.000    |
| B17  | Energy                  | 0.000    | 0.000   | 0.000    |
| B17  | Energy                  | 0.279    | 0.131   | 0.206    |
| B17  | Utilities               | 0.290    | 0.244   | 0.141    |
| B17  | Energy                  | 0.291    | 0.128   | 0.198    |
| B17  | Materials               | 0.291    | 0.190   | 0.154    |
| B17  | Materials               | 0.293    | 0.160   | 0.163    |
| B17  | Materials               | 0.313    | 0.161   | 0.153    |
| B17  | Real Estate             | 0.318    | 0.174   | 0.250    |
| B18  | Consumer Staples        | 0.318    | 0.489   | 0.465    |
| B18  | Materials               | 0.318    | 0.425   | 0.529    |
| B18  | Utilities               | 0.319    | 0.468   | 0.489    |
| B18  | Health Care             | 0.320    | 0.499   | 0.460    |
| B18  | Health Care             | 0.320    | 0.496   | 0.464    |
| B18  | Health Care             | 0.321    | 0.497   | 0.465    |
| B18  | Health Care             | 0.321    | 0.496   | 0.468    |
| B18  | Communication Services  | 0.322    | 0.496   | 0.470    |
| B18  | Consumer Staples        | 0.323    | 0.463   | 0.506    |
| B18  | Consumer Staples        | 0.323    | 0.481   | 0.489    |
| B19  | Consumer Staples        | 0.322    | 0.494   | 0.470    |
| B19  | Materials               | 0.322    | 0.445   | 0.521    |
| B19  | Utilities               | 0.323    | 0.488   | 0.483    |
| B19  | Communication Services  | 0.325    | 0.493   | 0.480    |
| B19  | Health Care             | 0.325    | 0.507   | 0.468    |
| B19  | Utilities               | 0.325    | 0.513   | 0.463    |
| B19  | Utilities               | 0.325    | 0.487   | 0.489    |
| B19  | Consumer Staples        | 0.326    | 0.479   | 0.498    |
| B19  | Materials               | 0.326    | 0.455   | 0.523    |
| B19  | Materials               | 0.326    | 0.466   | 0.512    |
| B20  | Energy                  | 0.297    | 0.428   | 0.464    |
| B20  | Energy                  | 0.300    | 0.450   | 0.450    |
| B20  | Energy                  | 0.308    | 0.441   | 0.482    |
| B20  | Utilities               | 0.309    | 0.570   | 0.357    |
| B20  | Materials               | 0.311    | 0.467   | 0.467    |
| B20  | Utilities               | 0.314    | 0.561   | 0.380    |
| B20  | Utilities               | 0.316    | 0.545   | 0.403    |
| B20  | Energy                  | 0.317    | 0.473   | 0.477    |
| B20  | Materials               | 0.317    | 0.470   | 0.480    |
| B20  | Materials               | 0.320    | 0.473   | 0.486    |
| B21  | Energy                  | 0.297    | 0.428   | 0.464    |
| B21  | Energy                  | 0.300    | 0.450   | 0.450    |
| B21  | Energy                  | 0.308    | 0.441   | 0.482    |
| B21  | Utilities               | 0.309    | 0.570   | 0.357    |
| B21  | Materials               | 0.311    | 0.467   | 0.467    |
| B21  | Utilities               | 0.314    | 0.561   | 0.380    |
| B21  | Utilities               | 0.316    | 0.545   | 0.403    |
| B21  | Energy                  | 0.317    | 0.473   | 0.477    |
| B21  | Materials               | 0.317    | 0.470   | 0.480    |
| B21  | Materials               | 0.320    | 0.473   | 0.486    |
| B22  | Energy                  | 0.297    | 0.428   | 0.464    |
| B22  | Energy                  | 0.300    | 0.450   | 0.450    |
| B22  | Energy                  | 0.308    | 0.441   | 0.482    |
| B22  | Utilities               | 0.309    | 0.570   | 0.357    |
| B22  | Materials               | 0.311    | 0.467   | 0.467    |
| B22  | Utilities               | 0.314    | 0.561   | 0.380    |
| B22  | Utilities               | 0.316    | 0.545   | 0.403    |
| B22  | Energy                  | 0.317    | 0.473   | 0.477    |
| B22  | Materials               | 0.317    | 0.470   | 0.480    |
| B22  | Materials               | 0.320    | 0.473   | 0.486    |
| B25  | Energy                  | 0.297    | 0.428   | 0.464    |
| B25  | Energy                  | 0.300    | 0.450   | 0.450    |
| B25  | Energy                  | 0.308    | 0.441   | 0.482    |
| B25  | Utilities               | 0.309    | 0.570   | 0.357    |
| B25  | Materials               | 0.311    | 0.467   | 0.467    |
| B25  | Utilities               | 0.314    | 0.561   | 0.380    |
| B25  | Utilities               | 0.316    | 0.545   | 0.403    |
| B25  | Energy                  | 0.317    | 0.473   | 0.477    |
| B25  | Materials               | 0.317    | 0.470   | 0.480    |
| B25  | Materials               | 0.320    | 0.473   | 0.486    |
| B26  | Energy                  | 0.293    | 0.422   | 0.458    |
| B26  | Energy                  | 0.297    | 0.441   | 0.449    |
| B26  | Energy                  | 0.308    | 0.454   | 0.469    |
| B26  | Utilities               | 0.310    | 0.571   | 0.358    |
| B26  | Utilities               | 0.311    | 0.563   | 0.368    |
| B26  | Utilities               | 0.312    | 0.539   | 0.397    |
| B26  | Energy                  | 0.313    | 0.466   | 0.474    |
| B26  | Communication Services  | 0.317    | 0.510   | 0.442    |
| B26  | Communication Services  | 0.319    | 0.510   | 0.445    |
| B26  | Information Technology  | 0.322    | 0.505   | 0.459    |
| B27  | Energy                  | 0.293    | 0.422   | 0.458    |
| B27  | Energy                  | 0.297    | 0.441   | 0.449    |
| B27  | Energy                  | 0.308    | 0.454   | 0.469    |
| B27  | Utilities               | 0.310    | 0.571   | 0.358    |
| B27  | Utilities               | 0.311    | 0.563   | 0.368    |
| B27  | Utilities               | 0.312    | 0.539   | 0.397    |
| B27  | Energy                  | 0.313    | 0.466   | 0.474    |
| B27  | Communication Services  | 0.317    | 0.510   | 0.442    |
| B27  | Communication Services  | 0.319    | 0.510   | 0.445    |
| B27  | Information Technology  | 0.322    | 0.505   | 0.459    |
| B30  | Energy                  | 0.297    | 0.428   | 0.464    |
| B30  | Energy                  | 0.300    | 0.450   | 0.450    |
| B30  | Energy                  | 0.308    | 0.441   | 0.482    |
| B30  | Utilities               | 0.309    | 0.570   | 0.357    |
| B30  | Materials               | 0.311    | 0.467   | 0.467    |
| B30  | Utilities               | 0.314    | 0.561   | 0.380    |
| B30  | Utilities               | 0.316    | 0.545   | 0.403    |
| B30  | Energy                  | 0.317    | 0.473   | 0.477    |
| B30  | Materials               | 0.317    | 0.470   | 0.480    |
| B30  | Materials               | 0.320    | 0.473   | 0.486    |
| B31  | Energy                  | 0.309    | 0.469   | 0.459    |
| B31  | Energy                  | 0.311    | 0.471   | 0.461    |
| B31  | Materials               | 0.311    | 0.446   | 0.489    |
| B31  | Materials               | 0.312    | 0.464   | 0.471    |
| B31  | Materials               | 0.313    | 0.459   | 0.480    |
| B31  | Utilities               | 0.313    | 0.498   | 0.440    |
| B31  | Utilities               | 0.315    | 0.499   | 0.445    |
| B31  | Energy                  | 0.319    | 0.487   | 0.468    |
| B31  | Communication Services  | 0.319    | 0.510   | 0.449    |
| B31  | Utilities               | 0.320    | 0.480   | 0.479    |
| B32  | Energy                  | 0.293    | 0.428   | 0.452    |
| B32  | Energy                  | 0.300    | 0.457   | 0.442    |
| B32  | Utilities               | 0.310    | 0.559   | 0.372    |
| B32  | Energy                  | 0.310    | 0.446   | 0.485    |
| B32  | Utilities               | 0.315    | 0.548   | 0.396    |
| B32  | Energy                  | 0.315    | 0.466   | 0.479    |
| B32  | Utilities               | 0.315    | 0.569   | 0.376    |
| B32  | Information Technology  | 0.319    | 0.514   | 0.443    |
| B32  | Utilities               | 0.319    | 0.556   | 0.401    |
| B32  | Materials               | 0.319    | 0.482   | 0.476    |
| B33  | Energy                  | 0.297    | 0.458   | 0.432    |
| B33  | Materials               | 0.304    | 0.464   | 0.446    |
| B33  | Energy                  | 0.305    | 0.484   | 0.431    |
| B33  | Energy                  | 0.312    | 0.454   | 0.483    |
| B33  | Energy                  | 0.312    | 0.471   | 0.466    |
| B33  | Communication Services  | 0.314    | 0.498   | 0.443    |
| B33  | Utilities               | 0.315    | 0.539   | 0.407    |
| B33  | Materials               | 0.317    | 0.462   | 0.488    |
| B33  | Materials               | 0.319    | 0.463   | 0.492    |
| B33  | Utilities               | 0.320    | 0.562   | 0.398    |
| B34  | Materials               | 0.304    | 0.464   | 0.448    |
| B34  | Energy                  | 0.309    | 0.494   | 0.434    |
| B34  | Energy                  | 0.310    | 0.501   | 0.430    |
| B34  | Energy                  | 0.315    | 0.496   | 0.448    |
| B34  | Energy                  | 0.316    | 0.496   | 0.451    |
| B34  | Materials               | 0.317    | 0.472   | 0.478    |
| B34  | Real Estate             | 0.320    | 0.439   | 0.521    |
| B34  | Utilities               | 0.320    | 0.568   | 0.392    |
| B34  | Utilities               | 0.321    | 0.562   | 0.401    |
| B34  | Materials               | 0.321    | 0.472   | 0.492    |
| B35  | Consumer Staples       | 0.286    | 0.332   | 0.527    |
| B35  | Consumer Staples       | 0.290    | 0.340   | 0.529    |
| B35  | Energy                 | 0.293    | 0.528   | 0.351    |
| B35  | Energy                 | 0.304    | 0.521   | 0.390    |
| B35  | Communication Services | 0.304    | 0.437   | 0.476    |
| B35  | Communication Services | 0.307    | 0.457   | 0.465    |
| B35  | Energy                 | 0.309    | 0.479   | 0.447    |
| B35  | Energy                 | 0.309    | 0.492   | 0.435    |
| B35  | Energy                 | 0.309    | 0.521   | 0.407    |
| B35  | Communication Services | 0.309    | 0.413   | 0.515    |
| B36  | Consumer Staples       | 0.292    | 0.341   | 0.535    |
| B36  | Consumer Staples       | 0.299    | 0.347   | 0.548    |
| B36  | Consumer Staples       | 0.299    | 0.360   | 0.536    |
| B36  | Energy                 | 0.299    | 0.528   | 0.371    |
| B36  | Communication Services | 0.304    | 0.401   | 0.510    |
| B36  | Energy                 | 0.304    | 0.521   | 0.390    |
| B36  | Communication Services | 0.305    | 0.423   | 0.492    |
| B36  | Energy                 | 0.308    | 0.515   | 0.408    |
| B36  | Communication Services | 0.310    | 0.442   | 0.487    |
| B36  | Consumer Staples       | 0.312    | 0.441   | 0.495    |
| B37  | Real Estate            | 0.247    | 0.301   | 0.440    |
| B37  | Real Estate            | 0.277    | 0.393   | 0.438    |
| B37  | Utilities              | 0.281    | 0.433   | 0.409    |
| B37  | Real Estate            | 0.291    | 0.445   | 0.430    |
| B37  | Utilities              | 0.293    | 0.508   | 0.371    |
| B37  | Energy                 | 0.299    | 0.516   | 0.381    |
| B37  | Real Estate            | 0.303    | 0.364   | 0.545    |
| B37  | Energy                 | 0.306    | 0.508   | 0.410    |
| B37  | Utilities              | 0.308    | 0.444   | 0.482    |
| B37  | Utilities              | 0.311    | 0.336   | 0.598    |
| B38  | Energy                 | 0.287    | 0.417   | 0.445    |
| B38  | Energy                 | 0.301    | 0.444   | 0.458    |
| B38  | Energy                 | 0.307    | 0.449   | 0.471    |
| B38  | Materials              | 0.318    | 0.458   | 0.496    |
| B38  | Energy                 | 0.319    | 0.470   | 0.485    |
| B38  | Materials              | 0.320    | 0.468   | 0.491    |
| B38  | Communication Services | 0.320    | 0.505   | 0.454    |
| B38  | Information Technology | 0.320    | 0.521   | 0.439    |
| B38  | Health Care            | 0.321    | 0.503   | 0.460    |
| B38  | Communication Services | 0.322    | 0.520   | 0.445    |
| B39  | Energy                 | 0.293    | 0.422   | 0.458    |
| B39  | Energy                 | 0.297    | 0.441   | 0.449    |
| B39  | Energy                 | 0.308    | 0.454   | 0.469    |
| B39  | Utilities              | 0.310    | 0.571   | 0.358    |
| B39  | Utilities              | 0.311    | 0.563   | 0.368    |
| B39  | Utilities              | 0.312    | 0.539   | 0.397    |
| B39  | Energy                 | 0.313    | 0.466   | 0.474    |
| B39  | Communication Services | 0.317    | 0.510   | 0.442    |
| B39  | Communication Services | 0.319    | 0.510   | 0.445    |
| B39  | Information Technology | 0.322    | 0.505   | 0.459    |
| B40  | Energy                 | 0.307    | 0.449   | 0.473    |
| B40  | Energy                 | 0.309    | 0.458   | 0.470    |
| B40  | Materials              | 0.310    | 0.436   | 0.495    |
| B40  | Energy                 | 0.311    | 0.441   | 0.492    |
| B40  | Materials              | 0.312    | 0.461   | 0.474    |
| B40  | Communication Services | 0.314    | 0.503   | 0.439    |
| B40  | Materials              | 0.315    | 0.449   | 0.495    |
| B40  | Utilities              | 0.316    | 0.576   | 0.372    |
| B40  | Utilities              | 0.316    | 0.543   | 0.406    |
| B40  | Energy                 | 0.317    | 0.486   | 0.464    |
| B41  | Energy                 | 0.291    | 0.420   | 0.453    |
| B41  | Energy                 | 0.296    | 0.436   | 0.451    |
| B41  | Materials              | 0.308    | 0.454   | 0.471    |
| B41  | Energy                 | 0.311    | 0.438   | 0.494    |
| B41  | Communication Services | 0.311    | 0.490   | 0.443    |
| B41  | Materials              | 0.313    | 0.456   | 0.482    |
| B41  | Energy                 | 0.313    | 0.457   | 0.483    |
| B41  | Utilities              | 0.313    | 0.555   | 0.385    |
| B41  | Materials              | 0.319    | 0.460   | 0.496    |
| B41  | Materials              | 0.320    | 0.456   | 0.503    |
| B42  | Energy                 | 0.307    | 0.449   | 0.473    |
| B42  | Energy                 | 0.309    | 0.458   | 0.470    |
| B42  | Materials              | 0.310    | 0.436   | 0.495    |
| B42  | Energy                 | 0.311    | 0.441   | 0.492    |
| B42  | Materials              | 0.312    | 0.461   | 0.474    |
| B42  | Communication Services | 0.314    | 0.503   | 0.439    |
| B42  | Materials              | 0.315    | 0.449   | 0.495    |
| B42  | Utilities              | 0.316    | 0.576   | 0.372    |
| B42  | Utilities              | 0.316    | 0.543   | 0.406    |
| B42  | Energy                 | 0.317    | 0.486   | 0.464    |

## 2.9 Diagnostic par régime de marché — Walk-Forward

| Test | Split | Début OOS  | Fin OOS    | Régime            | F1 macro | F1 short | F1 long | SPY % | VIX moy | Nb symb. |
|:-----|:------|:-----------|:-----------|:------------------|---------:|---------:|--------:|------:|--------:|---------:|
| B0   | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.315    | 0.438    | 0.508   | 7.7   | 15.0    | 11       |
| B0   | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.337    | 0.486    | 0.524   | 19.1  | 25.7    | 11       |
| B0   | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.325    | 0.464    | 0.511   | 9.8   | 18.8    | 11       |
| B0   | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.336    | 0.464    | 0.545   | 0.1   | 24.9    | 11       |
| B0   | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.316    | 0.487    | 0.461   | 9.0   | 15.1    | 11       |
| B0   | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.335    | 0.505    | 0.501   | 5.6   | 17.4    | 11       |
| B1   | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.317    | 0.437    | 0.515   | 7.7   | 15.0    | 11       |
| B1   | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.334    | 0.478    | 0.524   | 19.1  | 25.7    | 11       |
| B1   | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.324    | 0.455    | 0.516   | 9.8   | 18.8    | 11       |
| B1   | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.337    | 0.473    | 0.539   | 0.1   | 24.9    | 11       |
| B1   | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.317    | 0.482    | 0.470   | 9.0   | 15.1    | 11       |
| B1   | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.331    | 0.500    | 0.493   | 5.6   | 17.4    | 11       |
| B2   | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.317    | 0.441    | 0.511   | 7.7   | 15.0    | 11       |
| B2   | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.335    | 0.491    | 0.515   | 19.1  | 25.7    | 11       |
| B2   | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.327    | 0.464    | 0.516   | 9.8   | 18.8    | 11       |
| B2   | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.333    | 0.456    | 0.542   | 0.1   | 24.9    | 11       |
| B2   | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.315    | 0.482    | 0.462   | 9.0   | 15.1    | 11       |
| B2   | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.333    | 0.504    | 0.495   | 5.6   | 17.4    | 11       |
| B3   | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.311    | 0.424    | 0.509   | 7.7   | 15.0    | 11       |
| B3   | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.335    | 0.480    | 0.525   | 19.1  | 25.7    | 11       |
| B3   | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.326    | 0.459    | 0.518   | 9.8   | 18.8    | 11       |
| B3   | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.334    | 0.459    | 0.542   | 0.1   | 24.9    | 11       |
| B3   | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.317    | 0.483    | 0.469   | 9.0   | 15.1    | 11       |
| B3   | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.330    | 0.494    | 0.496   | 5.6   | 17.4    | 11       |
| B4   | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.319    | 0.437    | 0.520   | 7.7   | 15.0    | 11       |
| B4   | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.332    | 0.454    | 0.542   | 19.1  | 25.7    | 11       |
| B4   | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.321    | 0.453    | 0.511   | 9.8   | 18.8    | 11       |
| B4   | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.340    | 0.500    | 0.519   | 0.1   | 24.9    | 11       |
| B4   | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.321    | 0.494    | 0.469   | 9.0   | 15.1    | 11       |
| B4   | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.331    | 0.509    | 0.483   | 5.6   | 17.4    | 11       |
| B5   | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.319    | 0.440    | 0.516   | 7.7   | 15.0    | 11       |
| B5   | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.332    | 0.452    | 0.544   | 19.1  | 25.7    | 11       |
| B5   | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.327    | 0.463    | 0.516   | 9.8   | 18.8    | 11       |
| B5   | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.337    | 0.498    | 0.514   | 0.1   | 24.9    | 11       |
| B5   | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.317    | 0.493    | 0.459   | 9.0   | 15.1    | 11       |
| B5   | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.331    | 0.508    | 0.485   | 5.6   | 17.4    | 11       |
| B6   | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.322    | 0.445    | 0.520   | 7.7   | 15.0    | 11       |
| B6   | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.331    | 0.451    | 0.541   | 19.1  | 25.7    | 11       |
| B6   | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.325    | 0.458    | 0.516   | 9.8   | 18.8    | 11       |
| B6   | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.336    | 0.500    | 0.509   | 0.1   | 24.9    | 11       |
| B6   | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.318    | 0.488    | 0.467   | 9.0   | 15.1    | 11       |
| B6   | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.329    | 0.502    | 0.485   | 5.6   | 17.4    | 11       |
| B7   | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.318    | 0.437    | 0.517   | 7.7   | 15.0    | 11       |
| B7   | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.329    | 0.440    | 0.549   | 19.1  | 25.7    | 11       |
| B7   | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.321    | 0.450    | 0.514   | 9.8   | 18.8    | 11       |
| B7   | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.338    | 0.502    | 0.512   | 0.1   | 24.9    | 11       |
| B7   | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.322    | 0.494    | 0.472   | 9.0   | 15.1    | 11       |
| B7   | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.329    | 0.510    | 0.478   | 5.6   | 17.4    | 11       |
| B8   | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.324    | 0.451    | 0.520   | 7.7   | 15.0    | 11       |
| B8   | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.327    | 0.435    | 0.547   | 19.1  | 25.7    | 11       |
| B8   | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.322    | 0.462    | 0.504   | 9.8   | 18.8    | 11       |
| B8   | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.334    | 0.493    | 0.509   | 0.1   | 24.9    | 11       |
| B8   | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.315    | 0.490    | 0.455   | 9.0   | 15.1    | 11       |
| B8   | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.332    | 0.505    | 0.490   | 5.6   | 17.4    | 11       |
| B9   | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.320    | 0.473    | 0.495   | 7.7   | 15.0    | 11       |
| B9   | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.335    | 0.493    | 0.509   | 19.1  | 25.7    | 11       |
| B9   | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.322    | 0.458    | 0.508   | 9.8   | 18.8    | 11       |
| B9   | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.334    | 0.437    | 0.559   | 0.1   | 24.9    | 11       |
| B9   | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.314    | 0.486    | 0.462   | 9.0   | 15.1    | 11       |
| B9   | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.334    | 0.511    | 0.491   | 5.6   | 17.4    | 11       |
| B10  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.319    | 0.440    | 0.514   | 7.7   | 15.0    | 11       |
| B10  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.335    | 0.475    | 0.530   | 19.1  | 25.7    | 11       |
| B10  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.326    | 0.480    | 0.496   | 9.8   | 18.8    | 11       |
| B10  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.340    | 0.510    | 0.508   | 0.1   | 24.9    | 11       |
| B10  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.319    | 0.505    | 0.454   | 9.0   | 15.1    | 11       |
| B10  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.334    | 0.498    | 0.510   | 5.6   | 17.4    | 11       |
| B11  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.324    | 0.452    | 0.520   | 7.7   | 15.0    | 11       |
| B11  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.334    | 0.461    | 0.540   | 19.1  | 25.7    | 11       |
| B11  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.317    | 0.424    | 0.528   | 9.8   | 18.8    | 11       |
| B11  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.335    | 0.507    | 0.498   | 0.1   | 24.9    | 11       |
| B11  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.318    | 0.486    | 0.470   | 9.0   | 15.1    | 11       |
| B11  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.329    | 0.494    | 0.492   | 5.6   | 17.4    | 11       |
| B12  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.321    | 0.438    | 0.525   | 7.7   | 15.0    | 11       |
| B12  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.331    | 0.447    | 0.546   | 19.1  | 25.7    | 11       |
| B12  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.324    | 0.459    | 0.512   | 9.8   | 18.8    | 11       |
| B12  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.343    | 0.500    | 0.529   | 0.1   | 24.9    | 11       |
| B12  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.319    | 0.493    | 0.464   | 9.0   | 15.1    | 11       |
| B12  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.329    | 0.507    | 0.481   | 5.6   | 17.4    | 11       |
| B13  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.324    | 0.444    | 0.528   | 7.7   | 15.0    | 11       |
| B13  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.336    | 0.470    | 0.537   | 19.1  | 25.7    | 11       |
| B13  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.326    | 0.510    | 0.467   | 9.8   | 18.8    | 11       |
| B13  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.342    | 0.516    | 0.511   | 0.1   | 24.9    | 11       |
| B13  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.322    | 0.517    | 0.449   | 9.0   | 15.1    | 11       |
| B13  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.326    | 0.478    | 0.499   | 5.6   | 17.4    | 11       |
| B14  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.320    | 0.438    | 0.521   | 7.7   | 15.0    | 11       |
| B14  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.331    | 0.442    | 0.550   | 19.1  | 25.7    | 11       |
| B14  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.322    | 0.454    | 0.512   | 9.8   | 18.8    | 11       |
| B14  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.337    | 0.496    | 0.514   | 0.1   | 24.9    | 11       |
| B14  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.321    | 0.495    | 0.467   | 9.0   | 15.1    | 11       |
| B14  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.330    | 0.502    | 0.488   | 5.6   | 17.4    | 11       |
| B15  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.326    | 0.465    | 0.514   | 7.7   | 15.0    | 11       |
| B15  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.323    | 0.452    | 0.518   | 19.1  | 25.7    | 11       |
| B15  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.310    | 0.447    | 0.484   | 9.8   | 18.8    | 11       |
| B15  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.345    | 0.518    | 0.518   | 0.1   | 24.9    | 11       |
| B15  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.325    | 0.498    | 0.477   | 9.0   | 15.1    | 11       |
| B15  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.328    | 0.496    | 0.487   | 5.6   | 17.4    | 11       |
| B16  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.324    | 0.451    | 0.521   | 7.7   | 15.0    | 11       |
| B16  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.332    | 0.469    | 0.526   | 19.1  | 25.7    | 11       |
| B16  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.326    | 0.458    | 0.518   | 9.8   | 18.8    | 11       |
| B16  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.338    | 0.472    | 0.542   | 0.1   | 24.9    | 11       |
| B16  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.313    | 0.495    | 0.445   | 9.0   | 15.1    | 11       |
| B16  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.326    | 0.492    | 0.485   | 5.6   | 17.4    | 11       |
| B17  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.320    | 0.211    | 0.230   | 7.7   | 15.0    | 11       |
| B17  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.317    | 0.183    | 0.217   | 19.1  | 25.7    | 11       |
| B17  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.318    | 0.230    | 0.209   | 9.8   | 18.8    | 11       |
| B17  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.311    | 0.195    | 0.158   | 0.1   | 24.9    | 11       |
| B17  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.316    | 0.272    | 0.186   | 9.0   | 15.1    | 11       |
| B17  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.317    | 0.260    | 0.198   | 5.6   | 17.4    | 11       |
| B18  | 0     | 2014-07-03 | 2014-12-31 | —                 | 0.341    | 0.495    | 0.528   | 3.7   | —       | 11       |
| B18  | 1     | 2015-07-06 | 2015-12-31 | —                 | 0.328    | 0.508    | 0.475   | -1.4  | —       | 11       |
| B18  | 2     | 2016-07-05 | 2016-12-30 | —                 | 0.329    | 0.498    | 0.489   | 7.3   | —       | 11       |
| B18  | 3     | 2017-07-05 | 2018-01-02 | 🟢 Bull           | 0.332    | 0.522    | 0.473   | 10.7  | 9.8     | 11       |
| B18  | 4     | 2018-07-05 | 2019-01-03 | 🔵 Range low vol  | 0.326    | 0.487    | 0.491   | -10.6 | 17.1    | 11       |
| B18  | 5     | 2019-07-08 | 2020-01-03 | 🟢 Bull           | 0.322    | 0.466    | 0.501   | 8.6   | 15.0    | 11       |
| B18  | 6     | 2020-07-07 | 2021-01-04 | 🔵 Range low vol  | 0.327    | 0.453    | 0.528   | 17.5  | 25.7    | 11       |
| B18  | 7     | 2021-07-07 | 2022-02-01 | 🔵 Range low vol  | 0.316    | 0.425    | 0.523   | 4.3   | 19.5    | 11       |
| B19  | 0     | 2014-07-03 | 2014-12-31 | —                 | 0.341    | 0.495    | 0.528   | 3.7   | —       | 11       |
| B19  | 1     | 2015-07-06 | 2015-12-31 | —                 | 0.328    | 0.508    | 0.475   | -1.4  | —       | 11       |
| B19  | 2     | 2016-07-05 | 2016-12-30 | —                 | 0.329    | 0.498    | 0.489   | 7.3   | —       | 11       |
| B19  | 3     | 2017-07-05 | 2018-01-02 | 🟢 Bull           | 0.332    | 0.522    | 0.473   | 10.7  | 9.8     | 11       |
| B19  | 4     | 2018-07-05 | 2019-01-03 | 🔵 Range low vol  | 0.326    | 0.487    | 0.491   | -10.6 | 17.1    | 11       |
| B19  | 5     | 2019-07-08 | 2020-01-03 | 🟢 Bull           | 0.322    | 0.466    | 0.501   | 8.6   | 15.0    | 11       |
| B19  | 6     | 2020-07-07 | 2021-01-04 | 🔵 Range low vol  | 0.327    | 0.453    | 0.528   | 17.5  | 25.7    | 11       |
| B19  | 7     | 2021-07-07 | 2022-02-01 | 🔵 Range low vol  | 0.316    | 0.425    | 0.523   | 4.3   | 19.5    | 11       |
| B19  | 8     | 2022-08-04 | 2023-02-02 | 🟠 Range high vol | 0.342    | 0.500    | 0.526   | 0.6   | 24.1    | 11       |
| B19  | 9     | 2023-08-07 | 2024-03-05 | 🟢 Bull           | 0.314    | 0.487    | 0.455   | 12.5  | 14.9    | 11       |
| B19  | 10    | 2024-09-05 | 2025-03-07 | 🔵 Range low vol  | 0.335    | 0.500    | 0.506   | 4.8   | 17.5    | 11       |
| B20  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.319    | 0.437    | 0.520   | 7.7   | 15.0    | 11       |
| B20  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.332    | 0.454    | 0.542   | 19.1  | 25.7    | 11       |
| B20  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.321    | 0.447    | 0.516   | 9.8   | 18.8    | 11       |
| B20  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.340    | 0.497    | 0.524   | 0.1   | 24.9    | 11       |
| B20  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.316    | 0.489    | 0.460   | 9.0   | 15.1    | 11       |
| B20  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.327    | 0.502    | 0.480   | 5.6   | 17.4    | 11       |
| B21  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.319    | 0.437    | 0.520   | 7.7   | 15.0    | 11       |
| B21  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.332    | 0.454    | 0.542   | 19.1  | 25.7    | 11       |
| B21  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.321    | 0.447    | 0.516   | 9.8   | 18.8    | 11       |
| B21  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.340    | 0.497    | 0.524   | 0.1   | 24.9    | 11       |
| B21  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.316    | 0.489    | 0.460   | 9.0   | 15.1    | 11       |
| B21  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.327    | 0.502    | 0.480   | 5.6   | 17.4    | 11       |
| B22  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.319    | 0.437    | 0.520   | 7.7   | 15.0    | 11       |
| B22  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.332    | 0.454    | 0.542   | 19.1  | 25.7    | 11       |
| B22  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.321    | 0.447    | 0.516   | 9.8   | 18.8    | 11       |
| B22  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.340    | 0.497    | 0.524   | 0.1   | 24.9    | 11       |
| B22  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.316    | 0.489    | 0.460   | 9.0   | 15.1    | 11       |
| B22  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.327    | 0.502    | 0.480   | 5.6   | 17.4    | 11       |
| B25  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.320    | 0.435    | 0.524   | 7.7   | 15.0    | 11       |
| B25  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.330    | 0.453    | 0.537   | 19.1  | 25.7    | 11       |
| B25  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.326    | 0.465    | 0.513   | 9.8   | 18.8    | 11       |
| B25  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.335    | 0.485    | 0.521   | 0.1   | 24.9    | 11       |
| B25  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.320    | 0.492    | 0.469   | 9.0   | 15.1    | 11       |
| B25  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.332    | 0.509    | 0.486   | 5.6   | 17.4    | 11       |
| B26  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.320    | 0.435    | 0.524   | 7.7   | 15.0    | 11       |
| B26  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.330    | 0.453    | 0.537   | 19.1  | 25.7    | 11       |
| B26  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.326    | 0.465    | 0.513   | 9.8   | 18.8    | 11       |
| B26  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.335    | 0.485    | 0.521   | 0.1   | 24.9    | 11       |
| B26  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.320    | 0.492    | 0.469   | 9.0   | 15.1    | 11       |
| B26  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.332    | 0.509    | 0.486   | 5.6   | 17.4    | 11       |
| B27  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.320    | 0.435    | 0.524   | 7.7   | 15.0    | 11       |
| B27  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.330    | 0.453    | 0.537   | 19.1  | 25.7    | 11       |
| B27  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.326    | 0.465    | 0.513   | 9.8   | 18.8    | 11       |
| B27  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.335    | 0.485    | 0.521   | 0.1   | 24.9    | 11       |
| B27  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.320    | 0.492    | 0.469   | 9.0   | 15.1    | 11       |
| B27  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.332    | 0.509    | 0.486   | 5.6   | 17.4    | 11       |
| B30  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.319    | 0.437    | 0.520   | 7.7   | 15.0    | 11       |
| B30  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.332    | 0.454    | 0.542   | 19.1  | 25.7    | 11       |
| B30  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.321    | 0.447    | 0.516   | 9.8   | 18.8    | 11       |
| B30  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.340    | 0.497    | 0.524   | 0.1   | 24.9    | 11       |
| B30  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.316    | 0.489    | 0.460   | 9.0   | 15.1    | 11       |
| B30  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.327    | 0.502    | 0.480   | 5.6   | 17.4    | 11       |
| B31  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.321    | 0.467    | 0.496   | 7.7   | 15.0    | 11       |
| B31  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.337    | 0.509    | 0.502   | 19.1  | 25.7    | 11       |
| B31  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.329    | 0.493    | 0.494   | 9.8   | 18.8    | 11       |
| B31  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.329    | 0.459    | 0.528   | 0.1   | 24.9    | 11       |
| B31  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.317    | 0.464    | 0.487   | 9.0   | 15.1    | 11       |
| B31  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.322    | 0.482    | 0.484   | 5.6   | 17.4    | 11       |
| B32  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.321    | 0.438    | 0.525   | 7.7   | 15.0    | 11       |
| B32  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.331    | 0.447    | 0.546   | 19.1  | 25.7    | 11       |
| B32  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.324    | 0.457    | 0.514   | 9.8   | 18.8    | 11       |
| B32  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.343    | 0.503    | 0.526   | 0.1   | 24.9    | 11       |
| B32  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.318    | 0.490    | 0.465   | 9.0   | 15.1    | 11       |
| B32  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.327    | 0.503    | 0.478   | 5.6   | 17.4    | 11       |
| B33  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.324    | 0.444    | 0.528   | 7.7   | 15.0    | 11       |
| B33  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.336    | 0.471    | 0.537   | 19.1  | 25.7    | 11       |
| B33  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.324    | 0.507    | 0.465   | 9.8   | 18.8    | 11       |
| B33  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.343    | 0.517    | 0.511   | 0.1   | 24.9    | 11       |
| B33  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.323    | 0.520    | 0.450   | 9.0   | 15.1    | 11       |
| B33  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.322    | 0.471    | 0.496   | 5.6   | 17.4    | 11       |
| B34  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.324    | 0.451    | 0.521   | 7.7   | 15.0    | 11       |
| B34  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.335    | 0.500    | 0.505   | 19.1  | 25.7    | 11       |
| B34  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.320    | 0.494    | 0.465   | 9.8   | 18.8    | 11       |
| B34  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.335    | 0.487    | 0.519   | 0.1   | 24.9    | 11       |
| B34  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.322    | 0.514    | 0.454   | 9.0   | 15.1    | 11       |
| B34  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.328    | 0.475    | 0.508   | 5.6   | 17.4    | 11       |
| B35  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.324    | 0.433    | 0.540   | 7.7   | 15.0    | 6        |
| B35  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.318    | 0.490    | 0.464   | 19.1  | 25.7    | 6        |
| B35  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.285    | 0.362    | 0.492   | 9.8   | 18.8    | 6        |
| B35  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.288    | 0.349    | 0.516   | 0.1   | 24.9    | 6        |
| B35  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.345    | 0.563    | 0.471   | 9.0   | 15.1    | 6        |
| B35  | 5     | 2024-09-03 | 2025-03-05 | 🔵 Range low vol  | 0.334    | 0.552    | 0.451   | 5.6   | 17.4    | 6        |
| B36  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.329    | 0.440    | 0.546   | 7.7   | 15.0    | 6        |
| B36  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.331    | 0.518    | 0.475   | 19.1  | 25.7    | 6        |
| B36  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.292    | 0.389    | 0.487   | 9.8   | 18.8    | 6        |
| B36  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.294    | 0.364    | 0.517   | 0.1   | 24.9    | 6        |
| B36  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.339    | 0.557    | 0.458   | 9.0   | 15.1    | 6        |
| B36  | 5     | 2024-09-03 | 2025-03-05 | 🔵 Range low vol  | 0.331    | 0.548    | 0.443   | 5.6   | 17.4    | 6        |
| B37  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.341    | 0.506    | 0.516   | 7.7   | 15.0    | 9        |
| B37  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.328    | 0.494    | 0.491   | 19.1  | 25.7    | 9        |
| B37  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.323    | 0.460    | 0.507   | 9.8   | 18.8    | 9        |
| B37  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.305    | 0.380    | 0.535   | 0.1   | 24.9    | 9        |
| B37  | 3     | 2023-04-06 | 2023-11-02 | 🟢 Bull           | 0.268    | 0.260    | 0.545   | 5.3   | 16.2    | 1        |
| B37  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.320    | 0.501    | 0.460   | 9.0   | 15.1    | 10       |
| B37  | 4     | 2024-05-07 | 2024-12-03 | 🟢 Bull           | 0.322    | 0.396    | 0.571   | 16.8  | 16.3    | 1        |
| B37  | 5     | 2024-09-03 | 2025-03-05 | 🔵 Range low vol  | 0.312    | 0.488    | 0.448   | 5.6   | 17.4    | 10       |
| B37  | 5     | 2025-06-09 | 2025-12-02 | 🟢 Bull           | 0.288    | 0.457    | 0.408   | 13.6  | 17.3    | 1        |
| B38  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.317    | 0.445    | 0.507   | 7.7   | 15.0    | 11       |
| B38  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.334    | 0.459    | 0.542   | 19.1  | 25.7    | 11       |
| B38  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.312    | 0.441    | 0.496   | 9.8   | 18.8    | 11       |
| B38  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.332    | 0.453    | 0.543   | 0.1   | 24.9    | 11       |
| B38  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.317    | 0.497    | 0.455   | 9.0   | 15.1    | 11       |
| B38  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.341    | 0.511    | 0.511   | 5.6   | 17.4    | 11       |
| B39  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.320    | 0.435    | 0.524   | 7.7   | 15.0    | 11       |
| B39  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.330    | 0.453    | 0.537   | 19.1  | 25.7    | 11       |
| B39  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.326    | 0.465    | 0.513   | 9.8   | 18.8    | 11       |
| B39  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.335    | 0.485    | 0.521   | 0.1   | 24.9    | 11       |
| B39  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.320    | 0.492    | 0.469   | 9.0   | 15.1    | 11       |
| B39  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.332    | 0.509    | 0.486   | 5.6   | 17.4    | 11       |
| B40  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.324    | 0.442    | 0.530   | 7.7   | 15.0    | 11       |
| B40  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.327    | 0.443    | 0.538   | 19.1  | 25.7    | 11       |
| B40  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.326    | 0.478    | 0.499   | 9.8   | 18.8    | 11       |
| B40  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.344    | 0.502    | 0.530   | 0.1   | 24.9    | 11       |
| B40  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.328    | 0.515    | 0.470   | 9.0   | 15.1    | 11       |
| B40  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.324    | 0.504    | 0.468   | 5.6   | 17.4    | 11       |
| B41  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.325    | 0.444    | 0.530   | 7.7   | 15.0    | 11       |
| B41  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.329    | 0.445    | 0.540   | 19.1  | 25.7    | 11       |
| B41  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.322    | 0.473    | 0.492   | 9.8   | 18.8    | 11       |
| B41  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.339    | 0.490    | 0.528   | 0.1   | 24.9    | 11       |
| B41  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.324    | 0.512    | 0.461   | 9.0   | 15.1    | 11       |
| B41  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.326    | 0.506    | 0.472   | 5.6   | 17.4    | 11       |
| B42  | 0     | 2019-07-03 | 2019-12-31 | 🟢 Bull           | 0.324    | 0.442    | 0.530   | 7.7   | 15.0    | 11       |
| B42  | 1     | 2020-07-02 | 2020-12-30 | 🔵 Range low vol  | 0.327    | 0.443    | 0.538   | 19.1  | 25.7    | 11       |
| B42  | 2     | 2021-07-02 | 2021-12-30 | 🔵 Range low vol  | 0.326    | 0.478    | 0.499   | 9.8   | 18.8    | 11       |
| B42  | 3     | 2022-07-05 | 2022-12-30 | 🟠 Range high vol | 0.344    | 0.502    | 0.530   | 0.1   | 24.9    | 11       |
| B42  | 4     | 2023-08-03 | 2024-02-01 | 🟢 Bull           | 0.328    | 0.515    | 0.470   | 9.0   | 15.1    | 11       |
| B42  | 5     | 2024-09-03 | 2025-03-05 | 🟢 Bull           | 0.324    | 0.504    | 0.468   | 5.6   | 17.4    | 11       |

---

## 📝 Notes & Observations

- **B0 (Baseline)** : Catboost 5/5 Global. LightGBM per-sector 6/11. IC Rank 0.0186.
- **B1** : +sentiment. Aucun gain.
- **B2** : +screener (166 feat). ⚠️ IC IR 0.97. H15/H20 up, H3/H5/H10 down.
- **B3** : +short-score. 🏆 IC Rank 0.0202, IC IR H10=1.47 record.
- **B4** : B3 + `--target-excess-vs-spy`. 🏆 **MEILLEUR BATCH !** IC Rank 0.0202, F1 long H5=0.514 (record), Dir Acc H15=0.5022. LightGBM per-sector 8/11. V2=−7.1%, V3=−24.8%. **Batch recommandé pour la production.**
- **B5** : B4 + VIX. Per-Sector dégradé (F1 long H5 0.514→0.510).
- **B6** : B4 + VXN. Per-Sector comparable à B4. IT dans le top 10.
- **B7** : B4 + VIX3M. Per-Sector légèrement en retrait. Split 1 F1 long=0.549 record.
- **B8** : B4 + MOVE. ❌ Pire variante B4 pour Per-Sector.
- **B9** : B4 + Fondamentaux. ❌❌ PIRE BATCH. IC Rank −22%.
- **B10** : B4 + CAPM. 🤔 MITIGÉ. IC IR record 1.09. H3/H5 fortement améliorés. Mais H10/H15 dégradés. **V2=−1.9% (record !)** — le filtre H5 rising est quasi neutre en H10, excellente nouvelle pour la robustesse.
- **B11** : B4 + `--include-macro-regime`. Aucun gain vs B4. Global identique (IC Rank 0.0202, même backtest V2=−7.1%). Per-Sector légèrement dégradé (lightgbm 7 vs 8). Le macro regime n'apporte rien.
- **B12** : B4 SANS `--no-include-score-components` (score components inclus, 153 feat). ⚠️ EFFET MIXTE. Global dégradé (IC Rank 0.0188, IC IR 0.92, best horizon passe à H15). Mais Per-Sector **lightgbm 10/11 (record !)** et **V2=−2.5%** (2ᵉ meilleur après B10). Les score components nuisent au Global mais boostent le Per-Sector.
- **B13** : B4 + `--enable-cross-sectional`. ❌❌ **PIRE BATCH**. IC Rank 0.0144 (−29% vs B4), IC IR 0.84 (−18%), V2=−16.9% (le pire), V3=−47.1%. Les features cross-sectional (z-scores sectoriels, rangs relatifs) détruisent le signal. **À ne pas utiliser.**
- **B14** : B4 + `--enable-global-stacking`. 🔥 **V2=−0.1% (record absolu !)** Le stacking injecte `global_rank` dans le per-sector → backtest quasi-neutre avec filtre H5 rising. F1 long H5 maintenu à 0.514. IC légèrement ↓ (0.0196). **Nouveau champion backtest.**
- **B15** : B4 + `--target-skip-vol-scaling` (T1). V2=−0.1% mais Per-Sector dégradé : F1 long H5 0.503 (−0.011), CatBoost reprend 7/11. Le vol scaling est crucial pour le F1 long.
- **B16** : B4 + `--target-intra-sector-rank` (T2). V2=−0.1% mais Dir Acc < 0.50 partout, F1 long H5 0.504 (−0.010). Le rang intra-secteur ne fonctionne pas.
- **B17** : B4 + `--target-ternary-intra-sector` (T3, quantile 0.3). ❌❌ **ÉCHEC**. Le target ternaire (short/flat/long) fait que le modèle prédit massivement « flat » (72% des prédictions catboost WF). F1 long/short s'effondrent (0.15-0.24). Dir Acc WF=0.475. NaN sur Consumer Discretionary et Health Care (modèles mono-classe). Le target binaire reste supérieur.
- **B18** : B4 + `--training-start-date 2011-01-01` + 8 splits. ⚠️ **DÉGRADÉ**. Ajouter 2011-2015 réduit l'IC Rank de 0.0202→0.0165 (−18%), IC IR de 1.03→0.66 (−36%). H5 devient meilleur horizon. CatBoost Per-Sector reprend l'avantage (7/11). V4=−3.8%. Les données anciennes ajoutent du bruit sans améliorer le signal.
- **B19** : B4 + from 2011 + 16 splits max (11 effectifs). ❌ **CONFIRME B18**. IC Rank 0.0157 (−22% vs B4). Plus de splits = encore plus de dégradation. V4=−15.3%. La période 2011-2015 dilue le signal, quel que soit le nombre de splits. **Conclusion : rester sur training_start_date=2016-01-01.**
- **B20** : B4 + YetiRank. 🔥🔥 **IC RECORD 0.0238 (+18% vs B4)**. YetiRank gagne 4/5 horizons : H3 +64%, H5 +16%, H15 +19%, H20 +18%. Seul H10 reste meilleur en RMSE (IC −1%, IR −29%). V2=−10.1%. **Nouveau champion IC Global.** Prochaine étape : per-horizon specialization (YetiRank H3/H5/H15/H20 + RMSE H10).
- **B21** : B4 + QueryRMSE. ❌ IC 0.0188 (−7% vs B4), IR 0.92. H15 perdu par CatBoost face à LightGBM. H10/H15/H20 tous dégradés.
- **B22** : B4 + QuerySoftMax. ❌ IC 0.0185 (−8% vs B4), IR 0.89. Mêmes problèmes que B21 : H15 perdu, horizons longs dégradés. **QueryRMSE et QuerySoftMax sont inférieurs à RMSE.**
- **B25** : B10 + YetiRank (= B4 + CAPM + YetiRank). 🔥🔥🔥 **NOUVEAU RECORD IC 0.0241 (+19% vs B4, +1.3% vs B20)**. IR 1.07. CAPM + YetiRank se complètent : H5 +5%, H10 +11% vs B20. H15/H20 légèrement en retrait vs B20 (−6%/0%). Backtest V2=−2.6%. **Nouveau champion IC Global et H5/H10.**
- **B26** : B10 + QueryRMSE (= B4 + CAPM + QueryRMSE). ❌ IC 0.0172 (−15% vs B4, −12% vs B10). IR 0.97. CAPM n'aide pas QueryRMSE, QueryRMSE dégrade CAPM. H3 s'effondre à 0.0099 (−23% vs B10). **Confirme que QueryRMSE est inférieur à RMSE, même avec CAPM.**
- **B27** : B10 + QuerySoftMax (= B4 + CAPM + QuerySoftMax). ❌ IC 0.0161 (−20% vs B4, −33% vs B25). IR 0.95. Pire batch de la série CAPM. H10 s'effondre (0.0142). **Confirme que QuerySoftMax est inférieur à RMSE, même avec CAPM.**
- **🎯 Matrice finale losses × CAPM** : YetiRank+CAPM = 0.0241 🏆 (seule interaction positive), YetiRank seul = 0.0238, RMSE = 0.0202, QueryRMSE/SoftMax = 0.0161-0.0188 ❌.
- **B30** : B20 + P1-3 (raw rank target). ❌ **ÉCHEC** — IC 0.0153 (−36% vs B20), IR 0.49. Le raw rank détruit H5/H15/H20, CatBoost YetiRank s'effondre (H15 −0.0006, H20 −0.0043) et perd 3/5 horizons face à LightGBM LambdaRank. Seul H3 profite (+23%). **Le pipeline complet (smoothing + sector-neutral + factor-neutral) est essentiel, surtout sur les horizons longs. P1-3 clos.**
- **B31** : B4 + fondamentaux + YetiRank. ❌ **ÉCHEC** — IC 0.0146 (−28% vs B4, −39% vs B25), IR 0.66. Les fondamentaux restent toxiques même avec YetiRank (encore pire que B9 RMSE : 0.0146 vs 0.0157). `--target-excess-vs-spy` est mathématiquement neutre pour le ranking (constante par date). LightGBM s'effondre à H10-H20 (IC ≤ 0, négatif en splits 5-6). H10 Decile Spread 0.0080 = 2× plus faible que les autres horizons. Split 4 (2022 H1) négatif sur les 5 horizons (structurel). **Confirme : B32 (score components) dernier candidat YetiRank prometteur, B33/B34 peu probables.**
- **B32** : B4 + score components + YetiRank (153 feat, sans `--no-include-score-components`). ⚠️ **BON MAIS PAS CHAMPION** — IC 0.0224 (+11% vs B4, +19% vs B12 RMSE 0.0188), IR 0.95. H15/H20 (0.0255/0.0250) proches de B20. YetiRank sauve les score components (B12 était mixte en RMSE). Per-Sector LightGBM 8/11 (confirme le boost score comps). V2=−8.0%, V4=−17.7%. Split 4 (2022 H1) négatif sur les 5 horizons. **Classement final : B25 (0.0241) > B20 (0.0238) > B32 (0.0224) > B4 (0.0202).**
- **B33** : B4 + cross-sectional + YetiRank (159-177 feat). ❌ **ÉCHEC** — IC 0.0138 (−32% vs B4, −43% vs B25), IR 0.72. Encore pire que B13 RMSE (0.0144). H15 Decile Spread 0.0046 (séparation top/bottom quasi nulle), H15/H20 s'effondrent (0.0115/0.0107, IR 0.59/0.52). V4=−24.6%. **Les features cross-sectional détruisent le signal avec ou sans YetiRank. Campagne feature-flags close : B25 champion définitif.**
- **B34** : B4 + screener + YetiRank (181-199 feat, commande incluant aussi `--enable-cross-sectional`). ❌ **ÉCHEC** — IC 0.0151 (−25% vs B4, −37% vs B25), IR 0.78. H20 s'effondre (0.0102, IR 0.46), H15 Decile Spread 0.0044. LightGBM quasi nul partout (IC ≤ 0.007). V2=−13.4%. **Dernier batch de la campagne B31-B34 : aucun flag ne bat B25. Podium final : B25 (0.0241) > B20 (0.0238) > B32 (0.0224) > B4 (0.0202).**
- **B35** : B25 sur la liste réduite de 196 symboles (mêmes flags, 145 feat). ❌ **ÉCHEC** — IC 0.0154 (−36% vs B25), IR 0.51. Réduire 400→196 booste H3 (0.0283, IR 1.46 — record mais sur petit univers, non comparable) mais détruit H10/H15/H20 (0.012/0.008/0.006, IR 0.40/0.23/0.17). CatBoost perd H10/H20 face à LightGBM. Per-sector passe à 9 secteurs, F1 dégradé (Dir Acc ≤ 0.50). **Garder la liste de 400 symboles (config/ticket_mid_cap_400.txt) — le cross-section large est essentiel aux horizons longs.**
- **B36** : B20 sur la liste réduite de 196 symboles (144 feat). ❌ **ÉCHEC — CONFIRME B35** — IC 0.0148 (−38% vs B20), IR 0.45. H3/H5 très forts (0.0277/0.0246, IR 1.57/1.23) mais H10-H20 morts (0.008/0.007/0.007, Decile Spread ≤ 0.004). Le CAPM n'aide pas sur petit univers. Per-sector 9 secteurs, Dir Acc ≤ 0.50. **Conclusion : la taille du cross-section (400) est un facteur de premier ordre pour les horizons longs. Garder la liste 400.**
- **B37** : B25 sur 393 symboles sélectionnés par swing score (145 feat, mêmes flags). ❌ **ÉCHEC — LE PIRE DES TESTS D'UNIVERS** — IC 0.0123 (−49% vs B25), IR 0.89. H10 0.0116, H20 mort (0.0035, Decile Spread −0.0003), meilleur horizon H3 (0.0199). Pire que B35 (196 liquidité, 0.0154) alors que B37 a plus de symboles. Per-sector hasard habituel (F1 ~0.33, Dir Acc ≤ 0.50). **Conclusion : la composition de l'univers prime sur la taille — la sélection « swing score » est toxique pour le Global Ranking. Garder la sélection liquidité 400.**
- **B39** : B25 + XGBoost rank:ndcg (P3-3). ❌ **ÉCHEC — CLOS** — IC 0.0129 (−47% vs B25), IR 0.57. Perd les 5 horizons vs catboost B25 (H3 −92%, H5 −52%, H10 −48%, H15 −24%, H20 −35%). Backtest V2=−8.8% (H15), V4=−23.9%. Per-sector identique à B25. **CatBoost YetiRank reste champion — ne pas retenter XGBoost.**
- **B40** : B4 + volume features (P3-5). ❌ vs B4 — IC 0.0178 (−12% vs 0.0202), IR 1.13 (meilleure stabilité). H3 seul gagnant (+40% : 0.0146, IR 1.77 record) ; H5 −2%, H10 −13%, H15 −26%, H20 −27%. **Les features volume/liquidité aident le court terme mais détruisent les horizons longs en RMSE. Le verdict final P3-5 attend B41 (B25 + volume).**
- **B41** : B25 + volume features (P3-5). 🔥🔥 **NOUVEAU RECORD IC 0.0260 (+7.9% vs B25), IR 1.55 (+45%)** — **5/5 horizons gagnés vs B25** (H3 +29%, H5 +8%, H15 +13%, H20 +2% ; H10 IC 0.0265, −5%, mais IR 1.61 vs 1.18, +36% → la stabilité prime, B41 prend aussi H10). Decile spreads +36 à +80% (H3 0.0198 vs 0.0145, H10 0.0313 vs 0.0207, H15 0.0359 vs 0.0199). H15 = 0.0294 (IR 1.94). Backtest V2=−11.6%. **L'interaction volume × YetiRank est fortement positive (inverse du RMSE B40). ⚠️ In-sample : OOS 2025 + backtest obligatoires avant promotion.**
- **B42** : B20 + volume features (P3-5, **sans CAPM ni include-factors** — ablation pure du volume). 🔥 **IC 0.0250 (+5.0% vs B20 0.0238), IR 1.46 (+42% vs B20 1.03)**. H3 +21%, H5 +9%, H10 +12% (0.0282, IR 1.60 = **record H10 de la série, bat B25 0.0279**), H15 −7%, H20 −1% vs B20. Backtest V2=−9.7% (H20), V4=−24.8%. Per-sector lightgbm 6 / catboost 5. **Le volume seul (B42) > CAPM seul (B25 0.0241) — le volume est le driver principal, le CAPM un bonus sur H3/H5/H15/H20 (B41 0.0260) mais nuisible sur H10 (0.0265 < 0.0282).** ⚠️ In-sample : OOS 2025 + backtest obligatoires avant promotion.
- **B38** : B25 sur 300 symboles pris **parmi les 400 habituels** (mêmes flags, 145 feat, 6 splits). ⚠️ **QUASI ÉQUIVALENT À B25** — IC 0.0229 (−5% vs B25), **IR 1.14 (+7%, meilleur de la série)**. H15 devient meilleur horizon (0.0255, IR 1.54), H10/H20 solides (0.0253/0.0252, IR 1.28/1.11). LightGBM s'effondre partout (IC ≤ 0.0092) → catboost 5/5. Per-sector hasard habituel (F1 ~0.33). **Conclusion : la réduction 400→300 à composition égale (liquidité) coûte seulement −5% d'IC et améliore la stabilité — contrairement à B35/B37, c'est la COMPOSITION qui tue, pas la taille au-dessus de ~300. Conforte le garde-fou breadth live à 75 % (= 300 symboles).**
- **⛔ Batches abandonnés (temps d'entraînement excessif)** : B23 (PairLogit), B24 (PairLogitPairwise), B28 (CAPM+PairLogit), B29 (CAPM+PairLogitPairwise) — 20h+ de calcul bloquées sur H3. Les losses pairwise CatBoost sont trop lentes (O(n²) par groupe) pour le Global Ranking. **Verdict : PairLogit et PairLogitPairwise sont inexploitables en production, abandonnés.**
- **Classement flags** : YetiRank+CAPM+volume (🥇 B41, IC 0.0260, IR 1.55) > YetiRank+volume (🥈 B42, IC 0.0250, IR 1.46) > CAPM+YetiRank (🥉 B25, IC 0.0241) > YetiRank (B20, IC 0.0238) > stacking (V2=−0.1%). **B41 champion IC Global 4/5 horizons (H3/H5/H15/H20) ; B42 champion H10 (record 0.0282). B14 reste champion backtest.**
- **🆕 V4 top horizons** : V4 entre −12% et −27%. B14/B15/B16 à −12.4% (meilleur), B2 à −26.9% (pire).
- Catboost Global imbattable (5/5). LightGBM Per-Sector jusqu'à 10/11 (B12). **Configuration recommandée : `--include-short-score --target-excess-vs-spy --include-factors --catboost-loss-function YetiRank --include-volume-features` (B41, en attente OOS 2025) pour IC — H3/H5/H15/H20. Pour H10, B42 (même config SANS CAPM ni include-factors) détient le record 0.0282. Ou `--enable-global-stacking` (B14) pour backtest.**
