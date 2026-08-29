# Compliance, fiscalité et sandbox health

## Compliance & Audit

La page agrège chaîne HMAC, drill DR, vulnérabilités, couverture, mutation, TLAPS, fuzzing et sandbox. Elle peut relancer certains jobs, exporter un snapshot et produire un PDF. Un statut indisponible n’est pas vert ; un job `skipped` faute d’outil n’est pas une preuve réussie.

Avant relance pre-live, sélectionner le compte et le mode broker. `skip network` réduit la portée. Conserver commit, paramètres, rapport et erreurs. Voir [qualité avancée](../operations/qualite_avancee_fuzz_mutation_formel.md).

## Tax Compliance

La page filtre période, symbole et compte, affiche les lots, exporte CSV et présente les ajustements wash sale. Les résultats dépendent des fills et événements cash persistés. Réconcilier le broker et les corporate actions avant export fiscal. Le module est une aide technique, pas un conseil fiscal.

## Sandbox health

Le calendrier charge `_rollup.json` et les `health.json` quotidiens. Fichier absent ou invalide signifie absence de preuve, pas succès. Lire le dernier échec et son étape, puis relancer cross-check Stooq ou health providers depuis les onglets prévus. Conserver l’artefact initial avant relance.

Une anomalie portant sur ordres, PIT, protections, réconciliation ou audit impose NO-GO jusqu’à explication. Voir [runbook sandbox](../operations/sandbox_health.md).

