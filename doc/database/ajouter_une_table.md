# Ajouter ou faire évoluer une table

## Principe

Une table n’est pas terminée quand son DDL existe. Il faut aligner migration Alembic, repository, transactions/idempotence, producteurs, consommateurs, tests, observabilité, rétention et documentation. Le graphe `revision/down_revision` fait autorité ; ne jamais modifier une migration déjà appliquée.

## Procédure

1. définir owner, criticité, clés métier, temporalité/PIT, volume et rétention ;
2. chercher une table ou un événement existant pour éviter le doublon ;
3. créer une révision Alembic à partir du head réel ;
4. préférer expand/migrate/contract pour un changement incompatible ;
5. définir types, UTC/date, nullabilité, contraintes, uniques et index selon les requêtes ;
6. isoler un backfill lourd du DDL bloquant ;
7. ajouter les opérations au repository du domaine, avec paramètres et conversions explicites ;
8. définir frontière transactionnelle, clé d’idempotence, retry et statut partiel ;
9. mettre à jour producteur, consommateurs, lineage et run summary ;
10. tester installation vierge, upgrade précédent→head, contraintes, rollback sûr, concurrence et reprise ;
11. mesurer plan, lock, durée et croissance sur une copie ;
12. déployer schéma additif avant le code qui en dépend.

## Revue du DDL

Une clé technique ne remplace pas une contrainte d’unicité métier. Pour une donnée temporelle, préciser date d’événement, date de disponibilité et source. Pour les montants, préciser devise et précision ; pour pourcentages, fraction ou points ; pour enum, politique des valeurs inconnues. Les timestamps de création/modification ne rendent pas une table PIT.

## Idempotence et panne

La clé doit représenter l’événement stable : symbole+séance+source pour une barre, batch+symbole+date+horizon pour une prédiction, client/broker id pour ordre/fill. Après timeout, relire avant retry : l’absence de réponse ne prouve pas l’absence de commit. Après exception SQL, rollback avant réutilisation de session.

## Backfill

Le backfill doit être borné, relançable, observable et compatible avec l’ancien code pendant la transition. Enregistrer plage, lignes lues/écrites/rejetées, checkpoint et erreurs. Vérifier avant/après nulls, doublons, distribution, dates futures et taille.

## Documentation à mettre à jour

- [schéma métier](schema_metier.md) : rôle, clés, writer/readers ;
- [migrations/transactions](migrations_et_transactions.md) : stratégie spéciale ;
- [intégrité/lineage](../data/integrite_lineage_et_qualite.md) ;
- guide du producteur et des consommateurs ;
- inventaire API si une interface publique change ;
- rétention/reprise si la table est critique.

## Gates

Ne pas livrer si plusieurs heads non résolus, downgrade destructif non signalé, backfill non relançable, index non mesuré, nouvelle donnée non reliée à un run/source, ou migration/test dépendant d’un état local implicite.

