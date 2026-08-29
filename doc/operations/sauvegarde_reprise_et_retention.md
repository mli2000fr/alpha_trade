# Sauvegarde, reprise après incident et rétention

## Périmètre et vérité exécutable

Une reprise complète peut exiger base MySQL, schéma Alembic, configuration, artefacts ML compatibles, manifests et secrets recréés. Les scripts courants sont `scripts/backup_db.py`, `scripts/backup_ml_artifacts.py`, `scripts/restore_from_backup.py` et `scripts/prune_artifacts.py`. Les secrets ne doivent jamais être placés dans les archives ni dans les rapports.

## Sauvegarde MySQL

`backup_db.py` appelle `mysqldump` avec transaction cohérente, routines, triggers et `utf8mb4`, puis compresse en `.sql.gz`. Par défaut la destination est `backups/db` et 30 dumps sont conservés. Les identifiants viennent de `LOGIN_DB` et `PASSWORD_DB`; hôte et base de `DB_HOST`/`DB_NAME` ou des arguments.

Le rapport contient début/fin, durée, cible, chemin, taille, fichiers tournés/conservés, dry-run et erreurs. Un fichier créé n’est pas une sauvegarde validée : vérifier taille non nulle, lisibilité gzip, rapport sans erreur et restauration périodique. `--dry-run` ne crée aucune sauvegarde.

## Restauration

`restore_from_backup.py` accepte `.sql` ou `.sql.gz`, alimente le client `mysql`, exécute `alembic upgrade head`, compte les tables critiques et appelle `scripts/verify_audit_chain.py --strict`. Son rapport expose chargement, migration, comptages, chaîne d’audit, âge du dump (`rpo_seconds`), durée (`rto_seconds`) et erreurs.

Tables contrôlées : `assets`, `stock_bars_daily`, `stock_scores`, `risk_decisions`, `execution_runs`, `corporate_actions`, `audit_chain_events`. Un comptage `-1` est un échec de lecture, pas zéro ligne.

1. empêcher les nouvelles mutations et isoler l’incident ;
2. conserver l’état dégradé ;
3. choisir et vérifier le dernier dump cohérent ;
4. restaurer d’abord dans une cible isolée ;
5. converger le schéma et examiner les comptages ;
6. vérifier audit, intégrité, positions, cash et ordres ;
7. restaurer les artefacts compatibles et recréer les secrets ;
8. réconcilier broker/base, effectuer les preflights et reprendre progressivement.

`--skip-alembic` et `--skip-audit` réduisent les garanties et doivent être justifiés.

## Drill mensuel

`.github/workflows/dr_drill.yml` crée une base MySQL 8, applique Alembic, injecte un jeu minimal, dump, détruit/recrée puis restaure. Il échoue si le rapport contient des erreurs ou si le RTO dépasse 1 800 secondes. Le rapport est conservé 365 jours. Ce petit dataset valide le chemin technique, pas le RTO d’un volume de production.

## Politique de purge codée

`prune_artifacts.py` est en dry-run par défaut et écrit `artifacts/prune_report.json`. `--apply` supprime, `--rule` limite à une règle et `--older-than` remplace l’âge. La purge est best-effort et retourne toujours 0 : lire le compteur `errors`.

| Règle | Âge | Nombre max. | Protection | Criticité |
|---|---:|---:|---|---|
| `eodhd_cache` | 90 j | — | — | P3 |
| `finnhub_cache` | 30 j | — | — | P3 |
| `ihm_pipeline_runs` | 60 j | 200 | — | P2 |
| `ihm_backtesting_runs` | 180 j | 100 | — | P2 |
| `ihm_preferences` | illimité | — | tout | P3 |
| `models` | 365 j | — | motifs `champion` illimités | P1 |
| `signal_aggregator_runs` | 60 j | — | — | P3 |
| `pre_live_checks` | 365 j | — | — | P1 |

Le plafond porte sur les fichiers triés par mtime. Pour les modèles, `**/champion*`, `**/CHAMPION*` et `**/*.champion.*` sont protégés. Vérifier manifests et chemins servis avant toute purge complémentaire.

## Preuves attendues

- rapport sans erreur et dump non vide ;
- restauration isolée réussie et Alembic à la tête ;
- tables critiques lisibles et chaîne HMAC valide ;
- artefacts ML compatibles ;
- réconciliation broker/base sans ordre orphelin ;
- commit, dates, RPO/RTO et anomalies archivés.

Voir [administration](../guide_utilisateur/11_parametres_administration.md), [sécurité live](securite_live.md) et [réconciliation](../execution/reconciliation_et_tca.md).
