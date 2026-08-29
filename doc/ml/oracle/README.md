# Oracle Extreme — dossier technique complet

Ce dossier décrit la couche Oracle telle qu’elle existe dans le code actuel. Il remplace la fonction documentaire de l’ancien `doc/ml_oracle.md` sans recopier ses journaux d’expériences.

## Parcours

1. [Concept, sémantique et architecture](01_concept_et_architecture.md)
2. [Labels, univers et tables](02_labels_univers_et_tables.md)
3. [Dataset, features, ablations et anti-fuite](03_dataset_features_et_leakage.md)
4. [Entraînement, walk-forward, calibration et métriques](04_train_walk_forward_et_calibration.md)
5. [Prédiction, persistance et gate quotidien](05_inference_persistance_et_gate.md)
6. [Diagnostics, expériences et statut actuel](06_diagnostics_et_historique.md)

## Résumé du contrat actuel

Oracle Extreme estime `P(mouvement cross-sectionnel extrême à H20 | information disponible à D)`. La cible positive réunit le TOP 10 % et le BOTTOM 10 % des rendements futurs du jour. Le modèle mesure donc une magnitude/opportunité extrême, pas une direction.

```mermaid
flowchart LR
  U[Univers date D] --> L[Labels futurs H20]
  F[Features PIT à D] --> O[Oracle Extreme O0]
  L --> O
  O --> P[proba_extreme]
  P --> X[Percentile intra-date]
  X --> G[Extreme gate]
  G --> R[Contrat directionnel séparé]
```

La direction long/short doit venir d’une autre couche. Interpréter `proba_extreme` comme `P(long)` est une erreur de contrat.

## Sources de vérité

- `modelFactory/oracle/` pour les labels, datasets, modèles et diagnostics ;
- `database/sql/ml/global_oracle_labels.sql` et `database/sql/oracle/oracle_extreme_predictions.sql` ;
- migrations Alembic 0064–0065 et suivantes pertinentes ;
- `config.yaml/oracle` et `batch_diagnostics.backtest_batch_id` ;
- tests Oracle sous `tests/`.

Retour : [références ML](../README.md) · [vue Oracle](../../08_ml_oracle_extreme.md)

