# Global Ranking — Synthèse des tests A/B (2026-08-02)

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
| 9 | **+ Target smoothing** | **0.0163** | **+44%** | ⚠️ retiré P1 |
| 10 | **max_depth 7, num_leaves 31** | **0.0166** | **+47%** | ✅ |
| 11 | LightGBM LambdaRank | 0.0130 → 0.0086 P1 | −24% | ❌ confirmé |
| 12 | **+ Target sector-neutral** | **0.0208** | **+84%** | 🔥🔥 |
| 13 | 8 splits (252j) → 13 splits | 0.0161 → 0.0139 P1 | inversé | ✅ 8 gagne |
| 14 | Composite features (×11) | 0.0198 | +75% | ❌ |
| 15 | **+ H3/H5 (5 horizons)** | **0.0208** | **+84%** | 🔥 |
| 16 | **+ Target factor-neutral (OLS)** | **0.0208** | **+84%** | ✅ |
| R1 | **Baseline P1 réel** (504j, H10 seul, étanche) | 0.0084 | — | référence réelle |
| R2 | **Smoothing OFF** (P1, 13 splits) | H20 +36%, H10 −12% | — | conservé avec 8 splits |
| R3 | **8 splits × 252j** (P1) | **0.0194 (+40%)** | — | 🔥🔥 adopté |
| R4 | **8 splits + no smoothing** | H10 −24% vs avec | — | ❌ interaction |
| R5 | **Z-score fondamentales secteur** | H20 IR +54%, H5 IC −8% | — | ✅ adopté |
| R6 | **Signal blending** (grid search) | IC 0.0246 vs H15 0.0249 | — | ❌ rejeté |

## 🎯 Configuration gagnante (finale P1)

| Paramètre | Baseline | Final |
|-----------|----------|-------|
| Modèle | CatBoost RMSE | **CatBoost RMSE** |
| `max_train_size` | 504j | **756j** |
| `demi-vie` | 180j | **360j** |
| Splits | — | **8 × 252j** |
| `regime_risk_off` | blacklisté | **disponible** |
| Target smoothing | non | **50% h + 50% avg(10,15,20)** |
| Target sector-neutral | non | **oui** |
| Target factor-neutral | non | **oui (OLS)** |
| Target computation | pré-split (leakage) | **post-split (P1 étanche)** |
| Z-score fondamentales | non | **oui (médiane/MAD secteur)** |
| Config séparée | non | `GlobalModelConfig.ranking_max_depth=7` |
| Horizons | 3 | **3, 5, 10, 15, 20** |

> **Interaction smoothing × splits** : le smoothing seul (13 splits) diluait (−12% H10).
> Avec 8 splits (régimes distincts), il apporte +31% sur H10. Les deux sont complémentaires.
| Horizons | 3 | **3, 5, 10, 15, 20** |

## 📈 Détail par horizon (P1 étanche, 8 splits, smoothing ON, Z-score)

| Métrique | H3 | H5 | H10 | H15 | H20 | Global |
|----------|----|----|-----|-----|-----|--------|
| IC Mean | 0.0129 | **0.0120** | 0.0211 | 0.0239 | 0.0251 | **0.0190** |
| IC IR | 1.46 | **1.19** | 1.69 | 2.28 | 2.76 | — |
| Decile Spread | 0.0116 | 0.0147 | 0.0238 | 0.0247 | 0.0260 | — |

> Baseline P1 réel = 0.0084 / IR 0.30. Pipeline cible ×2.3.

## 🧠 Leçons apprises

1. **Target sector-neutral est le levier #1** : +84% IC.
2. **CatBoost RMSE > LightGBM LambdaRank** pour ranking financier faible signal.
3. **8 splits > 13 splits** (post-leakage) : moins de chevauchement → +40% IC, IR ×2.
4. **Smoothing retiré** : contre-productif sans leakage, H20 gagne 36% sans.
5. **H5 exploitable** : IC 0.013, IR 1.40 pour trading 5j.
6. **Data leakage corrigé** : 33% de bruit, P1 post-split étanche.
7. **Tous les IC IR > 1.0** — signal stable.
8. **756j** sweet spot, 360j demi-vie.
9. **Factor-neutral** stabilise l'IC IR.
10. **Univers « all »** reste optimal vs séparation cyclique/défensive.
11. **Z-score fondamentales** : stabilise H15/H20 (IR +54%), trade-off acceptable sur H5.
12. **Blending inutile** : horizons trop corrélés.

## ✅ 18 tests + 6 retests P1. IC réel = 0.0190, H20 IR = 2.76
