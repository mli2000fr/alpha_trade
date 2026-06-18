# Sprint 3 — Synthèse

_Date : 2026-06-18_

## Objectif
Rendre le pipeline d'exécution live direction-aware : les ordres d'entrée,
de protection (TP/SL/trailing) et le force-close consomment le `side`
canonique. Injection de l'Option C (short via MomentumRotationState) dans
le pipeline live.

## Livrables

### C1 — `order_intents.py` : entrées direction-aware

| Fonction | Changement |
|---|---|
| `build_entry_intents()` | Lit `side` depuis `ExecutionTarget.side` (défaut `"buy"`) |
| `build_entry_intents()` | `limit_price` directionnel : pour short, signe du buffer inversé → limite au-dessus du signal |
| `idempotency_key` / `submission_key` | Utilisent le `side` réel, plus `"buy"` hardcodé |

### C2 — `order_intents.py` : protections direction-aware

| Fonction | Changement |
|---|---|
| `build_take_profit_intent()` | TP directionnel via `compute_take_profit_price(side, ...)`, `exit_side="buy"` pour short |
| `build_initial_stop_intent()` | Stop directionnel via `resolve_initial_stop_price(..., side=)`, `exit_side="buy"` pour short |
| `build_trailing_stop_intent()` | Trailing directionnel, `exit_side="buy"` pour short |
| `resolve_initial_stop_price()` | Accepte `side`, stop > entry pour short |
| `resolve_trailing_activation_price()` | Accepte `side`, activation directionnelle |

### C3 — `executor.py` : force-close side-aware

| Point | Changement |
|---|---|
| Détection side | Lit `pos.side` depuis la position broker (`"long"` / `"sell"` / `"short"`) |
| Close side | Short → `"buy"` (buy-to-cover) ; Long → `"sell"` |
| Tri PnL | Utilise `abs(qty)` pour inclure les shorts |
| Log | `Force-close: liquidating X (side=Y) xZ -> buy/sell` |

### C4 — `risk_management/cli.py` : Option C live

| Point | Changement |
|---|---|
| Injection | Après `load_candidates_asof()`, avant `PortfolioBuilder.build()` |
| Déclencheur | `regime_snapshot.allowed_short_entries` OU `rotation_state.should_rotate()` |
| Tagging | Conversion candidats → DataFrame → `_tag_short_candidates()` → mise à jour `c.side` |
| Filtrage longs | Si `allowed_long_entries=False`, ne garde que les `side="sell"` |
| Log | `Option C live: date=X candidates=Y shorts=Z` |

### C5 — `execution_engine/models.py` (existant, vérifié)

| Modèle | Statut |
|---|---|
| `ExecutionTarget.side` | ✅ Déjà présent (Sprint 1) |
| `OrderIntent.side` | ✅ Déjà présent |
| `ProtectionWatchItem` | ⚠️ Pas de champ `side` (→ Sprint 5, migration DB) |

### C6 — `execution_engine/db_io.py` (existant, vérifié)

| Fonction | Statut |
|---|---|
| `load_portfolio_targets()` | ✅ Lit `side` depuis la DB |
| `write_portfolio_targets()` | ✅ Écrit `side` (Sprint 1) |

## Backtest ✅

Aucune régression : le simulateur (`backtesting/simulator.py`) est déjà direction-aware (Sprint 2).
Les 20 shorts exécutés dans le backtest `20260618_191636_84a7c7b3` confirment le pipeline complet.

## Live ✅

| Composant | Backtest | Live | Statut |
|---|---|---|---|
| `core/direction.py` | ✅ | ✅ | Commun |
| `PortfolioBuilder` (score/breakout) | ✅ | ✅ | Commun |
| Option C tagging | ✅ `risk_bridge.py` | ✅ `cli.py` | Injecté |
| Entry intents (`side`) | N/A (simulateur) | ✅ `order_intents.py` | Fait |
| TP/Stop/Trailing intents | N/A (simulateur) | ✅ `order_intents.py` | Fait |
| Force-close side-aware | ✅ `simulator.py` | ✅ `executor.py` | Fait |
| `limit_price_buffer` directionnel | N/A | ✅ `order_intents.py` | Fait |

## Points restants (Sprint 4-5)

| Point | Priorité |
|---|---|
| `ProtectionWatchItem.side` (DB migration) | Sprint 5 |
| `protection_watcher.py` — `_process_item` passer le side | Sprint 5 |
| `protection_transition.py` — passer le side | Sprint 5 |
| `children_submission.py` — passer le side | Sprint 5 |
| Watcher `time_stop` directionnel | Sprint 5 |
| Reporting PnL long/short séparé | Sprint 4 |

## Tests

```
75 passed in 0.84s (42 portfolio_builder + 30 regime_scoring + 33 order_intents)
```
