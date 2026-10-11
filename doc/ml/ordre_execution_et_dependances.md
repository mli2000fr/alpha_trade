# Ordre d’exécution ML et dépendances

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

## Chaîne logique

```text
univers et données PIT
 → sanitation/qualité
 → features et labels
 → entraînement + validation
 → manifests/artefacts
 → gouvernance/promotion
 → prédiction
 → ranking/screener
 → risque puis exécution
```

Le pipeline quotidien peut regrouper ou optionnaliser certaines étapes, mais ne
supprime pas les dépendances causales.

## Entraînement vs prédiction

L’entraînement écrit une campagne et ses artefacts. La prédiction doit cibler
une campagne compatible et peut être quotidienne ou historique pour backtest.
Ne pas entraîner implicitement pendant un replay destiné à mesurer un modèle
gelé.

## Batches et dates

Conserver `batch_id`, horizon, date de prédiction et date de disponibilité. Le
Global Ranking et Oracle peuvent utiliser des batchs distincts. Une campagne
historique choisie dans l’IHM ne devient pas la campagne de production.

## Reprises

Une reprise ciblée doit vérifier quelles écritures sont idempotentes et quels
artefacts partiels existent. Après erreur, contrôler manifests, métriques,
prédictions et registre avant de relancer l’étape aval.

Voir [pipeline](../04_pipeline_quotidien.md), [orchestration](orchestration_train_predict.md)
et [guide Pipeline](../guide_utilisateur/03_pipeline.md).
