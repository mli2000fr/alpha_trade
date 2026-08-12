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

## 🧪 Tests flags B0-B19 — Feature flags sur config P1 (2026-08-11)

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
| B14 | **B4 + stacking** | 0.0196 | 1.03 | H10 | **−0.1%** | 7/11 | 🔥 V2 quasi-neutre |
| B15 | B4 + T1 skip vol scaling | 0.0196 | 1.03 | H10 | — | cb 7/11 | ❌ 0 gain |
| B16 | B4 + T2 intra-sector rank | 0.0196 | 1.03 | H10 | — | 8/11 | ❌ 0 gain |
| B17 | B4 + T3 ternary | 0.0196 | 1.03 | H10 | — | 9/11 | ❌ per-sect: 72% flat |
| B18 | B4 + from 2011 (8 splits) | ⚠️ 0.0165 | ❌ 0.66 | H5 | — | cb 7/11 | ❌ −18% IC vs B4 |
| B19 | B4 + from 2011 (16 splits) | ❌ 0.0157 | ❌ 0.68 | H5 | — | cb 6/11 | ❌ −22% IC vs B4 |
| **B20** | **B4 + YetiRank** | 0.0238 | 1.03 | H15 | ⏳ | — | 🔥 +18% vs B4 |
| B21 | B4 + QueryRMSE | 0.0188 | 0.92 | H10 | — | — | ❌ −7% vs B4 |
| B22 | B4 + QuerySoftMax | 0.0185 | 0.89 | H5 | — | — | ❌ −8% vs B4 |
| **B25** | **B10 + YetiRank** | 🏆 **0.0241** | **1.07** | H10 | ⏳ | — | 🔥🔥 **NOUVEAU RECORD +19%** |
| B26 | B10 + QueryRMSE | 0.0172 | 0.97 | H5 | — | — | ❌ −15% vs B4, −12% vs B10 |

### 🏆 Podium B0-B20

| Rang | Batch | Flags | IC Rank | IR | V2 | LightGBM |
|:----:|:------|:------|--------:|:--:|:---|:--------:|
| 🥇 | **B25** | B10 + YetiRank | **0.0241** | 1.07 | ⏳ | — |
| 🥈 | **B20** | B4 + YetiRank | 0.0238 | 1.03 | ⏳ | — |
| 🥉 | **B4** | short + SPY | 0.0202 | 1.03 | −7.1% | 8/11 |
| 4ᵉ | **B14** | B4 + stacking | 0.0196 | 1.03 | **−0.1%** | 7/11 |
| 5ᵉ | **B10** | B4 + CAPM | 0.0195 | **1.09** | −1.9% | 9/11 |
| 🔴 | B13 | B4 + cross-sectional | 0.0144 | 0.84 | −16.9% | 7/11 |
| 🔴 | B19 | B4 + from 2011 | 0.0157 | 0.68 | — | cb 6/11 |

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
- **Stacking** (B14) : V2 quasi-neutre (−0.1%), IC quasi-équivalent à B4 (−3%), champion 🥈
- **Target experiments T1/T2/T3** (B15-B17) : 0 gain Global, T3 = échec Per-Sector (72% flat)
- **From 2011** (B18/B19) : IC −18% à −22% vs B4, confirme `training_start_date=2016-01-01`
- **Fondamentaux et cross-sectional détruisent le signal** (−16% à −23% IC)
- **Score components** (B12) : booste LightGBM (10/11) mais dégrade le Global
- **CAPM + YetiRank** (B25) : 🏆🔥 **NOUVEAU RECORD IC 0.0241 (+19% vs B4)**. CAPM améliore H5/H10, YetiRank améliore tout. H10 IC 0.0279 (+10% vs B4 RMSE). Meilleur combo.
- **YetiRank** (B20) : IC 0.0238 (+18% vs B4), gagne 3/5 horizons (H3/H15/H20).
- **QueryRMSE / QuerySoftMax** (B21/B22) : ❌ < RMSE, H15 perdu par CatBoost. Seul YetiRank surpasse RMSE.
- **Per-Sector ≈ hasard** : F1 macro ~0.33, F1 short < 0.50. Seul le Global Ranking a un vrai pouvoir prédictif.

## � Reste à faire — Priorisé (2026-08-11)

### 🔥 P0 — Quick wins (impact immédiat, effort minimal)

| # | Action | Effort | Impact | Pourquoi |
|---|--------|:------:|:------:|----------|
| **P0-1** | **Caps sectoriels en production** | 1j | 🔥🔥 | ✅ **Fait (2026-08-11)** — `sector_limits.enabled: true` + alignement backtest/live dans `capital_presets.yaml`. |

### 🔥 P1 — Alpha additionnel (impact élevé, effort moyen)

| # | Action | Effort | Impact | Pourquoi |
|---|--------|:------:|:------:|----------|
| **P1-1** | ~~**Per-symbol 50-100 titres liquides**~~ | 5j | 🔥🔥 | ✅ **Fait** |
| **P1-2** | **CatBoost YetiRank** | 2j | 🔥 | ✅ **B20/B25 terminés** — B25 (CAPM+YetiRank) IC record 0.0241 (+19%). YetiRank validé, CAPM+YetiRank encore meilleur.<br>→ Prochaine étape : per-horizon specialization ou lancer B25 en production. |
| **P1-3** | **Target = rang percentile** (optimiser IC au lieu de MSE) | 3j | 🔥 | À faire juste après P1-2. Target `future_return` → `rank_percentile(future_return)` ∈ [0,1].<br>→ Prototype déjà testé : IC passée de −0.023 à +0.012, variance ÷ 4, 6/8 splits > 0.<br>→ ⚠️ Plus profond que P1-2 : touche `global_ranking.py` (pipeline de préparation), pas juste un paramètre CatBoost. Risque de régression si la target en rang perd de l'information utile pour le sizing.<br>→ Complémentaire à P1-2 : les deux peuvent se cumuler (target = rang + loss = YetiRank). |
| **P1-4** | **Portfolio OOS V1/V2/V3/V4** (top 5/10/20/30%) | 3j | 🔥🔥 | Validation de tradabilité réelle. Pour chaque date OOS : ranking → sélection top N% → caps sectoriels → V1/V2/V3/V4 → sizing → frais+slippage → PnL net.<br>→ Répond à la question : « Est-ce que le signal survit aux frictions réelles ? »<br>→ Plus important que XGBoost ou un MLP. |
| **P1-5** | **IC/PnL par régime** (bull/bear, high/low vol, high/low dispersion) | 2j | 🔥 | Analyse de robustesse, pas de feature engineering. VIX/MOVE/etc. n'améliorent pas le modèle, mais le signal est-il stable dans tous les régimes ?<br>→ B4 en bull market vs bear market vs high vol vs low vol.<br>→ Si IC tombe à zéro en bear market → information utile pour le risk management (quand désactiver). |
| **P1-6** | **Rolling IC 6/12 mois** (stabilité temporelle) | 1j | 🔥 | IC glissant par période de 6-12 mois pour détecter un modèle qui a un bon IC moyen grâce à 2 très bonnes périodes.<br>→ IC > 0 sur chaque période ? IC IR stable ? Max drawdown du signal ? |

### ⚠️ P2 — Optimisation (après P1 confirmé)

| # | Action | Effort | Impact | Pourquoi |
|---|--------|:------:|:------:|----------|
| **P2-1** | Optimisation de poids P1/P2 (contraintes secteur) | 5j | 🔥🔥 | Après P0-1. Transforme un bon score en bon PnL. |
| **P2-2** | Feature ablation F0-F4 per-symbol | 3j | 🔥 | Comprendre CE QUI marche dans le per-symbol. Après P1-1. |

### 💡 P3 — Idées (priorité basse, à tester si bande passante)

| # | Action | Effort | Impact | Pourquoi |
|---|--------|:------:|:------:|----------|
| **P3-1** | Target asymétrique LONG/SHORT | 2j | ⚠️ | F1 short < 0.50 → pénaliser plus le LONG. |
| **P3-2** | Ensemble CatBoost + LightGBM (stacking) | 3j | ⚠️ | B12 : ils excellent sur des secteurs différents. |
| **P3-3** | XGBoost (3ᵉ algo) | 2j | ⚠️ | Challenger unique, pas une grille. Même famille que CatBoost/LightGBM → gain marginal probable.<br>→ 1 run suffit pour décider : si XGBoost < CatBoost, on ferme sans regret. Si XGBoost > CatBoost, retester top 3 (B4/B10/B3). |
| **P3-4** | NN simple (MLP 2-3 couches) | 3j | ❓ | Interactions non-linéaires. Risqué. |
| **P3-5** | Volume profile / liquidity features | 2j | ❓ | Jamais testé. 1 run avec les 5-10 features volume/liquidité ajoutées à la baseline B4. Si IC > B4, ça vaut le coup d'investiguer. Sinon, on ferme. |
| **P3-6** | Rolling feature importance + dropout | 3j | ❌ | Éviter overfitting. Faible priorité. |

### ✅ Fait / Archivé

| # | Action | Statut |
|---|--------|:------:|
| — | Per-sector : 8 campagnes + B0-B19 → aucun alpha | ✅ Clos, research-only |
| — | Per-symbol 50-100 titres liquides | ✅ **Fait (2026-08-11)** — pas d'alpha supplémentaire vs Global Ranking |
| — | Flags macro (VIX, VXN, VIX3M, MOVE, regime) | ✅ Testés B5-B8, B11 → 0 gain |
| — | Fondamentaux, cross-sectional, screener, sentiment | ✅ Testés B1, B2, B9, B13 → 0 ou négatif |
| — | Target experiments T1/T2/T3 (B15-B17) | ✅ Testés → 0 gain Global, T3 = 72% flat |
| — | Training from 2011 (B18/B19) | ✅ Testé → IC −18% à −22%, confirme 2016 |
| — | Stacking (B14) | ✅ Testé → V2 −0.1%, champion 🥈 |
| — | Audit leakage (P0/P1) | ✅ Archivé dans prompt/ml/ |
| — | LSTM calibration (MSE hors échelle) | 📦 Quarantaine |
| — | CAPM + YetiRank B25 | ✅ **Fait (2026-08-12)** — NOUVEAU RECORD IC 0.0241, +19% vs B4 |
| — | CAPM + QueryRMSE B26 | ✅ **Fait (2026-08-12)** — IC 0.0172, −15% vs B4, rejeté |
| — | YetiRank B20 (B4 + YetiRank) | ✅ **Fait (2026-08-12)** — IC 0.0238, +18% vs B4 |
| — | QueryRMSE B21, QuerySoftMax B22 | ✅ **Faits (2026-08-12)** — < RMSE, rejetés |
| P0-1 | Caps sectoriels en production | ✅ **Fait (2026-08-11)** |

### 🎯 Ordre d'exécution

```
P0-1 (caps) ──→ ✅ fait
  │
  ├─→ P1-1 (per-symbol) ──→ ✅ fait
  │
  ├─→ P1-2 (YetiRank B4+B10) ──→ dernier levier Global
  │     │
  │     └─→ P1-3 (target = rang) ──→ cumulable avec YetiRank
  │
  ├─→ P1-4 (portfolio OOS) ──→ validation tradabilité
  │
  ├─→ P1-5 (IC/PnL par régime) ──→ robustesse
  │
  ├─→ P1-6 (rolling IC 6/12m) ──→ stabilité temporelle
  │
  └─→ P2-1 (optimisation poids) ──→ après P0-1
        │
        └─→ P3-* (idées) ──→ si bande passante
```
