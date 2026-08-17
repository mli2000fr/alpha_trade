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

## ⚠️ AUDIT COMPTABLE DES COÛTS (post-Test 1) — découverte critique

À la demande de revue : que multiplie réellement `cost_multiplier` et combien le
moteur débite-t-il réellement par trade ?

### Code exact du calcul de coût (`backtesting/simulator.py`)

- **Entrée** (ligne ~1451) : `slippage_bps = 5.0 * cost_multiplier + spread/2`
  (le spread est déjà multiplié par `cost_multiplier` dans `_get_spread_bps`).
  → prix d'exécution = prix ± `slippage_bps/10000`.
- **Sortie** (ligne ~2124) : `fees_rate = _effective_fees_pct + spread/2`
  avec `_effective_fees_pct` = (comm 1 + slip 2 bps) × `cost_multiplier`.
- Donc `cost_multiplier` multiplie bien **tout le coût** (spread + 5 bps d'entrée
  + comm + slippage). Le test ×3 est un vrai triple du coût de transaction.

### Coût réellement débité (audit par différence ×3−×1, 77 trades identiques)

| métrique | valeur |
|---|---|
| Coût total mesuré (77 trades) | **924.90 $** |
| Coût moyen / trade | 12.01 $ |
| **Coût round-trip en bps** (coût/notional moyen) | **10.32 bps** |
| Notional entrée total | 904 892 $ (moy 11 639 $/trade) |

**Votre intuition était correcte : le moteur ne débite PAS 44-49 bps par trade.**
Il débite ~10 bps round-trip. Pourquoi :
- Les **titres tradés** (top 10 % global rank) sont des large caps liquides :
  spreads réels ~6-16 bps (CAG 6.4, VTRS 7.4, LBRDK 7.8, BSY 8.8, VRNS 12.7, KD 16.2).
- La **médiane globale de 44 bps est trompeuse** : elle est tirée par 37.6 % de
  données CORROMPUES (>300 bps, ex: MNDY 2782 bps, GDDY 841, FMC 357, QFIN 11902)
  qui sont filtrées par `MAX_REALISTIC_SPREAD_BPS=300` → **fallback 5 bps**.
- 43.5 % des trades utilisent le fallback 5 bps (données absentes ou corrompues).

### Conséquences

1. **Le coût de base réel est ~10 bps round-trip**, pas 44-49 bps. Le test ×3
   (≈30 bps round-trip) est donc une marge réaliste par rapport au coût actuel,
   mais pas une preuve de robustesse à 44-49 bps.
2. **Marge absolue** : chaque bps round-trip coûte ~90 $ (≈0.09 pt de rendement).
   Le point de non-rentabilité ≈ 300 bps round-trip. Même un scénario pessimiste
   à 44 bps round-trip donnerait ~+24 % (PF ~2). Le système reste donc très
   robuste MÊME si le vrai coût était 44 bps.
3. **⚠️ Faiblesse des données** : 37.6 % des snapshots >300 bps sont corrompues.
   Le filtre 300 bps est trop permissif (un spread de 100-300 bps sur large cap
   est quasi certainement corrompu et est APPLIQUÉ — ex: CLX 126.5 bps le 21/01
   alors que le vrai spread est 3.6 bps). Il y a à la fois des trades surpayés
   (spreads 100-300 corrompus appliqués) et des trades sous-payés (fallback 5).
4. **Recommandation** : avant de conclure sur la robustesse, nettoyer les
   données de spread (médiane mobile / winsorisation) ou refaire le test avec un
   fallback plus conservateur (10-20 bps) pour mesurer le coût pessimiste réaliste.

Scripts : `scripts/audit_costs.py`, `scripts/audit_spread_data.py`,
`scripts/check_traded_spreads.py`.

---

## Test 1b — Coût round-trip ABSOLU + fallback (résultats)

Pour lever l'ambiguïté « coût relatif ×N vs coût absolu », deux nouvelles séries
forcent directement le coût (nouveaux flags `--cost-round-trip-bps` = coût RT
absolu C/2 par jambe, et `--fallback-spread-bps` = fallback relevé).

### Série A — coût round-trip ABSOLU forcé (2026)

| Coût RT | Rendement | DD | PF | trades |
|---------|-----------|-----|-----|--------|
| 10 bps (contrôle ≈ actuel) | +27.11 % | 3.08 % | 2.225 | 77 |
| 20 bps (prudent) | +26.17 % | 3.19 % | 2.140 | 77 |
| 30 bps (très prudent) | +25.23 % | 3.29 % | 2.060 | 77 |
| **44 bps (pessimiste)** | **+23.93 %** | **3.43 %** | **1.953** ✅ | 77 |
| 60 bps (extrême) | +22.43 % | 3.60 % | 1.840 | 77 |

**Verdict 44 bps RT : PF = 1.95 > 1.5 ET DD = 3.43 % < 10 % → ✅ risque coûts CLOS.**
Même à 60 bps RT (6× le coût actuel), le système reste à +22.4 % / PF 1.84.
Chaque +10 bps RT coûte ≈ 0.94 pt de rendement (cohérent avec l'audit : ~0.09 pt/bps).

### Série B — fallback relevé (données absentes/corrompues rejetées)

| Fallback | Rendement | DD | PF | trades |
|----------|-----------|-----|-----|--------|
| 10 bps | +27.00 % | 3.10 % | 2.215 | 77 |
| 15 bps | +26.92 % | 3.10 % | 2.206 | 77 |
| 20 bps | +26.83 % | 3.11 % | 2.197 | 77 |

Impact **quasi nul** : les titres tradés ont déjà des spreads réels ~6-16 bps, donc
relever le fallback de 5 → 20 bps ne change presque rien. Confirme que le coût
actuel (~10 bps RT) n'est pas sous-estimé de façon significative pour l'univers tradé.

### Audit de prise en compte des coûts sur TOUS les stress tests

Vérification que chaque run débite bien son coût cible (méthode : P&L brut estimé
constant, coût = P&L brut − P&L net du run ; tous les runs ont les 77 mêmes trades).

| run | type | cible bps | P&L net $ | coût $ | coût bps | ratio |
|-----|------|-----------|-----------|--------|----------|-------|
| benchmark | baseline | 10.32 | 20 175 | 925 | 10.32 | 1.00 |
| stress_cost_m125 | multiplier ×1.25 | 12.90 | 19 943 | 1 156 | 12.90 | 1.00 ✅ |
| stress_cost_m15 | multiplier ×1.5 | 15.48 | 19 712 | 1 387 | 15.48 | 1.00 ✅ |
| stress_cost_m20 | multiplier ×2 | 20.64 | 19 250 | 1 850 | 20.64 | 1.00 ✅ |
| stress_cost_m30 | multiplier ×3 | 30.96 | 18 325 | 2 775 | 30.96 | 1.00 ✅ |
| cost_rt10 | RT absolu 10 | 10.00 | 20 203 | 896 | 10.00 | 1.00 ✅ |
| cost_rt20 | RT absolu 20 | 20.00 | 19 307 | 1 792 | 20.00 | 1.00 ✅ |
| cost_rt30 | RT absolu 30 | 30.00 | 18 411 | 2 689 | 30.00 | 1.00 ✅ |
| cost_rt44 | RT absolu 44 | 44.00 | 17 156 | 3 943 | 44.00 | 1.00 ✅ |
| cost_rt60 | RT absolu 60 | 60.00 | 15 722 | 5 377 | 60.00 | 1.00 ✅ |
| fb10 | fallback 10 | 10.32 | 20 087 | 1 013 | 11.30 | 1.10 |
| fb15 | fallback 15 | 10.32 | 19 999 | 1 101 | 12.28 | 1.19 |
| fb20 | fallback 20 | 10.32 | 19 911 | 1 189 | 13.26 | 1.29 |
| fills_imp50 | impact 50 | 10.32 | 20 060 | 1 039 | 11.60 | 1.12 |
| fills_imp100 | impact 100 | 10.32 | 19 946 | 1 154 | 12.87 | 1.25 |
| fills_imp200 | impact 200 | 10.32 | 19 717 | 1 383 | 15.43 | 1.50 |
| fills_lat5 | base5+impact100 | 10.32 | 19 049 | 2 050 | 22.87 | 2.22 |

**Lecture** :
- **Ratio = 1.00 sur les scénarios à cible exacte** (multiplier ×m et RT absolu C) →
  le moteur débite **exactement** le coût cible annoncé. Les mécanismes
  `--cost-multiplier` et `--cost-round-trip-bps` sont fidèles.
- **Fallback / fills** : ratio > 1 = le surcoût attendu PAR-DESSUS la baseline
  (cible = baseline 10.32). Relever le fallback 5→20 bps ajoute 1-3 bps RT ;
  l'impact volume 50→200 bps ajoute 1.3→5.1 bps RT ; la latence (base5+impact100)
  ajoute 12.5 bps RT. Tous cohérents avec les modèles.

Script : `scripts/audit_stress_costs.py`.

---

## Synthèse

1. **Coûts** : marge très large. Coût réellement débité ~10 bps RT. Scénario
   pessimiste **44 bps RT → +23.9 % / DD 3.4 % / PF 1.95** (critère PF>1.5 & DD<10%
   satisfait). Extrême 60 bps RT → +22.4 % / PF 1.84. **✅ risque coûts CLOS.**
2. **Fills** : ✅ robuste aux fills dégradés (PF > 2.1 même à impact 200 bps + latence).
3. **Concentration** : 8 positions max (plafond atteint 50 % des jours), poids
   symbole ≤ 25 %, secteur/jour ≤ 45 % (jamais > 50 %). Le risque principal est
   la **concentration du PnL** : top3 = 43 % du PnL, top10 = 121 % (les 67 autres
   trades nets négatifs). ⚠️ à surveiller en réel.
4. **Bootstrap** : P(DD > 15 %) ≈ 9 % sur 4 ans, P(DD > 20 %) < 1 %, P(ret<0) sur
   4 ans = 0 %. ✅

Décision : la pile est suffisamment validée → **GO paper Alpaca directement**
(le paper rend le shadow mode redondant). Pas besoin de P25/P26/P27.

Scripts : `scripts/stress_cost_multiplier.py`, `scripts/stress_cost_multiplier_rerun.py`,
`scripts/stress_fills.py`, `scripts/analyze_concentration_m8.py`, `scripts/bootstrap_m8.py`.
