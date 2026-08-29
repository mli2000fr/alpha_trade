# 3 — Entraînement, walk-forward et champions

## LSTM

Le réseau utilise hidden size, couches, dropout, learning rate et weight decay
configurés. Lightning surveille `val_loss`, conserve un seul meilleur checkpoint
et applique une patience. Le meilleur checkpoint est rechargé pour calculer
métriques val/test, calibration et seuil.

## Walk-forward

Les splits utilisent `min_train_size`, `val_size`, `test_size`, `step_size` et
`max_splits`. Chaque split reçoit une seed dérivée. Les prédictions WF peuvent
être sauvegardées pour audit. La synthèse agrège les folds sans autoriser le
holdout final à choisir le champion.

## Tabulaires

`run_tabular_baseline` entraîne LightGBM et CatBoost sur le DataFrame préparé ;
`run_tabular_walk_forward` applique le protocole temporel. Calibration et
politique ternaire sont partagées avec l’inférence via les artefacts.

## Sélection champion

`selection_score_from_result` privilégie le F1 macro walk-forward, puis F1 val,
puis AUC val. Les métriques test/final holdout sont interdites pour la sélection.
Les gates rejettent notamment probabilités invalides, AUC hors bornes, collapse,
action rate nul en ternaire, métriques legacy et artefacts/routes incomplets.

La quarantaine optionnelle exige un nombre de runs et/ou de jours avant qu’un
nouveau modèle soit éligible. Si l’auto-sélection est désactivée ou si aucun
challenger n’est admissible, le champion par défaut et les fallbacks gouvernés
s’appliquent. Le rapport conserve raison, mode, score et ranking des challengers.

