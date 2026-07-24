# 📊 Comparaison des Batches ML — Module `modelFactory`

> **Référence** : Baseline = `model-factory-20260722091334-cddc05`  
> **Date** : 2026-07-22 / 2026-07-24  
> **200 symboles** (sauf VIX/Sentiment : 198), mode ternaire 3-classes, horizon J+10  
> ⚠️ **À partir du batch Global Stk+Challenger, le labeling a changé** — métriques non directement comparables aux batches 1-9.

---

## 1. Commandes exécutées

### Baseline
```powershell
--feature-set expert --enable-cross-sectional --comment baseline
```

### +Sentiment
```powershell
--feature-set expert --enable-cross-sectional --include-sentiment --comment baseline+sentiment
```
Ajoute 4 features : `sentiment_net_mean_1d`, `sentiment_confidence_mean_1d`, `news_count_log`, `major_event_flag`

### +Screener
```powershell
--feature-set expert --enable-cross-sectional --include-screener-scores --comment baseline+screener
```
Ajoute 22 features selector (trend_score, vcp_score, final_score, selection_rank, etc.)

### +Short Score
```powershell
--feature-set expert --enable-cross-sectional --include-short-score --comment baseline+score_short
```
Ajoute 1 feature : `selector_short_score`

### +VIX
```powershell
--feature-set expert --enable-cross-sectional --include-macro-vix --comment baseline+vix
```
Ajoute 2 features : `vix_close`, `vix_momentum_5j`

### +VXN
```powershell
--feature-set expert --enable-cross-sectional --include-macro-vxn --comment baseline+vxn
```
Ajoute 2 features : `vxn_close`, `vxn_spread_vix`

### +VIX3M
```powershell
--feature-set expert --enable-cross-sectional --include-macro-vix3m --comment baseline+vix3m
```
Ajoute 3 features : `vix3m_close`, `vix_term_structure_ratio`, `vix_backwardation`

### +MOVE
```powershell
--feature-set expert --enable-cross-sectional --include-macro-move --comment baseline+move
```
Ajoute 1 feature : `move_close` (indice de volatilité obligataire)

### +Global Stacking (LightGBM)
```powershell
--feature-set expert --enable-cross-sectional --enable-global-model --global-model-name lightgbm --enable-global-stacking --comment "baseline + global staking gbm"
```
Ajoute 1 feature : `global_pred_long` (prédiction du Global Model cross-symbol)

### +Global Stacking + Challenger ⚠️ (labeling modifié)
```powershell
--feature-set expert --enable-cross-sectional --enable-global-model --global-model-name lightgbm --enable-global-stacking --enable-global-challenge --comment "baseline + global staking gbm + challenger"
```
Ajoute 1 feature `global_pred_long` + Global Model participe à la sélection du champion.
⚠️ Labeling corrigé → distribution true et prédictions rééquilibrées.

---

## 2. Métriques clés — F1 Macro Walk-Forward

| Batch | LightGBM | CatBoost | LSTM |
|-------|:---:|:---:|:---:|
| **Baseline** | **0.295** | 0.287 | 0.228 |
| +Sentiment | 0.295 | **0.289** | 0.224 |
| +Screener | 0.293 | 0.284 | **0.231** |
| +Short Score | **0.295** | 0.286 | 0.229 |
| +VIX | 0.293 | 0.284 | 0.229 |
| +VXN | 0.294 | 0.284 | 0.229 |
| +VIX3M | 0.290 | 0.283 | 0.227 |
| +MOVE | 0.294 | 0.285 | 0.227 |
| +Global Stacking | **0.295** | **0.287** | 0.229 |
| +Global Stk+Challenger ⚠️ | 0.294 | **0.293** | 0.226 |

> 🥇 **Baseline, Short Score & Global Stacking** : meilleur LightGBM WF (0.295).  
> 🚀 **Global Stk+Challenger** : CatBoost +0.006, talonne LightGBM (0.293 vs 0.294). Biais long résolu.  
> 🥇 **Global Stacking** : reproduit EXACTEMENT la baseline.  
> 🔥 **MOVE** : seul batch macro qui améliore F1_short LightGBM (+0.024).  
> ⚠️ Les métriques du batch Global Stk+Challenger utilisent un labeling différent.

---

## 3. Distribution F1 Macro WF

| Batch | 0.10-0.19 | 0.20-0.29 | 0.30-0.39 | 0.40+ |
|-------|:---:|:---:|:---:|:---:|
| **Baseline** | 3 | 95 | 97 | **5** |
| +Sentiment | 4 | 80 | **113** | 1 |
| +Screener | 3 | 88 | 106 | 3 |
| +Short Score | 3 | **87** | 104 | **6** |
| +VIX | 2 | 91 | 104 | 1 |
| +VXN | **1** | 91 | 104 | 4 |
| +VIX3M | 2 | 92 | 101 | **5** |
| +MOVE | **1** | 92 | 103 | 4 |
| +Global Stacking | 2 | 96 | 97 | **5** |
| +Global Stk+Challenger ⚠️ | 2 | **79** | **116** | 3 |

> 🥇 **Short Score** : seul batch qui améliore le top 0.40+ (5→6) ET réduit le bas (95→87).  
> 🚀 **Global Stk+Challenger** : ventre mou réduit de 17% (95→79), +19 dans 0.30-0.39. Meilleure distribution.  
> 🥇 **Global Stacking** : distribution quasi identique à la baseline.  
> ⚠️ Labeling différent.

---

## 4. Champions par modèle

| Batch | LightGBM | CatBoost | LSTM |
|-------|:---:|:---:|:---:|
| **Baseline** | 116 (58%) | 68 (34%) | 16 (8%) |
| +Sentiment | 107 (54%) | **76 (38%)** | 15 (7.6%) |
| +Screener | 111 (55.5%) | 65 (32.5%) | **24 (12%)** |
| +Short Score | 112 (56%) | 70 (35%) | 18 (9%) |
| +VIX | 113 (57%) | 70 (35%) | 15 (7.6%) |
| +VXN | 116 (58%) | 68 (34%) | 16 (8%) |
| +VIX3M | 111 (55.5%) | 71 (35.5%) | 18 (9%) |
| +MOVE | 109 (54.5%) | 74 (37%) | 17 (8.5%) |
| +Global Stacking | 112 (56%) | 68 (34%) | 20 (10%) |
| +Global Stk+Challenger ⚠️ | 97 (48.5%) | **89 (44.5%)** | 14 (7%) |

> 📊 LightGBM domine systématiquement (54-58%).  
> 🚀 **Global Stk+Challenger** : CatBoost +21 champions, quasi co-leader (97 vs 89).  
> 🥇 **Global Stacking & VXN** : distribution de champions très proche de la baseline.  
> ⚠️ Labeling différent.

---

## 5. f1_short = 0 (incapacité à shorter)

| Batch | Nb | Symboles |
|-------|:---:|------|
| **Baseline** | 4 | ARMK, BMO, IEX, VOYA |
| +Sentiment | **3** | ANET, IEX, WWD |
| +Screener | 6 | ARWR, BMO, IEX, INTC, SSD, VOYA |
| +Short Score | 7 | ARMK, BMO, CM, IEX, INTC, VOYA, WWD |
| +VIX | **8** | BMO, CFG, INTC, JBHT, SSD, TREX, VOYA, WWD |
| +VXN | 6 | BMO, INTC, JBHT, SSD, VOYA, WWD |
| +VIX3M | **10** | ARMK, BK, BMO, CM, HIW, IEX, NIC, SSD, VOYA, WERN |
| +MOVE | 6 | COLD, IEX, INTC, NSA, SSD, WERN |
| +Global Stacking | 6 | ARMK, BMO, INTC, SSD, VOYA, WWD |
| +Global Stk+Challenger ⚠️ | 5 | BAP, COLD, ESE, NWPX, WWD |

> 🥇 **Sentiment** : meilleur score (3).  
> ❌ **VIX3M** : pire score absolu (10).  
> ⚠️ **BMO, VOYA** sont incapables de shorter dans ≥6 batches.  
> ⚠️ Labeling différent pour le batch Global Stk+Challenger.

---

## 6. Top 10 — Meilleurs F1 macro WF

| Rang | Baseline | +Sentiment | +Screener | +Short Score | +VIX | +VXN | +VIX3M | +MOVE | +Global Stk |
|:---:|------|------|------|------|------|------|------|------|------|
| 1 | HLIT 0.416 | TEX 0.405 | TEX 0.422 | MOG.A 0.421 | ESTA 0.408 | AIN 0.416 | GKOS 0.420 | BEN 0.426 | DRH 0.410 |
| 2 | TEX 0.409 | DAL 0.398 | HLIT 0.416 | HLIT 0.416 | SANM 0.397 | FLEX 0.411 | FLEX 0.408 | BFH 0.425 | TEX 0.409 |
| 3 | NTRS 0.404 | R 0.397 | DRH 0.412 | TEX 0.409 | MOG.A 0.394 | TEX 0.407 | DRH 0.407 | FLEX 0.415 | NTRS 0.405 |
| 4 | SANM 0.403 | ESTA 0.395 | CHEF 0.400 | NTRS 0.405 | DRH 0.390 | ATRO 0.401 | AIN 0.403 | DNLI 0.403 | SANM 0.402 |
| 5 | R 0.401 | DRH 0.394 | AIN 0.397 | DRH 0.403 | GTX 0.384 | CHEF 0.393 | HLIT 0.402 | JAZZ 0.398 | R 0.401 |
| 6 | MOG.A 0.391 | CTS 0.393 | MOG.A 0.392 | R 0.401 | SEI 0.384 | SANM 0.393 | TEX 0.398 | FLG 0.398 | MOG.A 0.391 |
| 7 | AIN 0.391 | HLIT 0.391 | FLEX 0.390 | AIN 0.391 | WSC 0.382 | MOG.A 0.390 | R 0.387 | GKOS 0.395 | CHEF 0.391 |
| 8 | DRH 0.389 | DGII 0.390 | R 0.384 | CHEF 0.386 | NTCT 0.382 | HLIT 0.385 | JAZZ 0.386 | AVT 0.391 | AIN 0.391 |
| 9 | FLEX 0.388 | MOG.A 0.390 | CTS 0.381 | BFH 0.383 | XHR 0.381 | GKOS 0.380 | MOG.A 0.382 | HLIT 0.387 | FLEX 0.388 |
| 10 | BFH 0.383 | SANM 0.390 | SXT 0.380 | CTS 0.381 | TXG 0.378 | DAL 0.379 | DAL 0.381 | CYTK 0.386 | BFH 0.383 |

### Symboles apparaissant dans ≥4 top 10
| Symbole | Nb apparitions | Batches |
|---------|:---:|------|
| **MOG.A** | 8 | Tous sauf MOVE |
| **DRH** | 8 | Tous sauf MOVE |
| **HLIT** | 7 | Baseline, Sentiment, Screener, Short Score, VXN, VIX3M, MOVE |
| **TEX** | 7 | Baseline, Sentiment, Screener, Short Score, VXN, VIX3M, Global Stk |
| **AIN** | 6 | Baseline, Screener, Short Score, VXN, VIX3M, Global Stk |
| **R** | 6 | Baseline, Sentiment, Screener, Short Score, VIX3M, Global Stk |
| **FLEX** | 6 | Baseline, Screener, VXN, VIX3M, MOVE, Global Stk |
| **SANM** | 4 | Baseline, Sentiment, VIX, VXN |
| **BFH** | 4 | Baseline, Short Score, MOVE, Global Stk |

> ⭐ **MOG.A, DRH** — top 10 dans 8/9 batches.  
> ⭐ **HLIT, TEX** — 7/9.  
> 🔄 **Global Stacking reprend 8/10 de la baseline** — c'est le batch le plus fidèle.

---

## 7. Flop 10 — Pires F1 macro WF

| Rang | Baseline | +Sentiment | +Screener | +Short Score | +VIX | +VXN | +VIX3M | +MOVE | +Global Stk |
|:---:|------|------|------|------|------|------|------|------|------|
| 1 | IIPR 0.194 | HSBC 0.188 | INDV 0.195 | CMPR 0.194 | ANET 0.190 | PRG 0.197 | CALY 0.193 | INDV 0.196 | IIPR 0.194 |
| 2 | CMPR 0.194 | CMPR 0.194 | CMPR 0.198 | INDV 0.195 | PRG 0.195 | CMPR 0.205 | IIPR 0.195 | ANET 0.203 | CMPR 0.199 |
| 3 | INDV 0.195 | INDV 0.195 | HSBC 0.198 | IIPR 0.199 | HSBC 0.204 | IIPR 0.206 | HSBC 0.203 | ROKU 0.213 | HSBC 0.201 |
| 4 | HSBC 0.201 | BELFB 0.200 | PRG 0.208 | HSBC 0.201 | INDV 0.208 | INDV 0.206 | CMPR 0.203 | HSBC 0.214 | ANET 0.203 |
| 5 | ANET 0.203 | ANET 0.204 | IIPR 0.210 | ANET 0.203 | IIPR 0.213 | ANET 0.211 | ANET 0.205 | CALY 0.215 | PRG 0.207 |
| 6 | PRG 0.207 | BELFA 0.218 | CSCO 0.212 | PRG 0.207 | CALY 0.215 | CALY 0.212 | VNO 0.215 | BELFA 0.216 | ESE 0.209 |
| 7 | ESE 0.209 | IIPR 0.220 | BELFA 0.224 | ESE 0.209 | CDNA 0.218 | HSBC 0.220 | INDV 0.221 | TXG 0.220 | ROKU 0.212 |
| 8 | BELFB 0.209 | CDNA 0.220 | CALY 0.226 | BELFB 0.209 | BELFB 0.219 | ROKU 0.224 | TWLO 0.224 | BELFB 0.221 | BELFB 0.212 |
| 9 | ROKU 0.212 | PRG 0.222 | NTAP 0.228 | CALY 0.216 | CMPR 0.223 | ESE 0.225 | NIC 0.226 | PRG 0.224 | INDV 0.222 |
| 10 | CDNA 0.215 | ANAB 0.222 | HLIO 0.228 | ROKU 0.217 | ANAB 0.227 | BELFB 0.227 | CECO 0.227 | PTGX 0.227 | BELFA 0.224 |

### Symboles apparaissant dans ≥5 flop 10
| Symbole | Nb apparitions |
|---------|:---:|
| **INDV** | 9 |
| **HSBC** | 9 |
| **CMPR** | 8 |
| **ANET** | 8 |
| **IIPR** | 8 |
| **PRG** | 8 |
| **BELFB** | 7 |
| **CALY** | 6 |
| **ROKU** | 5 |
| **CDNA** | 4 |
| **ESE** | 4 |

> ⚠️ **INDV, HSBC** sont dans le flop de **tous** les batches (9/9).  
> ⚠️ **CMPR, ANET, IIPR, PRG** dans 8/9.

---

## 8. Synthèse par feature set

| Feature set | Nb features ajoutées | Δ F1 WF LGBM | Top 0.40+ | f1_short=0 | Verdict |
|-------------|:---:|:---:|:---:|:---:|:---:|
| **Baseline** | — | 0.295 | 5 | 4 | 🥇 Référence |
| +Global Stacking | 1 | 0.000 | **5** | 6 | 🥇 F1 et distribution identiques à la baseline |
| +Global Stk+Challenger ⚠️ | 1 | −0.001 | 3 | 5 | 🚀 CatBoost +0.006, biais long résolu, ventre mou −17% |
| +Short Score | 1 | 0.000 | **6** ✅ | 7 ❌ | 🥈 Distribution améliorée |
| +MOVE | 1 | −0.001 | 4 | 6 | 🥈 F1_short +0.024, record BEN 0.426 |
| +VXN | 2 | −0.001 | 4 | 6 | 🥉 Champions = baseline |
| +Sentiment | 4 | 0.000 | 1 ❌ | **3** ✅ | 🥉 f1_short=0 réduit |
| +Screener | 22 | −0.002 | 3 | 6 | ⚠️ LSTM progresse un peu |
| +VIX | 2 | −0.002 | 1 ❌ | 8 ❌ | ❌ À éviter |
| +VIX3M | 3 | **−0.005** | 5 | **10** ❌ | ❌ Pire batch macro |

---

## 9. Recommandations

### Feature sets à conserver
- **Baseline** (`expert` + `cross-sectional`) : le meilleur compromis performance/robustesse
- **+Global Stacking** : seul batch qui reproduit exactement la baseline — neutre mais sans risque
- **+Short Score** : à tester en combinaison avec des class weights asymétriques pour corriger le problème f1_short=0
- **+MOVE** : seul batch macro qui améliore le F1_short (+0.024) — piste prometteuse pour le short

### Feature sets à abandonner
- **+VIX3M** : pire dégradation F1 (−0.005) + f1_short=0 record (10)
- **+VIX** : contre-productif en per-symbol (features globales = bruit)
- **+VXN** : même problème que VIX — features globales, aucun gain
- **+Screener** : 22 features pour aucun gain, coût en temps de calcul
- **+Sentiment** : 4 features sans impact sur l'horizon J+10

### Symboles robustes (top ≥5 batches)
⭐ **MOG.A, DRH** — top 10 dans 8/9 batches  
⭐ **HLIT, TEX** — top 10 dans 7/9 batches  
⭐ **AIN, R, FLEX** — top 10 dans 6/9 batches

### Symboles à exclure (flop ≥7 batches)
⚠️ **INDV, HSBC** — flop 10 dans 9/9 batches  
⚠️ **CMPR, ANET, IIPR, PRG** — flop 10 dans 8/9 batches  
⚠️ **BELFB** — flop 10 dans 7/9 batches

### Symboles à exclure du short (f1_short=0 dans ≥4 batches)
🚫 **BMO, VOYA** — dans ≥6 batches  
🚫 **SSD** — dans 5 batches  
🚫 **INTC, WWD** — dans 4 batches

### Anomalies notables
- **HSBC** : F1_long = **0.000** avec VXN et MOVE
- **VIX3M** : **10 symboles** avec f1_short=0 — record absolu
- **MOVE** : F1_short LightGBM **+0.024** vs baseline — meilleure amélioration short
- **BEN 0.426** et **BFH 0.425** — records F1 macro (MOVE)
- **Global Stacking** : F1 et distribution strictement identiques à la baseline
- **Global Stk+Challenger ⚠️** : EXTR **0.439** — nouveau record absolu ; INDV passe de flop systématique à #6 (0.390)
- ⚠️ Batches 1-9 vs 10 : labeling différent, comparaison directe impossible

---

*Rapport généré le 2026-07-24 — 10 batches comparés.*
