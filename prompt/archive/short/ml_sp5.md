# ML Sprint 5 — Synthèse

_Date : 2026-06-18_

## Objectif
Compléter les diagnostics backtest avec le split force-close par side
(long vs short). La majorité des fonctionnalités directionnelles étaient
déjà implémentées dans les Sprints 2-3 trading.

## Ce qui était déjà fait (Sprints 2-3 trading)

| Fonctionnalité | Fait dans | Statut |
|---|---|---|
| `DrawdownCircuitBreaker.allocation_scale(side)` | Sprint 2 | ✅ |
| Force-close side-aware (simulateur) | Sprint 2 | ✅ |
| Force-close side-aware (executor live) | Sprint 3 | ✅ |
| Time stop directionnel | Sprint 2 | ✅ |
| Pullback entry inversé shorts | Sprint 2 | ✅ |
| Trackers concentration side-aware | Sprint 5 trading | ✅ |

## Livrables Sprint 5 ML

### C1 — `BacktestDiagnostics` : force-close par side

| Champ | Description |
|---|---|
| `force_close_exits_long` | Sorties force-close de positions longues |
| `force_close_exits_short` | Sorties force-close de positions short |

### C2 — `simulator.py` : comptage par side

Le bloc force-close incrémente désormais le compteur approprié selon `pos_side`.

### C3 — `BacktestReport` : affichage split

| Champ | Source |
|---|---|
| `force_close_exits_long` | `trades_df` filtré `exit_reason=force_close_breaker & side=buy` |
| `force_close_exits_short` | `trades_df` filtré `exit_reason=force_close_breaker & side=sell` |

### C4 — Affichage console

```
Force-close (total)     10
Force-close Long         7
Force-close Short        3
```

## Backtest ✅

| Fichier | Changement |
|---|---|
| `backtesting/simulator.py` | `BacktestDiagnostics` +2 champs, comptage par side |
| `backtesting/report.py` | `BacktestReport` +2 champs, split dans `generate_report` |

## Live ✅

Les diagnostics live sont gérés par `executor.py` (force-close side-aware déjà fait Sprint 3).

## Tests

```
115 passed, 2 warnings
```

## Prochain sprint

**ML Sprint 6** — Exécution live / paper (déjà fait dans Sprint 3 trading).

**ML Sprint 7** — Gouvernance et monitoring.
