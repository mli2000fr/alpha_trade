# Plan d'exécution — Refactoring Alpha Trade

> **Source** : 14 audits dans `prompt/refactor/audit_*.md` + synthèse `audit_global.md`.
> **Objectif** : traiter méthodiquement Risques + Choix recommandés + Quick Wins +
> Recommandations structurelles + Plan d'action priorisé de chaque audit, sans
> rebrassage inutile.
> **Stratégie** : ordre **hybride** = fondations transverses (Phase 1) → modules
> dans l'ordre du pipeline (Phases 2→6) → revue transverse finale (Phase 7).

---

## Pourquoi cet ordre (et pas purement global puis modules ou l'inverse)

- `audit_global.md` est une **synthèse** des audits modulaires : ne traiter que lui
  ne descend pas au niveau opérationnel des risques par module.
- Mais corriger les modules **avant** les fondations transverses (Protocols
  `core/interfaces.py`, Alembic baseline, `core/conviction.py`,
  `core/filter_profiles.py`, retry helper, secrets DB, `schema_version`)
  obligerait à les rebrasser 2 fois.
- Solution : **extraire d'abord les "rocks" transverses du Court terme global**
  (Phase 1), **puis dérouler module par module** (Phases 2→6 dans l'ordre du
  pipeline pour minimiser les conflits), **puis valider transverse final**
  (Phase 7 = items vraiment cross-modules : kill switch global, dashboard,
  shadow mode, import-linter, doc cible).

---

## Conventions

- **Une PR / commit par phase ou sous-phase**, jamais par audit complet (trop gros).
- **Tests verts à chaque commit** (`pytest -q --no-cov` avant push).
- **`run_summary`** : à chaque modification de CLI, mettre à jour le payload puis
  `tests/test_*_run_summary*.py`.
- **Doc** : la mise à jour de `doc/<module>.md` fait partie de la sous-phase, pas
  un commit à part.
- **Audit clos** : à la fin de chaque sous-phase, cocher les items dans le `.md`
  d'audit du module (`✅ corrigé en Phase X`).

---

## Phase 0 — Préparation (½ jour)

| # | Action | Sortie |
|---|---|---|
| 0.1 | Créer la branche `refactor/audit-rollout` à partir de `develop_refactor_1` | branche |
| 0.2 | Snapshot DB locale (mysqldump → `backups/pre_refactor.sql`) | fichier |
| 0.3 | Lancer la suite tests complète (`pytest --no-cov -q`) → archiver le rapport | rapport baseline |
| 0.4 | Vérifier que `pip install -e .` fonctionne, créer `requirements-dev.lock` | lockfile |
| 0.5 | Activer pre-commit (`ruff`, `mypy`, `pytest -k smoke`) | `.pre-commit-config.yaml` |

**Critère de sortie** : tests baseline verts + branche prête.

---

## Phase 1 — Fondations transverses (≤ 1 semaine)

> Items "Court terme" extraits d'`audit_global.md` qui débloquent tous les
> modules. À traiter **avant** la première sous-phase modulaire pour éviter le
> rebrassage.

### 1.1 — Schéma SQL Alembic (profite de la réinit DB prévue)
- [ ] Baseline `alembic/versions/0001_initial_schema.py` reflétant l'état actuel
      (réinitialiser `alembic_version`).
- [ ] Migration `0002_data_adjustment_check` : ajouter
      `data_adjustment VARCHAR(16) NOT NULL DEFAULT 'split'` + `CHECK` sur
      `stock_bars` et `stock_bars_daily`.
- [ ] Migration `0003_provenance_columns` : `data_source VARCHAR(16)`,
      `market_cap_refreshed_at`, `metadata_synced_at` sur `stock_metadata`.
- [ ] CI : job `alembic upgrade head` obligatoire.
- [ ] Doc : section "ajouter une migration" dans `doc/database.md`.

### 1.2 — Sécurité opérationnelle
- [ ] **Equity fallback fatal** dans `run_execution.py` (mode `live` / `paper` :
      `raise RuntimeError` si `broker.get_account_equity()` échoue).
- [ ] **Confirmation live renforcée** : saisie du nom de compte par l'opérateur
      (chaîne libre comparée stricte).
- [ ] **Secrets DB hors `config.yaml`** : placeholders `${DB_PASSWORD}` partout +
      check au démarrage.
- [ ] **Lock SQL watcher** via table `execution_locks` (insert-or-fail, expiry).
- [ ] **Heartbeat watcher SQL persistant** (`watcher_heartbeats`).

### 1.3 — Observabilité minimale
- [ ] Ajouter `schema_version: int = 1` dans **tous** les payloads
      `run_summary` (helper `core/run_summary.py`).
- [ ] Compteurs IEX : `symbols_zero_volume_30d`, `stale_quote_pct`,
      `stale_market_cap_pct` propagés depuis `dataIntegrityEngine`.

### 1.4 — Service / clients data
- [ ] `feed=iex` paramètre **validé** dans `service/alpaca/clientAlpaca.fetch_bars`
      (`Literal["iex","sip"]` + log explicite si fallback).
- [ ] Helper unique `service/_http_retry.py` (politique exponentielle + circuit
      breaker simple) — TOUS les clients y migrent.
- [ ] Cache TTL 7j pour profils Finnhub.

### 1.5 — Documentation transverse
- [ ] Section "Limites IEX et impact concret" dans `doc/dataIntegrityEngine.md`
      et `README.md`.
- [ ] Affirmer la convention `split_adjusted` dans `README.md`,
      `doc/dataIntegrityEngine.md`, `doc/corporate_actions.md`,
      `doc/backetesting.md`.

**Critère de sortie** : tests verts + DB recréée sous Alembic + un live trading
ne peut plus partir avec equity 100k$ par défaut.

---

## Phase 2 — Modules de socle (≤ 1 semaine)

> Modules transverses consommés par tout le reste : à clore avant les modules
> métier.

### 2.1 — `core/` + `common/` (réf. `audit_core_common.md`)
- [x] **Centraliser les Protocols** dans `core/interfaces.py` :
      `BrokerPort`, `MarketDataPort`, `BarsRepository`, `ScoresRepository`,
      `RiskRepository`, `ExecutionRepository`, `NewsProvider`,
      `CorporateActionProvider`.
- [x] Créer `core/conviction.py` (formule de fusion partagée).
- [x] Créer `core/filter_profiles.py` (déplacer `STRICT_SWING_CASH_FILTERS`).
- [x] Découper `common/utils.py` (fourre-tout) en sous-modules.
- [x] Doc `doc/core_common.md` (manquante d'après audit).

### 2.2 — `database/` (réf. `audit_database.md`)
- [x] Façade `database/repositories/` : un repository typé par domaine,
      consommée via Protocol `core/interfaces.py`.
- [x] Élargir le pool SQLAlchemy (audit signale "minuscule").
- [x] Activer `DB_SSL_CA_PATH` (TLS optionnel).
- [x] Tests d'intégration `testcontainers[mysql]` activés en CI.

### 2.3 — `service/` (réf. `audit_service.md`)
- [x] Migrer tous les clients (Alpaca / Finnhub / News) sur
      `service/_http_retry.py`.
- [x] Cache Finnhub 7j (déjà préparé en 1.4 si bien factorisé).
- [x] Documenter `feed=iex` explicite et son impact.

**Critère de sortie** : aucun module métier n'importe encore une implémentation
concrète au lieu d'un Protocol.

---

## Phase 3 — Pipeline data (≤ 1 semaine)

### 3.1 — `dataIntegrityEngine/` (réf. `audit_dataIntegrityEngine.md`)
- [x] Exit ≠ 0 si ratio succès `import_alpaca_bar` < seuil.
- [x] Découpler le calendrier de SPY → `pandas_market_calendars`.
- [x] Audit dédié quotes (`cleaning_audit_quotes_runs`).
- [x] Audit dédié earnings (`cleaning_audit_earnings_runs`).
- [x] `market_cap_refreshed_at` consommé par filtre TTL.

### 3.2 — `screener/` (réf. `audit_screener.md`)
- [x] Filtrer `WHERE is_filled = 0` dans `historical_range_score` /
      `high_52w_proximity`.
- [x] `chunk_failures` dans `run_summary`.
- [x] Migrer vers `core/filter_profiles.py`.

### 3.3 — `selector/` (réf. `audit_selector.md`)
- [ ] Découper `alpha_scanner.py` (`factors.py` + `filters.py` + `ranking.py`).
- [x] `rejected_by_filter` (par filtre) dans `run_summary`.
- [x] Adapter `spread_bps` au biais IEX (relâchement contrôlé documenté).
- [x] Filtre `market_cap` consomme `market_cap_refreshed_at` (TTL).
- [x] Migrer vers `core/filter_profiles.py`.

**Critère de sortie** : pipeline 1→6 reproductible, biais IEX visible dans les
`run_summary`, schéma `core/filter_profiles.py` partagé.

---

## Phase 4 — ML & signaux (≤ 2 semaines)

### 4.1 — `event_sentiment/` (réf. `audit_event_sentiment.md`)
- [x] Versionner FinBERT (sha de checkpoint + champ `model_fingerprint`). _(4.1.c)_
- [x] Migrer `signal_aggregator` vers `core/conviction.py`. _(4.1.a + 4.1.b)_
- [x] Documenter sources (Alpaca News unique). _(4.1.c — `doc/event_sentiment.md`)_

### 4.2 — `modelFactory/` (réf. `audit_modelFactory.md`)
- [x] **Migrer LightGBM/CatBoost vers format natif** (`save_model`),
      déprécier `pickle`. _(4.2.c)_
- [x] **Fingerprint features SHA256** dans `config.json` du modèle. _(4.2.b)_
- [x] Activer `--walkforward` par défaut (déjà fait IHM, à matérialiser CLI). _(4.2.g)_
- [x] **Quarantaine champion** : `--champion-min-runs N`,
      `--champion-min-days N`. _(4.2.e)_
- [x] Persistance `metrics.json` BLOB DB pour les champions. _(4.2.f — table `model_metrics_full`)_
- [x] Cache modèles dans le predictor (évite recharge complète). _(4.2.d — `_ModelCache` + `clear_model_cache`)_
- [x] Garde-fou anti-leak `--ml-mode rebuild-missing`. _(4.2.g)_
- [x] Découper `trainer.py` (`train_symbol` en sous-fonctions). _(4.2.a)_
- [x] `run_summary` ML standardisé (`feature_fingerprint`, `champion_quarantine`, `schema_version`). _(4.2.h)_

**Critère de sortie** : aucun artefact `.pkl` produit en sortie ; champions
gouvernés (run-min + days-min).

---

## Phase 5 — Décision & exécution (≤ 1 semaine)

### 5.1 — `risk_management/` (réf. `audit_risk_management.md`)
- [x] `account_equity_breakdown` dans `run_summary`. _(5.1.a)_
- [x] Migrer fusion conviction vers `core/conviction.py`. _(5.1.b)_
- [x] Documenter pondérations 40/60 (et plan de calibration empirique). _(5.1.c)_

### 5.2 — `execution_engine/` (réf. `audit_execution.md`)
- [x] Découper `executor.py` (`execute_run` en sous-méthodes + state machine
      explicite). _(5.2.a + 5.2.b — `ExecutionPhase` enum, `_phase_*` extraits)_
- [x] Runbook `MANUAL_REVIEW` / `BLOCKED` dans `doc/execution_engine.md`. _(5.2.d)_
- [x] **Kill switch global** : `python -m execution_engine cancel-all
      --account live1`. _(5.2.c — table `execution_kill_switch_runs`, migration 0017)_

### 5.3 — `corporate_actions/` (réf. `audit_corporate_actions.md`)
- [x] Documenter construction `idempotency_key`. _(5.3.a — `compute_idempotency_key(account_id)`, migration 0019, doc §9.1)_
- [x] Audit dédié `corporate_actions_audit_runs`. _(5.3.b — migration 0018, `persist_audit_run`, doc §9.2)_
- [x] Évaluer Yahoo dividends comme cross-check. _(5.3.c — `cross_check_yahoo.py`, extra `[cross-check]`, CLI `--cross-check yahoo`, doc §9.3)_

**Critère de sortie** : execution reproductible et auditable, kill switch testé.

---

## Phase 6 — Périphérie (≤ 1 semaine)

### 6.1 — `backtesting/` (réf. `audit_backtesting.md`)
- [x] `--commission-bps`, `--slippage-bps` (défauts > 0). _(6.1.b — `backtesting/cli.py`, `backtesting/simulator.py`)_
- [x] `total_return_with_dividends` au rapport. _(6.1.c — `backtesting/report.py::BacktestReport`, `load_dividends_received`)_
- [x] Validation hold-out diagnostic screener phase 5-7. _(6.1.d — `backtesting/screener_diagnostics.py::validate_recommendations_holdout`, flags `--holdout-train-end/--holdout-test-end`)_
- [x] Profiles CLI consolidés. _(6.1.e — `backtesting/profiles.py::BACKTEST_PROFILES`, `--profile {strict_swing_cash,swing_cash_aggressive,custom}`)_
- [x] Migrer `signal_replay` vers `core/conviction.py`. _(6.1.a — `backtesting/signal_replay.py` consomme `core.conviction.fuse`, payload `params.conviction_weights`)_

### 6.2 — `ihm/` (réf. `audit_ihm.md`)
- [ ] **Découper `pages/pipeline.py`** en sous-modules
      (`_workflow.py`, `_data_integrity.py`, `_execution_center.py`,
      `_alpha_scanner_diagnostics.py`, `_watcher_block.py`).
      _(reporté Phase 7 — fichier 2872 lignes, refactor non destructif différé pour minimiser le risque sur l'IHM en production.)_
- [x] Hook `atexit` dans `process_registry` (kill enfants). _(6.2 — `ihm/services/process_registry.py::_atexit_kill_all_children`)_
- [x] Rotation artefacts `IHM_RUNS_RETENTION_DAYS=30`. _(6.2 — `rotate_pipeline_artifacts`, env `IHM_RUNS_RETENTION_DAYS`)_
- [x] Audit shell quoting `process_registry`. _(6.2 — `subprocess.Popen(list[str], shell=False)` confirmé, documenté dans `doc/ihm.md`)_
- [x] Cache obligatoire (`@st.cache_data`) sur toutes les requêtes DB des pages. _(6.2 — toutes les fonctions publiques de `ihm/services/queries.py` sont cachées avec TTL=60s)_
- [x] Test contractuel **IHM ↔ CLI** (introspection argparse). _(6.2 — `tests/test_ihm_cli_contract.py` : pour chaque step, vérifie que les flags `--xxx` sont reconnus par l'argparse cible)_
- [x] Auth basique optionnelle (token) si exposé hors localhost. _(6.2 — `ihm/services/security.py::render_auth_gate`, env `IHM_AUTH_TOKEN`)_
- [x] Check démarrage `--server.address=localhost`. _(6.2 — `render_security_banner` + env `IHM_REQUIRE_LOCALHOST`)_
- [x] Documenter sécurité IHM dans `doc/ihm.md`. _(6.2 — section « Sécurité réseau » + démarrage prod locale)_

### 6.3 — `watcher/` (réf. `audit_watcher.md`)
- [x] Leader election via `execution_locks` (déjà partiellement Phase 1.2). _(6.3 — `ProtectionWatcherService.run` acquiert `watcher:<account_id>` via `acquire_execution_lock`, status `LEADER_LOCK_HELD` si déjà détenu)_
- [x] Heartbeat persistant SQL (idem). _(déjà fait Phase 1.3 — `repo.upsert_watcher_heartbeat`, table `watcher_heartbeats`)_
- [x] Tests rigoureux allowlist PowerShell. _(6.3 — `tests/test_watcher_powershell_allowlist.py` : 23 tests (deny `Invoke-Expression`/`iex`/`Add-Type`/`DownloadString`, exige `Set-StrictMode` + `$ErrorActionPreference`))_
- [x] Revue `protection_watcher_secrets.ps1`. _(6.3 — DPAPI scope contraint via ValidateSet, avertissement LocalMachine, `ZeroFreeBSTR` après usage, store JSON via `Set-Content -LiteralPath`)_

**Critère de sortie** : IHM modulaire, watcher mono-instance garanti, backtest
réaliste.

---

## Phase 7 — Revue transverse finale (≤ 3 jours)

> Items d'`audit_global.md` qui restent vraiment cross-modules après les
> Phases 2→6.

- [x] **`import-linter`** enforced (interdit aux modules métier d'importer les
      implémentations directement). _(7.1 — `.importlinter` (warn-only) +
      `tests/test_import_linter_contracts.py` + extra `[dev]` `import-linter>=2.0`.
      Passage strict reporté backlog L11.)_
- [x] **Mode "shadow"** simulate parallèle d'un live (mesure dérive). _(7.7 —
      shadow compare **offline** livré : `risk_management/shadow_compare.py` +
      table `shadow_drift_runs` (migration `0022`) + `tests/test_risk_shadow_compare.py`.
      Daemon shadow live continu reporté backlog L2.)_
- [x] **Calibration empirique** des poids conviction / signal_aggregator sur
      backtest glissant 6 mois (table `weights_calibration_runs`). _(7.2 —
      `backtesting/weights_calibration.py` + table (migration `0020`) +
      `tests/test_weights_calibration.py`.)_
- [x] **Stooq cross-check** OHLC daily / volume (best-effort). _(7.3 —
      `service/stooq/clientStooq.py` (zéro dépendance externe) +
      `dataIntegrityEngine/cross_check_stooq.py` + `tests/test_stooq_cross_check.py`.)_
- [x] **SEC EDGAR 8-K** comme second canal news (long terme — peut sortir du
      scope). _(7.8 — reporté backlog L1 explicitement, justifié dans
      `prompt/refactor/backlog_long_terme.md`.)_
- [x] Dashboard observabilité minimal (Prometheus / Grafana ou équivalent).
      _(7.5 — `core/metrics.py` (Counter/Gauge/Histogram, lazy
      `prometheus_client`, fallback no-op) + `start_metrics_server` opt-in
      via `ALPHA_TRADE_METRICS_PORT` + extra `[observability]` +
      `doc/observability.md` + `tests/test_core_metrics.py`. Grafana /
      Alertmanager déploiement reporté backlog L3.)_
- [x] Drift ML monitoring auto. _(7.4 — `modelFactory/drift_monitor.py`
      (KS + PSI, scipy optionnel) + table `ml_drift_runs` (migration `0021`) +
      `tests/test_modelfactory_drift_monitor.py`.)_
- [x] **Mapping table ↔ producteur ↔ consommateurs** (matrice impact). _(7.6
      — `doc/data_lineage_matrix.md` couvrant 6 domaines (market data,
      scoring, ML, risk/exec, corporate actions, backtest).)_
- [x] Doc cible : runbook incident provider, runbook réconciliation, guide
      "ajouter une nouvelle table" (template Alembic). _(7.6 —
      `doc/runbook_provider_incident.md`, `doc/runbook_reconciliation.md`,
      `doc/guide_add_new_table.md`.)_
- [x] Cocher tous les `✅` restants dans `audit_global.md` ; ce qui reste devient
      le **backlog "Long terme" suivant**. _(7.10 — section §11 "Clôture
      refactor" ajoutée à `audit_global.md` + `prompt/refactor/backlog_long_terme.md`
      créé avec entrées L1 → L11 (justification + esquisse cible + estimation).)_

**Critère de sortie** : `audit_global.md` à jour, items "Long terme"
explicitement reportés au backlog avec justification. **✅ Atteint.**

---

## Récapitulatif chronologique

| Phase | Durée cible | Livrables clés |
|---|---|---|
| 0 | 0.5 j | branche, baseline tests, lockfile, pre-commit |
| 1 | 5-7 j | Alembic baseline, equity fatal, secrets, lock watcher, schema_version, retry helper |
| 2 | 5-7 j | `core/interfaces.py` Protocols, repositories DB, clients service unifiés |
| 3 | 5-7 j | dataIntegrityEngine + screener + selector industrialisés |
| 4 | 10-14 j | event_sentiment + modelFactory (formats natifs, fingerprint, quarantaine) |
| 5 | 5-7 j | risk + execution (kill switch) + corporate_actions |
| 6 | 5-7 j | backtesting (costs/slippage) + ihm (découpage, auth) + watcher |
| 7 | 3 j | import-linter, mode shadow, doc cible, backlog long terme |
| **Total** | **6-8 sem.** | Refactor structurel complet, dette d'audit close |

---

## Ordre de traitement audit-par-audit (TL;DR)

> Réponse directe à la question initiale : **commence par les fondations
> transverses tirées d'`audit_global.md` (Phase 1), puis enchaîne les modules
> dans l'ordre ci-dessous, et finis par une re-lecture d'`audit_global.md` pour
> le solde transverse**.

1. `audit_global.md` (Phase 1 uniquement = items Court terme transverses).
2. `audit_core_common.md` (Phase 2.1).
3. `audit_database.md` (Phase 2.2).
4. `audit_service.md` (Phase 2.3).
5. `audit_dataIntegrityEngine.md` (Phase 3.1).
6. `audit_screener.md` (Phase 3.2).
7. `audit_selector.md` (Phase 3.3).
8. `audit_event_sentiment.md` (Phase 4.1).
9. `audit_modelFactory.md` (Phase 4.2).
10. `audit_risk_management.md` (Phase 5.1).
11. `audit_execution.md` (Phase 5.2).
12. `audit_corporate_actions.md` (Phase 5.3).
13. `audit_backtesting.md` (Phase 6.1).
14. `audit_ihm.md` (Phase 6.2).
15. `audit_watcher.md` (Phase 6.3).
16. `audit_global.md` (Phase 7 = solde transverse + backlog long terme).

---

## Garde-fous transverses

- **Ne JAMAIS skipper Phase 1** : tout le reste suppose Alembic en place,
  Protocols `core/interfaces.py` créés, equity fatal actif, secrets externalisés.
- **Tests verts entre chaque sous-phase**, sinon revert et relancer le subagent
  Plan.
- **Documentation = partie de la sous-phase**, pas une dette à part.
- **Cocher `audit_*.md` au fur et à mesure** pour traçabilité.
- **Backlog explicite** pour ce qui n'est pas faisable en 6-8 semaines (mode
  shadow live, EDGAR 8-K, fine-tune FinBERT, dashboard Grafana).

