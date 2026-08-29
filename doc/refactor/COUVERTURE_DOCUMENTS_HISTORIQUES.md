# Couverture des documents historiques

## But et règle de migration

Cet inventaire couvre les **178 fichiers Markdown** présents hors
`doc/refactor` lors de l’audit. Il indique où retrouver leur connaissance utile
dans la refonte. Il ne certifie pas le contenu historique : le code courant a
été utilisé comme source de vérité.

Les fichiers historiques restent physiquement inchangés. « Expérience » signifie
qu’une synthèse autonome est créée sous `experiences/`, pas que le journal
d’expérience est recopié. « Archive » signifie que le fichier est un doublon,
un audit ponctuel, une proposition ou un état de migration et n’a pas vocation à
devenir une référence courante.

## Références générales racine

| Ancien document | Destination dans la refonte | Traitement |
|---|---|---|
| `DOC_FONCTIONNELLE.md` | [Vue fonctionnelle](01_vue_fonctionnelle.md), [workflow](guide_utilisateur/02_workflow_quotidien.md), guides modules | réécrit et réparti |
| `DOC_TECHNIQUE.md` | [Architecture globale](02_architecture_globale.md), [base](15_base_de_donnees.md), docs modules | réécrit et réparti |
| `CHANGELOG.md`, `mutation_history.md` | [Évolution et compatibilité](operations/evolution_et_compatibilite.md) | synthèse ; historique brut non substitué |
| `backtest_audit.md` | [Backtesting](12_backtesting_validation.md), [validation statistique/PIT](backtesting/validation_statistique.md), [guide opérateur](guide_utilisateur/08_backtesting.md) | règles actuelles, constats ponctuels synthétisés |
| `recherche_vs_pipeline.md` | [Recherche vs production](research/recherche_vs_production.md), [pipeline](04_pipeline_quotidien.md) | réécrit selon les chemins actuels |
| `controle_couverture.md` | [Qualité et couverture ML](ml/qualite_couverture_et_fallbacks.md) | référence dédiée |
| `alpha_trade_recalibration_guide.md` | [Recalibration](ml/recalibration_et_promotion.md), [calibrations IHM](guide_utilisateur/09_supervision_parite.md) | réécrit |
| `alpha_trade_anti_overfitting_oos_protocol_2026-08-22.md` | [Validation et gouvernance](ml/validation_et_gouvernance.md) | protocole durable extrait |
| `per_sector.md`, `per_sector_todo.md` | [Per-sector détaillé](ml/per_sector/README.md), [Global Ranking détaillé](ml/global_ranking/README.md), [synthèse historique](experiences/global_ranking_et_per_sector.md) | état courant + synthèse |
| `mode_cascade.md` | [Cascade et fallback](ml/cascade_et_fallbacks.md) | réécrit |
| `model_extreme_mode.md`, `oracle_extreme.md` | [Oracle Extreme](ml/oracle/README.md) | remplacé par dossier détaillé |
| `ml_oracle.md`, `ml_oracle_sprint.md`, `calibration_oracle_exterme.md` | [Oracle architecture à diagnostics](ml/oracle/README.md), [expériences Oracle](experiences/oracle_extreme.md) | référence et historique séparés |
| `persistent_tail_price.md`, `persistent_top10_dip.md` | [Filtres persistants](signals/filtres_persistants.md), [expériences filtres](experiences/filtres_et_direction.md) | contrat actuel + synthèse |
| `Tiebreaker.md` | [Championnat et tie-break](ml/global_ranking/04_train_walk_forward_et_championnat.md) | intégré |
| `directional_data_research.md`, `global_direction_h20.md`, `global_direction_temporal.md` | [Expériences direction](experiences/filtres_et_direction.md) | synthèse uniquement |
| `check_performance_model_global.md`, `check_performance_model_global ask.md` | [Diagnostic global ranking](07_ml_global_ranking.md), [expériences](experiences/global_ranking_et_per_sector.md) | synthèse |
| `ml_calivraiton_important.md` | [Recalibration et promotion](ml/recalibration_et_promotion.md) | règles mises à jour |

## Journaux de recherche et verdicts datés

Ces fichiers sont couverts par les synthèses thématiques. Les chiffres et
verdicts datés restent historiques et ne sont pas présentés comme configuration
active.

| Fichiers | Synthèse |
|---|---|
| `b4_force_close_side_attribution.md`, `e45_force_close_airbag_verdict.md`, `stepB_C_timestop_parity_2026-08-19.md` | [Risque, exécution et lifecycle](experiences/risque_execution_lifecycle.md) |
| `e46_exposure_verdict.md`, `smart_sector_cap_verdict_2026-08-27.md`, `synthese_gestion_drawdown_reprise_2026-08-21.md` | [Risque, exécution et lifecycle](experiences/risque_execution_lifecycle.md) |
| `c2_b4_breaker_go_paper_2026-08-21.md`, `go_live_b25_p14_m8_2026-08-17.md` | [Validation/recalibration](experiences/validation_et_recalibration.md) |
| `rebench_canonique_postfix_tp_2026-08-19.md`, `synthese_e6_e13_2026-08-20.md`, `e17_synthese_gpt.md` | [Risque/lifecycle](experiences/risque_execution_lifecycle.md) et [Oracle](experiences/oracle_extreme.md) |

## Ancien manuel utilisateur (22 fichiers)

| Ancien manuel | Nouveau guide |
|---|---|
| `manuel/00_README.md`, `01_demarrage_rapide.md`, `02_premiers_pas_ihm.md` | [Index](guide_utilisateur/README.md), [démarrage](guide_utilisateur/01_demarrage_navigation_securite.md) |
| `manuel/03_workflow_quotidien.md` | [Workflow](guide_utilisateur/02_workflow_quotidien.md) |
| `manuel/04_page_pipeline.md` | [Pipeline](guide_utilisateur/03_pipeline.md) |
| `manuel/05_page_screening.md` | [Screening](guide_utilisateur/04_screening.md) |
| `manuel/06_page_ml_predictions.md` | [ML / Prédictions](guide_utilisateur/05_ml_predictions.md) |
| `manuel/07_page_risk.md` | [Risk](guide_utilisateur/06_risque.md) |
| `manuel/08_page_execution.md` | [Execution](guide_utilisateur/07_execution.md) |
| `manuel/09_page_corporate_actions.md` | [Conformité et CA](guide_utilisateur/10_conformite_corporate_actions.md) |
| `manuel/10_page_backtesting.md` | [Backtesting](guide_utilisateur/08_backtesting.md) |
| `manuel/11_page_parity.md`, `12_page_supervision_ops.md` | [Supervision et parité](guide_utilisateur/09_supervision_parite.md) |
| `manuel/17_page_settings.md` | [Paramètres/admin](guide_utilisateur/11_parametres_administration.md) |
| `manuel/20_gestion_petit_capital_2000eur.md`, `40_workflow_type_swing_2000eur.md` | [Capital et sizing](risk/capital_sizing_et_fractionnement.md), [workflow](guide_utilisateur/02_workflow_quotidien.md) ; les montants historiques ne sont pas des recommandations |
| `manuel/30_glossaire_financier.md`, `31_glossaire_application.md` | [Glossaire unifié](20_glossaire.md) |
| `manuel/50_faq.md`, `51_depannage.md` | [Dépannage/FAQ](guide_utilisateur/12_depannage_faq.md) |
| `manuel/52_securite_et_argent_reel.md` | [Sécurité opérateur](guide_utilisateur/01_demarrage_navigation_securite.md), [sécurité live](operations/securite_live.md) |
| `manuel/99_pour_aller_plus_loin.md` | [Index général](README.md) |

## Ancienne documentation ML

| Fichiers | Destination |
|---|---|
| `ml/features_ml.md` | [Features ML](ml/features_et_dataset.md) |
| `ml/module_model_factory.md` | [ML vue d'ensemble](06_ml_vue_ensemble.md) et [entraînement/serving](ml/entrainement_serving_et_gouvernance.md) |
| `ml/ordre_execution_ml.md` | [Pipeline ML](ml/ordre_execution_et_dependances.md) |
| `ml/ml_todo.md` | backlog historique, sujets réalisés documentés par [ML](ml/README.md) |
| `ml/synthese_long_short.md` | [Expériences filtres/direction](experiences/filtres_et_direction.md) |
| `ml/synthese_per_symbol_v2_2026-08-19.md` | [Per-symbol détaillé](ml/per_symbol/README.md), [expériences](experiences/global_ranking_et_per_sector.md) |
| `ml/synthese_s7_feature_whitelist_2026-08-18.md` | [Features/dataset](ml/features_et_dataset.md), [validation historique](experiences/validation_et_recalibration.md) |
| `ml/synthese_tp_risk_execution_2026-08-18.md` | [Expériences lifecycle](experiences/risque_execution_lifecycle.md) |
| `ml/global_per_symbol/test/test_global_per_symbol.md` | [Per-symbol détaillé](ml/per_symbol/README.md), [expériences ranking/per-symbol](experiences/global_ranking_et_per_sector.md) |
| `ml_old/filtre_ml.md`, `ml_old/ml_hybride.md`, `ml_old/ml_refactor_1.md` | archives de conception ; concepts encore actifs couverts par [ML](ml/README.md) |

## Campagnes B0–B44 Global/Per-Sector (41 fichiers)

Tous les fichiers sous `ml/global_per_sector/test/` — `B0`, `B1`, `B2`, `B3`,
`B4`, `B5`, `B6`, `B7`, `B8`, `B9`, `B10`, `B11`, `B12`, `B13`, `B14`,
`B15`, `B16`, `B17`, `B18`, `B19`, `B20`, `B21`, `B22`, `B25`, `B26`,
`B27`, `B30`, `B31`, `B32`, `B33`, `B34`, `B35`, `B36`, `B37`, `B38`,
`B39`, `B40`, `B41`, `B42`, `B44` — ainsi que
`test_global_per_sector.md`, sont des journaux d’expérience.

Leur enseignement est condensé dans
[Expériences Global Ranking et per-sector](experiences/global_ranking_et_per_sector.md).
Le contrat exécutable actuel est documenté dans
[Global Ranking détaillé](ml/global_ranking/README.md), [features](ml/features_et_dataset.md) et
[entraînement/serving](ml/entrainement_serving_et_gouvernance.md). Les noms de
campagnes ne sont pas assimilés à des modèles actifs.

## `doc/backup` (64 fichiers)

Le répertoire est traité comme une archive historique, mais ses thèmes utiles
ont une destination explicite :

| Groupe de fichiers backup | Destination actuelle |
|---|---|
| `INDEX`, `CONVENTIONS`, `core_common`, `service`, `phase_f_implementation`, `relecture_phase_g`, audits/todo | [Architecture globale](02_architecture_globale.md), [tests/contribution](19_tests_et_contribution.md) |
| `database`, `guide_add_new_table`, `sector_normalization_full_production_sql`, `async_db_*`, `perf_*` | [Base de données](15_base_de_donnees.md), [schéma métier](database/schema_metier.md), [performance](operations/performance_et_capacite.md) |
| `dataIntegrityEngine`, `data_lineage_matrix`, `formal_verification`, `tlaps_proofs`, `fuzz_diff`, `mutation_*` | [Intégrité et lineage](data/integrite_lineage_et_qualite.md), [tests](19_tests_et_contribution.md) |
| `corporate_actions`, `EODHD_vs_Alpaca`, `macro_regime`, `mode_regime`, `event_sentiment`, `pipelin_sentiment`, `sentiment_issue`, `sentiments_migration` | [Données](data/README.md), [screener/sentiment](13_screener_selector_sentiment.md), [régime](10_regime_marche.md) |
| `ml`, `modelFactory`, `ml_regime_ablation`, `poid`, `AlignementEchelles`, `calcul_tp_tl` | [ML](ml/README.md), [expériences](experiences/README.md) |
| `selector`, `selector-driven`, `selector_pipeline_compatibility`, `screener` | [Sélection/screener](signals/selection_et_scoring.md) |
| `risk_management`, `execution_engine`, `watcher`, `ibkr_setup` | [Risque](risk/README.md), [exécution](execution/README.md) |
| `backtesting`, `backtesting_report_schema` | [Backtesting](backtesting/README.md) |
| `ihm`, `onboarding_operator`, `onboarding_video_script` | [Guide utilisateur](guide_utilisateur/README.md) ; script vidéo non conservé comme référence |
| `observability`, `runbook_24_7`, `runbook_broker_failover`, `runbook_provider_incident`, `runbook_reconciliation`, `sandbox_health_runbook`, `pre_live_checklist` | [Runbook](22_runbook_exploitation.md), [sécurité live](operations/securite_live.md) |
| `disaster_recovery`, `artifacts_retention_policy` | [Sauvegarde et reprise](operations/sauvegarde_reprise_et_retention.md) |
| `api_v1_stability_policy` | [API et compatibilité](api/README.md) |
| `external_audit_*`, `pre_audit_findings` | [Compliance/audit](operations/compliance_et_audit.md) ; modèles de mission restent archives |
| `AUDIT_2026_05_22_doc_updates`, `audit_alignment_tod2`, `question_1` | audits ponctuels, pas de référence runtime |

## Autres archives

- `external_audit/ia1.md` : constat d’audit historique, synthétisé dans les
  références actuelles concernées, pas recopié.
- `onboarding_assets/README.md` : inventaire d’assets historiques ; le parcours
  d’onboarding actuel est [Guide utilisateur](guide_utilisateur/README.md).

## Critère de suppression future des anciens documents

Avant suppression manuelle par le propriétaire, vérifier :

1. tous les liens internes de `doc/refactor` sont valides ;
2. chaque destination ci-dessus existe ;
3. les exemples de configuration sont comparés au chargeur actuel ;
4. aucune destination ne dépend d’un lien vers un ancien document ;
5. les journaux expérimentaux à conserver pour preuve sont archivés hors du
   corpus documentaire courant, même si leur synthèse suffit à l’onboarding.
