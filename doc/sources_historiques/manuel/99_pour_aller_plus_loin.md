# 99. Pour aller plus loin

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Archive conservée pour traçabilité : les commandes, paramètres et promotions ci-dessous décrivent leur époque, pas une consigne actuelle. Ne pas réactiver un batch sur la base de ce texte. [Référence actuelle](../../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

Vous maîtrisez l'IHM. Voici la documentation **avancée** pour comprendre
le moteur ou le modifier.

## Documentation fonctionnelle

- [doc/DOC_FONCTIONNELLE.md](../racine_doc/DOC_FONCTIONNELLE.md) — vision métier complète
- [doc/DOC_TECHNIQUE.md](../racine_doc/DOC_TECHNIQUE.md) — architecture technique
- doc/ihm.md — référence historique absente localement : `../backup/ihm.md` — guide opérateur IHM complet
- [doc/onboarding_operator.md](../../guide_utilisateur/README.md) — onboarding opérateur

## Modules métier

| Module | Doc |
|---|---|
| Screener | doc/screener.md — référence historique absente localement : `../backup/screener.md` |
| Selector | doc/selector.md — référence historique absente localement : `../backup/selector.md` |
| Event Sentiment | doc/event_sentiment.md — référence historique absente localement : `../backup/event_sentiment.md` |
| ModelFactory (ML) | doc/modelFactory.md — référence historique absente localement : `../backup/modelFactory.md` |
| Risk Management | doc/risk_management.md — référence historique absente localement : `../backup/risk_management.md` |
| Execution Engine | doc/execution_engine.md — référence historique absente localement : `../backup/execution_engine.md` |
| Corporate Actions | doc/corporate_actions.md — référence historique absente localement : `../backup/corporate_actions.md` |
| Backtesting | doc/backtesting.md — référence historique absente localement : `../backup/backtesting.md` |
| Data Integrity | doc/dataIntegrityEngine.md — référence historique absente localement : `../backup/dataIntegrityEngine.md` |
| Watcher | [doc/watcher.md](../backup/execution/watcher.md) |

## Architecture & qualité

- [doc/architecture/](../../02_architecture_globale.md) — diagrammes
- doc/database.md — référence historique absente localement : `../backup/database.md` — schéma DB
- [doc/data_lineage_matrix.md](../backup/data/data_lineage_matrix.md)
- [doc/observability.md](../backup/operations/observability.md)
- [doc/perf_pipeline.md](../../operations/performance_et_capacite.md)
- [doc/perf_hotspots.md](../../operations/performance_et_capacite.md)

## Runbooks ops

- [doc/runbook_24_7.md](../../operations/us_pipeline.md)
- [doc/runbook_provider_incident.md](../backup/operations/runbook_provider_incident.md)
- [doc/runbook_reconciliation.md](../backup/operations/runbook_reconciliation.md)
- [doc/sandbox_health_runbook.md](../../operations/sandbox_health.md)
- [doc/disaster_recovery.md](../../operations/sauvegarde_reprise_et_retention.md)

## Conformité & audit

- [doc/external_audit_checklist.md](../../operations/compliance_et_audit.md)
- [doc/external_audit_engagement.md](../../operations/compliance_et_audit.md)
- [doc/pre_audit_findings.md](../../operations/compliance_et_audit.md)
- [doc/pre_live_checklist.md](../../operations/pre_live_et_progression.md)
- [doc/artifacts_retention_policy.md](../../operations/sauvegarde_reprise_et_retention.md)

## Audits internes (Sprint S26)

- [doc/audit/matrice_ihm_cli.md](../../guide_utilisateur/COUVERTURE_PAGES_IHM.md) — matrice
  IHM ↔ CLI et gaps
- [doc/audit/preset_petit_capital_2000eur.md](../../risk/capital_sizing_et_fractionnement.md)
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

