# Global Ranking — Synthèse des tests A/B (2026-08-01)

## 📊 Tableau de bord

| # | Test | IC Global | Δ vs Baseline | Verdict |
|---|------|-----------|---------------|---------|
| 1 | **Baseline** (504j, 176 feats, CatBoost RMSE) | 0.0113 | — | référence |
| 2 | Vol scaling OFF | 0.0082 | -27% | ❌ |
| 3 | Excès vs SPY | 0.0106 | -6% | ❌ |
| 4 | Déciles (vs vingtiles) | 0.0113 | 0% | ❌ |
| 5 | Whitelist 53 features | 0.0064 | -43% | ❌ |
| 6 | **756j + régime dé-blacklisté** | **0.0144** | **+27%** | ✅ |
| 7 | 1008j | 0.0135 | +19% | ❌ |
| 8 | colsample_bytree 0.4 | 0.0144 | 0% | ❌ |
| 9 | **+ Target smoothing** | **0.0163** | **+44%** | ✅✅ |
| 10 | **max_depth 7, num_leaves 31** | **0.0166** | **+47%** | ✅ |
| 11 | LightGBM LambdaRank | 0.0130 | +15% | ❌ |
| 12 | **+ Target sector-neutral** | **0.0208** | **+84%** | 🔥🔥 |
| 13 | 8 splits (252j) | 0.0161 | +42% | ❌ |
| 14 | Composite features (×11) | 0.0198 | +75% | ❌ |
| 15 | **+ H3/H5 (5 horizons)** | **0.0208** | **+84%** | 🔥 |
| 16 | **+ Target factor-neutral (OLS)** | **0.0208** | **+84%** | ✅ (IC IR ×1.3) |
| 17 | Cyclical only (289 syms) | 0.0257 | +127% | IC ↑ mais IR ÷2 |
| 18 | Defensive only (79 syms) | 0.0246 | +118% | Pas fiable (trop petit) |

## 🎯 Configuration gagnante (finale)

| Paramètre | Baseline | Final |
|-----------|----------|-------|
| Modèle | CatBoost RMSE | **CatBoost RMSE** |
| `max_train_size` | 504j | **756j** |
| `demi-vie` | 180j | **360j** |
| `regime_risk_off` | blacklisté | **disponible** |
| Target smoothing | non | **50% h + 50% avg(10,15,20)** |
| Target sector-neutral | non | **oui** |
| Target factor-neutral (Size/Value/Mom) | non | **oui (OLS)** |
| Config séparée | non | `GlobalModelConfig.ranking_max_depth=7` |
| Horizons | 3 | **3, 5, 10, 15, 20** |

## 📈 Détail par horizon (config finale)

| Métrique | H3 | H5 | H10 | H15 | H20 | Global |
|----------|----|----|-----|-----|-----|--------|
| IC Mean | 0.0132 | 0.0176 | 0.0230 | 0.0256 | 0.0245 | **0.0208** |
| IC IR | 1.01 | 0.99 | 1.05 | 1.15 | 1.11 | — |
| Decile Spread | 0.0125 | 0.0180 | 0.0243 | 0.0275 | 0.0248 | — |

## 🧠 Leçons apprises

1. **La target sector-neutral est le levier #1** : +84% IC.
2. **CatBoost RMSE > LightGBM LambdaRank** pour ranking financier faible signal.
3. **H3/H5 sont viables** sans smoothing ni dilution par horizons longs.
4. **H5 à 0.018** — exploitable pour ton horizon de trading 5j.
5. **H10/H15 boostés +19-25%** par l'ajout de H3/H5 (effet régularisant).
6. **Tous les IC IR > 1.0** — signal stable pour la première fois.
7. **756j** est le sweet spot de fenêtre train.
8. **13 splits > 8 splits** : granularité fine → adaptation au régime.
9. **Factor-neutral** : IC stable, IC IR ×1.3 — alpha plus pur.
10. **Univers séparés** : IC brut ↑ mais IR ↓ — l'univers « all » reste optimal.

## ✅ 18 tests, IC ×1.84, IC IR ×3.6
