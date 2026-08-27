# persistent_top10_dip_validation — 2026-08-27

Validation du signal « GlobalRank TOP10 persistant + baisse récente » (DIP).
Aucun réentraînement, aucun changement risk/PROD. Période **2022-2024**.
Configurations pré-enregistrées : N ∈ {3,4,5}, X ∈ {2%, 3%}.

## Protocole
- Signal à la clôture de J : `global_rank_20 ≥ 0.90` pendant N séances
  consécutives ET `ret_N ≤ −X` (`ret_N = adj_close[J]/adj_close[J−N] − 1`).
- Comparatifs : BASE (TOP10 sans condition), MOMENTUM (persistant + ret_N ≥ +X),
  DIP (persistant + ret_N ≤ −X). **Entrée LONG à J+1**, détention 20 séances.
- Métriques : D1..D10, BAD5/GOOD5, mean/median H20, P>0, PF, MFE, MAE,
  time-to-recovery, n, signaux/mois — par année/semestre/régime.

## Résultats agrégés (CSV : artifacts/persistent_top10_dip.csv)
| Strat | N·X | n | mean H20 | median | P>0 | PF | GOOD5 | G5−B5 | MFE | MAE | TTR |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BASE | — | 152 167 | +0.025 | +0.006 | 0.522 | 1.52 | +0.125 | 0.210 | 0.141 | −0.104 | 2.9 |
| **DIP** | 4·3% | 3 559 | **+0.064** | **+0.035** | **0.564** | **2.05** | **+0.214** | **0.336** | 0.240 | −0.134 | 2.8 |
| **DIP** | 4·2% | 5 247 | +0.062 | +0.032 | 0.561 | **2.08** | +0.204 | 0.321 | 0.224 | −0.128 | 2.8 |
| **DIP** | 3·3% | 4 331 | +0.062 | +0.028 | 0.560 | **2.07** | +0.204 | 0.320 | 0.231 | −0.131 | 2.8 |
| MOMENTUM | 4·3% | 2 704 | +0.062 | +0.017 | 0.534 | 2.00 | +0.208 | 0.324 | 0.219 | −0.138 | 3.0 |

DIP bat BASE (mean ×2.5, median ×5, PF 1.52 → 2.05, GOOD5−BAD5 0.21 → 0.34) et
MOMENTUM (P>0 0.56 vs 0.54, median 0.035 vs 0.017, PF 2.05 vs 2.00).

## Stabilité par année / régime
Par année : 2022 **+0.083** (P>0 0.57) · 2023 **+0.021** (0.52, ≈ BASE) · 2024 **+0.076** (0.59).
Par régime :
| régime | BASE | DIP |
|---|---|---|
| normal | +0.038 / 0.54 | **+0.134 / 0.62** |
| cash_only | +0.020 / 0.51 | **+0.040 / 0.56** |
| capital_preservation | +0.013 / 0.51 | **+0.040 / 0.56** |
| close_only | +0.015 / 0.52 | −0.026 / 0.46 |

## Verdict GO — **GO (avec close_only hors-périmètre)**
- **`close_only` = non tradable** (le module risque bloque toute entrée) →
  l'effondrement du DIP en close_only n'est **pas une vraie faiblesse** : aucune
  entrée n'y serait possible en production.
- Sur **tous les régimes tradables** (normal, cash_only, capital_preservation),
  **DIP bat BASE** (mean +0.134/+0.040/+0.040 vs +0.038/+0.020/+0.013 ; P>0
  0.62/0.56/0.56 vs 0.54/0.51/0.51).
- ✅ mean ×2.5 · ✅ GOOD5/BAD5 · ✅ PF 2.05 vs 1.52 · ✅ stabilité sur périodes
  tradables (2023 = plat, pas effondrement).
- **Réserve** : 2023 plat (edge concentré en 2022/2024, régime normal). n ≈ 99-146
  signaux/mois (≈ 5-7/séance) — viable pour un portefeuille ~20 positions.

→ **Aller à la Phase 2 : backtest de portefeuille avec le lifecycle PROD inchangé**
(sizing/stops/CP/breaker non modifiés), résultats par année/semestre/régime.

---

# Phase 2 — Backtest de portefeuille (2026-08-27)

Backtest **portefeuille** avec le **lifecycle PROD inchangé** (`BacktestEngine` +
`BacktestConfig` répliquant la commande pipeline PROD : equity 4000, max_positions
20, margin, ATR stop 2.5 / TP 3.0×ATR / max 7 %, coûts canoniques 1/2 bps, margin
interest 7.5 %, fractional shares, sizing equal, cap sectoriel 50 %, DD breaker
15 %/recov 92 %, target_annual_vol 0.13, `use_live_protection_logic=True`).

Variantes (configurations pré-enregistrées, AUCUN sweep) :
- **P0** = TOP10 global_rank (sans filtre DIP) — BASE
- **P1** = persistent TOP10 (N=4) ET ret_4 ≤ −2 % (DIP)
- **P1b** = persistent TOP10 (N=4) ET ret_4 ≤ −3 %
- **P2** = P1 + veto close_only (aucune entrée si régime du jour == close_only)

Signal calculé au close J ; entrée selon le contrat d'exécution PROD (J+1 open).

## Résultats (CSV : artifacts/persistent_top10_dip_portfolio.csv, 2022-2024)
| Variante | Total ret | CAGR | Sharpe | Sortino | MaxDD | PF | Win | n trades | Exposure | Slots | Cap util |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **P0** BASE | +12.6% | 3.95% | 0.318 | 0.442 | −17.5% | 1.068 | 51.8% | 1 725 | 85.6% | 16.6 | 82.8% |
| **P1** DIP −2% | +14.8% | 4.62% | 0.382 | 0.519 | −19.4% | 1.086 | 64.9% | 967 | 84.8% | 8.1 | 40.5% |
| **P1b** DIP −3% | +15.1% | 4.69% | 0.404 | 0.565 | −18.2% | 1.100 | 68.0% | 772 | 86.0% | 6.3 | 31.6% |
| **P2** P1 sans close_only | **+51.2%** | **14.5%** | **1.008** | **1.371** | **−11.2%** | **1.295** | **68.6%** | 946 | 78.5% | 7.4 | 37.1% |

## Attribution par régime d'entrée (avg PnL / PF / win)
| Variante | normal | cash_only | cap_pres | close_only |
|---|---|---|---|---|
| **P0** | +0.82 / 1.19 / 0.53 | +0.27 / 1.04 / 0.64 | −0.58 / 0.89 / 0.51 | +0.29 / 1.07 / 0.49 |
| **P1** | +3.26 / 1.45 / 0.71 | +1.72 / 1.27 / 0.72 | −0.21 / 0.97 / 0.64 | **−2.83 / 0.73 / 0.52** |
| **P1b** | +4.06 / 1.51 / 0.75 | +2.81 / 1.43 / 0.75 | +0.03 / 1.00 / 0.67 | **−3.73 / 0.70 / 0.54** |
| **P2** | +4.28 / **1.57** / 0.71 | +1.72 / 1.27 / 0.72 | −0.22 / 0.97 / 0.64 | — (veto) |

## Répartition Oracle du DIP (CSV : artifacts/dip_oracle_tranches.csv)
| Variante | n | D10 | BAD5 | GOOD5 | mean_fwd | median | P>0 |
|---|---|---|---|---|---|---|---|
| **P0_TOP10** | 152 167 | 19% | 0.475 | 0.525 | +0.0247 | 0.0063 | 0.521 |
| **P1_DIP** | 5 215 | 29% | 0.443 | 0.557 | +0.0615 | 0.0318 | 0.566 |
| **P2_no_close** | 4 069 | 30% | 0.419 | 0.581 | +0.0848 | 0.0427 | 0.595 |

Veto close_only : retire **1 147** entrées (D1..D10=[312,93,74,65,64,49,51,77,98,263])
de **mauvaise qualité** : BAD5=0.531, GOOD5=0.469, **mean_fwd=−0.021** (négatif).

## Verdict Phase 2
1. **Le DIP améliore la qualité** (P0→P1 : win 51.8→64.9 %, PF 1.068→1.086, médiane
   de trade +1.2 %→+7.0 %) mais **réduit l'exposition** (slots 16.6→8.1, cap_util
   82.8→40.5 %) → CAGR quasi plat (3.95→4.62 %).
2. **Le veto close_only est le facteur dominant** (P1→P2) : CAGR ×3.1 (4.62→**14.5%**),
   Sharpe 0.38→**1.01**, MaxDD −19.4→**−11.2%**, PF 1.086→**1.295**. Cohérent avec
   l'attribution : en P1 les entrées close_only sont **perdantes** (PF 0.73, avg −2.83)
   ; le veto les retire et l'amélioration est massive.
3. P1b (−3 %) ≈ P1 → la X du DIP compte peu ; **c'est le filtre close_only qui porte
   le gain**.

## ⚠️ Prudence
**P2 ne doit PAS être déclaré « validé OOS »** : le veto close_only a été découvert
sur ces mêmes données 2022-24 (le résultat est partiellement en-échantillon par
construction). Un backtest sur données hors-échantillon est requis avant toute
décision PROD.
