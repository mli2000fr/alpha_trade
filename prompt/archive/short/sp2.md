# Sprint 2 — Synthèse

_Date : 2026-06-18_

## Objectif
Rendre le moteur de backtest bidirectionnel : toutes les boucles de simulation
(entrée, sortie, mark-to-market, force-close, PnL) sont direction-aware via
`core/direction.py`. Valeur par défaut : `side="buy"` → comportement long-only
inchangé.

## Livrables

### C1 — `_OpenPosition` direction-aware
| Fichier | Changement |
|---|---|
| `backtesting/simulator.py` | `side: str = "buy"` ajouté au dataclass |
| `backtesting/simulator.py` | `trough_low: float` ajouté (trailing short) |

### C2 — Mark-to-market bidirectionnel
| Méthode | Changement |
|---|---|
| `_mark_to_market()` | Utilise `direction_sign(side)` → valeur nette signée (+long, -short) |
| `_compute_gross_notional()` | NOUVEAU — `sum(abs(qty) * px)` toujours ≥ 0 |
| Lignes 794, 1032 | `current_gross_notional` utilise `_compute_gross_notional()` |

### C3 — Entrées direction-aware
| Point d'entrée | Changement |
|---|---|
| `_try_open_entries` | Lecture `side` depuis le signal row |
| Pullback entry | Utilise `compute_pullback_limit_price(side, ...)` |
| Cash entry | Short → crédit cash ; Long → débit cash |
| `_resolve_initial_protection_state` | Accepte `side`, stop directionnel (short : stop > entry) |
| Création position | `side=side`, `trough_low=entry_price` |
| Event `entry_opened` | Inclut `side=side` |

### C4 — Sorties direction-aware
| Point de sortie | Changement |
|---|---|
| `_try_close_positions` | `side` lu depuis `position.side` |
| `peak_high` / `trough_low` | Mise à jour directionnelle (peak pour long, trough pour short) |
| Take-profit | `compute_take_profit_price(side, entry_price, tp_pct)` |
| Trailing stop | `compute_trailing_stop_price(side, ref, pct)` avec ref = trough_low pour short |
| Time stop | `objective_move` et `current_move` directionnels |
| PnL | `compute_realized_pnl(side, qty, entry, exit)` |
| Return % | `compute_return_pct(side, entry, exit)` |
| Cash settlement | Short → débit cash (buy-to-cover) ; Long → crédit cash |
| `closed_trades` | Inclut `"side": side` |
| Event `exit_closed` | Inclut `side=side` |

### C5 — Force-close direction-aware
| Fichier | Changement |
|---|---|
| `backtesting/simulator.py` (lignes 723-767) | PnL via `compute_realized_pnl`, return via `compute_return_pct` |
| Cash settlement | Short → débit ; Long → crédit |
| Trade record | Inclut `"side": pos_side` |

### C6 — DrawdownCircuitBreaker
| Fichier | Changement |
|---|---|
| `backtesting/risk_overlay.py` | `allocation_scale(side=None)` — paramètre réservé, comportement inchangé |

### C7 — Import module-level
| Fichier | Import |
|---|---|
| `backtesting/simulator.py` | `from core.direction import (compute_gross_notional, compute_pullback_limit_price, compute_realized_pnl, compute_return_pct, compute_take_profit_price, compute_trailing_stop_price, is_short_side)` |

### Bugfix — `execution_engine/executor.py`
| Problème | Correction |
|---|---|
| `SyntaxError: expected 'except' or 'finally' block` (ligne 272) | Indentation du bloc `# Force-close` corrigée (était au niveau `try:` au lieu du corps du `try:`) |

## Backtest ✅
- `short_selling_enabled: false` → tous les `side` sont `"buy"`
- Toutes les fonctions `core/direction` retournent les mêmes valeurs que les formules long-only originales
- Tests 42/42 passent sans modification
- Import `BacktestEngine` OK

## Live ✅
- Le `DrawdownCircuitBreaker.allocation_scale()` accepte `side` (optionnel, rétrocompatible)
- L'`executor.py` a été corrigé (bug de syntaxe préexistant)
- Aucun changement de comportement live (tous les side = "buy")

## Prochain sprint
**Sprint 3 — Exécution live direction-aware**
- `executor.py` : consommer `side` pour les ordres d'entrée (buy vs sell short)
- `executor.py` : force-close side-aware (buy-to-cover pour shorts)
- `execution_engine/config.py` : `limit_price_buffer_bps` directionnel
- Protection watcher directionnel (TP/TS selon side)

---

## Annexe — Option C : Short via MomentumRotationState

### Injection
| Fichier | Changement |
|---|---|
| `backtesting/risk_bridge.py` | `_tag_short_candidates()` — helper qui flip bottom-N en `side="sell"` |
| `backtesting/risk_bridge.py` | `_build_candidates_from_day()` — lit `side` depuis le DataFrame |
| `backtesting/risk_bridge.py` | `build_phase2_risk_result()` — injection après rotation check |
| `risk_management/config.py` | Champs `short_selling_enabled`, `short_max_positions`, `short_min_score`, etc. |
| `config.yaml` | Section `short_*` avec valeurs par défaut |

### Fonctionnement
1. `MomentumRotationState` accumule les returns quotidiens de l'equity
2. Quand `should_rotate()` = True (cumul < -3% sur 4 semaines) ET `short_selling_enabled` = True
3. `_tag_short_candidates()` trie les candidats par score ascendant
4. Les N pires scores (sous `short_min_score`) reçoivent `side="sell"`
5. Les autres restent `side="buy"`
6. Le `side` est propagé via `CandidateScore` → `PortfolioBuilder` → signaux → simulateur

### Test de validation
```bash
# 1. Activer le short dans config.yaml
#    short_selling_enabled: true

# 2. Lancer un backtest sur 2022 (année baissière)
python -m backtesting run --preset micro_capital --start 2022-01-01 --end 2022-12-31

# 3. Vérifier dans les diagnostics :
#    - rotation_state.should_rotate() doit être True pendant les drawdowns
#    - Des candidats avec side="sell" doivent apparaître dans les signaux
#    - Les trades shorts doivent avoir un PnL positif si le prix baisse
#    - Le return_pct des shorts doit utiliser la formule directionnelle
```
