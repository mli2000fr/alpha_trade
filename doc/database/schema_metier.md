# Schéma métier et ownership des tables

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

Retour : [base de données](../15_base_de_donnees.md)

Les migrations Alembic et les DDL sous `database/sql/` sont la vérité des colonnes/contraintes. Cette carte indique le propriétaire d'écriture ; elle n'est pas un DDL.

## Trois bases, trois contrats

US utilise `alpha_trade`, CN `alpha_trade_cn` et FR `alpha_trade_fr`, résolues
par `database/router.py` et les profils de marché. Les schémas ne sont pas
interchangeables : un même nom comme `stock_bars_daily` ne suffit pas à choisir
le bon loader. Les arbres `alembic`, `alembic_cn` et `alembic_fr` évoluent
séparément. Voir le [registre DDL/migrations](../reference/schema_et_migrations_generes.md)
et les guides [CN](../cn/README.md)/[FR](../fr/README.md).

La carte ci-dessous décrit principalement le parcours historique US. Elle ne
doit pas servir à inventer les tables manquantes dans les deux autres bases.

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

## Catalogue fonctionnel

### Marché et qualité

`stock_metadata` porte le référentiel. `stock_bars` conserve ingestion et provenance ; `stock_bars_daily` est la série nettoyée aval. `stock_quote_snapshots` et `stock_earnings_calendar` alimentent spread et blackout. Les tables `cleaning_audit_latest` et `cleaning_audit_*_runs` séparent état courant et preuve historique.

### Univers et scores

`tradable_universe_runs` décrit une publication et `tradable_universe_history` ses membres PIT. `stock_scores` est mutable ; `stock_scores_history` sert à reconstruire les décisions. Consommer latest dans un backtest introduit un look-ahead.

### ML

`model_training_batch` et `model_training_run` identifient données et entraînements. Registry, metrics, governance et `champion_history` portent la sélection. `model_predictions` contient les inférences auditées. `global_rank_history`, `global_oracle_labels` et `oracle_extreme_predictions` ont des contrats spécialisés.

### Collectes et études US spécialisées

`pit_collection_runs` et `pit_raw_payloads` tracent les passages et versions
reçues ; ce ne sont pas des tables de sélection du portefeuille. Le statut
actif/autorisé du catalogue reste distinct de la présence de données anciennes.
`oracle_atr_market_regime_daily` conserve l'étude rétrospective quotidienne,
y compris les listes de rendements **réalisés**, couverture et politique de
listes partielles : ne pas les traiter comme prédictions disponibles à J.

Le filtre GPT écrit `llm_directional_runs`, `llm_directional_assessments` et
`llm_directional_evaluations`. Les assessments archivés ne deviennent des
candidats risque qu'après validation du run, de la date, du marché et du scope.
Voir les contrats [GPT](../ml/oracle_llm_directional_filter.md) et
[Oracle × ATR](../ml/oracle_atr_market_regime_daily.md).

### Staging FR

`fr_provider_universe_staging`, `fr_provider_bars_staging`,
`fr_provider_actions_staging` et `fr_staging_progress` enregistrent la collecte
fournisseur et sa reprise. Leur remplissage ne prouve ni qualification PIT ni
promotion dans les tables canoniques. Les DDL FR distinguent ensuite référentiel,
barres fournisseur/canoniques, anomalies, univers et recherches relatives.

### Risque et exécution

`risk_decisions` explique acceptations/rejets ; `portfolio_targets` matérialise l’intention. L’exécution conserve successivement run, target snapshot, request, ordre, fill, position/lot, événement, réconciliation et TCA. Ne pas compresser cette causalité dans une seule table.

### Corporate actions et audit

`corporate_actions_events` représente le fait provider, `corporate_actions_applications` l’application par compte et `portfolio_cash_ledger` l’impact cash. Summaries et `audit_chain_events` apportent une preuve transversale sans remplacer les tables métier.

## Règles de lecture

- Opérationnel : latest avec contrôle de fraîcheur.
- Décision PIT : publication disponible à la date de décision.
- Audit : partir du run id et suivre ses références.
- Multi-compte : filtrer explicitement `account_id`.
- Prix : vérifier source et `data_adjustment`.
- Modèle : vérifier batch, horizon, modèle, features et timestamp.

## Ajouter une table

Définir propriétaire, clé naturelle, cycle de vie, statut, dates métier/disponibilité/ingestion, compte, provenance, retry et rétention. Ajouter migration, index issus des requêtes, repository, tests d’idempotence et documentation. Une table latest importante doit disposer d’une preuve history/run.
