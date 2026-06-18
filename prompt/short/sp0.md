# Sprint 0 — Synthèse

_Date : 2026-06-18_

## Objectif
Fixer la représentation canonique du short avant d'éditer les moteurs.

## Livrables

### C4 — `core/direction.py`
Module central de 18 helpers directionnels, zéro dépendance externe.

```
core/direction.py
├── Prédicats : is_short_side, is_long_side, is_valid_side, normalize_side
├── Direction : direction_sign, closing_side
├── Protections : compute_take_profit_price, compute_initial_stop_price,
│                compute_trailing_stop_price, compute_trailing_activation_price
├── Entrée     : compute_pullback_limit_price
├── PnL        : compute_realized_pnl, compute_unrealized_pnl, compute_return_pct
└── Exposition : compute_gross_notional, compute_net_notional,
                 compute_gross_exposure_pct, compute_net_exposure_pct
```

### C8 — Feature flag `short_selling_enabled`
Ajouté dans `config.yaml` → `risk_management.short_selling_enabled: false`

### C7 — Direction-aware `MarketRegimeSnapshot`
- `allowed_long_entries: bool = True`
- `allowed_short_entries: bool = False`
- `blocks_entry_for()` accepte un paramètre `side`
- `to_summary_dict()` exporte les nouveaux champs
- `build_snapshot()` définit la matrice :
  - `normal` : long ✅, short ❌
  - `capital_preservation` : long ❌, short ✅
  - `close_only` / `cash_only` : ni long ni short

### Tests
✅ 42/42 existants passent
✅ `core/direction.py` validé manuellement (PnL long/short, TP, SL, pullback, exposition)

## Fichiers modifiés
- `core/direction.py` (créé)
- `config.yaml` (ajout `short_selling_enabled`)
- `service/market/models.py` (ajout `allowed_long_entries`, `allowed_short_entries`, `blocks_entry_for(side)`)
- `service/market/regime_manager.py` (matrice directionnelle dans `build_snapshot`)
