# 08 — Plan d’action par sprints

## S0 — Corrections P0 provider/config/doc

- Priorité : P0
- Modules : `config`, `dataIntegrityEngine`, `doc`, `ihm`
- Anomalies : A-001, A-003
- Objectif : supprimer le faux fallback et rendre les runbooks provider-aware.
- Tâches :
  1. Décider : implémenter `fallback_on_failure` ou le retirer.
  2. Corriger `doc/dataIntegrityEngine.md` : EODHD nominal, Alpaca rétrocompat.
  3. Ajouter doc-check provider switch.
  4. Afficher dans IHM “EODHD primaire / Alpaca no-op”.
- Fichiers : `config.yaml`, `dataIntegrityEngine/eodhd/cli.py`, `ihm/services/pipeline_runner.py`, docs.
- Critères d’acceptation : aucune doc ne recommande Alpaca daily sans mention rétrocompat ; fallback testé.
- Tests nouveaux :
  - `tests/test_market_data_provider_switch.py::test_fallback_on_failure_is_effective_or_rejected`
  - `tests/test_docs_provider_consistency.py::test_no_unqualified_import_alpaca_bar_runbook`
- Gain attendu : documentation +0.8, configuration +0.6, dataIntegrityEngine +0.3.

## S1 — Schéma et lineage OHLCV

- Priorité : P1
- Modules : database, dataIntegrityEngine, backtesting
- Anomalies : A-002, A-004
- Objectif : aligner capacité DB et promesse de lineage source.
- Tâches :
  1. Choisir stratégie : source unique active ou multi-source versionné.
  2. Si source unique : corriger docs et ajouter audit SQL source active.
  3. Si multi-source : migration PK `(symbol,date,data_source)` et adaptation consumers.
  4. Ajouter preflight backtesting source.
- Tests :
  - SQL migration test `tests/test_stock_bars_daily_source_versioning.py`
  - Backtest preflight `tests/test_backtesting_data_source_preflight.py`
- Critères : impossible de croire à une cohabitation non supportée.
- Gain : database +0.8, backtesting +0.5, OHLCV +0.7.

## S2 — Qualité quotes/spreads et sync historique

- Priorité : P1
- Modules : dataIntegrityEngine, selector, IHM
- Anomalies : A-007, A-008, A-009
- Objectif : éviter faux signaux d’exécutabilité liés aux quotes IEX et aux runs historiques coûteux.
- Tâches :
  1. Ajouter `quote_source`, `quote_age`, `quote_size_quality` dans diagnostics selector.
  2. Bloquer ou downgraded si quotes stale.
  3. IHM : estimation coût/durée avant sync historique quotes.
  4. Limites par défaut et confirmation forte pour univers large.
- Tests :
  - `tests/test_alpha_scanner_quote_quality.py`
  - `tests/test_sync_latest_quotes_cost_estimator.py`
  - `tests/test_pages_pipeline_quote_history_warning.py`
- Gain : selector +0.5, IHM +0.4, data quality +0.5.

## S3 — Presets capital et exécutabilité petits comptes

- Priorité : P1
- Modules : config, risk_management, execution_engine, backtesting
- Anomalies : A-006, A-007, A-014
- Objectif : rendre chaque tranche explicitement réaliste et testée.
- Tâches :
  1. Réviser descriptions micro-compte.
  2. Ajouter stress slippage/frais par tranche.
  3. Ajouter ML weight gate si drift/precision insuffisants.
  4. Simuler cash settlement et min notional.
- Tests :
  - `tests/test_capital_presets_executability.py`
  - `tests/test_small_account_cash_settlement.py`
  - `tests/test_risk_ml_weight_gate.py`
- Gain : configuration +0.5, risk +0.6, swing fitness +0.5.

## S4 — Parité backtest ↔ live/paper

- Priorité : P1
- Modules : backtesting, execution_engine, risk_management
- Anomalies : A-013
- Objectif : fournir un profil “production parity” obligatoire avant live.
- Tâches :
  1. Créer profil CLI `--profile production-parity`.
  2. Activer phases execution/protection/watcher/exit replay par défaut dans ce profil.
  3. Golden dataset de targets/fills/positions.
  4. Rapport écart live-vs-backtest.
- Tests :
  - `tests/test_backtest_live_parity_golden.py`
  - `tests/test_execution_replay_parity.py`
- Gain : backtesting +1.0, execution +0.4, readiness +0.5.

## S5 — Corporate actions production hardening

- Priorité : P1
- Modules : corporate_actions, database, execution
- Anomalies : A-010, A-011
- Objectif : garantir sync/apply CA sans surprise provider/snapshot.
- Tâches :
  1. Préflight positions snapshots avant apply.
  2. Interdire sync globale EODHD sans univers explicite avec message clair.
  3. Cross-check dividends/splits provider vs broker si disponible.
  4. Reconciliation cash ledger.
- Tests :
  - `tests/test_corporate_actions_eodhd_scope.py`
  - `tests/test_corporate_actions_apply_requires_positions.py`
  - `tests/test_portfolio_cash_ledger_idempotence.py`
- Gain : corporate_actions +0.8, DB audit +0.3.

## S6 — Observabilité et exploitation incident

- Priorité : P1/P2
- Modules : IHM, observabilité, execution
- Anomalies : A-012, A-015, A-018
- Objectif : passer de logs dispersés à cockpit incident.
- Tâches :
  1. Correlation ID global workflow.
  2. Dashboard run parent/enfants, stale steps, retry/resume.
  3. Coverage artifact validé uniquement suite complète.
  4. Kill/restart safe avec statut DB/artifact.
- Tests :
  - `tests/test_pipeline_workflow_correlation_id.py`
  - `tests/test_ihm_process_kill_marks_failed.py`
  - `tests/test_coverage_artifact_is_complete.py`
- Gain : observabilité +1.0, IHM +0.6, readiness +0.6.

## S7 — ML/sentiment gouvernance alpha

- Priorité : P2
- Modules : event_sentiment, modelFactory, risk
- Anomalies : A-014
- Objectif : prouver que ML/sentiment ajoutent de la valeur et ne dégradent pas le risk.
- Tâches :
  1. Ablation quant-only vs sentiment vs ML par régime.
  2. Drift gates bloquants.
  3. Seuils min precision/action rate persistés et affichés IHM.
  4. Fallback quant-only automatique.
- Tests :
  - `tests/test_model_governance_drift_gate.py`
  - `tests/test_sentiment_ablation_report.py`
  - `tests/test_risk_fallback_quant_only.py`
- Gain : modelFactory +0.8, event_sentiment +0.7, risk +0.4.

## S8 — Sécurité et production readiness

- Priorité : P2
- Modules : config, security, CI/CD, execution
- Objectif : maturité production.
- Tâches :
  1. Secret manager/vault obligatoire pour live.
  2. CI `pip-audit`, CVE, secret scan, ruff, mypy, pytest critical.
  3. Approval live et immutable run plan.
  4. Runbooks incident : broker outage, provider outage, DB outage, partial fill.
- Tests :
  - `tests/test_live_requires_vault_or_env_policy.py`
  - `tests/test_execution_live_requires_approval_token.py`
  - CI security workflow.
- Gain : sécurité +1.0, readiness +0.9.

## Matrice anomalies corrigées → sprints

| Anomalie | Sprint |
|---|---|
| A-001 | S0 |
| A-002 | S1 |
| A-003 | S0 |
| A-004 | S1/S4 |
| A-005 | S3/S6 |
| A-006 | S3 |
| A-007 | S2/S3 |
| A-008 | S2 |
| A-009 | S2/S6 |
| A-010 | S5 |
| A-011 | S5 |
| A-012 | S6 |
| A-013 | S4 |
| A-014 | S7 |
| A-015 | S6 |
| A-016 | S8 |
| A-017 | S0 |
| A-018 | S6 |

## À partir de quel sprint l’application devient suffisamment robuste pour un swing trading réel discipliné

Après **S0 à S5** validés, l’application peut être considérée suffisamment robuste pour un **live pilote très discipliné**, capital limité, exécution paper comparée et supervision quotidienne. Pour monter en taille, S6 et S7 deviennent nécessaires.

## Ce qu’il restera pour un vrai 10/10 pro-grade

- Orchestrateur durable type Prefect/Airflow avec reprise transactionnelle.
- Monitoring centralisé Prometheus/Grafana + alerting.
- Validation indépendante modèles/signaux.
- Change management, approvals, séparation env dev/paper/live.
- Tests broker contract et simulation incidents.
- Documentation générée automatiquement depuis config/code.

