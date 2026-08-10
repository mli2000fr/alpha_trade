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

## 🧪 Tests flags B0-B13 — Feature flags sur config P1 (2026-08-10)

> Tous les tests utilisent la config P1 (target sector/factor-neutral, smoothing, 8 splits, 756j).
> Baseline B0 = 143 features, IC Rank 0.0186, IR 1.02, CatBoost 5/5 Global.

| # | Test | IC Rank | IC IR | Best H | V2 backtest | Per-Sector LightGBM | Verdict |
|---|------|--------:|------:|:------:|:-----------|:-------------------:|:--------|
| B0 | **Baseline P1** | 0.0186 | 1.02 | H10 | −7.7% | 6/11 | référence |
| B1 | +sentiment | 0.0186 | 1.02 | H10 | −7.7% | 6/11 | ❌ 0 gain |
| B2 | +screener (166 feat) | 0.0186 | 0.97 | H20 | −8.2% | 6/11 | ⚠️ IR down |
| B3 | **+short-score** | **0.0202** | **1.03** | H10 | −7.1% | 6/11 (catboost) | ✅ IC +9% |
| B4 | **+target-excess-vs-spy** | **0.0202** | **1.03** | H10 | −7.1% | 8/11 | 🏆 **MEILLEUR** |
| B5 | +VIX | 0.0202 | 1.03 | H10 | −7.1% | 8/11 | ❌ 0 gain |
| B6 | +VXN | 0.0202 | 1.03 | H10 | −7.1% | 8/11 | ❌ 0 gain |
| B7 | +VIX3M | 0.0202 | 1.03 | H10 | −7.1% | 8/11 | ❌ 0 gain |
| B8 | +MOVE | 0.0202 | 1.03 | H10 | −7.1% | 8/11 | ❌ 0 gain |
| B9 | +fondamentaux (156 feat) | 0.0157 | 0.98 | H10 | −10.3% | 5/11 | ❌❌ −16% IC |
| B10 | **+CAPM (145 feat)** | 0.0195 | **1.09** | H10 | **−1.9%** | 9/11 | 🔥 IR record |
| B11 | +macro-regime | 0.0202 | 1.03 | H10 | −7.1% | 7/11 | ❌ 0 gain |
| B12 | +score-components (153 feat) | 0.0188 | 0.92 | H15 | −2.5% | **10/11** | ⚠️ mixte |
| B13 | +cross-sectional (177 feat) | 0.0144 | 0.84 | H10 | −16.9% | 7/11 | ❌❌ −23% IC |

### 🏆 Podium B0-B13

| Rang | Batch | Flags | IC Rank | IR | V2 | LightGBM |
|:----:|:------|:------|--------:|:--:|:---|:--------:|
| 🥇 | **B4** | short + SPY | 0.0202 | 1.03 | −7.1% | 8/11 |
| 🥈 | **B10** | B4 + CAPM | 0.0195 | **1.09** | **−1.9%** | 9/11 |
| 🥉 | **B6** | B4 + VXN | 0.0202 | 1.03 | −7.1% | 8/11 |
| 🔴 | B13 | B4 + cross-sectional | 0.0144 | 0.84 | −16.9% | 7/11 |

### 🧠 Constats flags

- **Aucun flag macro (VIX, VXN, VIX3M, MOVE, regime) n'apporte de gain** — ni Global, ni Per-Sector
- **short-score + SPY** (B4) = combinaison gagnante, IC +9%, Per-Sector boosté
- **CAPM** (B10) améliore l'IR (1.09 record) et le backtest V2 (−1.9%, quasi-neutre)
- **Fondamentaux et cross-sectional détruisent le signal** (−16% à −23% IC)
- **Score components** (B12) : booste LightGBM (10/11) mais dégrade le Global
- **Per-Sector ≈ hasard** : F1 macro ~0.33, F1 short < 0.50. Seul le Global Ranking a un vrai pouvoir prédictif.

## � Reste à faire — Priorisé (2026-08-11)

### 🔥 P0 — Quick wins (impact immédiat, effort minimal)

| # | Action | Effort | Impact | Pourquoi |
|---|--------|:------:|:------:|----------|
| **P0-1** | **Caps sectoriels en production** | 1j | 🔥🔥 | Risk management existant. Zéro risque, zéro changement ML. |

### 🔥 P1 — Alpha additionnel (impact élevé, effort moyen)

| # | Action | Effort | Impact | Pourquoi |
|---|--------|:------:|:------:|----------|
| **P1-1** | **Per-symbol 50-100 titres liquides** | 5j | 🔥🔥 | Pilote 71ad0b : CatBoost DA WF=57%. Confirmer ou infirmer. |
| **P1-2** | **CatBoost YetiRank** (loss pairwise) | 2j | 🔥 | Loss de ranking natif > MSE. Dernier levier Global non testé. |

### ⚠️ P2 — Optimisation (après P1 confirmé)

| # | Action | Effort | Impact | Pourquoi |
|---|--------|:------:|:------:|----------|
| **P2-1** | Optimisation de poids P1/P2 (contraintes secteur) | 5j | 🔥🔥 | Après P0-1. Transforme un bon score en bon PnL. |
| **P2-2** | Feature ablation F0-F4 per-symbol | 3j | 🔥 | Comprendre CE QUI marche dans le per-symbol. Après P1-1. |

### 💡 P3 — Idées (priorité basse, à tester si bande passante)

| # | Action | Effort | Impact | Pourquoi |
|---|--------|:------:|:------:|----------|
| **P3-1** | Target rank IC direct (optimiser IC au lieu de MSE) | 3j | 🔥 | Cohérent avec l'objectif réel (ranking). Test #14 +75% mais mal fait. |
| **P3-2** | Target asymétrique LONG/SHORT | 2j | ⚠️ | F1 short < 0.50 → pénaliser plus le LONG. |
| **P3-3** | Ensemble CatBoost + LightGBM (stacking) | 3j | ⚠️ | B12 : ils excellent sur des secteurs différents. |
| **P3-4** | XGBoost (3ᵉ algo) | 2j | ⚠️ | Challenger unique, pas une grille. |
| **P3-5** | NN simple (MLP 2-3 couches) | 3j | ❓ | Interactions non-linéaires. Risqué. |
| **P3-6** | Features d'interaction (×, ÷) | 2j | ❌ | Déjà rejeté (test #14). |
| **P3-7** | Volume profile / liquidity features | 2j | ❓ | Jamais testé. |
| **P3-8** | Rolling feature importance + dropout | 3j | ❌ | Éviter overfitting. Faible priorité. |

### ✅ Fait / Archivé

| # | Action | Statut |
|---|--------|:------:|
| — | Per-sector : 8 campagnes + B0-B13 → aucun alpha | ✅ Clos, research-only |
| — | Flags macro (VIX, VXN, VIX3M, MOVE, regime) | ✅ Testés B5-B8, B11 → 0 gain |
| — | Fondamentaux, cross-sectional, screener, sentiment | ✅ Testés B1, B2, B9, B13 → 0 ou négatif |
| — | Audit leakage (P0/P1) | ✅ Archivé dans prompt/ml/ |
| — | LSTM calibration (MSE hors échelle) | 📦 Quarantaine |

### 🎯 Ordre d'exécution

```
P0-1 (caps) ──→ dispo aujourd'hui, zero risque
  │
  ├─→ P1-1 (per-symbol) ──→ confirmer 2ᵉ alpha
  │     └─→ P2-2 (ablation features)
  │
  ├─→ P1-2 (YetiRank) ──→ dernier levier Global
  │
  └─→ P2-1 (optimisation poids) ──→ après P0-1
        │
        └─→ P3-* (idées) ──→ si bande passante
```
