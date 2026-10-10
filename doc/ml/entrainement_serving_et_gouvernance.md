# Entraînement, serving et gouvernance ML

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

## Cycle de vie

```mermaid
flowchart LR
  D[Dataset PIT] --> T[Train / walk-forward]
  T --> A[Artefacts + métriques]
  A --> G[Challenger / champion]
  G --> P[Promotion]
  P --> S[Serving]
  S --> M[Monitoring, drift, couverture]
  M --> D
```

## Artefact complet

Un artefact exploitable associe modèle, schéma de features, configuration,
métriques, fenêtre d’entraînement, identité de campagne et contrôles de
compatibilité. Un fichier modèle isolé n’est pas un livrable gouverné.

## Serving

Le serving résout l’artefact, prépare les features selon le même contrat,
applique calibration/gates et persiste la prédiction avec provenance. Les
fallbacks et le `selection_mode` doivent rester visibles.

## Gouvernance

Champion et challengers sont des statuts de comparaison. La promotion doit
rapprocher ce registre avec les fichiers réellement chargés. L’IHM fournit un
audit serving↔gouvernance ; toute divergence doit être expliquée.

## Exploitabilité

Versionner manifests, garder rollback, vérifier couverture après déploiement et
surveiller drift par population. Une régression de couverture peut être plus
grave qu’une faible variation de métrique.

Voir [orchestration train/predict](orchestration_train_predict.md),
[validation](validation_et_gouvernance.md) et [recalibration](recalibration_et_promotion.md).

