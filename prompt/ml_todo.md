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
| B27 | B10 + QuerySoftMax | 0.0161 | 0.95 | H5 | — | — | ❌ −20% vs B4, −33% vs B25 |
| B23 | B4 + PairLogit | ⛔ | ⛔ | ⛔ | ⛔ | — | ⛔ abandonné (20h+, bloqué H3) |
| B24 | B4 + PairLogitPairwise | ⛔ | ⛔ | ⛔ | ⛔ | — | ⛔ abandonné (20h+, bloqué H3) |
| B28 | B10 + PairLogit | ⛔ | ⛔ | ⛔ | ⛔ | — | ⛔ abandonné (20h+, bloqué H3) |
| B29 | B10 + PairLogitPairwise | ⛔ | ⛔ | ⛔ | ⛔ | — | ⛔ abandonné (20h+, bloqué H3) |
| B30 | B20 + P1-3 raw rank target | 0.0153 | 0.49 | H10 | — | — | ❌ −36% vs B20, CatBoost perd 3/5 horizons |
| B31 | B4 + fondamentaux + YetiRank | 0.0146 | 0.66 | H5 | — | cb 6/11 | ❌ −28% vs B4, −39% vs B25 (fondamentaux toxiques aussi en YetiRank) |
| B32 | B4 + score components + YetiRank | 0.0224 | 0.95 | H10 | −8.0% | lgbm 8/11 | ⚠️ 3ᵉ (+11% vs B4, −7% vs B25) — YetiRank sauve les score comps (B12 0.0188→0.0224) mais ne bat pas B20/B25 |
| B33 | B4 + cross-sectional + YetiRank | 0.0138 | 0.72 | H5 | −24.6% (V4) | lgbm 7/11 | ❌ −32% vs B4, −43% vs B25 — sectoriel toxique aussi en YetiRank (pire que B13) |
| B34 | B4 + screener + YetiRank | 0.0151 | 0.78 | H10 | −13.4% | lgbm 6/11 | ❌ −25% vs B4, −37% vs B25 (screener toxique aussi en YetiRank) |
| B35 | B25 + symbols 196 | 0.0154 | 0.51 | H3 | −9.7% | lgbm 7/9 | ❌ −36% vs B25 — 196 symboles boostent H3 (0.0283, IR 1.46) mais tuent H10-H20. **Garder la liste 400.** |
| B36 | B20 + symbols 196 | 0.0148 | 0.45 | H3 | −15.0% | lgbm 7/9 | ❌ −38% vs B20 — confirme B35 : 196 symboles tuent H10-H20, le CAPM n'y change rien |

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
- **Fondamentaux + YetiRank** (B31) : ❌ IC 0.0146 (−28% vs B4, −39% vs B25), IR 0.66. Encore pire que B9 RMSE (0.0157). Les fondamentaux détruisent le signal même avec YetiRank. LightGBM s'effondre à H10-H20.
- **Score components + YetiRank** (B32) : ⚠️ IC 0.0224 (+11% vs B4, +19% vs B12 RMSE), IR 0.95. Meilleur batch hors CAPM mais ne bat ni B20 (0.0238) ni B25 (0.0241). H15/H20 quasi au niveau de B20. Confirme : **B25 reste champion.**
- **Cross-sectional + YetiRank** (B33) : ❌ IC 0.0138 (−32% vs B4, −43% vs B25), IR 0.72. Encore pire que B13 RMSE (0.0144). Les features cross-sectional détruisent le signal avec ou sans YetiRank. H15 Decile Spread 0.0046 (séparation top/bottom nulle). **Campagne feature-flags close : B25 champion définitif.**
- **Screener + YetiRank** (B34, commande avec `--enable-cross-sectional` en plus) : ❌ IC 0.0151 (−25% vs B4, −37% vs B25), IR 0.78. H20 s'effondre (0.0102, IR 0.46), H15 Decile Spread 0.0044. LightGBM quasi nul partout (IC ≤ 0.007). **Dernier batch de la campagne : aucun flag ne bat B25.**
- **Universe 196** (B35 = B25 sur la liste réduite) : ❌ IC 0.0154 (−36% vs B25), IR 0.51. Réduire 400→196 booste H3 (0.0283, IR 1.46 — record mais sur petit univers, non comparable) mais détruit H10/H15/H20 (0.012/0.008/0.006). CatBoost perd H10/H20 face à LightGBM. **Garder la liste de 400 symboles (config/ticket_mid_cap_400.txt).**
- **Universe 196 + B20** (B36) : ❌ IC 0.0148 (−38% vs B20), IR 0.45. H3/H5 très forts (0.0277/0.0246, IR 1.57/1.23) mais H10-H20 morts (≤0.008, Decile Spread ≤0.004). **Confirme B35 : le petit univers détruit les horizons longs avec ou sans CAPM. Garder la liste 400.**
- **YetiRank** (B20) : IC 0.0238 (+18% vs B4), gagne 3/5 horizons (H3/H15/H20).
- **QueryRMSE / QuerySoftMax** (B21/B22/B26/B27) : ❌ < RMSE avec ou sans CAPM (0.0161-0.0188). **Seul YetiRank surpasse RMSE. Matrice finale : YetiRank+CAPM 0.0241 🏆 > YetiRank 0.0238 > RMSE 0.0202 > Query***
- **PairLogit / PairLogitPairwise** (B23/B24/B28/B29) : ⛔ abandonnés — 20h+ bloquées sur H3, coût O(n²) par groupe inacceptable pour le Global Ranking.
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
| **P1-3** | **Target = rang percentile** (optimiser IC au lieu de MSE) | 3j | 🔥 | ✅ **B30 testé (2026-08-12)** — ❌ ÉCHEC. IC 0.0153 (−36% vs B20). Le rank brut détruit H5/H15/H20, CatBoost s'effondre et perd 3/5 horizons face à LightGBM. Seul H3 profite (+23%). **Le pipeline complet (smoothing + neutralisation) est essentiel. P1-3 clos — ne pas retenter.** |
| **P1-4** | **Portfolio OOS V1/V2/V3/V4** (top 5/10/20/30%) | 3j | 🔥🔥 | ✅ **Fait (2026-08-13)** — Backtest B25 complet (400 symboles, 2019-01→2024-06, frais **5 bps entrée + 5 bps sortie**). **+126.7% total, CAGR 16.1%, Sharpe 0.81, Sortino 1.06, Max DD 32.4%, PF 1.32, 358 trades (143L/215S).** Exposition brute moy. 62.8%, nette −35.6%, turnover 45.7x/an. Bootstrap : return moyen 124.5% ≈ réel, IC Sharpe [0.06, 1.03]. PnL net cohérent avec l'equity. **Le signal survit aux frictions réelles.** (Rappel run précédent 1+5 bps : +151.7%, Sharpe 0.90 — sensibilité aux frais mesurée.) |
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
| — | CAPM + QuerySoftMax B27 | ✅ **Fait (2026-08-12)** — IC 0.0161, −20% vs B4, rejeté |
| — | P1-4 backtest OOS B25 | ✅ **Fait (2026-08-13)** — **5+5 bps : +126.7%, Sharpe 0.81, DD 32.4%** (1+5 bps : +151.7%, Sharpe 0.90) — signal validé en PnL réel |
| — | Campagne YetiRank B31-B34 (flags) | ✅ **Fait (2026-08-13)** — aucun flag ne bat B25 |
| — | Univers 196 (B35/B36) | ✅ **Fait (2026-08-13)** — ❌ détruit H10-H20, garder 400 |
| — | PairLogit / PairLogitPairwise (B23/B24/B28/B29) | ⛔ **Abandonnés (2026-08-12)** — 20h+ de calcul bloquées sur H3, trop lents (O(n²) par groupe) |
| — | P1-3 raw rank target (B30) | ✅ **Fait (2026-08-12)** — ❌ ÉCHEC, IC 0.0153, pipeline complet essentiel |
| — | YetiRank B20 (B4 + YetiRank) | ✅ **Fait (2026-08-12)** — IC 0.0238, +18% vs B4 |
| — | QueryRMSE B21, QuerySoftMax B22 | ✅ **Faits (2026-08-12)** — < RMSE, rejetés |
| P0-1 | Caps sectoriels en production | ✅ **Fait (2026-08-11)** |

### 🎯 Ordre d'exécution

```
P0-1 (caps) ──→ ✅ fait
  │
  ├─→ P1-1 (per-symbol) ──→ ✅ fait
  │
  ├─→ P1-2 (YetiRank B4+B10) ──→ ✅ fait (B25 champion 0.0241)
  │
  ├─→ P1-3 (target = rang) ──→ ✅ testé (B30 ❌ échec, pipeline complet essentiel)
  │
  ├─→ P1-4 (portfolio OOS) ──→ ✅ fait (2026-08-13 : 5+5bps +126.7%, Sharpe 0.81, signal validé)
  │
  ├─→ P1-5 (IC/PnL par régime) ──→ robustesse
  │
  ├─→ P1-6 (rolling IC 6/12m) ──→ stabilité temporelle
  │
  ├─→ 🔥 Promotion B25 en production ──→ prochaine étape majeure
  │
  └─→ P2-1 (optimisation poids) ──→ après P0-1
        │
        └─→ P3-* (idées) ──→ si bande passante
```
