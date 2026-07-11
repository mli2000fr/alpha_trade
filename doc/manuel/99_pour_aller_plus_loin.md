# 99. Pour aller plus loin

Vous maîtrisez l'IHM. Voici la documentation **avancée** pour comprendre
le moteur ou le modifier.

## Documentation fonctionnelle

- [doc/DOC_FONCTIONNELLE.md](../DOC_FONCTIONNELLE.md) — vision métier complète
- [doc/DOC_TECHNIQUE.md](../DOC_TECHNIQUE.md) — architecture technique
- [doc/ihm.md](../backup/ihm.md) — guide opérateur IHM complet
- [doc/onboarding_operator.md](../backup/onboarding_operator.md) — onboarding opérateur

## Modules métier

| Module | Doc |
|---|---|
| Screener | [doc/screener.md](../backup/screener.md) |
| Selector | [doc/selector.md](../backup/selector.md) |
| Event Sentiment | [doc/event_sentiment.md](../backup/event_sentiment.md) |
| ModelFactory (ML) | [doc/modelFactory.md](../backup/modelFactory.md) |
| Risk Management | [doc/risk_management.md](../backup/risk_management.md) |
| Execution Engine | [doc/execution_engine.md](../backup/execution_engine.md) |
| Corporate Actions | [doc/corporate_actions.md](../backup/corporate_actions.md) |
| Backtesting | [doc/backtesting.md](../backup/backtesting.md) |
| Data Integrity | [doc/dataIntegrityEngine.md](../backup/dataIntegrityEngine.md) |
| Watcher | [doc/watcher.md](../backup/watcher.md) |

## Architecture & qualité

- [doc/architecture/](../architecture/) — diagrammes
- [doc/database.md](../backup/database.md) — schéma DB
- [doc/data_lineage_matrix.md](../backup/data_lineage_matrix.md)
- [doc/observability.md](../backup/observability.md)
- [doc/perf_pipeline.md](../backup/perf_pipeline.md)
- [doc/perf_hotspots.md](../backup/perf_hotspots.md)

## Runbooks ops

- [doc/runbook_24_7.md](../backup/runbook_24_7.md)
- [doc/runbook_provider_incident.md](../backup/runbook_provider_incident.md)
- [doc/runbook_reconciliation.md](../backup/runbook_reconciliation.md)
- [doc/sandbox_health_runbook.md](../backup/sandbox_health_runbook.md)
- [doc/disaster_recovery.md](../backup/disaster_recovery.md)

## Conformité & audit

- [doc/external_audit_checklist.md](../backup/external_audit_checklist.md)
- [doc/external_audit_engagement.md](../backup/external_audit_engagement.md)
- [doc/pre_audit_findings.md](../backup/pre_audit_findings.md)
- [doc/pre_live_checklist.md](../backup/pre_live_checklist.md)
- [doc/artifacts_retention_policy.md](../backup/artifacts_retention_policy.md)

## Audits internes (Sprint S26)

- [doc/audit/matrice_ihm_cli.md](../audit/matrice_ihm_cli.md) — matrice
  IHM ↔ CLI et gaps
- [doc/audit/preset_petit_capital_2000eur.md](../audit/preset_petit_capital_2000eur.md)
  — analyse preset 2 000 €

## Code source — points d'entrée

- `run.py` — démarre l'IHM Streamlit
- `ihm/app.py` — routage des pages
- `ihm/pages/*.py` — une page IHM = un fichier
- `ihm/services/pipeline_runner.py` — builder des commandes pipeline
- `ihm/services/backtesting_runner.py` — builder backtest
- `common/capital_presets.py` — résolution du preset
- `config/capital_presets.yaml` — définition des presets

## Communauté & liens externes

- Alpaca docs : <https://alpaca.markets/docs/>
- EODHD docs : <https://eodhistoricaldata.com/financial-apis/>
- Streamlit docs : <https://docs.streamlit.io/>
- FinBERT paper : <https://arxiv.org/abs/1908.10063>
- Mark Minervini *Trade Like a Stock Market Wizard* (livre référence
  swing trade momentum)

