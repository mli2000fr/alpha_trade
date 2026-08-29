# Migration exhaustive de `doc/backup`

Cette matrice suit les 64 fichiers trouvés le 29 août 2026. La destination est autonome sous `doc/refactor`; le code courant prime. Audits, plans et expériences ne sont repris qu’en synthèse. Une archive n’est supprimable qu’après destination et validation des liens.

| Archive | Traitement et destination maintenue |
|---|---|
| `AlignementEchelles.md` | unités/calibration dans [scoring](signals/selection_et_scoring.md) et [recalibration](ml/recalibration_et_promotion.md) |
| `api_v1_stability_policy.md` | réécrit dans [stabilité API](api/stabilite_v1_et_deprecation.md) |
| `artifacts_retention_policy.md` | règles du script dans [rétention](operations/sauvegarde_reprise_et_retention.md) |
| `async_db_benchmark.md` | résultat historique dans [POC async](database/async_db_poc.md) |
| `async_db_poc.md` | contrat actuel dans [POC async](database/async_db_poc.md) |
| `AUDIT_2026_05_22_doc_updates.md` | audit daté absorbé par [audit refonte](AUDIT_REMPLACEMENT.md) |
| `audit_alignment_tod2.md` | migration historique absorbée par [couverture](COUVERTURE_DOCUMENTS_HISTORIQUES.md) |
| `backtesting_report_schema.md` | réécrit dans [`report.json`](backtesting/report_json_et_artefacts.md) |
| `backtesting.md` | réparti dans [backtesting](backtesting/README.md) et [guide](guide_utilisateur/08_backtesting.md) |
| `calcul_tp_tl.md` | [lifecycle](execution/lifecycle_ordres.md) et [parité](backtesting/parite_live_backtest.md) |
| `CONVENTIONS.md` | [configuration](18_reference_configuration.md) et [glossaire](20_glossaire.md) |
| `core_common.md` | [architecture](02_architecture_globale.md) et [API core/common](api/README.md) |
| `corporate_actions.md` | [vue](17_corporate_actions.md) et [référence](operations/corporate_actions_reference.md) |
| `data_lineage_matrix.md` | remplacé par [lineage](data/integrite_lineage_et_qualite.md) et [schéma](database/schema_metier.md) |
| `database.md` | [base](15_base_de_donnees.md) et [database](database/schema_metier.md) |
| `dataIntegrityEngine.md` | [données](data/README.md) et [API](api/dataIntegrityEngine.md) |
| `disaster_recovery.md` | corrigé dans [reprise](operations/sauvegarde_reprise_et_retention.md) |
| `EODHD_vs_Alpaca.md` | [EODHD](data/ingestion_eodhd.md) et [services](14_services_externes.md) |
| `event_sentiment.md` | [sentiment](signals/event_sentiment_reference.md) et [API](api/event_sentiment.md) |
| `execution_engine.md` | [exécution](execution/README.md) et [API](api/execution_engine.md) |
| `external_audit_checklist.md` | [compliance](operations/compliance_et_audit.md) |
| `external_audit_engagement.md` | modèle historique synthétisé dans [compliance](operations/compliance_et_audit.md) |
| `external_audit_findings_template.md` | structure synthétisée dans [compliance](operations/compliance_et_audit.md) |
| `formal_verification.md` | [qualité avancée](operations/qualite_avancee_fuzz_mutation_formel.md) |
| `fuzz_diff.md` | [qualité avancée](operations/qualite_avancee_fuzz_mutation_formel.md) |
| `guide_add_new_table.md` | [migrations](database/migrations_et_transactions.md) et [contribution](19_tests_et_contribution.md) |
| `ibkr_setup.md` | corrigé dans [IBKR](execution/ibkr.md) et [failover](operations/broker_failover.md) |
| `ihm.md` | [guide utilisateur](guide_utilisateur/README.md) et [IHM](operations/ihm_reference.md) |
| `INDEX.md` | remplacé par [index](README.md) |
| `macro_regime.md` | [régime](10_regime_marche.md) |
| `ml_regime_ablation.md` | expérience synthétisée dans [validation](experiences/validation_et_recalibration.md) |
| `ml.md` | réparti dans [ML](ml/README.md) |
| `mode_regime.md` | [régime](10_regime_marche.md) et [paramètres](guide_utilisateur/11_parametres_administration.md) |
| `modelFactory.md` | [ML](ml/README.md) et [API](api/modelFactory.md) |
| `mutation_history.md` | journal daté synthétisé dans [évolution](operations/evolution_et_compatibilite.md) |
| `mutation_testing.md` | [qualité avancée](operations/qualite_avancee_fuzz_mutation_formel.md) |
| `observability.md` | [métriques](operations/alerting_et_metriques.md) et [supervision](operations/supervision_et_securite.md) |
| `onboarding_operator.md` | [guide](guide_utilisateur/README.md) et [runbook](22_runbook_exploitation.md) |
| `onboarding_video_script.md` | média daté remplacé par [démarrage](guide_utilisateur/01_demarrage_navigation_securite.md) |
| `perf_hotspots.md` | hypothèses historiques dans [performance](operations/performance_et_capacite.md) |
| `perf_pipeline.md` | benchmarks historiques dans [performance](operations/performance_et_capacite.md) |
| `phase_f_implementation.md` | livraison historique absorbée par [architecture](02_architecture_globale.md) |
| `pipelin_sentiment.md` | [sentiment](signals/event_sentiment_reference.md) |
| `poid.md` | [scoring](signals/selection_et_scoring.md) et [recalibration](ml/recalibration_et_promotion.md) |
| `pre_audit_findings.md` | constats datés synthétisés dans [compliance](operations/compliance_et_audit.md) |
| `pre_live_checklist.md` | corrigé dans [pré-live](operations/pre_live_et_progression.md) |
| `question_1.md` | Q/R réparties dans le [guide](guide_utilisateur/README.md) et la [FAQ](guide_utilisateur/12_depannage_faq.md) |
| `relecture_phase_g.md` | revue datée absorbée par [audit](AUDIT_REMPLACEMENT.md) |
| `risk_management.md` | [risque](risk/README.md) et [API](api/risk_management.md) |
| `runbook_24_7.md` | scénarios actuels dans [runbook](22_runbook_exploitation.md) et [opérations](operations/) |
| `runbook_broker_failover.md` | [failover](operations/broker_failover.md) |
| `runbook_provider_incident.md` | [runbook](22_runbook_exploitation.md) et [services](14_services_externes.md) |
| `runbook_reconciliation.md` | [réconciliation](execution/reconciliation_et_tca.md) |
| `sandbox_health_runbook.md` | [sandbox health](operations/sandbox_health.md) |
| `screener.md` | [screener](signals/screener_reference.md) et [API](api/README.md) |
| `sector_normalization_full_production_sql.md` | remplacé par [schéma](database/schema_metier.md) et [migrations](database/migrations_et_transactions.md) |
| `selector_pipeline_compatibility.md` | [selector](signals/selector_reference.md) et [pipeline](04_pipeline_quotidien.md) |
| `selector-driven.md` | conception historique dans [scoring](signals/selection_et_scoring.md) |
| `selector.md` | [selector](signals/selector_reference.md) et [API](api/selector.md) |
| `sentiment_issue.md` | incident historique synthétisé dans [sentiment](signals/event_sentiment_reference.md) |
| `sentiments_migration.md` | résultat actuel dans [sentiment](signals/event_sentiment_reference.md) |
| `service.md` | [services](14_services_externes.md) et [API](api/service.md) |
| `tlaps_proofs.md` | [qualité avancée](operations/qualite_avancee_fuzz_mutation_formel.md) |
| `watcher.md` | [protections/watcher](execution/protections_et_watcher.md) et [runbook](22_runbook_exploitation.md) |

## Fichiers non Markdown découverts dans `doc/backup`

| Archive | Traitement |
|---|---|
| `api_v1_public_symbols.txt` | snapshot historique conservé sous `sources_historiques/backup/general`; le contrat courant est [stabilité API](api/stabilite_v1_et_deprecation.md) et les inventaires `api/` |
| `question.txt` | questions historiques conservées sous `sources_historiques/backup/ihm`; parcours courant dans le [guide utilisateur](guide_utilisateur/README.md) |

## Migration de `doc/ml`

Les trois références générales ont été conservées sous `sources_historiques/backup/ml` : `features_ml.md`, `module_model_factory.md` et `ordre_execution_ml.md`. Leurs contrats courants sont respectivement [features/dataset](ml/features_et_dataset.md), [architecture ML](ml/README.md) et [ordre d’exécution](ml/ordre_execution_et_dependances.md).

Les campagnes `global_per_sector/test` B0–B44 et le test per-symbol ont été déplacés intégralement sous [campagnes Global Ranking](experiences/campagnes_global_ranking/README.md). Ils restent des preuves historiques ; leur synthèse maintenue est [Global Ranking et per-sector](experiences/global_ranking_et_per_sector.md).

`analyse_oos.txt`, `ml_todo.md`, `synthese_long_short.md`, `synthese_per_symbol_v2_2026-08-19.md`, `synthese_s7_feature_whitelist_2026-08-18.md` et `synthese_tp_risk_execution_2026-08-18.md` sont sous [archives ML](experiences/archives_ml/README.md). Les verdicts encore utiles sont synthétisés dans `experiences/`; les TODO et chiffres datés ne deviennent pas configuration active.

## Migration de `doc/monitoring`

Les deux actifs ont été déplacés sous [operations/monitoring](operations/monitoring/README.md). Ils n’ont pas été copiés tels quels : leurs anciennes expressions visaient six métriques inexistantes. Les règles et le dashboard utilisent désormais le registre réellement exposé par `service/prometheus_metrics.py` : erreurs API, runs d’exécution, alertes, circuit breaker, heartbeat stale, univers vide, kill switch, drift et alignement cash.

## Statut des textes intégraux

Les anciens guides volumineux qui mélangent connaissances et valeurs obsolètes sont conservés sous [sources historiques](sources_historiques/README.md), hors parcours d’onboarding. Leur contenu utile a une destination normative dans la matrice ci-dessus. Ce classement évite à la fois la perte d’information et la présentation d’une ancienne commande comme contrat courant.

## Contrôle final

Après migration : les répertoires `doc/backup`, `doc/ml` et `doc/monitoring` n’existent plus. Aucun code source n’a été modifié. Les liens du corpus maintenu sont validés séparément des liens internes aux snapshots historiques, qui peuvent volontairement viser leur ancien contexte.
