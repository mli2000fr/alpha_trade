# IHM, supervision et opérations

## Documents spécialisés

- [Architecture IHM et services](operations/ihm_reference.md)
- [Supervision, notifications et sécurité](operations/supervision_et_securite.md)
- [Reporting, lineage et vérification formelle](operations/reporting_lineage_formal.md)
- [Fiscalité et wash sale](operations/fiscalite_wash_sale.md)

## Structure

`ihm/app.py` est le point d'entrée Streamlit. `ihm/pages/` contient les pages métier ; `ihm/components/` les composants de rendu ; `ihm/services/` les requêtes, commandes et états ; `ihm/theme/` la présentation.

La couche thème sépare palette, badges, icônes et `typography.py`. Elle ne porte aucune décision métier.

## Pages principales

Overview, Pipeline, Screening, ML, ML diagnostics, Risk, Execution, Corporate Actions, Backtesting, Parity, Market Regime, Fundamentals, Alpaca Accounts, Supervision Ops, Infrastructure, Compliance/Audit, Tax, Settings, DB admin et Sandbox Health.

L'IHM affiche et orchestre ; elle ne doit pas réimplémenter les règles métier. Les commandes sont construites par `pipeline_runner.py` et les services dédiés, puis exécutées avec journalisation, verrou de pipeline et registre de processus.

## Pipeline IHM

`PipelineOptions` contient paramètres de date, compte, provider, ML, backtest et watcher. Les commandes produites doivent rester équivalentes aux CLI publiques. `pipeline_lock.py` empêche des workflows concurrents dangereux ; `process_registry.py` suit les processus et artefacts.

## Sécurité

`ihm/services/security.py` limite l'exposition réseau et valide certains chemins/commandes. Les secrets sont masqués. Les actions live doivent rendre visibles compte, mode et confirmation. DB admin et opérations destructives demandent une intention explicite.

## Supervision

- run summaries et business summaries ;
- santé provider, DB, quotes et données ;
- processus actifs et logs ;
- watcher protections ;
- notifications email ;
- métriques Prometheus et règles Grafana/alertes historiques ;
- conformité, audit chain et réconciliation.

## Reporting et lineage

`reporting/` produit rapports mensuels JSON/PDF selon extras installés. `lineage/` peut enregistrer événements et relations dans un graph store mémoire ou Neo4j. Ces couches consomment les faits persistés ; elles ne modifient pas une décision de trading.

## Diagnostic d'une page vide

Vérifier connexion DB, existence/migration de la table, sélection du compte, plage de dates, statut du run amont, présence des artefacts et cache Streamlit. Une page vide ne prouve pas qu'un calcul n'a jamais eu lieu ; consulter run summary, logs et base.
