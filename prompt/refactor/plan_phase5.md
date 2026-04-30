# Plan Phase 5 — Décision & exécution

> Source : `prompt/refactor/plan.md` §Phase 5 (lignes 191-211), `prompt/refactor/audit_risk_management.md`, `prompt/refactor/audit_execution.md`, `prompt/refactor/audit_corporate_actions.md`.
> Périmètre : `risk_management/` (5.1) puis `execution_engine/` (5.2) puis `corporate_actions/` (5.3).
> Conventions (rappel `plan.md` §Conventions) : 1 PR/commit par sous-phase, `pytest -q --no-cov` vert avant push, doc `doc/<module>.md` mise à jour dans la même sous-phase, audit coché en fin de sous-phase.

---

## 1. Inventaire des fichiers concernés

### 1.1 `risk_management/`

| Fichier | Rôle |
|---|---|
| `cli.py` (236 LOC) | CLI standalone : parse args, charge `account_risk_snapshot`, construit `RiskConfig`, appelle `PortfolioBuilder.build()`, persiste, **émet `run_summary`** — manque `account_equity_breakdown`. |
| `config.py` | `RiskConfig` (poids `score_weight=0.4`, `prediction_weight=0.6`, sizing ATR/Kelly). |
| `conviction.py` (16 LOC) | `compute_conviction(...)` legacy ; ré-exporté par `core/conviction.py`. À déprécier. |
| `portfolio_builder.py` (270 LOC) | `PortfolioBuilder.build()` : enrich → conviction (ligne 57 appel direct legacy) → tri → corrélation → sizing → contraintes. |
| `db_io.py` | `RiskRepository` : load_*, persist_*. À étendre avec `load_account_equity_breakdown`. |
| `audit.py` | `build_run_id`, `persist_decisions`, `persist_portfolio_targets`. |
| `models.py`, `position_sizer.py`, `kelly.py`, `constraints.py`, `correlation_filter.py`, `risk_checker.py`, `circuit_breaker.py` | Inchangés Phase 5. |

### 1.2 `execution_engine/`

| Fichier | Rôle |
|---|---|
| `cli.py` (~132 LOC) | CLI minimaliste : `parse_args` → `ProductionExecutor.execute_run` ; pas de sous-commande. |
| `config.py` | `ExecutionConfig` (modes simulate/paper/live, `enable_kill_switch` interne sur échecs consécutifs). |
| `models.py` | `OrderIntent`, `BrokerOrder`, `ExecutionEvent`, `EventType`, `ReconciliationStatus`. |
| `state_machine.py` (60 LOC) | `_TRANSITIONS` order lifecycle. **Pas de `ExecutionPhase`.** |
| `executor.py` (**1157 LOC**) | `execute_run` lignes 98-589 monolithique. |
| `broker_adapter.py` | `BrokerAdapter` wrappant `AlpacaTradingClient`. |
| `oco_manager.py`, `order_intents.py`, `broker_state_sync.py`, `reconciliation.py`, `tca.py` | Helpers inchangés Phase 5 (sauf reconciliation : surface `manual_review_symbols`/`blocked_symbols`). |
| `db_io.py` | `ExecutionRepository`. À étendre : `persist_kill_switch_run`. |
| `audit.py` | `build_execution_run_summary`. À enrichir avec `last_phase`, `manual_review_symbols`, `blocked_symbols`. |

### 1.3 `corporate_actions/`

| Fichier | Rôle |
|---|---|
| `cli.py` (~470 LOC) | 4 sous-commandes (sync/apply/status/run). `run_summary` n'a pas `schema_version`. |
| `engine.py` (~279 LOC) | `CorporateActionEngine.sync` + `apply` + `_apply_single` (ligne 233 vérifie `event.idempotency_key`). |
| `models.py` (~140 LOC) | `CorporateActionEvent` + `idempotency_key` lignes 60-67 — **manque `account_id`**. |
| `provider.py` | `CorporateActionProvider` Protocol + `AlpacaCorporateActionProvider`. |
| `db_io.py` | `CorporateActionRepository`. |
| `reconciliation.py` (74 LOC) | Pas de table d'audit dédiée. |

---

## 2. Consommateurs externes (impact rétrocompat)

### 2.1 `risk_management/`
- CLI consommé par IHM (`build_pipeline_command("risk_management", ...)`) — toute nouvelle option doit être facultative.
- `risk_management.conviction.compute_conviction` ré-exporté par `core.conviction` ; conserver le wrapper déprécié.

### 2.2 `execution_engine/`
- CLI consommé par IHM + `run_execution.py` (menu opérateur, equity fatal Phase 1.2).
- Nouvelle sous-commande `cancel-all` : **default subparser = `run`** pour préserver `python -m execution_engine --broker-mode paper …`.

### 2.3 `corporate_actions/`
- `idempotency_key` : changement = breaking ; conserver propriété legacy + nouvelle méthode `compute_idempotency_key(account_id)`.
- Migration Alembic backfill non destructif (clé legacy = `account_id="GLOBAL"`).

---

## 3. Sous-phases atomiques

### 5.1.a — `account_equity_breakdown` dans `run_summary` risk
- **Fichiers** : `risk_management/db_io.py` (méthode `load_account_equity_breakdown`), `risk_management/cli.py` (lignes 189-217 → `summary["account_equity_breakdown"]`, `attach_schema_version`).
- **Tests** : `tests/test_risk_management_run_summary.py` (`test_summary_contains_account_equity_breakdown`, `test_summary_has_schema_version`).
- **Doc** : `doc/risk_management.md` — section "Run summary risk".
- **Done** : `account_equity_breakdown` + `schema_version` présents.
- **Dépendances** : aucune.

### 5.1.b — Migrer la fusion conviction risk vers `core/conviction.py`
- **Fichiers** : `risk_management/portfolio_builder.py` (import + appel ligne 57), `risk_management/config.py` (`to_conviction_weights()`), `risk_management/conviction.py` (deprecation warning), `risk_management/cli.py` (`summary["conviction_weights"]`).
- **Tests** : `tests/test_portfolio_builder.py` (`test_builder_uses_core_conviction_fuse`), `tests/test_risk_management_conviction.py` (`test_legacy_emits_deprecation_warning`).
- **Doc** : `doc/risk_management.md` — section "Calcul de conviction" pointe vers `core/conviction.py`.
- **Done** : aucun appel `risk_management.conviction.compute_conviction` hors test legacy ; `final_score` strictement inchangé.
- **Dépendances** : 5.1.a.

### 5.1.c — Documenter et versionner les pondérations 40/60
- **Fichiers** : `doc/risk_management.md` (section "Pondérations conviction (40/60)"), `risk_management/cli.py` (`summary["conviction_weights_calibration"] = {"source": "default", "calibration_run_id": None}`).
- **Tests** : `tests/test_risk_management_run_summary.py` (`test_summary_contains_conviction_weights_calibration_placeholder`).
- **Doc** : `doc/risk_management.md`.
- **Done** : section doc + placeholder `run_summary`.
- **Dépendances** : 5.1.b.

---

### 5.2.a — Découper `executor.execute_run` + enum `ExecutionPhase`
- **Fichiers** : `execution_engine/executor.py` (extraire 10 sous-méthodes `_phase_*`), `execution_engine/state_machine.py` (enum `ExecutionPhase`).
- **Tests** : `tests/test_executor.py` (verts) + `tests/test_execution_state_machine.py` (`test_execution_phase_enum_values_stable`).
- **Doc** : `doc/execution_engine.md` — diagramme "10 phases".
- **Done** : `execute_run` < 100 lignes ; chaque `_phase_*` < 80 lignes.
- **Dépendances** : aucune.

### 5.2.b — State machine d'exécution explicite (transitions + invariants)
- **Fichiers** : `execution_engine/state_machine.py` (`_PHASE_TRANSITIONS`, `can_transition_phase`, `require_transition_phase`), `execution_engine/executor.py` (`_PhaseTracker`), `execution_engine/audit.py` (`summary["last_phase"]`).
- **Tests** : `tests/test_execution_state_machine.py`, `tests/test_executor.py` (`test_execute_run_records_last_phase_in_summary`).
- **Doc** : `doc/execution_engine.md` — diagramme transitions.
- **Done** : `last_phase ∈ {COMPLETED, ABORTED, FAILED}` documenté.
- **Dépendances** : 5.2.a.

### 5.2.c — **Kill switch global** : `python -m execution_engine cancel-all --account live1`
- **Fichiers** :
  - `execution_engine/cli.py` : refactor `argparse` avec `subparsers` ; default subparser = `run` (compat IHM).
  - Handler `_run_cancel_all` : valide compte + confirm-account en live, appelle `BrokerAdapter.cancel_all_open_orders()`, persiste `execution_kill_switch_runs`, émet `run_summary`.
  - `execution_engine/broker_adapter.py` : `cancel_all_open_orders() -> list[CancelResult]`.
  - `execution_engine/models.py` : `EventType.KILL_SWITCH_TRIGGERED`.
  - `execution_engine/db_io.py` : `persist_kill_switch_run`, `load_recent_kill_switch_runs`.
  - **Migration Alembic `00XX_execution_kill_switch_runs.py`**.
- **Tests** : `tests/test_execution_cli_cancel_all.py`, `tests/test_broker_adapter.py`, `tests/test_execution_cli_subcommands.py` (`test_cli_default_subcommand_is_run`).
- **Doc** : `doc/execution_engine.md` — section "Kill switch d'urgence" + lien `README.md`.
- **Done** : `--dry-run` lance simu + ligne en DB ; live exige `--confirm-account`.
- **Dépendances** : 5.2.a, 5.2.b.

### 5.2.d — Runbook `MANUAL_REVIEW` / `BLOCKED`
- **Fichiers** : `doc/execution_engine.md` (section "Runbook réconciliation"), `execution_engine/audit.py` (`summary["reconciliation_manual_review_symbols"]`, `..._blocked_symbols`).
- **Tests** : `tests/test_executor.py` (`test_summary_lists_manual_review_symbols`, `test_summary_lists_blocked_symbols`).
- **Doc** : `doc/execution_engine.md`.
- **Done** : runbook complet + symboles exposés.
- **Dépendances** : 5.2.a.

---

### 5.3.a — Documenter `idempotency_key` + ajouter `account_id`
- **Fichiers** : `corporate_actions/models.py` (méthode `compute_idempotency_key(account_id)`, propriété legacy conservée = `account_id=None` → `"GLOBAL"`), `corporate_actions/engine.py` (`_apply_single` utilise la nouvelle méthode), **migration Alembic** ajout colonne `account_idempotency_key VARCHAR(64) NULL` + UNIQUE INDEX, backfill legacy.
- **Tests** : `tests/test_corporate_actions_models.py` (`test_idempotency_key_includes_account_id`, `test_two_accounts_distinct_keys`, `test_legacy_property_equivalent_to_account_id_none`).
- **Doc** : `doc/corporate_actions.md` — section "Construction de l'`idempotency_key`".
- **Done** : nouvelle clé documentée ; aucun double-crédit replay events historiques.
- **Dépendances** : aucune.

### 5.3.b — Audit dédié `corporate_actions_audit_runs`
- **Fichiers** : migration Alembic `00XX_corporate_actions_audit_runs.py`, `database/sql/stock/corporate_actions_audit_runs.sql`, `corporate_actions/db_io.py` (`persist_audit_run`), `corporate_actions/cli.py` (chaque sous-commande appelle `persist_audit_run` + `attach_schema_version`).
- **Tests** : `tests/test_corporate_actions_audit_runs.py`, `tests/test_corporate_actions_run_summary.py` (`test_run_summary_has_schema_version`).
- **Doc** : `doc/corporate_actions.md` — section "Audit & monitoring", `doc/database.md` — table.
- **Done** : `SELECT * FROM corporate_actions_audit_runs` retourne les runs ; `schema_version` partout.
- **Dépendances** : 5.3.a.

### 5.3.c — Cross-check Yahoo dividends (opt-in)
- **Fichiers** : `corporate_actions/provider.py` (`YahooDividendCrossCheckProvider`, lazy import yfinance), `corporate_actions/cli.py` (`--cross-check {none,yahoo}`), `corporate_actions/db_io.py` (`load_dividend_events_in_range`), `pyproject.toml` (`[project.optional-dependencies] cross-check = ["yfinance>=0.2"]`).
- **Tests** : `tests/test_corporate_actions_cross_check_yahoo.py`.
- **Doc** : `doc/corporate_actions.md` — section "Cross-check Yahoo (opt-in)".
- **Done** : commande produit anomalies dans audit run sans crash si yfinance absent.
- **Dépendances** : 5.3.b.

---

## 4. Risques de régression et mitigations

| Sous-phase | Risque | Mitigation |
|---|---|---|
| 5.1.a | `load_account_equity_breakdown` lent. | Index `(account_id, trade_date)` ; fallback `None` + warning. |
| 5.1.b | Drift numérique sur `conviction_score`. | Test gold 5 cas tol `1e-12`. |
| 5.1.c | Doc-only → régression silencieuse poids. | `test_default_conviction_weights_are_40_60`. |
| 5.2.a | Régression silencieuse `execute_run`. | Pas de change de logique ; gold sur `metrics` retournés. |
| 5.2.b | State machine refuse transition légitime. | Couverture gold ; feature flag `strict_phase_transitions=False` 1 release. |
| 5.2.c | Sous-commandes argparse cassent IHM. | Default subparser = `run` ; `tests/test_ihm_pipeline_runner.py` vert. |
| 5.2.c | `cancel-all` annule ordres légitimes en plein run. | Refus si `execution_locks` actif (sauf `--force`) ; reason obligatoire. |
| 5.3.a | Migration backfill long. | NULL-able ; backfill batch 1000 ; documenté. |
| 5.3.a | Replay events legacy = doublons. | `is_event_applied` essaie nouvelle clé puis legacy. |
| 5.3.b | `summary_json` LONGBLOB volumineux. | Rétention 90j ; gzip > 50 KB. |
| 5.3.c | yfinance instable. | Lazy import ; try/except global ; jamais bloquant. |

---

## 5. Ordre d'exécution

```
5.1.a → 5.1.b → 5.1.c
                    (commit indépendant)
5.2.a → 5.2.b → 5.2.c
          ↓
          5.2.d
                    (commit indépendant)
5.3.a → 5.3.b → 5.3.c
```

---

## 6. Critère de sortie de Phase 5

- `run_summary` risk porte `account_equity_breakdown` + `schema_version` + `conviction_weights` (5.1.a + 5.1.b).
- `risk_management.portfolio_builder` consomme exclusivement `core.conviction.fuse` (5.1.b).
- Pondérations 40/60 documentées + plan de calibration référencé en backlog Phase 7 (5.1.c).
- `executor.execute_run` < 100 lignes ; 10 sous-méthodes `_phase_*` testables (5.2.a).
- `ExecutionPhase` enum + state machine + `last_phase` dans `run_summary` (5.2.b).
- **Kill switch testé** : `python -m execution_engine cancel-all --account live1` (5.2.c).
- Runbook `MANUAL_REVIEW` / `BLOCKED` + symboles exposés (5.2.d).
- `idempotency_key` corporate actions documentée + scope `account_id` (5.3.a).
- Table `corporate_actions_audit_runs` peuplée (5.3.b).
- Cross-check Yahoo opt-in disponible (5.3.c).
- Audits `audit_risk_management.md`, `audit_execution.md`, `audit_corporate_actions.md` cochés ✅ Phase 5.

