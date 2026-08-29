# Catalogue des modules et fichiers clés

Ce catalogue aide à localiser rapidement le propriétaire d'un comportement. Les fonctions privées ne sont pas une API stable ; partir du point d'entrée public, puis suivre les appels.

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

