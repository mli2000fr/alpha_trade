# Inventaire API — backtesting

Cet inventaire est dérivé des signatures présentes dans le code. Les symboles préfixés par `_` restent internes. Les numéros de ligne sont indicatifs ; le chemin et le nom du symbole sont les repères stables.

## `backtesting/adaptive_breaker.py`

- ligne 101 — `def b0_allocation(episode: BreakerEpisode, equity: float, recovery_pct: float, degraded: float, ramp_max: float, favorable: bool, per_day: float = 0.025) -> float:`
- ligne 115 — `def b1_allocation(episode: BreakerEpisode, equity: float) -> float:`
- ligne 121 — `def b2_allocation(episode: BreakerEpisode, equity: float, favorable: bool) -> float:`
- ligne 136 — `def b3_allocation(episode: BreakerEpisode, equity: float, favorable: bool) -> float:`
- ligne 154 — `def b4_allocation(`
- ligne 208 — `def _dd_pct(episode: BreakerEpisode, equity: float) -> float:`
- ligne 215 — `def _b4_check_relapse(episode: BreakerEpisode, equity: float, prev_trough: float) -> None:`
- ligne 234 — `def allocate(policy: str, episode: BreakerEpisode, equity: float, *, regime: str | None = None, recovery_pct: float = 0.92, degraded: float = 0.06, ramp_max: float = 0.25) -> float:`
- ligne 253 — `def trip_or_recover(episode: BreakerEpisode, equity: float, peak_equity: float, *, policy: str, max_dd_pct: float = TRIP_DD_PCT, recovery_pct: float = 0.92) -> None:`
- ligne 296 — `def update_streak(episode: BreakerEpisode, favorable: bool) -> None:`
- ligne 52 — `class BreakerEpisode:`
- ligne 64 — `def recovery_ratio(episode: BreakerEpisode, equity: float) -> float:`
- ligne 75 — `def _tiers_from_ratio(rr: float, tiers: list[tuple[float, float]]) -> float:`
- ligne 97 — `def is_favorable(regime: str | None) -> bool:`
## `backtesting/analytics.py`

- ligne 119 — `def compute_benchmark_analytics(`
- ligne 179 — `def sector_attribution(closed_trades_df: pd.DataFrame) -> pd.DataFrame:`
- ligne 194 — `def monthly_returns_table(equity: pd.Series) -> pd.DataFrame:`
- ligne 217 — `class TailAnalytics:`
- ligne 232 — `def compute_tail_analytics(equity: pd.Series, *, alpha: float = 0.05) -> TailAnalytics:`
- ligne 255 — `def save_equity_curve_html(equity: pd.Series, output_path: Path) -> Path | None:`
- ligne 286 — `def build_extended_report_payload(`
- ligne 30 — `def compute_total_return_with_dividends(`
- ligne 62 — `def compare_total_return_to_oracle(`
- ligne 98 — `class BenchmarkAnalytics:`
## `backtesting/attribution.py`

- ligne 114 — `def _spearman_ic(scores: pd.Series, fwd: pd.Series) -> float:`
- ligne 126 — `def evaluate_scenario(`
- ligne 199 — `def run_attribution(`
- ligne 44 — `class AttributionScenario:`
- ligne 64 — `class AttributionResult:`
- ligne 88 — `class AttributionReport:`
## `backtesting/backfill_scores_history.py`

- ligne 125 — `class BackfillScoresHistoryResult:`
- ligne 136 — `class BackfillScoresHistoryService:`
## `backtesting/brinson_fachler.py`

- ligne 24 — `class SectorBucket:`
- ligne 33 — `class SectorAttribution:`
- ligne 45 — `class BrinsonFachlerResult:`
- ligne 58 — `def compute_brinson_fachler(buckets: list[SectorBucket]) -> BrinsonFachlerResult:`
## `backtesting/cache.py`

- ligne 29 — `class ParquetCache:`
- ligne 99 — `def _safe_filename(s: str) -> str:`
## `backtesting/cli/_impl.py`

- ligne 193 — `def _load_batch_training_universe_scope(`
- ligne 2181 — `def _explicit_flags(argv: list[str]) -> set[str]:`
- ligne 2237 — `def _infer_programmatic_explicit_flags(args: argparse.Namespace, *, argv: list[str]) -> set[str]:`
- ligne 2276 — `def _run_statistical_validation(`
- ligne 2409 — `def _resolve_pipeline_preset_float(preset, *keys: str, default: float | None = None) -> float | None:`
- ligne 2419 — `def _apply_pipeline_defensive_defaults_from_preset(`
- ligne 250 — `def _parse_sector_multipliers_json(raw: str | None) -> dict[str, float] | None:`
- ligne 2596 — `def _enforce_ml_coverage_gate(`
- ligne 2650 — `def _risk_tp_overrides(args: argparse.Namespace) -> dict:`
- ligne 2687 — `def _run_backtest(args: argparse.Namespace) -> None:`
- ligne 270 — `def _load_sector_map_for_sizing(engine: object) -> dict[str, str]:`
- ligne 281 — `def _load_benchmark_close(`
- ligne 328 — `def _run_bars_source_preflight_or_skip(engine: object, start_date: date, end_date: date) -> dict[str, object]:`
- ligne 359 — `def _extract_symbols_for_log(symbols: object) -> list[str]:`
- ligne 37 — `def _resolve_phase2_ohlcv_history_start(`
- ligne 373 — `def _format_symbol_preview(symbols: list[str], *, limit: int = 20) -> str:`
- ligne 382 — `def _emit_backtest_missing_coverage_logs(`
- ligne 426 — `def _build_execution_broker_like_summary(`
- ligne 4634 — `def _run_backfill_scores_history(args: argparse.Namespace) -> None:`
- ligne 4747 — `def _parse_csv_values(raw: str, *, cast_type):`
- ligne 4756 — `def _run_screener_diagnostics(args: argparse.Namespace) -> None:`
- ligne 489 — `def _build_backtest_component_details(`
- ligne 5066 — `def _run_screener_recommendation(args: argparse.Namespace) -> None:`
- ligne 5276 — `def _run_calibrate_sentiment_weights(args: argparse.Namespace) -> None:`
- ligne 5333 — `def _run_calibrate_conviction_weights(args: argparse.Namespace) -> None:`
- ligne 5393 — `def _run_walk_forward_conviction(args: argparse.Namespace) -> None:`
- ligne 5467 — `def _run_walk_forward_sentiment(args: argparse.Namespace) -> None:`
- ligne 5552 — `def _run_walk_forward_financial(args: argparse.Namespace) -> None:`
- ligne 56 — `def _safe_print(*values: object, sep: str = " ", end: str = "\n") -> None:`
- ligne 5710 — `def main() -> None:`
- ligne 594 — `def _build_backtest_common_params(`
- ligne 67 — `def _coerce_date_value(value: object) -> date | None:`
- ligne 767 — `def _collect_compare_to_live_trade_dates(`
- ligne 797 — `def _build_compare_to_live_artifacts(`
- ligne 81 — `def _apply_idio_gate(`
- ligne 951 — `def _build_parser() -> argparse.ArgumentParser:`
## `backtesting/data_loader.py`

- ligne 101 — `def get_required_bars_source_filter(`
- ligne 124 — `def _resolve_bars_date_column(columns: set[str], table_name: str) -> str:`
- ligne 133 — `def preflight_required_bars_data_source(`
- ligne 214 — `def load_ohlcv(engine: Engine, start: date, end: date) -> pd.DataFrame:`
- ligne 258 — `def load_spreads(`
- ligne 28 — `def load_tradable_universe_asof(`
- ligne 337 — `def load_scores(`
- ligne 44 — `def load_tradable_universe_scope(`
- ligne 578 — `def load_sentiment(engine: Engine, start: date, end: date, lookback_days: int = 365) -> pd.DataFrame:`
- ligne 620 — `def load_predictions(`
- ligne 718 — `def pivot_ohlcv(df: pd.DataFrame) -> dict[str, pd.DataFrame]:`
- ligne 72 — `def _build_table_access_error(table_name: str, exc: Exception) -> RuntimeError:`
- ligne 81 — `def _table_exists(engine: Engine, table_name: str) -> bool:`
- ligne 90 — `def _get_table_columns(engine: Engine, table_name: str, *, required: bool = False) -> set[str]:`
## `backtesting/execution_bridge.py`

- ligne 132 — `def _dataclasses_to_frame(items: list[object]) -> pd.DataFrame:`
- ligne 138 — `def save_phase2_execution_artifacts(result: ExecutionBridgeResult, output_dir: Path) -> dict[str, str]:`
- ligne 21 — `class ExecutionBridgeResult:`
- ligne 30 — `def portfolio_entries_to_execution_targets(`
- ligne 74 — `def simulate_phase2_execution(`
## `backtesting/execution_broker_like.py`

- ligne 108 — `def concat_broker_event_frames(*frames: pd.DataFrame | None) -> pd.DataFrame:`
- ligne 118 — `def _string_count_map(series: pd.Series | None) -> dict[str, int]:`
- ligne 128 — `def _session_key_from_row(row: Mapping[str, Any]) -> str | None:`
- ligne 140 — `def _count_true(series: pd.Series | None) -> int:`
- ligne 147 — `def _count_event_type(frame: pd.DataFrame, event_type: str) -> int:`
- ligne 151 — `def build_execution_broker_like_summary(`
- ligne 301 — `def save_execution_broker_like_artifacts(`
- ligne 78 — `def ensure_order_lifecycle_frame(frame: pd.DataFrame | None) -> pd.DataFrame:`
- ligne 88 — `def ensure_broker_event_frame(frame: pd.DataFrame | None) -> pd.DataFrame:`
- ligne 98 — `def concat_order_lifecycle_frames(*frames: pd.DataFrame | None) -> pd.DataFrame:`
## `backtesting/execution_lifecycle_replay.py`

- ligne 22 — `class ProtectionReplayResult:`
- ligne 30 — `def _child_intents_by_parent(child_intents: list[OrderIntent]) -> dict[str, list[OrderIntent]]:`
- ligne 313 — `def save_phase4_protection_replay_artifacts(result: ProtectionReplayResult, output_dir: Path) -> dict[str, str]:`
- ligne 40 — `def _aggregate_entry_fills_by_intent(execution_replay_result: ExecutionReplayResult) -> dict[str, dict[str, object]]:`
- ligne 62 — `def build_phase4_protection_replay(`
## `backtesting/execution_replay.py`

- ligne 128 — `def _build_synthetic_fill_attempts(`
- ligne 310 — `def _execution_fills_from_attempts(`
- ligne 345 — `def _weighted_average_fill_price(fills: list[ExecutionFill]) -> float:`
- ligne 353 — `def _event_type_for_attempt_terminal_state(attempt: _SyntheticFillAttempt) -> str:`
- ligne 363 — `def simulate_phase3_execution_replay(`
- ligne 38 — `class ExecutionReplayResult:`
- ligne 47 — `class _SyntheticFillAttempt:`
- ligne 71 — `def _resolve_execution_day(snapshot_date: datetime | pd.Timestamp | object, trading_days: pd.DatetimeIndex) -> pd.Timestamp | None:`
- ligne 81 — `def _entry_to_target(`
- ligne 869 — `def save_phase3_execution_replay_artifacts(result: ExecutionReplayResult, output_dir: Path) -> dict[str, str]:`
## `backtesting/exit_lifecycle_replay.py`

- ligne 23 — `class ExitLifecycleReplayResult:`
- ligne 33 — `def _map_exit_reason_to_intent_role(exit_reason: str) -> str:`
- ligne 381 — `def save_phase7_exit_lifecycle_replay_artifacts(result: ExitLifecycleReplayResult, output_dir: Path) -> dict[str, str]:`
- ligne 44 — `def build_phase7_exit_lifecycle_replay(`
## `backtesting/fidelity.py`

- ligne 1005 — `def _first_present_float(series: pd.Series | None) -> float | None:`
- ligne 101 — `def _normalize_reason(reason: object) -> str:`
- ligne 1014 — `def _aggregate_trade_compare_frame(frame: pd.DataFrame | None) -> pd.DataFrame:`
- ligne 106 — `def _normalize_reason_list(reasons: object) -> list[str]:`
- ligne 1088 — `def _execution_fills_to_compare_frame(fills: Sequence[object], *, run_id: str | None = None) -> pd.DataFrame:`
- ligne 1109 — `def _exit_signals_to_compare_frame(signals_df: pd.DataFrame, *, execution_date: pd.Timestamp) -> pd.DataFrame:`
- ligne 1136 — `def _position_lots_to_exit_compare_frame(lots_df: pd.DataFrame | None) -> pd.DataFrame:`
- ligne 1159 — `def _exit_signals_to_pnl_frame(signals_df: pd.DataFrame, *, execution_date: pd.Timestamp) -> pd.DataFrame:`
- ligne 1187 — `def _position_lots_to_pnl_frame(lots_df: pd.DataFrame | None) -> pd.DataFrame:`
- ligne 120 — `def _reason_details(reasons: Sequence[str]) -> list[dict[str, str]]:`
- ligne 1208 — `def _qty_within_compare_tolerance(live_qty: float, replay_qty: float, *, pct: float = 0.05, abs_: float = 1.0) -> bool:`
- ligne 1216 — `def _status_for_trade_section(*, live_available: bool, replay_available: bool, divergent: bool) -> str:`
- ligne 1226 — `def _summarize_trade_lifecycle_section(`
- ligne 1316 — `def _summarize_pnl_section(`
- ligne 1398 — `def _build_selection_live_compare_section(`
- ligne 1443 — `def _summarize_parity_section(`
- ligne 147 — `def _normalize_symbols(symbols: object) -> list[str]:`
- ligne 1502 — `def _collect_compare_session_dates(`
- ligne 1533 — `def _build_compare_to_live_markdown(summary: Mapping[str, Any]) -> str:`
- ligne 1575 — `def build_compare_to_live_summary(`
- ligne 161 — `def _safe_int(value: object, default: int = 0) -> int:`
- ligne 168 — `def _safe_float(value: object, default: float = 0.0) -> float:`
- ligne 175 — `def _coverage_payload(`
- ligne 1895 — `def save_compare_to_live_summary(summary: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:`
- ligne 1939 — `def _normalize_phase_modes_from_payload(*payloads: Mapping[str, Any] | None) -> dict[str, str]:`
- ligne 1955 — `def _safe_ratio(numerator: object, denominator: object) -> float:`
- ligne 1962 — `def _sanitize_baseline_id(value: object) -> str | None:`
- ligne 1967 — `def build_fidelity_baseline_snapshot(`
- ligne 207 — `def _component_status_payload(`
- ligne 2083 — `def save_fidelity_baseline_snapshot(snapshot: Mapping[str, Any], output_dir: Path) -> Path:`
- ligne 2091 — `def save_fidelity_baseline_promotion_manifest(manifest: Mapping[str, Any], output_dir: Path) -> Path:`
- ligne 2099 — `def _load_json_mapping(path: Path) -> dict[str, Any] | None:`
- ligne 2109 — `def _resolve_report_artifacts_dir(source_report_path: Path | None) -> Path | None:`
- ligne 2115 — `def _load_json_artifact_from_report(`
- ligne 2130 — `def _extract_run_id_from_report_path(source_report_path: Path | None) -> str | None:`
- ligne 2141 — `def build_fidelity_baseline_promotion_manifest(`
- ligne 2203 — `def promote_fidelity_baseline_from_report(`
- ligne 2278 — `def promote_fidelity_baseline_from_report_path(`
- ligne 2302 — `def _resolve_baseline_entry(`
- ligne 231 — `def _extract_component_reasons(component: str, reasons: Sequence[str]) -> list[str]:`
- ligne 2329 — `def _default_baseline_metric_thresholds() -> dict[str, dict[str, object]]:`
- ligne 2347 — `def _normalize_metric_thresholds(value: object) -> dict[str, dict[str, object]]:`
- ligne 2365 — `def _evaluate_numeric_baseline_check(`
- ligne 2399 — `def _evaluate_exact_mapping_check(`
- ligne 2419 — `def build_fidelity_baseline_comparison(`
- ligne 242 — `def _normalize_string_list(values: object) -> list[str]:`
- ligne 2535 — `def save_fidelity_baseline_comparison(comparison: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:`
- ligne 256 — `def _normalize_symbol_cause_mapping(value: object) -> dict[str, list[str]]:`
- ligne 2567 — `def _build_scores_provenance(score_payload: Mapping[str, Any], *, requested_score_column: str | None) -> dict[str, object]:`
- ligne 2587 — `def _build_sentiment_provenance(sentiment_payload: Mapping[str, Any], *, sentiment_mode: str) -> dict[str, object]:`
- ligne 2614 — `def _build_ml_provenance(ml_payload: Mapping[str, Any], *, ml_mode: str, ml_pit_strategy: str) -> dict[str, object]:`
- ligne 2645 — `class PitHistoryRequiredError(RuntimeError):`
- ligne 2649 — `class PitMlStrategyUnsupportedError(RuntimeError):`
- ligne 2653 — `def resolve_ml_pit_strategy(*, engine_mode: str, ml_mode: str, requested_strategy: str | None) -> str:`
- ligne 2669 — `class ScoreLoadDiagnostics:`
- ligne 270 — `def _normalize_count_mapping(value: object) -> dict[str, int]:`
- ligne 2700 — `class ScoreLoadResult:`
- ligne 2708 — `class SentimentPreparationDiagnostics:`
- ligne 2746 — `class PreparedScoresResult:`
- ligne 2752 — `class MlPreparationDiagnostics:`
- ligne 2797 — `class PreparedPredictionsResult:`
- ligne 2802 — `def evaluate_ml_coverage_gate(`
- ligne 282 — `def _normalize_trade_date_series(frame: pd.DataFrame) -> pd.Series:`
- ligne 2875 — `def build_fidelity_manifest(`
- ligne 288 — `def _normalize_timestamp_value(value: object) -> pd.Timestamp:`
- ligne 298 — `def _infer_score_source_counts(scores_day: pd.DataFrame) -> dict[str, int]:`
- ligne 3034 — `def save_fidelity_manifest(manifest: dict[str, Any], output_dir: Path) -> Path:`
- ligne 3042 — `def build_coverage_summary(manifest: Mapping[str, Any]) -> dict[str, Any]:`
- ligne 3068 — `def save_coverage_summary(manifest: Mapping[str, Any], output_dir: Path) -> Path:`
- ligne 3077 — `def build_fidelity_symbol_matrix(`
- ligne 319 — `def _sorted_unique_symbols(frame: pd.DataFrame, *, mask: pd.Series | None = None) -> list[str]:`
- ligne 3204 — `def save_fidelity_symbol_matrix(matrix: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:`
- ligne 328 — `def _sorted_unique_values(frame: pd.DataFrame, column: str) -> list[str]:`
- ligne 334 — `def _status_from_flag(degraded: bool) -> str:`
- ligne 338 — `def _extract_run_level_ref(component_details: Mapping[str, Any], *paths: tuple[str, ...]) -> str | None:`
- ligne 348 — `def _build_session_scores_snapshot_id(`
- ligne 370 — `def _build_component_attribution(`
- ligne 435 — `def _build_critical_symbol_payload(`
- ligne 496 — `def build_replay_diagnostic_summary(`
- ligne 668 — `def save_replay_diagnostic_summary(summary: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:`
- ligne 713 — `def _sorted_session_dates_from_frames(*frames: pd.DataFrame) -> list[pd.Timestamp]:`
- ligne 722 — `def _normalize_research_selected_rows(research_signals_df: pd.DataFrame) -> pd.DataFrame:`
- ligne 732 — `def _portfolio_entries_to_parity_frame(entries: Sequence[object]) -> pd.DataFrame:`
- ligne 772 — `def build_selection_target_parity_summary(`
- ligne 877 — `def save_selection_target_parity_summary(summary: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:`
- ligne 911 — `def _normalize_compare_frame(frame: pd.DataFrame | None) -> pd.DataFrame:`
- ligne 920 — `def _normalize_live_buy_symbol_set(frame: pd.DataFrame) -> list[str]:`
- ligne 932 — `def _research_selected_symbols_for_date(research_signals_df: pd.DataFrame, trade_date: pd.Timestamp) -> list[str]:`
- ligne 946 — `def _portfolio_entries_to_compare_frame(entries: Sequence[object], *, run_id: str | None = None) -> pd.DataFrame:`
- ligne 968 — `def _execution_targets_to_compare_frame(targets: Sequence[object], *, run_id: str | None = None) -> pd.DataFrame:`
- ligne 987 — `def _extract_compare_value(item: object, name: str, default: object = None) -> object:`
- ligne 993 — `def _first_present_text(series: pd.Series | None) -> str | None:`
## `backtesting/fuzz_runner.py`

- ligne 104 — `class _ExecResult:`
- ligne 121 — `def _run_engine(`
- ligne 205 — `def _diff_kind(`
- ligne 226 — `class FuzzReport:`
- ligne 249 — `def run_fuzz_diff(`
- ligne 42 — `class FuzzScenario:`
- ligne 63 — `def generate_scenarios(n: int, *, master_seed: int = 1234) -> list[FuzzScenario]:`
## `backtesting/fuzz_tolerance.py`

- ligne 14 — `class FuzzTolerance:`
## `backtesting/microstructure.py`

- ligne 118 — `class MicrostructureConfig:`
- ligne 151 — `def should_skip_entry_for_gap(`
- ligne 171 — `class IntraBarResolution:`
- ligne 179 — `def resolve_intrabar_exit(`
- ligne 247 — `def compute_execution_price(`
- ligne 297 — `def should_split_order(`
- ligne 33 — `class ExecutionModelConfig:`
- ligne 58 — `class SlippageConfig:`
- ligne 89 — `def compute_adv_usd(`
## `backtesting/parity.py`

- ligne 121 — `def _norm_symbol(value: Any) -> Optional[str]:`
- ligne 128 — `def _norm_action(value: Any) -> Optional[str]:`
- ligne 135 — `def _safe_float(value: Any, default: float = 0.0) -> float:`
- ligne 147 — `def _safe_optional_float(value: Any) -> Optional[float]:`
- ligne 159 — `def _qty_within_tolerance(live: float, replay: float, *, pct: float, abs_: float) -> bool:`
- ligne 172 — `def _index_by_symbol(df: pd.DataFrame) -> dict[str, dict[str, Any]]:`
- ligne 185 — `def compare_decisions(`
- ligne 316 — `def compare_risk_layers(`
- ligne 398 — `def summarize_paper_coverage(`
- ligne 457 — `def write_parity_artifacts(report: ParityReport, output_dir: Path | str) -> dict[str, Path]:`
- ligne 478 — `def _build_alert_body(report: ParityReport, threshold: float) -> str:`
- ligne 497 — `def run_daily_parity(`
- ligne 52 — `class ParityRow:`
- ligne 69 — `class ParityReport:`
## `backtesting/profiles.py`

- ligne 51 — `def apply_profile(args, profile_name: str | None, *, explicit_flags: set[str]) -> None:`
## `backtesting/protection_watcher_replay.py`

- ligne 21 — `class ProtectionWatcherReplayResult:`
- ligne 250 — `def save_phase5_watcher_replay_artifacts(result: ProtectionWatcherReplayResult, output_dir: Path) -> dict[str, str]:`
- ligne 30 — `def _find_trigger_date(`
- ligne 59 — `def _next_trading_day(day: pd.Timestamp, trading_days: pd.DatetimeIndex) -> pd.Timestamp | None:`
- ligne 66 — `def build_phase5_watcher_replay(`
## `backtesting/regime_trailing.py`

- ligne 34 — `def compute_regime(spy_close: pd.Series) -> pd.Series:`
- ligne 52 — `def trailing_for_regime(regime: str | None, policy: str) -> tuple[float | None, bool]:`
- ligne 66 — `def build_regime_trailing_map(spy_close: pd.Series, policy: str) -> dict[date, tuple[float | None, bool]]:`
- ligne 77 — `def regime_distribution(dates: pd.Series, spy_close: pd.Series) -> pd.Series:`
## `backtesting/report_schema.py`

- ligne 100 — `class RunMetadataSchema:`
- ligne 112 — `class DiagnosticsSchema:`
- ligne 128 — `class BacktestReportSchema:`
- ligne 157 — `def _check_type(value: Any, expected: tuple[type, ...], path: str) -> None:`
- ligne 164 — `def validate_report_payload(payload: dict[str, Any], *, strict: bool = False) -> BacktestReportSchema:`
- ligne 30 — `class ReportSchemaError(ValueError):`
- ligne 40 — `class SummarySchema:`
- ligne 68 — `class MicrostructureParamsSchema:`
- ligne 81 — `class RiskOverlayParamsSchema:`
## `backtesting/report.py`

- ligne 103 — `def _with_trade_merge_seq(frame: pd.DataFrame, *, execution_date_col: str) -> pd.DataFrame:`
- ligne 119 — `def _build_legacy_trade_export_frame(pf) -> tuple[pd.DataFrame, str]:`
- ligne 143 — `def _build_pipeline_trade_export_frame(`
- ligne 22 — `def _as_float(value) -> float:`
- ligne 29 — `def _as_int(value) -> int:`
- ligne 311 — `def build_trade_export_bundle(`
- ligne 346 — `def load_corporate_actions_summary(`
- ligne 36 — `def _clean_metric(value: float, default: float = 0.0) -> float:`
- ligne 399 — `class BacktestReport:`
- ligne 43 — `def _extract_equity_curve(pf) -> pd.Series:`
- ligne 525 — `def load_dividends_received(`
- ligne 548 — `def _compute_ulcer_index(equity: pd.Series) -> float:`
- ligne 55 — `def _extract_closed_trades_df(pf) -> Optional[pd.DataFrame]:`
- ligne 560 — `def _compute_calmar(cagr_pct: float, max_dd_pct: float) -> float:`
- ligne 572 — `def generate_report(`
- ligne 59 — `def _extract_trade_events_df(pf) -> Optional[pd.DataFrame]:`
- ligne 63 — `def extract_diagnostics(pf) -> dict[str, object]:`
- ligne 78 — `def _normalize_symbol_column(df: pd.DataFrame, column_name: str = "symbol") -> pd.DataFrame:`
- ligne 811 — `def save_equity_curve(pf, output_dir: Path | None = None) -> Path:`
- ligne 846 — `def save_trades_csv(`
- ligne 85 — `def _normalize_datetime_columns(df: pd.DataFrame, *column_names: str) -> pd.DataFrame:`
- ligne 875 — `def save_trade_audit_csv(pf, output_dir: Path | None = None) -> Path:`
- ligne 894 — `def save_equity_curve_csv(pf, output_dir: Path | None = None) -> Path:`
- ligne 910 — `def save_report_json(`
- ligne 93 — `def _coalesce_columns(frame: pd.DataFrame, columns: tuple[str, ...], *, default: object = None) -> pd.Series:`
## `backtesting/resilience.py`

- ligne 109 — `def _freeze_missing_causes_by_symbol(symbol_causes: dict[str, set[str]]) -> dict[str, tuple[str, ...]]:`
- ligne 117 — `def _rebuild_prediction_frame(`
- ligne 142 — `def _rebuild_prediction_batch_frame(`
- ligne 167 — `def _resolve_scores_history_identity(scores_df: pd.DataFrame) -> tuple[str | None, str | None]:`
- ligne 181 — `def prepare_scores_for_sentiment_mode(`
- ligne 346 — `def _apply_walk_forward_overlay(scores_df: pd.DataFrame, artifacts_dir: Path | None) -> tuple[pd.DataFrame, bool, str | None]:`
- ligne 35 — `def _normalize_dates(df: pd.DataFrame, date_col: str = "trade_date") -> pd.DataFrame:`
- ligne 374 — `def prepare_predictions_for_ml_mode(`
- ligne 43 — `def _expected_symbol_dates(universe_df: pd.DataFrame) -> set[tuple[str, pd.Timestamp]]:`
- ligne 54 — `def _extract_unique_symbols(frame: pd.DataFrame, *, mask: pd.Series | None = None) -> tuple[str, ...]:`
- ligne 68 — `def _ensure_dataframe(value: object) -> pd.DataFrame:`
- ligne 78 — `def _merge_prediction_frames(existing: pd.DataFrame, rebuilt: pd.DataFrame) -> pd.DataFrame:`
- ligne 85 — `def _classify_ml_missing_cause_from_runtime_status(status: dict[str, object]) -> str:`
## `backtesting/risk_bridge.py`

- ligne 101 — `def _build_selection_inputs_from_day(day_df: pd.DataFrame, snapshot_date: date) -> list[SelectionScore]:`
- ligne 153 — `def _compute_atr_20(high_series: pd.Series, low_series: pd.Series, close_series: pd.Series) -> float | None:`
- ligne 172 — `def _build_prices(`
- ligne 222 — `def _build_predictions(predictions_df: pd.DataFrame, snapshot_date: date) -> dict[str, PredictionInfo]:`
- ligne 280 — `def _build_ml_selection_inputs_from_day(`
- ligne 353 — `def _build_return_matrix(close_df: pd.DataFrame, snapshot_date: date, symbols: list[str], lookback_days: int) -> pd.DataFrame | None:`
- ligne 365 — `def _resolve_regime_snapshot_dates(close_df: pd.DataFrame, execution_dates: list[date]) -> list[date]:`
- ligne 379 — `def portfolio_entries_to_signals(entries: list[PortfolioEntry], snapshot_date: date) -> pd.DataFrame:`
- ligne 415 — `def _concat_signal_frames(signal_frames: Iterable[pd.DataFrame]) -> pd.DataFrame:`
- ligne 422 — `def build_phase2_risk_result(`
- ligne 58 — `class RiskBridgeResult:`
- ligne 66 — `def _normalize_trade_dates(df: pd.DataFrame) -> pd.DataFrame:`
- ligne 73 — `def _resolve_float(row: pd.Series, column: str) -> float | None:`
- ligne 789 — `def entries_to_dataframe(entries: list[PortfolioEntry]) -> pd.DataFrame:`
- ligne 795 — `def _regime_snapshots_to_dataframe(regime_snapshots: dict[date, dict]) -> pd.DataFrame:`
- ligne 80 — `def _prepare_score_columns(scores_df: pd.DataFrame, *, preferred_score_column: str | None = None) -> pd.DataFrame:`
- ligne 822 — `def save_phase2_risk_artifacts(result: RiskBridgeResult, output_dir: Path) -> dict[str, str]:`
- ligne 93 — `def _build_selection_inputs(scores_df: pd.DataFrame, snapshot_date: date) -> list[SelectionScore]:`
## `backtesting/risk_overlay.py`

- ligne 100 — `class SectoralCapConfig:`
- ligne 118 — `class DrawdownCircuitBreaker:`
- ligne 24 — `class RegimeFilterConfig:`
- ligne 336 — `def compute_portfolio_vol_scaler(`
- ligne 357 — `def snapshot_sector_exposure(`
- ligne 406 — `class RiskOverlayConfig:`
- ligne 49 — `class BullStrictConfig:`
## `backtesting/run_metadata.py`

- ligne 31 — `def _safe_git_command(args: list[str]) -> str | None:`
- ligne 43 — `def collect_git_info() -> dict[str, Any]:`
- ligne 51 — `def collect_environment_info() -> dict[str, Any]:`
- ligne 67 — `def hash_dataset(frames: Mapping[str, pd.DataFrame | pd.Series | None]) -> str:`
- ligne 99 — `def build_run_metadata(`
## `backtesting/screener_diagnostics/_impl.py`

- ligne 1048 — `def recommend_screener_scenarios_by_regime(`
- ligne 1108 — `def recommend_screener_scenarios_by_objective(`
- ligne 121 — `class ScreenerDiagnosticsResult:`
- ligne 1351 — `class ScreenerDiagnosticsService:`
- ligne 152 — `def _dedupe_preserve_order(values: Sequence[float | int] | None) -> list[float | int]:`
- ligne 165 — `def _scenario_config_key(config: ScreenerConfig) -> tuple[float, int, float, float]:`
- ligne 174 — `def _format_float_token(value: float) -> str:`
- ligne 180 — `def _format_liquidity_token(value: float) -> str:`
- ligne 1904 — `def export_screener_diagnostics(result: ScreenerDiagnosticsResult, output_dir: str | Path) -> dict[str, Path]:`
- ligne 192 — `def build_screener_oat_scenarios(`
- ligne 1938 — `def export_screener_recommendations(`
- ligne 1959 — `def export_screener_regime_recommendations(`
- ligne 1988 — `def export_screener_objective_recommendations(`
- ligne 2009 — `def validate_recommendations_holdout(`
- ligne 2095 — `def export_holdout_validation(`
- ligne 272 — `def build_screener_grid_scenarios(`
- ligne 336 — `def _safe_divide(numerator: float | int, denominator: float | int) -> float:`
- ligne 342 — `def _safe_numeric_mean(frame: pd.DataFrame, column: str) -> float:`
- ligne 351 — `def summarize_screener_diagnostics(`
- ligne 412 — `def classify_market_regimes(`
- ligne 500 — `def summarize_screener_diagnostics_by_regime(`
- ligne 526 — `def _pick_first_available_column(frame: pd.DataFrame, candidates: Sequence[str]) -> str | None:`
- ligne 536 — `def _winsorize_series(series: pd.Series, *, quantile: float = 0.05) -> pd.Series:`
- ligne 546 — `def _normalize_metric_series(series: pd.Series, *, higher_is_better: bool) -> pd.Series:`
- ligne 565 — `def _weighted_average_columns(frame: pd.DataFrame, columns_with_weights: Sequence[tuple[str, float]]) -> pd.Series:`
- ligne 578 — `def _weighted_confidence(frame: pd.DataFrame, columns_with_weights: Sequence[tuple[str, float]]) -> pd.Series:`
- ligne 591 — `def _weighted_geometric_mean(frame: pd.DataFrame, columns_with_weights: Sequence[tuple[str, float]]) -> pd.Series:`
- ligne 606 — `def _candidate_mean_columns(prefix: str, metric: str, target_horizon: int) -> list[str]:`
- ligne 611 — `def _candidate_daily_columns(prefix: str, metric: str, target_horizon: int) -> list[str]:`
- ligne 616 — `def _enrich_summary_with_daily_stability(`
- ligne 659 — `def _build_recommendation_text(row: pd.Series, *, forward_column: str | None) -> str:`
- ligne 674 — `def _build_objective_reason(`
- ligne 699 — `def _empty_objective_summary(`
- ligne 712 — `def _resolve_objective_summary_by_regime(`
- ligne 725 — `def recommend_screener_scenarios(`
- ligne 97 — `class ScreenerDiagnosticsScenario:`
- ligne 973 — `def build_cross_regime_recommendations(`
## `backtesting/sentiment_calibration.py`

- ligne 113 — `class WalkForwardCalibrationResult:`
- ligne 1132 — `def _emit_run_summary(summary: dict[str, object]) -> None:`
- ligne 1151 — `def _build_arg_parser() -> argparse.ArgumentParser:`
- ligne 1172 — `def main(argv: list[str] | None = None) -> int:`
- ligne 128 — `class SentimentWeightCalibrator:`
- ligne 38 — `def _resolve_symbol_source(engine: Engine, symbol_source: str) -> list[str]:`
- ligne 53 — `def _normalize_preset_keys(`
- ligne 68 — `def _utc_now_naive() -> datetime:`
- ligne 72 — `def _build_run_id(prefix: str) -> str:`
- ligne 77 — `class SentimentCalibrationScenario:`
- ligne 88 — `class SentimentCalibrationResult:`
- ligne 99 — `class WalkForwardFoldResult:`
## `backtesting/signal_replay.py`

- ligne 33 — `def _validate_prediction_policy_consistency(df: pd.DataFrame) -> None:`
- ligne 58 — `def _pick_score_column(`
- ligne 93 — `def replay_signals(`
## `backtesting/simulator.py`

- ligne 279 — `class BacktestDiagnostics:`
- ligne 337 — `class _OpenPosition:`
- ligne 376 — `class _RunState:`
- ligne 397 — `class _DailyLeverageState:`
- ligne 405 — `class _ReadableTradesAccessor:`
- ligne 447 — `class BacktestResult:`
- ligne 471 — `class BacktestEngine:`
- ligne 59 — `def _effective_trailing_pct(cfg: "BacktestConfig", short: bool, derived_pct: float) -> float:`
- ligne 72 — `def _production_tp_price(`
- ligne 94 — `class BacktestConfig:`
## `backtesting/statistical_validation.py`

- ligne 152 — `def parameter_sensitivity(`
- ligne 218 — `class WalkForwardPlan:`
- ligne 262 — `class DeflatedSharpeResult:`
- ligne 285 — `def deflated_sharpe_ratio(`
- ligne 34 — `class BootstrapResult:`
- ligne 354 — `def block_bootstrap_sharpe(`
- ligne 413 — `def multiple_testing_correction(`
- ligne 453 — `class PromotionScoreResult:`
- ligne 480 — `def compute_promotion_score(`
- ligne 575 — `def _skewness(x: np.ndarray) -> float:`
- ligne 586 — `def _kurtosis(x: np.ndarray) -> float:`
- ligne 65 — `def bootstrap_trades(`
## `backtesting/trading_constraints.py`

- ligne 11 — `class TradingConstraintConfig:`
- ligne 123 — `def resolve_commission_preset(equity: float) -> TieredCommissionConfig:`
- ligne 58 — `def build_current_trading_constraints(`
- ligne 76 — `class TieredCommissionConfig:`
## `backtesting/walk_forward_engine.py`

- ligne 153 — `class WalkForwardResult:`
- ligne 216 — `def _compute_equity_metrics(`
- ligne 265 — `def _compute_trade_metrics(`
- ligne 330 — `def run_walk_forward_fold(`
- ligne 40 — `class WalkForwardConfig:`
- ligne 426 — `def _simulate_fold_execution(`
- ligne 515 — `def run_walk_forward(`
- ligne 638 — `class WalkForwardReport:`
- ligne 72 — `class FoldFinancials:`
- ligne 722 — `def _json_default(obj: object) -> object:`
- ligne 733 — `def generate_walk_forward_report(`
- ligne 786 — `def create_db_data_provider(`
## `backtesting/walk_forward.py`

- ligne 104 — `def validate_walk_forward_weights(`
- ligne 188 — `def resolve_latest_walk_forward_weights(search_roots: Iterable[Path] | None = None) -> WalkForwardWeights | None:`
- ligne 212 — `class RiskParamResult:`
- ligne 231 — `def walk_forward_risk_params(`
- ligne 342 — `def apply_walk_forward_weights(scores_df: pd.DataFrame, weights: WalkForwardWeights | None) -> pd.DataFrame:`
- ligne 44 — `class WalkForwardWeights:`
- ligne 54 — `def _candidate_roots(search_roots: Iterable[Path] | None = None) -> list[Path]:`
- ligne 65 — `def _extract_weight(payload: dict[str, Any], *names: str) -> float | None:`
- ligne 77 — `def load_walk_forward_weights(path: Path) -> WalkForwardWeights | None:`
## `backtesting/weights_calibration.py`

- ligne 107 — `def metric_strategy_log_growth(strategy_returns: np.ndarray) -> float:`
- ligne 126 — `class CalibrationCandidate:`
- ligne 132 — `class CalibrationResult:`
- ligne 159 — `class EmpiricalRiskCalibrationRun:`
- ligne 186 — `class CalibrationSegmentDrift:`
- ligne 203 — `def _conviction_grid(step: float = 0.05) -> Iterable[ConvictionWeights]:`
- ligne 2039 — `def persist_calibration_run(`
- ligne 212 — `def _sentiment_grid(step: float = 0.05) -> Iterable[SentimentFusionWeights]:`
- ligne 2148 — `def persist_segment_drifts(drifts: Sequence[CalibrationSegmentDrift], *, engine: Any) -> int:`
- ligne 247 — `def _kelly_grid(`
- ligne 263 — `def _subtract_months(reference: date, months: int) -> date:`
- ligne 273 — `def _build_segment_key(*, market_regime_mode: str, horizon_days: int, lookback_months: int | None) -> str:`
- ligne 282 — `def _compute_relative_drift(current: float, reference: float) -> float | None:`
- ligne 288 — `def _evaluate_live_governance(`
- ligne 308 — `def compute_segment_drifts(`
- ligne 392 — `def calibrate_conviction(`
- ligne 452 — `def calibrate_sentiment(`
- ligne 516 — `def _compute_kelly_fraction(`
- ligne 538 — `def _weighted_daily_strategy_returns(`
- ligne 57 — `def normalize_market_regime_mode(value: object) -> str:`
- ligne 571 — `def calibrate_conviction_kelly(`
- ligne 678 — `def calibrate_conviction_kelly_short(`
- ligne 68 — `def metric_information_coefficient(predictions: np.ndarray, forward_returns: np.ndarray) -> float:`
- ligne 787 — `class EmpiricalRiskCalibrator:`
- ligne 79 — `def metric_hit_rate(predictions: np.ndarray, forward_returns: np.ndarray, *, threshold: float = 0.5) -> float:`
- ligne 96 — `def metric_strategy_sharpe(strategy_returns: np.ndarray) -> float:`

