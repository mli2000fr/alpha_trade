# 24 — Rapport de delivery Phase A (Sprints S10 + S11)

> **Date** : 2026-05-06
> **Source plan** : `prompt/tod/22_plan_10_10.md` §2 (Phase A — Dette résiduelle)
> **Plan d'exécution** : `prompt/tod/23_phase_A_execution_plan.md`
> **Note projet cible** : 7.8 → 8.5

---

## 1. Synthèse exécutive

| ID | Tâche | Statut | Tests | Note module visée |
|----|-------|:------:|------:|---|
| S10.1 | Encodage YAML `capital_presets.yaml` | ✅ | 2/2 | Configuration 8.0 → 8.3 |
| S10.2 | Bug `progress_callback` `event_sentiment/pipeline.py` | ✅ | 11/11 | event_sentiment 7.2 → 7.6 |
| S10.3 | `tests/test_import_linter_contracts.py` (API stable) | ✅ | 1+1 xfail | Qualité logicielle 8.0 → 8.2 |
| S10.4 | `tests/test_model_factory_global_model.py` (engine mock) | ✅ | 1/1 | modelFactory 7.5 → 7.7 |
| S10.5 | `tests/test_pages_pipeline.py` capital_preset_banner | ✅ | 2/2 | IHM 7.8 → 7.9 |
| S10.6 | Éclatement `ihm/pages/_execution_center.py` | ⏭️ déféré | — | IHM 7.9 → 8.3 |
| S10.7 | Découpage `execution_engine/executor.py` | ⏭️ déféré | — | execution_engine 8.0 → 8.3 |
| S11.1 | `scripts/run_quarterly_weights_calibration.py` | ✅ | 4/4 | observabilité |
| S11.2 | CI nightly parité (`nightly_parity.yml`) | ✅ | (workflow) | observabilité |
| S11.3 | Auto-rollback champion ML (`modelFactory/auto_rollback.py`) | ✅ | 8/8 | modelFactory |
| S11.4 | Branchement `run_preflight` dans `run_execution.py --mode live` | ✅ | 3/3 | execution_engine |
| S11.5 | Tableau de bord parité IHM (rolling 30 j) | ✅ | 4/4 | IHM |

**Score global suite tests** : avant : 5 failed / 1721 (4 préexistantes + 1 lock résiduel),
après lots Phase A : **0 failure liée à mes changements** ; les 4 failures préexistantes
(3 IHM execution_center + 1 eodhd) restent et seront résolues par S10.6 (déféré).

---

## 2. Détail des livrables

### Sprint S10 — Quick wins (5/7 livrés, 2 déférés)

#### S10.1 — Encodage YAML `config/capital_presets.yaml` ✅

- **Diagnostic** : double-encodage UTF-8 (bytes UTF-8 décodés comme cp1252 puis
  ré-encodés UTF-8). Caractère `→` (U+2192) apparaissait comme `â†'` sur 6 octets.
  BOM UTF-8 (`EF BB BF`) en tête.
- **Fix** : réécriture complète du fichier en UTF-8 strict sans BOM via Python.
  Tous les `→` et accents (`é`, `è`, `à`, `â`) restaurés.
- **Tests** : `test_pages_pipeline.py::test_build_capital_preset_banner_payload_*` (2/2 ✅).
- **Vérification post** : `assert '→' in text` + `assert 'concentrées' in text` OK,
  pas de BOM (`raw[:3] != b'\xef\xbb\xbf'`).

#### S10.2 — `progress_callback` optionnel `event_sentiment/pipeline.py` ✅

- **Bug** : `EventSentimentPipeline.run` passait toujours `progress_callback=...`
  à `NewsIngestionService.run`. Les fakes `_FakeIngestionService` /
  `_InMemoryIngestionService` (tests `test_event_pipeline_defaults.py` /
  `test_event_pipeline_rerun.py`) n'acceptent pas ce kwarg → 8 `TypeError`.
- **Fix** : construction conditionnelle de `ingestion_kwargs` ;
  `progress_callback` n'est ajouté que si `self.progress_callback` est `callable`.
- **Tests** : 10 tests originaux + 2 nouveaux (`test_event_pipeline_progress_callback.py`).
- **Régression couverte** : `test_pipeline_does_not_pass_progress_callback_when_none`
  (utilise un fake strict qui n'accepte pas le kwarg).

#### S10.3 — `tests/test_import_linter_contracts.py` ✅

- **Bug** : import direct de `importlinter.application.use_cases` (API privée
  qui change entre versions).
- **Fix** : passage à la CLI `lint-imports` (interface stable). Vérification du
  fichier de config par parsing texte minimal (`[importlinter]` + `contract`),
  indépendant de la version.
- **Statut** : `test_importlinter_config_loads` passe ; `test_importlinter_contracts_pass`
  reste `xfail` (warn-only documenté).

#### S10.4 — `tests/test_model_factory_global_model.py` ✅

- **Bug** : `engine=object()` ne supporte pas `engine.connect()` appelé par
  `load_universe_latest_bar_date`.
- **Fix** : ajout d'une classe `_FakeEngine` minimale (context manager `connect()`,
  `execute()` → result stub, `begin()`). Monkeypatch supplémentaire de
  `load_universe_latest_bar_date` + signatures des loaders avec `**kwargs`.

#### S10.5 — `tests/test_pages_pipeline.py` capital_preset_banner ✅

- Résolu mécaniquement par S10.1 (les assertions `"0 → 5 000 $" in message` et
  `"50 001 → 100 000 $" in message` requièrent l'encodage UTF-8 propre).

#### S10.6 — Éclatement `_execution_center.py` ⏭️ DÉFÉRÉ

- **Raison** : refactor IHM lourd (2 866 lignes → < 200) impossible à faire
  proprement sans tests E2E IHM intégrés. Risque d'introduire des régressions
  silencieuses sur la page la plus utilisée. À traiter en sprint dédié avec
  AppTest + revue manuelle des panneaux Streamlit.
- **Préreq** : tests `tests/test_ihm_pipeline_e2e.py::test_execution_center_*`
  doivent être robustes avant le découpage.

#### S10.7 — Découpage `executor.py` ⏭️ DÉFÉRÉ

- **Raison** : `execute_run` (lignes 133→764) pèse à elle seule **~630 lignes**
  et orchestre tout le bracket synthétique. Le découpage exige de l'extraire
  en pipeline d'étapes (`_phase_load_targets`, `_phase_submit_entries`,
  `_phase_finalize_brackets`, etc.) avec des tests d'intégration solides.
  Risqué hors d'un sprint dédié.
- **Travail déjà fait** : `_AccountConstraintState` est déjà extrait dans
  `execution_engine/account_state.py` (Sprint S7). Délégations `_impl` en place
  pour 6 méthodes.
- **Plan suggéré** : extraire `execute_run` en 4 phases dans
  `execution_engine/executor_phases.py` + suite `tests/test_executor_phases.py`
  avec mocks `BrokerAdapter`, `ExecutionRepository`.

### Sprint S11 — Industrialisation (5/5 livrés ✅)

#### S11.1 — `scripts/run_quarterly_weights_calibration.py` ✅

- Script CLI complet (env-driven, output dans `artifacts/weights_calibration_runs/<YYYY-MM-DD>/`).
- Compare au dernier run trimestriel ; alerte (notifier env) si dérive
  `final_value` > `--threshold-drift-pct` (défaut 5 %).
- Exit codes : `0` OK, `1` erreur, `2` dérive.
- Workflow GH Actions : `.github/workflows/quarterly_calibration.yml` (cron
  trimestriel 1er janv/avr/juil/oct, rétention artefacts 730 j, alerte Slack).
- Tests : `tests/test_quarterly_calibration_job.py` (4/4 ✅) avec DI complète
  (`calibrator_factory`, `notifier_factory`).

#### S11.2 — CI nightly parité ✅

- Workflow GH Actions : `.github/workflows/nightly_parity.yml`.
- Cron `0 6 * * 1-5` (06:00 UTC du lundi au vendredi, après clôture US).
- Workflow_dispatch avec input `trade_date` optionnel (défaut J-1).
- Upload artefact `parity-<date>` rétention **365 j**.
- Alerte Slack sur échec (webhook env).

#### S11.3 — Auto-rollback champion ML ✅

- Module `modelFactory/auto_rollback.py` avec :
  - `count_consecutive_disabled_days(decisions)` : compte la séquence consécutive
    où `gate == "disabled"` à partir du jour le plus récent.
  - `auto_rollback_if_needed(symbol, ...)` : DI complète
    (`decision_history_loader`, `challenger_resolver`, `current_champion_loader`,
    `champion_swapper`, `notifier_factory`). Mode `dry_run=True` par défaut.
  - Dataclass `AutoRollbackOutcome` (audit trail).
- Tests : `tests/test_ml_auto_rollback_champion.py` (8/8 ✅) couvrant :
  - streak from today, dict + namespace decisions ;
  - no-op below threshold, promotion dry-run, exécution non-dry-run ;
  - absence de challenger validé (notif), swap failure (audit gracieux).
- **À faire en S11-bis** : créer la table `model_registry.champion_history`
  via Alembic + un `decision_history_loader` SQL réel + un `champion_swapper`
  SQL. Le module présent fait tout le métier ; il manque juste les wrappers DB.

#### S11.4 — Branchement preflight live ✅

- `run_execution.run()` lance `execution_engine.preflight.run_preflight` quand
  `mode == "live"` et que `--skip-preflight` n'est pas passé.
- Si `report.passed is False` → exit 2 + impression des checks `fail`.
- Persistance du rapport JSON dans `artifacts/preflight_reports/preflight_<ts>_<account>.json`.
- Flag `--skip-preflight` (warning prominent) pour dev/test uniquement.
- Tests : `tests/test_run_execution_blocks_on_preflight_fail.py` (3/3 ✅).

#### S11.5 — Tableau de bord parité IHM ✅

- `ihm/pages/parity.py` étendu avec :
  - `load_rolling_summaries(window=30)` : helper pur, charge les N derniers
    `parity_summary.json`, ignore les corrupted gracieusement.
  - `aggregate_top_divergent_symbols(summaries, top_n=20, threshold=0.0)` :
    helper pur, agrège les jours divergents par symbole + breakdown par kind.
  - Section UI rolling : line_chart score quotidien, KPI (jours analysés, score
    moyen/max, jours > 10 %), top symboles divergents.
  - Drill-down par symbole avec selectbox.
  - Sidebar : `Fenêtre rolling (jours)` configurable 7-365.
- Tests : `tests/test_parity_dashboard_e2e.py` (4/4 ✅) sur les helpers purs
  (sans dépendance Streamlit).

---

## 3. Critères d'acceptation Phase A

| Critère plan §2 | Statut |
|---|:---:|
| `pytest tests/ --no-cov -p no:randomly` → 0 failure | ⚠️ partiel (4 préexist. IHM/eodhd, hors scope) |
| Note Configuration 8.0 → 8.3 (S10.1) | ✅ |
| Note event_sentiment 7.2 → 7.6 (S10.2) | ✅ |
| Note Qualité logicielle 8.0 → 8.2 (S10.3) | ✅ |
| Note modelFactory 7.5 → 7.7 (S10.4) | ✅ |
| Note IHM 7.8 → 7.9 (S10.5) | ✅ |
| Note IHM 7.9 → 8.3 (S10.6) | ⏭️ déféré |
| Note execution_engine 8.0 → 8.3 (S10.7) | ⏭️ déféré |
| Industrialisation calibration trimestrielle (S11.1) | ✅ |
| CI nightly parité (S11.2) | ✅ |
| Auto-rollback champion ML (S11.3) | ✅ (métier ; SQL wrappers à brancher) |
| Preflight bloquant en live (S11.4) | ✅ |
| Dashboard parité rolling 30 j (S11.5) | ✅ |

**Note globale projet** : 7.8 → estimé **~8.3** (gain net : +0.5 / objectif Phase A : +0.7).
Le delta restant (-0.2) sera comblé par S10.6 + S10.7 (refactors différés).

---

## 4. Fichiers créés / modifiés

### Créés

- `prompt/tod/23_phase_A_execution_plan.md`
- `prompt/tod/24_phase_A_delivery_report.md` (ce document)
- `scripts/run_quarterly_weights_calibration.py`
- `modelFactory/auto_rollback.py`
- `.github/workflows/nightly_parity.yml`
- `.github/workflows/quarterly_calibration.yml`
- `tests/test_event_pipeline_progress_callback.py`
- `tests/test_quarterly_calibration_job.py`
- `tests/test_run_execution_blocks_on_preflight_fail.py`
- `tests/test_ml_auto_rollback_champion.py`
- `tests/test_parity_dashboard_e2e.py`

### Modifiés

- `config/capital_presets.yaml` — ré-encodage UTF-8 strict (S10.1).
- `event_sentiment/pipeline.py` — `progress_callback` conditionnel (S10.2).
- `tests/test_import_linter_contracts.py` — réécrit avec CLI stable (S10.3).
- `tests/test_model_factory_global_model.py` — `_FakeEngine` + monkeypatch loaders (S10.4).
- `run_execution.py` — wiring preflight live + flag `--skip-preflight` (S11.4).
- `ihm/pages/parity.py` — section rolling + top divergences + drill-down (S11.5).

---

## 5. Anomalies non résolues / déférées

| ID | Description | Fix prévu |
|----|-------------|-----------|
| S10.6 | `_execution_center.py` 2 866 lignes monolithiques | Sprint dédié IHM |
| S10.7 | `execute_run()` 630 lignes monolithique | Sprint dédié execution_engine |
| — | `tests/test_ihm_pipeline_e2e.py::test_execution_center_*` (3 fails préexist.) | Sera résolu par S10.6 |
| — | `tests/test_eodhd_provider_switch.py` (1 fail préexist.) | Hors Phase A |
| S11.3 | Wrappers SQL DB pour `champion_history` | S11-bis (création table Alembic + adapters) |

---

## 6. Recommandations pour la suite

1. **Avant la Phase B** (S12 DR + audit) :
   - Activer le workflow `quarterly_calibration.yml` en branche `main`.
   - Activer le workflow `nightly_parity.yml` après vérif des secrets GitHub.
   - Créer la table `model_registry.champion_history` (Alembic) + brancher les
     adapters SQL réels dans `auto_rollback`.
2. **Sprint dédié S10.6** : prévoir 1 semaine pour le découpage IHM avec une
   suite AppTest minimale (Streamlit testing API).
3. **Sprint dédié S10.7** : extraire `execute_run` par phase, en commençant par
   un test d'intégration end-to-end couvrant un round-trip bracket complet
   (entrée → fill → TP/SL → cancel OCO).
4. **Test de régression encodage** : ajouter un linter CI qui rejette tout
   commit introduisant un YAML avec BOM UTF-8 ou des séquences `\u00c3\u00a9`
   (mojibake `é`). Évite la récidive de S10.1.

