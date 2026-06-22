# ML Sprint 3 — Synthèse

_Date : 2026-06-18_

## Objectif
Étendre le schéma `model_predictions` pour stocker les prédictions ternaires
(`predicted_side`, `proba_long`, `proba_flat`, `proba_short`). Adapter les
consommateurs (backtest, risk) pour lire ces nouvelles colonnes.

## Livrables

### C1 — Schéma DB : `model_predictions`

| Colonne | Type | Description |
|---|---|---|
| `predicted_side` | `VARCHAR(10)` | `"long"`, `"flat"` ou `"short"` (mode ternaire) |
| `proba_long` | `DOUBLE` | Probabilité classe long |
| `proba_flat` | `DOUBLE` | Probabilité classe flat |
| `proba_short` | `DOUBLE` | Probabilité classe short |

Colonnes existantes (`predicted_proba`, `predicted_class`) inchangées pour la rétrocompatibilité binaire.

### C2 — Migration Alembic

Fichier : `alembic/versions/0038_add_model_predictions_ternary.py`

- `upgrade()` : ajoute les 4 colonnes + index `idx_predicted_side`
- `downgrade()` : supprime les colonnes et l'index
- Idempotent : vérifie `_has_column` avant chaque opération

### C3 — `database/sql/ml/model_predictions.sql`

CREATE TABLE mis à jour avec les 4 nouvelles colonnes (DEFAULT NULL).

### C4 — `modelFactory/db_registry.py`

| Changement | Détail |
|---|---|
| `_PREDICTION_TERNARY_COLUMNS` | Nouveau set : `{predicted_side, proba_long, proba_flat, proba_short}` |
| `insert_predictions_v2` | Détecte si les colonnes ternaires sont présentes → utilise le SQL étendu |
| Params INSERT | Inclut `:ps, :pl, :pf, :psh` si mode ternaire |
| `_validate_predictions_frame` | Inchangeé (colonnes ternaires optionnelles) |

### C5 — Modèles

| Fichier | Changement |
|---|---|
| `risk_management/models.py` | `PredictionInfo` +4 champs optionnels : `predicted_side`, `proba_long`, `proba_flat`, `proba_short` |

### C6 — Consommateurs backtest

| Fichier | Changement |
|---|---|
| `backtesting/data_loader.py` | `load_predictions()` : SELECT des 4 nouvelles colonnes via `_optional_select` |
| `backtesting/risk_bridge.py` | `_build_predictions()` : lit les colonnes ternaires depuis le DataFrame |

## Rétrocompatibilité

- **Mode binaire** : `predicted_side=NULL`, `proba_* = NULL` → les consommateurs existants ignorent ces champs
- **Mode ternaire** : `predicted_side` est rempli, `predicted_proba` reste la proba classe 1 (long) pour compatibilité
- Tous les appels existants fonctionnent sans modification

## Tests

```
123 passed in 4.79s (48 ML + 75 trading)
```

## Prochain sprint

**ML Sprint 4** — Ranking, conviction et risk management bilatéraux :
- `selector/ranking.py` : produire deux shortlists (long et short)
- `CAPITAL_PRESERVATION_WEIGHTS` décliné long/short
- Trackers de concentration déjà side-aware (Sprint 5 trading)
- `core/conviction.py` : conviction directionnelle
