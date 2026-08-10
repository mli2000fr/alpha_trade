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

## 🔮 Pistes non testées (potentiel restant)

### 🥇 Priorité haute — Target engineering

| Piste | Raison | Potentiel |
|:------|:-------|:---------:|
| **CatBoost YetiRank** (loss pairwise) | Loss de ranking natif au lieu de MSE | Fort |
| **Target rank IC** (optimiser IC direct) | Test #14 composite +75% mais mal implémenté | Fort |
| **Target asymétrique LONG/SHORT** | F1 short < 0.50 → pénaliser plus le LONG | Moyen |

### 🥈 Priorité moyenne — Architecture

| Piste | Raison | Potentiel |
|:------|:-------|:---------:|
| **XGBoost** (3ᵉ algo) | Parfois > CatBoost en finance | Moyen |
| **NN simple (MLP 2-3 couches)** | Interactions non-linéaires | Moyen |
| **Ensemble CatBoost + LightGBM** (stacking) | B12 montre qu'ils excellent sur des secteurs différents | Moyen |

### 🥉 Priorité basse — Features

| Piste | Raison | Potentiel |
|:------|:-------|:---------:|
| **Features d'interaction (×, ÷)** | momentum × volume, etc. | Faible (test #14 rejeté) |
| **Volume profile / liquidity** | Jamais testé | Faible |
| **Rolling feature importance + dropout** | Éviter overfitting par split | Faible |

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
13. **Macro flags (VIX, VXN, VIX3M, MOVE, regime) = 0 gain** sur B5-B8, B11. Inutiles en l'état.
14. **Fondamentaux bruts = −16% IC** (B9). Trop de bruit, pas assez de signal.
15. **Cross-sectional intra-secteur = −23% IC** (B13). Pire flag testé.
16. **CAPM = +IR** (B10, 1.09 record) sans dégrader l'IC. Seul facteur utile.
17. **Per-Sector ≈ hasard** : F1 macro ~0.33, F1 short < 0.50. Le Global Ranking est le seul signal fiable.
18. **short-score + target-excess-vs-spy (B4) = configuration recommandée** pour la production.
19. **Prochaine étape** : tester CatBoost YetiRank (loss de ranking) et target rank IC direct.

## ✅ 18 tests + 6 retests P1 + 13 tests flags B0-B13. IC réel = 0.0190, H20 IR = 2.76.

---

## 📋 Reste à faire (2026-08-11)

### 🔥 Priorité haute — Impact direct PnL

| # | Action | Effort | Impact | Dépendance |
|---|--------|:------:|:------:|------------|
| **T1** | **P0 — Caps sectoriels en production** | 1j | Élevé | Aucune — risk_management existant |
| **T2** | **Per-symbol 50-100 titres liquides** | 3-5j | Élevé | Protocole D (pilote 71ad0b prometteur) |
| **T3** | **CatBoost YetiRank** (loss pairwise) | 2j | Fort | Global Ranking uniquement |

### ⚠️ Priorité moyenne — Confirmation

| # | Action | Effort | Impact | Dépendance |
|---|--------|:------:|:------:|------------|
| **T4** | P1/P2 — Optimisation de poids avec contraintes secteur | 5j | Élevé | Après T1 |
| **T5** | Feature ablation F0-F4 per-symbol | 3j | Moyen | Après T2 |
| **T6** | Target rank IC direct (optimiser IC au lieu de MSE) | 3j | Fort | Global Ranking |

### ✅ Fait / Archivé

| # | Action | Statut |
|---|--------|:------:|
| T7 | Per-sector : 8 campagnes + B0-B13 → aucun alpha | ✅ Clos, research-only |
| T8 | Flags macro (VIX, VXN, VIX3M, MOVE, regime) | ✅ Testés B5-B8, B11 → 0 gain |
| T9 | Fondamentaux, cross-sectional, screener, sentiment | ✅ Testés B1, B2, B9, B13 → 0 ou négatif |
| T10 | Audit leakage (P0/P1) | ✅ Archivé dans prompt/ml/ |
| T11 | LSTM calibration (MSE hors échelle) | 📦 Quarantaine |

### 🎯 Ordre d'exécution recommandé

```
T1 (caps sectoriels) → dispo aujourd'hui, zero risque
  ↓
T2 (per-symbol 50-100) → confirmer/infirmer le 2ᵉ alpha
  ↓
T3 (YetiRank) → dernier levier Global Ranking non testé
  ↓
T4 (optimisation poids) → après T1+T2 confirmés
```
