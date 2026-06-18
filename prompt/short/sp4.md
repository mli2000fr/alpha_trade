# Sprint 4 — Synthèse

_Date : 2026-06-18_

## Objectif
Ajouter les métriques directionnelles (long/short) et force-close dans les
rapports de backtest. Le pipeline live est déjà couvert côté données (les
colonnes `side` sont persistées en DB), l'affichage IHM est un travail frontend.

## Livrables

### C1 — `BacktestReport` : métriques long/short

| Champ | Type | Description |
|---|---|---|
| `long_trades` | `int` | Nombre de trades longs |
| `short_trades` | `int` | Nombre de trades shorts |
| `long_win_rate_pct` | `float` | Win rate des longs |
| `short_win_rate_pct` | `float` | Win rate des shorts |
| `long_pnl_total` | `float` | PnL total des longs ($) |
| `short_pnl_total` | `float` | PnL total des shorts ($) |
| `force_close_exits` | `int` | Nombre de sorties force-close |

### C2 — `generate_report()` : calcul des splits

```python
if "side" in trades_df.columns:
    long_mask = trades_df["side"] == "buy"
    short_mask = trades_df["side"] == "sell"
    long_trades = int(long_mask.sum())
    short_trades = int(short_mask.sum())
    # ...
if "exit_reason" in trades_df.columns:
    force_close_exits = int((trades_df["exit_reason"] == "force_close_breaker").sum())
```

### C3 — `report_schema.SummarySchema` : nouveaux champs

Ajout des 7 champs directionnels avec défauts `0` (rétrocompatibilité).

### C4 — Affichage console

```
Trades Long    367 (WR: 38.1%, PnL: $1,234.56)
Trades Short    20 (WR: 0.0%, PnL: $-543.21)
Force-close exits  10
```

### C5 — `report.json`

Les champs sont automatiquement inclus via `to_serializable_dict()`.

## Backtest ✅

| Fichier | Changement |
|---|---|
| `backtesting/report.py` | `BacktestReport` +7 champs, `to_dict()` / `to_serializable_dict()` / `generate_report()` |
| `backtesting/report_schema.py` | `SummarySchema` +7 champs |

## Live ✅

Le pipeline live persiste déjà `side` dans :
- `risk_decisions.side` → DB (Sprint 1)
- `portfolio_targets.side` → DB (Sprint 1)
- `trades.side` → CSV + DB (Sprint 2)

L'IHM peut consommer ces données pour afficher le split long/short sans
modification du backend Python. Le travail IHM (frontend) est hors scope
de ce sprint.

## Points restants (Sprint 5)

| Point | Priorité |
|---|---|
| `ProtectionWatchItem.side` (DB migration) | Sprint 5 |
| `protection_watcher.py` — passer le `side` aux `resolve_*` | Sprint 5 |
| Tests de non-régression long/short | Sprint 5 |
| Tests force-close portefeuille mixte | Sprint 5 |
| Option B — short_score dédié (trend_score, RSI, SMA) | Sprint 5 |

## Tests

```
75 passed in 0.95s
```
