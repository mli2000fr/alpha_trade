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
- [ ] `account_equity_breakdown` dans `run_summary`.
- [ ] Migrer fusion conviction vers `core/conviction.py`.
- [ ] Documenter pondérations 40/60 (et plan de calibration empirique).

### 5.2 — `execution_engine/` (réf. `audit_execution.md`)
- [ ] Découper `executor.py` (`execute_run` en sous-méthodes + state machine
      explicite).
- [ ] Runbook `MANUAL_REVIEW` / `BLOCKED` dans `doc/execution_engine.md`.
- [ ] **Kill switch global** : `python -m execution_engine cancel-all
      --account live1`.

### 5.3 — `corporate_actions/` (réf. `audit_corporate_actions.md`)
- [ ] Documenter construction `idempotency_key`.
- [ ] Audit dédié `corporate_actions_audit_runs`.
- [ ] Évaluer Yahoo dividends comme cross-check.

**Critère de sortie** : execution reproductible et auditable, kill switch testé.

---

## Phase 6 — Périphérie (≤ 1 semaine)

### 6.1 — `backtesting/` (réf. `audit_backtesting.md`)
- [ ] `--commission-bps`, `--slippage-bps` (défauts > 0).
- [ ] `total_return_with_dividends` au rapport.
- [ ] Validation hold-out diagnostic screener phase 5-7.
- [ ] Profiles CLI consolidés.
- [ ] Migrer `signal_replay` vers `core/conviction.py`.

### 6.2 — `ihm/` (réf. `audit_ihm.md`)
- [ ] **Découper `pages/pipeline.py`** en sous-modules
      (`_workflow.py`, `_data_integrity.py`, `_execution_center.py`,
      `_alpha_scanner_diagnostics.py`, `_watcher_block.py`).
- [ ] Hook `atexit` dans `process_registry` (kill enfants).
- [ ] Rotation artefacts `IHM_RUNS_RETENTION_DAYS=30`.
- [ ] Audit shell quoting `process_registry`.
- [ ] Cache obligatoire (`@st.cache_data`) sur toutes les requêtes DB des pages.
- [ ] Test contractuel **IHM ↔ CLI** (introspection argparse).
- [ ] Auth basique optionnelle (token) si exposé hors localhost.
- [ ] Check démarrage `--server.address=localhost`.
- [ ] Documenter sécurité IHM dans `doc/ihm.md`.

### 6.3 — `watcher/` (réf. `audit_watcher.md`)
- [ ] Leader election via `execution_locks` (déjà partiellement Phase 1.2).
- [ ] Heartbeat persistant SQL (idem).
- [ ] Tests rigoureux allowlist PowerShell.
- [ ] Revue `protection_watcher_secrets.ps1`.

**Critère de sortie** : IHM modulaire, watcher mono-instance garanti, backtest
réaliste.

---

## Phase 7 — Revue transverse finale (≤ 3 jours)

> Items d'`audit_global.md` qui restent vraiment cross-modules après les
> Phases 2→6.

- [ ] **`import-linter`** enforced (interdit aux modules métier d'importer les
      implémentations directement).
- [ ] **Mode "shadow"** simulate parallèle d'un live (mesure dérive).
- [ ] **Calibration empirique** des poids conviction / signal_aggregator sur
      backtest glissant 6 mois (table `weights_calibration_runs`).
- [ ] **Stooq cross-check** OHLC daily / volume (best-effort).
- [ ] **SEC EDGAR 8-K** comme second canal news (long terme — peut sortir du
      scope).
- [ ] Dashboard observabilité minimal (Prometheus / Grafana ou équivalent).
- [ ] Drift ML monitoring auto.
- [ ] **Mapping table ↔ producteur ↔ consommateurs** (matrice impact).
- [ ] Doc cible : runbook incident provider, runbook réconciliation, guide
      "ajouter une nouvelle table" (template Alembic).
- [ ] Cocher tous les `✅` restants dans `audit_global.md` ; ce qui reste devient
      le **backlog "Long terme" suivant**.

**Critère de sortie** : `audit_global.md` à jour, items "Long terme"
explicitement reportés au backlog avec justification.

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

