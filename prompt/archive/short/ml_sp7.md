# ML Sprint 7 — Synthèse

_Date : 2026-06-18_

## Objectif
Étendre les tables de gouvernance ML pour supporter le mode ternaire
(long/flat/short) : stocker le `num_classes`, les F1 par classe, et
adapter `insert_metrics` pour persister ces métriques.

## Livrables

### C1 — `model_governance` : nouvelles colonnes

| Colonne | Type | Description |
|---|---|---|
| `num_classes` | `TINYINT` | 2 = binaire, 3 = ternaire |
| `val_f1_macro` | `DOUBLE` | F1 macro validation (ternaire) |
| `test_f1_macro` | `DOUBLE` | F1 macro test (ternaire) |

### C2 — `model_metrics` : F1 par classe

| Colonne | Description |
|---|---|
| `f1_macro` | F1 macro (moyenne short/flat/long) |
| `f1_short` | F1 classe short |
| `f1_flat` | F1 classe flat |
| `f1_long` | F1 classe long |

### C3 — Alembic `0039_add_model_metrics_ternary.py`

- `upgrade()` : ajoute les colonnes aux deux tables
- `downgrade()` : supprime les colonnes
- Idempotent

### C4 — `modelFactory/db_registry.py` : `insert_metrics`

Détecte si les métriques ternaires (`f1_macro`, `f1_short`, ...) sont présentes
dans le dict → utilise le SQL étendu avec les 4 colonnes F1.

### C5 — SQL create tables

- `database/sql/ml/model_governance.sql` : +3 colonnes
- `database/sql/ml/model_metrics.sql` : +4 colonnes

## Rétrocompatibilité

Toutes les nouvelles colonnes sont `DEFAULT NULL`. Les modèles binaires
continuent de fonctionner sans changement.

## Tests

```
52 passed, 2 warnings
```

## Bilan final — Plan ML v2

| Sprint | Objet | Statut |
|---|---|---|
| Sprint 1 | Target ternaire | ✅ `build_target(mode="ternary")` |
| Sprint 2 | Modèle 3 classes | ✅ `LSTMAttentionModule(num_classes=3)` |
| Sprint 3 | Persistance | ✅ `model_predictions` +4 colonnes |
| Sprint 4 | Ranking + conviction | ✅ `min_score_threshold_short` + `compute_conviction_short` |
| Sprint 5 | Backtest directionnel | ✅ `force_close_exits_long/short` |
| Sprint 6 | Exécution live | ✅ ML priority dans `_tag_short_candidates` |
| Sprint 7 | Gouvernance | ✅ `model_governance` + `model_metrics` ternaires |
