# Calibrations de poids et Diagnostic ML

## Calibrations

La page filtre les runs par scope, régime, horizon, fenêtre et statut de promotion live. Le détail expose meilleurs poids, candidats, historique et drifts inter-segments. Une calibration terminée n’est pas automatiquement éligible.

Promouvoir ou bloquer modifie l’état en base. Avant promotion : vérifier période/OOS, objectif, scope, régime, stabilité, provenance, fingerprint et fallback consommateur. Conserver reviewer et justification. Une amélioration moyenne instable entre segments ne suffit pas.

## Diagnostic ML

Cette page très large inspecte batches, symboles, splits walk-forward, régimes, distributions true/pred, Oracle Extreme, modèle global, per-symbol/per-sector et historique des rangs. Elle peut générer/lancer des backtests exploratoires, calculer des labels Oracle et supprimer des batches/artefacts.

Pour un batch ternaire per-symbol, elle peut également préparer et télécharger
trois listes exclusives de candidats stables : LONG uniquement, SHORT uniquement
et LONG+SHORT. Le contrat détaillé des supports, folds et seuils F1 est documenté
dans [Sélection des candidats directionnels](../ml/per_symbol/06_selection_candidats_directionnels.md).

Le diagnostic ne change pas le modèle servi tant qu’une promotion explicite n’a pas lieu. Toujours identifier batch id, horizon, source symboles, dates training/univers et champion. Les mini-backtests et commandes générées doivent être relus avec leur contrat d’exécution.

Les suppressions sont irréversibles sans sauvegarde. Vérifier que le batch n’est ni servi, ni requis comme fallback/rollback, puis archiver rapports et manifests. Les métriques Oracle sont OOS seulement si les lignes et splits affichés le garantissent.

Références : [ML](../ml/README.md), [Global Ranking](../ml/global_ranking/README.md), [Oracle](../ml/oracle/README.md), [per-symbol](../ml/per_symbol/README.md) et [per-sector](../ml/per_sector/README.md).

