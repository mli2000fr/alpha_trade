# IHM, supervision et opérations

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

## Documents spécialisés

- [Architecture IHM et services](operations/ihm_reference.md)
- [Supervision, notifications et sécurité](operations/supervision_et_securite.md)
- [Alerting multicanal et métriques](operations/alerting_et_metriques.md)
- [Reporting, lineage et vérification formelle](operations/reporting_lineage_formal.md)
- [Fiscalité et wash sale](operations/fiscalite_wash_sale.md)

## Structure

`ihm/app.py` est le point d'entrée Streamlit. `ihm/pages/` contient les pages métier ; `ihm/components/` les composants de rendu ; `ihm/services/` les requêtes, commandes et états ; `ihm/theme/` la présentation.

La couche thème sépare palette, badges, icônes et `typography.py`. Elle ne porte aucune décision métier.

## Pages principales

Overview, Pipeline, Batch, Screening, ML, ML diagnostics, Risk, Execution,
Corporate Actions, Backtesting, Parity, Market Regime, Fundamentals, Alpaca
Accounts, Supervision Ops, Infrastructure, Compliance/Audit, Tax, Settings,
DB admin, Sandbox Health et Glossaire.

Les vues Pipeline, Diagnostic ML, Backtesting et Batch ont des parcours
US/CN/FR. Cela n'est pas un switch global transformant Risk/Execution Alpaca
en moteur broker CN/FR. Les capacités servent de garde-fous.

L'IHM affiche et orchestre ; elle ne doit pas réimplémenter les règles métier. Les commandes sont construites par `pipeline_runner.py` et les services dédiés, puis exécutées avec journalisation, verrou de pipeline et registre de processus.

## Pipeline IHM

`PipelineLaunchOptions` contient paramètres de date, compte, provider, ML,
filtre GPT, backtest et watcher. Les commandes produites doivent rester
équivalentes aux CLI publiques. `pipeline_lock.py` et `process_registry.py`
gèrent verrous, processus et artefacts. Un défaut de checkbox IHM n'est pas
automatiquement transmis aux options fraîches du batch us_pipeline.

## Workflow & Orchestration → Batch

`ihm/pages/batches.py` et `ihm/services/batch_management.py` résolvent les
catalogues séparés et affichent priorité, description, tables, fenêtres/second
passage, raison de blocage, commandes, installation, dernier run et compteurs.
Installer/réinstaller tous agit uniquement sur les batchs activés compatibles
du marché sélectionné ; désinstaller tous vise ses tâches installées hors runs actifs.

Un dernier échec opérationnel est rouge/gras ; les blocages droits/prudence
restent noirs avec icônes très visibles ⛔ ⚖️. Une date Windows sentinelle
antérieure à 2000 n'est pas une véritable dernière collecte. Le résumé métier
et l'état Windows sont distincts. `enabled=true` ne lève pas un blocage de droits.
[Manuel de la page](guide_utilisateur/19_batchs_et_marches.md).

## Sécurité

`ihm/services/security.py` limite l'exposition réseau et valide certains chemins/commandes. Les secrets sont masqués. Les actions live doivent rendre visibles compte, mode et confirmation. DB admin et opérations destructives demandent une intention explicite.

## Supervision

- run summaries et business summaries ;
- santé provider, DB, quotes et données ;
- processus actifs et logs ;
- watcher protections ;
- notifications email et Telegram, avec compteurs/erreur et principal/secours selon le launcher ;
- métriques Prometheus et règles Grafana/alertes historiques ;
- conformité, audit chain et réconciliation.

## Reporting et lineage

`reporting/` produit rapports mensuels JSON/PDF selon extras installés. `lineage/` peut enregistrer événements et relations dans un graph store mémoire ou Neo4j. Ces couches consomment les faits persistés ; elles ne modifient pas une décision de trading.

## Diagnostic d'une page vide

Vérifier connexion DB, existence/migration de la table, sélection du compte, plage de dates, statut du run amont, présence des artefacts et cache Streamlit. Une page vide ne prouve pas qu'un calcul n'a jamais eu lieu ; consulter run summary, logs et base.
