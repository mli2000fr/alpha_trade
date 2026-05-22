# 08 — Plan d’action par sprints vers 10/10

## Cap cible

- **Point de départ consolidé** : `7,8 / 10`.
- **Cap court terme réaliste** : `8,5 / 10` après fermeture des écarts repo/CI/runbooks encore ouverts.
- **Cap intermédiaire** : `9,2 / 10` une fois l’orchestration, l’observabilité et la parité nightly industrialisées.
- **Cap final `10 / 10`** : atteint uniquement quand les garde-fous runtime déjà solides sont complétés par des **preuves d’exploitation institutionnelles** : CI bloquante versionnée, séparation stricte des environnements, observabilité centralisée, validation indépendante, change management et exercices d’incident documentés.

## Lecture du plan

- **S0 → S8** : socle déjà livré, ayant permis de monter la plateforme au niveau actuel.
- **S9 → S13** : trajectoire priorisée pour passer de `7,8 / 10` à `10 / 10`.
- Le plan ci-dessous est organisé pour fermer d’abord les **écarts structurels restants** identifiés dans `01_global_scorecard.md`, `02_module_scorecards.md` et `09_final_verdict.md`.

## Jalons de score et conditions de passage

| Jalon | Score cible | Horizon indicatif | Ce qui doit être vrai pour valider le jalon |
|---|---:|---|---|
| M1 | 8,5 / 10 | 2 à 4 semaines | Workflow CI sécurité versionné et bloquant, runbooks incidents exhaustifs, critères d’entrée/sortie live documentés, séparation minimale dev/paper/live visible. |
| M2 | 9,2 / 10 | 4 à 8 semaines supplémentaires | Orchestrateur durable avec reprise, monitoring/alerting centralisés, contract tests broker/providers, nightly parity et sandbox drills. |
| M3 | 10,0 / 10 | 1 à 2 trimestres | Validation indépendante complète, change management traçable, SLO/SLI exploités, exercices d’incident/DR prouvés, pack d’audit externe prêt. |

## Chantiers prioritaires pour atteindre 10/10

### C1 — CI sécurité et qualité bloquante

- **Pourquoi** : l’écart le plus explicitement bloquant reste l’absence de workflow repo versionné imposant CVE/secrets/lint/type/tests critiques.
- **Quick wins M1** :
  1. Ajouter `.github/workflows/ci-security.yml`.
  2. Exécuter `ruff`, `mypy`, `pytest` critique, scan secrets, SBOM, audit CVE.
  3. Rendre ces checks bloquants pour merge/release.
- **Industrialisation M2** : matrix OS/Python, artefacts SBOM signés, publication des rapports de sécurité, seuils de couverture critiques.
- **Critère de sortie M3** : aucune release/live sans pipeline vert, traces de scan archivées et auditables.
- **Dépendances** : scripts sécurité existants, sélection d’une suite critique stable, politique de branches/protection repo.

### C2 — Orchestration durable et séparation stricte des environnements

- **Pourquoi** : l’orchestration est encore trop locale/opérateur-dépendante pour un niveau institutionnel mature.
- **Quick wins M1** :
  1. Formaliser les environnements `dev`, `paper`, `live` avec variables, DB, artefacts et secrets distincts.
  2. Documenter les règles de promotion d’un run ou d’une config entre environnements.
- **Industrialisation M2** : orchestrateur type Prefect/Airflow/équivalent avec reprise transactionnelle, scheduling, retries, locks globaux, approbations.
- **Critère de sortie M3** : aucune exécution sensible dépendante d’un lancement manuel local non tracé ; séparation d’environnement vérifiée automatiquement.
- **Dépendances** : conventions de config, stockage d’artefacts, stratégie de déploiement et de secrets.

### C3 — Observabilité centralisée et discipline SRE

- **Pourquoi** : les run summaries sont riches, mais pas encore consolidés en monitoring/alerting central de niveau production.
- **Quick wins M1** :
  1. Définir la liste canonique des métriques critiques (latence provider, quote staleness, failures, stuck workflows, parity drift).
  2. Finaliser les runbooks d’incident broker/provider/DB/partial fill.
- **Industrialisation M2** : Prometheus/Grafana/Alertmanager ou équivalent, dashboards par chaîne, alertes routées, SLI/SLO explicites.
- **Critère de sortie M3** : incidents détectés automatiquement, horodatés, corrélés et rejouables avec postmortem standardisé.
- **Dépendances** : corrélation workflow déjà livrée, instrumentation supplémentaire runtime/IHM, stratégie de stockage métriques/logs.

### C4 — Validation indépendante, parité et tests contractuels

- **Pourquoi** : plusieurs briques sont quasi pro, mais la validation indépendante et les preuves de parité restent incomplètes.
- **Quick wins M1** :
  1. Définir la suite minimale de contract tests broker/provider.
  2. Versionner un jeu de golden datasets et un rapport nightly de parity.
- **Industrialisation M2** : sandbox drills nocturnes, replay incidents, validation indépendante des signaux/modèles et revue d’écarts par release.
- **Critère de sortie M3** : toute modification significative produit une preuve de non-régression backtest ↔ paper/live et une validation indépendante traçable.
- **Dépendances** : accès sandbox broker/provider, datasets PIT stables, gouvernance ML existante.

### C5 — Gouvernance, documentation et change management

- **Pourquoi** : pour atteindre `10/10`, il faut transformer la qualité actuelle en système opérable, auditable et transmissible.
- **Quick wins M1** :
  1. Unifier les runbooks et checklists de go-live.
  2. Définir un format standard de RFC/changement/approbation.
  3. Ajouter une matrice `owner / preuve / fréquence / escalade` pour chaque contrôle critique.
- **Industrialisation M2** : doc générée depuis config/code, journal de changements exploitable, approbations versionnées, pack de preuves de release.
- **Critère de sortie M3** : audit externe possible sans connaissance implicite du système par son auteur principal.
- **Dépendances** : CI versionnée, conventions de documentation, disponibilité des preuves issues des autres chantiers.

## S0 — Corrections P0 provider/config/doc

**Statut : ✅ Livré (config/doc/IHM/tests alignés)**

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
- Avancement réalisé :
  - ✅ `market_data.fallback_on_failure` retiré de `config.yaml` (pas de faux fallback runtime).
  - ✅ Runbooks/documents réalignés sur **EODHD nominal** et **Alpaca rétrocompatibilité**.
  - ✅ IHM paramètres/pipeline/backtesting rendue provider-aware.
  - ✅ Garde-fous de non-régression ajoutés côté config/doc/IHM.
- Validation réalisée :
  - ✅ `tests/test_market_data_provider_switch.py`
  - ✅ `tests/test_docs_provider_consistency.py`
  - ✅ `tests/test_doc_provider_alignment.py`
- Tests nouveaux :
  - `tests/test_market_data_provider_switch.py::test_fallback_on_failure_is_effective_or_rejected`
  - `tests/test_docs_provider_consistency.py::test_no_unqualified_import_alpaca_bar_runbook`
- Gain attendu : documentation +0.8, configuration +0.6, dataIntegrityEngine +0.3.

## S1 — Schéma et lineage OHLCV

**Statut : ✅ Livré (stratégie source unique active + préflight backtesting)**

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
- Décision actée :
  - ✅ **Source unique active** conservée sur `stock_bars_daily` (pas de migration PK multi-source à ce sprint).
  - ✅ `data_source` reste un champ de lineage/audit, sans promesse de cohabitation simultanée pour un même `(symbol,date)`.
- Avancement réalisé :
  - ✅ Documentation SQL/database/lineage corrigée.
  - ✅ Matrice de lineage régénérée avec la contrainte réelle de schéma.
  - ✅ Préflight `data_source='eodhd_eod'` branché dans le backtesting et le backfill PIT.
  - ✅ Adaptation IHM backtesting pour rendre la contrainte visible.
- Validation réalisée :
  - ✅ `tests/test_stock_bars_daily_source_versioning.py`
  - ✅ `tests/test_backtesting_data_source_preflight.py`
  - ✅ régression ciblée `tests/test_backtesting.py -k "run_backtest_"`
- Gain : database +0.8, backtesting +0.5, OHLCV +0.7.

## S2 — Qualité quotes/spreads et sync historique

**Statut : ✅ Livré (diagnostics quotes enrichis + garde-fous IHM historique)**

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
- Avancement réalisé :
  - ✅ `dataIntegrityEngine/sync_latest_quotes.py` enrichi avec `estimate_sync_latest_quotes_cost(...)` pour distinguer run latest vs historique, estimer appels API/durée et lever un warning opérateur sur les gros rattrapages.
  - ✅ `selector/db_io.py` enrichi avec `quote_source`, `quote_age_days`, `quote_size_quality` dérivés au fetch runtime, sans migration de schéma.
  - ✅ `selector/filters.py` propage désormais ces overlays quotes enrichis dans les diagnostics selector.
  - ✅ Adaptation IHM `ihm/pages/pipeline.py` : prévisualisation de charge, métriques coût/durée, et confirmation explicite requise pour un run quotes historique volumineux.
  - ✅ Compatibilité CLI/runtime conservée sur `sync_latest_quotes.main()` y compris avec doubles de tests qui ne passent pas `start_symbol`.
- Validation réalisée :
  - ✅ `tests/test_sync_latest_quotes.py`
  - ✅ `tests/test_data_integrity_run_summaries.py`
  - ✅ `tests/test_ihm_pipeline_runner.py`
  - ✅ `tests/test_pages_pipeline.py`
  - ✅ garde-fous ajoutés :
    - `tests/test_sync_latest_quotes.py::test_estimate_sync_latest_quotes_cost_flags_large_historical_runs`
    - `tests/test_pages_pipeline.py::test_render_period_sync_block_requires_confirmation_for_large_quotes_history_run`
- Gain : selector +0.5, IHM +0.4, data quality +0.5.

## S3 — Presets capital et exécutabilité petits comptes

**Statut : ✅ Livré (presets réalistes + exécutabilité visible en IHM + gate ML explicite)**

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
- Avancement réalisé :
  - ✅ `config/capital_presets.yaml` enrichi par tranche avec `execution_cash_settlement_days`, `backtesting_commission_bps_stress` et `backtesting_slippage_bps_stress`.
  - ✅ `common/capital_presets.py` expose `build_capital_preset_executability_summary(...)` pour résumer ticket mini, part d’equity, settlement cash, stress backtest et politique ML gate.
  - ✅ Adaptation IHM `ihm/pages/_execution_center/__init__.py` : affichage d’un résumé d’exécutabilité du preset capital actif pour l’opérateur.
  - ✅ `risk_management/ml_gate.py` ajoute `apply_ml_gate_to_risk_config(...)` afin de forcer explicitement le mode `quant_only` quand le gate ML est fermé.
  - ✅ `risk_management/cli.py` branche ce gate sur le runtime : pas de chargement des prédictions si ML coupé, et visibilité `effective_policy` dans le résumé risk.
  - ✅ La simulation petits comptes conserve explicitement `cash settlement` et `min notional` via les defaults de preset déjà propagés au backtesting/risk.
- Validation réalisée :
  - ✅ `tests/test_capital_presets_executability.py`
  - ✅ `tests/test_small_account_cash_settlement.py`
  - ✅ `tests/test_risk_ml_weight_gate.py`
  - ✅ `tests/test_execution_center_prefills.py`
  - ✅ `tests/test_ml_disable_modes.py`
- Gain : configuration +0.5, risk +0.6, swing fitness +0.5.

## S4 — Parité backtest ↔ live/paper

**Statut : ✅ Livré (profil `production-parity` + preset IHM + garde-fous de replay)**

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
- Avancement réalisé :
  - ✅ Ajout du profil CLI `--profile production-parity` dans `backtesting`, aligné sur la chaîne `pipeline` de replay `risk → execution → protection → watcher → exit lifecycle`.
  - ✅ Ajout du preset IHM `production_parity` dans `ihm/pages/backtesting/__init__.py` pour rendre ce mode visible et préremplissable côté opérateur.
  - ✅ Durcissement du message IHM autour des presets live-like / production parity pour rappeler la dépendance à un historique PIT valide.
  - ✅ Jeu de référence parité backtest ↔ live stabilisé dans un test golden dédié.
- Validation réalisée :
  - ✅ `tests/test_backtest_live_parity_golden.py`
  - ✅ `tests/test_execution_replay_parity.py`
  - ✅ régression ciblée :
    - `tests/test_backtesting_profiles.py`
    - `tests/test_pages_backtesting.py`
    - `tests/test_ihm_backtesting_runner.py`
    - `tests/test_parity_backtest_live.py`
- Gain : backtesting +1.0, execution +0.4, readiness +0.5.

## S5 — Corporate actions production hardening

**Statut : ✅ Livré (préflight apply snapshot + scope EODHD explicite + IHM ops sync/apply)**

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
- Avancement réalisé :
  - ✅ `corporate_actions/cli.py` bloque désormais explicitement une sync globale `EODHD` sans univers explicite (`--portfolio-only` ou `--symbols ...`) avec un message opérateur clair.
  - ✅ Préflight `apply` ajouté avant application : si des corporate actions sont en attente mais qu'aucun snapshot positions broker n'est disponible, l'apply est marqué en échec et bloqué avant tout crédit cash / split.
  - ✅ Résumés métier `corporate_actions_apply` / `corporate_actions_run` enrichis avec `apply_preflight` et provider/scope de sync pour audit IHM.
  - ✅ IHM `corporate_actions` enrichie avec une commande ops `Corporate Actions — sync` sécurisée par défaut (`portfolio-only`) et warning visible quand le dernier apply a été bloqué faute de snapshot positions.
  - ✅ Garde-fou d'idempotence cash ledger verrouillé par un test dédié sur réapplication d'un même dividende.
- Validation réalisée :
  - ✅ `tests/test_corporate_actions_eodhd_scope.py`
  - ✅ `tests/test_corporate_actions_apply_requires_positions.py`
  - ✅ `tests/test_portfolio_cash_ledger_idempotence.py`
  - ✅ régression ciblée :
    - `tests/test_corporate_actions_cli.py`
    - `tests/test_corporate_actions.py`
    - `tests/test_eodhd_corporate_action_provider.py`
    - `tests/test_corporate_actions_cross_check_yahoo.py`
    - `tests/test_ihm_cli_contract.py`
    - `tests/test_ihm_run_summary.py`
- Gain : corporate_actions +0.8, DB audit +0.3.

## S6 — Observabilité et exploitation incident

**Statut : ✅ Livré (corrélation workflow IHM + supervision incident + contrôle coverage)**

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
- Avancement réalisé :
  - ✅ `ihm/services/process_registry.py` propage désormais `workflow_correlation_id` sur les workflows IHM et tous leurs runs enfants, avec persistance/récupération depuis les artefacts de run.
  - ✅ `ihm/services/ops_supervision.py` expose un `run_lineage` lisible côté cockpit ops et un contrôle de santé `coverage.json` (présence, complétude, branch coverage).
  - ✅ Adaptation IHM `ihm/pages/supervision_ops.py` : panneau dédié de corrélation workflow parent/enfants et panneau `Artefact coverage` visible pour l'exploitation incident.
  - ✅ Les garde-fous stop/recovery du registre IHM restent verts après régression complète ciblée (`running/scheduled orphan` → `stopped`, watchdog/reprise conservés).
- Validation réalisée :
  - ✅ `tests/test_ihm_process_registry.py`
  - ✅ `tests/test_pipeline_workflow_correlation_id.py`
  - ✅ `tests/test_ops_supervision.py`
  - ✅ `tests/test_coverage_artifact_is_complete.py`
  - ✅ `tests/test_pages_supervision_ops.py`
  - ✅ régression élargie :
    - `tests/test_ihm_pipeline_e2e.py`
    - `tests/test_ihm_run_summary.py`
- Gain : observabilité +1.0, IHM +0.6, readiness +0.6.

## S7 — ML/sentiment gouvernance alpha

**Statut : ✅ Livré (ablation par régime + seuils gouvernance visibles + fallback quant-only confirmé)**

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
- Avancement réalisé :
  - ✅ `backtesting/attribution.py` enrichi avec des `regime_results` et la persistance `attribution_by_regime.csv` pour comparer quant-only / sentiment / ML globalement puis par régime.
  - ✅ `ihm/services/ml_artifacts.py` remonte désormais un résumé `governance_thresholds` (min precision, bornes action-rate, seuil retenu, éligibilité champion) et charge les rapports d'ablation quand ils existent dans les artefacts symbole.
  - ✅ Adaptation IHM `ihm/pages/ml.py` : affichage des seuils de gouvernance persistés, visibilité explicite d'un champion non encore éligible / fallback attendu, et tableaux d'ablation globale + par régime.
  - ✅ Le fallback quant-only automatique côté risque reste explicitement branché via `risk_management/ml_gate.py` et revalidé dans les régressions S7.
- Validation réalisée :
  - ✅ `tests/test_sentiment_attribution.py`
  - ✅ `tests/test_sentiment_ablation_report.py`
  - ✅ `tests/test_services_ml_artifacts.py`
  - ✅ `tests/test_model_governance_drift_gate.py`
  - ✅ `tests/test_pages_ml.py`
  - ✅ régressions gouvernance/gate :
    - `tests/test_ml_drift_policy_gate.py`
    - `tests/test_ml_disable_modes.py`
    - `tests/test_risk_ml_weight_gate.py`
    - `tests/test_model_factory_run_summary.py`
    - `tests/test_model_factory_cli.py`
    - `tests/test_model_factory_config.py`
    - `tests/test_model_factory_evaluation.py`
    - `tests/test_model_factory_db_registry.py`
- Gain : modelFactory +0.8, event_sentiment +0.7, risk +0.4.

## S8 — Sécurité et production readiness

**Statut : 🟡 Partiellement livré (runtime/IHM/tests en place ; workflow CI security repo encore absent)**

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
  - `tests/test_execution_live_plan_immutable.py`
  - `tests/test_config_loader_vault.py`
  - `tests/test_security_scripts.py`
- Avancement réalisé :
  - ✅ `execution_engine.preflight.check_live_secret_policy(...)` bloque désormais le live sans Vault explicite (`ALPHA_TRADE_VAULT_ADDR` + `ALPHA_TRADE_VAULT_TOKEN`) ni override assumé `ALPHA_TRADE_LIVE_SECRET_POLICY=env`.
  - ✅ `run_execution.py` exige un token d’approbation live (`ALPHA_TRADE_LIVE_APPROVAL_TOKEN`) et vérifie/écrit un run plan immuable avant tout run live.
  - ✅ L’IHM expose ces garde-fous live dans `ihm/pages/_execution_center/__init__.py` et les jobs ops/sécurité dans `ihm/pages/compliance_audit.py` / `ihm/pages/settings.py`.
  - ✅ Les scripts `generate_sbom.py`, `scan_cves.py`, `scan_repo_secrets.py` et `verify_vault_rotation.py` existent et sont couverts par des tests dédiés.
  - ⚠️ Aucun dossier `.github/workflows/` n’est présent dans le repo audité : la partie “CI security workflow” reste donc **non livrée côté dépôt versionné**.
- Validation réalisée :
  - ✅ `tests/test_live_requires_vault_or_env_policy.py`
  - ✅ `tests/test_execution_live_requires_approval_token.py`
  - ✅ `tests/test_execution_live_plan_immutable.py`
  - ✅ `tests/test_pre_live_checklist.py`
  - ✅ `tests/test_config_loader_vault.py`
  - ✅ `tests/test_security_scripts.py`
  - ✅ régressions IHM associées :
    - `tests/test_ihm_pipeline_runner.py`
    - `tests/test_execution_center_prefills.py`
    - `tests/test_ihm_pipeline_e2e.py`
    - `tests/test_pages_settings.py`
- Reste à faire :
  - créer un workflow CI security versionné (scan CVE, secret scan, ruff, mypy, pytest critique) ;
  - versionner des runbooks incidents exhaustifs (broker outage, provider outage, DB outage, partial fill) si l’objectif est un go-live plus ambitieux.
- Gain : sécurité +0.7, readiness +0.6 tant que la CI security versionnée manque.

## S9 — CI sécurité versionnée et runbooks bloquants

**Statut : 🔴 À lancer en priorité (jalon M1)**

- Priorité : P0
- Chantiers : C1, C5
- Modules : CI/CD, `scripts/`, `doc/`, sécurité, qualité logicielle
- Objectif : fermer l’écart principal entre runtime durci et dépôt encore insuffisamment bloquant.
- Tâches :
  1. Créer un workflow repo versionné exécutant `ruff`, `mypy`, `pytest` critique, scan CVE, scan secrets, génération SBOM.
  2. Définir la suite `pytest critical` minimale et stable requise avant merge/release.
  3. Versionner les runbooks incidents `broker outage`, `provider outage`, `DB outage`, `partial fill`, `stuck workflow`.
  4. Ajouter une checklist de go-live et de rollback signée par environnement.
- Preuves attendues :
  - workflow CI visible dans le dépôt et configuré en statut requis ;
  - rapports de sécurité archivés ;
  - runbooks versionnés et reliés au verdict/readiness.
- Critères d’acceptation :
  - aucun merge sur branche protégée sans pipeline sécurité vert ;
  - aucun live sans checklist de pré-vol complète ;
  - documentation incident sans contradiction opératoire.
- Dépendances : stabilisation des tests critiques, conventions de branches et droits repo.
- Gain attendu : sécurité +1.0, qualité logicielle +0.5, documentation +0.4.

## S10 — Orchestrateur durable et séparation dev/paper/live

**Statut : 🔴 Planifié après S9 (jalon M2)**

- Priorité : P0/P1
- Chantiers : C2, C5
- Modules : `ihm`, `flows`, `service`, `execution_engine`, configuration, artefacts
- Objectif : sortir d’une orchestration principalement locale et rendre les environnements non interchangeables par erreur.
- Tâches :
  1. Introduire une notion d’`environment` stricte dans la config et les artefacts (`dev`, `paper`, `live`).
  2. Séparer DB, buckets d’artefacts, secrets et approbations par environnement.
  3. Brancher un orchestrateur durable avec reprise, retries, scheduling, locks et lineage.
  4. Rendre impossible la promotion implicite d’une config `paper` en `live` sans approbation formelle.
- Preuves attendues :
  - runs rejouables et reprenables sans intervention manuelle opaque ;
  - journaux de promotion d’environnement ;
  - démonstration de reprise après interruption de workflow.
- Critères d’acceptation :
  - séparation visible et testée des environnements ;
  - exécution live impossible depuis un contexte non autorisé ;
  - orphelins/reprises gérés par l’orchestrateur et non uniquement par l’IHM locale.
- Dépendances : S9 vert, stratégie de secrets, conventions de déploiement.
- Gain attendu : execution +0.6, IHM +0.4, readiness +0.8.

## S11 — Observabilité centralisée, alerting et SLO

**Statut : 🔴 Planifié (jalon M2)**

- Priorité : P1
- Chantiers : C3
- Modules : observabilité, `ihm`, `execution_engine`, `dataIntegrityEngine`, backtesting
- Objectif : transformer les métriques existantes en dispositif SRE centralisé, actionnable et mesuré.
- Tâches :
  1. Exposer métriques et événements critiques au monitoring central.
  2. Définir SLI/SLO pour disponibilité provider, fraîcheur quotes, durée workflow, parity drift, erreurs d’exécution.
  3. Construire dashboards et alertes par chaîne critique.
  4. Standardiser postmortem, annotation d’incident et lien run ↔ alerte ↔ runbook.
- Preuves attendues :
  - dashboard central avec au moins les flux `data`, `selection`, `risk`, `execution`, `corporate actions` ;
  - alertes testées et horodatées ;
  - exemple d’incident traité avec postmortem complet.
- Critères d’acceptation :
  - incident majeur détectable sans lecture manuelle des logs ;
  - time-to-detect et time-to-recover mesurables ;
  - lien direct depuis une alerte vers le runbook applicable.
- Dépendances : S10 instrumentation/orchestrateur, stockage central des logs/métriques.
- Gain attendu : observabilité +1.2, IHM +0.3, readiness +0.5.

## S12 — Validation indépendante, contract tests et parity nightly

**Statut : 🔴 Planifié (jalon M2 → M3)**

- Priorité : P1
- Chantiers : C4
- Modules : backtesting, `execution_engine`, `risk_management`, `modelFactory`, providers, broker adapters
- Objectif : produire des preuves de non-régression indépendantes des seuls tests unitaires locaux.
- Tâches :
  1. Ajouter des contract tests broker/provider exécutés en sandbox ou via mocks certifiés.
  2. Exécuter un job nightly de `production-parity` avec rapport d’écart versionné.
  3. Instituer une revue indépendante des signaux/modèles avant changement majeur de pondération ou de gate.
  4. Tester des scénarios d’incident : partial fills, latence provider, coupure broker, reprise post-failure.
- Preuves attendues :
  - rapports nightly historisés ;
  - seuils d’écart acceptables explicités ;
  - validation indépendante signée sur les évolutions ML/risk/execution.
- Critères d’acceptation :
  - aucune release significative sans parity report vert ;
  - contrats broker/provider cassés détectés avant exploitation ;
  - modifications de modèles/signaux bloquées si validation indépendante absente.
- Dépendances : S9 CI, S10 orchestrateur, datasets golden stables, sandbox broker/provider.
- Gain attendu : backtesting +0.8, execution +0.5, modelFactory +0.8, service/providers +0.7.

## S13 — Gouvernance de changement, DR drills et pack d’audit externe

**Statut : 🔴 Cible finale (jalon M3)**

- Priorité : P1/P2
- Chantiers : C3, C5
- Modules : documentation, sécurité, exploitation, conformité, IHM ops
- Objectif : franchir le dernier palier entre “indépendant avancé/quasi pro” et “institutionnel mature prouvé”.
- Tâches :
  1. Versionner le change management complet : RFC, approbation, rollback, preuves de release, journal d’exceptions.
  2. Réaliser des exercices de reprise après incident et de disaster recovery documentés.
  3. Construire un pack d’audit externe : architecture, contrôles, preuves CI, historiques incidents, validations indépendantes.
  4. Régénérer automatiquement la documentation technique/fonctionnelle depuis config/code/tests critiques.
- Preuves attendues :
  - exercices DR/postmortem archivés ;
  - dossier d’audit consultable sans contexte oral ;
  - matrice contrôle → owner → fréquence → preuve → escalade.
- Critères d’acceptation :
  - auditabilité complète de bout en bout ;
  - un opérateur tiers peut exécuter/surveiller/escalader selon procédure ;
  - la plateforme n’a plus de dépendance critique à la mémoire implicite du développeur principal.
- Dépendances : S9 à S12 réalisés et stabilisés sur plusieurs cycles d’exploitation.
- Gain attendu : documentation +0.8, sécurité +0.5, observabilité +0.4, qualité globale +0.6.

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

Après **S0 à S8** validés, la plateforme est suffisamment robuste pour un **live pilote très discipliné** et de faible ampleur, à condition de conserver une supervision quotidienne stricte. 

Pour passer à un **live plus ambitieux et répétable**, le vrai seuil d’industrialisation devient **S9** : tant que la CI sécurité versionnée et les runbooks incidents exhaustifs ne sont pas livrés, l’exploitation reste dépendante d’une discipline locale trop forte.

Pour un niveau **quasi institutionnel exploitable**, il faut viser **S10 à S12** validés avec preuves ; le niveau **10/10** n’est crédible qu’après **S13** et plusieurs cycles d’exploitation sans incident non maîtrisé.

## Ce qu’il restera pour un vrai 10/10 pro-grade

- **Rien de structurellement majeur** si `S9 → S13` sont réellement livrés avec preuves ; à ce stade, la question n’est plus “quoi ajouter ?” mais “quelles preuves d’exploitation répétée peut-on montrer ?”.
- Les critères finaux à démontrer pour assumer un `10/10` sont :
  1. **CI sécurité et qualité bloquante** sur chaque merge/release.
  2. **Séparation stricte dev/paper/live** techniquement vérifiée.
  3. **Orchestrateur durable** avec reprise, locks, lineage et approbations.
  4. **Monitoring centralisé + alerting + SLO** réellement exploités.
  5. **Contract tests broker/provider + parity nightly** en place et archivés.
  6. **Validation indépendante** des signaux/modèles/changements critiques.
  7. **Runbooks, postmortems et DR drills** versionnés, testés et transmissibles.
  8. **Pack d’audit externe** consultable sans dépendance à la mémoire du développeur principal.

