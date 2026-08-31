# Compliance et auditabilité

## Objectif

Pouvoir expliquer une décision depuis les données disponibles jusqu’au broker,
avec identités, versions, timestamps et motifs. L’audit porte autant sur les
refus/fallbacks que sur les trades exécutés.

## Chaîne de preuve

```text
source + disponibilité → feature/score → modèle/batch/prédiction
 → décision risque + motifs → cible → request/ordre/fill
 → position/lot → rapprochement/reporting
```

## Contrôles

La page Compliance & Audit relance des jobs et présente leurs résultats. Les
exceptions doivent avoir règle, objet, période, sévérité, preuve et résolution.
La page Tax Compliance couvre lots et wash sale ; Corporate Actions conserve
événements et applications.

## Immutabilité et corrections

Corriger par un mécanisme traçable plutôt qu’écraser une preuve historique.
Conserver avant/après, responsable, motif et lien au run. Les exports ne doivent
pas exposer de secrets ou données hors périmètre.

Voir [reporting/lineage/formel](reporting_lineage_formal.md) et
[guide conformité](../guide_utilisateur/10_conformite_corporate_actions.md).

