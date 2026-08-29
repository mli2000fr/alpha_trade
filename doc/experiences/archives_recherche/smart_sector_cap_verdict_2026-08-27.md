# Chantier `smart_sector_cap` — Verdict C0/C1/C2 (2026-08-27)

Famille homogène 2022-01-01 → 2024-12-31, commande PROD identique pour les 3 runs
(engine-mode pipeline, batch ef2cd0, cap count=2, `--sector-cap-mode` varie).
Source des métriques : **logs** (`logs/smart_c0|smart_c1|smart_c2.log`) — source unique fiable.

## Résultats

| Métrique | C0 (count=2) | C1 (expo 20%) | C2 (hybrid) |
|---|---:|---:|---:|
| Valeur finale | $4,663.71 | $4,330.35 | $4,559.03 |
| Rendement total | **16.59%** | 8.26% | 13.98% |
| CAGR | **5.27%** | 2.69% | 4.48% |
| Sharpe | **0.329** | 0.230 | 0.299 |
| Sortino | **0.411** | 0.303 | 0.365 |
| Calmar | **0.207** | 0.117 | 0.178 |
| Ulcer | 16.297 | **15.025** | 16.205 |
| MaxDD | 25.41% | **23.00%** | 25.20% |
| Trades | 1436 | 1316 | 1461 |
| Win rate | **50.6%** | 50.8% | 50.4% |
| Durée moy (j) | 5.7 | 5.3 | 5.6 |
| Profit Factor | **1.08** | 1.03 | 1.07 |
| PnL net | **$987.33** | $364.49 | $842.10 |
| Expo brute moy | 74.2% | **53.3%** | 72.4% |
| Turnover (x/an) | 79.32x | 62.96x | **81.77x** |
| Force-close | **8** | 12 | 14 |

## Activité des variantes (logs)

- **C0** : aucun rejet exposure/corr, aucun 3e ticker (cap count pur).
- **C1** : 2209 rejets `sector_exposure_cap` (position réduite → 0).
- **C2** : 24 acceptations 3e ticker (exception hybrid), 1210 rejets `sector_exposure_cap`,
  157 rejets `sector_corr_threshold` → approche très stricte (24/1391 tentatives ≈ 1.7%).

## Attribution marginale (trades clos, clé symbol+entry_date, PnL BRUT exit_closed)

### C0 → C1
- Retirés **414** (trades que C0 prenait) : PnL brut **+$518.86**, WR 46.4%
  → C1 retire des trades **gagnants** (le cap expos 20% détruit de la valeur).
- Ajoutés **290** : PnL brut **-$60.50**, WR 46.6%.
- Communs (1014) : delta PnL variant-base = **-$36.04**.
- → Coût net brut ≈ -$579 ; net du rapport : $987 → $364 (**-$623**).

### C0 → C2
- Ajoutés **85** (3e ticker hybrid + réallocations) : PnL brut **+$579.48**, WR 55.3%,
  mean return +0.67% → **gagnants en brut**.
- Retirés **66** : PnL brut **+$383.85** perdu (sizing/budget modifiés par l'ajout des 3e tickers).
- Communs (1362) : delta **+$28.03**.
- Brut : C2 +$224 de plus que C0 ($1725 vs $1501).
- **MAIS net : C2 $842 vs C0 $987 → -$145.** Les coûts additionnels (turnover 81.77x vs 79.32x,
  +25 trades, force-close 14 vs 8, intérêts marge) absorbent plus que le gain brut des trades ajoutés.

### C1 → C2
- Ajoutés **416** : PnL brut +$809 (C2 relâche ce que l'expo 20% bloquait).
- Retirés **273** : PnL brut +$16 perdu.

## Verdict — critères GO du chantier

| Critère | C1 | C2 |
|---|---|---|
| Sharpe > C0 (0.329) | 0.230 ✗ | 0.299 ✗ |
| Return >= C0 (16.59%) | 8.26% ✗ | 13.98% ✗ |
| PF >= C0 (1.08) | 1.03 ✗ | 1.07 ✗ |
| MaxDD pas pire | 23.00% ✓ (mieux) | 25.20% ✓ (≈) |
| Concentration contrôlée | ✓ (≤2) | ✓ (≤3, 24 j) |
| PnL marginal ajoutés > 0 après coûts | ✗ (retire +$518 gagnants) | ✗ (-$145 net vs C0) |

- **C1 = NO-GO** : échoue Sharpe/return/PF ; retire des trades gagnants (+$518 brut) ;
  sacrifie beaucoup de rendement pour une réduction de MaxDD modeste.
- **C2 = NO-GO** : échoue Sharpe/return/PF ; les 85 trades ajoutés sont gagnants en brut
  (+$579) mais le PnL net après coûts est **négatif** (-$145 vs C0) → le turnover/frais
  mangent l'avantage. Concentration bornée (≤3/secteur) mais au prix d'une performance nette inférieure.
- **C0 (count cap=2) = statu quo optimal** → on garde `max_tickers_per_sector: 2`.
- C3 = NO-IMPLEMENTATION (pas de budget risque PIT) — inchangé.

## Décision
`--sector-cap-mode` reste configurable (count/exposure/hybrid, défaut = count)
mais **aucune des variantes n'est retenue pour la production**. Cap=2 conservé.

## Fix appliqués au passage
- `portfolio_builder.py` : `import pandas as pd` au niveau module (NameError C2).
- `portfolio_builder.py` : assertion PIT hybrid utilise `_decision_date = trade_date or date.today()`
  calculé localement (UnboundLocalError `decision_date` avant assignation).

## ✅ CLÔTURE OFFICIELLE DU CHANTIER (validée 2026-08-27)
- **C0 — cap count=2 : KEEP / GO** (figé, on n'y touche plus)
- **C1 — cap exposition 20% : NO-GO**
- **C2 — hybride count+expo+corr : NO-GO**
- **C3 — risk budget : non implémenté** (pas de définition PIT propre)

Leçon : le cap=2 ne gagne pas seulement par conservatisme — il produit une meilleure
efficacité de portefeuille réelle (les alternatives ajoutent des trades bons en brut
mais le turnover + coûts + force-close détruisent l'avantage net).

**État gelé (architecture DIP) : N4/X2 = gelé · sector cap = gelé à 2 · reclaim = NO-GO · smart cap = NO-GO.**
Prochain ordre : 1) adapter le pipeline autour de N4/X2 → 2) gaps couverture/parité →
3) valider que le pipeline exploite N4/X2 → 4) chantier DipQualityModel / GlobalDirection conditionnel sur N4/X2.
