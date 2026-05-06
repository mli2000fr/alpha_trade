# 12 — Rapport de livraison Sprint S2

**Sprint** : S2 — Cohérence pipeline & IHM
**Durée** : 1 semaine (clôture 2026-05-06)
**Livrable** : 6 anomalies (1 P0 reliquat + 1 P1 + 4 P2) + 5 tests dédiés

---

## 1. Périmètre adressé

| Anomalie | Priorité | État S1 | État S2 |
|---|---|---|---|
| **A-003** — `import_alpaca_bar` no-op silencieux quand `bars_provider != alpaca` | P0 | doc OK (README §6) | ✅ runtime WARNING + `skipped_reason='wrong_provider'` |
| **A-008** — Check env contextuel par compte / mode dans `run_execution.py` | P1 | — | ✅ `check_env(account_id, mode)` + `abort_missing_env` |
| **A-014** — Verrou IHM contre concurrence pipeline ↔ backtesting | P2 | — | ✅ `ihm/services/pipeline_lock.py` + branchement bilatéral |
| **A-017** — Télémétrie `data_source` mixte au runtime (screener / selector) | P2 | — | ✅ `core.run_summary.build_data_source_mix_check` + émission |
| **A-018** — Flag `--auto-watcher` dans `run_execution` | P2 | — | ✅ `_launch_post_watcher()` + flag CLI |
| **A-023** — Check homogénéité provider OHLCV au démarrage du pipeline | P2 | — | ✅ `dataIntegrityEngine/data_source_health.py` |

---

## 2. Modifications code

### 2.1 `dataIntegrityEngine/import_alpaca_bar.py` (A-003)

- `main()` détecte `bars_provider != alpaca` :
  - Logge un **WARNING** explicite (`"import_alpaca_bar no-op silencieux supprime …"`).
  - Émet un `run_summary` JSON avec :
    - `mode="noop"`
    - `warning="import_alpaca_bar_skipped_due_to_provider"`
    - `skipped_reason="wrong_provider"` (valeur canonique audit)
    - `bars_provider_active=<provider>` (diagnostic)
  - Retourne 0 sans appeler `import_alpaca_bars()`.
- Plus de no-op silencieux : l'opérateur / l'IHM voient désormais une trace explicite.

### 2.2 `run_execution.py` (A-008 + A-018)

- **A-008** — `check_env(account_id, mode)` :
  - `simulate` : seul `LOGIN_DB`/`PASSWORD_DB` requis.
  - `paper`/`live` : résolution via `AccountRegistry`.
  - `--account ghost` introuvable → message ciblé `"compte 'ghost' introuvable …"`.
  - `--account paper1` mais `mode=live` et `acct.mode=paper` → message ciblé.
  - `mode=live` sans aucun compte live configuré → message ciblé.
- `abort_missing_env(account_id, mode)` exit 1 avec message FATAL contextualisé.
- **A-018** — Flag `--auto-watcher` :
  - Argparse : `--auto-watcher` (action store_true).
  - `run(..., auto_watcher=False)` : si `True`, appelle `_launch_post_watcher()` qui spawn `subprocess.Popen` détaché de
    `run_execution_protection_watch.py --mode once --broker-mode <m> --trailing-stop-pct … [--exec-run-id …] [--account …]`.
  - PID watcher loggué pour traçabilité.

### 2.3 `ihm/services/pipeline_lock.py` (A-014)

- Nouveau module verrou **cross-process** fichier-JSON sous `artifacts/ihm_pipeline_runs/.locks/<scope>.lock`.
- Scopes : `pipeline` ⊥ `backtesting` (exclusion mutuelle bilatérale).
- API : `acquire_lock(scope, owner, run_id, pid)` → `LockHandle` ; lève `PipelineLockBusy` si conflit ; auto-récupération des locks "stale" (PID mort, détection `OpenProcess` sur Windows / `os.kill(pid, 0)` ailleurs).
- `release_lock(handle)` idempotent (tolère `None` et double-release).
- `set_locks_dir_for_tests(path)` pour isolation des tests.
- Branchements :
  - `ihm/services/process_registry.py:start_pipeline_workflow()` → `acquire_lock("pipeline", …)` puis `release_lock` en finally.
  - `ihm/services/backtesting_registry.py:start_backtesting_run()` → `acquire_lock("backtesting", …)` puis libération via `_finalize_if_needed()` quand le process se termine.

### 2.4 `core/run_summary.py` + `dataIntegrityEngine/data_source_health.py` (A-017 + A-023)

- `core.run_summary` :
  - `DEFAULT_DATA_SOURCE_MIN_DOMINANT_RATIO = 0.95`.
  - `aggregate_data_source_mix(counts)` : normalise `{data_source: rows}` en `{counts, ratios, rows_total, dominant_source, dominant_ratio}` (fusion des `NULL`/blank sous `"unknown"`).
  - `build_data_source_mix_check(counts, min_dominant_ratio)` : retourne `status ∈ {ok, warning, empty}`.
- `dataIntegrityEngine/data_source_health.py` :
  - `fetch_data_source_counts(engine, recent_days=30)` : SQL agrégé sur `stock_bars_daily` fenêtre roulante.
  - `check_data_source_homogeneity(engine, …)` : enveloppe défensive (DB cassée → `status="unavailable"`), logge un WARNING quand mix.
  - Seuil overridable via `config.yaml › market_data.data_source_min_dominant_ratio`.
- Émetteurs runtime :
  - `screener/stock_screener.py` enrichit son run_summary de `data_source_mix_check` + `data_source_mix`.
  - `selector/alpha_scanner.py` émet `{"data_source_mix_check": …}` via `_emit_run_summary`.

---

## 3. Tests ajoutés

| Fichier | Cas couverts | Anomalie |
|---|---|---|
| `tests/test_import_alpaca_bar_noop.py` | 4 tests : WARNING loggué, summary contient `skipped_reason='wrong_provider'`, pas d'appel `import_alpaca_bars` en mode no-op, mode `alpaca` exécute normalement. | A-003 |
| `tests/test_run_execution_check_env_per_account.py` | 7 tests : simulate ne demande pas Alpaca, missing DB détecté, account inconnu ciblé, paper-on-live bloqué, no-live-account détecté, valid pass, abort exit code + message. | A-008 |
| `tests/test_ihm_pipeline_concurrency_lock.py` | 6 tests : pipeline bloque backtesting, backtesting bloque pipeline, release autorise réacquisition, release idempotent, stale-pid récupéré, même run_id idempotent. | A-014 |
| `tests/test_data_source_consistency_runtime.py` | 10 tests : agrégation None/empty/blank, status ok/warning/empty, engine cassé→unavailable, WARNING loggué, seuil défaut ≥ 0.90, screener et selector émettent bien la clé. | A-017 + A-023 |
| `tests/test_run_execution_auto_watcher.py` | 5 tests : flag exposé, command builder OK avec/sans `--account`, FileNotFoundError si script absent, signature `run` accepte kwarg. | A-018 |

**Total tests S2 ajoutés : 32 — tous verts.**

---

## 4. Résultats de tests

```
$ python -m pytest --no-cov tests/test_import_alpaca_bar_noop.py \
    tests/test_run_execution_check_env_per_account.py \
    tests/test_ihm_pipeline_concurrency_lock.py \
    tests/test_data_source_consistency_runtime.py \
    tests/test_run_execution_auto_watcher.py
================ 32 passed in 2.80s ================
```

Non-régression sur le périmètre adjacent recommandé par `08_sprint_plan.md` :

```
$ python -m pytest --no-cov tests/test_import_alpaca_bar.py \
    tests/test_ihm_eodhd_provider_switch.py tests/test_run_execution.py \
    tests/test_executor.py tests/test_ihm_backtesting_registry.py
================ 52 passed in 4.82s ================
```

**Total : 84 / 84 verts** sur le scope S2 + adjacents.

> Les 10 échecs préexistants identifiés en S1 (`test_event_pipeline_*`,
> `test_import_linter_contracts`, `test_model_factory_global_model`)
> restent hors-scope S2 (à traiter en S3/S4/S6).

---

## 5. Critères d'acceptation S2

| Critère (`08_sprint_plan.md`) | État |
|---|---|
| Run no-op silencieux supprimé | ✅ WARNING + `skipped_reason='wrong_provider'` + clé `warning` dans run_summary |
| Lancement live sans creds → erreur claire | ✅ `abort_missing_env` exit 1 avec message contextualisé compte/mode |
| Télémétrie `data_source_mix` présente dans `run_summary` | ✅ screener + selector + dataIntegrityEngine |
| Verrou IHM pipeline ↔ backtesting | ✅ exclusion mutuelle bilatérale, stale-pid recovery, idempotent |
| Option `--auto-watcher` dans `run_execution` | ✅ flag + spawn détaché du watcher post-run |
| Check homogénéité au démarrage du pipeline | ✅ `check_data_source_homogeneity` + seuil configurable |

---

## 6. Notes techniques

- **A-014 robustesse Windows** : la détection PID vivant utilise `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` (ctypes) — gère les processus zombies du tracker IHM Streamlit.
- **A-018 sécurité shell** : `subprocess.Popen` détaché (`CREATE_NEW_PROCESS_GROUP` Windows), aucun `shell=True`, command list-form (pas d'injection).
- **A-023 valeur seuil** : `0.95` choisi comme conservateur (un audit de migration EODHD → Alpaca, ou inverse, doit déclencher l'alerte sans bloquer le pipeline). Overridable opérateur via `market_data.data_source_min_dominant_ratio`.
- **A-003 valeur canonique** : `skipped_reason="wrong_provider"` (string littérale audit) ; valeur précise du provider dans `bars_provider_active` pour observabilité.

---

## 7. Gain de notes attendu (audit)

| Module | Avant S1 | Après S1 | Après S2 (cible) |
|---|---|---|---|
| dataIntegrityEngine | 7.0 | 7.0 | **7.5** |
| IHM | 6.5 | 6.5 | **7.0** |
| Sécurité | 6.0 | 6.0 | **6.8** |
| Documentation | 5.5 | 7.0 | 7.0 |
| Configuration | 6.0 | 7.0 | 7.0 |
| Corporate actions | 6.5 | 7.0 | 7.0 |

---

## 8. Suivi pour Sprint S3 (live readiness)

- A-006 : parité backtest ↔ live ledger dividendes.
- A-007 : brancher `PnLSnapshot` réel dans `run_risk` (lecture
  `broker_positions_snapshots` + `execution_runs`).
- A-009 : assouplissement `weekly_trend_score` si univers vide.
- A-010 : émettre `rejected_for_notional` / `rejected_for_atr_missing` dans le `run_summary` du risk.
- A-011 : overrides `risk_max_drawdown_pct` / `risk_max_daily_loss_pct` aux 6 presets.

Le live trading reste **déconseillé** tant que S3 n'est pas livré (cf. `08_sprint_plan.md` § "À partir de quel sprint l'application devient suffisamment robuste …").

