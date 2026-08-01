# Global Ranking — Synthèse des tests A/B (2026-08-01)

## 📊 Tableau de bord

| # | Test | IC Global | Δ vs Baseline | Verdict |
|---|------|-----------|---------------|---------|
| 1 | **Baseline** (504j, vol ON, 176 feats) | 0.0113 | — | référence |
| 2 | Vol scaling OFF | 0.0082 | -27% | ❌ |
| 3 | Excès vs SPY | 0.0106 | -6% | ❌ |
| 4 | Déciles (vs vingtiles) | 0.0113 | 0% | ❌ |
| 5 | Whitelist 53 features | 0.0064 | -43% | ❌ |
| 6 | **756j + régime dé-blacklisté** | **0.0144** | **+27%** | ✅ |
| 7 | 1008j | 0.0135 | +19% | ❌ (diminishing) |
| 8 | colsample_bytree 0.4 | 0.0144 | 0% | ❌ |
| 9 | **+ Target smoothing** | **0.0163** | **+44%** | ✅✅ |

## 🎯 Configuration gagnante (cumulée)

| Paramètre | Baseline | Final | Gain |
|-----------|----------|-------|------|
| `max_train_size` | 504j | **756j** | +27% |
| `demi-vie` | 180j | **360j** | (combiné) |
| `regime_risk_off` | blacklisté | **disponible** | (combiné) |
| Target smoothing | non | **50% h + 50% avg** | +13% |

## 📈 Détail par horizon (config finale)

| Métrique | H10 | H15 | H20 | Global |
|----------|-----|-----|-----|--------|
| IC Mean | 0.0137 | 0.0160 | 0.0194 | **0.0163** |
| IC Std | 0.0349 | 0.0343 | 0.0362 | — |
| IC IR | 0.39 | 0.46 | 0.54 | — |
| Decile Spread | 0.0097 | 0.0113 | 0.0158 | — |

## 🧠 Leçons apprises

1. **La fenêtre d'entraînement est le levier #1** : 504→756j = +27% IC. Le sweet spot est ~3 ans.
2. **Le lissage de target aide les horizons courts** : H10 +65%, H20 stable.
3. **Moins de features ≠ meilleur** : les arbres excellent à combiner des signaux faibles.
4. **Le vol scaling est indispensable** sur cet univers.
5. **Le signal est concentré en bear market** (IC -0.05 vs ~0 en bull).
6. **Les hyperparamètres tree-based (colsample, depth) ont peu d'effet** tant que le signal sous-jacent est faible.

## ▶️ Pistes restantes

| Priorité | Piste | Gain estimé |
|----------|-------|-------------|
| 🔵 | max_depth 5→7 | Moyen |
| 🔵 | Target sector-neutral | Moyen |
| 🔵 | CatBoost au lieu de LightGBM | Faible-Moyen |
| 🔵 | max_splits 13→15 | Faible (plus de data) |
