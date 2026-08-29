# Migrations, transactions et idempotence

Retour : [base de données](../15_base_de_donnees.md)

Alembic versionne le schéma dans `alembic/versions/`. Une migration ajoute/modifie DDL, index et backfill avec stratégie downgrade lorsque réaliste. Ne jamais réécrire une révision appliquée. Tester upgrade depuis la révision précédente sur une copie et vérifier volumes/locks.

## Cycle d’une migration

1. Vérifier `current`, `heads` et `history`.
2. Créer un identifiant unique et le bon `down_revision`.
3. Séparer DDL rapide et backfill volumineux si nécessaire.
4. Définir nullabilité, default temporaire et contraintes finales.
5. Mesurer locks et durée sur une copie.
6. Tester upgrade puis downgrade lorsque sûr.
7. Déployer le schéma additif avant le code consommateur.
8. Vérifier schéma, index, volumes et application.

Le graphe `revision/down_revision`, non le nom lexical, fait autorité. Un conflit de heads se résout explicitement.

## Compatibilité

Préférer expand/migrate/contract : ajouter de façon compatible, déployer un code lisant ancien et nouveau, backfiller, basculer, puis retirer l’ancien dans une révision ultérieure. Éviter rename/drop dans le même déploiement que le changement applicatif.

Les publications d'univers utilisent une transaction logique building→members→published. Les corporate actions séparent événement/application/ledger pour idempotence. L'exécution sépare request/order/fill et utilise ids broker/client. Les imports utilisent upsert et bookmarks.

Une clé d'idempotence doit représenter l'événement métier, pas l'heure du retry. Les commits batch rendent un run partiel ; summary/checkpoint indique jusqu'où reprendre. Ne pas supprimer les rows partielles sans analyser leur statut.

Exemples : barre = symbole + timestamp + source/convention ; univers = run + symbole ; prédiction = batch/run + symbole + date + horizon ; ordre = request/client id stable ; fill = broker fill id ; corporate action = événement + compte + application.

## Frontières transactionnelles

Une transaction protège un invariant cohérent, pas nécessairement tout un long run. Une publication d’univers ne doit pas exposer des membres sans run publié. Une application de dividende relie application et ledger. La DB et le broker ne peuvent pas former une transaction atomique : états, identifiants idempotents et réconciliation comblent cette limite.

Les commits par chunks réduisent locks et mémoire mais exposent un état partiel. Checkpoint et summary indiquent alors la dernière unité validée.

Les repositories centralisent SQL et conversion. Ajouter un index selon requêtes réelles date/symbol/run/account, mesurer plan avant/après. Les modes async sont optionnels et ne changent pas atomicité.

## Échec, reprise et tests

Après exception SQL, rollback avant nouvelle requête. Avant retry, relire par clé d’idempotence : un timeout ne prouve pas l’absence de commit.

Tester migration précédente→nouvelle, installation vierge, contraintes, double exécution logique, rollback, reprise après chunk et concurrence. `tests/test_alembic_rollback.py` fait partie des garde-fous.
