# 📊 Étape A — Re-benchmark canonique post-fix TP (B25 P14 m8)

**Date** : 2026-08-19
**Méthode** : re-run exact des runs production-parity sur le HEAD actuel (contient le fix `take_profit_price`, commit `26cfa346` inclus), **même commande CLI** que l'original (reconstituée depuis `_console.log` du benchmark).

**Commande reproduite** (source de vérité : `artifacts/benchmarks/OOS2026_B25_P14_m8_v1/_console.log` ligne 0) :
```
python -X utf8 -m backtesting run --engine-mode pipeline --ml-pit-strategy use-persisted
  --phase2-mode risk_execution --phase3-mode execution_replay --phase4-mode protection_replay
  --phase5-mode watcher_replay --phase7-mode exit_lifecycle_replay
  --start <2026-01-02|2025-01-02> --end <2026-05-31|2025-12-31>
  --ml-batch-id model-factory-20260811223551-ef2cd0 --cascade-batch-id model-factory-20260811223551-ef2cd0
  --batch-diagnostics-batch-id model-factory-20260811223551-ef2cd0 --best-horizon 20
  --cascade-top-pct 0.10 --min-ml-coverage-ratio 0.90 --capital-preset-key capital_2001_5000
  --max-positions 8 --use-canonical-costs --atr-risk-stop-multiple 2.5 --tp-atr-multiple 3.0 --tp-max-pct 0.07
```
Seule différence vs original : **HEAD vs cceb808f** (fix TP inclus). Aucun autre paramètre modifié.

---

## Tableau canonique

| Run | Ret% | PF | Sharpe | DD% | N | Win% | L_pnl | S_pnl | net |
|---|---|---|---|---|---|---|---|---|---|
| **2025 BUGGÉ** (cceb808f) | +45.95 | 1.82 | 3.13 | 6.19 | 191 | 46.6 | +22 898 | +21 248 | +44 145 |
| **2025 POST-FIX** (HEAD) | **+4.36** | **1.04** | **0.37** | **12.70** | 284 | 46.1 | +15 846 | **−12 310** | +3 536 |
| **2026 BUGGÉ** (cceb808f) | +27.09 | 2.22 | 4.62 | 3.10 | 77 | 50.6 | +1 488 | +18 686 | +20 175 |
| **2026 POST-FIX** (HEAD) | **+12.65** | **1.31** | **2.59** | **5.05** | 143 | 50.3 | +6 644 | +5 183 | +11 827 |

## Exits + TP distance

| Run | TP moyen | Exits TP | Exits trailing | L/S PnL |
|---|---|---|---|---|
| 2025 buggé | 23.1% | 22 | 168 | +22 898 / +21 248 |
| 2025 post-fix | 6.7% | 124 | 156 | +15 846 / −12 310 |
| 2026 buggé | 27.5% | 8 | 69 | +1 488 / +18 686 |
| 2026 post-fix | 6.9% | 70 | 73 | +6 644 / +5 183 |

---

## Verdict Étape A

1. **Le fix TP fonctionne** : le TP passe de ~23-27% (fallback buggé `max(12%, 2R)`) à ~7% (`min(3×ATR, 7%)` cap production respecté).
2. **Les sorties TP explosent** (2026 : 8 → 70 ; 2025 : 22 → 124) → rotation beaucoup plus rapide (N trades : 77→143, 191→284).
3. **Le short était gonflé par le bug** : en 2025 il passe de **+21 248 à −12 310** ; en 2026 de +18 686 à +5 183.
4. **La vraie baseline canonique post-fix est bien plus faible** que le benchmark gelé : **+4.36% (2025) / +12.65% (2026)** vs +45.95%/+27.09%.
5. Le +27.09% du benchmark OOS 2026 **était un artefact du TP fallback buggé** — confirmé quantitativement. La stratégie post-fix est **marginalement positive** (PF 1.04 / 1.31), le short 2025 structurellement perdant.

## ⚠️ Implications décisionnelles

- **Le benchmark OOS 2026 (+27.09%) est caduc** : la référence canonique est désormais **+12.65% (PF 1.31, DD 5.05%)** pour 2026.
- **Le doc go_live doit être ré-édité** (Étape D) : remplacer +27.09% par la baseline post-fix + statut time_stop.
- L'étape B (time_stop parity) doit se faire **sur cette nouvelle baseline**, pas sur l'ancienne.

## Fichiers
- Runs : `artifacts/backtesting/cmp_b25_h20_{2025,2026}_postfix_tp_m8/`
- Commandes log : `cmp_b25_h20_{2025,2026}_postfix_tp_m8.log`
- Scripts : `scripts/b25_rebench_compare.py`, `scripts/b25_rebench_table2.py`
