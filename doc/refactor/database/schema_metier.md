# Schéma métier et ownership des tables

Retour : [base de données](../15_base_de_donnees.md)

Les migrations Alembic sont la vérité des colonnes/contraintes. Cette carte indique le propriétaire d'écriture ; elle n'est pas un DDL.

| Domaine | Tables principales | Writer |
|---|---|---|
| marché | metadata, bars, daily, quotes, earnings | Data Integrity |
| qualité | cleaning audit latest/runs | Sanitizer |
| univers | tradable universe runs/history | common publisher |
| signaux | scores/latest/history, news et features sentiment | screener/selector/sentiment |
| ML | training runs, registry, metrics, governance, predictions, ranks, Oracle | modelFactory |
| risque | decisions, targets, journals/états | risk_management |
| exécution | runs, snapshots, requests, orders, fills, positions, lots, events, reconciliation | execution_engine |
| broker | account/position snapshots | execution sync |
| CA | events, applications, cash ledger | corporate_actions |

Les consumers ne doivent pas écrire dans la table d'un autre domaine hors repository/API prévu. Latest est une vue opérationnelle mutable ; history/run est nécessaire au PIT/audit.

Clés usuelles combinent symbol/date, run id et account id. Les tables multi-comptes doivent toujours filtrer account. Les dates économiques, dates de disponibilité et timestamps d'ingestion doivent rester distincts lorsqu'ils existent.

