# Walk-forward, calibration et gouvernance ML

Retour : [références ML](README.md)

## Séparation des usages

Train ajuste les poids ; validation choisit modèle/seuil/calibration ; test OOS estime la performance finale. Réutiliser le test pour sélectionner un horizon le transforme en validation. Les folds walk-forward répètent ce principe chronologiquement.

## Reproductibilité

Archiver seed racine et seeds dérivés, commit/dirty state, versions, commande, config effective, dates, univers/fingerprint, liste ordonnée des features et hash des données. Une seed identique ne compense pas une base backfillée différemment.

## Calibration

Mesurer reliability par bins, Brier/log loss et calibration par période. Apprendre isotonic/Platt uniquement sur validation. Vérifier que la calibration ne détruit pas le rang. Pour ranking, la calibration de probabilité n'est pas l'objectif ; analyser IC/quantiles.

## Champion

La sélection doit comparer baselines et challengers sur métrique primaire, dispersion des folds, classes/couverture et contraintes opérationnelles. La registry conserve états et transitions. Une promotion requiert artefacts complets et contrat compatible ; un batch incomplet reste non promouvable.

## Drift et rollback

Le drift peut toucher features, prédictions, couverture ou performance. Identifier source/univers avant de conclure à un drift modèle. Selon la politique : warning, shadow, abstention, rollback vers champion antérieur ou blocage. Le rollback conserve l'audit et ne supprime pas le batch défectueux.

## Essais multiples

Compter toutes les variantes, seeds, horizons et whitelists inspectés. Utiliser correction multiple/deflated metrics dans la validation backtest. Une amélioration choisie après dizaines d'essais exige un holdout non consulté.

