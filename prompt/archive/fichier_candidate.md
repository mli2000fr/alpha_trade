# Inventaire des fichiers contenant le mot-clé `candidate`

> Date : 2026-07-11
> Total : ≈ 84 fichiers uniques, plus de 1 700 occurrences

---

## 📁 Fichiers Python (63 fichiers)

### 🔹 `alembic/versions/` (migrations DB)

| Fichier | Références clés |
|---|---|
| `alembic/versions/0020_weights_calibration_runs.py` | `candidates` (colonne JSON) |
| `alembic/versions/0023_stock_scores_history_capital_preset.py` | `idx_history_preset_candidate` (index), `is_candidate` |
| `alembic/versions/0029_selector_explainability_persistence.py` | `candidate_rank` (colonne) |
| `alembic/versions/0047_add_selection_rank_to_risk_execution.py` | `candidate_rank` |
| `alembic/versions/0048_drop_candidate_columns_from_score_snapshots.py` | `candidate_rank`, migration de suppression des colonnes candidate |

### 🔹 `backtesting/`

| Fichier | Références clés |
|---|---|
| `backtesting/backfill_scores_history.py` | `merged_candidates`, fusion de DataFrames |
| `backtesting/cli/_impl.py` | `filter_candidates_without_ml` |
| `backtesting/execution_lifecycle_replay.py` | `candidate for candidate in execution_result.targets` |
| `backtesting/fidelity.py` | `candidate_symbols`, `_sorted_unique_symbols`, `load_candidates_asof`, `missing_ml_symbols`, `candidate_column` |
| `backtesting/report.py` | `candidate = frame[column_name]` |
| `backtesting/risk_bridge.py` | `tag_short_candidates`, `_build_candidates`, `_build_candidates_from_day`, `CandidateScore` |
| `backtesting/risk_overlay.py` | `compute_weights(self, candidates, max_positions)` |
| `backtesting/screener_diagnostics/_impl.py` | `_pick_first_available_column`, `_candidate_mean_columns`, `_candidate_daily_columns` |
| `backtesting/sentiment_calibration.py` | `long_candidates`, `short_candidates` |
| `backtesting/simulator.py` | `_select_candidate_rows`, `record_candidates`, filtrage breakout |
| `backtesting/walk_forward.py` | `_candidate_roots` |
| `backtesting/weights_calibration.py` | `CalibrationCandidate`, `candidates: list[CalibrationCandidate]`, `lookback_candidates` |

### 🔹 `common/`

| Fichier | Références clés |
|---|---|
| `common/logging_setup.py` | `candidate = Path(log_path)` |
| `common/metrics.py` | `alpha_candidates_count` (Gauge Prometheus) |

### 🔹 `database/`

| Fichier | Références clés |
|---|---|
| `database/selector_reference.py` | `"candidates": "active-tradable"` |

### 🔹 `dataIntegrityEngine/`

| Fichier | Références clés |
|---|---|
| `dataIntegrityEngine/data_sanitizer_daily.py` | `candidates = [value for value in dates if value is not None]` |
| `dataIntegrityEngine/sync_latest_quotes.py` | `quote_iex_vs_consolidated_candidates` |

### 🔹 `event_sentiment/`

| Fichier | Références clés |
|---|---|
| `event_sentiment/config.py` | `candidate_reactivation_backfill_days: int = 365` |
| `event_sentiment/db_io.py` | `lignes candidates au` (docstring) |
| `event_sentiment/pipeline.py` | `candidate_reactivation_backfill_days` |
| `event_sentiment/scoring.py` | `for candidate in (64, 32, 16)` |

### 🔹 `execution_engine/`

| Fichier | Références clés |
|---|---|
| `execution_engine/db_io.py` | `candidate_lots` |
| `execution_engine/protection_watcher.py` | `time_stop_candidates` |

### 🔹 `flows/`

| Fichier | Références clés |
|---|---|
| `flows/daily_pipeline.py` | `candidates_count as _candidates_count` |

### 🔹 `ihm/pages/`

| Fichier | Références clés |
|---|---|
| `ihm/pages/_data_integrity.py` | `candidates: list[tuple[tuple[str, str, str, int], dict, dict]]` |
| `ihm/pages/_execution_center/__init__.py` | `DEFAULT_ML_CANDIDATE_DECISION_THRESHOLDS`, `DEFAULT_ML_CANDIDATE_DOWN_THRESHOLDS`, `DEFAULT_ML_CANDIDATE_HORIZONS`, `DEFAULT_ML_CANDIDATE_UP_THRESHOLDS`, `grilles candidate` |
| `ihm/pages/_execution_center/_render_pending.py` | `grilles candidate` |
| `ihm/pages/_shared.py` | `candidates = value if isinstance(value, list) else []` |
| `ihm/pages/backtesting/__init__.py` | `candidate_compare` |
| `ihm/pages/ml.py` | `selector_universe_max_candidate_rank` |
| `ihm/pages/ops_infra.py` | `alpha_candidates_count` |
| `ihm/pages/pipeline.py` | `candidate = str(widget_value or default).strip().lower()` |
| `ihm/pages/screening.py` | `build_candidate_explainability_payload` |
| `ihm/pages/weights_calibration_runs.py` | `_build_candidates_frame`, `candidates_df` |

### 🔹 `ihm/services/`

| Fichier | Références clés |
|---|---|
| `ihm/services/backtesting_registry.py` | `candidate_kinds: list[str]` |
| `ihm/services/compliance_loader.py` | `candidates = [p for p in root.iterdir() if p.is_dir()]` |
| `ihm/services/doc_links.py` | `candidate = (PROJECT_ROOT / path_part).resolve()` |
| `ihm/services/ml_artifacts.py` | `selector_universe_max_candidate_rank` |
| `ihm/services/notifications_preferences.py` | `candidates = re.split(r"[;,\n]+", raw)` |
| `ihm/services/notifications.py` | `candidates: list[str]` |
| `ihm/services/pipeline_ml_defaults.py` | `Grilles candidate (resserrées swing 2-10 j)` |
| `ihm/services/pipeline_runner.py` | `DEFAULT_ML_CANDIDATE_DECISION_THRESHOLDS`, `DEFAULT_ML_CANDIDATE_DOWN_THRESHOLDS`, `DEFAULT_ML_CANDIDATE_HORIZONS`, `DEFAULT_ML_CANDIDATE_UP_THRESHOLDS`, `grilles candidate` |
| `ihm/services/process_registry.py` | `candidate = run_dir / file_name` |
| `ihm/services/queries.py` | `build_candidate_explainability_payload` |
| `ihm/services/run_summary.py` | `selected_candidates`, `selector_earnings_blackout_candidates`, `_format_alpha_scanner_candidate_detail_line`, `candidate_explainability_payload`, `candidate.get("rank")`, `candidate.get("symbol")` |
| `ihm/services/screener_recommendations.py` | `candidate = payload.get("recommended_scenario")` |
| `ihm/services/varEnv.py` | `candidate_dir in ("conf", "config")`, `candidate = ancestor / candidate_dir / "var_env.json"` |

### 🔹 `modelFactory/`

| Fichier | Références clés |
|---|---|
| `modelFactory/cli.py` | `--candidate-horizons`, `--candidate-up-thresholds`, `--candidate-down-thresholds` |
| `modelFactory/config.py` | `candidate_horizons`, `candidate_up_thresholds`, `candidate_down_thresholds`, `candidate_decision_thresholds` |
| `modelFactory/evaluation.py` | `candidate_thresholds`, `candidates: list[dict[str, Any]]` |
| `modelFactory/global_model.py` | `candidate_thresholds=cfg.threshold_optimization.candidate_decision_thresholds` |
| `modelFactory/tabular_baseline.py` | `candidate_thresholds=cfg.threshold_optimization.candidate_decision_thresholds` |
| `modelFactory/target_optimization.py` | `TargetCandidateResult`, `score_target_candidate`, `find_best_candidate_for_horizon`, `candidates` |
| `modelFactory/trainer.py` | `"candidates": []` |

### 🔹 `risk_management/`

| Fichier | Références clés |
|---|---|
| `risk_management/cli.py` | `candidates`, `candidate_dates`, `candidate_snapshot_date`, `candidate_freshness_days`, `candidate_status` |
| `risk_management/concentration.py` | `record_candidates(self, symbols: list[str], trade_date: date)` |
| `risk_management/config.py` | `filter_candidates_without_ml: bool = False` |
| `risk_management/correlation_filter.py` | `candidates: list[EnrichedSelection]` |
| `risk_management/db_io.py` | `eligible_candidates`, `blocked_candidates`, `blocked_candidate_available`, `_level_candidates` |
| `risk_management/factor_model.py` | `filtered_candidates: list[EnrichedCandidate]`, `candidate_symbols` |
| `risk_management/live_pipeline_guards.py` | `candidate_count: int = 0`, `GuardReport` |
| `risk_management/portfolio_builder.py` | `_apply_regime_scoring_to_candidates`, `apply_full_regime_to_candidates`, `shielded_candidates`, `_build_enriched_candidates`, `EnrichedCandidate` |

### 🔹 `screener/`

| Fichier | Références clés |
|---|---|
| `screener/pipeline.py` | `CANDIDATE_COLUMNS`, `_empty_candidates()` |
| `screener/stock_screener.py` | `candidates, stage_counts = screen_recent_prices(...)` |

### 🔹 `selector/`

| Fichier | Références clés |
|---|---|
| `selector/scanner.py` | `_summarize_zero_candidate_filters`, `_scan_primary_candidates`, `selected_candidates`, `merged_candidates`, `lignes_candidates` |
| `selector/short_score.py` | `tag_short_candidates()` |

### 🔹 `service/`

| Fichier | Références clés |
|---|---|
| `service/market/regime_manager.py` | `_escalate(current: RegimeMode, candidate: str) -> RegimeMode` |

### 🔹 `tests/`

| Fichier | Références clés |
|---|---|
| `tests/benchmarks/test_screener_run.py` | `candidates = [...]` |
| `tests/test_alpha_scanner.py` | `is_candidate`, `test_update_database_does_not_write_candidate_selection_flags` |
| `tests/test_backtesting.py` | `is_candidate` (DataFrame fixtures) |
| `tests/test_backtesting_fractional.py` | `candidate_rank=1` |
| `tests/test_backtesting_refactor.py` | `candidates = pd.DataFrame({"symbol": ["A", "B", "C"]})` |
| `tests/test_capital_preset_universe_yield.py` | `test_synthetic_universe_yields_at_least_5_candidates_per_preset` |
| `tests/test_db_io_v2.py` | `candidates JSON`, `test_load_candidates_asof_uses_history_snapshot` |
| `tests/test_event_pipeline_defaults.py` | `candidates=None` |
| `tests/test_event_pipeline_progress_callback.py` | `candidate_reactivation_backfill_days=30` |
| `tests/test_event_sentiment_run_summaries.py` | `load_candidate_symbols` |
| `tests/test_execution_db_io.py` | `candidate_rank INT` (schéma SQL) |
| `tests/test_execution_engine_executor.py` | `candidate_rank=1` |
| `tests/test_factor_model.py` | `sample_enriched_candidates`, `EnrichedSelection` |
| `tests/test_ihm_cli_contract.py` | `candidates: Iterable[str]` |
| `tests/test_ihm_pipeline_e2e.py` | `candidate grids` |
| `tests/test_ihm_run_summary.py` | `selector_earnings_blackout_candidates` |

### 🔹 Racine du projet

| Fichier | Références clés |
|---|---|
| `validate_score_predictiveness.py` | `--no-candidates-only` |

---

## 📁 Fichiers non-Python (21 fichiers)

### 🔹 Artefacts JSON

| Fichier | Références clés |
|---|---|
| `.import_linter_cache/76079ced8b8e3cdfd97b78278727913324215634.data.json` | Import path `candidate_filters` |
| `artifacts/ihm_backtesting_runs/run/.../replay_diagnostic_summary.json` | `candidate_rows`, `candidate_symbols`, `candidate_symbol_count` (très nombreuses occurrences) |
| `artifacts/ihm_backtesting_runs/run/.../report.json` | `candidate_target_parity_summary_json` |
| `artifacts/sentiment_walk_forward/all_presets/report.json` | `candidates_only: true` |

### 🔹 Fichiers de configuration

| Fichier | Références clés |
|---|---|
| `config/fidelity_baseline_catalog.json` | `parity_diverged_session_ratio`, `candidate→target` |

### 🔹 Documentation (`doc/`)

| Fichier | Références clés |
|---|---|
| `doc/manuel/30_glossaire_financier.md` | Définition de **Candidate** |
| `doc/manuel/31_glossaire_application.md` | `is_candidate` |
| `doc/ml.md` | `candidate_rank max`, `--selector-universe-max-candidate-rank` |
| `doc/modelFactory.md` | `candidate_rank <= N` |
| `doc/question_1.md` | `grilles candidate` |
| `doc/risk_management.md` | `CandidateScore`, propagation dans `risk_decisions` |
| `doc/screener.md` | `is_candidate` (flag initialisé à 0) |
| `doc/selector_pipeline_compatibility.md` | `candidate_rank`, compatibilité schéma |
| `doc/selector-driven.md` | `is_candidate`, `candidate_rank` |
| `doc/selector.md` | `_tag_short_candidates()` (Option B) |
| `doc/sentiment_issue.md` | `is_candidate = 1`, périmètre `candidates` vide |
| `doc/sentiments_migration.md` | `symbol_source` (`candidates`, `stock_bars_daily`) |
| `doc/synthese_long_short.md` | `apply_full_regime_to_candidates()` |

### 🔹 Prompts & Refactoring (`prompt/`, `refactor/`)

| Fichier | Références clés |
|---|---|
| `prompt/bug_long_short.md` | `is_candidate=1`, ~120 candidats/jour |
| `prompt/plan_short_long.md` | `candidates_df`, `EnrichedCandidate` |
| `prompt/refactor_ml.md` | **Document maître du refactoring ML-First** : suppression `candidate -> ML`, `is_candidate`, `filter_candidates_without_ml`, `symbol_source=candidates` |
| `prompt/to-check/LiquiditeDynamique.md` | `EnrichedCandidate` |
| `prompt/to-check/RisqueSectoriel.md` | `candidates: list[EnrichedCandidate]` |
| `refactor/backtest_vs_live_roadmap.md` | `candidate -> target` rejouable |
| `refactor/backtesting/audit_plan_resume.md` | `_select_candidate_rows` |

### 🔹 IHM README

| Fichier | Références clés |
|---|---|
| `ihm/README.md` | `candidate_rank` max, filtrage d'univers ML |

---

## 📊 Statistiques

| Catégorie | Nombre de fichiers |
|---|---|
| **Fichiers Python (`.py`)** | **63** |
| Fichiers JSON d'artefacts | **4** |
| Fichiers Markdown (doc) | **13** |
| Fichiers Markdown (prompt/refactor) | **7** |
| Fichier de config (`.json`) | **1** |
| **Total** | **≈ 88 fichiers** |

---

## 🎯 Modules les plus impactés (top 5)

| # | Module | Fichiers concernés | Poids |
|---|---|---|---|
| 1 | **`risk_management/`** | 8 fichiers | Cœur de la logique candidate (portfolio_builder, factor_model, cli, db_io) |
| 2 | **`ihm/`** | 22 fichiers | Interface utilisateur et services (pages, services, run_summary) |
| 3 | **`backtesting/`** | 12 fichiers | Simulateur, fidélité, risk_bridge, weights_calibration |
| 4 | **`modelFactory/`** | 7 fichiers | Optimisation des cibles et hyperparamètres |
| 5 | **`tests/`** | 16 fichiers | Tests unitaires et d'intégration |

---

## 🔑 Constats clés

1. **`is_candidate`** est utilisé comme flag SQL dans `stock_scores` et `stock_scores_history` — c'est le point d'entrée de toute la chaîne candidate.
2. **`candidate_rank`** est une colonne persistée dans les snapshots et utilisée pour le classement selector.
3. **`CANDIDATE_COLUMNS`** dans `screener/pipeline.py` définit le schéma canonique des colonnes candidate.
4. **`EnrichedCandidate`** / **`CandidateScore`** sont des structures métier centrales dans `risk_management/` et `backtesting/`.
5. **`filter_candidates_without_ml`** dans `risk_management/config.py` contrôle le basculement entre les mondes candidate-first et ML-first.
6. **`symbol_source = "candidates"`** est le défaut IHM et CLI pour `ml_train` / `ml_predict`.
7. Le document **`prompt/refactor_ml.md`** décrit la stratégie complète de suppression de la dépendance `candidate`.
