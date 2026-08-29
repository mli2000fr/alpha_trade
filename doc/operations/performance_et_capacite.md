# Performance, capacité et quotas

## Axes de capacité

CPU et mémoire pour features/ML, connexions et écritures DB, latence broker,
quota fournisseur, volume d’artefacts et concurrence de workers. Optimiser un
axe peut déplacer le goulot.

## Mesure

Mesurer durée par étape, débit lignes/symboles, mémoire, appels fournisseur,
temps DB, retries et taille des sorties. Utiliser le même périmètre et un état de
cache explicite. Les anciens benchmarks async restent historiques.

## Concurrence

Batch et workers sont configurables dans l’IHM. Augmenter les workers peut
saturer DB/quota/mémoire. Les verrous pipeline↔backtesting protègent la cohérence
et ne sont pas un problème de performance à contourner.

## Quotas

Prévisualiser univers et coût avant collecte. Planifier les gros backfills,
éviter les doublons et conserver les retries. Un fallback fournisseur exige un
cross-check des conventions.

## Artefacts et rétention

La croissance des runs/logs/modèles doit suivre une politique de rétention avec
protection du serving et des preuves d’audit. Voir
[sauvegarde/reprise](sauvegarde_reprise_et_retention.md) et
[IHM et opérations](../16_ihm_et_operations.md).
