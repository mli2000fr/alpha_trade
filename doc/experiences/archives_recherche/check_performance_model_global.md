# Check Performance — Modèle Global (LONG Alpha Attribution)

**Date** : 2026-08-21
**Univers** : `config/ticket_recherche.txt` (400 tickers, identique à `ticket_mid_cap_400.txt`)
**Modèle** : Global Ranking B25 (`model-factory-20260811223551-ef2cd0`, colonne `global_rank_20`)
**Question** : le LONG B25 a-t-il un **vrai pouvoir de sélection**, indépendamment de la hausse générale du marché ?
**Script** : `scripts/e30_long_alpha_attribution.py` — **aucun tuning**, aucun modèle modifié.

---

## 1. Verdict (règle pré-engagée)

> **GO FAIBLE**

- **Ce n'est PAS un NO-GO alpha** : le TOP10 bat significativement le Random (t=8.7), le placebo permutation (z=+23.9) et le random sector-matché (t=8.8) sur 2018-2025 → le portefeuille LONG ne gagne **pas que du bêta**.
- **Ce n'est PAS un GO fort** : la propriété **n'est pas stable OOS** — 2026 (vrai OOS) est **négatif** (TOP < Random, TOP−BOTTOM < 0, IC < 0), 2020 ≈ nul, CORRECTION ≈ nul.
- **Lecture** : l'alpha de sélection a été réel et robuste sur l'historique, mais son pouvoir de classement **s'est inversé hors-échantillon récent** (2026). Cohérent avec l'architecture C2+B4 : le modèle reprend quand son ranking revient — mais en 2026 il ne revient pas encore.

---

## 2. Méthodologie

| Élément | Définition |
|---|---|
| Univers | 400 tickers (`config/ticket_recherche.txt`) |
| Rank | `global_rank_history.global_rank_20` (batch B25), PIT |
| **TOP B25** | 10 titres au **rank le plus ÉLEVÉ** (proba_long = global_rank, corr 1.0) |
| **BOTTOM B25** | 10 titres au rank le plus FAIBLE |
| **RANDOM** | 1 000 tirages de 10 titres dans l'univers éligible **du même jour** (avec remise) |
| Retour forward | `close(D+H)/open(D+1) − 1`, H ∈ {5, 10, 15, 20} (entrée next-open) |
| Régime SPY | PIT, 4 états (BULL/CORRECTION/SLIDE/REBOUND), `backtesting.regime_trailing.compute_regime` |
| Secteur | GICS via `stock_metadata` (`modelFactory.cross_sectional._load_sector_mapping`) |
| Période | 2018-10-01 → 2026-05-29 (**2026 = vrai OOS**, entraînement → 2025-12-31) |
| Échantillon | 566 268 lignes, 400 symboles, **1 527 jours** (n ≥ 20 éligibles/jour) |

Le test est **pur** : il compare des rendements forward equal-weight, sans C2, sans B4, sans sizing, sans coûts. Il répond UNIQUEMENT à « le rank classe-t-il correctement les gagnants relatifs ? ».

---

## 3. Test A — Rank pur (TOP vs RANDOM vs UNIVERS vs BOTTOM)

**Ce que ça teste** : à chaque date, les 10 meilleurs rangs font-ils mieux qu'un tirage aléatoire du même jour, que la moyenne de l'univers, et que les 10 pires rangs ?

**Résultat (TOP10, equal-weight)** :

| H | nD | TOP | UNIV | BOT | RAND | TOP−RD | t | TOP−UN | TOP−BOT | hit>RD | hit>UN | pctile | IC | IC_t |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 1527 | 0.79% | 0.15% | −0.06% | 0.14% | +0.64pp | 5.2 | +0.64 | +0.85 | 52.7% | 52.6% | 55.9% | 0.013 | 3.2 |
| 10 | 1527 | 1.46% | 0.31% | −0.10% | 0.31% | +1.15 | 6.0 | +1.15 | +1.57 | 54.3% | 54.4% | 60.0% | 0.021 | 5.6 |
| 15 | 1527 | 2.15% | 0.48% | −0.16% | 0.48% | +1.67 | 6.4 | +1.67 | +2.31 | 55.1% | 54.6% | 61.8% | 0.026 | 7.5 |
| 20 | 1526 | 2.54% | 0.70% | −0.12% | 0.70% | **+1.84** | **8.7** | +1.84 | **+2.65** | 57.3% | 57.5% | **63.5%** | **0.029** | **8.8** |

**Lecture** :
- Le **TOP bat nettement le Random** (+1.84pp à H20, t=8.7) et l'univers (+1.84pp).
- Le **spread TOP−BOTTOM est positif et monotone croissant avec l'horizon** (+0.85 → +2.65pp) → le rank **classe réellement** les gagnants relatifs (ce n'est pas du bruit).
- **Rank IC** positif et croissant (0.013 → 0.029), t-stat 3.2 → 8.8 (très significatif).
- **Percentile médian de TOP dans les randoms du jour = 63.5%** : un jour typique, le TOP bat ~63.5% des 1 000 portefeuilles aléatoires du même jour (50% = aucun edge).

**Pourquoi 63.5% vs hit 57.3% ?** le percentile compare le TOP aux **1 000 tirages individuels** (distribution large), le hit compare à leur **moyenne** (plus stable). Les deux convergent : le TOP est au-dessus du hasard le même jour, dans le même univers.

---

## 4. Test B — Placebo permutation (IC H20)

**Ce que ça teste** : l'IC de 0.029 pourrait-il être obtenu **par chance** avec un rank aléatoire ?

**Méthode** :
1. IC réel = corrélation de Spearman (rank B25, rendement H20) **par jour**, moyenne = **+0.0295**.
2. H0 = « le rank ne contient aucune information » → on **mélange (permute) les ranks entre symboles** à chaque date.
3. 200 permutations × 1 526 jours ; pour chaque permutation on calcule la **moyenne d'IC sur les dates** → distribution nulle de la moyenne.
4. On compare l'IC réel à cette distribution.

**Résultat** :

```
IC réel (moy. dates)      = +0.0295
Distribution nulle (moy.) :
  médiane                  +0.0001
  p95                      +0.0020
  p99                      +0.0032
p-value                    = 0.0000
z                          = +23.9
```

**Lecture** : même le 99ᵉ percentile du hasard n'atteint que +0.003, alors que l'IC réel vaut +0.0295 (~9× au-dessus). Sur 200 permutations, **aucune** n'a produit une moyenne ≥ 0.0295 → **p-value ≈ 0, z = +23.9** (24σ au-dessus du hasard). **Le pouvoir de classement de B25 est réel, pas un artefact de tirage.**

> ⚠️ Correction de méthode : la 1ʳᵉ version du test poolait les IC par date (agrégation fausse). Le test valide teste la **distribution de la MOYENNE d'IC** sous H0. C'est cette version qui est documentée ici.

---

## 5. Test C — Sector-matched random

**Ce que ça teste** : le TOP surperforme-t-il parce qu'il choisit les bons secteurs (biais sectoriel) ou les bonnes actions **dans** les secteurs ?

**Méthode** : à chaque date, on reproduit la **composition sectorielle exacte du TOP10** (ex : 4 Tech + 3 Industriels + 2 Santé + 1 Finance) et on tire 1 000 portefeuilles random avec **cette même composition** (au hasard dans chaque secteur). Le random a donc les mêmes poids sectoriels que B25 → la seule différence restante vient du choix intra-sectoriel.

**Résultat (H20)** :

| | Rendement |
|---|---|
| TOP10 B25 | **2.54%** |
| Random sector-matched | **1.02%** |
| **TOP − secteur-random** | **+1.52pp (t = 8.8)** |
| hit (TOP > secteur-random) | 57.4% |

**Lecture** : le TOP bat très significativement un random **aux mêmes secteurs** → l'alpha vient de la **sélection intra-sectorielle**, pas d'un tilt sectoriel. La comparaison avec Test A (sans contrainte +1.84pp) montre qu'une petite partie de l'edge était sectorielle (1.84 → 1.52), mais **le gros de l'avantage survit** au matching sectoriel.

---

## 6. Test D — Stabilité (par année et par régime)

**Ce que ça teste** : l'alpha est-il uniforme dans le temps, ou concentré dans quelques périodes ? Empêche de conclure sur un agrégat trompeur.

### 6.1 Par année (H20, TOP−RAND en pp)

| Année | nD | TOP | RAND | TOP−RD | TOP−BOT | IC |
|---|---|---|---|---|---|---|
| 2018 | 63 | 0.85% | −1.92% | **+2.77** | +5.35 | 0.136 |
| 2019 | 122 | 4.28% | 1.75% | **+2.52** | +2.28 | 0.019 |
| 2020 | 123 | −0.58% | −0.52% | **−0.06** | +1.26 | 0.044 |
| 2021 | 122 | 3.87% | 2.84% | +1.03 | +1.78 | 0.007 |
| 2022 | 248 | 3.57% | −0.32% | **+3.89** | +5.26 | 0.040 |
| 2023 | 248 | 2.56% | 0.98% | +1.57 | +2.75 | 0.049 |
| 2024 | 252 | 3.23% | 1.32% | +1.90 | +2.10 | −0.001 |
| 2025 | 250 | 2.34% | 0.56% | +1.77 | +2.63 | 0.041 |
| **2026** | 98 | −0.24% | 0.52% | **−0.76** | **−1.15** | **−0.042** |

**Lecture** :
- Alpha positif **7/9 années** (2018, 2019, 2021, 2022, 2023, 2024, 2025).
- **2020 ≈ zéro** (le rank ne discrimine pas pendant le crash COVID).
- **2026 (vrai OOS) NÉGATIF** : TOP < Random (−0.76pp), TOP−BOTTOM < 0 (−1.15pp), IC < 0 (−0.042). **La seule vraie fenêtre OOS est inversée** → confirme l'avertissement perso « l'IC positif s'est inversé sur certaines fenêtres 2026 ».

### 6.2 Par régime (H20)

| Régime | nD | TOP | RAND | TOP−RD | TOP−BOT | IC |
|---|---|---|---|---|---|---|
| BULL | 907 | 1.94% | 0.12% | +1.82 | +2.29 | 0.014 |
| CORRECTION | 188 | −0.94% | −1.14% | **+0.20** | +0.57 | 0.008 |
| SLIDE | 311 | 4.25% | 2.75% | +1.50 | +3.34 | 0.072 |
| **REBOUND** | 120 | 8.03% | 2.61% | **+5.42** | **+6.85** | 0.072 |

**Lecture** :
- Alpha **fort en REBOUND** (+5.42pp, TOP−BOT +6.85) et **bon en BULL** (+1.82pp).
- **Correct en SLIDE** (+1.50pp).
- **Quasi nul en CORRECTION** (+0.20pp).

**Pourquoi c'est décisif** : l'alpha est **réel mais conditionnel** — fort en REBOUND/BULL/SLIDE, nul en CORRECTION, et **inversé en 2026 OOS**. C'est ce qui fait passer le verdict de « GO fort » (exigence : stable OOS) à **GO faible**.

---

## 7. Test E — Portefeuille B25+C2+B4 vs 1 000 portefeuilles random (**EXÉCUTÉ — GO fort portefeuille**)

**Question** (spec user 2026-08-21) : est-ce que **C2+B4+sizing transforme un rank récemment faible en portefeuille encore supérieur au hasard**, ou la bonne performance vient-elle surtout du risk management ?

**Méthode** (`scripts/e31_testE_portfolio.py`) — tout est IDENTIQUE entre B25 et random **sauf les noms** :
- Sélection B25 = **TOP8 par `global_rank_20`** (procuration du rang réel, LONG-only) ; random = **8 tirages sans remise** dans l'univers éligible du jour (univers 400).
- Mêmes dates d'entrée (décision D → entrée open D+1), ~8 entrées/jour, **~68 positions concurrentes** (equal-weight, gross ≤ 100%), **même C2** (trailing ATR 2,5× en BULL/REBOUND, 7 % en CORRECTION/SLIDE), **même B4** (breaker adaptatif, trip 15 %, recovery 92 %), **mêmes coûts** (3 bps aller-retour : 1 comm + 2 slippage), exits intrabar `resolve_intrabar_exit` (conservateur), **time stop 20 j conditionnel**, TP = min(3×ATR, 7 %), initial stop 2,5×ATR, contrainte de secteur ≤ 50 % (max 4/8 par GICS).
- **Calibration** : B25 replay 2025→2026 = **+48.0 % / Sharpe 1.08 / MaxDD −21.3 %** vs run réel C2+B4 (`e23b4_main`) **+34.6 % / 1.33 / −16.7 %** → même ordre de grandeur (écart expliqué : LONG-only TOP8 vs vraie sélection 6L/2S + conviction + capital_preservation).
- **1 000 portefeuilles random** × 2 fenêtres (2018-2025, 2026 OOS), seed 12345.

### Fenêtre A — 2018-2025 (valeur historique de l'architecture)

B25 : **+203.3 %**, Sharpe 0.68, Sortino 0.89, MaxDD −31.7 %, PF 1.20, worst 6m −26.2 %, worst 12m −26.6 %.

| métrique | B25 | P50 random | P75 | P90 | P95 | pctl B25 | p-emp |
|---|---|---|---|---|---|---|---|
| Return | **+203.3 %** | +17.8 % | +27.9 % | +40.1 % | +48.0 % | **98.1 %** | 0.019 |
| Sharpe | **0.68** | 0.21 | 0.27 | 0.35 | 0.39 | **100 %** | 0.000 |
| Sortino | 0.89 | 0.26 | 0.34 | 0.43 | 0.49 | 98.1 % | 0.019 |
| MaxDD | −31.7 % | −25.6 % | −23.6 % | −21.8 % | −21.0 % | **6.8 % ⚠️** | — |
| PF | 1.20 | 1.04 | 1.06 | 1.08 | 1.09 | 100 % | 0.000 |
| worst 6m | −26.2 % | −19.8 % | −18.5 % | −17.7 % | −17.1 % | **2.3 % ⚠️** | — |
| worst 12m | −26.6 % | −21.9 % | −20.2 % | −18.6 % | −17.8 % | **7.0 % ⚠️** | — |

### Fenêtre B — 2026 OOS (aujourd'hui, malgré l'inversion du rank pur)

B25 : **+17.8 %**, Sharpe 1.34, Sortino 2.15, MaxDD −14.7 %, PF 1.41 (~100 jours, H1).

| métrique | B25 | P50 random | P75 | P90 | P95 | pctl B25 | p-emp |
|---|---|---|---|---|---|---|---|
| Return | **+17.8 %** | −0.6 % | +2.0 % | +4.2 % | +5.7 % | **100 %** | 0.0000 |
| Sharpe | **1.34** | −0.01 | 0.38 | 0.73 | 0.91 | **98.8 %** | 0.012 |
| Sortino | 2.15 | −0.02 | 0.63 | 1.20 | 1.55 | 98.5 % | 0.015 |
| MaxDD | −14.7 % | −10.6 % | −9.3 % | −8.2 % | −7.5 % | **2.8 % ⚠️** | — |
| PF | 1.41 | 0.99 | 1.06 | 1.12 | 1.16 | 100 % | 0.000 |

**Contributions** : 2025 = **+60.6 %** (B25) ; 2026 = **+17.8 %** (pctl 100 %, p=0.0000).

### Verdict (règle stricte user)

> **GO fort portefeuille** : B25 > P95 random sur Return (98.1 %) et Sharpe (100 %) historiquement, **ET** reste supérieur en 2026 (Return pctl 100 %, Sharpe 98.8 %).

### Lecture honnête (ne pas sur-vendre)

1. **Le C2+B4+sizing transforme bien le rank faible en valeur économique** : en 2026 OOS, malgré l'inversion du rank pur (E30 : IC −0.042, TOP−BOT −1.15 pp), le portefeuille B25 bat le hasard à ~100 % des randoms (+17.8 % vs médiane random −0.6 %). C'est exactement l'hypothèse de l'utilisateur.
2. **La mécanique seule ne suffit pas** : les 1 000 randoms passent la MÊME machine C2+B4+sizing+coûts et font −0.6 % médian en 2026 → l'avantage vient de l'**interaction selection×exits** (les noms top-rangés montent en absolu ; C2/trailing récolte les gains, coupe les pertes à −7 %).
3. **⚠️ Coût en risque réel** : les drawdowns de B25 sont **plus profonds que random** (MaxDD pctl 6.8 % en A / 2.8 % en B ; worst 6m/12m en bas de distribution). Le rang sélectionne des noms momentum plus volatils ; B4 réduit les entrées mais **ne force pas la liquidation** des positions existantes.
4. **⚠️ 2026 est court** (~100 jours, H1) — un seul semestre, pas une preuve de pérennité.
5. **Replay avec assomptions documentées** (TOP8 long proxy, C2+B4 calibrés, ATR moyenne simple 20 TR) — pas un bit-for-bit du backtest production.

### Confirmation avec la vraie structure de slots 6L/2S (**exécuté**)

Le GO fort n'est **pas un artefact du proxy TOP8 long** : le même test rejoué avec la structure réelle **6 longs + 2 shorts/jour** (`scripts/e31b_testE_6l2s.py` ; shorts = les 2 plus bas `global_rank_20`, mécanique short en miroir C2, identique pour B25 et random) confirme le verdict. Calibration 2025→2026 : B25 6L/2S = **+54.6 % / Sharpe 1.51 / MaxDD −11.1 %** (plausible vs réel 2025 +46 %/2026 +27 %).

**Fenêtre A (2018-2025)** : B25 = +89.1 % (Sharpe 0.52, PF 1.13, MaxDD −26.0 %) → **pctl Return 98.1 %** (p=0.019), **Sharpe 98.4 %** (p=0.016), PF 98.6 % ; ⚠️ MaxDD pctl 3.2 % (plus profond que 97 % des randoms).

**Fenêtre B (2026 OOS)** : B25 = +10.3 % (Sharpe 1.11, PF 1.23, MaxDD −11.1 %) → **pctl Return 99.5 %** (p=0.005), Sharpe 93.7 % ; ⚠️ MaxDD pctl 4.8 %.

**Contributions** : 2025 = +49.3 % · 2026 = +10.3 % (pctl 99.5 %). **VERDICT : GO fort portefeuille 6L/2S.**

**Lecture** : les 2 shorts réduisent le premium brut (LONG-only +203 % vs 6L/2S +89 % en historique ; +17.8 % vs +10.3 % en 2026) mais améliorent le MaxDD (−26 % vs −31.7 %) ; le risque de drawdown plus profond que random persiste (pctl 3-5 %) → sujet de l'audit force-close B4 (étape 2).

---

## 8. Lien avec la décision B4 / GO live

**Rappel** : B4 (breaker adaptatif) est **actif en production** (`config.yaml policy: b4`, GO live 2026-08-21). B4 réduit l'exposition en régimes difficiles (CORRECTION/SLIDE) et le cash dégagé est assumé.

**Alpha conditionnel observé** (Test D) :
- **Fort** en REBOUND (+5.42pp) et BULL (+1.82pp), correct en SLIDE (+1.50pp).
- **Quasi nul** en CORRECTION (+0.20pp).
- **Inversé** en 2026 OOS (−0.76pp, IC −0.042).

**Cohérence avec l'architecture C2+B4** :
- B4 réduit l'exposition **précisément là où l'alpha de sélection est le plus faible** (CORRECTION ≈ 0) → le breaker protège quand le modèle perd son pouvoir de classement.
- B4 libère du cash en phase difficile → **limite l'impact d'un ranking inversé** (2026).
- Au retour en régime normal (REBOUND), l'alpha est **le plus fort** (+5.42pp) → c'est là que le modèle « reprend son travail », exactement l'hypothèse C2+B4.

**Conséquence pour le GO live** :
- Le GO live B4 (déjà actif) **reste justifié — et Test E le renforce** : au niveau **portefeuille**, B25+C2+B4 bat le hasard à 98-100 % des randoms sur 2018-2025 ET en 2026 OOS (Return pctl 100 %), alors même que le rank pur s'est inversé en 2026. **L'architecture complète apporte une vraie valeur économique aujourd'hui**.
- **Nuance importante** : cette valeur économique vient de l'**interaction selection×exits** (C2 récolte les gains des noms top-rangés, coupe à −7 %), pas du ranking seul — et elle s'accompagne de **drawdowns plus profonds que random** (MaxDD pctl 2.8-6.8 %). B4 réduit l'exposition mais ne liquide pas les positions ouvertes.
- Le passage en **capital plein** reste soumis aux conditions du plan : parité stricte backtest↔prod + période représentative (`check_paper_coverage` exit 0) — en cours (todo).

---

## 8bis. E32 — Audit drawdown / force-close B4 (**exécuté, audit causal — aucune règle modifiée**)

**Question** (spec user) : au moment où B4 trippe, **liquider les positions ouvertes protège-t-il réellement**, ou coupe-t-on des positions qui auraient récupéré ? Audit causal KEEP vs LIQUIDATE, sans toucher au code de décision (`scripts/e32_b4_trip_attribution.py`).

**Méthode** : rejeu B25 6L/2S 2018-2026 ; détection des **épisodes de drawdown ≥ 15 %** (pic → trip → trough) ; pour chaque épisode, snapshot des positions ouvertes **au trip** (spéc user) **et au pic local** (début du drawdown, plus informatif) ; chaque position rejouée en **KEEP** (lifecycle normal : trailing/TP/stop/time stop précalculés) vs **LIQUIDATE** (sortie immédiate au prix du jour, coûts inclus) ; Δ = KEEP − LIQ ; horizons J+1/5/10/20 ; concentration top-2/5/10 sur le DD.

**Résultat — 1 seul épisode ≥ 15 % : le bear 2022** (pic 2021-03-15 → trip 2022-01-05 → trough 2022-11-28, dd 26 %). ⚠️ **Ni 2020 ni avril 2025 ne déclenchent B4** dans ce replay (shorts 6L/2S + B4 les absorbent, DD < 15 %) → **pas de cas V-recovery disponible** pour comparer.

**Au TRIP (19 positions)** : PnL trip −5 189 $ · KEEP −6 470 $ · LIQ −5 222 $ · **Δ = −1 247 $** (LIQ légèrement mieux) ; rec 4/19, TP 2, stop 17, BE@J20 4/19. → Le gros du DD (5,2 k$ des 27,8 k$) est **déjà réalisé** par les stops : **liquider au trip est trop tardif**.

**Au PIC local (52 positions, début du drawdown)** : PnL au pic −1 915 $ · KEEP final **−9 831 $** · LIQ@pic **−1 953 $** · **Δ = −7 878 $** (LIQ nettement mieux) ; rec 8/52, TP 2, stop 50, BE@J20 8/52. → Liquider **au début du drawdown** aurait évité ~7,9 k$ de pertes.

**Horizons (bear prolongé)** : J+1 89 % encore en perte · J+5 95 % · J+20 **79 % encore en perte, BE@J20 21 %** → **pas de recovery** → pas de coût d'opportunité à liquider.

**Concentration au trip** : top-2 = 35 % des pertes (RVLV −1 198 $, REXR −644 $), top-5 = 59 %, top-10 = 87 %. **RVLV apparaît 3× dans le top-10 (cluster multi-positions)** → un **cap de concentration par symbole** est un levier distinct du force-close global.

**Verdict (règle préfixée user)** :
- Liquider **au TRIP 15 % est trop tardif** (DD déjà réalisé, Δ marginal −1,2 k$) ;
- Liquider **au début du drawdown protège nettement** (Δ −7,9 k$) avec **zéro coût de recovery** (bear prolongé) → **une force-close (ou liquidation partielle) déclenchée au début du drawdown mérite un test moteur** ;
- le **cluster RVLV** suggère d'ajouter en parallèle un **cap de concentration par symbole** ;
- ⚠️ **portée limitée** : un seul épisode (2022), pas de V-recovery pour vérifier le cas où KEEP récupère.

---

## 8ter. E33 — Concentration Risk Control (**exécuté, gate OK pour un cap modéré**)

E32 a montré que le bear 2022 commençait **avant** le trip B4 et qu'une partie des pertes venait de positions concentrées (RVLV ×3). Avant tout force-close, on teste des **caps de concentration** (mêmes signaux, mêmes C2+B4, mêmes coûts, même lifecycle — `scripts/e33_concentration_cap.py`).

**Résultat (full 2018-2026)** :

| variant | ret | Sharpe | MaxDD | worst6 | PF | maxSym |
|---|---|---|---|---|---|---|
| V0 baseline | +108.6% | 0.55 | −26.0% | −18.8% | 1.14 | **19 ⚠️** |
| V1 max2/sym | +72.9% | 0.44 | −32.4% | −22.9% | 1.11 | 2 |
| V2 max3/sym | +95.9% | 0.52 | −26.5% | −17.3% | 1.14 | 3 |
| V3 max5/sym | +97.0% | 0.53 | −26.9% | −18.1% | 1.13 | 5 |
| **V4 max3/sym + secteur 50 %** | **+98.7 %** | **0.53** | −26.5 % | **−17.3 %** | **1.15** | 3 |

**Gate (spec user)** : **V4 (max 3/sym + secteur 50 %) → GATE OK** — worst6 **+1.5 pp**, rendement **−9.1 %** (≤ 10 %), Sharpe −0.02, PF +0.01. V1 (max2) KO (−33 % rendement, MaxDD pire) ; V2/V3 KO (−11.7 %/−10.7 %).

**Lecture honnête** :
1. **Concentration du replay extrême (maxSym=19)** — en partie un **artefact du proxy TOP8-by-rank** (la prod a `concentration_max_trades_per_symbol=5`). Un cap est une **hygiène** utile.
2. **⚠️ Les caps ne réduisent PAS le MaxDD** (≈ −26 % pour tous) : le bear 2022 a frappé **tout le livre** → **la concentration n'est pas le moteur principal du drawdown** (le MaxDD est le prix de l'alpha momentum).
3. **La concentration est un moteur de rendement** : la restreindre trop (max1/2) coûte cher — les top-noms répétés sont la source de l'alpha.

**Conclusion E33** : cap modéré (3/sym + secteur 50 %) **recommandable comme règle d'hygiène production** (safe, gate OK, worst6 amélioré), mais il ne résout pas le MaxDD → pour le bear 2022 généralisé, le levier est l'**E34 (réduction partielle d'exposition pré-breaker)**, pas la concentration ni un force-close global.

---

## 9. Limites et mises en garde

1. **Rank pur OOS négatif (Test A–D)** : le seul vrai test hors-échantillon du RANK est mauvais (2026 IC −0.042). Ne pas conclure « le rank marche » sur le seul agrégat 2018-2025.
2. **Test E = replay avec assomptions** (pas bit-for-bit) : TOP8 long proxy (le réel est 6L/2S + conviction + capital_preservation), C2/B4 calibrés, ATR = moyenne simple 20 TR, sizing equal-weight gross ≤ 100 %. Les écarts vs le backtest production sont attendus.
3. **Coût en risque de B25** : drawdowns plus profonds que random (MaxDD pctl 6.8 % / 2.8 % ; worst 6m/12m bas de distribution). Le GO fort Test E porte sur Return/Sharpe — le risque de drawdown est plus élevé que le hasard.
4. **2026 court** (~100 jours, H1) : le GO fort en 2026 repose sur un seul semestre.
5. **Overlapping** (Test A–D) : fenêtres forward H20 chevauchées → autocorrélation ; les t-stats sont des repères.
6. **Période rank limitée** : `global_rank_history` B25 s'arrête à 2026-05-29.

---

## 10. Ré-exécution

```powershell
$env:PYTHONPATH='f:/projets'
# Test A-D (rank pur)
.venv\Scripts\python.exe -X utf8 scripts/e30_long_alpha_attribution.py *> logs/_e30.txt
# Test E (portefeuille C2+B4 vs 1000 random, 2 fenêtres)
.venv\Scripts\python.exe -X utf8 scripts/e31_testE_portfolio.py *> logs/_e31_test1000.txt
# puis convertir les logs UTF-16 → UTF-8 (scripts/_conv_eXX.py) et lire *_utf8.txt
```

- Changer l'univers : modifier `TICKETS` dans le script (ex : `config/ticket_mid_cap_400.txt`, `config/ticket_live.txt`).
- Test E : `N_RANDOM`, `SEED`, `MODE` ("calibrate" / "full") en tête de `e31_testE_portfolio.py`.
- Données : cache OHLCV `artifacts/backtest_cache/39587735630f_ohlcv_2017-10-26_2026-06-30.parquet`, `global_rank_history`, `stock_metadata` (secteur GICS).
- Cible de calibration Test E : run réel C2+B4 `artifacts/backtesting/e23b4_main` (+34.6 %, Sharpe 1.33).

---

## 11. Synthèse d'une ligne

> **Niveau RANK (Test A–D)** : le rank global B25 a un pouvoir de sélection réel historiquement (TOP > Random t=8.7, placebo z=24, sector-matched t=8.8), **mais instable OOS** : 2020 ≈ 0, CORRECTION ≈ 0, **2026 négatif** (IC −0.042) → **GO faible**.
>
> **Niveau PORTEFEUILLE (Test E)** : avec C2+B4+sizing+coûts, B25 bat le hasard à **98-100 %** des 1 000 randoms sur 2018-2025 **et en 2026 OOS** (Return +17.8 % vs médiane −0.6 %, pctl 100 %) → **GO fort portefeuille** (règle >P95 Return/Sharpe), **avec un coût en drawdown plus élevé que random** et une fenêtre 2026 courte. **L'architecture complète apporte une vraie valeur économique aujourd'hui, même si le ranking seul a perdu son pouvoir OOS.**
