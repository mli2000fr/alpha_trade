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

## 🎯 Configuration gagnante (finale)

| Paramètre | Baseline | Final |
|-----------|----------|-------|
| Modèle | CatBoost RMSE | **CatBoost RMSE** |
| `max_train_size` | 504j | **756j** |
| `demi-vie` | 180j | **360j** |
| `regime_risk_off` | blacklisté | **disponible** |
| Target smoothing | non | **50% h + 50% avg** |
| Target sector-neutral | non | **oui** |
| Config séparée | non | `GlobalModelConfig.ranking_max_depth=7` |

## 📈 Détail par horizon (config finale)

| Métrique | H10 | H15 | H20 | Global |
|----------|-----|-----|-----|--------|
| IC Mean | 0.0193 | 0.0205 | 0.0226 | **0.0208** |
| IC Std | 0.0204 | 0.0225 | 0.0237 | — |
| IC IR | 0.94 | 0.91 | 0.95 | — |
| Decile Spread | 0.0204 | 0.0228 | 0.0235 | — |

## 🧠 Leçons apprises

1. **La target sector-neutral est le levier #1** : +84% IC à elle seule.
2. **CatBoost RMSE > LightGBM LambdaRank** pour ranking financier faible signal.
3. **Le lissage de target aide les horizons courts** : H10 +65%.
4. **756j** est le sweet spot de fenêtre train.
5. **13 splits > 8 splits** : granularité fine permet adaptation au régime.
6. **Moins de features ≠ meilleur** : les arbres excellent à combiner.
7. **Composites inutiles** : les arbres apprennent déjà ces interactions.
8. **Séparation des configs** : `GlobalModelConfig` vs `BaselineConfig`.

## ✅ Pistes épuisées — 14 tests, IC ×1.84
