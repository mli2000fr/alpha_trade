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

---

## 2. Métriques clés — F1 Macro Walk-Forward

| Batch | LightGBM | CatBoost | LSTM |
|-------|:---:|:---:|:---:|
| **Baseline** | **0.295** | 0.287 | 0.228 |
| +Sentiment | 0.295 | **0.289** | 0.224 |
| +Screener | 0.293 | 0.284 | **0.231** |
| +Short Score | **0.295** | 0.286 | 0.229 |
| +VIX | 0.293 | 0.284 | 0.229 |

> 🥇 **Baseline & Short Score** : meilleur LightGBM WF (0.295).  
> 🥈 **Sentiment** : meilleur CatBoost WF (0.289).  
> ❌ **Screener & VIX** : dégradent les deux tree models.

---

## 3. Distribution F1 Macro WF

| Batch | 0.10-0.19 | 0.20-0.29 | 0.30-0.39 | 0.40+ |
|-------|:---:|:---:|:---:|:---:|
| **Baseline** | 3 | 95 | 97 | **5** |
| +Sentiment | 4 | 80 | **113** | 1 |
| +Screener | 3 | 88 | 106 | 3 |
| +Short Score | 3 | **87** | 104 | **6** |
| +VIX | **2** | 91 | 104 | 1 |

> 🥇 **Short Score** : seul batch qui améliore le top 0.40+ (5→6) ET réduit le bas (95→87).  
> 🥈 **Baseline** : top 0.40+ solide (5), mais ventre mou important (95).  
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

> 📊 LightGBM domine systématiquement (54-58%).  
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

> 🥇 **Sentiment** : meilleur score (3).  
> ❌ **VIX** : pire score (8).  
> ⚠️ **BMO, IEX, VOYA** sont incapables de shorter dans ≥3 batches → à exclure du short.

---

## 6. Top 10 — Meilleurs F1 macro WF

| Rang | Baseline | +Sentiment | +Screener | +Short Score | +VIX |
|:---:|------|------|------|------|------|
| 1 | HLIT 0.416 | TEX 0.405 | TEX 0.422 | MOG.A 0.421 | ESTA 0.408 |
| 2 | TEX 0.409 | DAL 0.398 | HLIT 0.416 | HLIT 0.416 | SANM 0.397 |
| 3 | NTRS 0.404 | R 0.397 | DRH 0.412 | TEX 0.409 | MOG.A 0.394 |
| 4 | SANM 0.403 | ESTA 0.395 | CHEF 0.400 | NTRS 0.405 | DRH 0.390 |
| 5 | R 0.401 | DRH 0.394 | AIN 0.397 | DRH 0.403 | GTX 0.384 |
| 6 | MOG.A 0.391 | CTS 0.393 | MOG.A 0.392 | R 0.401 | SEI 0.384 |
| 7 | AIN 0.391 | HLIT 0.391 | FLEX 0.390 | AIN 0.391 | WSC 0.382 |
| 8 | DRH 0.389 | DGII 0.390 | R 0.384 | CHEF 0.386 | NTCT 0.382 |
| 9 | FLEX 0.388 | MOG.A 0.390 | CTS 0.381 | BFH 0.383 | XHR 0.381 |
| 10 | BFH 0.383 | SANM 0.390 | SXT 0.380 | CTS 0.381 | TXG 0.378 |

### Symboles apparaissant dans ≥3 top 10
| Symbole | Nb apparitions | Batches |
|---------|:---:|------|
| **MOG.A** | 5 | Tous |
| **DRH** | 5 | Tous |
| **HLIT** | 4 | Baseline, Sentiment, Screener, Short Score |
| **TEX** | 4 | Baseline, Sentiment, Screener, Short Score |
| **R** | 4 | Baseline, Sentiment, Screener, Short Score |
| **AIN** | 3 | Baseline, Screener, Short Score |
| **SANM** | 3 | Baseline, Sentiment, VIX |
| **CTS** | 3 | Sentiment, Screener, Short Score |

> ⭐ **MOG.A, DRH, HLIT, TEX, R** sont les 5 titres les plus robustes — ils performent quel que soit le feature set.

---

## 7. Flop 10 — Pires F1 macro WF

| Rang | Baseline | +Sentiment | +Screener | +Short Score | +VIX |
|:---:|------|------|------|------|------|
| 1 | IIPR 0.194 | HSBC 0.188 | INDV 0.195 | CMPR 0.194 | ANET 0.190 |
| 2 | CMPR 0.194 | CMPR 0.194 | CMPR 0.198 | INDV 0.195 | PRG 0.195 |
| 3 | INDV 0.195 | INDV 0.195 | HSBC 0.198 | IIPR 0.199 | HSBC 0.204 |
| 4 | HSBC 0.201 | BELFB 0.200 | PRG 0.208 | HSBC 0.201 | INDV 0.208 |
| 5 | ANET 0.203 | ANET 0.204 | IIPR 0.210 | ANET 0.203 | IIPR 0.213 |
| 6 | PRG 0.207 | BELFA 0.218 | CSCO 0.212 | PRG 0.207 | CALY 0.215 |
| 7 | ESE 0.209 | IIPR 0.220 | BELFA 0.224 | ESE 0.209 | CDNA 0.218 |
| 8 | BELFB 0.209 | CDNA 0.220 | CALY 0.226 | BELFB 0.209 | BELFB 0.219 |
| 9 | ROKU 0.212 | PRG 0.222 | NTAP 0.228 | CALY 0.216 | CMPR 0.223 |
| 10 | CDNA 0.215 | ANAB 0.222 | HLIO 0.228 | ROKU 0.217 | ANAB 0.227 |

### Symboles apparaissant dans ≥3 flop 10
| Symbole | Nb apparitions |
|---------|:---:|
| **INDV** | 5 |
| **HSBC** | 5 |
| **IIPR** | 5 |
| **CMPR** | 5 |
| **PRG** | 5 |
| **BELFB** | 4 |
| **ANET** | 3 |
| **CALY** | 3 |
| **CDNA** | 3 |

> ⚠️ **INDV, HSBC, IIPR, CMPR, PRG** sont systématiquement dans le flop — à exclure du trading.

---

## 8. Synthèse par feature set

| Feature set | Nb features ajoutées | Δ F1 WF LGBM | Top 0.40+ | f1_short=0 | Verdict |
|-------------|:---:|:---:|:---:|:---:|:---:|
| **Baseline** | — | 0.295 | 5 | 4 | 🥇 Référence |
| +Short Score | 1 | 0.000 | **6** ✅ | 7 ❌ | 🥈 Distribution améliorée |
| +Sentiment | 4 | 0.000 | 1 ❌ | **3** ✅ | 🥉 f1_short=0 réduit |
| +Screener | 22 | −0.002 | 3 | 6 | ⚠️ LSTM progresse un peu |
| +VIX | 2 | −0.002 | 1 ❌ | 8 ❌ | ❌ À éviter |

---

## 9. Recommandations

### Feature sets à conserver
- **Baseline** (`expert` + `cross-sectional`) : le meilleur compromis performance/robustesse
- **+Short Score** : à tester en combinaison avec des class weights asymétriques pour corriger le problème f1_short=0

### Feature sets à abandonner
- **+VIX** : contre-productif en per-symbol (features globales = bruit)
- **+Screener** : 22 features pour aucun gain, coût en temps de calcul
- **+Sentiment** : 4 features sans impact sur l'horizon J+10

### Symboles robustes (top ≥3 batches)
⭐ **MOG.A, DRH, HLIT, TEX, R** — à trader en priorité

### Symboles à exclure (flop ≥3 batches)
⚠️ **INDV, HSBC, IIPR, CMPR, PRG** — F1 systematically < 0.22

### Symboles à exclure du short (f1_short=0 dans ≥2 batches)
🚫 **BMO, IEX, VOYA, INTC, WWD**

---

*Rapport généré le 2026-07-23 — 5 batches comparés.*
