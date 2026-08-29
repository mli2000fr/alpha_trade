# Inventaire API — modelFactory

Cet inventaire est dérivé des signatures présentes dans le code. Les symboles préfixés par `_` restent internes. Les numéros de ligne sont indicatifs ; le chemin et le nom du symbole sont les repères stables.

## `modelFactory/analyze_p21_attribution.py`

- ligne 36 — `def factor_for(eff_bps: float) -> float:`
- ligne 49 — `def _variant_stats(trades: pd.DataFrame, label: str, w: pd.Series) -> dict:`
- ligne 68 — `def main(run_dir: str, out_json: str | None, min_trades: int) -> None:`
## `modelFactory/auto_rollback.py`

- ligne 204 — `def _coerce_date(value: Any) -> date:`
- ligne 212 — `def decision_history_loader_sql(`
- ligne 260 — `def current_champion_loader_sql(`
- ligne 283 — `def champion_swapper_sql(`
- ligne 32 — `class AutoRollbackOutcome:`
- ligne 57 — `def count_consecutive_disabled_days(`
- ligne 77 — `def auto_rollback_if_needed(`
## `modelFactory/backfill_global_rank_history.py`

- ligne 114 — `def main() -> None:`
- ligne 28 — `def _resolve_engine():`
- ligne 42 — `def backfill_global_rank_history(batch_id: str, *, parquet_path: Path | None = None) -> dict:`
## `modelFactory/batch_diagnostics.py`

- ligne 146 — `class Section7Filters:`
- ligne 176 — `class BatchFilters:`
- ligne 192 — `def _load_config_defaults() -> dict[str, Any]:`
- ligne 203 — `def _load_section7_config() -> dict[str, Any]:`
- ligne 209 — `def _compute_section7_filters(`
- ligne 29 — `def _sanitize_float(value: Any) -> float | None:`
- ligne 295 — `def persist_batch_diagnostics(`
- ligne 517 — `def _get_latest_completed_batch_id(engine: Engine) -> str | None:`
- ligne 527 — `def get_batch_filters(`
- ligne 688 — `def filter_predictions(`
## `modelFactory/batch_logs.py`

- ligne 143 — `def batch_logs_text(batch_id: str) -> str:`
- ligne 30 — `def _safe_name(batch_id: str) -> str:`
- ligne 34 — `def _scan_log_files() -> list[Path]:`
- ligne 47 — `def extract_batch_log_lines(batch_id: str) -> list[str]:`
- ligne 59 — `def persist_batch_log(batch_id: str) -> Path | None:`
- ligne 85 — `def read_batch_log(batch_id: str) -> str | None:`
- ligne 96 — `def backfill_existing_batches() -> dict[str, int]:`
## `modelFactory/calibration.py`

- ligne 115 — `class TemperatureScaler:`
- ligne 12 — `def margin_from_logits(logits: np.ndarray | torch.Tensor) -> np.ndarray:`
- ligne 220 — `class VectorScaler:`
- ligne 24 — `class PlattCalibrator:`
- ligne 86 — `def margins_from_logits_or_margin(values: np.ndarray | torch.Tensor) -> np.ndarray:`
- ligne 97 — `def calibrator_from_state_dict(state: dict[str, Any] | None) -> PlattCalibrator | TemperatureScaler | VectorScaler | None:`
## `modelFactory/catboost_baseline.py`

- ligne 16 — `def _import_catboost() -> Any:`
- ligne 21 — `def run_catboost_baseline(`
## `modelFactory/champion_selection.py`

- ligne 114 — `def verify_route_artifact_signatures(`
- ligne 159 — `def is_under_quarantine(`
- ligne 196 — `def selection_score_from_result(result: dict[str, Any], metric: str = "selection_score") -> float:`
- ligne 254 — `def evaluate_selection_eligibility(`
- ligne 305 — `def _validate_metric_gates(result: dict[str, Any]) -> str | None:`
- ligne 33 — `class ArtifactSignatureError(RuntimeError):`
- ligne 369 — `def annotate_challengers(`
- ligne 385 — `def select_champion(`
- ligne 42 — `def _artifact_path_from_value(value: object) -> Path | None:`
- ligne 495 — `def build_challenger_ranking(`
- ligne 50 — `def _sha256_file(path: Path) -> str:`
- ligne 58 — `def build_artifact_signature_manifest(`
- ligne 94 — `def persist_artifact_signature_manifest(`
## `modelFactory/cleanup_incomplete_batches.py`

- ligne 16 — `def list_batches(include_completed: bool = False) -> list[str]:`
- ligne 39 — `def cleanup_batches(dry_run: bool = False, include_completed: bool = False) -> dict:`
- ligne 98 — `def main() -> None:`
## `modelFactory/cli.py`

- ligne 115 — `def _generate_and_save_batch_report(engine: Engine, batch_id: str) -> None:`
- ligne 140 — `def _resolve_predict_batch_id(artifacts_dir: Path) -> str | None:`
- ligne 1496 — `def _load_drift_baseline(engine, *, days: int = 30):`
- ligne 1523 — `def _emit_run_summary(summary: dict[str, object]) -> None:`
- ligne 1530 — `def _build_run_summary(`
- ligne 171 — `def _resolve_last_bar_date(engine) -> date | None:`
- ligne 186 — `def _load_synth_frame_for_range(engine, batch_id: str, dates) -> "pd.DataFrame":`
- ligne 217 — `def _build_training_batch_command(raw_args: list[str]) -> tuple[str, str]:`
- ligne 222 — `def _build_training_batch_metadata(opts: argparse.Namespace, cfg: TrainingConfig) -> str:`
- ligne 254 — `def _parse_selector_signal_modes_arg(values: list[str] | None) -> tuple[str, ...]:`
- ligne 267 — `def _parse_iso_date_arg(value: str) -> date:`
- ligne 274 — `class _LiveRunSummaryEmitter:`
- ligne 343 — `def build_arg_parser() -> argparse.ArgumentParser:`
- ligne 43 — `def _resolve_synth_best_h(opts, batch_id: str | None) -> int:`
- ligne 665 — `def main(args: list[str] | None = None) -> None:`
- ligne 85 — `def _load_live_dip_config() -> dict | None:`
## `modelFactory/config.py`

- ligne 10 — `class DataConfig:`
- ligne 148 — `class CalibrationConfig:`
- ligne 165 — `class WalkForwardConfig:`
- ligne 189 — `class BaselineConfig:`
- ligne 270 — `class GlobalModelConfig:`
- ligne 322 — `class TargetOptimizationConfig:`
- ligne 377 — `class ThresholdOptimizationConfig:`
- ligne 402 — `class ChampionSelectionConfig:`
- ligne 433 — `class ModelConfig:`
- ligne 481 — `class ReproducibilityConfig:`
- ligne 493 — `class TrainingConfig:`
## `modelFactory/cross_sectional.py`

- ligne 117 — `def _sector_zscore_column_name(source_col: str) -> str:`
- ligne 151 — `def _compute_symbol_raw_values(`
- ligne 203 — `def _build_benchmark_returns(`
- ligne 220 — `def _load_sector_mapping(engine) -> dict[str, str]:`
- ligne 321 — `def _map_to_gics_sector(db_sector: str) -> str:`
- ligne 330 — `def load_sector_groups(engine) -> dict[str, list[str]]:`
- ligne 350 — `def _compute_sector_features(`
- ligne 459 — `def _compute_cross_symbol_features(`
- ligne 578 — `def _compute_sector_neutral_features(`
- ligne 634 — `def build_cross_sectional_features_from_db(`
- ligne 75 — `def _sector_neutral_column_name(source_col: str) -> str:`
- ligne 792 — `def build_cross_sectional_features(`
- ligne 889 — `def merge_cross_sectional_features(`
## `modelFactory/data_loader.py`

- ligne 108 — `def load_symbol_latest_bar_date(engine: Engine, symbol: str, end_date: date | None = None) -> date | None:`
- ligne 122 — `def load_symbol_latest_bar_dates(`
- ligne 149 — `def load_universe_latest_bar_date(`
- ligne 172 — `def load_available_trading_dates(`
- ligne 213 — `def load_historical_prediction_scopes_from_scores_history(`
- ligne 302 — `def load_symbol_bars(`
- ligne 339 — `def load_benchmark_bars(`
- ligne 356 — `def load_universe_bars(`
- ligne 390 — `def _load_universe_bars_chunk(`
- ligne 419 — `def load_symbol_sentiment(`
- ligne 458 — `def load_symbols_sentiment(`
- ligne 495 — `def load_symbols_selector_context(`
- ligne 52 — `def _get_table_columns(engine: Engine, table_name: str) -> set[str]:`
- ligne 557 — `def load_symbol_selector_context(`
- ligne 60 — `def _coerce_date_value(value: object) -> date | None:`
- ligne 74 — `def _subtract_years(anchor_date: date, years: int) -> date:`
- ligne 81 — `def resolve_training_start_date(`
- ligne 93 — `def resolve_history_window_start_date(anchor_date: date | None, history_window_years: int | None) -> date | None:`
- ligne 98 — `def _build_in_clause(symbols: list[str]) -> tuple[str, dict[str, object]]:`
## `modelFactory/dataset.py`

- ligne 130 — `def generate_walk_forward_splits(`
- ligne 187 — `def chrono_split_by_dates(`
- ligne 220 — `def generate_walk_forward_splits_by_dates(`
- ligne 296 — `class FoldIsolationReport:`
- ligne 30 — `class ChronoSplit:`
- ligne 312 — `def validate_fold_isolation(`
- ligne 38 — `class WalkForwardSplit:`
- ligne 449 — `class FeatureScaler:`
- ligne 47 — `def _validate_ordered_frame(df: pd.DataFrame, *, date_column: str | None = None) -> None:`
- ligne 502 — `def build_sequences(features: np.ndarray, targets: np.ndarray, seq_len: int) -> tuple[np.ndarray, np.ndarray]:`
- ligne 527 — `def build_sequence_dataset(df: pd.DataFrame, scaler: FeatureScaler, seq_len: int, *, is_regression: bool = False) -> SequenceDataset | None:`
- ligne 539 — `class SequenceDataset(Dataset):  # type: ignore[type-arg]`
- ligne 56 — `def _purged_bounds(*, start: int, end: int, purge_tail: int) -> tuple[int, int]:`
- ligne 562 — `class SymbolDataModule(L.LightningDataModule):`
- ligne 68 — `def _embargoed_start(*, val_end: int, embargo_rows: int) -> int:`
- ligne 730 — `def prepare_symbol_frame(`
- ligne 79 — `def _purge_by_dates(`
- ligne 94 — `def chrono_split(`
## `modelFactory/db_registry.py`

- ligne 1008 — `def load_stock_scores_all_symbols(engine: Engine) -> list[str]:`
- ligne 1030 — `def _load_ticket_recherche_symbols() -> list[str]:`
- ligne 1054 — `def detect_batch_training_mode(engine: Engine, batch_id: str | None) -> str:`
- ligne 108 — `def _normalize_signal_modes(signal_modes: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:`
- ligne 1145 — `def get_serving_batch(engine: Engine) -> str | None:`
- ligne 1158 — `def set_serving_batch(engine: Engine, *, batch_id: str) -> None:`
- ligne 1169 — `def load_symbols_for_source(`
- ligne 1193 — `def load_tradable_universe_symbols(`
- ligne 120 — `def _load_distinct_symbols(engine: Engine, query: str) -> list[str]:`
- ligne 1216 — `def load_stock_bars_daily_symbols(engine: Engine) -> list[str]:`
- ligne 126 — `def has_score_context_filter(`
- ligne 135 — `def filter_symbols_by_score_context(`
- ligne 240 — `def _optional_float(value: Any) -> float | None:`
- ligne 250 — `def _optional_int(value: Any) -> int | None:`
- ligne 259 — `def build_governance_rows(`
- ligne 331 — `def ensure_registry_entry(engine: Engine, symbol: str, architecture: str = "lstm_attention") -> int:`
- ligne 380 — `def insert_training_batch(`
- ligne 425 — `def update_training_batch(engine: Engine, batch_id: str, **kwargs: Any) -> None:`
- ligne 437 — `def insert_training_run(`
- ligne 462 — `def update_training_run(engine: Engine, run_id: str, **kwargs: Any) -> None:`
- ligne 471 — `def _delete_predictions_chunked(conn: Any, run_ids: list[str], chunk_size: int) -> int:`
- ligne 500 — `def delete_batch_rows(`
- ligne 608 — `def load_training_run(engine: Engine, symbol: str, run_id: str | None = None, batch_id: str | None = None) -> dict[str, Any] | None:`
- ligne 652 — `def insert_metrics(engine: Engine, run_id: str, symbol: str, split_name: str, metrics: dict[str, float], *, model_name: str = "lstm_attention", horizon: int | None = None) -> None:`
- ligne 66 — `def _source_priority(source: str | None) -> int:`
- ligne 694 — `def count_completed_runs(`
- ligne 727 — `def upsert_metrics_full(`
- ligne 73 — `def _required_text(value: Any, *, field_name: str) -> str:`
- ligne 758 — `def upsert_directional_oos_metrics(`
- ligne 80 — `def _required_finite_float(value: Any, *, field_name: str) -> float:`
- ligne 817 — `def replace_model_governance(`
- ligne 870 — `def insert_predictions(engine: Engine, predictions: pd.DataFrame) -> int:`
- ligne 90 — `def _validate_predictions_frame(predictions: pd.DataFrame) -> None:`
- ligne 96 — `def _normalize_symbols(symbols: list[str]) -> list[str]:`
- ligne 964 — `def load_score_symbols(engine: Engine) -> list[str]:`
- ligne 971 — `def load_score_context(engine: Engine, *, limit: int | None = None) -> pd.DataFrame:`
- ligne 978 — `def load_stock_scores_symbols(engine: Engine) -> list[str]:`
- ligne 993 — `def load_stock_scores_history_symbols(engine: Engine) -> list[str]:`
## `modelFactory/dip_research/dip_context_pattern_analysis.py`

- ligne 1074 — `def _prod_universe(engine) -> pd.DataFrame:`
- ligne 1091 — `def _auc_for(y: np.ndarray, score: np.ndarray) -> float:`
- ligne 1095 — `def _run_deltas(engine, smoke: bool = False) -> None:`
- ligne 123 — `def assert_events(events: pd.DataFrame) -> None:`
- ligne 1326 — `def main() -> None:`
- ligne 150 — `def _reg(feature: str, family: str, source: str) -> None:`
- ligne 154 — `def _ema(s: pd.Series, span: int) -> pd.Series:`
- ligne 158 — `def _compute_bars_features(bars: pd.DataFrame) -> pd.DataFrame:`
- ligne 216 — `def _compute_beta126(dip_bars: pd.DataFrame, spy: pd.DataFrame) -> pd.DataFrame:`
- ligne 258 — `def _compute_market_features(engine: Any) -> pd.DataFrame:`
- ligne 297 — `def _load_universe_bars(engine: Any, top_n: int = 3000, bars_start: str = _BARS_START, bars_end: str = _BARS_END) -> pd.DataFrame:`
- ligne 319 — `def _compute_breadth_ranks(engine: Any, top_n: int = 3000, bars_start: str = _BARS_START, bars_end: str = _BARS_END):`
- ligne 352 — `def _compute_sector_features(engine: Any, uni: pd.DataFrame):`
- ligne 377 — `def build_features(engine: Any, events: pd.DataFrame, *, smoke: bool = False) -> pd.DataFrame:`
- ligne 53 — `def _quiet() -> None:`
- ligne 544 — `def _register_meta() -> None:`
- ligne 60 — `def _plog(msg: str) -> None:`
- ligne 617 — `def _load_panel():`
- ligne 626 — `def _feature_set(df: pd.DataFrame, fam: dict[str, str]) -> list[str]:`
- ligne 642 — `def _auc_rank(y: np.ndarray, score: np.ndarray) -> float:`
- ligne 653 — `def _group_stats(s1: pd.Series, s2: pd.Series) -> dict:`
- ligne 67 — `def build_dip_events(engine: Any) -> pd.DataFrame:`
- ligne 673 — `def _run_analyses(smoke: bool = False) -> None:`
- ligne 992 — `def _build_report(master, wl, ex, q12, ctx, null_max, q_df, feats, n_events=None,`
## `modelFactory/dip_research/dip_quality_static_model.py`

- ligne 108 — `def run_dataset(engine: Any, *, smoke: bool = False) -> None:`
- ligne 164 — `def _load_dataset() -> pd.DataFrame:`
- ligne 170 — `def _run_lr_wf(df: pd.DataFrame, feats: list[str], y_al: np.ndarray, folds,`
- ligne 205 — `def _fit_lgb_early(X_tr: np.ndarray, y_tr: np.ndarray, X_te: np.ndarray) -> np.ndarray:`
- ligne 220 — `def _pr_auc(y: np.ndarray, score: np.ndarray) -> float:`
- ligne 227 — `def run_models(*, smoke: bool = False) -> None:`
- ligne 391 — `def _sector_map(engine) -> dict[str, str]:`
- ligne 399 — `def _select_per_day(cands: pd.DataFrame, order_col: str, top_pct: float | None,`
- ligne 428 — `def run_portfolio(engine: Any, *, smoke: bool = False) -> None:`
- ligne 566 — `def run_report() -> None:`
- ligne 720 — `def _quintile_mono(quint: pd.DataFrame) -> bool:`
- ligne 728 — `def _q(quint: pd.DataFrame, qi: int):`
- ligne 739 — `def main() -> None:`
- ligne 85 — `def _greedy_compact(main: pd.DataFrame) -> list[str]:`
## `modelFactory/dip_research/dip_temporal_pattern_feasibility.py`

- ligne 1002 — `def main() -> None:`
- ligne 115 — `def _quiet() -> None:`
- ligne 122 — `def _plog(msg: str) -> None:`
- ligne 132 — `def run_events(engine: Any, *, smoke: bool = False) -> None:`
- ligne 143 — `def _load_market_features(engine: Any, bs: str, be: str, uni_start: str, top_n: int) -> pd.DataFrame:`
- ligne 160 — `def build_daily_panel(engine: Any, symbols: list[str], *, smoke: bool = False) -> pd.DataFrame:`
- ligne 228 — `def _shape_metrics(x: np.ndarray) -> dict[str, float]:`
- ligne 251 — `def run_panel(engine: Any, *, smoke: bool = False) -> None:`
- ligne 315 — `def _load_temporal(engine: Any) -> pd.DataFrame:`
- ligne 322 — `def _prod_universe(engine: Any, df: pd.DataFrame) -> pd.DataFrame:`
- ligne 339 — `def _select_features(df: pd.DataFrame) -> list[str]:`
- ligne 368 — `def run_coverage(engine: Any, *, smoke: bool = False) -> list[str]:`
- ligne 436 — `def _build_reps(seq: pd.DataFrame, feats: list[str]) -> dict[str, pd.DataFrame]:`
- ligne 465 — `def _chrono_folds(dates: np.ndarray, n_folds: int = N_FOLDS, purge_days: int = PURGE_DAYS,`
- ligne 494 — `def _fit_predict(rep_train: pd.DataFrame, rep_val: pd.DataFrame, y_tr: np.ndarray,`
- ligne 521 — `def _fold_metrics(y_val: np.ndarray, score: np.ndarray, fwd_val: np.ndarray) -> dict[str, float]:`
- ligne 535 — `def _summarize(aucs: list[float]) -> dict[str, float]:`
- ligne 546 — `def run_models(engine: Any, *, smoke: bool = False) -> None:`
- ligne 850 — `def _pr_auc_score(y: np.ndarray, score: np.ndarray) -> float:`
- ligne 861 — `def run_report() -> None:`
- ligne 986 — `def _quintile_monotonicity(quint: pd.DataFrame) -> str:`
## `modelFactory/dip_research/persistent_tail_price.py`

- ligne 119 — `def evaluate(panel: pd.DataFrame) -> pd.DataFrame:`
- ligne 199 — `def main() -> None:`
- ligne 57 — `def load_panel(engine: Any, batch_id: str, start_date: str, end_date: str) -> pd.DataFrame:`
- ligne 97 — `def compute_persistence(df: pd.DataFrame) -> pd.DataFrame:`
## `modelFactory/dip_research/persistent_top10_dip_parity.py`

- ligne 117 — `def _schedule_local(signals: pd.DataFrame, trading_days: pd.DatetimeIndex) -> pd.DataFrame:`
- ligne 133 — `def capacity_attribution(`
- ligne 230 — `def main() -> None:`
- ligne 61 — `def build_signals_parity(engine: Any, batch_id: str, start_date: str, end_date: str) -> pd.DataFrame:`
## `modelFactory/dip_research/persistent_top10_dip_portfolio.py`

- ligne 122 — `def build_signals(engine: Any, batch_id: str, start_date: str, end_date: str) -> pd.DataFrame:`
- ligne 185 — `def _pivot(bars: pd.DataFrame, col: str) -> pd.DataFrame:`
- ligne 189 — `def load_ohlcv_pivots(engine: Any, start_date: str, end_date: str, symbols: list[str]) -> dict[str, pd.DataFrame]:`
- ligne 202 — `def build_config(start_date: str, end_date: str) -> BacktestConfig:`
- ligne 244 — `def _enrich_atr(signals: pd.DataFrame, pivots: dict[str, pd.DataFrame]) -> pd.DataFrame:`
- ligne 265 — `def run_variant(engine: Any, signals: pd.DataFrame, pivots: dict[str, pd.DataFrame],`
- ligne 277 — `def _metrics(res: Any, raw_signals: pd.DataFrame, reg_map: dict[pd.Timestamp, str],`
- ligne 352 — `def main() -> None:`
- ligne 66 — `def _load_regime_map() -> dict[pd.Timestamp, str]:`
- ligne 91 — `def load_regime_map_db(engine: Any) -> dict[pd.Timestamp, str]:`
## `modelFactory/dip_research/persistent_top10_dip_reclaim.py`

- ligne 102 — `def _per_symbol_paths(bars: pd.DataFrame) -> dict[str, dict[str, np.ndarray]]:`
- ligne 115 — `def _build_rank_index(panel: pd.DataFrame) -> dict[tuple[str, pd.Timestamp], float]:`
- ligne 127 — `def _find_reclaim(`
- ligne 157 — `def forward_metrics_from_entry(`
- ligne 185 — `def build_reclaim_rows(`
- ligne 243 — `def signal_diagnostics(signals: pd.DataFrame) -> dict[str, Any]:`
- ligne 268 — `def metrics_per_strategy(signals: pd.DataFrame) -> pd.DataFrame:`
- ligne 299 — `def cost_of_delay(signals: pd.DataFrame) -> pd.DataFrame:`
- ligne 316 — `def build_signals_for_backtest(signals: pd.DataFrame, name: str, reg_map: dict[pd.Timestamp, str]) -> pd.DataFrame:`
- ligne 338 — `def main() -> None:`
- ligne 69 — `def load_panel(engine: Any, batch_id: str, start_date: str, end_date: str) -> pd.DataFrame:`
## `modelFactory/dip_research/persistent_top10_dip.py`

- ligne 101 — `def forward_path_metrics(`
- ligne 133 — `def build_signal_rows(`
- ligne 195 — `def _meta(r: pd.Series) -> dict[str, Any]:`
- ligne 205 — `def aggregate(signals: pd.DataFrame, paths: dict[str, dict[str, np.ndarray]]) -> pd.DataFrame:`
- ligne 246 — `def breakdown(signals: pd.DataFrame, paths: dict[str, dict[str, np.ndarray]]) -> pd.DataFrame:`
- ligne 262 — `def main() -> None:`
- ligne 55 — `def load_panel(engine: Any, batch_id: str, start_date: str, end_date: str) -> pd.DataFrame:`
- ligne 88 — `def _per_symbol_paths(bars: pd.DataFrame) -> dict[str, dict[str, np.ndarray]]:`
## `modelFactory/directional_data_research/analyst_revisions.py`

- ligne 154 — `def main() -> None:`
- ligne 71 — `def load_earnings_calendar(engine: Any) -> pd.DataFrame:`
- ligne 85 — `def build_features(pool: pd.DataFrame, cal: pd.DataFrame) -> pd.DataFrame:`
## `modelFactory/directional_data_research/earnings_revisions.py`

- ligne 118 — `def load_close_prices(engine: Any, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame:`
- ligne 143 — `def main() -> None:`
- ligne 51 — `def load_earnings_features(engine: Any, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame:`
- ligne 77 — `def derive_earnings_features(raw: pd.DataFrame) -> pd.DataFrame:`
- ligne 93 — `def merge_into_pool(pool: pd.DataFrame, feats: pd.DataFrame, price_map: pd.DataFrame) -> pd.DataFrame:`
## `modelFactory/directional_data_research/harness.py`

- ligne 112 — `def _ic_spearman(series: pd.Series, decile: pd.Series) -> float | None:`
- ligne 123 — `def _auc_bad_good(series: pd.Series, decile: pd.Series, bad=(1, 5), good=(6, 10)) -> float | None:`
- ligne 132 — `def analyze_features(pool: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:`
- ligne 188 — `def format_report(df: pd.DataFrame, top_n: int = 12) -> str:`
- ligne 34 — `def load_oracle_pool_proba(batch_id: str, oracle_run: str | None = None) -> pd.DataFrame:`
- ligne 55 — `def assemble_pool(`
## `modelFactory/directional_data_research/news_sentiment.py`

- ligne 110 — `def main() -> None:`
- ligne 48 — `def load_sentiment_daily(engine: Any, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame:`
- ligne 82 — `def build_news_features(pool: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:`
## `modelFactory/directional_data_research/short_interest.py`

- ligne 107 — `def build_short_interest_features(pool: pd.DataFrame, si: pd.DataFrame) -> pd.DataFrame:`
- ligne 133 — `def main() -> None:`
- ligne 52 — `def load_daily_short_volume() -> pd.DataFrame:`
- ligne 63 — `def load_short_interest() -> pd.DataFrame:`
- ligne 78 — `def build_daily_features(pool: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:`
## `modelFactory/drift_monitor.py`

- ligne 101 — `def _psi(now: np.ndarray, baseline: np.ndarray, *, buckets: int = 10) -> float:`
- ligne 123 — `def compute_drift(`
- ligne 174 — `def persist_drift_run(report: DriftReport, *, engine: Any, run_id: str | None = None) -> str:`
- ligne 42 — `class DriftReport:`
- ligne 70 — `def _ks_two_sample(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:`
## `modelFactory/drift_policy.py`

- ligne 195 — `def apply_kill_switch(`
- ligne 224 — `def persist_kill_switch_event(decision: MLPolicyDecision, *, engine: Any) -> None:`
- ligne 268 — `def summary_fields(decision: MLPolicyDecision | None) -> dict[str, Any]:`
- ligne 47 — `class MLPolicyDecision:`
- ligne 65 — `def evaluate_drift_gate(`
## `modelFactory/evaluation.py`

- ligne 101 — `def multiclass_log_loss(`
- ligne 126 — `def multiclass_balanced_accuracy(`
- ligne 146 — `def compute_multiclass_metrics(`
- ligne 20 — `def _validate_proba_array(proba: np.ndarray, *, tol: float = 1e-6) -> str | None:`
- ligne 243 — `def compute_directional_oos_metrics(`
- ligne 283 — `def check_model_collapse(`
- ligne 34 — `def multiclass_auc_one_vs_rest(`
- ligne 341 — `def compute_business_score(`
- ligne 361 — `def bucket_analysis(`
- ligne 437 — `def compute_threshold_metrics(`
- ligne 507 — `def optimize_decision_threshold(`
- ligne 586 — `def align_sequence_rows(df: pd.DataFrame, seq_len: int) -> pd.DataFrame:`
- ligne 79 — `def multiclass_brier_score(`
## `modelFactory/factor_features.py`

- ligne 128 — `def fill_factor_defaults(df: pd.DataFrame) -> pd.DataFrame:`
- ligne 37 — `def compute_factor_features(`
## `modelFactory/feature_logging.py`

- ligne 131 — `def log_feature_duplicates(df: pd.DataFrame, feature_columns: list[str], *, label: str) -> None:`
- ligne 28 — `def log_feature_values(df: pd.DataFrame, feature_columns: list[str], *, label: str) -> None:`
- ligne 63 — `def log_feature_weights(model: Any, feature_columns: list[str], *, label: str) -> None:`
- ligne 90 — `def _extract_importance(model: Any) -> np.ndarray | None:`
## `modelFactory/features.py`

- ligne 1010 — `def compute_features(`
- ligne 1520 — `def compute_rank_interactions(df: pd.DataFrame) -> pd.DataFrame:`
- ligne 1558 — `def build_target(`
- ligne 1630 — `def compute_future_return(df: pd.DataFrame, horizon: int = 5) -> pd.Series:`
- ligne 1636 — `def build_multi_horizon_targets(`
- ligne 1687 — `def standardize_regression_target(`
- ligne 1731 — `def _build_adjusted_price_frame(df: pd.DataFrame) -> pd.DataFrame:`
- ligne 1760 — `def _range_position(close: pd.Series, window: int) -> pd.Series:`
- ligne 1765 — `def _rsi(close: pd.Series, period: int = 14) -> pd.Series:`
- ligne 1775 — `def _atr_norm(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:`
- ligne 1786 — `def _atr_value(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:`
- ligne 1797 — `def _adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:`
- ligne 196 — `def _zscore_column_name(source_col: str) -> str:`
- ligne 383 — `def apply_feature_whitelist(`
- ligne 417 — `def get_feature_columns(`
- ligne 531 — `def fingerprint(`
- ligne 602 — `def normalize_feature_columns(value: object) -> list[str] | None:`
- ligne 611 — `def build_feature_contract(`
- ligne 689 — `def validate_feature_contract(`
- ligne 865 — `def _merge_macro_features(`
- ligne 986 — `def _fill_macro_defaults(`
## `modelFactory/fundamental_features.py`

- ligne 1023 — `def main() -> None:`
- ligne 129 — `def load_fundamentals_from_db(`
- ligne 208 — `def forward_fill_fundamentals(`
- ligne 269 — `def derive_features(df: pd.DataFrame) -> pd.DataFrame:`
- ligne 324 — `def merge_fundamentals(`
- ligne 413 — `def fetch_and_store_fundamentals(`
- ligne 605 — `def _extract_quarterly_fundamentals(`
- ligne 770 — `def _get_prev_year_quarter(quarter_date: str) -> str | None:`
- ligne 782 — `def _fetch_fundamentals_record(`
- ligne 826 — `def _extract_eodhd_highlights(highlights: dict) -> dict[str, Any]:`
- ligne 862 — `def _extract_eodhd_valuation(valuation: dict) -> dict[str, Any]:`
- ligne 875 — `def _extract_eodhd_technicals(technicals: dict) -> dict[str, Any]:`
- ligne 884 — `def _upsert_fundamentals_row(`
- ligne 937 — `def _enrich_sec_with_market_ratios(`
- ligne 973 — `def _resolve_cli_symbols(`
## `modelFactory/global_benchmark_runner.py`

- ligne 155 — `class GlobalBenchmarkRunner:`
- ligne 45 — `class GlobalBenchmarkConfig:`
- ligne 69 — `class GlobalBenchmarkReport:`
## `modelFactory/global_direction/audit_scores.py`

- ligne 139 — `def audit_pool_lags(`
- ligne 220 — `def format_pool_report(lag_row: dict[str, Any]) -> str:`
- ligne 235 — `def main() -> None:`
- ligne 51 — `def load_scores(engine: Any, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame:`
- ligne 68 — `def load_bars_dates(engine: Any, symbols: list[str], start_date: str, end_date: str) -> dict[str, np.ndarray]:`
- ligne 84 — `def _pit_series(snap_dates: np.ndarray, snap_values: np.ndarray, trading_days: np.ndarray) -> pd.Series:`
- ligne 93 — `def audit_universe(engine: Any, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame:`
## `modelFactory/global_direction/conditioning.py`

- ligne 143 — `def main() -> None:`
- ligne 52 — `def _ic_spearman(series: pd.Series, decile: pd.Series) -> float | None:`
- ligne 63 — `def _auc(series: pd.Series, decile: pd.Series, good: tuple = (6, 10), bad: tuple = (1, 5)) -> float | None:`
- ligne 72 — `def _top_decile_stats(sub: pd.DataFrame, feature: str) -> dict[str, float | None]:`
- ligne 91 — `def measure_depth(`
## `modelFactory/global_direction/config.py`

- ligne 25 — `class GlobalDirectionConfig:`
- ligne 35 — `def load_global_direction_config(path: Path | str = _CONFIG_PATH) -> GlobalDirectionConfig:`
- ligne 68 — `def resolve_global_direction_batch_id(path: Path | str = _CONFIG_PATH) -> str | None:`
## `modelFactory/global_direction/dataset.py`

- ligne 130 — `def build_sector_features(`
- ligne 192 — `def gd_labels_from_oracle(`
- ligne 230 — `def build_dataset(`
- ligne 94 — `def select_direction_features(available: list[str], mode: str = "minimal") -> list[str]:`
## `modelFactory/global_direction/pipeline.py`

- ligne 119 — `def build_pool(combined: pd.DataFrame, pool_pct: float) -> pd.DataFrame:`
- ligne 127 — `def select_top_m24(pool: pd.DataFrame, score_col: str, m24: int) -> pd.DataFrame:`
- ligne 143 — `def compute_metrics(picks: pd.DataFrame, label: str = "") -> dict[str, Any]:`
- ligne 174 — `def quintile_gradient(pool: pd.DataFrame, score_col: str) -> pd.DataFrame:`
- ligne 196 — `def fold_go_reproducibility(pool: pd.DataFrame, score_col: str, key: str = "fold_start") -> pd.DataFrame:`
- ligne 234 — `def breakdown(pool: pd.DataFrame, variant_picks: dict[str, pd.DataFrame], key: str) -> pd.DataFrame:`
- ligne 265 — `def _fmt_metrics(m: dict[str, Any]) -> str:`
- ligne 274 — `def quintile_distribution(pool: pd.DataFrame, score_col: str) -> pd.DataFrame:`
- ligne 305 — `def _dist_gradient_summary(dist: pd.DataFrame) -> str:`
- ligne 315 — `def _fmt_dist(dist: pd.DataFrame) -> str:`
- ligne 329 — `def run_pipeline(`
- ligne 480 — `def main() -> None:`
- ligne 52 — `def _latest_run(root: Path, prefix: str, tag_batch: str | None = None) -> Path | None:`
- ligne 67 — `def load_run_oos(run_dir: Path) -> pd.DataFrame:`
- ligne 74 — `def load_b25_ranks(engine: Any, batch_id: str) -> pd.DataFrame:`
- ligne 86 — `def load_regime_map(path: Path = _REGIME_FILE) -> dict[pd.Timestamp, str]:`
## `modelFactory/global_direction/separability.py`

- ligne 116 — `def _ic_spearman(series: pd.Series, decile: pd.Series) -> float | None:`
- ligne 127 — `def _auc_bad_good(series: pd.Series, decile: pd.Series, bad=(1, 3), good=(8, 10)) -> float | None:`
- ligne 136 — `def analyze_separability(`
- ligne 199 — `def format_report(df: pd.DataFrame, top_n: int = 15) -> str:`
- ligne 218 — `def main() -> None:`
- ligne 49 — `def load_oracle_pool_proba(batch_id: str) -> pd.DataFrame:`
- ligne 67 — `def build_pool_features(`
## `modelFactory/global_direction/temporal.py`

- ligne 113 — `def load_score_panel(engine: Any, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame:`
- ligne 140 — `def _score_history_columns(engine: Any) -> list[str]:`
- ligne 148 — `def load_sector_panel(engine: Any, symbols: list[str], start_date: str, end_date: str) -> tuple[pd.DataFrame, list[str]]:`
- ligne 168 — `def build_panel(`
- ligne 290 — `def _ic_spearman(series: pd.Series, decile: pd.Series) -> float | None:`
- ligne 301 — `def _auc(series: pd.Series, decile: pd.Series, good: tuple = (6, 10), bad: tuple = (1, 5)) -> float | None:`
- ligne 310 — `def _auc_d1_d10(series: pd.Series, decile: pd.Series) -> float | None:`
- ligne 314 — `def _auc_amplitude(series: pd.Series, decile: pd.Series) -> float | None:`
- ligne 323 — `def run_separability(pool: pd.DataFrame, base_features: list[str], temporal_cols: list[str]) -> pd.DataFrame:`
- ligne 419 — `def format_report(out: pd.DataFrame, base_features: list[str]) -> str:`
- ligne 439 — `def main() -> None:`
- ligne 75 — `def _temporal_columns(base: str) -> list[str]:`
- ligne 88 — `def _slope(series: pd.Series, window: int) -> pd.Series:`
- ligne 95 — `def load_bars_panel(engine: Any, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame:`
## `modelFactory/global_direction/walk_forward.py`

- ligne 122 — `def _auc_d10_vs_d1(oos: pd.DataFrame) -> float | None:`
- ligne 132 — `def run_walk_forward(`
- ligne 233 — `def persist_oos(oos: pd.DataFrame, run_id: str, batch_id: str | None = None) -> Path:`
- ligne 248 — `def format_report(result: dict[str, Any]) -> str:`
- ligne 277 — `def main() -> None:`
- ligne 51 — `def _train_lightgbm_multiclass(`
- ligne 87 — `def _train_lightgbm_regression(`
## `modelFactory/global_model.py`

- ligne 102 — `def _import_lightgbm() -> Any:`
- ligne 108 — `def _import_catboost() -> Any:`
- ligne 114 — `def _prepare_global_symbol_frame(`
- ligne 166 — `def _split_global_by_dates(`
- ligne 182 — `def _build_global_estimator(cfg: TrainingConfig, *, resolved_seed: int) -> tuple[str, Any]:`
- ligne 261 — `def _compute_by_symbol_metrics(`
- ligne 305 — `def _aggregate_wf_per_symbol_metrics(`
- ligne 358 — `def train_global_model(`
- ligne 61 — `def _get_global_feature_columns(cfg: TrainingConfig) -> list[str]:`
- ligne 726 — `def train_global_model_wf(`
## `modelFactory/global_ranking.py`

- ligne 130 — `def _xs_rank_column_name(source_col: str) -> str:`
- ligne 134 — `def _directional_features_subset() -> list[str] | None:`
- ligne 149 — `def _compute_sector_neutral_inplace(`
- ligne 1934 — `def predict_global_rank(`
- ligne 243 — `def _prepare_global_ranking_frame(`
- ligne 284 — `def _get_ranking_feature_columns(cfg: TrainingConfig) -> list[str]:`
- ligne 417 — `def compute_ic_rank(predicted: np.ndarray, actual: np.ndarray) -> float | None:`
- ligne 440 — `def compute_cross_sectional_ic(`
- ligne 500 — `def _compute_mean_importance(`
- ligne 515 — `def _compute_decile_spread(`
- ligne 568 — `def _import_lightgbm() -> Any:`
- ligne 573 — `def _import_xgboost() -> Any:`
- ligne 578 — `def _import_catboost(as_ranker: bool = False) -> Any:`
- ligne 586 — `def _build_ranking_estimator(`
- ligne 595 — `def _build_ranking_estimators(`
- ligne 687 — `def _compute_ranking_targets(`
- ligne 83 — `def _classify_sector_group(sector: str) -> str:`
- ligne 831 — `def train_global_ranking_wf(`
## `modelFactory/labeling.py`

- ligne 110 — `class TripleBarrierLabel:`
- ligne 157 — `def _compute_atr(`
- ligne 182 — `def _deduct_costs(`
- ligne 200 — `def _resolve_exit(`
- ligne 319 — `def build_triple_barrier_label(`
- ligne 425 — `def build_triple_barrier_labels(`
- ligne 48 — `class TripleBarrierConfig:`
- ligne 508 — `def build_triple_barrier_targets(`
- ligne 537 — `def compare_label_methods(`
## `modelFactory/lightgbm_baseline.py`

- ligne 16 — `def _import_lightgbm() -> Any:`
- ligne 22 — `def run_lightgbm_baseline(`
## `modelFactory/liquidity_filter.py`

- ligne 103 — `def filter_symbols_by_liquidity(`
- ligne 323 — `def _apply_spread_filter(`
## `modelFactory/lstm_benchmark_adapter.py`

- ligne 58 — `def _build_sequences(`
- ligne 84 — `def _validate_target_distribution(y_train: np.ndarray, y_val: np.ndarray) -> dict[str, object]:`
- ligne 97 — `def run_lstm_benchmark(`
## `modelFactory/model_benchmark.py`

- ligne 214 — `class BenchmarkConfig:`
- ligne 230 — `class ChallengerResult:`
- ligne 249 — `class BenchmarkReport:`
- ligne 316 — `class BenchmarkRunner:`
- ligne 43 — `class SimpleBaselineResult:`
- ligne 56 — `class SimpleBaselines:`
- ligne 664 — `def run_model_benchmark(`
- ligne 697 — `def _count_lightgbm_leaves(dump: dict[str, Any]) -> int:`
- ligne 710 — `def _count_leaves_recursive(node: dict[str, Any]) -> int:`
- ligne 726 — `def persist_benchmark_report(`
- ligne 768 — `def load_benchmark_report(path: Path | str) -> dict[str, Any]:`
- ligne 787 — `class BenchmarkQualityReport:`
- ligne 799 — `def validate_benchmark_quality(`
## `modelFactory/model.py`

- ligne 24 — `class TemporalAttention(nn.Module):`
- ligne 49 — `class LSTMAttentionClassifier(nn.Module):`
- ligne 89 — `class LSTMAttentionModule(L.LightningModule):`
## `modelFactory/oracle/audit.py`

- ligne 124 — `def compute_decile_returns(oracle_df: pd.DataFrame) -> pd.DataFrame:`
- ligne 137 — `def decile_monotonicity(decile_stats: pd.DataFrame) -> float | None:`
- ligne 153 — `def compare_golden(labeled: pd.DataFrame, golden_df: pd.DataFrame) -> dict[str, Any]:`
- ligne 193 — `def audit_run(`
- ligne 243 — `def format_report(result: dict[str, Any]) -> str:`
- ligne 299 — `def main() -> None:`
- ligne 41 — `def load_trades(trades_path: Path | str) -> pd.DataFrame:`
- ligne 50 — `def load_oracle_labels(`
- ligne 86 — `def attach_oracle_labels(trades_df: pd.DataFrame, oracle_df: pd.DataFrame) -> pd.DataFrame:`
- ligne 98 — `def compute_capture(labeled: pd.DataFrame) -> dict[str, Any]:`
## `modelFactory/oracle/build_labels.py`

- ligne 104 — `def load_universe_from_bars(`
- ligne 138 — `def check_universe_equality(`
- ligne 162 — `def load_close_matrix(engine: Any, symbols: list[str], start_date: str) -> pd.DataFrame:`
- ligne 188 — `def compute_cross_sectional_ranks(`
- ligne 220 — `def _upsert_rows(engine: Any, rows: list[tuple[Any, ...]]) -> int:`
- ligne 234 — `def build_labels(`
- ligne 458 — `def main() -> None:`
- ligne 70 — `def _iso(value: Any) -> str:`
- ligne 77 — `def load_universe_from_ranks(`
- ligne 93 — `def load_universe_from_predictions(engine: Any, batch_id: str) -> set[tuple[str, str]]:`
## `modelFactory/oracle/catastrophic_detector.py`

- ligne 114 — `def run_catastrophic_detector_wf(`
- ligne 177 — `def format_report(report: dict[str, Any]) -> str:`
- ligne 197 — `def main() -> None:`
- ligne 51 — `def _auc(y_true, y_score):`
- ligne 56 — `def _build_dataset(engine, batch_id: str, horizon: int = 20, start: str = "2022-01-01") -> pd.DataFrame:`
- ligne 90 — `def _rejection_tradeoff(v: pd.DataFrame, score_col: str, cat_col: str) -> list[dict[str, Any]]:`
## `modelFactory/oracle/combine.py`

- ligne 100 — `def calibrate_p_extreme(`
- ligne 126 — `def apply_oracle_calibration(`
- ligne 194 — `def _evaluate_on_folds(`
- ligne 206 — `def run_combination_search(`
- ligne 252 — `def format_report(report: dict[str, Any]) -> str:`
- ligne 278 — `def main() -> None:`
- ligne 41 — `def combine_scores(`
- ligne 62 — `def isotonic_regression(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:`
## `modelFactory/oracle/config.py`

- ligne 27 — `class OracleConfig:`
- ligne 37 — `def load_oracle_config(path: Path | str = _CONFIG_PATH) -> OracleConfig:`
- ligne 78 — `def load_backtest_batch_id(path: Path | str = _CONFIG_PATH) -> str | None:`
- ligne 91 — `def resolve_oracle_batch_id(path: Path | str = _CONFIG_PATH) -> str | None:`
## `modelFactory/oracle/confound_validation.py`

- ligne 105 — `def format_report(report: dict[str, Any]) -> str:`
- ligne 119 — `def main() -> None:`
- ligne 36 — `def _average_random_tradeoff(df: pd.DataFrame, cat_col: str, seeds: int) -> list[dict[str, Any]]:`
- ligne 55 — `def run_confound_validation(batch_id: str, *, horizon: int = 20, start: str = "2022-01-01") -> dict[str, Any]:`
- ligne 94 — `def _print_table(title: str, rows: list[dict[str, Any]]) -> str:`
## `modelFactory/oracle/dataset.py`

- ligne 110 — `def load_global_rank_feature(engine: Any, batch_id: str) -> pd.DataFrame:`
- ligne 121 — `def load_oracle_targets(engine: Any, batch_id: str, horizon: int = 20) -> pd.DataFrame:`
- ligne 135 — `def build_dataset(`
- ligne 206 — `def split_dataset(`
- ligne 219 — `def ablation_features(`
- ligne 50 — `def expert_feature_columns() -> list[str]:`
- ligne 55 — `def lean_feature_columns(features: list[str]) -> list[str]:`
- ligne 61 — `def build_feature_matrix(`
## `modelFactory/oracle/directional_features.py`

- ligne 113 — `def run_directional_diagnostic(batch_id: str, *, horizon: int = 20, start: str = "2022-01-01") -> dict[str, Any]:`
- ligne 153 — `def format_report(report: dict[str, Any]) -> str:`
- ligne 169 — `def main() -> None:`
- ligne 37 — `def _cs_spearman(df: pd.DataFrame, feat: str, target: str, min_universe: int = 30) -> float | None:`
- ligne 48 — `def build_directional_features(engine, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame:`
## `modelFactory/oracle/error_severity.py`

- ligne 158 — `def format_report(report: dict[str, Any]) -> str:`
- ligne 176 — `def main() -> None:`
- ligne 49 — `def _rank_quality(valid: pd.DataFrame, score_col: str) -> dict[str, Any]:`
- ligne 71 — `def _mag_corr(valid: pd.DataFrame, score_col: str) -> float | None:`
- ligne 85 — `def run_error_severity_experiment(`
## `modelFactory/oracle/extreme_gate.py`

- ligne 40 — `def compute_extreme_gate(`
- ligne 76 — `def build_oracle_rank_map(`
## `modelFactory/oracle/feature_diagnostic.py`

- ligne 135 — `def format_report(report: dict[str, Any]) -> str:`
- ligne 167 — `def main() -> None:`
- ligne 54 — `def _cs_spearman(df: pd.DataFrame, feat: str, target: str, min_universe: int = 30) -> float | None:`
- ligne 66 — `def _feature_columns(dataset: pd.DataFrame, feature_columns: list[str]) -> list[str]:`
- ligne 74 — `def run_feature_diagnostic(batch_id: str, *, horizon: int = 20, start: str = "2022-01-01") -> dict[str, Any]:`
## `modelFactory/oracle/fundamental_diagnostic.py`

- ligne 103 — `def _load_sentiment(engine, symbols: list[str]) -> pd.DataFrame:`
- ligne 117 — `def run_fundamental_diagnostic(batch_id: str, *, horizon: int = 20, start: str = "2022-01-01") -> dict[str, Any]:`
- ligne 196 — `def format_report(report: dict[str, Any]) -> str:`
- ligne 215 — `def main() -> None:`
- ligne 41 — `def _cs_spearman(df: pd.DataFrame, feat: str, target: str, min_universe: int = 30) -> float | None:`
- ligne 52 — `def _auc(y_true: np.ndarray, y_score: np.ndarray) -> float | None:`
- ligne 68 — `def _load_earnings(engine, symbols: list[str]) -> pd.DataFrame:`
- ligne 89 — `def _load_fundamentals(engine, symbols: list[str]) -> pd.DataFrame:`
## `modelFactory/oracle/hard_negatives.py`

- ligne 121 — `def run_hard_negative_experiment(`
- ligne 199 — `def format_report(report: dict[str, Any]) -> str:`
- ligne 218 — `def main() -> None:`
- ligne 57 — `def _intra_date_rank(df: pd.DataFrame, score_col: str) -> pd.Series:`
- ligne 61 — `def _intra_date_corr(df: pd.DataFrame, a: str, b: str) -> float | None:`
- ligne 75 — `def _train_model(algo: str, X_tr, y_tr, X_va, y_va, sample_weight=None):`
- ligne 83 — `def _diagnose(valid: pd.DataFrame, ptop_col: str, pbot_col: str) -> dict[str, Any]:`
## `modelFactory/oracle/leakage.py`

- ligne 105 — `def assert_training_cutoff_valid(`
- ligne 127 — `def assert_no_future_oracle_read(*, today: Any, oracle_available_date: Any) -> None:`
- ligne 42 — `def assert_availability_after_prediction(`
- ligne 80 — `def assert_no_forbidden_features(feature_columns: Iterable[str]) -> None:`
- ligne 88 — `def assert_no_future_features(feature_columns: Iterable[str]) -> None:`
## `modelFactory/oracle/predict_history.py`

- ligne 35 — `def has_oracle_champions(batch_id: str | None) -> bool:`
- ligne 42 — `def _load_champions_meta(batch_id: str) -> list[dict[str, Any]]:`
- ligne 57 — `def predict_oracle_extreme_history(`
## `modelFactory/oracle/predictions_store.py`

- ligne 113 — `def load_oracle_predictions(`
- ligne 58 — `def ensure_oracle_predictions_table(engine: Any) -> None:`
- ligne 64 — `def write_oracle_predictions(`
## `modelFactory/oracle/research/dip_quality_synthesis.py`

- ligne 28 — `def metrics_from_trades(df):`
## `modelFactory/oracle/research/tiebreak_t0_t1_compare.py`

- ligne 33 — `def metrics_from_trades(df: pd.DataFrame) -> dict:`
- ligne 64 — `def main() -> None:`
## `modelFactory/oracle/train.py`

- ligne 103 — `def decile_monotonicity(df: pd.DataFrame, score_col: str) -> tuple[float | None, pd.DataFrame]:`
- ligne 118 — `def train_lightgbm(`
- ligne 159 — `def train_catboost(`
- ligne 197 — `def _proba_catboost(model: Any, X: pd.DataFrame) -> np.ndarray:`
- ligne 202 — `def train_lightgbm_regressor(`
- ligne 236 — `def train_catboost_regressor(`
- ligne 266 — `def evaluate_model(model: Any, valid_df: pd.DataFrame, feature_cols: list[str]) -> dict[str, Any]:`
- ligne 291 — `def run_ablation(`
- ligne 338 — `def format_report(report: dict[str, Any]) -> str:`
- ligne 361 — `def main() -> None:`
- ligne 44 — `def get_universe_symbols(engine: Any, batch_id: str, horizon: int) -> list[str]:`
- ligne 55 — `def roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float | None:`
- ligne 71 — `def precision_recall_at_top_pct(`
## `modelFactory/oracle/walk_forward.py`

- ligne 143 — `def run_walk_forward(`
- ligne 248 — `def persist_oos(`
- ligne 312 — `def format_report(result: dict[str, Any]) -> str:`
- ligne 345 — `def main() -> None:`
- ligne 61 — `def build_folds(dataset: pd.DataFrame, test_windows: list[tuple[str, str]]) -> list[dict[str, Any]]:`
- ligne 86 — `def build_folds_adaptive(`
## `modelFactory/orchestrator.py`

- ligne 206 — `def _gpu_requested_or_available(cfg: TrainingConfig) -> bool:`
- ligne 210 — `def _filter_symbols_by_mode(`
- ligne 339 — `def _train_worker(`
- ligne 466 — `def train_oracle_extreme(`
- ligne 60 — `def get_last_liquidity_diagnostics() -> dict[str, Any]:`
- ligne 621 — `def run_training_batch(`
- ligne 69 — `def _with_batch_artifacts_dir(cfg: TrainingConfig, batch_id: str) -> TrainingConfig:`
- ligne 81 — `def _inject_global_model_into_symbol_artifacts(`
## `modelFactory/predict_per_sector.py`

- ligne 33 — `def _last_bar_date() -> date | None:`
- ligne 44 — `def _parse_args(argv: list[str]) -> tuple[str, int, str, date | None, date | None]:`
- ligne 77 — `def main() -> None:`
## `modelFactory/predictor.py`

- ligne 1060 — `def _build_lstm_fallback_route(`
- ligne 1086 — `def _load_data_cfg_from_payload(`
- ligne 1131 — `def _prepare_prediction_frame(`
- ligne 124 — `class ArtifactIntegrityError(RuntimeError):`
- ligne 1296 — `def _predict_with_global_model(`
- ligne 1328 — `def _predict_with_tabular_model(`
- ligne 133 — `def _record_db_issue(`
- ligne 147 — `def _record_artifact_issue(symbol: str, *, reason: str, path: Path | None = None) -> None:`
- ligne 156 — `def _record_prediction_fallback(`
- ligne 1680 — `def predict_symbol(`
- ligne 172 — `def _load_json_dict(path: Path, *, symbol: str, artifact_kind: str) -> dict[str, Any]:`
- ligne 199 — `def _load_optional_calibrator(`
- ligne 2174 — `def load_cascade_config() -> dict[str, Any]:`
- ligne 2207 — `def load_extreme_gate_config() -> dict[str, Any]:`
- ligne 2250 — `def load_per_symbol_features(artifacts_dir: Path) -> dict[str, Any]:`
- ligne 227 — `def _apply_optional_calibration(`
- ligne 2292 — `def upsert_global_ranks(`
- ligne 2371 — `def predict_global_rank_history(`
- ligne 2517 — `def compute_per_symbol_cross_sectional_ic(`
- ligne 262 — `def _extract_positive_class_probability(`
- ligne 2641 — `class CascadePrediction:`
- ligne 2650 — `def load_global_ranks_from_db(`
- ligne 2717 — `def _load_best_horizon_for_batch(batch_id: str, *, engine: Any | None = None) -> int | None:`
- ligne 2744 — `def _load_momentum_for_symbols(`
- ligne 2795 — `def cascade_select(`
- ligne 305 — `def _persist_predictions_best_effort(`
- ligne 324 — `def _path_from_value(value: object) -> Path | None:`
- ligne 3282 — `def _apply_dip_quality_policy(`
- ligne 332 — `def _numeric_threshold(value: object, default: float) -> float:`
- ligne 3333 — `def _apply_dip_quality_tiebreak(`
- ligne 3378 — `def apply_cascade_to_predictions(`
- ligne 341 — `def _resolve_route_decision_threshold(route: dict[str, object], cfg_data: dict[str, Any]) -> float | None:`
- ligne 348 — `def _resolve_artifact_signature_manifest_path(cfg_data: dict[str, Any], *, config_path: Path) -> Path:`
- ligne 354 — `def _verify_route_signature_if_needed(`
- ligne 3712 — `def _try_compute_global_rank_for_prediction(`
- ligne 3786 — `def _warn_global_rank_fallbacks() -> None:`
- ligne 3800 — `def predict_batch(`
- ligne 384 — `def _build_prediction_result(`
- ligne 441 — `def _has_matching_latest_feature_date(df: pd.DataFrame, cutoff_date: date | None) -> bool:`
- ligne 453 — `def _pit_validate_bars(`
- ligne 501 — `def _pit_build_availability(`
- ligne 526 — `def _record_route_fallback_if_any(symbol: str, route: dict[str, object]) -> None:`
- ligne 545 — `def _resolve_inference_device(accelerator: str = "auto") -> torch.device:`
- ligne 562 — `def _resolve_artifact_paths(`
- ligne 637 — `def _classify_prediction_source(`
- ligne 669 — `def _resolve_sector_run(`
- ligne 69 — `def _batch_has_per_symbol_or_sector(engine: "Engine", batch_id: str | None) -> bool:`
- ligne 742 — `def _check_feature_contract(cfg_data: dict, *, symbol: str, config_path: Path) -> str | None:`
- ligne 791 — `class _LightGBMBoosterAdapter:`
- ligne 804 — `def _load_tabular_model(model_path: Path, *, selected_model: str) -> Any:`
- ligne 837 — `def _cached_tabular_model(model_path_str: str, cache_token: tuple[int, int], selected_model: str) -> Any:`
- ligne 842 — `def _cached_scaler(scaler_path_str: str, cache_token: tuple[int, int]) -> Any:`
- ligne 848 — `def _cached_calibrator(calibrator_path_str: str, cache_token: tuple[int, int]) -> Any:`
- ligne 854 — `def _cached_lstm_module(ckpt_path_str: str, cache_token: tuple[int, int], device_str: str) -> Any:`
- ligne 863 — `def _safe_cache_token(path: Path) -> tuple[int, int]:`
- ligne 871 — `def load_tabular_model_cached(model_path: Path, *, selected_model: str) -> Any:`
- ligne 876 — `def load_scaler_cached(scaler_path: Path) -> Any:`
- ligne 880 — `def load_calibrator_cached(calibrator_path: Path) -> Any:`
- ligne 884 — `def load_lstm_module_cached(ckpt_path: Path, device: Any) -> Any:`
- ligne 888 — `def clear_model_cache() -> None:`
- ligne 896 — `def clear_prediction_data_cache() -> None:`
- ligne 911 — `def _load_benchmark_bars_cached(`
- ligne 938 — `def _load_cross_sectional_features_cached(`
- ligne 999 — `def _resolve_selected_model_route(`
## `modelFactory/report.py`

- ligne 1021 — `def _build_regime_table(engine: Engine, batch_id: str) -> pd.DataFrame:`
- ligne 1152 — `def generate_batch_report(engine: Engine, batch_id: str) -> str:`
- ligne 283 — `def _classify_regime(spy_return_pct: float, vix: float, median_vix: float) -> str:`
- ligne 297 — `def _safe_query(engine: Engine, query: str, params: dict | None = None) -> pd.DataFrame:`
- ligne 305 — `def _df_to_md(df: pd.DataFrame) -> str:`
- ligne 315 — `def _append_champion_status(`
- ligne 358 — `def _append_global_ranking_horizon_details(`
- ligne 578 — `def _append_backtest_results(`
- ligne 731 — `def _oracle_split_table(picks: pd.DataFrame) -> dict | None:`
- ligne 757 — `def _oracle_direction_split(df: pd.DataFrame) -> dict | None:`
- ligne 782 — `def _oracle_omniscient_split(df: pd.DataFrame, top_pct: float = 0.10) -> dict | None:`
- ligne 815 — `def _append_oracle_extreme_quality(`
## `modelFactory/reproducibility.py`

- ligne 18 — `def normalize_seed(seed: int) -> int:`
- ligne 23 — `def derive_seed(base_seed: int, *parts: object) -> int:`
- ligne 30 — `def seed_worker(base_seed: int, worker_id: int) -> None:`
- ligne 41 — `def build_torch_generator(seed: int) -> torch.Generator:`
- ligne 47 — `def apply_reproducibility(config: ReproducibilityConfig, *, context: str | None = None) -> dict[str, Any]:`
## `modelFactory/runtime_status.py`

- ligne 16 — `def reset_runtime_status(initial: dict[str, Any] | None = None) -> None:`
- ligne 23 — `def update_runtime_status(**updates: Any) -> dict[str, Any]:`
- ligne 29 — `def increment_runtime_counter(name: str, amount: int = 1) -> int:`
- ligne 36 — `def snapshot_runtime_status() -> dict[str, Any]:`
## `modelFactory/synthesize_global_rank_predictions.py`

- ligne 171 — `def _build_dip_long_set(`
- ligne 228 — `def neutralize_illiquid(batch_id: str, *, end_date: str = "2018-12-31") -> dict:`
- ligne 277 — `def main() -> None:`
- ligne 53 — `def synthesize(batch_id: str, best_h: int, *, top_pct: float = 0.10,`
## `modelFactory/synthesize_oracle_predictions.py`

- ligne 149 — `def main() -> None:`
- ligne 55 — `def synthesize(`
## `modelFactory/tabular_baseline.py`

- ligne 101 — `def compute_tabular_metrics(`
- ligne 184 — `def fit_tabular_calibrator(`
- ligne 214 — `def _fit_ternary_calibrator(`
- ligne 245 — `def apply_tabular_calibration(`
- ligne 269 — `def _compute_regression_metrics(`
- ligne 32 — `def tabular_split(`
- ligne 376 — `def run_tabular_baseline(`
- ligne 67 — `def binary_auc(labels: np.ndarray, scores: np.ndarray) -> float | None:`
- ligne 707 — `def save_baseline_artifact(`
- ligne 820 — `def run_tabular_walk_forward(`
- ligne 89 — `def expected_calibration_error(labels: np.ndarray, proba: np.ndarray, n_bins: int = 10) -> float:`
## `modelFactory/target_optimization.py`

- ligne 153 — `def score_triple_barrier_candidate(`
- ligne 248 — `def optimize_triple_barrier_parameters(`
- ligne 29 — `class TargetCandidateResult:`
- ligne 303 — `def optimize_target_parameters(`
- ligne 404 — `def optimize_target_horizon(`
- ligne 46 — `class TripleBarrierCandidateResult:`
- ligne 64 — `def score_target_candidate(`
## `modelFactory/trainer_sector.py`

- ligne 222 — `def _persist_sector_metrics(`
- ligne 353 — `def _train_sector_models(`
- ligne 48 — `def _prepare_sector_data(`
- ligne 750 — `def run_per_sector_batch(`
- ligne 873 — `def _load_benchmark(engine: Any, cfg: TrainingConfig) -> pd.DataFrame | None:`
- ligne 886 — `def _load_sentiment_for_symbols(symbols: list[str], engine: Any, cfg: TrainingConfig) -> pd.DataFrame | None:`
- ligne 904 — `def _load_universe(symbols: list[str], engine: Any) -> pd.DataFrame | None:`
- ligne 913 — `def _load_selector_for_symbols(symbols: list[str], engine: Any, cfg: TrainingConfig) -> pd.DataFrame | None:`
- ligne 931 — `def _load_fundamentals_for_symbols(symbols: list[str], engine: Any, cfg: TrainingConfig) -> pd.DataFrame | None:`
## `modelFactory/trainer.py`

- ligne 1028 — `def _run_walk_forward_validation(`
- ligne 113 — `def _metric_to_float(value: Any) -> float | None:`
- ligne 126 — `def _format_metric(value: Any) -> str:`
- ligne 131 — `class _EpochProgressLogger(Callback):`
- ligne 1321 — `def train_symbol(`
- ligne 187 — `class TrainResult:`
- ligne 204 — `def _extract_best_epoch(checkpoint_path: Path) -> int | None:`
- ligne 218 — `def _build_loader(dataset: SequenceDataset | None, batch_size: int, *, shuffle: bool, seed: int) -> DataLoader | None:`
- ligne 237 — `def _selection_score_from_metrics(metrics: dict[str, Any]) -> float:`
- ligne 253 — `def _build_challenger_summary(`
- ligne 276 — `def _skip_train_symbol(`
- ligne 292 — `def _record_training_db_issue(symbol: str, run_id: str, *, operation: str, exc: Exception) -> None:`
- ligne 307 — `def _run_training_registry_writes(`
- ligne 32 — `def _build_ternary_policy(cfg: TrainingConfig) -> TernaryDecisionPolicy:`
- ligne 439 — `def _build_feature_contract_for_columns(cfg: TrainingConfig, feature_columns: list[str]) -> dict[str, Any] | None:`
- ligne 464 — `def _build_tabular_artifact_route(`
- ligne 488 — `def _prepare_target_optimization_summary(`
- ligne 538 — `def _collect_outputs(model: LSTMAttentionModule, dataloader: DataLoader | None, device: torch.device) -> dict[str, np.ndarray]:`
- ligne 602 — `def _binary_auc(labels: np.ndarray, scores: np.ndarray) -> float | None:`
- ligne 627 — `def _expected_calibration_error(labels: np.ndarray, proba: np.ndarray, n_bins: int = 10) -> float:`
- ligne 649 — `def _compute_metrics(`
- ligne 82 — `def _atomic_write_json(path: Path, data: Any, *, indent: int = 2) -> None:`
- ligne 855 — `def _fit_calibrator(`
- ligne 892 — `def _evaluate_best_checkpoint(`
- ligne 974 — `def _aggregate_walk_forward_metrics(split_metrics: list[dict[str, Any]]) -> dict[str, Any]:`
## `modelFactory/universe_guard.py`

- ligne 26 — `def compute_min_breadth(reference_size: int, pct: float) -> int:`
- ligne 33 — `def load_min_universe_pct() -> float:`
- ligne 50 — `def load_reference_universe_size() -> int:`
- ligne 67 — `def load_min_universe_breadth() -> int:`
- ligne 72 — `def current_universe_size(engine, trade_date: date) -> int:`
- ligne 92 — `def enforce_min_universe_breadth(`

