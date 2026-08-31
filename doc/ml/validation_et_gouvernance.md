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

## Unité d’évaluation

Une métrique agrégée ligne par ligne peut surpondérer les dates riches en symboles. Pour un modèle cross-sectionnel, calculer d’abord IC, quantiles et spreads par date, puis résumer leur distribution. Pour un modèle directionnel, publier aussi couverture, confusion par classe, calibration et métriques par semestre/régime.

Chaque résultat doit préciser population : univers PIT, symbols exclus, dates, horizon, côté, coûts et règle d’abstention. « Accuracy 60 % » sans ces éléments n’est pas une preuve exploitable.

## Gates de promotion

Un gate documenté distingue :

- intégrité : artefacts, features et lineage complets ;
- causalité : folds chronologiques, embargo/purge si nécessaire ;
- qualité : métrique primaire et stabilité ;
- calibration : probabilités utilisables si consommées comme telles ;
- capacité : couverture et turnover compatibles ;
- risque : pertes extrêmes, concentration et sous-périodes ;
- exploitation : latence, mémoire, dépendances, rollback disponible.

Une règle de promotion est fixée avant lecture du holdout. Les exceptions sont conservées avec justification ; elles ne réécrivent pas le seuil a posteriori.

## Drift et rollback

Le drift peut toucher features, prédictions, couverture ou performance. Identifier source/univers avant de conclure à un drift modèle. Selon la politique : warning, shadow, abstention, rollback vers champion antérieur ou blocage. Le rollback conserve l'audit et ne supprime pas le batch défectueux.

`modelFactory/drift_policy.py` produit une `MLPolicyDecision`, peut appliquer un kill-switch et persister l’événement. Côté risque, `ml_gate.py` lit les derniers payloads `drift_policy_decision` dans `ml_drift_runs`. Toute modification de cette structure JSON doit être versionnée ou rester rétrocompatible.

Le drift de données est vérifié avant le drift de performance : changement provider, couverture, correction de split ou univers peuvent déplacer les distributions sans dégradation intrinsèque du modèle. La performance réalisée arrive avec retard et ne doit pas être mélangée aux proxy immédiats.

## Essais multiples

Compter toutes les variantes, seeds, horizons et whitelists inspectés. Utiliser correction multiple/deflated metrics dans la validation backtest. Une amélioration choisie après dizaines d'essais exige un holdout non consulté.

## Rapport minimal d’un entraînement

Le rapport autonome contient batch/run ids, commit et état dirty, config fingerprint, plage de données, folds, univers, convention de prix, feature hash, target, seeds, versions, métriques par fold, agrégats robustes, calibration, coverage, diagnostics par période/régime/secteur, artefacts produits et décision de gouvernance.

## Reproductibilité et non-déterminisme

Fixer Python/NumPy/estimators et dériver les seeds par horizon/fold. Certains algorithmes, threads et GPU restent non déterministes ; documenter la tolérance et mesurer la dispersion multi-seed. La reproductibilité signifie reconstruire le protocole et expliquer les écarts, pas exiger un binaire identique dans tous les environnements.

## Checklist avant promotion

1. Batch immuable et dataset reconstructible.
2. Aucun chevauchement train/test causal.
3. Holdout non utilisé pour sélectionner.
4. Baseline battue sur métrique primaire préfixée.
5. Stabilité par fold et sous-période acceptable.
6. Calibration/couverture cohérentes avec le consumer.
7. Lifecycle backtest identique au contrat PROD si PnL évalué.
8. Artefacts, registry et governance complets.
9. Shadow/replay et rollback testés.
10. Champion précédent conservé.
