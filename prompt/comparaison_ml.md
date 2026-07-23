# 📊 Comparaison des Batches ML — Module `modelFactory`

> **Référence** : Baseline = `model-factory-20260722091334-cddc05`  
> **Date** : 2026-07-22 / 2026-07-23  
> **200 symboles** (sauf VIX/Sentiment : 198), mode ternaire 3-classes, horizon J+10

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

> 🥇 **Baseline & Short Score** : meilleur LightGBM WF (0.295).  
> 🥈 **Sentiment** : meilleur CatBoost WF (0.289).  
> 🥉 **VXN** : quasi stable (−0.001), seul batch avec champions identiques à la baseline.  
> ❌ **Screener & VIX** : dégradent les deux tree models.

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

> 🥇 **Short Score** : seul batch qui améliore le top 0.40+ (5→6) ET réduit le bas (95→87).  
> 🥈 **Baseline** : top 0.40+ solide (5), mais ventre mou important (95).  
> 🥉 **VXN** : bon profil (top 4, bas quasi éliminé avec 1 seul dans 0.10-0.19).  
> ❌ **Sentiment & VIX** : écrasent le top 0.40+ (5→1).

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

> 📊 LightGBM domine systématiquement (54-58%).  
> 🥇 **VXN** : seul batch avec une distribution de champions **identique** à la baseline (116/68/16).  
> 📈 CatBoost progresse avec le sentiment (+8).  
> 📈 LSTM progresse avec le screener (+8).

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

> 🥇 **Sentiment** : meilleur score (3).  
> ❌ **VIX** : pire score (8).  
> ⚠️ **BMO, VOYA** sont incapables de shorter dans ≥4 batches → à exclure du short.  
> ⚠️ **INTC, SSD, WWD** apparaissent dans ≥3 batches avec f1_short=0.

---

## 6. Top 10 — Meilleurs F1 macro WF

| Rang | Baseline | +Sentiment | +Screener | +Short Score | +VIX | +VXN |
|:---:|------|------|------|------|------|------|
| 1 | HLIT 0.416 | TEX 0.405 | TEX 0.422 | MOG.A 0.421 | ESTA 0.408 | AIN 0.416 |
| 2 | TEX 0.409 | DAL 0.398 | HLIT 0.416 | HLIT 0.416 | SANM 0.397 | FLEX 0.411 |
| 3 | NTRS 0.404 | R 0.397 | DRH 0.412 | TEX 0.409 | MOG.A 0.394 | TEX 0.407 |
| 4 | SANM 0.403 | ESTA 0.395 | CHEF 0.400 | NTRS 0.405 | DRH 0.390 | ATRO 0.401 |
| 5 | R 0.401 | DRH 0.394 | AIN 0.397 | DRH 0.403 | GTX 0.384 | CHEF 0.393 |
| 6 | MOG.A 0.391 | CTS 0.393 | MOG.A 0.392 | R 0.401 | SEI 0.384 | SANM 0.393 |
| 7 | AIN 0.391 | HLIT 0.391 | FLEX 0.390 | AIN 0.391 | WSC 0.382 | MOG.A 0.390 |
| 8 | DRH 0.389 | DGII 0.390 | R 0.384 | CHEF 0.386 | NTCT 0.382 | HLIT 0.385 |
| 9 | FLEX 0.388 | MOG.A 0.390 | CTS 0.381 | BFH 0.383 | XHR 0.381 | GKOS 0.380 |
| 10 | BFH 0.383 | SANM 0.390 | SXT 0.380 | CTS 0.381 | TXG 0.378 | DAL 0.379 |

### Symboles apparaissant dans ≥3 top 10
| Symbole | Nb apparitions | Batches |
|---------|:---:|------|
| **MOG.A** | 6 | Tous |
| **DRH** | 6 | Tous |
| **TEX** | 5 | Baseline, Sentiment, Screener, Short Score, VXN |
| **HLIT** | 5 | Baseline, Sentiment, Screener, Short Score, VXN |
| **SANM** | 4 | Baseline, Sentiment, VIX, VXN |
| **AIN** | 4 | Baseline, Screener, Short Score, VXN |
| **R** | 4 | Baseline, Sentiment, Screener, Short Score |
| **FLEX** | 3 | Baseline, Screener, VXN |
| **CHEF** | 3 | Screener, Short Score, VXN |
| **CTS** | 3 | Sentiment, Screener, Short Score |

> ⭐ **MOG.A, DRH** sont dans le top 10 de **tous** les batches (6/6).  
> ⭐ **TEX, HLIT** dans 5/6 — très robustes.  
> 🆕 **FLEX, CHEF** entrent dans le club des ≥3 apparitions grâce à VXN.

---

## 7. Flop 10 — Pires F1 macro WF

| Rang | Baseline | +Sentiment | +Screener | +Short Score | +VIX | +VXN |
|:---:|------|------|------|------|------|------|
| 1 | IIPR 0.194 | HSBC 0.188 | INDV 0.195 | CMPR 0.194 | ANET 0.190 | PRG 0.197 |
| 2 | CMPR 0.194 | CMPR 0.194 | CMPR 0.198 | INDV 0.195 | PRG 0.195 | CMPR 0.205 |
| 3 | INDV 0.195 | INDV 0.195 | HSBC 0.198 | IIPR 0.199 | HSBC 0.204 | IIPR 0.206 |
| 4 | HSBC 0.201 | BELFB 0.200 | PRG 0.208 | HSBC 0.201 | INDV 0.208 | INDV 0.206 |
| 5 | ANET 0.203 | ANET 0.204 | IIPR 0.210 | ANET 0.203 | IIPR 0.213 | ANET 0.211 |
| 6 | PRG 0.207 | BELFA 0.218 | CSCO 0.212 | PRG 0.207 | CALY 0.215 | CALY 0.212 |
| 7 | ESE 0.209 | IIPR 0.220 | BELFA 0.224 | ESE 0.209 | CDNA 0.218 | HSBC 0.220 |
| 8 | BELFB 0.209 | CDNA 0.220 | CALY 0.226 | BELFB 0.209 | BELFB 0.219 | ROKU 0.224 |
| 9 | ROKU 0.212 | PRG 0.222 | NTAP 0.228 | CALY 0.216 | CMPR 0.223 | ESE 0.225 |
| 10 | CDNA 0.215 | ANAB 0.222 | HLIO 0.228 | ROKU 0.217 | ANAB 0.227 | BELFB 0.227 |

### Symboles apparaissant dans ≥4 flop 10
| Symbole | Nb apparitions |
|---------|:---:|
| **INDV** | 6 |
| **HSBC** | 6 |
| **IIPR** | 6 |
| **CMPR** | 6 |
| **PRG** | 6 |
| **BELFB** | 5 |
| **ANET** | 4 |
| **CALY** | 4 |
| **CDNA** | 4 |
| **ROKU** | 3 |
| **ESE** | 3 |

> ⚠️ **INDV, HSBC, IIPR, CMPR, PRG** sont dans le flop de **tous** les batches (6/6) — à exclure du trading.  
> ⚠️ **BELFB** dans 5/6 — très instable.

---

## 8. Synthèse par feature set

| Feature set | Nb features ajoutées | Δ F1 WF LGBM | Top 0.40+ | f1_short=0 | Verdict |
|-------------|:---:|:---:|:---:|:---:|:---:|
| **Baseline** | — | 0.295 | 5 | 4 | 🥇 Référence |
| +Short Score | 1 | 0.000 | **6** ✅ | 7 ❌ | 🥈 Distribution améliorée |
| +VXN | 2 | −0.001 | 4 | 6 | 🥉 Champions = baseline, top stable |
| +Sentiment | 4 | 0.000 | 1 ❌ | **3** ✅ | 🥉 f1_short=0 réduit |
| +Screener | 22 | −0.002 | 3 | 6 | ⚠️ LSTM progresse un peu |
| +VIX | 2 | −0.002 | 1 ❌ | **8** ❌ | ❌ À éviter |

---

## 9. Recommandations

### Feature sets à conserver
- **Baseline** (`expert` + `cross-sectional`) : le meilleur compromis performance/robustesse
- **+Short Score** : à tester en combinaison avec des class weights asymétriques pour corriger le problème f1_short=0

### Feature sets à abandonner
- **+VIX** : contre-productif en per-symbol (features globales = bruit)
- **+VXN** : même problème que VIX — features globales, aucun gain
- **+Screener** : 22 features pour aucun gain, coût en temps de calcul
- **+Sentiment** : 4 features sans impact sur l'horizon J+10

### Symboles robustes (top ≥4 batches)
⭐ **MOG.A, DRH** — top 10 dans 6/6 batches  
⭐ **TEX, HLIT** — top 10 dans 5/6 batches  
⭐ **SANM, AIN, R** — top 10 dans 4/6 batches

### Symboles à exclure (flop ≥4 batches)
⚠️ **INDV, HSBC, IIPR, CMPR, PRG** — flop 10 dans 6/6 batches  
⚠️ **BELFB** — flop 10 dans 5/6 batches

### Symboles à exclure du short (f1_short=0 dans ≥3 batches)
🚫 **BMO, VOYA** — dans ≥4 batches  
🚫 **INTC, SSD, WWD** — dans ≥3 batches

### Anomalies notables
- **HSBC** : F1_long = **0.000** avec VXN (le modèle ne prédit que flat pour ce titre)
- **IEX** : présent uniquement dans les 4 premiers batches (corrigé dans VIX et VXN)

---

*Rapport généré le 2026-07-23 — 6 batches comparés.*
