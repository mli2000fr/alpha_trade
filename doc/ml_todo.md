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
| **B37** | **B25 + symbols 393 (swing score)** | 0.0123 | 0.89 | H3 | — | — | ❌ **−49% vs B25** — univers sélectionné par swing score : H10 0.0116, **H20 mort** (0.0035, decile spread −0.0003). Pire que B35 (0.0154) → la composition prime sur la taille : **garder l'univers liquidité 400** |

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
- **Universe 393 swing score** (B37 = B25 + 393 symboles sélectionnés par swing score) : ❌ IC 0.0123 (−49% vs B25), IR 0.89. H10 0.0116, H20 mort (0.0035, Decile Spread −0.0003), meilleur horizon H3 (0.0199). Pire que B35 (196 liquidité, 0.0154) → **la composition de l'univers prime sur la taille : l'univers « swing score » est toxique pour le Global Ranking. Garder la sélection liquidité 400.**
- **Universe 300 parmi 400** (B38 = B25 + 300 symboles pris parmi les 400 liquidité, `a8aadc`) : ⚠️ **QUASI ÉQUIVALENT À B25** — IC 0.0229 (−5% vs B25), **IR 1.14 (+7%, meilleur de la série)**, H15 best (0.0255, IR 1.54), H10/H20 solides. LightGBM s'effondre (catboost 5/5). **La réduction 400→300 à composition égale coûte −5% d'IC et améliore la stabilité → conforte le garde-fou breadth live 75 % (= 300).**
- **YetiRank** (B20) : IC 0.0238 (+18% vs B4), gagne 3/5 horizons (H3/H15/H20).
- **QueryRMSE / QuerySoftMax** (B21/B22/B26/B27) : ❌ < RMSE avec ou sans CAPM (0.0161-0.0188). **Seul YetiRank surpasse RMSE. Matrice finale : YetiRank+CAPM 0.0241 🏆 > YetiRank 0.0238 > RMSE 0.0202 > Query***
- **PairLogit / PairLogitPairwise** (B23/B24/B28/B29) : ⛔ abandonnés — 20h+ bloquées sur H3, coût O(n²) par groupe inacceptable pour le Global Ranking.
- **Per-Sector ≈ hasard** : F1 macro ~0.33, F1 short < 0.50. Seul le Global Ranking a un vrai pouvoir prédictif.

## � Reste à faire — Priorisé (2026-08-11)

### 🔥 P0 — Quick wins (impact immédiat, effort minimal)

| # | Action | Effort | Impact | Pourquoi |
|---|--------|:------:|:------:|----------|
| **P0-1** | **Caps sectoriels en production** | 1j | 🔥🔥 | ✅ **Fait (2026-08-11)** — `sector_limits.enabled: true` + alignement backtest/live dans `capital_presets.yaml`. |
| **P0-4** | **⚠️ Univers live dégradé + garde-fou breadth** | 1j | 🔥🔥🔥 | 🔴 **CRITIQUE** — l'univers tradable live est écrasé : 4-279 symboles/jour (avg 48) depuis 2024-07 vs 311-391 dans le backtest validé. Cause en amont : ingestion barres/quotes (eodhd s'arrête 2026-07-10, snapshots quotes clairsemés) → l'étape 6 n'évalue que quelques symboles. **Fait (2026-08-13)** : garde-fou `modelFactory/universe_guard.py` **bloquant** — seuil = `ml_min_universe_pct: 75` (% du référentiel `config/ticket_recherche.txt` = 400 → 300), branché dans l'étape 10 dispatch et `predict_per_sector` (6/6 tests + E2E : blocage vérifié, exit 1). **✅ Fait (2026-08-13) — garde-fou en place ET seuil validé par B38** : B25 sur 300 symboles (parmi les 400) → IC 0.0229 (−5%), IR 1.14 record → un live à 300 symboles conserve l'alpha. **Réparation de l'ingestion (étapes 1/4/6) : prise en charge par l'utilisateur.** |

### 🔥 P1 — Alpha additionnel (impact élevé, effort moyen)

| # | Action | Effort | Impact | Pourquoi |
|---|--------|:------:|:------:|----------|
| **P1-1** | ~~**Per-symbol 50-100 titres liquides**~~ | 5j | 🔥🔥 | ✅ **Fait** |
| **P1-2** | **CatBoost YetiRank** | 2j | 🔥 | ✅ **B20/B25 terminés** — B25 (CAPM+YetiRank) IC record 0.0241 (+19%). YetiRank validé, CAPM+YetiRank encore meilleur.<br>→ Prochaine étape : per-horizon specialization ou lancer B25 en production. |
| **P1-3** | **Target = rang percentile** (optimiser IC au lieu de MSE) | 3j | 🔥 | ✅ **B30 testé (2026-08-12)** — ❌ ÉCHEC. IC 0.0153 (−36% vs B20). Le rank brut détruit H5/H15/H20, CatBoost s'effondre et perd 3/5 horizons face à LightGBM. Seul H3 profite (+23%). **Le pipeline complet (smoothing + neutralisation) est essentiel. P1-3 clos — ne pas retenter.** |
| **P1-4** | **Portfolio OOS V1/V2/V3/V4** (top 5/10/20/30%) | 3j | 🔥🔥 | ✅ **Fait (2026-08-13, chiffres corrigés 2026-08-14)** — Backtest B25 complet (400 symboles, 2019-01→2024-06, frais **5 bps entrée + 5 bps sortie**). **+205.9% total, CAGR 22.6%, Sharpe 1.05, Sortino 1.41, Max DD 27.3%, PF 1.30, 386 trades (173L/213S).** Exposition brute moy. 61.9%, nette −29.7%, turnover 49.0x/an. PnL net 200.1k cohérent avec l'equity. **Le signal survit aux frictions réelles.** ⚠️ Les chiffres initiaux du 13/08 (+126.7%, 358 trades) venaient du run matinal `b25_p15_step3` tourné sur un arbre de travail dirty (dataset_hash eafc60) ; référence corrigée = `b25_p23_control`/`control2` (hash cf8b17, reproductible au bit près). (Rappel run précédent 1+5 bps : +151.7%, Sharpe 0.90 — sensibilité aux frais mesurée, à re-vérifier sur l'arbre propre.) |
| **P1-5** | **IC/PnL par régime** (bull/bear, high/low vol, high/low dispersion) | 2j | 🔥 | Analyse de robustesse, pas de feature engineering.<br>**Étape 2 (IC) ✅ 2026-08-13** — `scripts/analyze_ic_by_regime_b25.py`, 722 jours, 392 symboles : sector-neutral bull +0.0146 / range +0.0169 / vol +0.0137 / bear +0.0226 (11j) — stable partout ; vol-scalé : low_disp +0.0150 vs high_disp −0.0037 ; 2020 = −0.0311 (krach, seul trou).<br>**Étape 3 (PnL) ✅ 2026-08-13** — ⚠️ run effectué sur l'arbre dirty du matin (358 trades, +126.65%, hash eafc60) : high_disp **+157.9k** vs low_disp −32.4k ; vol +82.7k, range +51.2k, **bull −13.4k** ; shorts +86.2k (longs +39.3k). Equity Sharpe : vol 2.06, bear 1.64, bull −0.08. A/B post-hoc : couper high_disp → −125% ; couper vol → −66% ; couper dd_deep → −45%. **Verdict : NE PAS filtrer high_disp/vol/dd (c'est là que la stratégie gagne) ; seule piste = réduire les shorts en régime bull (test overlay P2).**
| **P1-6** | **Rolling IC 6/12 mois** (stabilité temporelle) | 1j | 🔥 | ✅ **Fait (2026-08-13)** — `scripts/analyze_rolling_ic_b25.py` : IC sector-neutral moyen 0.0148 ; **fenêtres 252j : 100% positives** (471), fenêtres 126j : 94.3% positives (597) → le bon IC ne vient PAS de 2-3 périodes isolées. Roll 252j IR 1.92. Séquence négative max : 21 jours. Par année : 2019 −0.002, 2020 +0.016, 2021 +0.004 (point faible), 2022 +0.026, 2023 +0.017, 2024 +0.030. ⚠️ Le seul vrai trou reste 2020 sur l'IC **vol-scalé** (−0.031) : les krachs tuent l'alpha risk-adjusted, pas l'alpha brut. |

### ⚠️ P2 — Optimisation (après P1 confirmé)

| # | Action | Effort | Impact | Pourquoi |
|---|--------|:------:|:------:|----------|
| **P2-1** | Optimisation de poids P1/P2 (contraintes secteur) | 5j | 🔥🔥 | Après P0-1. Transforme un bon score en bon PnL.<br>**Inc.1 ✅ 2026-08-13** — `modelFactory/analyze_p21_attribution.py` : attribution sectorielle (Retail/Banking shorts +23k/+19k ; Health Care/Chemicals shorts −15k/−12k ; Technology = 12.1% notionnel pour PnL ≈ 0). `conviction` ≈ 1.0 partout (sizing actuel non différenciant). A/B post-hoc : rank-weighted +5.5%, rank² +9%, top1 +18% (DD accru).<br>**Inc.2 ✅ 2026-08-13, corrigé 2026-08-14** — mode `rank_weighted` ajouté (`risk_overlay.SizingConfig`, CLI, IHM, 11/11 tests). **A/B réel 5+5 bps sur arbre propre (même dataset_hash cf8b17) : equal 205.9%/Sharpe 1.05/DD 27.3% (386 trades) → rank_weighted 335.0%/Sharpe 1.26/DD 23.6% (+129 pts, 378 trades).** Cohérent (pnl_net 334k, expo brute 64.4%). ⚠️ Le « equal » initial du 13/08 (126.6%) était un run dirty (hash eafc60) — le gain réel du mode est **+129 pts, pas +208**. **In-sample** (règle choisie sur la même période) → **Inc.4 OOS 2025 obligatoire avant promotion.**<br>**Inc.4 ✅ OOS 2025 (2026-08-13)** — backfill rangs 2025 sur univers ticket (260 dates, 394-400 symboles/j, synthèse 340 603 lignes, smoke 400 ✓). **A/B OOS : equal 28.0%/Sharpe 1.10/Sortino 1.82/DD 15.6% → rank_weighted 33.4%/Sharpe 1.18/Sortino 2.00/DD 18.5% (+5.4 pts retour, +0.08 Sharpe, +0.18 Sortino, PF 1.27, 119 trades).** → **le gain se confirme hors échantillon** (plus modeste qu'in-sample, DD +2.9 pts). Shorts restent le moteur (+34.3k vs longs −3.2k). **Recommandation : adopter rank_weighted (ou variante adoucie) en défaut après Inc.3 sectoriel.**<br>**Inc.3 ✅ OOS 2025 (2026-08-13)** — sizing sectoriel : multiplicateurs dérivés de l'attribution Inc.1 (≥+150bps→1.25 ; +50..+150→1.10 ; ±50→1.00 ; −50..−150→0.75 ; ≤−150→0.50), appliqués au mode rank_weighted (`--sector-multipliers-json @config/p21_sector_multipliers.json`, chargement auto du mapping `stock_metadata`). **A/B OOS : rankw 33.41%/Sharpe 1.182/Sortino 2.002/DD 18.53% → rankw+secteur 34.37%/1.203/2.034/18.75% (+1.0 pt retour, +0.02 Sharpe, PF 1.276, +931 PnL).** Gain réel mais faible, DD +0.2 pt → adopté (5/6 métriques positives), à surveiller.<br>**IHM ✅ 2026-08-13** — page backtest : selectbox « Multiplicateurs sectoriels » (off/default/custom) dans le bloc Calibration conviction/Kelly + expander « Calibrer depuis un run passé » (exécute `modelFactory.analyze_p21_attribution`, aperçu des facteurs). `backtesting_runner` : `sizing_mode` inclut `rank_weighted`, `sector_multipliers_json` transmis au CLI. Tests 30/30 + 12/12.<br>**Live ✅ 2026-08-13** — branchement `risk_management` : `SizingConfig` extrait dans `common/sizing.py` (ré-export `backtesting.risk_overlay`), `RiskConfig.sizing_mode`/`sector_multipliers_path` + `build_sizing_config()`, `compute_allocation_factors()` dans `portfolio_builder` (scale du sizing ATR/Kelly par les facteurs, contraintes conservées), CLI `--sizing-mode`/`--sector-multipliers-path`. Opt-in (`sizing_mode: atr` par défaut). Tests 22/22 + 30/30 + 177/177.<br>**IHM ✅ 2026-08-13** — tout pilotable depuis l'IHM : Pipeline > Risk > expander « Allocation P2-1 » (mode + JSON, propagés au step 11) ; Calibrations poids → boutons « Promouvoir/Bloquer pour le live » (`eligible_for_live`, via `set_weights_calibration_live_eligibility` + `safe_execute`) ; promotion batch = bouton page ML. Tests IHM 87/87.<br>**→ P2-1 terminé : rank_weighted + multiplicateurs sectoriels = sizing de production candidat.** ✅ **Activé en live via IHM (2026-08-13, utilisateur).** |
| **P2-3** | **Overlay no-shorts en bull strict** (SPY>SMA200 **ET** ret60j>+3%) | 1j | 🔥 | ❌ **CLOS (2026-08-13/14)** — vrai A/B sur le pipeline actuel : control equal 205.9%/Sharpe 1.05/DD 27.3% → no_shorts 140.1%/0.81/24.1% (−65.8 pts) → no_trades 127.2%/0.96/DD 15.0% (DD −12.3 pts mais retour/Sharpe/PnL effondrés). **2/6 métriques seulement → overlay rejeté.** Runs faits sur les **bonnes données B25** (rangs DB + univers PIT, indépendants de `ticket_recherche.txt`). Le post-hoc positif (+9.4%/+10.7%) était un artefact de l'ancien run `b25_p15_step3` : sur le pipeline actuel les shorts GAGNENT en bull strict (+202k moteur). ✅ **Reproductibilité confirmée 2026-08-14** — `b25_p23_control2` ≡ `b25_p23_control` au bit près (205.9258 %, même hash cf8b17) → pipeline déterministe. La dérive 126.6%→205.9% venait du run matinal `b25_p15_step3` (arbre dirty, hash eafc60) — sans effet sur les 4 runs P2-3 ni sur le verdict. |
| **P2-2** | Feature ablation F0-F4 per-symbol | 3j | 🔥 | 📌 **TODO à venir (différé 2026-08-14)** — un run per-symbol antérieur a donné de **meilleurs résultats que le per-sector** → piste **exploitable**, à reprendre plus tard. Décision : concentration sur le modèle global pour l'instant ; le per-symbol sera retravaillé ultérieurement (ablation F0-F4, protocole `prompt/ml/ml_analyse_per_symbol.md`). ⚠️ Ne pas supprimer la piste. |
| **P2-4** | Ablation features pour comprendre pourquoi les longs sous-performent (réparer le long) | 3j | 🔥🔥 | 📌 **TODO à venir (retrouvé 2026-08-14)** — item d'origine de `logs.txt` (« P2-2 : ablation features pour comprendre pourquoi les longs sous-performent — pour réparer le long »), remplacé par erreur dans `doc/ml_todo.md` par l'ablation per-symbol. Preuves : control propre P2-3 → **longs −2.2k vs shorts +202.3k** (le long ≈ poids mort sur 2019-2024) ; P1-5 → longs +39.3k vs shorts +86.2k. Objectif : ablation par famille de features pour identifier ce qui détruit la jambe longue, puis corriger. Complémentaire à P3-1 (target asymétrique long / renforcer le scoring long). |

### 💡 P3 — Idées (priorité basse, à tester si bande passante)

| # | Action | Effort | Impact | Pourquoi |
|---|--------|:------:|:------:|----------|
| **P3-1** | Target asymétrique LONG/SHORT | 2j | ⚠️ | F1 short < 0.50 → pénaliser plus le LONG. |
| **P3-2** | Ensemble CatBoost + LightGBM (stacking) | 3j | ⚠️ | B12 : ils excellent sur des secteurs différents. |
| **P3-3** | XGBoost (3ᵉ algo) | 2j | ⚠️ | ❌ **CLOS (2026-08-14, batch B39)** — challenger rank:ndcg sur baseline B25 (mêmes flags/features/folds) : **perd sur les 5 horizons** — H3 0.0014 vs 0.0170 (−92 %), H5 0.0108 vs 0.0223 (−52 %), H10 0.0145 vs 0.0279 (−48 %), H15 0.0197 vs 0.0260 (−24 %), H20 0.0178 vs 0.0274 (−35 %). **CatBoost YetiRank reste champion — ne pas retenter XGBoost.** Support conservé : `--global-model-name xgboost` (candidat unique) + championnat à 3 candidats via `--global-champion`, IHM (dropdown + checkbox). Incident 00:28 (sample_weight/qid) corrigé. |
| **P3-4** | NN simple (MLP 2-3 couches) | 3j | ❓ | Interactions non-linéaires. Risqué. |
| **P3-5** | Volume profile / liquidity features | 2j | ❓ | **⏳ LANCÉ (2026-08-14, 2 runs)** — 10 features volume/liquidité opt-in (`--include-volume-features` : dollar_volume_log_20, dollar_volume_trend_20_60, amihud_illiq_20, volume_std_ratio_20, up_volume_ratio_20, volume_price_corr_20, obv_slope_20, dollar_volume_zscore_20, high_low_range_20, volume_skew_20). Câblage complet : `features.py` (compute/get_columns/fingerprint), `DataConfig`, CLI, global_ranking, dataset, trainer_sector, global_model. **B40** = B4 (short+SPY, RMSE) + volume → test d'isolation vs B4 (0.0202). **B41** = B25 (CAPM+YetiRank) + volume (155 feats) → **test décisif** vs la colonne catboost de B25 (0.0241). Candidat catboost unique pour les deux. **Décision : si IC(B41) > IC catboost B25 → les features volume aident le champion (investiguer). Sinon, on ferme.** |
| **P3-6** | Rolling feature importance + dropout | 3j | ❌ | Éviter overfitting. Faible priorité. |

### ✅ Fait / Archivé

| # | Action | Statut |
|---|--------|:------:|
| — | Per-sector : 8 campagnes + B0-B19 → aucun alpha | ✅ Clos, research-only |
| — | Per-symbol 50-100 titres liquides | ✅ **Fait (2026-08-11)** — pas d'alpha supplémentaire vs Global Ranking. ⚠️ Note utilisateur (2026-08-14) : un run per-symbol antérieur battait le per-sector et est exploitable → piste rouverte, **reprise prévue plus tard** (P2-2 TODO à venir) |
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
| — | P1-4 backtest OOS B25 | ✅ **Fait (2026-08-13, corrigé 2026-08-14)** — **5+5 bps : +205.9%, Sharpe 1.05, DD 27.3%** (référence propre `b25_p23_control`/`control2`, reproductible bit-for-bit) — signal validé en PnL réel |
| — | Contrôle d'intégrité (reproductibilité) | ✅ **Clos (2026-08-14)** — `b25_p23_control2` ≡ `b25_p23_control` bit-for-bit → pipeline déterministe ; dérive du 13/08 = arbre dirty (run matinal `b25_p15_step3`, hash eafc60) ; références recalculées sur l'arbre propre : baseline 205.9%, A/B rankw in-sample +129 pts, OOS 2025 +5.4 pts |
| — | **P1-5 IC/PnL par régime** | ✅ **Fait (2026-08-13)** — IC stable partout (sector-neutral 0.014-0.017, 2020 seul trou). PnL : 80% du gain en high_disp+vol, bull perdant (−13.4k), shorts moteur (+86.2k). **Ne pas filtrer par régime ; piste P2-3 = no-trades en bull strict.** |
| — | **P1-6 Rolling IC 6/12 mois** | ✅ **Fait (2026-08-13)** — fenêtres 252j 100% positives, 126j 94.3% → stabilité temporelle confirmée |
| — | **🔥 Promotion B25 en production** | ✅ **Fait (2026-08-13)** — `model_serving_batch` → `model-factory-20260811223551-ef2cd0` (remplace la référence morte `model-factory-20260725215754-bbd8ba`). **✅ Flux live activé** : (1) fix jointure `risk_management/db_io.load_predictions_asof` (égalité `training_run.symbol=prediction.symbol` supprimée — bloquait les runs synth rank-driven ; colonnes qualifiées ; 23/23 tests + test de régression ajouté) ; (2) `config.yaml` `live_batch_id` = B25 ; (3) génération live : 189 rangs 2026-07-10 + synthèse 259 428 lignes ; (4) smoke test : 545 symboles consommés dont 37 datés 2026-07-10 (19L/18S). ⚠️ **Ingestion à vérifier** : les barres eodhd s'arrêtent au 2026-07-10. Job quotidien/backfill : `python -m modelFactory.predict_per_sector` (générique : tout batch per-sector via `--batch-id`).
| — | **Étape 10 dispatch intelligent per-symbol/per-sector** | ✅ **Fait (2026-08-13)** — `detect_batch_training_mode()` (argv_json/command_line + fallback runs GICS/sentinelle) ; `modelFactory/cli.py` mode predict aiguille automatiquement : per-symbol → `predict_batch` (inchangé), per-sector → global ranks + synthèse (live ET plage historique) ; CLI `--batch-id` explicite (fixe aussi le hijack `backtest_batch_id`) passé par l'IHM ; drift gate conservé. 7/7 tests unitaires + run E2E réel (189 rangs, 259 428 lignes). **L'étape 10 est désormais batch-agnostique (Batch LIVE et Batch BACKTEST).** |
| — | Campagne YetiRank B31-B34 (flags) | ✅ **Fait (2026-08-13)** — aucun flag ne bat B25 |
| — | Univers 196 (B35/B36) | ✅ **Fait (2026-08-13)** — ❌ détruit H10-H20, garder 400 |
| — | Univers 393 swing score (B37) | ✅ **Fait (2026-08-13)** — ❌ IC 0.0123 (−49% vs B25), H20 mort — garder univers liquidité 400 |
| — | Univers 300 parmi 400 (B38) | ✅ **Fait (2026-08-13)** — ⚠️ IC 0.0229 (−5% vs B25), IR 1.14 record — réduction 400→300 à composition égale quasi indolore → conforte le garde-fou breadth 75 % |
| — | Univers `ticket_recherche.txt` (liste B25) | ✅ **Rétabli (2026-08-13)** — la liste B25 = `TSCO,SMCI,TTD...` (commit `4457fd1f`, état au moment de l'entraînement B25). Le commit `568d91d` (12:11) avait remplacé le fichier par une liste erronée (`MRNA,IBRX...`), restaurée à 13:48 puis confirmée par l'utilisateur à 23:56. ⚠️ Ne pas confondre avec `ticket_mid_cap_400.txt` (même taille, 11/08). |
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
  ├─→ P1-5 (IC/PnL par régime) ──→ ✅ fait (2026-08-13) : IC stable, PnL concentré vol/high_disp, bull faible
  │
  ├─→ P1-6 (rolling IC 6/12m) ──→ ✅ fait (2026-08-13) : fenêtres 252j 100% positives
  │
  ├─→ 🔥 Promotion B25 en production ──→ ✅ fait (2026-08-13) — serving=B25 + fix jointure live + flux live activé (job quotidien python -m modelFactory.predict_per_sector)
  │
  └─→ P2-1 (optimisation poids) ──→ ✅ fait (rank_weighted + secteur validés OOS, activés en live)
        │
        ├─→ P2-3 (overlay no-trades bull strict) ──→ ✅ clos (2026-08-13/14) : A/B réel 3 runs → ❌ rejeté (2/6 métriques)
        │
        └─→ P3-* (idées) ──→ si bande passante
        └─→ Contrôle d'intégrité (dérive dataset_hash) ──→ ✅ clos 2026-08-14 : pipeline déterministe (control2 ≡ control bit-for-bit) ; toutes les références (baseline 205.9 %, rankw 335.0 %, OOS 2025) proviennent de l'arbre propre → aucun re-run nécessaire
```
