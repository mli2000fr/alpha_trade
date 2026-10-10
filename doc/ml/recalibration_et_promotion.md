# Recalibration, sélection et promotion des modèles

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

## Séparer quatre opérations

1. réentraîner produit de nouveaux artefacts ;
2. recalibrer ajuste seuils, poids ou transformation des sorties ;
3. sélectionner compare challengers et référence selon un protocole ;
4. promouvoir modifie ce qui est servi.

Une opération réussie n’autorise pas automatiquement la suivante.

## Déclencheurs légitimes

Calendrier défini, dérive persistante, dégradation OOS, évolution de schéma ou
nouvelle profondeur de données. Une mauvaise journée ou un semestre isolé ne
suffit pas sans diagnostic de régime et de stabilité.

## Protocole

- figer baseline, période et métriques ;
- construire les features exclusivement disponibles à la date ;
- utiliser splits temporels/walk-forward ;
- comparer couverture et stabilité, pas seulement moyenne ;
- tester coûts et impact portefeuille ;
- enregistrer configuration, code, données/batch et seeds ;
- appliquer les gates d’acceptation préfixées.

## Promotion

La promotion doit être atomique du point de vue de l’opérateur : manifeste
valide, artefacts présents, champion enregistré, serving cohérent et audit
possible. Préparer le rollback vers l’artefact précédent. Après promotion,
vérifier un échantillon de prédictions, la couverture et l’audit
serving↔gouvernance.

## Poids et calibrations

Les calibrations sentiment/conviction possèdent des runs dédiés et des variantes
walk-forward. Le meilleur poids in-sample reste un candidat. Conserver fenêtre,
population, objectif, tables, timeline et décision de promotion.

## Critères de rejet

Rejeter ou différer si gain dépendant d’une période, couverture réduite,
instabilité par seed/split, fuite temporelle, changement de contrat non isolé,
artefact non reproductible ou rollback impossible.

Voir [validation et gouvernance](validation_et_gouvernance.md),
[expériences de validation](../experiences/validation_et_recalibration.md) et
[Backtesting](../guide_utilisateur/08_backtesting.md).

