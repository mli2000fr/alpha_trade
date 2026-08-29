# Base de données et persistance

## Documents spécialisés

- [Schéma métier et ownership des tables](database/schema_metier.md)
- [Migrations, transactions et idempotence](database/migrations_et_transactions.md)

## Architecture

`database/connection.py` construit l'engine SQLAlchemy depuis `config.yaml` et `LOGIN_DB`/`PASSWORD_DB`. Les repositories dans `database/repositories/` encapsulent actifs, barres, quotes, scores et run summaries. Les modules métier possèdent aussi des `db_io.py` spécialisés.

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

## Idempotence

Les imports utilisent upsert, clés naturelles et bookmarks. Les runs utilisent des identifiants uniques. Les corporate actions ont event/application distincts. Les ordres conservent identifiants internes et broker. Une reprise doit vérifier l'état existant avant insertion ou envoi.

## Audit et intégrité

`database/audit_chain.py` maintient une chaîne d'audit. `run_business_summaries.py` et repositories de summaries stockent les résultats structurés. Les contraintes de prix matérialisent la convention split-adjusted. Les transactions doivent entourer une publication atomique ou une application financière.

## Performance

Charger par plages/chunks, utiliser les index date/symbol/run, éviter les requêtes par ligne et privilégier les repositories. `async_engine.py` et `async_loaders.py` sont optionnels ; leur usage ne change pas le contrat transactionnel.
