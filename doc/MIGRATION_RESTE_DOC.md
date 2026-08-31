# Migration du reste de l’ancien répertoire `doc`

Ce registre couvre tous les fichiers qui restaient hors `doc/refactor`. Les références globales sont conservées comme sources historiques ; les expériences sont archivées sans devenir normatives. Le code, les migrations, tests et configurations effectives restent la vérité.

| Ancien fichier | Classement | Référence courante |
|---|---|---|
| `DOC_FONCTIONNELLE.md` | source historique | [vue fonctionnelle](01_vue_fonctionnelle.md), [guide utilisateur](guide_utilisateur/README.md) |
| `DOC_TECHNIQUE.md` | source historique | [architecture](02_architecture_globale.md), [catalogue](21_catalogue_modules.md) |
| `CHANGELOG.md`, `mutation_history.md` | historique daté | [évolution](operations/evolution_et_compatibilite.md) |
| `alpha_trade_anti_overfitting_oos_protocol_2026-08-22.md` | protocole historique dont les règles durables sont reprises | [validation ML](ml/validation_et_gouvernance.md) |
| `alpha_trade_recalibration_guide.md`, `ml_calivraiton_important.md` | ancienne référence de recalibration | [recalibration/promotion](ml/recalibration_et_promotion.md) |
| `controle_couverture.md` | ancienne référence | [couverture/fallbacks](ml/qualite_couverture_et_fallbacks.md) |
| `ml_oracle.md`, `ml_oracle_sprint.md`, `oracle_extreme.md`, `model_extreme_mode.md` | anciennes spécifications/états | [Oracle actuel](ml/oracle/README.md) |
| `mode_cascade.md` | référence canonique actualisée | [mode cascade](mode_cascade.md) |
| `per_sector.md` | ancienne synthèse | [per-sector actuel](ml/per_sector/README.md) |
| `recherche_vs_pipeline.md` | analyse historique de lifecycles | [recherche/production](research/recherche_vs_production.md), [parité](backtesting/parite_live_backtest.md) |
| `ml_old/filtre_ml.md`, `ml_old/ml_hybride.md`, `ml_old/ml_refactor_1.md` | conceptions anciennes | [ML actuel](ml/README.md), [expériences](experiences/README.md) |
| `external_audit/ia1.md` | constat d’audit daté | [compliance](operations/compliance_et_audit.md) |
| `onboarding_assets/README.md`, `.gitkeep` | inventaire média historique | [guide utilisateur](guide_utilisateur/README.md) |
| `backtest_audit.md`, `rebench_canonique_postfix_tp_2026-08-19.md`, `stepB_C_timestop_parity_2026-08-19.md` | audits de runs | [expériences lifecycle](experiences/risque_execution_lifecycle.md) |
| `b4_force_close_side_attribution.md`, `e45_force_close_airbag_verdict.md`, `e46_exposure_verdict.md` | verdicts risque datés | [expériences lifecycle](experiences/risque_execution_lifecycle.md) |
| `c2_b4_breaker_go_paper_2026-08-21.md`, `go_live_b25_p14_m8_2026-08-17.md` | dossiers GO historiques | [validation/recalibration](experiences/validation_et_recalibration.md), [pré-live](operations/pre_live_et_progression.md) |
| `calibration_oracle_exterme.md`, `e17_synthese_gpt.md`, `synthese_e6_e13_2026-08-20.md` | expériences Oracle | [synthèse Oracle](experiences/oracle_extreme.md) |
| `check_performance_model_global.md`, `check_performance_model_global ask.md`, `per_sector_todo.md` | campagnes ranking/per-sector | [synthèse ranking](experiences/global_ranking_et_per_sector.md) |
| `directional_data_research.md`, `global_direction_h20.md`, `global_direction_temporal.md` | recherche directionnelle | [synthèse filtres/direction](experiences/filtres_et_direction.md) |
| `persistent_tail_price.md`, `persistent_top10_dip.md`, `Tiebreaker.md` | expériences filtres/dip | [filtres persistants](signals/filtres_persistants.md), [synthèse](experiences/filtres_et_direction.md) |
| `smart_sector_cap_verdict_2026-08-27.md`, `synthese_gestion_drawdown_reprise_2026-08-21.md` | expériences portefeuille/risque | [expériences lifecycle](experiences/risque_execution_lifecycle.md) |

Les textes intégraux de référence sont sous `sources_historiques/racine_doc`, `ml_old`, `external_audit` et `onboarding_assets`. Les journaux datés sont sous [archives_recherche](experiences/archives_recherche/README.md).

