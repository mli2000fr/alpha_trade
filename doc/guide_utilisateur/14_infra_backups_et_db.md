# Infra, sauvegardes et administration DB

## Infra & Backups

La page regroupe métriques, archives ML, dumps DB et reset ML. Les compteurs peuvent être actifs, no-op ou indisponibles selon dépendances ; un zéro après redémarrage n’est pas une preuve d’absence d’événement car le registre Prometheus est local au processus.

Une archive ML doit conserver artefacts, manifests et compatibilité de serving. Un dump DB doit être non vide, lisible et testé par restauration. Les listes d’archives facilitent l’inventaire mais ne certifient pas leur intégrité.

Le reset ML touche tables et répertoires, peut arrêter des runs et est destructif. Lire la liste calculée, créer les sauvegardes, confirmer l’environnement et conserver le journal. Préférer une purge ciblée.

## Administration DB

La page construit un plan par groupes et n’autorise que les entrées marquées purgeables. Le plan SQL, les tables protégées et la confirmation constituent des gates distinctes. Une sélection vide n’exécute rien.

Pour restaurer, fournir un dump explicite. Le dry-run est activé par défaut. `skip Alembic` et `skip audit` réduisent les garanties : ne les utiliser qu’avec justification. Après restauration, vérifier migrations, tables critiques, chaîne HMAC et réconciliation.

Voir [sauvegarde/reprise](../operations/sauvegarde_reprise_et_retention.md) et [ajouter une table](../database/ajouter_une_table.md).

