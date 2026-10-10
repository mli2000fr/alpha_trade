# Catalogue des modules et fichiers clés

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

Ce catalogue aide à localiser rapidement le propriétaire d'un comportement. Les fonctions privées ne sont pas une API stable ; partir du point d'entrée public, puis suivre les appels.

## Parcours ajoutés : repères du 10 octobre 2026

| Propriétaire | Fonction actuelle |
| --- | --- |
| common/market_context.py, common/config_loader.py | marché explicite, capacités, choix des fichiers de configuration |
| database/router.py, config/databases.yaml | bases physiques US/CN/FR et allowlists |
| ihm/services/batch_management.py, ihm/pages/batches.py | catalogues séparés, tâches Windows, état, commandes et blocages |
| service/forward_pit/batch.py, us_pipeline.py, recovery_gate.py, watcher_startup.py | collectes US, workflow planifié 1–14, secours et prérequis watcher |
| service/llm_directional/ | Oracle → GPT/Web prospectif → risque/PAPER, archivage et protections figées |
| service/market/oracle_atr_study.py, new_entry_data_guard.py | étude rétrospective et contrôle live séparés |
| service/baostock/, dataIntegrityEngine/cn_*, modelFactory/cn_* | données/recherche/replay CN ; propriétaires quotidiens bloqués selon catalogue |
| service/fr/, service/inpi/ | collecte, staging, preuves et qualification FR ; droits/capacités contrôlés |

Ce tableau explique les responsabilités. L'[inventaire statique complet](reference/modules_generes.md)
et les [API régénérées](api/README.md) donnent les chemins et signatures actuels,
y compris les scripts et les migrations US/CN/FR. [État actuel](ETAT_ACTUEL_IMPLEMENTATION.md).

## `core/`

- `direction.py`, `types.py`, `broker_models.py` : types et directions partagés ;
- `ternary_decision_policy.py` : décision long/flat/short, validation probabilités et artefact baseline ;
- `ml_selection_contract.py`, `eligibility.py` : contrats d'admissibilité ;
- `conviction.py` : représentation de conviction ;
- `secrets.py` : placeholders, scan et validation ;
- `run_summary.py`, `metrics.py` : résumé versionné et métriques ;
- `interfaces.py`, `feature_flags.py`, `filter_profiles.py` : abstractions et politiques communes.

## `common/`

- `config_loader.py`, `config_vault.py` : chargement et overrides ;
- `tradable_universe.py`, `publish_tradable_universe.py` : snapshot PIT ;
- `entry_data_gate.py`, `data_availability.py` : disponibilité/fail-closed ;
- `market_calendar.py` : séances ;
- `price_convention.py`, `trading_costs.py` : prix et coûts ;
- `sizing.py`, `quantity_utils.py`, `capital_presets.py` : tailles/capital ;
- `logging_setup.py`, `metrics.py`, `daily_quality_report.py` : observabilité ;
- `windows_sleep_guard.py` : empêche la veille pendant un run critique.

## `database/`

`connection.py` est l'accès synchrone principal. `repositories/` porte les accès génériques. Les autres fichiers encapsulent tables spécialisées, audits, bar metadata, macro et summaries. `async_*` est optionnel.

## `dataIntegrityEngine/`

`import_alpaca_assets.py` initialise les actifs. `import_eodhd_bar.py` et `import_alpaca_bar.py` importent selon provider. `backfill_eodhd_history.py` gère l'historique et bookmark. `data_sanitizer_daily.py` nettoie. `sync_latest_quotes.py` et `sync_earnings_calendar.py` complètent les gates. `update_sector.py` enrichit le référentiel. `data_source_health.py` et `cross_check_stooq.py` diagnostiquent.

## Signaux

`screener/pipeline.py` contient les calculs purs ; `stock_screener.py` l'orchestration parallèle ; `db_io.py` la persistance. Dans `selector/`, `scanner.py` est le cœur, `factors.py` et `filters.py` calculent, `ranking.py` ordonne, `regime_*` adapte et `explainability.py` justifie. Dans `event_sentiment/`, `pipeline.py`/`cli.py` orchestrent et les fichiers ingestion, relevance, scoring, aggregation isolent chaque phase.

## `modelFactory/`

`analyst_research/` est un propriétaire distinct : collecte, parseurs, disponibilité,
features et monitoring des snapshots analystes. Son existence ne signifie pas que
le batch consensus soit autorisé/actif ; consulter le catalogue et les blocages.

`cli.py` construit la configuration et distribue train/predict. `orchestrator.py` séquence les familles. `data_loader.py`, `dataset.py`, `features.py`, `labeling.py` forment la donnée. `trainer*.py`, `global_model.py`, `global_ranking.py` entraînent. `evaluation.py`, `calibration.py`, `champion_selection.py` gouvernent. `predictor.py`, `run_predict.py` infèrent. `db_registry.py`, `report.py`, `runtime_status.py` persistent et exposent l'état. Les sous-dossiers `oracle/`, `global_direction/`, `dip_research/` et `directional_data_research/` ont des objectifs spécialisés.

## `risk_management/`

`cli.py` est le point d'entrée réel derrière `run_risk.py`. `db_io.py` charge et persiste. `ml_gate.py`/`selection_contract.py` valident. `regime_apply.py`, `circuit_breaker.py`, `freshness_gate.py` filtrent. `position_sizer.py`, `kelly.py`, `capacity.py` dimensionnent. `constraints.py`, `concentration*.py`, `correlation_filter.py`, `portfolio_optimizer.py` arbitrent. `portfolio_builder.py` produit les targets. Les fichiers audit/journal/fingerprint assurent la preuve.

## `execution_engine/`

`executor.py` orchestre, `executor_phases.py` découpe, `broker_adapter.py` abstrait le broker. `order_intents.py` construit les ordres. `children_submission.py` et `oco_manager.py` gèrent protections. `state_machine.py` contrôle les états. `broker_state_sync.py`, `reconciliation.py`, `reconcile_statement.py` rapprochent. `protection_watcher.py` surveille après run. `tca.py` mesure l'exécution.

## `backtesting/`

`cli/` expose les commandes. `simulator.py` est la boucle. `signal_replay.py`, `risk_bridge.py`, `execution_*replay.py` rapprochent le live. `microstructure.py` modélise les coûts. `walk_forward*`, `statistical_validation.py` valident. `report.py` et `report_schema*` structurent les sorties.

## Exploitation et auxiliaires

- `corporate_actions/` : événements financiers ;
- `service/` : providers/adaptateurs ;
- `ihm/` : interface, composants et services ;
- `flows/` : orchestration Prefect opt-in ;
- `reporting/` : rapports JSON/PDF ;
- `lineage/` : graphe de traçabilité ;
- `tax/wash_sale.py` : règles wash-sale ;
- `formal/` : invariants et vérification formelle.
