# Robustesse B25+H20+top10%+P14+m8 — 4 tests ciblés (2026-08-17)

Pile **GELÉE** (inchangée) : `B25` = model-factory-20260811223551-ef2cd0 → H20
(config `backtest_horizon: 20`) → top 10 % → P14 (défauts code) → m8
(`--max-positions 8`). Coûts canoniques réels (spread bid-ask `stock_quote_snapshots`
+ comm 1 bps + slippage 2 bps). Période : 2026-01-02 → 2026-05-31.

Référence (benchmark archivé OOS2026_B25_P14_m8_v1, parité bit-for-bit vérifiée
avec le run `stress_cost_ctl_m1`) : **+27.093 % / DD 3.096 % / PF 2.224 / 77
trades (46L/31S) / win 50.65 % / LONG +1 488 / SHORT +18 686 / gross 73.10 %**.

---

## Test 1 — Stress des coûts (`--cost-multiplier`, nouveau flag de diagnostic)

Le coût de transaction total (spread réel + commission + slippage + pénalité
d'exécution) est multiplié par un facteur. `1.0` = parité exacte (les 29 tests
de parité passent ; `x*1.0` est exact en IEEE 754).

| mult | Rendement | DD | PF | trades | LONG PnL | SHORT PnL | gross |
|------|-----------|-----|-----|--------|----------|-----------|-------|
| 1.0  | +27.093 % | 3.096 % | 2.224 | 77 | +1 488 | +18 686 | 73.10 % |
| 1.25 | +26.856 % | 3.124 % | 2.202 | 77 | +1 375 | +18 569 | 73.18 % |
| 1.5  | +26.619 % | 3.152 % | 2.180 | 77 | +1 261 | +18 451 | 73.25 % |
| 2.0  | +26.144 % | 3.208 % | 2.138 | 77 | +1 034 | +18 216 | 73.41 % |
| 3.0  | +25.196 % | 3.322 % | 2.057 | 77 | +580  | +17 745 | 73.71 % |

**Lecture** :
- Les 77 trades (46L/31S) restent **identiques** à tous les niveaux : le
  `cost_multiplier` n'affecte que le P&L, jamais la sélection.
- Chaque « +1.0 » de coût coûte ≈ 0.95 pt de rendement (27.09 → 25.20 quand les
  coûts triplent). DD ne bouge que de 3.10 → 3.32 %.
- PF reste > 2.05 même à coûts ×3.
- **Point de non-rentabilité extrapolé ≈ 28× les coûts actuels** (rendement
  → 0). Marge d'erreur économique **très large** sur 2026.
- La jambe LONG est la plus sensible (long PnL 1 488 → 580 à ×3) : petits PnL
  unitaires, coût relatif plus fort. Sans impact sur la robustesse globale.

---

## Test 2 — Stress FILLS / SLIPPAGE (résultats)

Détérioration de la qualité d'exécution (impact volume sur gros ordres, latence)
sans toucher la sélection. Le contrôle (`fills_ctl`) reproduit le benchmark
bit-for-bit → le mécanisme est valide.

| run | config | Rendement | DD | PF | trades |
|-----|--------|-----------|-----|-----|--------|
| `fills_ctl` | sqrt, base 0, impact 0 | +27.09 % | 3.096 % | 2.224 | 77 |
| `fills_imp50` | sqrt, impact 50 bps | +26.97 % | 3.108 % | 2.213 | 77 |
| `fills_imp100` | sqrt, impact 100 bps | +26.86 % | 3.121 % | 2.201 | 77 |
| `fills_imp200` | sqrt, impact 200 bps | +26.62 % | 3.146 % | 2.179 | 77 |
| `fills_lat5` | sqrt, base 5 + impact 100 | +25.92 % | 3.222 % | 2.118 | 77 |
| `fills_arrival50` | arrival_price factor 0.5 | +27.09 % | 3.096 % | 2.224 | 77 |

**Lecture** :
- Les 77 trades restent **identiques** (46L/31S) : la sélection est insensible à
  la qualité d'exécution.
- Impact volume 200 bps : −0.47 pt de rendement, PF 2.18 — très robuste.
- Latence systématique 5 bps + impact 100 : −1.17 pt, PF 2.12 — encore sain.
- `arrival_price` (factor 0.5) : **identique au benchmark** — le mode
  `execution_replay` fixe les prix d'exécution en phase 2/3, donc le modèle
  d'exécution intraday (`compute_execution_price`) n'est PAS appliqué dans ce
  chemin. À noter pour ne pas surinterpréter ce run.

**Verdict Test 2** : ✅ robuste aux fills dégradés (PF > 2.1 même à impact 200 bps + latence).

---

## Test 3 — Concentration m8 (benchmark 2026)

Source : `trade_audit_log.csv` (378 événements : 102 snapshots quotidiens,
85 entrées, 77 sorties, 84 transitions watcher).

**Gross / exposition par jour**
- Gross moyen 73.1 %, médian 69.0 %, max **128 %** (jamais > 150 % ; 10 jours > 100 %).
- Net moyen −30.7 % (bias SHORT structurel : 98/102 jours short net).
- LONG moyen 21.2 % (max 53.8 %) ; SHORT moyen 51.9 % (max 89.6 %).
- Notional cumulé : LONG 2.47 M$ vs SHORT 6.13 M$ (71 % du volume côté short).

**Positions simultanées** (appariement FIFO des 77 paires entrée→sortie)
- min 0 / moy **6.9** / max **8** ; p50 7, p95 8.
- 50/105 jours au plafond de 8 positions ; 79 jours > 6 positions.
- Gross max atteint 128 % avec 8 positions (poids cible moyen 11.5 %).

**Poids par symbole** (target_weight_pct à l'entrée)
- min 4.4 % / moy 11.6 % / max **24.9 %** ; p90 18.4 %, p95 21.3 %.
- Une seule entrée > 24 % (CLX 24.93 %).

**Poids par secteur** (joindre symbol → GICS, mapping 11 579 symbols)
- Cumul sur la période dominé par Technology (257 %, 28 entrées).
- **Par jour** : poids max secteur moy 25.7 %, max **45.3 %** (Technology, janvier),
  p95 41.9 %. Jours secteur > 30 % : 25 ; > 40 % : 7 ; **> 50 % : 0**.
- Le secteur dominant moyen est Energy (29.3 %) puis Financial Services (28.5 %).

**Contribution top trades**
- PnL net total +20 174 $ (exits).
- top1 = 3 190 $ (15.8 %) · top1+2 = 29.5 % · top1+2+3 = **42.8 %** · top10 = **121.5 %**.
- → Les 67 autres trades sont nets négatifs (−4 331 $) : la performance 2026 est
  **concentrée sur ~10 shorts**. C'est la principale caractéristique de risque.
- Pires trades : ALSN −1 320 $, BFH −1 154 $, CTRI ×2 (≈ −1 100 / −937 $), CAG −947 $.
- Titres récurrents : KD 6 trades (+2 972 $), BILL 5 (+24 $), VRNS 5 (+1 333 $).

---

## Test 4 — Bootstrap / Monte-Carlo (2022/2024/2025/2026, N=5000)

Runs m8 : 2022 +25.25 % (236 trades), 2024 −5.89 % (82), 2025 +45.95 % (191),
2026 +27.09 % (77). Pool total 586 trades.

### A. Stationary bootstrap journalier (bloc moyen 10 j)

| année | ret réel | DD réel | ret p5 | P(ret<0) | DD p95 | P(DD>10 %) | P(DD>15 %) |
|-------|----------|---------|--------|----------|--------|-----------|-----------|
| 2022  | +25.25 % | 8.43 %  | −0.1 % | 5.1 %    | 15.4 % | 32.5 %    | 5.9 %     |
| 2024  | −5.89 %  | 8.18 %  | −16.6 %| 79.7 %   | 19.2 % | 63.9 %    | **22.2 %**|
| 2025  | +45.95 % | 6.19 %  | +23.3 %| 0.0 %    | 8.5 %  | 1.4 %     | 0.0 %     |
| 2026  | +27.09 % | 3.10 %  | +11.7 %| 0.06 %   | 5.1 %  | 0.0 %     | 0.0 %     |

### B. Bootstrap des trades (resampling + réordonnancement, mise = notional/equity)

| année | ret moy | ret p5 | P(ret<0) | DD moy | DD p95 | P(DD>15 %) |
|-------|---------|--------|----------|--------|--------|-----------|
| 2022  | +39.4 % | +10.2 %| 0.8 %    | 6.7 %  | 11.0 % | 0.6 %     |
| 2024  | −2.6 %  | −14.7 %| 65.0 %   | 9.8 %  | 16.8 % | 10.3 %    |
| 2025  | +74.4 % | +33.8 %| 0.0 %    | 5.7 %  | 9.0 %  | 0.04 %    |
| 2026  | +29.9 % | +10.7 %| 0.3 %    | 3.4 %  | 5.7 %  | 0.0 %     |

### C. Pool combiné (586 trades, 4 ans mélangés)

- ret : moy +206 %, p5 +96.8 %, P(ret<0) = 0 %.
- DD : moy 8.5 %, p95 13.0 %, max 21 %.
- **P(DD > 10 %) = 22.2 % · P(DD > 15 %) = 1.8 % · P(DD > 20 %) = 0.02 %**.

### D. Compte multi-années (4 ans consécutifs simulés, bloc journalier)

- DD : moy 10.7 %, p50 10.1 %, p95 16.3 %, max 33.3 %.
- **P(DD > 5 %) = 99.96 % · P(DD > 10 %) = 51.8 % · P(DD > 15 %) = 8.7 % ·
  P(DD > 20 %) = 0.9 % · P(DD > 25 %) = 0.1 %**.
- ret combiné : moy +124 %, p5 +51.7 %, P(ret<0) = 0 %.

### Réponse à la question centrale

> « Avec la distribution de trades que B25 produit, quelle est la probabilité
> que mon compte réel subisse un DD > 15 % ? »

- Sur un compte multi-années (4 ans consécutifs) : **P(DD > 15 %) ≈ 9 %**,
  P(DD > 20 %) ≈ 0.9 %.
- Si une année ressemble à 2024 (la pire) : P(DD > 15 %) ≈ 10-22 % selon méthode.
- Sur une année type 2026 : P(DD > 15 %) ≈ 0 %.

---

## Synthèse

1. **Coûts** : marge d'erreur très large (rentabilité jusqu'à ~28× le coût actuel
   sur 2026). ✅
2. **Fills** : en cours (impact volume + latence).
3. **Concentration** : 8 positions max (plafond atteint 50 % des jours), poids
   symbole ≤ 25 %, secteur/jour ≤ 45 % (jamais > 50 %). Le risque principal est
   la **concentration du PnL** : top3 = 43 % du PnL, top10 = 121 % (les 67 autres
   trades nets négatifs). ⚠️ à surveiller en réel.
4. **Bootstrap** : P(DD > 15 %) ≈ 9 % sur 4 ans, P(DD > 20 %) < 1 %, P(ret<0) sur
   4 ans = 0 %. ✅

Décision proposée : si Test 2 passe (PF reste > ~1.5 à impact 200 bps), la pile
est suffisamment testée pour un **shadow/live très petit** (conformément au
plan) — pas besoin de P25/P26/P27.

Scripts : `scripts/stress_cost_multiplier.py`, `scripts/stress_cost_multiplier_rerun.py`,
`scripts/stress_fills.py`, `scripts/analyze_concentration_m8.py`, `scripts/bootstrap_m8.py`.
