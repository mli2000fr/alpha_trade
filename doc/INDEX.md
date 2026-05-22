# Index de la documentation Alpha Trade

> Généré automatiquement par `scripts/generate_doc_index.py` le 2026-05-22.
> 89 documents indexés.

## Sommaire

* [API & Stabilité](#api-stabilité) (4)
* [Architecture](#architecture) (3)
* [Audit externe](#audit-externe) (1)
* [Conformité & Audit](#conformité-audit) (6)
* [Divers](#divers) (53)
* [Documentation centrale](#documentation-centrale) (4)
* [Documentation utilisateur](#documentation-utilisateur) (3)
* [Performance](#performance) (4)
* [Runbooks & Ops](#runbooks-ops) (4)
* [Tests & Vérification](#tests-vérification) (7)

## API & Stabilité

| Document | Titre | Description |
|---|---|---|
| [`manuel/01_demarrage_rapide.md`](manuel/01_demarrage_rapide.md) | 1. Démarrage rapide — installer et lancer l'IHM | Objectif : à la fin de ce manuel vous voyez la page d'accueil de l'IHM |
| [`manuel/20_gestion_petit_capital_2000eur.md`](manuel/20_gestion_petit_capital_2000eur.md) | 20. Guide micro-compte ~2 000 € — paramétrage et bonnes pratiques | Ce manuel est **incontournable** si vous démarrez avec ~2 000 € (~2 150 USD). |
| [`api_v1_stability_policy.md`](api_v1_stability_policy.md) | Politique de stabilité API v1.0 | Phase C / S18.2. |
| [`audit/preset_petit_capital_2000eur.md`](audit/preset_petit_capital_2000eur.md) | Preset micro-compte (~2 000 €) — analyse & justification | **Sprint S26** — adaptation du paramétrage swing trade pour un capital initial |

## Architecture

| Document | Titre | Description |
|---|---|---|
| [`architecture/c4_component.md`](architecture/c4_component.md) | C4 Model — Niveau 3 : Composants Execution Engine | Phase C / S18.1. Zoom sur le container Execution Engine (le plus |
| [`architecture/c4_container.md`](architecture/c4_container.md) | C4 Model — Niveau 2 : Containers | Phase C / S18.1. Décomposition d'Alpha Trade en applications/services |
| [`architecture/c4_context.md`](architecture/c4_context.md) | C4 Model — Niveau 1 : Contexte système | Phase C / S18.1. Format Mermaid C4. Voir aussi `c4_container.md` et |

## Audit externe

| Document | Titre | Description |
|---|---|---|
| [`external_audit/ia1.md`](external_audit/ia1.md) | Audit externe IA — Alpha Trade | _Date : 2026-05-13_ |

## Conformité & Audit

| Document | Titre | Description |
|---|---|---|
| [`AUDIT_2026_05_22_doc_updates.md`](AUDIT_2026_05_22_doc_updates.md) | Note de réalignement documentaire — Audit 2026-05-22 | Cette note consolide les mises à jour documentaires identifiées par |
| [`audit_alignment_tod2.md`](audit_alignment_tod2.md) | Addendum documentaire — Audit `prompt/tod2` (2026-05-22) | Cet addendum réaligne les conventions documentaires avec le code courant audité. Il complète `DOC_FONCTIONNELLE.md`, `DOC_TECHNIQUE.md`, `da |
| [`external_audit_checklist.md`](external_audit_checklist.md) | Checklist d'auto-audit externe — Phase C / S18.3 | Substitut documentaire à l'audit externe humain (qui reste à |
| [`external_audit_engagement.md`](external_audit_engagement.md) | Engagement audit externe — Lettre de mission template | Sprint S25.2 — Phase G. |
| [`external_audit_findings_template.md`](external_audit_findings_template.md) | Rapport d'audit externe — Template | Sprint S25.2 — à compléter par l'auditeur externe. |
| [`pre_audit_findings.md`](pre_audit_findings.md) | Findings du pré-audit interne — registre | Sprint S25.1 — Phase G. |

## Divers

| Document | Titre | Description |
|---|---|---|
| [`manuel/00_README.md`](manuel/00_README.md) | 📖 Manuels utilisateur — Alpha Trade IHM | **Public visé** : utilisateur débutant, n'ayant **jamais** utilisé |
| [`manuel/02_premiers_pas_ihm.md`](manuel/02_premiers_pas_ihm.md) | 2. Premiers pas dans l'IHM — visite guidée | Objectif : comprendre la structure de l'interface. **Aucun lancement** ici, |
| [`manuel/03_workflow_quotidien.md`](manuel/03_workflow_quotidien.md) | 3. Workflow quotidien — comprendre le cycle complet | Objectif : comprendre **dans quel ordre** les choses doivent être lancées |
| [`manuel/04_page_pipeline.md`](manuel/04_page_pipeline.md) | 4. Page 🔄 Pipeline — orchestrer le cycle quotidien | C'est la page la plus utilisée. Elle permet de : |
| [`manuel/05_page_screening.md`](manuel/05_page_screening.md) | 5. Page 📊 Screening — l'univers des candidats | Consulter la table `stock_scores` produite par les étapes Screener + |
| [`manuel/06_page_ml_predictions.md`](manuel/06_page_ml_predictions.md) | 6. Page 🤖 ML / Prédictions — comprendre le modèle d'IA | Voir et gérer les **modèles de Machine Learning** qui prédisent la |
| [`manuel/07_page_risk.md`](manuel/07_page_risk.md) | 7. Page ⚖️ Risk — gestion du risque | Voir les **décisions de risque** : combien acheter de chaque ligne, où |
| [`manuel/08_page_execution.md`](manuel/08_page_execution.md) | 8. Page 🚀 Execution — envoyer les ordres au broker | Voir et superviser les **runs d'exécution** : quels ordres ont été envoyés |
| [`manuel/09_page_corporate_actions.md`](manuel/09_page_corporate_actions.md) | 9. Page 📑 Corporate Actions — dividendes, splits, etc. | Voir les **événements corporate** (dividendes, splits, fusions, spin-offs) |
| [`manuel/11_page_parity.md`](manuel/11_page_parity.md) | 11. Page 🔀 Parité Backtest ↔ Live | Comparer les décisions **simulées** (backtest) aux décisions **réelles** |
| [`manuel/12_page_supervision_ops.md`](manuel/12_page_supervision_ops.md) | 12. Page 🛟 Supervision Ops | Surveiller les **processus en arrière-plan** : pipeline qui tournent encore, |
| [`manuel/17_page_settings.md`](manuel/17_page_settings.md) | 17. Page ⚙️ Paramètres / Santé | ML, Sentiment, Execution). |
| [`manuel/30_glossaire_financier.md`](manuel/30_glossaire_financier.md) | 30. Glossaire financier | Définitions volontairement simples, en français, illustrées. |
| [`manuel/31_glossaire_application.md`](manuel/31_glossaire_application.md) | 31. Glossaire technique de l'application | Termes spécifiques au code, à la base de données et aux artefacts. |
| [`manuel/40_workflow_type_swing_2000eur.md`](manuel/40_workflow_type_swing_2000eur.md) | 40. Workflow type swing trader débutant ~2 000 € | Journée type, heure par heure, pour une routine **swing trade discipline |
| [`manuel/50_faq.md`](manuel/50_faq.md) | 50. FAQ — questions fréquentes des débutants | Comptez **6 mois minimum** : 2 mois en simulate + 3 mois en paper + |
| [`manuel/51_depannage.md`](manuel/51_depannage.md) | 51. Dépannage | Mauvais `ALPACA_API_KEY` / `_SECRET`. Régénérez-les sur |
| [`manuel/52_securite_et_argent_reel.md`](manuel/52_securite_et_argent_reel.md) | 52. Sécurité & passage en argent réel — checklist obligatoire | ⚠️ **Lisez ce document en entier avant tout passage en mode `live`.** |
| [`manuel/99_pour_aller_plus_loin.md`](manuel/99_pour_aller_plus_loin.md) | 99. Pour aller plus loin | Vous maîtrisez l'IHM. Voici la documentation **avancée** pour comprendre |
| [`EODHD_vs_Alpaca.md`](EODHD_vs_Alpaca.md) | EODHD vs Alpaca (IEX) — usage réel du volume dans l'application | Date d'analyse : 2026-05-10 |
| [`onboarding_assets/README.md`](onboarding_assets/README.md) | Assets vidéo onboarding | Sprint S25.3 — Phase G. |
| [`artifacts_retention_policy.md`](artifacts_retention_policy.md) | Politique de rétention `artifacts/` (Sprint S4 — A-023) | **Audience** : opérateurs / DevOps. |
| [`core_common.md`](core_common.md) | `core/` + `common/` — Modules de socle | Documentation Phase 2.1 du refactor (`prompt/refactor/plan.md`). |
| [`corporate_actions.md`](corporate_actions.md) | corporate_actions | — |
| [`dataIntegrityEngine.md`](dataIntegrityEngine.md) | Data Integrity Engine — documentation détaillée de reprise | ✅ **Provider OHLCV primaire actuel : `EODHD` (bulk EOD consolidé).** |
| [`data_lineage_matrix.md`](data_lineage_matrix.md) | Matrice Data Lineage — table ↔ producteur ↔ consommateurs (Phase 7.6) | **Audience** : développeurs et opérateurs. |
| [`database.md`](database.md) | Database — Guide d'usage | Ce document résume le rôle du module `database/` et les usages utiles pour : |
| [`disaster_recovery.md`](disaster_recovery.md) | Disaster Recovery — Alpha Trade | Sprint **S12.1** — Phase B (Industrialisation pro-grade). |
| [`event_sentiment.md`](event_sentiment.md) | Event Sentiment — Guide d'usage | Ce document résume le fonctionnement du module `event_sentiment/` et les commandes utiles pour : |
| [`execution_engine.md`](execution_engine.md) | Execution Engine — Guide d'usage | Ce document résume le fonctionnement du module `execution_engine/` et les commandes utiles pour : |
| [`ibkr_setup.md`](ibkr_setup.md) | Configuration TWS / IB Gateway pour Alpha Trade — Sprint S21.3 | Ce document décrit la qualification d'un environnement Interactive Brokers |
| [`ihm.md`](ihm.md) | IHM — Guide d'usage | Ce document résume le fonctionnement du module `ihm/` et les commandes utiles pour : |
| [`audit/matrice_ihm_cli.md`](audit/matrice_ihm_cli.md) | Matrice IHM ↔ CLI — couverture des fonctionnalités | **Sprint S26 — gaps comblés (2026-05-06)** : tous les gaps P1, P2 et P3 |
| [`mode_regime.md`](mode_regime.md) | FAQ et Explications — Mode régime Market-Aware | Avec la config corrigée, le comportement normal est : |
| [`modelFactory.md`](modelFactory.md) | Model Factory — Référence complète | `modelFactory/` est le module ML opérationnel du projet. Il ne se limite plus à un simple entraînement LSTM par symbole. |
| [`observability.md`](observability.md) | Observabilité — Endpoint `/metrics` Prometheus (Phase 7.5) | **Audience** : opérateurs Alpha Trade. |
| [`phase_f_implementation.md`](phase_f_implementation.md) | Phase F — Mesures effectives (Sprints S22 + S23) — Récap d'implémentation | Statut : **infrastructure livrée et fonctionnelle** ; les itérations |
| [`pipelin_sentiment.md`](pipelin_sentiment.md) | Pipeline sentiment — notes de synthèse | Cette note résume les explications utiles sur le pipeline sentiment du projet, en particulier : |
| [`pre_live_checklist.md`](pre_live_checklist.md) | Recette pré-live (Sprint S5 — A-013 + A-008) | **Audience** : opérateur en charge d'une bascule d'un compte Alpaca de |
| [`question_1.md`](question_1.md) | Réponses détaillées à `doc/question.txt` | Document rédigé à partir du code, de la documentation et des tests présents dans le workspace. |
| [`relecture_phase_g.md`](relecture_phase_g.md) | Relecture documentation — Phase G (Sprint S25.5) | Checklist humaine : passer en revue tous les fichiers `doc/` pour |
| [`risk_management.md`](risk_management.md) | Risk Management — Guide d'usage | Ce document résume le fonctionnement du module `risk_management/` et les commandes utiles pour : |
| [`sandbox_health_runbook.md`](sandbox_health_runbook.md) | Runbook — Sandbox health (régression nightly) | Sprint S24.2 — Phase G. |
| [`screener.md`](screener.md) | Screener — Guide d'usage | Ce document résume le fonctionnement du module `screener/` et les commandes utiles pour : |
| [`sector_normalization_full_production_sql.md`](sector_normalization_full_production_sql.md) | 🧠 ISecteurs métier principaux | sector_code sector_name |
| [`selector-driven.md`](selector-driven.md) | Contrat selector-driven | Ce document fige le contrat **selector-driven** aujourd’hui exposé côté opérateur et consommé par les briques avales `modelFactory`, IHM et |
| [`selector.md`](selector.md) | Selector — Guide d'usage | Ce document résume le fonctionnement du module `selector/` et les commandes utiles pour : |
| [`selector_pipeline_compatibility.md`](selector_pipeline_compatibility.md) | Compatibilité pipeline `screener` → `selector` → `modelFactory` | Cette note synthétise l’état de compatibilité autour des enrichissements récents du `selector` : |
| [`sentiment_issue.md`](sentiment_issue.md) | Diagnostic et reprise — pipeline `event_sentiment` | Ce document trace le diagnostic, les corrections apportées et la reprise opératoire effectuée pour le pipeline sentiment, avec priorité sur |
| [`sentiments_migration.md`](sentiments_migration.md) | Migration des résultats du pipeline « Import + score + history_backfill + relevance_backfill auto » | Date d'analyse : 2026-05-10 |
| [`service.md`](service.md) | Service — Guide d'usage | Ce document résume le rôle du dossier `service/` et les usages utiles pour : |
| [`tlaps_proofs.md`](tlaps_proofs.md) | Preuves TLAPS — Phase G / S24.3 | ⚠️ **POC / livrable consultant non activé par défaut**. Les preuves TLAPS |
| [`watcher.md`](watcher.md) | Watcher de protections — guide dédié | Ce document décrit le rôle, le positionnement et l'exploitation du watcher de protections post-exécution. |

## Documentation centrale

| Document | Titre | Description |
|---|---|---|
| [`CHANGELOG.md`](CHANGELOG.md) | Changelog documentaire Alpha Trade | Journal synthétique des changements de conventions, docs structurantes et clarifications opératoires. |
| [`CONVENTIONS.md`](CONVENTIONS.md) | Conventions canoniques Alpha Trade | Source de vérité documentaire transversale pour les conventions encore en vigueur. |
| [`DOC_FONCTIONNELLE.md`](DOC_FONCTIONNELLE.md) | Alpha Trade — Documentation Fonctionnelle | *Version : 0.3.0 — Dernière mise à jour : mai 2026* |
| [`DOC_TECHNIQUE.md`](DOC_TECHNIQUE.md) | Alpha Trade — Documentation Technique | *Version : 0.3.0 — Python ≥ 3.12 — Dernière mise à jour : mai 2026* |

## Documentation utilisateur

| Document | Titre | Description |
|---|---|---|
| [`guide_add_new_table.md`](guide_add_new_table.md) | Guide — Ajouter une nouvelle table (Phase 7.6) | **Audience** : développeur Alpha Trade. |
| [`onboarding_operator.md`](onboarding_operator.md) | Onboarding opérateur — Walkthrough 60 minutes | Phase C / S18.1. Substitut textuel à la vidéo onboarding (cf. |
| [`onboarding_video_script.md`](onboarding_video_script.md) | Vidéo onboarding opérateur — Script (10-15 min) | Sprint S25.3 — Phase G. Script destiné à la production de la vidéo |

## Performance

| Document | Titre | Description |
|---|---|---|
| [`async_db_benchmark.md`](async_db_benchmark.md) | Async DB benchmark — Sprint S28.4 / A10 | Méthodologie : sqlite in-memory (CI), même schéma seedé sur les 2 engines. |
| [`async_db_poc.md`](async_db_poc.md) | POC async DB I/O — asyncpg / aiosqlite (Phase F / S23.3) | ⚠️ **POC non activé en production par défaut**. Ce document décrit une piste |
| [`perf_hotspots.md`](perf_hotspots.md) | Profiling des 3 hotspots (Phase F / S23.2) | Outil : [`scripts/profile_hotspot.py`](../scripts/profile_hotspot.py) |
| [`perf_pipeline.md`](perf_pipeline.md) | Pipeline complet — performance < 3 min sur 5 000 symboles (Phase F / S23.4) | Cible : `screener → selector → risk → execution(dry-run)` en **< 180 s** |

## Runbooks & Ops

| Document | Titre | Description |
|---|---|---|
| [`runbook_24_7.md`](runbook_24_7.md) | Runbook 24/7 — Alpha Trade | Phase C / S18.1. Procédures opérationnelles pour l'astreinte. |
| [`runbook_broker_failover.md`](runbook_broker_failover.md) | Runbook — Broker failover primaire / secondaire | **Audience** : opérateur Alpha Trade. |
| [`runbook_provider_incident.md`](runbook_provider_incident.md) | Runbook — Incident provider data (Phase 7.6) | **Audience** : opérateur on-call Alpha Trade. |
| [`runbook_reconciliation.md`](runbook_reconciliation.md) | Runbook — Réconciliation `MANUAL_REVIEW` / `BLOCKED` (Phase 7.6) | **Audience** : opérateur on-call. |

## Tests & Vérification

| Document | Titre | Description |
|---|---|---|
| [`manuel/10_page_backtesting.md`](manuel/10_page_backtesting.md) | 10. Page 🧪 Backtesting — tester sur l'historique | Simuler la stratégie sur **plusieurs années passées** pour mesurer ses |
| [`backtesting.md`](backtesting.md) | Backtesting & Backfill — guide d’usage | Mise à jour : mai 2026 |
| [`backtesting_report_schema.md`](backtesting_report_schema.md) | Glossaire `report.json` — module `backtesting` | Référence des champs publiés dans `<output_dir>/report.json` après chaque |
| [`formal_verification.md`](formal_verification.md) | Vérification formelle — Phase C / S15 | ⚠️ **POC / chantier de recherche non activé comme contrôle bloquant en production**. |
| [`fuzz_diff.md`](fuzz_diff.md) | Fuzzing différentiel backtest replay ↔ live execution | Sprint S24.1 — Phase G. |
| [`mutation_history.md`](mutation_history.md) | Mutation testing — historique hebdomadaire (Phase F / S22.3) | Cible Phase F : score mutmut **≥ 70 %** sur les 3 modules critiques |
| [`mutation_testing.md`](mutation_testing.md) | Mutation Testing — Phase C / S14 | Mesurer la robustesse de la suite de tests sur les modules critiques |

