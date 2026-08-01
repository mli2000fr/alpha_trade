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

## 🎯 Configuration gagnante (finale)

| Paramètre | Baseline | Final |
|-----------|----------|-------|
| Modèle | CatBoost RMSE | **CatBoost RMSE** |
| `max_train_size` | 504j | **756j** |
| `demi-vie` | 180j | **360j** |
| `regime_risk_off` | blacklisté | **disponible** |
| Target smoothing | non | **50% h + 50% avg** |
| Config séparée | non | `GlobalModelConfig.ranking_max_depth=7` |

## 📈 Détail par horizon (config finale)

| Métrique | H10 | H15 | H20 | Global |
|----------|-----|-----|-----|--------|
| IC Mean | 0.0146 | 0.0160 | 0.0192 | **0.0166** |
| IC Std | 0.0348 | 0.0351 | 0.0366 | — |
| IC IR | 0.42 | 0.46 | 0.52 | — |
| Decile Spread | 0.0104 | 0.0111 | 0.0136 | — |

## 🧠 Leçons apprises

1. **CatBoost RMSE > LightGBM LambdaRank** pour ranking financier faible signal.
2. **La fenêtre d'entraînement est le levier #1** : 504→756j = +27% IC. Sweet spot ~3 ans.
3. **Le lissage de target aide les horizons courts** : H10 +65%, H20 stable.
4. **Moins de features ≠ meilleur** : les arbres excellent à combiner des signaux faibles.
5. **Le vol scaling est indispensable** sur cet univers (vol20_median=0.019).
6. **Le signal est concentré en bear market** (momentum_60 IC=-0.05 vs ~0 en bull).
7. **Séparation des configs** : `GlobalModelConfig` (ranking) vs `BaselineConfig` (per-symbol).

## ▶️ Pistes restantes

| Priorité | Piste | Gain estimé |
|----------|-------|-------------|
| 🔵 | Target sector-neutral | Moyen |
| 🔵 | max_splits 13→15 | Faible |
| 🔵 | Features d'interaction composites | Moyen |
