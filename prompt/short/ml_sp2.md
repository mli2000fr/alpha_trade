# ML Sprint 2 — Synthèse

_Date : 2026-06-18_

## Objectif
Adapter le modèle, les métriques et le trainer au mode ternaire `{-1, 0, +1}`
(long, flat, short) pour supporter le ML directionnel.

## Livrables

### C1 — `modelFactory/model.py` : `LSTMAttentionModule` dual binaire/ternaire

| Changement | Détail |
|---|---|
| Imports | Ajout `MulticlassAccuracy`, `MulticlassF1Score` |
| `__init__` | Si `num_classes=3` : métriques multi-classes ; si `num_classes=2` : métriques binaires (inchangé) |
| Class weights | Pour ternaire : `[1.0, 1.5, 1.0]` (short, flat, long) pour compenser le déséquilibre |
| `_shared_step` | Ternaire : décale labels `{-1,0,1}` → `{0,1,2}` pour `CrossEntropyLoss`, retourne `preds` (argmax) |
| `training/val/test_step` | Conditionnel sur `num_classes` : log `f1` pour ternaire, `precision/recall/auc` pour binaire |

### C2 — `modelFactory/trainer.py` : `_gather_outputs` + `_compute_metrics`

| Fonction | Changement |
|---|---|
| `_gather_outputs` | Pour ternaire : `raw_proba` = matrice [N, 3] (toutes les probas), `margins` = zéros |
| `_compute_metrics` | Nouveau bloc ternaire : accuracy, F1 par classe (short/flat/long), distribution prédictions/labels |
| `_fit_calibrator` | Skip si `num_classes != 2` (Platt est binaire seulement) |

### Métriques ternaires produites

```json
{
  "loss": 0.85,
  "accuracy": 0.62,
  "f1_short": 0.45,
  "f1_flat": 0.70,
  "f1_long": 0.55,
  "pred_short_pct": 15.2,
  "pred_flat_pct": 55.0,
  "pred_long_pct": 29.8,
  "true_short_pct": 12.0,
  "true_flat_pct": 60.0,
  "true_long_pct": 28.0
}
```

## Rétrocompatibilité

- `num_classes=2` (défaut) : comportement binaire inchangé
- Tous les tests existants passent (48/48)
- `PlattCalibrator` skip automatique en mode ternaire

## Tests

```
48 passed in 4.33s (modelFactory + features)
```

Test manuel ternaire :
```
✅ Forward: logits shape (4, 3)
✅ _shared_step: loss=1.0787, preds OK, y_shifted OK
✅ Training step: loss=1.0787
```

## Prochain sprint

**ML Sprint 3** — Persistance et registre ML :
- `model_predictions` : ajouter `predicted_side`, `proba_long`, `proba_flat`, `proba_short`
- Consommateurs aval (`risk_management`, `backtesting`) : lire le nouveau schéma
