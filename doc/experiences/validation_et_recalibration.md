# Expériences de validation, calibration et recalibration

Retour : [gouvernance ML](../ml/validation_et_gouvernance.md)

## Sources regroupées

`alpha_trade_anti_overfitting_oos_protocol_2026-08-22.md`, `alpha_trade_recalibration_guide.md`, `ml_calivraiton_important.md`, les checks de performance et plusieurs audits de batches.

## Enseignements

- séparer train, sélection/validation et holdout final ;
- compter toutes les variantes consultées ;
- figer universe, target, folds, coûts et lifecycle ;
- recalibrer après changement matériel de modèle/univers/distribution ;
- apprendre la calibration uniquement hors fold évalué ;
- vérifier rang et économie après calibration ;
- conserver champion précédent et procédure de rollback ;
- ne pas promouvoir sur une métrique unique.

## Recalibration

Une recalibration est justifiée par changement de base rate, dérive de reliability, changement d’univers ou nouveau modèle. Elle n’est pas un moyen de réparer a posteriori un holdout décevant. Le nouvel objet calibré porte batch, fenêtre, méthode, métriques avant/après et fingerprint.

## Relation au code

Les mécanismes actuels de calibration, drift policy, registry, governance et rollback sont décrits dans les guides ML. Les valeurs et plans datés des archives ne sont pas repris comme procédure automatique.

