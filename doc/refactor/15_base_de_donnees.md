# Base de données et persistance

## Documents spécialisés

- [Schéma métier et ownership des tables](database/schema_metier.md)
- [Accès asynchrone expérimental](database/async_db_poc.md)
- [Ajouter ou faire évoluer une table](database/ajouter_une_table.md)
- [Migrations, transactions et idempotence](database/migrations_et_transactions.md)

## Architecture

`database/connection.py` construit l'engine SQLAlchemy depuis `config.yaml` et `LOGIN_DB`/`PASSWORD_DB`. Les repositories dans `database/repositories/` encapsulent actifs, barres, quotes, scores et run summaries. Les modules métier possèdent aussi des `db_io.py` spécialisés.

En pratique, la connexion commune utilise les défauts `localhost` et `alpha_trade`, remplaçables par `DB_HOST` et `DB_NAME` lorsqu’aucun argument explicite différent n’est fourni. Le DSN est MySQL/PyMySQL en `utf8mb4`. Engine et session factory sont mis en cache dans le processus : changer l’environnement après leur première résolution ne recrée pas automatiquement l’engine.

## Pool, TLS et sessions

| Paramètre | Défaut | Validation |
|---|---:|---|
| `DB_POOL_SIZE` | 2 | entier ≥ 1 |
| `DB_MAX_OVERFLOW` | 3 | entier ≥ 0 |
| `DB_POOL_RECYCLE_SECONDS` | 3600 | entier ≥ 60 |
| `DB_SSL_CA_PATH` | absent | fichier existant |

`pool_pre_ping=True` détecte les connexions mortes. Chaque worker multiprocessus possède son engine et peut ouvrir `pool_size + max_overflow` connexions. Si `DB_SSL_CA_PATH` est défini, le CA est passé à PyMySQL ; son absence ne garantit aucun chiffrement.

`SessionLocal()` crée une session avec `autocommit=False` et `autoflush=False`. L’appelant possède commit, rollback et fermeture. Après exception SQL, rollback est obligatoire avant réutilisation. Une session ne se transmet pas à un autre processus.

## Familles de tables

| Famille | Exemples |
|---|---|
| Référentiel marché | `stock_metadata`, `stock_bars`, `stock_bars_daily`, quotes, earnings |
| Qualité | cleaning audits, metadata/provenance |
| Univers | `tradable_universe_runs`, `tradable_universe_history` |
| Signaux | `stock_scores`, historique, tables news/sentiment |
| ML | registry, training runs, metrics, governance, `model_predictions`, global ranks, Oracle predictions |
| Risque | `risk_decisions`, `portfolio_targets`, journaux/états |
| Exécution | runs, target snapshots, requests, broker orders/fills, positions/lots, events, reconciliation, TCA |
| Broker | account et position snapshots |
| Corporate actions | events, applications, `portfolio_cash_ledger` |
| Ops | run summaries, audit chain, reporting/lineage |

Les noms exacts et colonnes sont définis par les migrations Alembic et les DDL ; consulter la révision courante plutôt qu'un ancien diagramme.

## Migrations

```powershell
alembic current
alembic history
alembic upgrade head
```

Une nouvelle migration doit être additive et réversible lorsque possible, définir contraintes/index, gérer le backfill et être testée sur une copie. Ne jamais modifier une migration déjà appliquée en production pour changer l'histoire.

Le répertoire canonique est `alembic/versions/`. Le graphe `revision/down_revision`, et non l’ordre lexical des noms, fait autorité. `alembic.ini` contient un DSN factice ; la connexion réelle est résolue par l’environnement Alembic/runtime.

## Idempotence

Les imports utilisent upsert, clés naturelles et bookmarks. Les runs utilisent des identifiants uniques. Les corporate actions ont event/application distincts. Les ordres conservent identifiants internes et broker. Une reprise doit vérifier l'état existant avant insertion ou envoi.

## Audit et intégrité

`database/audit_chain.py` maintient une chaîne d'audit. `run_business_summaries.py` et repositories de summaries stockent les résultats structurés. Les contraintes de prix matérialisent la convention split-adjusted. Les transactions doivent entourer une publication atomique ou une application financière.

`database/sanitizer_db_ops.py` concentre les lectures/écritures du sanitizer. `database/cleaning_audits.py` expose les audits de nettoyage. `database/repositories/run_summaries.py` fournit l'accès repository aux résumés structurés, distinct de la vue métier portée par `run_business_summaries.py`.

## Diagnostic

| Symptôme | Contrôle |
|---|---|
| connexion refusée | host, base, credentials, TLS |
| saturation | workers × capacité de pool |
| colonne absente | `alembic current` contre heads |
| doublons | clé naturelle et chemin d’upsert |
| mauvais compte | filtre `account_id` |
| résultat stale | latest contre history/run et date |

## Performance

Charger par plages/chunks, utiliser les index date/symbol/run, éviter les requêtes par ligne et privilégier les repositories. `async_engine.py` et `async_loaders.py` sont optionnels ; leur usage ne change pas le contrat transactionnel.
