# ML Sprint 1 — Synthèse

_Date : 2026-06-18_

## Objectif
Ajouter le mode `ternary` à `build_target()` pour produire des labels directionnels
`{-1, 0, +1}` (short, flat, long) au lieu des seuls labels binaires existants.

## Livrables

### C1 — `modelFactory/config.py` : `DataConfig`

| Changement | Détail |
|---|---|
| `target_mode` | Accepte `"ternary"` en plus de `"binary"` et `"swing_cash"` |
| Validation | `__post_init__` vérifie `target_mode in {"binary", "swing_cash", "ternary"}` |

### C2 — `modelFactory/features.py` : `build_target()`

Ajout du mode `ternary` :

```python
if mode == "ternary":
    target = pd.Series(0, index=df.index, dtype=int)
    target = target.mask(future_return > positive_threshold, 1)   # long
    target = target.mask(future_return < negative_threshold, -1)  # short
    return target.where(future_return.notna())
```

| future_return | Label | Signification |
|---|---|---|
| `> positive_threshold` | `+1` | Cible long (ex: +12%, TP atteignable) |
| `< negative_threshold` | `-1` | Cible short (ex: -8%, baisse suffisante) |
| entre les deux | `0` | Flat (pas de signal) |
| NaN (queue) | `NaN` | Hors horizon (dernières N lignes) |

### Seuils recommandés

| Paramètre | Valeur | Justification |
|---|---|---|
| `target_up_threshold` | `0.12` | Aligné avec TP long (12%) |
| `target_down_threshold` | `-0.08` | Aligné avec TP short (8%) |
| `forecast_horizon` | `5` | 5 jours ouvrés (1 semaine) |

## Rétrocompatibilité

Les modes `binary` et `swing_cash` sont inchangés. Tous les appels existants
continuent de fonctionner sans modification.

## Tests

```
48 passed in 4.35s (modelFactory + features)
```

Test manuel du mode ternaire :

```
ternary target (+12%/-8%, horizon=1):
  row0: +15% > +12% → +1 ✅
  row1: -21.7% < -8% → -1 ✅
  row2: +11.1% → flat → 0  ✅
  row3: 0% → flat → 0      ✅
  row4: NaN                ✅
```

## Prochain sprint

**ML Sprint 2** — Modèle 3 classes + calibration :
- Adapter `LSTMAttentionClassifier(num_classes=3)` existant
- Métriques multi-classes (Accuracy, F1 macro)
- `PlattCalibrator` multi-classe
- `trainer.py` : supporter `target_mode='ternary'`
