# Migrations, transactions et idempotence

Retour : [base de données](../15_base_de_donnees.md)

Alembic versionne le schéma. Une migration ajoute/modifie DDL, index et backfill avec stratégie downgrade lorsque réaliste. Ne jamais réécrire une révision appliquée. Tester upgrade depuis la révision précédente sur une copie et vérifier volumes/locks.

Les publications d'univers utilisent une transaction logique building→members→published. Les corporate actions séparent événement/application/ledger pour idempotence. L'exécution sépare request/order/fill et utilise ids broker/client. Les imports utilisent upsert et bookmarks.

Une clé d'idempotence doit représenter l'événement métier, pas l'heure du retry. Les commits batch rendent un run partiel ; summary/checkpoint indique jusqu'où reprendre. Ne pas supprimer les rows partielles sans analyser leur statut.

Les repositories centralisent SQL et conversion. Ajouter un index selon requêtes réelles date/symbol/run/account, mesurer plan avant/après. Les modes async sont optionnels et ne changent pas atomicité.

