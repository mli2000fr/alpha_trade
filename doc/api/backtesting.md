# Inventaire API — backtesting

Extraction AST du 2026-10-10 ; aucune importation ni exécution métier.

Classes, fonctions de module et méthodes déclarées ; fonctions imbriquées exclues.
Les symboles `_...` sont internes. Signature présente ≠ API publique stable.

## `backtesting/__init__.py`

Source SHA-256 : `dc36d7f4cf9e499adcebbc87b7471b00a520ab853472bc5f1495ca4c9e80f70f`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `backtesting/__main__.py`

Source SHA-256 : `0f74053dfa627c9ad8ae4ef8afdf50352b77fd797bd98e794b0c06b7a32517bf`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `backtesting/adaptive_breaker.py`

Source SHA-256 : `c048ddf637ab302bcae8b38ba87a27601005bdcfc19a222ad0cb79e967f1e01b`

- [BreakerEpisode](../../backtesting/adaptive_breaker.py) — ligne 52 : `class BreakerEpisode`
- [recovery_ratio](../../backtesting/adaptive_breaker.py) — ligne 64 : `def recovery_ratio(episode: BreakerEpisode, equity: float) -> float`
- [_tiers_from_ratio](../../backtesting/adaptive_breaker.py) — ligne 75 : `def _tiers_from_ratio(rr: float, tiers: list[tuple[float, float]]) -> float`
- [is_favorable](../../backtesting/adaptive_breaker.py) — ligne 97 : `def is_favorable(regime: str | None) -> bool`
- [b0_allocation](../../backtesting/adaptive_breaker.py) — ligne 101 : `def b0_allocation(episode: BreakerEpisode, equity: float, recovery_pct: float, degraded: float, ramp_max: float, favorable: bool, per_day: float=0.025) -> float`
- [b1_allocation](../../backtesting/adaptive_breaker.py) — ligne 115 : `def b1_allocation(episode: BreakerEpisode, equity: float) -> float`
- [b2_allocation](../../backtesting/adaptive_breaker.py) — ligne 121 : `def b2_allocation(episode: BreakerEpisode, equity: float, favorable: bool) -> float`
- [b3_allocation](../../backtesting/adaptive_breaker.py) — ligne 136 : `def b3_allocation(episode: BreakerEpisode, equity: float, favorable: bool) -> float`
- [b4_allocation](../../backtesting/adaptive_breaker.py) — ligne 154 : `def b4_allocation(episode: BreakerEpisode, equity: float, regime: str | None, *, bull_streak_level: float=B4_BULL_STREAK_ALLOC) -> float`
- [_dd_pct](../../backtesting/adaptive_breaker.py) — ligne 208 : `def _dd_pct(episode: BreakerEpisode, equity: float) -> float`
- [_b4_check_relapse](../../backtesting/adaptive_breaker.py) — ligne 215 : `def _b4_check_relapse(episode: BreakerEpisode, equity: float, prev_trough: float) -> None`
- [allocate](../../backtesting/adaptive_breaker.py) — ligne 234 : `def allocate(policy: str, episode: BreakerEpisode, equity: float, *, regime: str | None=None, recovery_pct: float=0.92, degraded: float=0.06, ramp_max: float=0.25) -> float`
- [trip_or_recover](../../backtesting/adaptive_breaker.py) — ligne 253 : `def trip_or_recover(episode: BreakerEpisode, equity: float, peak_equity: float, *, policy: str, max_dd_pct: float=TRIP_DD_PCT, recovery_pct: float=0.92) -> None`
- [update_streak](../../backtesting/adaptive_breaker.py) — ligne 296 : `def update_streak(episode: BreakerEpisode, favorable: bool) -> None`

## `backtesting/analytics.py`

Source SHA-256 : `b0ac7efa551f712416883a760f680fa6f3d33674db1de9a0452b7f282d5392b0`

- [compute_total_return_with_dividends](../../backtesting/analytics.py) — ligne 30 : `def compute_total_return_with_dividends(initial_equity: float, final_value_mtm: float, dividends_received: float) -> dict[str, float]`
- [compare_total_return_to_oracle](../../backtesting/analytics.py) — ligne 62 : `def compare_total_return_to_oracle(*, initial_equity: float, final_value_mtm: float, dividends_received: float, oracle_total_return_pct: float, tolerance_bps: float=25.0) -> dict[str, float | bool]`
- [BenchmarkAnalytics](../../backtesting/analytics.py) — ligne 98 : `class BenchmarkAnalytics`
- [BenchmarkAnalytics.to_dict](../../backtesting/analytics.py) — ligne 107 : `def to_dict(self) -> dict[str, float]`
- [compute_benchmark_analytics](../../backtesting/analytics.py) — ligne 119 : `def compute_benchmark_analytics(equity: pd.Series, benchmark_close: pd.Series, *, risk_free_rate: float=0.0, trading_days_per_year: int=252) -> BenchmarkAnalytics`
- [sector_attribution](../../backtesting/analytics.py) — ligne 179 : `def sector_attribution(closed_trades_df: pd.DataFrame) -> pd.DataFrame`
- [monthly_returns_table](../../backtesting/analytics.py) — ligne 194 : `def monthly_returns_table(equity: pd.Series) -> pd.DataFrame`
- [TailAnalytics](../../backtesting/analytics.py) — ligne 217 : `class TailAnalytics`
- [TailAnalytics.to_dict](../../backtesting/analytics.py) — ligne 223 : `def to_dict(self) -> dict[str, float]`
- [compute_tail_analytics](../../backtesting/analytics.py) — ligne 232 : `def compute_tail_analytics(equity: pd.Series, *, alpha: float=0.05) -> TailAnalytics`
- [save_equity_curve_html](../../backtesting/analytics.py) — ligne 255 : `def save_equity_curve_html(equity: pd.Series, output_path: Path) -> Path | None`
- [build_extended_report_payload](../../backtesting/analytics.py) — ligne 286 : `def build_extended_report_payload(*, summary: dict[str, Any], benchmark: BenchmarkAnalytics | None=None, tail: TailAnalytics | None=None, sector_attr: pd.DataFrame | None=None, monthly_returns: pd.DataFrame | None=None) -> dict[str, Any]`

## `backtesting/attribution.py`

Source SHA-256 : `ce6985e1f6124a2d95071919c52721b0108d40778193460e75eb2af4325c814a`

- [AttributionScenario](../../backtesting/attribution.py) — ligne 44 : `class AttributionScenario`
- [AttributionScenario.fused_score](../../backtesting/attribution.py) — ligne 52 : `def fused_score(self, panel: pd.DataFrame) -> pd.Series`
- [AttributionResult](../../backtesting/attribution.py) — ligne 64 : `class AttributionResult`
- [AttributionResult.to_dict](../../backtesting/attribution.py) — ligne 74 : `def to_dict(self) -> dict`
- [AttributionReport](../../backtesting/attribution.py) — ligne 88 : `class AttributionReport`
- [AttributionReport.to_dict](../../backtesting/attribution.py) — ligne 94 : `def to_dict(self) -> dict`
- [_spearman_ic](../../backtesting/attribution.py) — ligne 114 : `def _spearman_ic(scores: pd.Series, fwd: pd.Series) -> float`
- [evaluate_scenario](../../backtesting/attribution.py) — ligne 126 : `def evaluate_scenario(panel: pd.DataFrame, scenario: AttributionScenario, *, top_n: int=DEFAULT_TOP_N, trading_days: int=DEFAULT_TRADING_DAYS) -> AttributionResult`
- [run_attribution](../../backtesting/attribution.py) — ligne 199 : `def run_attribution(panel: pd.DataFrame, scenarios: Iterable[AttributionScenario]=DEFAULT_SCENARIOS, *, top_n: int=DEFAULT_TOP_N, trading_days: int=DEFAULT_TRADING_DAYS, output_dir: Path | str | None=None, regime_column: str | None='market_regime') -> AttributionReport`

## `backtesting/backfill_scores_history.py`

Source SHA-256 : `fa1cc80f8e6ee9990eb7a494d990fd781fff3583f3f3214b712234d0c401bafe`

- [BackfillScoresHistoryResult](../../backtesting/backfill_scores_history.py) — ligne 126 : `class BackfillScoresHistoryResult`
- [BackfillScoresHistoryService](../../backtesting/backfill_scores_history.py) — ligne 137 : `class BackfillScoresHistoryService`
- [BackfillScoresHistoryService.__init__](../../backtesting/backfill_scores_history.py) — ligne 140 : `def __init__(self, engine: Engine | None=None, screener_config: ScreenerConfig | None=None, scanner_config: AlphaScannerConfig | None=None, sentiment_config: SentimentBoostConfig | None=None, screener_max_workers: int | None=None, capital_preset_key: str=DEFAULT_CAPITAL_PRESET_KEY, config_fingerprint: str | None=None, symbol_source: str | None=default_universe_file_source_or('tradable-universe')) -> None`
- [BackfillScoresHistoryService._coerce_date](../../backtesting/backfill_scores_history.py) — ligne 164 : `def _coerce_date(value: Any) -> date | None`
- [BackfillScoresHistoryService.resolve_end_date](../../backtesting/backfill_scores_history.py) — ligne 178 : `def resolve_end_date(self, start_date: date, explicit_end_date: date | None=None) -> date`
- [BackfillScoresHistoryService.list_trading_dates](../../backtesting/backfill_scores_history.py) — ligne 238 : `def list_trading_dates(self, start_date: date, end_date: date, overwrite_existing: bool=False) -> list[date]`
- [BackfillScoresHistoryService.build_snapshot_for_date](../../backtesting/backfill_scores_history.py) — ligne 287 : `def build_snapshot_for_date(self, as_of_date: date, *, screener_executor: ProcessPoolExecutor | None=None) -> pd.DataFrame`
- [BackfillScoresHistoryService._get_symbol_chunks](../../backtesting/backfill_scores_history.py) — ligne 335 : `def _get_symbol_chunks(self) -> tuple[tuple[str, ...], ...]`
- [BackfillScoresHistoryService._resolve_symbols_from_source](../../backtesting/backfill_scores_history.py) — ligne 345 : `def _resolve_symbols_from_source(self) -> tuple[tuple[str, ...], ...]`
- [BackfillScoresHistoryService._index_prefetched_symbol_frame](../../backtesting/backfill_scores_history.py) — ligne 399 : `def _index_prefetched_symbol_frame(frame: pd.DataFrame) -> pd.DataFrame`
- [BackfillScoresHistoryService._slice_prefetched_symbol_frame](../../backtesting/backfill_scores_history.py) — ligne 408 : `def _slice_prefetched_symbol_frame(frame: pd.DataFrame, symbols: list[str]) -> pd.DataFrame`
- [BackfillScoresHistoryService._create_screener_executor](../../backtesting/backfill_scores_history.py) — ligne 419 : `def _create_screener_executor(self) -> ProcessPoolExecutor`
- [BackfillScoresHistoryService._shutdown_screener_executor](../../backtesting/backfill_scores_history.py) — ligne 424 : `def _shutdown_screener_executor(self, executor: ProcessPoolExecutor | None) -> None`
- [BackfillScoresHistoryService._compute_screener_snapshot](../../backtesting/backfill_scores_history.py) — ligne 430 : `def _compute_screener_snapshot(self, as_of_date: date, *, screener_executor: ProcessPoolExecutor | None=None) -> pd.DataFrame`
- [BackfillScoresHistoryService._compute_selector_snapshot](../../backtesting/backfill_scores_history.py) — ligne 492 : `def _compute_selector_snapshot(self, screener_df: pd.DataFrame, as_of_date: date) -> pd.DataFrame`
- [BackfillScoresHistoryService._enrich_short_score_pit](../../backtesting/backfill_scores_history.py) — ligne 621 : `def _enrich_short_score_pit(self, merged_df: pd.DataFrame, as_of_date: date) -> None`
- [BackfillScoresHistoryService._empty_quote_snapshot_frame](../../backtesting/backfill_scores_history.py) — ligne 644 : `def _empty_quote_snapshot_frame() -> pd.DataFrame`
- [BackfillScoresHistoryService._build_scanner_with_overrides](../../backtesting/backfill_scores_history.py) — ligne 647 : `def _build_scanner_with_overrides(self, *, base_config: AlphaScannerConfig | None=None, **overrides: object) -> AlphaScanner`
- [BackfillScoresHistoryService._is_spread_filter_active](../../backtesting/backfill_scores_history.py) — ligne 656 : `def _is_spread_filter_active(self, scanner: AlphaScanner | object) -> bool`
- [BackfillScoresHistoryService._prepare_pit_quote_snapshots](../../backtesting/backfill_scores_history.py) — ligne 660 : `def _prepare_pit_quote_snapshots(self, symbols: list[str], quotes_df: pd.DataFrame, as_of_date: date) -> tuple[pd.DataFrame, dict[str, object]]`
- [BackfillScoresHistoryService._has_quote_snapshot_coverage](../../backtesting/backfill_scores_history.py) — ligne 761 : `def _has_quote_snapshot_coverage(self, as_of_date: date) -> bool`
- [BackfillScoresHistoryService._has_earnings_calendar_coverage](../../backtesting/backfill_scores_history.py) — ligne 781 : `def _has_earnings_calendar_coverage(self, as_of_date: date) -> bool`
- [BackfillScoresHistoryService._resolve_pit_scanner](../../backtesting/backfill_scores_history.py) — ligne 797 : `def _resolve_pit_scanner(self, as_of_date: date) -> tuple[AlphaScanner, bool, bool]`
- [BackfillScoresHistoryService._load_market_data](../../backtesting/backfill_scores_history.py) — ligne 822 : `def _load_market_data(self, symbols: list[str], as_of_date: date) -> pd.DataFrame`
- [BackfillScoresHistoryService._enrich_with_sma](../../backtesting/backfill_scores_history.py) — ligne 852 : `def _enrich_with_sma(self, selector_df: pd.DataFrame, as_of_date: date) -> pd.DataFrame`
- [BackfillScoresHistoryService._to_history_snapshot](../../backtesting/backfill_scores_history.py) — ligne 915 : `def _to_history_snapshot(self, enriched_df: pd.DataFrame, snapshot_date: date) -> pd.DataFrame`
- [BackfillScoresHistoryService._empty_history_frame](../../backtesting/backfill_scores_history.py) — ligne 1000 : `def _empty_history_frame(self) -> pd.DataFrame`
- [BackfillScoresHistoryService.backfill_universe_only](../../backtesting/backfill_scores_history.py) — ligne 1011 : `def backfill_universe_only(self, start_date: date, end_date: date | None=None, overwrite_existing: bool=False, limit_days: int | None=None) -> BackfillScoresHistoryResult`
- [BackfillScoresHistoryService._persist_universe_from_history](../../backtesting/backfill_scores_history.py) — ligne 1096 : `def _persist_universe_from_history(self, snapshot_date: date, overwrite_existing: bool=False) -> tuple[int, int]`
- [BackfillScoresHistoryService._persist_universe_members](../../backtesting/backfill_scores_history.py) — ligne 1144 : `def _persist_universe_members(self, snapshot_date: date, members: list[UniverseMember]) -> tuple[int, int]`
- [BackfillScoresHistoryService._build_universe_members_from_snapshot](../../backtesting/backfill_scores_history.py) — ligne 1202 : `def _build_universe_members_from_snapshot(self, snapshot_df: pd.DataFrame) -> list[UniverseMember]`
- [BackfillScoresHistoryService._persist_universe_snapshot](../../backtesting/backfill_scores_history.py) — ligne 1226 : `def _persist_universe_snapshot(self, snapshot_df: pd.DataFrame) -> tuple[int, int]`
- [BackfillScoresHistoryService.persist_snapshot](../../backtesting/backfill_scores_history.py) — ligne 1246 : `def persist_snapshot(self, snapshot_df: pd.DataFrame, overwrite_existing: bool=False) -> int`
- [BackfillScoresHistoryService.backfill](../../backtesting/backfill_scores_history.py) — ligne 1327 : `def backfill(self, start_date: date, end_date: date | None=None, overwrite_existing: bool=False, limit_days: int | None=None) -> BackfillScoresHistoryResult`
- [BackfillScoresHistoryService._resolve_screener_workers](../../backtesting/backfill_scores_history.py) — ligne 1413 : `def _resolve_screener_workers(self) -> int`
- [BackfillScoresHistoryService._append_completed_results](../../backtesting/backfill_scores_history.py) — ligne 1419 : `def _append_completed_results(done, all_results: list[pd.DataFrame]) -> None`

## `backtesting/brinson_fachler.py`

Source SHA-256 : `3112669aaa010181d18058425e5ab56083f9e6661baf89886de72c3fbbe89bd6`

- [SectorBucket](../../backtesting/brinson_fachler.py) — ligne 24 : `class SectorBucket`
- [SectorAttribution](../../backtesting/brinson_fachler.py) — ligne 33 : `class SectorAttribution`
- [SectorAttribution.total](../../backtesting/brinson_fachler.py) — ligne 40 : `def total(self) -> float`
- [BrinsonFachlerResult](../../backtesting/brinson_fachler.py) — ligne 45 : `class BrinsonFachlerResult`
- [BrinsonFachlerResult.total_active_return](../../backtesting/brinson_fachler.py) — ligne 54 : `def total_active_return(self) -> float`
- [compute_brinson_fachler](../../backtesting/brinson_fachler.py) — ligne 58 : `def compute_brinson_fachler(buckets: list[SectorBucket]) -> BrinsonFachlerResult`

## `backtesting/cache.py`

Source SHA-256 : `f08b920e946c39a1b529538cab8d5214a38cee215dcc5ae73900e9e2185f65b3`

- [ParquetCache](../../backtesting/cache.py) — ligne 29 : `class ParquetCache`
- [ParquetCache.__init__](../../backtesting/cache.py) — ligne 32 : `def __init__(self, cache_dir: Path | str=DEFAULT_CACHE_DIR, enabled: bool=True) -> None`
- [ParquetCache._hash_key](../../backtesting/cache.py) — ligne 39 : `def _hash_key(key: str) -> str`
- [ParquetCache.path_for](../../backtesting/cache.py) — ligne 42 : `def path_for(self, key: str) -> Path`
- [ParquetCache.get](../../backtesting/cache.py) — ligne 45 : `def get(self, key: str) -> pd.DataFrame | None`
- [ParquetCache.put](../../backtesting/cache.py) — ligne 59 : `def put(self, key: str, df: pd.DataFrame) -> None`
- [ParquetCache.get_or_load](../../backtesting/cache.py) — ligne 69 : `def get_or_load(self, key: str, loader: Callable[[], pd.DataFrame]) -> pd.DataFrame`
- [ParquetCache.invalidate](../../backtesting/cache.py) — ligne 81 : `def invalidate(self, key: str | None=None) -> int`
- [_safe_filename](../../backtesting/cache.py) — ligne 99 : `def _safe_filename(s: str) -> str`

## `backtesting/cli/__init__.py`

Source SHA-256 : `0b0c4be6dc767d15046ac2487badce7c27e30d69176767517486bce4be7de6b2`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `backtesting/cli/_impl.py`

Source SHA-256 : `47ec880828a0bb083c484ae28c22e56347ac673988a043ade9d32c320a67fdd1`

- [_resolve_phase2_ohlcv_history_start](../../backtesting/cli/_impl.py) — ligne 38 : `def _resolve_phase2_ohlcv_history_start(start_date: date, *, atr_window: int, correlation_lookback_days: int) -> date`
- [_safe_print](../../backtesting/cli/_impl.py) — ligne 57 : `def _safe_print(*values: object, sep: str=' ', end: str='\n') -> None`
- [_coerce_date_value](../../backtesting/cli/_impl.py) — ligne 68 : `def _coerce_date_value(value: object) -> date | None`
- [_apply_idio_gate](../../backtesting/cli/_impl.py) — ligne 82 : `def _apply_idio_gate(engine, preds_df, gate: str, seed: int, *, start_date, end_date)`
- [_load_batch_training_universe_scope](../../backtesting/cli/_impl.py) — ligne 194 : `def _load_batch_training_universe_scope(engine: object, batch_id: str | None, trade_dates, *, artifacts_dir: Path | None=None) -> pd.DataFrame | None`
- [_parse_sector_multipliers_json](../../backtesting/cli/_impl.py) — ligne 303 : `def _parse_sector_multipliers_json(raw: str | None) -> dict[str, float] | None`
- [_load_sector_map_for_sizing](../../backtesting/cli/_impl.py) — ligne 323 : `def _load_sector_map_for_sizing(engine: object) -> dict[str, str]`
- [_load_benchmark_close](../../backtesting/cli/_impl.py) — ligne 334 : `def _load_benchmark_close(engine: object, start_date: date, end_date: date, *, benchmark_symbol: str='SPY', warmup_days: int=400) -> pd.Series | None`
- [_run_bars_source_preflight_or_skip](../../backtesting/cli/_impl.py) — ligne 381 : `def _run_bars_source_preflight_or_skip(engine: object, start_date: date, end_date: date) -> dict[str, object]`
- [_extract_symbols_for_log](../../backtesting/cli/_impl.py) — ligne 412 : `def _extract_symbols_for_log(symbols: object) -> list[str]`
- [_format_symbol_preview](../../backtesting/cli/_impl.py) — ligne 426 : `def _format_symbol_preview(symbols: list[str], *, limit: int=20) -> str`
- [_emit_backtest_missing_coverage_logs](../../backtesting/cli/_impl.py) — ligne 435 : `def _emit_backtest_missing_coverage_logs(*, sentiment_mode: str, sentiment_diagnostics: object | None, ml_mode: str, ml_diagnostics: object | None) -> None`
- [_build_execution_broker_like_summary](../../backtesting/cli/_impl.py) — ligne 479 : `def _build_execution_broker_like_summary(*, signals_df, phase2_mode: str, phase3_mode: str, phase4_mode: str, phase5_mode: str, phase7_mode: str, phase3_execution_replay_result, phase4_protection_replay_result, phase5_watcher_replay_result, phase7_exit_lifecycle_result)`
- [_build_backtest_component_details](../../backtesting/cli/_impl.py) — ligne 542 : `def _build_backtest_component_details(*, ohlcv_df, bars_source_preflight: dict[str, object] | None=None, execution_pivoted, start_date: date, end_date: date, ohlcv_start: date, signals_df, phase2_mode: str, phase3_mode: str, phase4_mode: str, phase5_mode: str, phase7_mode: str, phase2_risk_result, phase2_execution_result, phase3_execution_replay_result, phase4_protection_replay_result, phase5_watcher_replay_result, phase7_exit_lifecycle_result) -> tuple[dict[str, dict[str, object]], dict[str, object] | None]`
- [_build_backtest_common_params](../../backtesting/cli/_impl.py) — ligne 647 : `def _build_backtest_common_params(*, args: argparse.Namespace, fees_pct: float, effective_preset, preset_source: str, preset_fingerprint: str, engine_mode: str, phase2_mode: str, phase3_mode: str, phase4_mode: str, phase5_mode: str, phase7_mode: str, ml_pit_strategy: str, dividends_received: float, trading_constraints, bt_config, microstructure_cfg, risk_overlay_cfg, phase2_risk_result, phase2_execution_result, phase3_execution_replay_result, phase4_protection_replay_result, phase5_watcher_replay_result, phase7_exit_lifecycle_result, ml_coverage_gate: dict[str, object] | None=None) -> dict[str, object]`
- [_collect_compare_to_live_trade_dates](../../backtesting/cli/_impl.py) — ligne 821 : `def _collect_compare_to_live_trade_dates(*, scores_df, research_signals_df, phase2_risk_result, phase2_execution_result)`
- [_build_compare_to_live_artifacts](../../backtesting/cli/_impl.py) — ligne 851 : `def _build_compare_to_live_artifacts(*, engine, output_dir: Path, fidelity_manifest: dict[str, object], scores_df, research_signals_df, phase2_risk_result, phase2_execution_result, phase7_exit_lifecycle_result, phase2_mode: str) -> tuple[dict[str, str], dict[str, object] | None]`
- [_build_parser](../../backtesting/cli/_impl.py) — ligne 1005 : `def _build_parser() -> argparse.ArgumentParser`
- [_explicit_flags](../../backtesting/cli/_impl.py) — ligne 2270 : `def _explicit_flags(argv: list[str]) -> set[str]`
- [_infer_programmatic_explicit_flags](../../backtesting/cli/_impl.py) — ligne 2327 : `def _infer_programmatic_explicit_flags(args: argparse.Namespace, *, argv: list[str]) -> set[str]`
- [_run_statistical_validation](../../backtesting/cli/_impl.py) — ligne 2366 : `def _run_statistical_validation(args: argparse.Namespace, pf: object, *, fees_pct: float, output_dir: 'Path | None') -> None`
- [_resolve_pipeline_preset_float](../../backtesting/cli/_impl.py) — ligne 2499 : `def _resolve_pipeline_preset_float(preset, *keys: str, default: float | None=None) -> float | None`
- [_apply_pipeline_defensive_defaults_from_preset](../../backtesting/cli/_impl.py) — ligne 2509 : `def _apply_pipeline_defensive_defaults_from_preset(args: argparse.Namespace, *, effective_preset, engine_mode: str, explicit_flags: set[str]) -> None`
- [_enforce_ml_coverage_gate](../../backtesting/cli/_impl.py) — ligne 2686 : `def _enforce_ml_coverage_gate(*, engine_mode: str, ml_mode: str, ml_diagnostics, min_ml_coverage_ratio: float | None, skip_ml_coverage: bool=False) -> dict[str, object]`
- [_risk_tp_overrides](../../backtesting/cli/_impl.py) — ligne 2740 : `def _risk_tp_overrides(args: argparse.Namespace) -> dict`
- [_run_backtest](../../backtesting/cli/_impl.py) — ligne 2777 : `def _run_backtest(args: argparse.Namespace) -> None`
- [_run_backfill_scores_history](../../backtesting/cli/_impl.py) — ligne 4955 : `def _run_backfill_scores_history(args: argparse.Namespace) -> None`
- [_parse_csv_values](../../backtesting/cli/_impl.py) — ligne 5068 : `def _parse_csv_values(raw: str, *, cast_type)`
- [_run_screener_diagnostics](../../backtesting/cli/_impl.py) — ligne 5077 : `def _run_screener_diagnostics(args: argparse.Namespace) -> None`
- [_run_screener_recommendation](../../backtesting/cli/_impl.py) — ligne 5387 : `def _run_screener_recommendation(args: argparse.Namespace) -> None`
- [_run_calibrate_sentiment_weights](../../backtesting/cli/_impl.py) — ligne 5597 : `def _run_calibrate_sentiment_weights(args: argparse.Namespace) -> None`
- [_run_calibrate_conviction_weights](../../backtesting/cli/_impl.py) — ligne 5654 : `def _run_calibrate_conviction_weights(args: argparse.Namespace) -> None`
- [_run_walk_forward_conviction](../../backtesting/cli/_impl.py) — ligne 5714 : `def _run_walk_forward_conviction(args: argparse.Namespace) -> None`
- [_run_walk_forward_sentiment](../../backtesting/cli/_impl.py) — ligne 5788 : `def _run_walk_forward_sentiment(args: argparse.Namespace) -> None`
- [_run_walk_forward_financial](../../backtesting/cli/_impl.py) — ligne 5873 : `def _run_walk_forward_financial(args: argparse.Namespace) -> None`
- [main](../../backtesting/cli/_impl.py) — ligne 6031 : `def main() -> None`

## `backtesting/cli/backfill.py`

Source SHA-256 : `f09119f5e5dac4ddd6837e848c032118416829a860d22ebb0b56b2e9d085ae53`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `backtesting/cli/calibrate.py`

Source SHA-256 : `87c4e3db4584702352bdb6de0cfc8541010277c6f7410b2faa9451564e66a1b2`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `backtesting/cli/diagnose.py`

Source SHA-256 : `3dfc051aa8dbdb8abee28029f94eb8454df4d25a4955784f4a996855c0048007`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `backtesting/cli/recommend.py`

Source SHA-256 : `ddb8fe51784f75bd9a4832d5ca6367dfc61ff16c4d45cac50d9d4419db0da011`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `backtesting/cli/run.py`

Source SHA-256 : `125cdf77d102c283fc82648dff937c7028c1d5ef13344a1082af7a1dc9ece49a`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `backtesting/cli/walk_forward.py`

Source SHA-256 : `ee3294c2f5e340dd63da7b089e63783860205b3c33198f1b9ebb2074b515bdab`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `backtesting/data_loader.py`

Source SHA-256 : `604c8a21a23250aa241e23b406ebe8854bc4faaae279b61f7a2e757cc2013018`

- [load_tradable_universe_asof](../../backtesting/data_loader.py) — ligne 28 : `def load_tradable_universe_asof(engine: Engine, trade_date: date, capital_preset_key: str=DEFAULT_CAPITAL_PRESET_KEY, *, tradable_only: bool=True) -> UniverseResolution`
- [load_tradable_universe_scope](../../backtesting/data_loader.py) — ligne 44 : `def load_tradable_universe_scope(engine: Engine, trade_dates: Iterable[object], capital_preset_key: str=DEFAULT_CAPITAL_PRESET_KEY) -> pd.DataFrame`
- [_build_table_access_error](../../backtesting/data_loader.py) — ligne 72 : `def _build_table_access_error(table_name: str, exc: Exception) -> RuntimeError`
- [_table_exists](../../backtesting/data_loader.py) — ligne 81 : `def _table_exists(engine: Engine, table_name: str) -> bool`
- [_get_table_columns](../../backtesting/data_loader.py) — ligne 90 : `def _get_table_columns(engine: Engine, table_name: str, *, required: bool=False) -> set[str]`
- [get_required_bars_source_filter](../../backtesting/data_loader.py) — ligne 101 : `def get_required_bars_source_filter(engine: Engine, *, table_name: str='stock_bars_daily', table_alias: str | None=None) -> tuple[str, dict[str, str]]`
- [_resolve_bars_date_column](../../backtesting/data_loader.py) — ligne 124 : `def _resolve_bars_date_column(columns: set[str], table_name: str) -> str`
- [preflight_required_bars_data_source](../../backtesting/data_loader.py) — ligne 133 : `def preflight_required_bars_data_source(engine: Engine, start: date, end: date, *, table_name: str='stock_bars_daily') -> dict[str, Any]`
- [load_ohlcv](../../backtesting/data_loader.py) — ligne 214 : `def load_ohlcv(engine: Engine, start: date, end: date) -> pd.DataFrame`
- [load_spreads](../../backtesting/data_loader.py) — ligne 258 : `def load_spreads(engine: Engine, start: date, end: date, *, table_name: str='stock_quote_snapshots', fallback_spread_bps: float=5.0) -> pd.DataFrame`
- [load_scores](../../backtesting/data_loader.py) — ligne 337 : `def load_scores(engine: Engine, start: date, end: date, capital_preset_key: str | None=None, *, scores_pit_mode: str='exact', strict_pit: bool=False, return_diagnostics: bool=False) -> Any`
- [load_sentiment](../../backtesting/data_loader.py) — ligne 578 : `def load_sentiment(engine: Engine, start: date, end: date, lookback_days: int=365) -> pd.DataFrame`
- [load_predictions](../../backtesting/data_loader.py) — ligne 620 : `def load_predictions(engine: Engine, start: date, end: date, *, symbols: list[str] | None=None, batch_id: str | None=None, sources: list[str] | None=None) -> pd.DataFrame`
- [pivot_ohlcv](../../backtesting/data_loader.py) — ligne 772 : `def pivot_ohlcv(df: pd.DataFrame) -> dict[str, pd.DataFrame]`

## `backtesting/execution_bridge.py`

Source SHA-256 : `2065435cdcbb07a7da33eb1e9a752ff0dde29883b771af276e84974c3b6f1d7b`

- [ExecutionBridgeResult](../../backtesting/execution_bridge.py) — ligne 21 : `class ExecutionBridgeResult`
- [portfolio_entries_to_execution_targets](../../backtesting/execution_bridge.py) — ligne 30 : `def portfolio_entries_to_execution_targets(entries: list[PortfolioEntry], *, risk_run_id: str, trade_date) -> list[ExecutionTarget]`
- [simulate_phase2_execution](../../backtesting/execution_bridge.py) — ligne 74 : `def simulate_phase2_execution(entries: list[PortfolioEntry], *, execution_config: ExecutionConfig, trade_date, risk_run_id: str, exec_run_id: str | None=None) -> ExecutionBridgeResult`
- [_dataclasses_to_frame](../../backtesting/execution_bridge.py) — ligne 132 : `def _dataclasses_to_frame(items: list[object]) -> pd.DataFrame`
- [save_phase2_execution_artifacts](../../backtesting/execution_bridge.py) — ligne 138 : `def save_phase2_execution_artifacts(result: ExecutionBridgeResult, output_dir: Path) -> dict[str, str]`

## `backtesting/execution_broker_like.py`

Source SHA-256 : `dbde869eb34adba50eb5522b820db51dabf601fef18eb31c6bccc633ce43e24c`

- [ensure_order_lifecycle_frame](../../backtesting/execution_broker_like.py) — ligne 78 : `def ensure_order_lifecycle_frame(frame: pd.DataFrame | None) -> pd.DataFrame`
- [ensure_broker_event_frame](../../backtesting/execution_broker_like.py) — ligne 88 : `def ensure_broker_event_frame(frame: pd.DataFrame | None) -> pd.DataFrame`
- [concat_order_lifecycle_frames](../../backtesting/execution_broker_like.py) — ligne 98 : `def concat_order_lifecycle_frames(*frames: pd.DataFrame | None) -> pd.DataFrame`
- [concat_broker_event_frames](../../backtesting/execution_broker_like.py) — ligne 108 : `def concat_broker_event_frames(*frames: pd.DataFrame | None) -> pd.DataFrame`
- [_string_count_map](../../backtesting/execution_broker_like.py) — ligne 118 : `def _string_count_map(series: pd.Series | None) -> dict[str, int]`
- [_session_key_from_row](../../backtesting/execution_broker_like.py) — ligne 128 : `def _session_key_from_row(row: Mapping[str, Any]) -> str | None`
- [_count_true](../../backtesting/execution_broker_like.py) — ligne 140 : `def _count_true(series: pd.Series | None) -> int`
- [_count_event_type](../../backtesting/execution_broker_like.py) — ligne 147 : `def _count_event_type(frame: pd.DataFrame, event_type: str) -> int`
- [build_execution_broker_like_summary](../../backtesting/execution_broker_like.py) — ligne 151 : `def build_execution_broker_like_summary(*, signals_df: pd.DataFrame | None, order_lifecycle_frame: pd.DataFrame | None, broker_event_frame: pd.DataFrame | None, phase_modes: Mapping[str, Any] | None=None, diagnostics: Mapping[str, Mapping[str, Any] | Mapping[str, object] | Any] | None=None) -> dict[str, Any]`
- [save_execution_broker_like_artifacts](../../backtesting/execution_broker_like.py) — ligne 301 : `def save_execution_broker_like_artifacts(*, signals_df: pd.DataFrame | None, order_lifecycle_frame: pd.DataFrame | None, broker_event_frame: pd.DataFrame | None, output_dir: Path, phase_modes: Mapping[str, Any] | None=None, diagnostics: Mapping[str, Mapping[str, Any] | Mapping[str, object] | Any] | None=None) -> dict[str, str]`

## `backtesting/execution_lifecycle_replay.py`

Source SHA-256 : `c70476e3ed97084e95b3f36200bbea6b4022f1b0dcad9118ce60d38b20e4cee6`

- [ProtectionReplayResult](../../backtesting/execution_lifecycle_replay.py) — ligne 22 : `class ProtectionReplayResult`
- [_child_intents_by_parent](../../backtesting/execution_lifecycle_replay.py) — ligne 30 : `def _child_intents_by_parent(child_intents: list[OrderIntent]) -> dict[str, list[OrderIntent]]`
- [_aggregate_entry_fills_by_intent](../../backtesting/execution_lifecycle_replay.py) — ligne 40 : `def _aggregate_entry_fills_by_intent(execution_replay_result: ExecutionReplayResult) -> dict[str, dict[str, object]]`
- [build_phase4_protection_replay](../../backtesting/execution_lifecycle_replay.py) — ligne 62 : `def build_phase4_protection_replay(execution_replay_result: ExecutionReplayResult, *, execution_config: ExecutionConfig) -> ProtectionReplayResult`
- [save_phase4_protection_replay_artifacts](../../backtesting/execution_lifecycle_replay.py) — ligne 313 : `def save_phase4_protection_replay_artifacts(result: ProtectionReplayResult, output_dir: Path) -> dict[str, str]`

## `backtesting/execution_replay.py`

Source SHA-256 : `ed65ce4a9bc3c795c611e13cfbe25f4e064b715bfa88cae01165078e1c9685b1`

- [ExecutionReplayResult](../../backtesting/execution_replay.py) — ligne 40 : `class ExecutionReplayResult`
- [_SyntheticFillAttempt](../../backtesting/execution_replay.py) — ligne 49 : `class _SyntheticFillAttempt`
- [_resolve_execution_day](../../backtesting/execution_replay.py) — ligne 73 : `def _resolve_execution_day(snapshot_date: datetime | pd.Timestamp | object, trading_days: pd.DatetimeIndex) -> pd.Timestamp | None`
- [_entry_to_target](../../backtesting/execution_replay.py) — ligne 83 : `def _entry_to_target(entry: PortfolioEntry, *, risk_run_id: str, execution_date: pd.Timestamp, entry_price: float, trailing_stop_pct: float | None=None, trailing_risk_based: bool=False) -> ExecutionTarget`
- [_build_synthetic_fill_attempts](../../backtesting/execution_replay.py) — ligne 130 : `def _build_synthetic_fill_attempts(*, execution_day: pd.Timestamp, target_qty: float, symbol: str='') -> list[_SyntheticFillAttempt]`
- [_execution_fills_from_attempts](../../backtesting/execution_replay.py) — ligne 312 : `def _execution_fills_from_attempts(*, intent: OrderIntent, symbol: str, fill_price: float, attempt_plan: list[_SyntheticFillAttempt]) -> list[ExecutionFill]`
- [_weighted_average_fill_price](../../backtesting/execution_replay.py) — ligne 347 : `def _weighted_average_fill_price(fills: list[ExecutionFill]) -> float`
- [_event_type_for_attempt_terminal_state](../../backtesting/execution_replay.py) — ligne 355 : `def _event_type_for_attempt_terminal_state(attempt: _SyntheticFillAttempt) -> str`
- [simulate_phase3_execution_replay](../../backtesting/execution_replay.py) — ligne 365 : `def simulate_phase3_execution_replay(entries: list[PortfolioEntry], *, execution_config: ExecutionConfig, open_df: pd.DataFrame, risk_run_id_prefix: str, exec_run_id: str | None=None, regime_trailing_map: dict | None=None, enforce_live_gap_filter: bool=False) -> ExecutionReplayResult`
- [save_phase3_execution_replay_artifacts](../../backtesting/execution_replay.py) — ligne 884 : `def save_phase3_execution_replay_artifacts(result: ExecutionReplayResult, output_dir: Path) -> dict[str, str]`

## `backtesting/exit_lifecycle_replay.py`

Source SHA-256 : `370cc7e0a6cd5bca7de57dc8b97ec78703ab4221f76b136e02288b6225601506`

- [ExitLifecycleReplayResult](../../backtesting/exit_lifecycle_replay.py) — ligne 23 : `class ExitLifecycleReplayResult`
- [_map_exit_reason_to_intent_role](../../backtesting/exit_lifecycle_replay.py) — ligne 33 : `def _map_exit_reason_to_intent_role(exit_reason: str) -> str`
- [build_phase7_exit_lifecycle_replay](../../backtesting/exit_lifecycle_replay.py) — ligne 44 : `def build_phase7_exit_lifecycle_replay(watcher_replay_result: ProtectionWatcherReplayResult, *, high_df: pd.DataFrame, low_df: pd.DataFrame, intrabar_priority: str='conservative', swing_only: bool=False, take_profit_enabled: bool=True, trailing_enabled: bool=True) -> ExitLifecycleReplayResult`
- [save_phase7_exit_lifecycle_replay_artifacts](../../backtesting/exit_lifecycle_replay.py) — ligne 387 : `def save_phase7_exit_lifecycle_replay_artifacts(result: ExitLifecycleReplayResult, output_dir: Path) -> dict[str, str]`

## `backtesting/fidelity.py`

Source SHA-256 : `afba96bf889b1d4d18160ce4cd6d0046d2143fc84b83464eae60a2a39a63f320`

- [_normalize_reason](../../backtesting/fidelity.py) — ligne 101 : `def _normalize_reason(reason: object) -> str`
- [_normalize_reason_list](../../backtesting/fidelity.py) — ligne 106 : `def _normalize_reason_list(reasons: object) -> list[str]`
- [_reason_details](../../backtesting/fidelity.py) — ligne 120 : `def _reason_details(reasons: Sequence[str]) -> list[dict[str, str]]`
- [_normalize_symbols](../../backtesting/fidelity.py) — ligne 147 : `def _normalize_symbols(symbols: object) -> list[str]`
- [_safe_int](../../backtesting/fidelity.py) — ligne 161 : `def _safe_int(value: object, default: int=0) -> int`
- [_safe_float](../../backtesting/fidelity.py) — ligne 168 : `def _safe_float(value: object, default: float=0.0) -> float`
- [_coverage_payload](../../backtesting/fidelity.py) — ligne 175 : `def _coverage_payload(*, rows_input: object, rows_missing_before: object, rows_missing_after: object, missing_symbols_before: object, missing_symbols_after: object) -> dict[str, object]`
- [_component_status_payload](../../backtesting/fidelity.py) — ligne 207 : `def _component_status_payload(component: str, *, enabled: bool, degraded_reasons: Sequence[str], details: Mapping[str, Any] | None=None) -> dict[str, object]`
- [_extract_component_reasons](../../backtesting/fidelity.py) — ligne 231 : `def _extract_component_reasons(component: str, reasons: Sequence[str]) -> list[str]`
- [_normalize_string_list](../../backtesting/fidelity.py) — ligne 242 : `def _normalize_string_list(values: object) -> list[str]`
- [_normalize_symbol_cause_mapping](../../backtesting/fidelity.py) — ligne 256 : `def _normalize_symbol_cause_mapping(value: object) -> dict[str, list[str]]`
- [_normalize_count_mapping](../../backtesting/fidelity.py) — ligne 270 : `def _normalize_count_mapping(value: object) -> dict[str, int]`
- [_normalize_trade_date_series](../../backtesting/fidelity.py) — ligne 282 : `def _normalize_trade_date_series(frame: pd.DataFrame) -> pd.Series`
- [_normalize_timestamp_value](../../backtesting/fidelity.py) — ligne 288 : `def _normalize_timestamp_value(value: object) -> pd.Timestamp`
- [_infer_score_source_counts](../../backtesting/fidelity.py) — ligne 298 : `def _infer_score_source_counts(scores_day: pd.DataFrame) -> dict[str, int]`
- [_sorted_unique_symbols](../../backtesting/fidelity.py) — ligne 319 : `def _sorted_unique_symbols(frame: pd.DataFrame, *, mask: pd.Series | None=None) -> list[str]`
- [_sorted_unique_values](../../backtesting/fidelity.py) — ligne 328 : `def _sorted_unique_values(frame: pd.DataFrame, column: str) -> list[str]`
- [_status_from_flag](../../backtesting/fidelity.py) — ligne 334 : `def _status_from_flag(degraded: bool) -> str`
- [_extract_run_level_ref](../../backtesting/fidelity.py) — ligne 338 : `def _extract_run_level_ref(component_details: Mapping[str, Any], *paths: tuple[str, ...]) -> str | None`
- [_build_session_scores_snapshot_id](../../backtesting/fidelity.py) — ligne 348 : `def _build_session_scores_snapshot_id(*, trade_date: pd.Timestamp, scores_day: pd.DataFrame, scores_provenance: Mapping[str, Any]) -> str`
- [_build_component_attribution](../../backtesting/fidelity.py) — ligne 370 : `def _build_component_attribution(*, score_source_counts: Mapping[str, int], selected_score_source_counts: Mapping[str, int], missing_sentiment_symbols: Sequence[str], missing_ml_symbols: Sequence[str], ml_missing_causes_by_symbol: Mapping[str, Sequence[str]], walk_forward_symbols: Sequence[str], selected_symbols: Sequence[str], signals_day: pd.DataFrame, provenance_refs: Mapping[str, Any], fidelity_manifest: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]`
- [_build_critical_symbol_payload](../../backtesting/fidelity.py) — ligne 435 : `def _build_critical_symbol_payload(*, candidate_symbols: Sequence[str], selected_symbols: Sequence[str], missing_sentiment_symbols: Sequence[str], missing_ml_symbols: Sequence[str], ml_missing_causes_by_symbol: Mapping[str, Sequence[str]], walk_forward_symbols: Sequence[str], score_source_by_symbol: Mapping[str, str]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]`
- [build_replay_diagnostic_summary](../../backtesting/fidelity.py) — ligne 496 : `def build_replay_diagnostic_summary(*, scores_df: pd.DataFrame, predictions_df: pd.DataFrame | None, signals_df: pd.DataFrame | None, fidelity_manifest: Mapping[str, Any]) -> dict[str, Any]`
- [save_replay_diagnostic_summary](../../backtesting/fidelity.py) — ligne 668 : `def save_replay_diagnostic_summary(summary: Mapping[str, Any], output_dir: Path) -> dict[str, Path]`
- [_sorted_session_dates_from_frames](../../backtesting/fidelity.py) — ligne 713 : `def _sorted_session_dates_from_frames(*frames: pd.DataFrame) -> list[pd.Timestamp]`
- [_normalize_research_selected_rows](../../backtesting/fidelity.py) — ligne 722 : `def _normalize_research_selected_rows(research_signals_df: pd.DataFrame) -> pd.DataFrame`
- [_portfolio_entries_to_parity_frame](../../backtesting/fidelity.py) — ligne 732 : `def _portfolio_entries_to_parity_frame(entries: Sequence[object]) -> pd.DataFrame`
- [build_selection_target_parity_summary](../../backtesting/fidelity.py) — ligne 772 : `def build_selection_target_parity_summary(*, research_signals_df: pd.DataFrame, risk_entries: Sequence[object], phase2_mode: str) -> dict[str, Any]`
- [save_selection_target_parity_summary](../../backtesting/fidelity.py) — ligne 877 : `def save_selection_target_parity_summary(summary: Mapping[str, Any], output_dir: Path) -> dict[str, Path]`
- [_normalize_compare_frame](../../backtesting/fidelity.py) — ligne 911 : `def _normalize_compare_frame(frame: pd.DataFrame | None) -> pd.DataFrame`
- [_normalize_live_buy_symbol_set](../../backtesting/fidelity.py) — ligne 920 : `def _normalize_live_buy_symbol_set(frame: pd.DataFrame) -> list[str]`
- [_research_selected_symbols_for_date](../../backtesting/fidelity.py) — ligne 932 : `def _research_selected_symbols_for_date(research_signals_df: pd.DataFrame, trade_date: pd.Timestamp) -> list[str]`
- [_portfolio_entries_to_compare_frame](../../backtesting/fidelity.py) — ligne 946 : `def _portfolio_entries_to_compare_frame(entries: Sequence[object], *, run_id: str | None=None) -> pd.DataFrame`
- [_execution_targets_to_compare_frame](../../backtesting/fidelity.py) — ligne 968 : `def _execution_targets_to_compare_frame(targets: Sequence[object], *, run_id: str | None=None) -> pd.DataFrame`
- [_extract_compare_value](../../backtesting/fidelity.py) — ligne 987 : `def _extract_compare_value(item: object, name: str, default: object=None) -> object`
- [_first_present_text](../../backtesting/fidelity.py) — ligne 993 : `def _first_present_text(series: pd.Series | None) -> str | None`
- [_first_present_float](../../backtesting/fidelity.py) — ligne 1005 : `def _first_present_float(series: pd.Series | None) -> float | None`
- [_aggregate_trade_compare_frame](../../backtesting/fidelity.py) — ligne 1014 : `def _aggregate_trade_compare_frame(frame: pd.DataFrame | None) -> pd.DataFrame`
- [_execution_fills_to_compare_frame](../../backtesting/fidelity.py) — ligne 1088 : `def _execution_fills_to_compare_frame(fills: Sequence[object], *, run_id: str | None=None) -> pd.DataFrame`
- [_exit_signals_to_compare_frame](../../backtesting/fidelity.py) — ligne 1109 : `def _exit_signals_to_compare_frame(signals_df: pd.DataFrame, *, execution_date: pd.Timestamp) -> pd.DataFrame`
- [_position_lots_to_exit_compare_frame](../../backtesting/fidelity.py) — ligne 1136 : `def _position_lots_to_exit_compare_frame(lots_df: pd.DataFrame | None) -> pd.DataFrame`
- [_exit_signals_to_pnl_frame](../../backtesting/fidelity.py) — ligne 1159 : `def _exit_signals_to_pnl_frame(signals_df: pd.DataFrame, *, execution_date: pd.Timestamp) -> pd.DataFrame`
- [_position_lots_to_pnl_frame](../../backtesting/fidelity.py) — ligne 1187 : `def _position_lots_to_pnl_frame(lots_df: pd.DataFrame | None) -> pd.DataFrame`
- [_qty_within_compare_tolerance](../../backtesting/fidelity.py) — ligne 1208 : `def _qty_within_compare_tolerance(live_qty: float, replay_qty: float, *, pct: float=0.05, abs_: float=1.0) -> bool`
- [_status_for_trade_section](../../backtesting/fidelity.py) — ligne 1216 : `def _status_for_trade_section(*, live_available: bool, replay_available: bool, divergent: bool) -> str`
- [_summarize_trade_lifecycle_section](../../backtesting/fidelity.py) — ligne 1226 : `def _summarize_trade_lifecycle_section(*, component: str, live_df: pd.DataFrame, replay_df: pd.DataFrame, live_available: bool, comparison_basis: str | None=None, price_tolerance_bps: float=25.0, compare_reason: bool=False) -> dict[str, object]`
- [_summarize_pnl_section](../../backtesting/fidelity.py) — ligne 1316 : `def _summarize_pnl_section(*, live_df: pd.DataFrame, replay_df: pd.DataFrame, live_available: bool, comparison_basis: str | None=None, pnl_tolerance_abs: float=5.0, pnl_tolerance_pct: float=0.1) -> dict[str, object]`
- [_build_selection_live_compare_section](../../backtesting/fidelity.py) — ligne 1398 : `def _build_selection_live_compare_section(*, research_selected_symbols: Sequence[str], live_selected_symbols: Sequence[str], live_available: bool) -> dict[str, object]`
- [_summarize_parity_section](../../backtesting/fidelity.py) — ligne 1443 : `def _summarize_parity_section(*, component: str, live_df: pd.DataFrame, replay_df: pd.DataFrame, trade_date: pd.Timestamp, account_id: str, live_available: bool, comparison_basis: str | None=None) -> dict[str, object]`
- [_collect_compare_session_dates](../../backtesting/fidelity.py) — ligne 1502 : `def _collect_compare_session_dates(*, fidelity_manifest: Mapping[str, Any], research_signals_df: pd.DataFrame, risk_entries: Sequence[object], live_risk_decisions: Mapping[str, pd.DataFrame], live_portfolio_targets: Mapping[str, Sequence[object]], live_execution_targets: Mapping[str, Sequence[object]]) -> list[pd.Timestamp]`
- [_build_compare_to_live_markdown](../../backtesting/fidelity.py) — ligne 1533 : `def _build_compare_to_live_markdown(summary: Mapping[str, Any]) -> str`
- [build_compare_to_live_summary](../../backtesting/fidelity.py) — ligne 1575 : `def build_compare_to_live_summary(*, fidelity_manifest: Mapping[str, Any], research_signals_df: pd.DataFrame, risk_entries: Sequence[object], execution_targets: Sequence[object], execution_fills: Sequence[object]=(), exit_signals_df: pd.DataFrame | None=None, live_risk_decisions: Mapping[str, pd.DataFrame] | None=None, live_portfolio_targets: Mapping[str, Sequence[object]] | None=None, live_execution_targets: Mapping[str, Sequence[object]] | None=None, live_execution_fills: Mapping[str, pd.DataFrame] | None=None, live_position_lots: Mapping[str, pd.DataFrame] | None=None, live_compare_context: Mapping[str, Mapping[str, Any]] | None=None, account_id: str='default', phase2_mode: str='off') -> dict[str, Any]`
- [save_compare_to_live_summary](../../backtesting/fidelity.py) — ligne 1895 : `def save_compare_to_live_summary(summary: Mapping[str, Any], output_dir: Path) -> dict[str, Path]`
- [_normalize_phase_modes_from_payload](../../backtesting/fidelity.py) — ligne 1939 : `def _normalize_phase_modes_from_payload(*payloads: Mapping[str, Any] | None) -> dict[str, str]`
- [_safe_ratio](../../backtesting/fidelity.py) — ligne 1955 : `def _safe_ratio(numerator: object, denominator: object) -> float`
- [_sanitize_baseline_id](../../backtesting/fidelity.py) — ligne 1962 : `def _sanitize_baseline_id(value: object) -> str | None`
- [build_fidelity_baseline_snapshot](../../backtesting/fidelity.py) — ligne 1967 : `def build_fidelity_baseline_snapshot(*, fidelity_manifest: Mapping[str, Any], replay_diagnostic_summary: Mapping[str, Any] | None=None, selection_target_parity_summary: Mapping[str, Any] | None=None, compare_to_live_summary: Mapping[str, Any] | None=None, execution_broker_like_summary: Mapping[str, Any] | None=None, baseline_id: str | None=None) -> dict[str, Any]`
- [save_fidelity_baseline_snapshot](../../backtesting/fidelity.py) — ligne 2083 : `def save_fidelity_baseline_snapshot(snapshot: Mapping[str, Any], output_dir: Path) -> Path`
- [save_fidelity_baseline_promotion_manifest](../../backtesting/fidelity.py) — ligne 2091 : `def save_fidelity_baseline_promotion_manifest(manifest: Mapping[str, Any], output_dir: Path) -> Path`
- [_load_json_mapping](../../backtesting/fidelity.py) — ligne 2099 : `def _load_json_mapping(path: Path) -> dict[str, Any] | None`
- [_resolve_report_artifacts_dir](../../backtesting/fidelity.py) — ligne 2109 : `def _resolve_report_artifacts_dir(source_report_path: Path | None) -> Path | None`
- [_load_json_artifact_from_report](../../backtesting/fidelity.py) — ligne 2115 : `def _load_json_artifact_from_report(artifacts: Mapping[str, Any], artifact_key: str, *, artifacts_dir: Path | None) -> dict[str, Any] | None`
- [_extract_run_id_from_report_path](../../backtesting/fidelity.py) — ligne 2130 : `def _extract_run_id_from_report_path(source_report_path: Path | None) -> str | None`
- [build_fidelity_baseline_promotion_manifest](../../backtesting/fidelity.py) — ligne 2141 : `def build_fidelity_baseline_promotion_manifest(*, baseline_id: str, snapshot: Mapping[str, Any], source_report: Mapping[str, Any], baseline_dir: Path, label: str | None=None, source_report_path: Path | None=None, source_run_id: str | None=None, promoted_at: str | None=None) -> dict[str, Any]`
- [promote_fidelity_baseline_from_report](../../backtesting/fidelity.py) — ligne 2203 : `def promote_fidelity_baseline_from_report(report_payload: Mapping[str, Any], *, baseline_id: str, destination_root: Path, label: str | None=None, source_report_path: Path | None=None, source_run_id: str | None=None, promoted_at: str | None=None) -> dict[str, Path]`
- [promote_fidelity_baseline_from_report_path](../../backtesting/fidelity.py) — ligne 2278 : `def promote_fidelity_baseline_from_report_path(report_path: Path, *, baseline_id: str, destination_root: Path, label: str | None=None, source_run_id: str | None=None, promoted_at: str | None=None) -> dict[str, Path]`
- [_resolve_baseline_entry](../../backtesting/fidelity.py) — ligne 2302 : `def _resolve_baseline_entry(catalog: Mapping[str, Any], *, baseline_id: str | None, requested_window: Mapping[str, Any]) -> dict[str, Any] | None`
- [_default_baseline_metric_thresholds](../../backtesting/fidelity.py) — ligne 2329 : `def _default_baseline_metric_thresholds() -> dict[str, dict[str, object]]`
- [_normalize_metric_thresholds](../../backtesting/fidelity.py) — ligne 2347 : `def _normalize_metric_thresholds(value: object) -> dict[str, dict[str, object]]`
- [_evaluate_numeric_baseline_check](../../backtesting/fidelity.py) — ligne 2365 : `def _evaluate_numeric_baseline_check(*, metric_name: str, baseline_value: object, current_value: object, rule: Mapping[str, object]) -> dict[str, object]`
- [_evaluate_exact_mapping_check](../../backtesting/fidelity.py) — ligne 2399 : `def _evaluate_exact_mapping_check(*, name: str, label: str, baseline_value: object, current_value: object) -> dict[str, object]`
- [build_fidelity_baseline_comparison](../../backtesting/fidelity.py) — ligne 2419 : `def build_fidelity_baseline_comparison(current_snapshot: Mapping[str, Any], *, catalog_path: Path, baseline_id: str | None=None) -> dict[str, Any]`
- [save_fidelity_baseline_comparison](../../backtesting/fidelity.py) — ligne 2535 : `def save_fidelity_baseline_comparison(comparison: Mapping[str, Any], output_dir: Path) -> dict[str, Path]`
- [_build_scores_provenance](../../backtesting/fidelity.py) — ligne 2567 : `def _build_scores_provenance(score_payload: Mapping[str, Any], *, requested_score_column: str | None) -> dict[str, object]`
- [_build_sentiment_provenance](../../backtesting/fidelity.py) — ligne 2587 : `def _build_sentiment_provenance(sentiment_payload: Mapping[str, Any], *, sentiment_mode: str) -> dict[str, object]`
- [_build_ml_provenance](../../backtesting/fidelity.py) — ligne 2614 : `def _build_ml_provenance(ml_payload: Mapping[str, Any], *, ml_mode: str, ml_pit_strategy: str) -> dict[str, object]`
- [PitHistoryRequiredError](../../backtesting/fidelity.py) — ligne 2645 : `class PitHistoryRequiredError(RuntimeError)`
- [PitMlStrategyUnsupportedError](../../backtesting/fidelity.py) — ligne 2649 : `class PitMlStrategyUnsupportedError(RuntimeError)`
- [resolve_ml_pit_strategy](../../backtesting/fidelity.py) — ligne 2653 : `def resolve_ml_pit_strategy(*, engine_mode: str, ml_mode: str, requested_strategy: str | None) -> str`
- [ScoreLoadDiagnostics](../../backtesting/fidelity.py) — ligne 2669 : `class ScoreLoadDiagnostics`
- [ScoreLoadDiagnostics.strict_pit_satisfied](../../backtesting/fidelity.py) — ligne 2682 : `def strict_pit_satisfied(self) -> bool`
- [ScoreLoadDiagnostics.to_dict](../../backtesting/fidelity.py) — ligne 2685 : `def to_dict(self) -> dict[str, object]`
- [ScoreLoadResult](../../backtesting/fidelity.py) — ligne 2700 : `class ScoreLoadResult`
- [SentimentPreparationDiagnostics](../../backtesting/fidelity.py) — ligne 2708 : `class SentimentPreparationDiagnostics`
- [SentimentPreparationDiagnostics.to_dict](../../backtesting/fidelity.py) — ligne 2725 : `def to_dict(self) -> dict[str, object]`
- [PreparedScoresResult](../../backtesting/fidelity.py) — ligne 2746 : `class PreparedScoresResult`
- [MlPreparationDiagnostics](../../backtesting/fidelity.py) — ligne 2752 : `class MlPreparationDiagnostics`
- [MlPreparationDiagnostics.to_dict](../../backtesting/fidelity.py) — ligne 2771 : `def to_dict(self) -> dict[str, object]`
- [PreparedPredictionsResult](../../backtesting/fidelity.py) — ligne 2797 : `class PreparedPredictionsResult`
- [evaluate_ml_coverage_gate](../../backtesting/fidelity.py) — ligne 2802 : `def evaluate_ml_coverage_gate(*, engine_mode: str, ml_mode: str, ml_diagnostics: MlPreparationDiagnostics | None, min_coverage_ratio: float | None) -> dict[str, object]`
- [build_fidelity_manifest](../../backtesting/fidelity.py) — ligne 2875 : `def build_fidelity_manifest(*, engine_mode: str, start_date: date, end_date: date, capital_preset_key: str | None, score_diagnostics: ScoreLoadDiagnostics | None, sentiment_diagnostics: SentimentPreparationDiagnostics | None, ml_diagnostics: MlPreparationDiagnostics | None, sentiment_mode: str, ml_mode: str, ml_pit_strategy: str, component_details: Mapping[str, Mapping[str, Any]] | None=None, requested_score_column: str | None=None, walk_forward_artifacts_dir: str | None=None) -> dict[str, Any]`
- [save_fidelity_manifest](../../backtesting/fidelity.py) — ligne 3034 : `def save_fidelity_manifest(manifest: dict[str, Any], output_dir: Path) -> Path`
- [build_coverage_summary](../../backtesting/fidelity.py) — ligne 3042 : `def build_coverage_summary(manifest: Mapping[str, Any]) -> dict[str, Any]`
- [save_coverage_summary](../../backtesting/fidelity.py) — ligne 3068 : `def save_coverage_summary(manifest: Mapping[str, Any], output_dir: Path) -> Path`
- [build_fidelity_symbol_matrix](../../backtesting/fidelity.py) — ligne 3077 : `def build_fidelity_symbol_matrix(*, scores_df: pd.DataFrame, predictions_df: pd.DataFrame | None, fidelity_manifest: Mapping[str, Any]) -> dict[str, Any]`
- [save_fidelity_symbol_matrix](../../backtesting/fidelity.py) — ligne 3204 : `def save_fidelity_symbol_matrix(matrix: Mapping[str, Any], output_dir: Path) -> dict[str, Path]`

## `backtesting/fuzz_runner.py`

Source SHA-256 : `4c13d4e1829c1dbfb34374f31a4f088e051de5f941dceb0fb1830c3c9a46a260`

- [FuzzScenario](../../backtesting/fuzz_runner.py) — ligne 42 : `class FuzzScenario`
- [FuzzScenario.to_dict](../../backtesting/fuzz_runner.py) — ligne 52 : `def to_dict(self) -> dict[str, Any]`
- [generate_scenarios](../../backtesting/fuzz_runner.py) — ligne 63 : `def generate_scenarios(n: int, *, master_seed: int=1234) -> list[FuzzScenario]`
- [_ExecResult](../../backtesting/fuzz_runner.py) — ligne 104 : `class _ExecResult`
- [_ExecResult.to_dict](../../backtesting/fuzz_runner.py) — ligne 111 : `def to_dict(self) -> dict[str, Any]`
- [_run_engine](../../backtesting/fuzz_runner.py) — ligne 121 : `def _run_engine(scenario: FuzzScenario, *, is_live: bool, inject_divergence: bool=False) -> _ExecResult`
- [_diff_kind](../../backtesting/fuzz_runner.py) — ligne 205 : `def _diff_kind(live: _ExecResult, replay: _ExecResult, tol: FuzzTolerance) -> str | None`
- [FuzzReport](../../backtesting/fuzz_runner.py) — ligne 226 : `class FuzzReport`
- [FuzzReport.to_dict](../../backtesting/fuzz_runner.py) — ligne 236 : `def to_dict(self) -> dict[str, Any]`
- [run_fuzz_diff](../../backtesting/fuzz_runner.py) — ligne 249 : `def run_fuzz_diff(n_scenarios: int, *, tolerance: FuzzTolerance | None=None, out_dir: Path | str | None=None, master_seed: int=1234, inject_divergence: bool=False, max_divergences_recorded: int=200) -> FuzzReport`

## `backtesting/fuzz_tolerance.py`

Source SHA-256 : `c61b8fa9dd58a17fcd322a4006afb369007c021830fbb27005539f9279ac8a91`

- [FuzzTolerance](../../backtesting/fuzz_tolerance.py) — ligne 14 : `class FuzzTolerance`
- [FuzzTolerance.to_dict](../../backtesting/fuzz_tolerance.py) — ligne 24 : `def to_dict(self) -> dict[str, Any]`
- [FuzzTolerance.from_dict](../../backtesting/fuzz_tolerance.py) — ligne 28 : `def from_dict(cls, data: Mapping[str, Any] | None) -> 'FuzzTolerance'`
- [FuzzTolerance.accepts_price](../../backtesting/fuzz_tolerance.py) — ligne 34 : `def accepts_price(self, live: float, replay: float) -> bool`
- [FuzzTolerance.accepts_qty](../../backtesting/fuzz_tolerance.py) — ligne 37 : `def accepts_qty(self, live: float, replay: float) -> bool`
- [FuzzTolerance.accepts_pnl](../../backtesting/fuzz_tolerance.py) — ligne 40 : `def accepts_pnl(self, live: float, replay: float) -> bool`

## `backtesting/microstructure.py`

Source SHA-256 : `031803bed09cc290f4b7879895cb1eb1316182bb0655261c1529a6c5c7a951c9`

- [ExecutionModelConfig](../../backtesting/microstructure.py) — ligne 33 : `class ExecutionModelConfig`
- [SlippageConfig](../../backtesting/microstructure.py) — ligne 58 : `class SlippageConfig`
- [SlippageConfig.compute_bps](../../backtesting/microstructure.py) — ligne 78 : `def compute_bps(self, size_usd: float, adv_usd: float | None) -> float`
- [compute_adv_usd](../../backtesting/microstructure.py) — ligne 89 : `def compute_adv_usd(close: pd.DataFrame, volume: pd.DataFrame | None, *, window: int=20) -> pd.DataFrame`
- [MicrostructureConfig](../../backtesting/microstructure.py) — ligne 118 : `class MicrostructureConfig`
- [MicrostructureConfig.is_default](../../backtesting/microstructure.py) — ligne 140 : `def is_default(self) -> bool`
- [should_skip_entry_for_gap](../../backtesting/microstructure.py) — ligne 151 : `def should_skip_entry_for_gap(previous_close: float | None, next_open: float, *, max_gap_pct: float) -> bool`
- [IntraBarResolution](../../backtesting/microstructure.py) — ligne 171 : `class IntraBarResolution`
- [resolve_intrabar_exit](../../backtesting/microstructure.py) — ligne 179 : `def resolve_intrabar_exit(*, day_high: float, day_low: float, take_profit_price: float, trailing_stop_price: float, initial_stop_price: float | None, priority: IntraBarPriority, side: str='buy', rng: np.random.Generator | None=None) -> IntraBarResolution`
- [compute_execution_price](../../backtesting/microstructure.py) — ligne 247 : `def compute_execution_price(*, model: ExecutionModelConfig, side: str, open_price: float, high_price: float | None=None, low_price: float | None=None, close_price: float | None=None, adv_usd: float | None=None, notional: float | None=None) -> float`
- [should_split_order](../../backtesting/microstructure.py) — ligne 297 : `def should_split_order(*, model: ExecutionModelConfig, notional_usd: float, adv_usd: float | None) -> bool`

## `backtesting/oracle_portfolio_ledger.py`

Source SHA-256 : `d702df73ce00a86446b5c2186ad19272773354779c47c923598418382e56831d`

- [OraclePortfolioLedger](../../backtesting/oracle_portfolio_ledger.py) — ligne 23 : `class OraclePortfolioLedger(BacktestEngine)`
- [OraclePortfolioLedger.__init__](../../backtesting/oracle_portfolio_ledger.py) — ligne 26 : `def __init__(self, config, *, opens, close, high, low, volume, sector_map)`
- [OraclePortfolioLedger._require_day](../../backtesting/oracle_portfolio_ledger.py) — ligne 56 : `def _require_day(self)`
- [OraclePortfolioLedger._marks](../../backtesting/oracle_portfolio_ledger.py) — ligne 60 : `def _marks(self)`
- [OraclePortfolioLedger.equity](../../backtesting/oracle_portfolio_ledger.py) — ligne 70 : `def equity(self)`
- [OraclePortfolioLedger.begin_day](../../backtesting/oracle_portfolio_ledger.py) — ligne 75 : `def begin_day(self, day)`
- [OraclePortfolioLedger.execute_approved](../../backtesting/oracle_portfolio_ledger.py) — ligne 91 : `def execute_approved(self, entries, *, execution_config)`
- [OraclePortfolioLedger._build_entry_protections](../../backtesting/oracle_portfolio_ledger.py) — ligne 172 : `def _build_entry_protections(self, phase3, *, execution_config)`
- [OraclePortfolioLedger.apply_observed_protections](../../backtesting/oracle_portfolio_ledger.py) — ligne 176 : `def apply_observed_protections(self, *, phase, take_profit_enabled=True, trailing_enabled=True)`
- [OraclePortfolioLedger.equity_unchecked](../../backtesting/oracle_portfolio_ledger.py) — ligne 241 : `def equity_unchecked(self)`
- [OraclePortfolioLedger.close_resolved](../../backtesting/oracle_portfolio_ledger.py) — ligne 246 : `def close_resolved(self, exits, *, phase)`
- [OraclePortfolioLedger.mark_close](../../backtesting/oracle_portfolio_ledger.py) — ligne 316 : `def mark_close(self)`
- [OraclePortfolioLedger.snapshot](../../backtesting/oracle_portfolio_ledger.py) — ligne 327 : `def snapshot(self, *, take_profit_enabled=True, trailing_enabled=True)`
- [OraclePortfolioLedger.finish_day](../../backtesting/oracle_portfolio_ledger.py) — ligne 351 : `def finish_day(self)`
- [OraclePortfolioLedger.reconciliation_error](../../backtesting/oracle_portfolio_ledger.py) — ligne 365 : `def reconciliation_error(self)`

## `backtesting/oracle_portfolio_session.py`

Source SHA-256 : `4cfc21e40a89045fccd20ca41d257b5c3f980afe53cccd7856dfbab1bdbe6d2e`

- [OraclePortfolioSession](../../backtesting/oracle_portfolio_session.py) — ligne 31 : `class OraclePortfolioSession`
- [OraclePortfolioSession.__init__](../../backtesting/oracle_portfolio_session.py) — ligne 34 : `def __init__(self, config: RiskConfig, *, sector_map: dict[str, str], market_regimes_config=None, account_long_only: bool)`
- [OraclePortfolioSession.decide](../../backtesting/oracle_portfolio_session.py) — ligne 55 : `def decide(self, day: date, *, scores: pd.DataFrame, snapshot: OperationalDataSnapshot, regime: MarketRegimeSnapshot, close: pd.DataFrame, high: pd.DataFrame, low: pd.DataFrame, volume: pd.DataFrame | None=None, transition=None, pnl=None, circuit_breaker=None)`
- [OraclePortfolioSession.record_fill](../../backtesting/oracle_portfolio_session.py) — ligne 142 : `def record_fill(self, event_id: str, *, day: date, symbol: str, entry: bool, realized_pnl: float | None=None)`

## `backtesting/parity.py`

Source SHA-256 : `7b69e89873ad1e87a49bbacc885ee43845b746d232b38226e39cb42d6c521c90`

- [ParityRow](../../backtesting/parity.py) — ligne 52 : `class ParityRow`
- [ParityRow.to_dict](../../backtesting/parity.py) — ligne 64 : `def to_dict(self) -> dict[str, Any]`
- [ParityReport](../../backtesting/parity.py) — ligne 69 : `class ParityReport`
- [ParityReport.to_dict](../../backtesting/parity.py) — ligne 84 : `def to_dict(self) -> dict[str, Any]`
- [ParityReport.to_json](../../backtesting/parity.py) — ligne 101 : `def to_json(self, *, indent: int=2) -> str`
- [ParityReport.to_dataframe](../../backtesting/parity.py) — ligne 104 : `def to_dataframe(self) -> pd.DataFrame`
- [_norm_symbol](../../backtesting/parity.py) — ligne 121 : `def _norm_symbol(value: Any) -> Optional[str]`
- [_norm_action](../../backtesting/parity.py) — ligne 128 : `def _norm_action(value: Any) -> Optional[str]`
- [_safe_float](../../backtesting/parity.py) — ligne 135 : `def _safe_float(value: Any, default: float=0.0) -> float`
- [_safe_optional_float](../../backtesting/parity.py) — ligne 147 : `def _safe_optional_float(value: Any) -> Optional[float]`
- [_qty_within_tolerance](../../backtesting/parity.py) — ligne 159 : `def _qty_within_tolerance(live: float, replay: float, *, pct: float, abs_: float) -> bool`
- [_index_by_symbol](../../backtesting/parity.py) — ligne 172 : `def _index_by_symbol(df: pd.DataFrame) -> dict[str, dict[str, Any]]`
- [compare_decisions](../../backtesting/parity.py) — ligne 185 : `def compare_decisions(live_df: pd.DataFrame, replay_df: pd.DataFrame, *, trade_date: str | date | None=None, account_id: str='default', qty_tolerance_pct: float=DEFAULT_QTY_TOLERANCE_PCT, qty_tolerance_abs: float=DEFAULT_QTY_TOLERANCE_ABS) -> ParityReport`
- [compare_risk_layers](../../backtesting/parity.py) — ligne 316 : `def compare_risk_layers(live_ctx: dict | None, replay_ctx: dict | None, *, float_tol: float=1e-06) -> list[dict[str, Any]]`
- [summarize_paper_coverage](../../backtesting/parity.py) — ligne 398 : `def summarize_paper_coverage(contexts: list[dict], *, min_days: int=2) -> dict[str, Any]`
- [write_parity_artifacts](../../backtesting/parity.py) — ligne 457 : `def write_parity_artifacts(report: ParityReport, output_dir: Path | str) -> dict[str, Path]`
- [_build_alert_body](../../backtesting/parity.py) — ligne 478 : `def _build_alert_body(report: ParityReport, threshold: float) -> str`
- [run_daily_parity](../../backtesting/parity.py) — ligne 497 : `def run_daily_parity(trade_date: date, *, live_loader: LiveLoader, replay_loader: ReplayLoader, account_id: str='default', artifacts_dir: Path | str=DEFAULT_ARTIFACTS_DIR, notifier=None, divergence_threshold: float=DEFAULT_DIVERGENCE_THRESHOLD, qty_tolerance_pct: float=DEFAULT_QTY_TOLERANCE_PCT, qty_tolerance_abs: float=DEFAULT_QTY_TOLERANCE_ABS) -> ParityReport`

## `backtesting/prediction_pit.py`

Source SHA-256 : `052aba239faeb105c1236515f9a05179cfa9dd9f4d4038055ee9edb8fe604374`

- [PredictionPitViolationError](../../backtesting/prediction_pit.py) — ligne 9 : `class PredictionPitViolationError(RuntimeError)`
- [PredictionPitAudit](../../backtesting/prediction_pit.py) — ligne 14 : `class PredictionPitAudit`
- [assert_directional_bundle_predictions_pit](../../backtesting/prediction_pit.py) — ligne 19 : `def assert_directional_bundle_predictions_pit(predictions: pd.DataFrame) -> PredictionPitAudit`

## `backtesting/profiles.py`

Source SHA-256 : `46724cf2f21d19f9b6633779e7d69c6ee7b997d703bd5aead85d087146e14ac6`

- [apply_profile](../../backtesting/profiles.py) — ligne 51 : `def apply_profile(args, profile_name: str | None, *, explicit_flags: set[str]) -> None`

## `backtesting/protection_watcher_replay.py`

Source SHA-256 : `8d79ed7e590d3c749eeea839174bca53e9c32bfcb16a0d75f7da77c50ceec7fe`

- [ProtectionWatcherReplayResult](../../backtesting/protection_watcher_replay.py) — ligne 21 : `class ProtectionWatcherReplayResult`
- [_find_trigger_date](../../backtesting/protection_watcher_replay.py) — ligne 30 : `def _find_trigger_date(*, symbol: str, execution_date: pd.Timestamp, trigger_price: float, high_df: pd.DataFrame, low_df: pd.DataFrame, short: bool) -> pd.Timestamp | None`
- [_next_trading_day](../../backtesting/protection_watcher_replay.py) — ligne 59 : `def _next_trading_day(day: pd.Timestamp, trading_days: pd.DatetimeIndex) -> pd.Timestamp | None`
- [build_phase5_watcher_replay](../../backtesting/protection_watcher_replay.py) — ligne 66 : `def build_phase5_watcher_replay(protection_replay_result: ProtectionReplayResult, *, high_df: pd.DataFrame, low_df: pd.DataFrame) -> ProtectionWatcherReplayResult`
- [save_phase5_watcher_replay_artifacts](../../backtesting/protection_watcher_replay.py) — ligne 250 : `def save_phase5_watcher_replay_artifacts(result: ProtectionWatcherReplayResult, output_dir: Path) -> dict[str, str]`

## `backtesting/regime_trailing.py`

Source SHA-256 : `4745cfe3519482028849d6cc28b35d542f9181954343687d46852932fc4fb3cf`

- [compute_regime](../../backtesting/regime_trailing.py) — ligne 34 : `def compute_regime(spy_close: pd.Series) -> pd.Series`
- [trailing_for_regime](../../backtesting/regime_trailing.py) — ligne 52 : `def trailing_for_regime(regime: str | None, policy: str) -> tuple[float | None, bool]`
- [build_regime_trailing_map](../../backtesting/regime_trailing.py) — ligne 66 : `def build_regime_trailing_map(spy_close: pd.Series, policy: str) -> dict[date, tuple[float | None, bool]]`
- [regime_distribution](../../backtesting/regime_trailing.py) — ligne 77 : `def regime_distribution(dates: pd.Series, spy_close: pd.Series) -> pd.Series`

## `backtesting/report.py`

Source SHA-256 : `997297458e1dc1c31bbf47408e539e9c57b9df9c0cd5ebdfb3a8f8f86dbfa6e9`

- [_as_float](../../backtesting/report.py) — ligne 22 : `def _as_float(value) -> float`
- [_as_int](../../backtesting/report.py) — ligne 29 : `def _as_int(value) -> int`
- [_clean_metric](../../backtesting/report.py) — ligne 36 : `def _clean_metric(value: float, default: float=0.0) -> float`
- [_extract_equity_curve](../../backtesting/report.py) — ligne 43 : `def _extract_equity_curve(pf) -> pd.Series`
- [_extract_closed_trades_df](../../backtesting/report.py) — ligne 55 : `def _extract_closed_trades_df(pf) -> Optional[pd.DataFrame]`
- [_extract_trade_events_df](../../backtesting/report.py) — ligne 59 : `def _extract_trade_events_df(pf) -> Optional[pd.DataFrame]`
- [extract_diagnostics](../../backtesting/report.py) — ligne 63 : `def extract_diagnostics(pf) -> dict[str, object]`
- [_normalize_symbol_column](../../backtesting/report.py) — ligne 78 : `def _normalize_symbol_column(df: pd.DataFrame, column_name: str='symbol') -> pd.DataFrame`
- [_normalize_datetime_columns](../../backtesting/report.py) — ligne 85 : `def _normalize_datetime_columns(df: pd.DataFrame, *column_names: str) -> pd.DataFrame`
- [_coalesce_columns](../../backtesting/report.py) — ligne 93 : `def _coalesce_columns(frame: pd.DataFrame, columns: tuple[str, ...], *, default: object=None) -> pd.Series`
- [_with_trade_merge_seq](../../backtesting/report.py) — ligne 103 : `def _with_trade_merge_seq(frame: pd.DataFrame, *, execution_date_col: str) -> pd.DataFrame`
- [_build_legacy_trade_export_frame](../../backtesting/report.py) — ligne 119 : `def _build_legacy_trade_export_frame(pf) -> tuple[pd.DataFrame, str]`
- [_build_pipeline_trade_export_frame](../../backtesting/report.py) — ligne 143 : `def _build_pipeline_trade_export_frame(pipeline_signals_df: pd.DataFrame | None, *, legacy_trades_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]`
- [build_trade_export_bundle](../../backtesting/report.py) — ligne 311 : `def build_trade_export_bundle(pf, *, pipeline_signals_df: pd.DataFrame | None=None, corporate_actions_summary: dict[str, object] | None=None) -> tuple[pd.DataFrame, dict[str, object]]`
- [load_corporate_actions_summary](../../backtesting/report.py) — ligne 349 : `def load_corporate_actions_summary(start_date, end_date, *, account_id: str | None=None, engine=None) -> dict[str, object]`
- [BacktestReport](../../backtesting/report.py) — ligne 402 : `class BacktestReport`
- [BacktestReport.to_serializable_dict](../../backtesting/report.py) — ligne 442 : `def to_serializable_dict(self) -> dict[str, float | int | str]`
- [BacktestReport.to_dict](../../backtesting/report.py) — ligne 486 : `def to_dict(self) -> dict`
- [BacktestReport.print_summary](../../backtesting/report.py) — ligne 519 : `def print_summary(self) -> None`
- [load_dividends_received](../../backtesting/report.py) — ligne 528 : `def load_dividends_received(start_date, end_date, *, account_id: str | None=None, engine=None) -> float`
- [_compute_ulcer_index](../../backtesting/report.py) — ligne 551 : `def _compute_ulcer_index(equity: pd.Series) -> float`
- [_compute_calmar](../../backtesting/report.py) — ligne 563 : `def _compute_calmar(cagr_pct: float, max_dd_pct: float) -> float`
- [generate_report](../../backtesting/report.py) — ligne 575 : `def generate_report(pf, initial_equity: float, *, dividends_received: float=0.0, risk_free_rate: float=0.0, trading_days_per_year: int=252) -> BacktestReport`
- [save_equity_curve](../../backtesting/report.py) — ligne 814 : `def save_equity_curve(pf, output_dir: Path | None=None) -> Path`
- [save_trades_csv](../../backtesting/report.py) — ligne 849 : `def save_trades_csv(pf, output_dir: Path | None=None, *, pipeline_signals_df: pd.DataFrame | None=None, corporate_actions_summary: dict[str, object] | None=None) -> Path`
- [save_pipeline_trade_candidates_csv](../../backtesting/report.py) — ligne 878 : `def save_pipeline_trade_candidates_csv(pf, pipeline_signals_df: pd.DataFrame | None, output_dir: Path | None=None) -> Path | None`
- [save_trade_audit_csv](../../backtesting/report.py) — ligne 907 : `def save_trade_audit_csv(pf, output_dir: Path | None=None) -> Path`
- [save_equity_curve_csv](../../backtesting/report.py) — ligne 926 : `def save_equity_curve_csv(pf, output_dir: Path | None=None) -> Path`
- [save_report_json](../../backtesting/report.py) — ligne 942 : `def save_report_json(report: BacktestReport, output_dir: Path | None=None, *, artifacts: dict[str, str] | None=None, params: dict[str, object] | None=None, diagnostics: dict[str, object] | None=None, run_metadata: dict[str, object] | None=None, fidelity: dict[str, object] | None=None, corporate_actions: dict[str, object] | None=None, trade_export: dict[str, object] | None=None) -> Path`

## `backtesting/report_schema.py`

Source SHA-256 : `c11f87e99922281d999699bf7d1c5769c72db131865a18d86deb07cd81b6ec9b`

- [ReportSchemaError](../../backtesting/report_schema.py) — ligne 30 : `class ReportSchemaError(ValueError)`
- [SummarySchema](../../backtesting/report_schema.py) — ligne 40 : `class SummarySchema`
- [MicrostructureParamsSchema](../../backtesting/report_schema.py) — ligne 68 : `class MicrostructureParamsSchema`
- [RiskOverlayParamsSchema](../../backtesting/report_schema.py) — ligne 81 : `class RiskOverlayParamsSchema`
- [RunMetadataSchema](../../backtesting/report_schema.py) — ligne 100 : `class RunMetadataSchema`
- [DiagnosticsSchema](../../backtesting/report_schema.py) — ligne 112 : `class DiagnosticsSchema`
- [BacktestReportSchema](../../backtesting/report_schema.py) — ligne 128 : `class BacktestReportSchema`
- [_check_type](../../backtesting/report_schema.py) — ligne 157 : `def _check_type(value: Any, expected: tuple[type, ...], path: str) -> None`
- [validate_report_payload](../../backtesting/report_schema.py) — ligne 164 : `def validate_report_payload(payload: dict[str, Any], *, strict: bool=False) -> BacktestReportSchema`

## `backtesting/report_schema_pydantic.py`

Source SHA-256 : `0e219820cbcef67c7aa20b1e47eb53b171d232d85e842360647e16f8d4638a71`

- [_coerce_inf](../../backtesting/report_schema_pydantic.py) — ligne 61 : `def _coerce_inf(value: Any) -> float`
- [PydanticSummary](../../backtesting/report_schema_pydantic.py) — ligne 76 : `class PydanticSummary(BaseModel)`
- [PydanticSummary._accept_inf_sentinel](../../backtesting/report_schema_pydantic.py) — ligne 102 : `def _accept_inf_sentinel(cls, value: Any) -> Any`
- [PydanticRunMetadata](../../backtesting/report_schema_pydantic.py) — ligne 105 : `class PydanticRunMetadata(BaseModel)`
- [PydanticBacktestReport](../../backtesting/report_schema_pydantic.py) — ligne 117 : `class PydanticBacktestReport(BaseModel)`

## `backtesting/resilience.py`

Source SHA-256 : `5756229c8a2f9343a41c80bbcbf77ad4819a02988f71e3f8a9ba937e843a299c`

- [_normalize_dates](../../backtesting/resilience.py) — ligne 35 : `def _normalize_dates(df: pd.DataFrame, date_col: str='trade_date') -> pd.DataFrame`
- [_expected_symbol_dates](../../backtesting/resilience.py) — ligne 43 : `def _expected_symbol_dates(universe_df: pd.DataFrame) -> set[tuple[str, pd.Timestamp]]`
- [_extract_unique_symbols](../../backtesting/resilience.py) — ligne 54 : `def _extract_unique_symbols(frame: pd.DataFrame, *, mask: pd.Series | None=None) -> tuple[str, ...]`
- [_ensure_dataframe](../../backtesting/resilience.py) — ligne 68 : `def _ensure_dataframe(value: object) -> pd.DataFrame`
- [_merge_prediction_frames](../../backtesting/resilience.py) — ligne 78 : `def _merge_prediction_frames(existing: pd.DataFrame, rebuilt: pd.DataFrame) -> pd.DataFrame`
- [_classify_ml_missing_cause_from_runtime_status](../../backtesting/resilience.py) — ligne 85 : `def _classify_ml_missing_cause_from_runtime_status(status: dict[str, object]) -> str`
- [_freeze_missing_causes_by_symbol](../../backtesting/resilience.py) — ligne 109 : `def _freeze_missing_causes_by_symbol(symbol_causes: dict[str, set[str]]) -> dict[str, tuple[str, ...]]`
- [_rebuild_prediction_frame](../../backtesting/resilience.py) — ligne 117 : `def _rebuild_prediction_frame(*, symbol: str, trade_date: date, artifacts_dir: Path, batch_id: str | None, engine: Engine, persist: bool) -> pd.DataFrame`
- [_rebuild_prediction_batch_frame](../../backtesting/resilience.py) — ligne 142 : `def _rebuild_prediction_batch_frame(*, symbols: list[str], trade_date: date, artifacts_dir: Path, batch_id: str | None, engine: Engine, persist: bool) -> pd.DataFrame`
- [_resolve_scores_history_identity](../../backtesting/resilience.py) — ligne 167 : `def _resolve_scores_history_identity(scores_df: pd.DataFrame) -> tuple[str | None, str | None]`
- [prepare_scores_for_sentiment_mode](../../backtesting/resilience.py) — ligne 181 : `def prepare_scores_for_sentiment_mode(engine: Engine, scores_df: pd.DataFrame, *, sentiment_mode: SentimentMode, walk_forward_artifacts_dir: Path | None=None, engine_mode: str='research', return_diagnostics: bool=False) -> object`
- [_apply_walk_forward_overlay](../../backtesting/resilience.py) — ligne 346 : `def _apply_walk_forward_overlay(scores_df: pd.DataFrame, artifacts_dir: Path | None) -> tuple[pd.DataFrame, bool, str | None]`
- [prepare_predictions_for_ml_mode](../../backtesting/resilience.py) — ligne 374 : `def prepare_predictions_for_ml_mode(engine: Engine, universe_df: pd.DataFrame, predictions_df: pd.DataFrame, *, ml_mode: MLMode, artifacts_dir: Path, batch_id: str | None=None, engine_mode: str='research', ml_pit_strategy: str='auto', return_diagnostics: bool=False) -> object`

## `backtesting/risk_bridge.py`

Source SHA-256 : `fdf2c2f8b1146f0793d984911096ae3bae196cc8a826b92ef50870d373eb3475`

- [RiskBridgeResult](../../backtesting/risk_bridge.py) — ligne 58 : `class RiskBridgeResult`
- [_normalize_trade_dates](../../backtesting/risk_bridge.py) — ligne 66 : `def _normalize_trade_dates(df: pd.DataFrame) -> pd.DataFrame`
- [_resolve_float](../../backtesting/risk_bridge.py) — ligne 73 : `def _resolve_float(row: pd.Series, column: str) -> float | None`
- [_prepare_score_columns](../../backtesting/risk_bridge.py) — ligne 80 : `def _prepare_score_columns(scores_df: pd.DataFrame, *, preferred_score_column: str | None=None) -> pd.DataFrame`
- [_build_selection_inputs](../../backtesting/risk_bridge.py) — ligne 93 : `def _build_selection_inputs(scores_df: pd.DataFrame, snapshot_date: date) -> list[SelectionScore]`
- [_build_selection_inputs_from_day](../../backtesting/risk_bridge.py) — ligne 101 : `def _build_selection_inputs_from_day(day_df: pd.DataFrame, snapshot_date: date) -> list[SelectionScore]`
- [_compute_atr_20](../../backtesting/risk_bridge.py) — ligne 153 : `def _compute_atr_20(high_series: pd.Series, low_series: pd.Series, close_series: pd.Series) -> float | None`
- [_build_prices](../../backtesting/risk_bridge.py) — ligne 172 : `def _build_prices(*, close_df: pd.DataFrame, high_df: pd.DataFrame, low_df: pd.DataFrame, volume_df: pd.DataFrame | None=None, snapshot_date: date, symbols: Iterable[str]) -> dict[str, PriceInfo]`
- [_build_predictions](../../backtesting/risk_bridge.py) — ligne 222 : `def _build_predictions(predictions_df: pd.DataFrame, snapshot_date: date) -> dict[str, PredictionInfo]`
- [_build_ml_selection_inputs_from_day](../../backtesting/risk_bridge.py) — ligne 280 : `def _build_ml_selection_inputs_from_day(day_scores: pd.DataFrame, predictions: dict[str, PredictionInfo], snapshot_date: date) -> list[MLRankedCandidate]`
- [_build_return_matrix](../../backtesting/risk_bridge.py) — ligne 353 : `def _build_return_matrix(close_df: pd.DataFrame, snapshot_date: date, symbols: list[str], lookback_days: int) -> pd.DataFrame | None`
- [_resolve_regime_snapshot_dates](../../backtesting/risk_bridge.py) — ligne 365 : `def _resolve_regime_snapshot_dates(close_df: pd.DataFrame, execution_dates: list[date]) -> list[date]`
- [portfolio_entries_to_signals](../../backtesting/risk_bridge.py) — ligne 379 : `def portfolio_entries_to_signals(entries: list[PortfolioEntry], snapshot_date: date) -> pd.DataFrame`
- [_concat_signal_frames](../../backtesting/risk_bridge.py) — ligne 415 : `def _concat_signal_frames(signal_frames: Iterable[pd.DataFrame]) -> pd.DataFrame`
- [build_phase2_risk_result](../../backtesting/risk_bridge.py) — ligne 422 : `def build_phase2_risk_result(*, scores_df: pd.DataFrame, predictions_df: pd.DataFrame, close_df: pd.DataFrame, high_df: pd.DataFrame, low_df: pd.DataFrame, volume_df: pd.DataFrame | None=None, risk_config: RiskConfig, score_column: str | None=None, correlation_lookback_days: int | None=None, market_regimes_config: 'MarketRegimesConfig | None'=None, equity_provider: Callable[[date], float] | None=None, macro_provider: object | None=None, sentiment_score_provider: Callable[[int], float | None] | None=None, earnings_lookup: Callable[[date, int, int], dict[str, date]] | None=None, sector_map: dict[str, str] | None=None, selection_policy: str='directional', operational_snapshot_provider: Callable[[date], object] | None=None) -> RiskBridgeResult`
- [entries_to_dataframe](../../backtesting/risk_bridge.py) — ligne 806 : `def entries_to_dataframe(entries: list[PortfolioEntry]) -> pd.DataFrame`
- [_regime_snapshots_to_dataframe](../../backtesting/risk_bridge.py) — ligne 812 : `def _regime_snapshots_to_dataframe(regime_snapshots: dict[date, dict]) -> pd.DataFrame`
- [save_phase2_risk_artifacts](../../backtesting/risk_bridge.py) — ligne 839 : `def save_phase2_risk_artifacts(result: RiskBridgeResult, output_dir: Path) -> dict[str, str]`

## `backtesting/risk_overlay.py`

Source SHA-256 : `a5784952490591a0e95d70bdd25a350e162ee4162a8b79728fcb84c3ec670e94`

- [RegimeFilterConfig](../../backtesting/risk_overlay.py) — ligne 24 : `class RegimeFilterConfig`
- [RegimeFilterConfig.is_entry_allowed](../../backtesting/risk_overlay.py) — ligne 31 : `def is_entry_allowed(self, benchmark_close: pd.Series | None, as_of: pd.Timestamp) -> bool`
- [BullStrictConfig](../../backtesting/risk_overlay.py) — ligne 49 : `class BullStrictConfig`
- [BullStrictConfig.is_bull_strict](../../backtesting/risk_overlay.py) — ligne 68 : `def is_bull_strict(self, benchmark_close: pd.Series | None, as_of: pd.Timestamp) -> bool`
- [BullStrictConfig.is_entry_allowed](../../backtesting/risk_overlay.py) — ligne 85 : `def is_entry_allowed(self, side: str, benchmark_close: pd.Series | None, as_of: pd.Timestamp) -> bool`
- [SectoralCapConfig](../../backtesting/risk_overlay.py) — ligne 100 : `class SectoralCapConfig`
- [SectoralCapConfig.is_entry_allowed](../../backtesting/risk_overlay.py) — ligne 106 : `def is_entry_allowed(self, sector: str | None, sector_exposure_pct: float, candidate_weight_pct: float) -> bool`
- [DrawdownCircuitBreaker](../../backtesting/risk_overlay.py) — ligne 118 : `class DrawdownCircuitBreaker`
- [DrawdownCircuitBreaker._ensure_episode](../../backtesting/risk_overlay.py) — ligne 183 : `def _ensure_episode(self) -> object`
- [DrawdownCircuitBreaker.set_spy_regime](../../backtesting/risk_overlay.py) — ligne 189 : `def set_spy_regime(self, trade_date) -> None`
- [DrawdownCircuitBreaker._reference_peak](../../backtesting/risk_overlay.py) — ligne 199 : `def _reference_peak(self, peak_equity: float) -> float`
- [DrawdownCircuitBreaker.allocation_scale](../../backtesting/risk_overlay.py) — ligne 206 : `def allocation_scale(self, entry_mode: str | None=None, side: str | None=None) -> float`
- [DrawdownCircuitBreaker.update_regime_streak](../../backtesting/risk_overlay.py) — ligne 232 : `def update_regime_streak(self, entry_mode: str | None, current_equity: float=0.0) -> None`
- [DrawdownCircuitBreaker.update](../../backtesting/risk_overlay.py) — ligne 282 : `def update(self, equity: float, peak_equity: float) -> bool`
- [DrawdownCircuitBreaker.just_tripped](../../backtesting/risk_overlay.py) — ligne 331 : `def just_tripped(self) -> bool`
- [compute_portfolio_vol_scaler](../../backtesting/risk_overlay.py) — ligne 336 : `def compute_portfolio_vol_scaler(daily_returns: pd.Series, *, target_annual_vol: float, lookback: int=60, floor: float=0.25, cap: float=1.5) -> float`
- [snapshot_sector_exposure](../../backtesting/risk_overlay.py) — ligne 357 : `def snapshot_sector_exposure(positions: dict, close: pd.DataFrame, trade_day: pd.Timestamp, sector_map: dict, current_equity: float) -> dict`
- [RiskOverlayConfig](../../backtesting/risk_overlay.py) — ligne 406 : `class RiskOverlayConfig`
- [RiskOverlayConfig.is_default](../../backtesting/risk_overlay.py) — ligne 416 : `def is_default(self) -> bool`

## `backtesting/run_metadata.py`

Source SHA-256 : `daeb298cb9f560a327d0790c6b94375a447e211d218de1d3ff8a8f76ff23d44b`

- [_safe_git_command](../../backtesting/run_metadata.py) — ligne 31 : `def _safe_git_command(args: list[str]) -> str | None`
- [collect_git_info](../../backtesting/run_metadata.py) — ligne 43 : `def collect_git_info() -> dict[str, Any]`
- [collect_environment_info](../../backtesting/run_metadata.py) — ligne 51 : `def collect_environment_info() -> dict[str, Any]`
- [hash_dataset](../../backtesting/run_metadata.py) — ligne 67 : `def hash_dataset(frames: Mapping[str, pd.DataFrame | pd.Series | None]) -> str`
- [build_run_metadata](../../backtesting/run_metadata.py) — ligne 99 : `def build_run_metadata(*, seed: int | None=None, dataset_frames: Mapping[str, pd.DataFrame | pd.Series | None] | None=None, extra: Mapping[str, Any] | None=None) -> dict[str, Any]`

## `backtesting/screener_diagnostics/__init__.py`

Source SHA-256 : `2aaef05f78b282be2377a81b2be3b26da4404b85e499d37f0c466ff8c4912dd2`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `backtesting/screener_diagnostics/_impl.py`

Source SHA-256 : `54d44d9f254b01a931d55cb00c2baa653e12c65c9fba280b39b9ff3179e9fefb`

- [ScreenerDiagnosticsScenario](../../backtesting/screener_diagnostics/_impl.py) — ligne 97 : `class ScreenerDiagnosticsScenario`
- [ScreenerDiagnosticsScenario.parameter_dict](../../backtesting/screener_diagnostics/_impl.py) — ligne 103 : `def parameter_dict(self) -> dict[str, float | int]`
- [ScreenerDiagnosticsScenario.to_record](../../backtesting/screener_diagnostics/_impl.py) — ligne 111 : `def to_record(self) -> dict[str, object]`
- [ScreenerDiagnosticsResult](../../backtesting/screener_diagnostics/_impl.py) — ligne 121 : `class ScreenerDiagnosticsResult`
- [ScreenerDiagnosticsResult.scenario_frame](../../backtesting/screener_diagnostics/_impl.py) — ligne 130 : `def scenario_frame(self) -> pd.DataFrame`
- [ScreenerDiagnosticsResult.metadata](../../backtesting/screener_diagnostics/_impl.py) — ligne 133 : `def metadata(self) -> dict[str, object]`
- [_dedupe_preserve_order](../../backtesting/screener_diagnostics/_impl.py) — ligne 152 : `def _dedupe_preserve_order(values: Sequence[float | int] | None) -> list[float | int]`
- [_scenario_config_key](../../backtesting/screener_diagnostics/_impl.py) — ligne 165 : `def _scenario_config_key(config: ScreenerConfig) -> tuple[float, int, float, float]`
- [_format_float_token](../../backtesting/screener_diagnostics/_impl.py) — ligne 174 : `def _format_float_token(value: float) -> str`
- [_format_liquidity_token](../../backtesting/screener_diagnostics/_impl.py) — ligne 180 : `def _format_liquidity_token(value: float) -> str`
- [build_screener_oat_scenarios](../../backtesting/screener_diagnostics/_impl.py) — ligne 192 : `def build_screener_oat_scenarios(base_config: ScreenerConfig, *, rs_values: Sequence[float] | None=None, range_lookback_values: Sequence[int] | None=None, historical_range_score_values: Sequence[float] | None=None, liquidity_threshold_values: Sequence[float] | None=None) -> list[ScreenerDiagnosticsScenario]`
- [build_screener_grid_scenarios](../../backtesting/screener_diagnostics/_impl.py) — ligne 272 : `def build_screener_grid_scenarios(base_config: ScreenerConfig, *, rs_values: Sequence[float], range_lookback_values: Sequence[int], historical_range_score_values: Sequence[float], liquidity_threshold_values: Sequence[float], max_scenarios: int | None=None) -> list[ScreenerDiagnosticsScenario]`
- [_safe_divide](../../backtesting/screener_diagnostics/_impl.py) — ligne 336 : `def _safe_divide(numerator: float | int, denominator: float | int) -> float`
- [_safe_numeric_mean](../../backtesting/screener_diagnostics/_impl.py) — ligne 342 : `def _safe_numeric_mean(frame: pd.DataFrame, column: str) -> float`
- [summarize_screener_diagnostics](../../backtesting/screener_diagnostics/_impl.py) — ligne 351 : `def summarize_screener_diagnostics(daily_metrics: pd.DataFrame, *, baseline_name: str | None=None) -> pd.DataFrame`
- [classify_market_regimes](../../backtesting/screener_diagnostics/_impl.py) — ligne 412 : `def classify_market_regimes(benchmark_history: pd.DataFrame, *, benchmark_symbol: str, trade_dates: Sequence[date] | None=None, trend_lookback_days: int=DEFAULT_REGIME_TREND_LOOKBACK_DAYS, long_ma_window: int=DEFAULT_REGIME_LONG_MA_WINDOW, vol_window: int=DEFAULT_REGIME_VOL_WINDOW, vol_lookback_window: int=DEFAULT_REGIME_VOL_LOOKBACK_WINDOW, bull_bear_return_threshold: float=DEFAULT_REGIME_BULL_BEAR_RETURN_THRESHOLD, volatility_multiplier: float=DEFAULT_REGIME_VOLATILITY_MULTIPLIER) -> pd.DataFrame`
- [summarize_screener_diagnostics_by_regime](../../backtesting/screener_diagnostics/_impl.py) — ligne 500 : `def summarize_screener_diagnostics_by_regime(daily_metrics: pd.DataFrame, *, baseline_name: str | None=None) -> pd.DataFrame`
- [_pick_first_available_column](../../backtesting/screener_diagnostics/_impl.py) — ligne 526 : `def _pick_first_available_column(frame: pd.DataFrame, candidates: Sequence[str]) -> str | None`
- [_winsorize_series](../../backtesting/screener_diagnostics/_impl.py) — ligne 536 : `def _winsorize_series(series: pd.Series, *, quantile: float=0.05) -> pd.Series`
- [_normalize_metric_series](../../backtesting/screener_diagnostics/_impl.py) — ligne 546 : `def _normalize_metric_series(series: pd.Series, *, higher_is_better: bool) -> pd.Series`
- [_weighted_average_columns](../../backtesting/screener_diagnostics/_impl.py) — ligne 565 : `def _weighted_average_columns(frame: pd.DataFrame, columns_with_weights: Sequence[tuple[str, float]]) -> pd.Series`
- [_weighted_confidence](../../backtesting/screener_diagnostics/_impl.py) — ligne 578 : `def _weighted_confidence(frame: pd.DataFrame, columns_with_weights: Sequence[tuple[str, float]]) -> pd.Series`
- [_weighted_geometric_mean](../../backtesting/screener_diagnostics/_impl.py) — ligne 591 : `def _weighted_geometric_mean(frame: pd.DataFrame, columns_with_weights: Sequence[tuple[str, float]]) -> pd.Series`
- [_candidate_mean_columns](../../backtesting/screener_diagnostics/_impl.py) — ligne 606 : `def _candidate_mean_columns(prefix: str, metric: str, target_horizon: int) -> list[str]`
- [_candidate_daily_columns](../../backtesting/screener_diagnostics/_impl.py) — ligne 611 : `def _candidate_daily_columns(prefix: str, metric: str, target_horizon: int) -> list[str]`
- [_enrich_summary_with_daily_stability](../../backtesting/screener_diagnostics/_impl.py) — ligne 616 : `def _enrich_summary_with_daily_stability(summary_metrics: pd.DataFrame, daily_metrics: pd.DataFrame | None, *, target_horizon: int) -> pd.DataFrame`
- [_build_recommendation_text](../../backtesting/screener_diagnostics/_impl.py) — ligne 659 : `def _build_recommendation_text(row: pd.Series, *, forward_column: str | None) -> str`
- [_build_objective_reason](../../backtesting/screener_diagnostics/_impl.py) — ligne 674 : `def _build_objective_reason(row: pd.Series, *, objective_name: str, objective_label: str) -> str`
- [_empty_objective_summary](../../backtesting/screener_diagnostics/_impl.py) — ligne 699 : `def _empty_objective_summary(*, baseline_name: str | None, message: str) -> dict[str, object]`
- [_resolve_objective_summary_by_regime](../../backtesting/screener_diagnostics/_impl.py) — ligne 712 : `def _resolve_objective_summary_by_regime(*, summary_metrics_by_regime: pd.DataFrame | None, daily_metrics: pd.DataFrame | None, baseline_name: str | None) -> pd.DataFrame`
- [recommend_screener_scenarios](../../backtesting/screener_diagnostics/_impl.py) — ligne 725 : `def recommend_screener_scenarios(summary_metrics: pd.DataFrame, *, daily_metrics: pd.DataFrame | None=None, baseline_name: str | None=None, target_horizon: int=DEFAULT_RECOMMENDATION_HORIZON, pillar_weights: dict[str, float] | None=None) -> tuple[pd.DataFrame, dict[str, object]]`
- [build_cross_regime_recommendations](../../backtesting/screener_diagnostics/_impl.py) — ligne 973 : `def build_cross_regime_recommendations(regime_recommendations: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]`
- [recommend_screener_scenarios_by_regime](../../backtesting/screener_diagnostics/_impl.py) — ligne 1048 : `def recommend_screener_scenarios_by_regime(summary_metrics_by_regime: pd.DataFrame, *, daily_metrics: pd.DataFrame | None=None, baseline_name: str | None=None, target_horizon: int=DEFAULT_RECOMMENDATION_HORIZON, pillar_weights: dict[str, float] | None=None) -> tuple[pd.DataFrame, dict[str, object], pd.DataFrame, dict[str, object]]`
- [recommend_screener_scenarios_by_objective](../../backtesting/screener_diagnostics/_impl.py) — ligne 1108 : `def recommend_screener_scenarios_by_objective(summary_metrics: pd.DataFrame, *, daily_metrics: pd.DataFrame | None=None, summary_metrics_by_regime: pd.DataFrame | None=None, baseline_name: str | None=None, target_horizon: int=DEFAULT_RECOMMENDATION_HORIZON) -> tuple[pd.DataFrame, dict[str, object]]`
- [ScreenerDiagnosticsService](../../backtesting/screener_diagnostics/_impl.py) — ligne 1351 : `class ScreenerDiagnosticsService`
- [ScreenerDiagnosticsService.__init__](../../backtesting/screener_diagnostics/_impl.py) — ligne 1354 : `def __init__(self, engine: Engine | None=None, *, base_screener_config: ScreenerConfig | None=None, scanner_config: AlphaScannerConfig | None=None, sentiment_config: SentimentBoostConfig | None=None, risk_config: RiskConfig | None=None, screener_max_workers: int | None=None, forward_return_horizons: Sequence[int]=DEFAULT_FORWARD_HORIZONS, capital_preset_key: str | None=None) -> None`
- [ScreenerDiagnosticsService._build_market_regime_frame](../../backtesting/screener_diagnostics/_impl.py) — ligne 1378 : `def _build_market_regime_frame(self, trading_dates: Sequence[date]) -> pd.DataFrame`
- [ScreenerDiagnosticsService._resolve_stock_bars_layout](../../backtesting/screener_diagnostics/_impl.py) — ligne 1400 : `def _resolve_stock_bars_layout(self) -> tuple[str, str]`
- [ScreenerDiagnosticsService.list_trading_dates](../../backtesting/screener_diagnostics/_impl.py) — ligne 1411 : `def list_trading_dates(self, start_date: date, end_date: date) -> list[date]`
- [ScreenerDiagnosticsService.analyze_period](../../backtesting/screener_diagnostics/_impl.py) — ligne 1433 : `def analyze_period(self, *, start_date: date, end_date: date, scenarios: Sequence[ScreenerDiagnosticsScenario], limit_days: int | None=None) -> ScreenerDiagnosticsResult`
- [ScreenerDiagnosticsService._make_snapshot_service](../../backtesting/screener_diagnostics/_impl.py) — ligne 1475 : `def _make_snapshot_service(self, screener_config: ScreenerConfig) -> BackfillScoresHistoryService`
- [ScreenerDiagnosticsService._evaluate_scenario_on_date](../../backtesting/screener_diagnostics/_impl.py) — ligne 1485 : `def _evaluate_scenario_on_date(self, snapshot_service: BackfillScoresHistoryService, scenario: ScreenerDiagnosticsScenario, as_of_date: date) -> dict[str, object]`
- [ScreenerDiagnosticsService._build_pit_frames](../../backtesting/screener_diagnostics/_impl.py) — ligne 1596 : `def _build_pit_frames(self, snapshot_service: BackfillScoresHistoryService, as_of_date: date) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]`
- [ScreenerDiagnosticsService._extract_selector_selections](../../backtesting/screener_diagnostics/_impl.py) — ligne 1619 : `def _extract_selector_selections(history_df: pd.DataFrame) -> pd.DataFrame`
- [ScreenerDiagnosticsService._build_portfolio_entries](../../backtesting/screener_diagnostics/_impl.py) — ligne 1650 : `def _build_portfolio_entries(self, selector_selections: pd.DataFrame, as_of_date: date) -> list[PortfolioEntry]`
- [ScreenerDiagnosticsService._load_price_history](../../backtesting/screener_diagnostics/_impl.py) — ligne 1685 : `def _load_price_history(self, symbols: Sequence[str], *, start_date: date | None=None, end_date: date | None=None, include_volume: bool=True) -> pd.DataFrame`
- [ScreenerDiagnosticsService._load_pit_prices](../../backtesting/screener_diagnostics/_impl.py) — ligne 1733 : `def _load_pit_prices(self, symbols: Sequence[str], *, as_of_date: date, atr_window: int) -> dict[str, PriceInfo]`
- [ScreenerDiagnosticsService._load_pit_return_matrix](../../backtesting/screener_diagnostics/_impl.py) — ligne 1769 : `def _load_pit_return_matrix(self, symbols: Sequence[str], *, as_of_date: date, lookback_days: int) -> pd.DataFrame`
- [ScreenerDiagnosticsService._compute_benchmark_forward_returns](../../backtesting/screener_diagnostics/_impl.py) — ligne 1795 : `def _compute_benchmark_forward_returns(self, as_of_date: date) -> dict[str, float]`
- [ScreenerDiagnosticsService._compute_symbol_set_forward_metrics](../../backtesting/screener_diagnostics/_impl.py) — ligne 1806 : `def _compute_symbol_set_forward_metrics(self, symbols: Sequence[str], *, weights: dict[str, float] | None, as_of_date: date, benchmark_returns: dict[str, float], prefix: str) -> dict[str, float]`
- [ScreenerDiagnosticsService._compute_symbol_forward_returns](../../backtesting/screener_diagnostics/_impl.py) — ligne 1847 : `def _compute_symbol_forward_returns(self, symbols: Sequence[str], *, as_of_date: date) -> dict[str, dict[int, float]]`
- [ScreenerDiagnosticsService._normalize_weights](../../backtesting/screener_diagnostics/_impl.py) — ligne 1880 : `def _normalize_weights(horizon_returns: dict[str, float], weights: dict[str, float] | None) -> dict[str, float]`
- [ScreenerDiagnosticsService._mean_entry_score](../../backtesting/screener_diagnostics/_impl.py) — ligne 1898 : `def _mean_entry_score(entries: Sequence[PortfolioEntry]) -> float`
- [export_screener_diagnostics](../../backtesting/screener_diagnostics/_impl.py) — ligne 1904 : `def export_screener_diagnostics(result: ScreenerDiagnosticsResult, output_dir: str | Path) -> dict[str, Path]`
- [export_screener_recommendations](../../backtesting/screener_diagnostics/_impl.py) — ligne 1938 : `def export_screener_recommendations(recommendations: pd.DataFrame, recommendation_summary: dict[str, object], output_dir: str | Path) -> dict[str, Path]`
- [export_screener_regime_recommendations](../../backtesting/screener_diagnostics/_impl.py) — ligne 1959 : `def export_screener_regime_recommendations(regime_recommendations: pd.DataFrame, regime_summary: dict[str, object], cross_regime_recommendations: pd.DataFrame, cross_regime_summary: dict[str, object], output_dir: str | Path) -> dict[str, Path]`
- [export_screener_objective_recommendations](../../backtesting/screener_diagnostics/_impl.py) — ligne 1988 : `def export_screener_objective_recommendations(objective_recommendations: pd.DataFrame, objective_summary: dict[str, object], output_dir: str | Path) -> dict[str, Path]`
- [validate_recommendations_holdout](../../backtesting/screener_diagnostics/_impl.py) — ligne 2009 : `def validate_recommendations_holdout(daily_metrics: pd.DataFrame, *, train_end, test_end, train_start=None, test_start=None, metric_column: str='portfolio_forward_return_20d', scenario_column: str='scenario_name', date_column: str='trade_date') -> tuple[pd.DataFrame, dict[str, object]]`
- [export_holdout_validation](../../backtesting/screener_diagnostics/_impl.py) — ligne 2095 : `def export_holdout_validation(holdout_df: pd.DataFrame, holdout_summary: dict[str, object], output_dir: str | Path) -> dict[str, Path]`

## `backtesting/screener_diagnostics/analyze.py`

Source SHA-256 : `d17e2461704a8542f002036b49fd26f0a46beddb39265d8f9a0018cda51b063f`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `backtesting/screener_diagnostics/holdout.py`

Source SHA-256 : `ebd8a36f704a135cbd44b470bdc81e5c761b4c496c1c2822c54e750ed530fdcb`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `backtesting/screener_diagnostics/recommend.py`

Source SHA-256 : `09be050c0ce6a38b7a40b5f94c940f871cc8778b067ad860f4bc628a4578c039`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `backtesting/screener_diagnostics/regime.py`

Source SHA-256 : `a7bcc77f8ee64ce4a2b68c9a147a41c5725c84d98d9766505e7c4b5b86b73c43`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `backtesting/screener_diagnostics/scenarios.py`

Source SHA-256 : `8d904eee8350bd25f408009088578e10bdda2634ab8520e95baef58e57baaadf`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `backtesting/sentiment_calibration.py`

Source SHA-256 : `cd8be4adadf3b0b62d3bc637ba36bcf4e34a1a4ecc5e6ee0f69ef386530802b4`

- [_resolve_symbol_source](../../backtesting/sentiment_calibration.py) — ligne 38 : `def _resolve_symbol_source(engine: Engine, symbol_source: str) -> list[str]`
- [_normalize_preset_keys](../../backtesting/sentiment_calibration.py) — ligne 51 : `def _normalize_preset_keys(keys: str | list[str] | None) -> list[str] | None`
- [_utc_now_naive](../../backtesting/sentiment_calibration.py) — ligne 66 : `def _utc_now_naive() -> datetime`
- [_build_run_id](../../backtesting/sentiment_calibration.py) — ligne 70 : `def _build_run_id(prefix: str) -> str`
- [SentimentCalibrationScenario](../../backtesting/sentiment_calibration.py) — ligne 75 : `class SentimentCalibrationScenario`
- [SentimentCalibrationScenario.scenario_name](../../backtesting/sentiment_calibration.py) — ligne 81 : `def scenario_name(self) -> str`
- [SentimentCalibrationResult](../../backtesting/sentiment_calibration.py) — ligne 86 : `class SentimentCalibrationResult`
- [WalkForwardFoldResult](../../backtesting/sentiment_calibration.py) — ligne 97 : `class WalkForwardFoldResult`
- [WalkForwardCalibrationResult](../../backtesting/sentiment_calibration.py) — ligne 111 : `class WalkForwardCalibrationResult`
- [SentimentWeightCalibrator](../../backtesting/sentiment_calibration.py) — ligne 126 : `class SentimentWeightCalibrator`
- [SentimentWeightCalibrator.__init__](../../backtesting/sentiment_calibration.py) — ligne 127 : `def __init__(self, engine: Engine | None=None) -> None`
- [SentimentWeightCalibrator.default_scenarios](../../backtesting/sentiment_calibration.py) — ligne 131 : `def default_scenarios() -> list[SentimentCalibrationScenario]`
- [SentimentWeightCalibrator.load_dataset](../../backtesting/sentiment_calibration.py) — ligne 168 : `def load_dataset(self, start_date: date, end_date: date, horizons: tuple[int, ...]=(5, 10, 20), selected_only: bool=True, capital_preset_keys: str | list[str] | None=None, symbol_source: str | None=None) -> pd.DataFrame`
- [SentimentWeightCalibrator._list_symbols](../../backtesting/sentiment_calibration.py) — ligne 252 : `def _list_symbols(self, start_date: date, end_date: date, selected_only: bool=True, capital_preset_keys: str | list[str] | None=None, symbol_source: str | None=None) -> list[str]`
- [SentimentWeightCalibrator._load_dataset_batch_sql](../../backtesting/sentiment_calibration.py) — ligne 293 : `def _load_dataset_batch_sql(self, batch_symbols: list[str], start_date: date, end_date: date, end_date_plus_buffer: date, selected_only: bool=True, capital_preset_keys: str | list[str] | None=None) -> pd.DataFrame`
- [SentimentWeightCalibrator.build_forward_return_frame](../../backtesting/sentiment_calibration.py) — ligne 359 : `def build_forward_return_frame(raw: pd.DataFrame, horizons: tuple[int, ...]=(5, 10, 20)) -> pd.DataFrame`
- [SentimentWeightCalibrator._normalize_signal](../../backtesting/sentiment_calibration.py) — ligne 401 : `def _normalize_signal(series: pd.Series) -> pd.Series`
- [SentimentWeightCalibrator.build_walk_forward_windows](../../backtesting/sentiment_calibration.py) — ligne 419 : `def build_walk_forward_windows(snapshot_dates: Iterable[pd.Timestamp | str | datetime | date], *, min_train_days: int=252, test_days: int=63, step_days: int | None=None) -> list[dict[str, Any]]`
- [SentimentWeightCalibrator.score_dataset_for_scenario](../../backtesting/sentiment_calibration.py) — ligne 521 : `def score_dataset_for_scenario(self, dataset: pd.DataFrame, scenario: SentimentCalibrationScenario, *, score_column: str='composite_score') -> pd.DataFrame`
- [SentimentWeightCalibrator.build_portfolio_signals](../../backtesting/sentiment_calibration.py) — ligne 556 : `def build_portfolio_signals(scored_df: pd.DataFrame, *, score_column: str, max_positions: int) -> pd.DataFrame`
- [SentimentWeightCalibrator.build_portfolio_signals_long_short](../../backtesting/sentiment_calibration.py) — ligne 590 : `def build_portfolio_signals_long_short(scored_df: pd.DataFrame, *, score_column: str='final_score_walk_forward', max_positions_long: int=4, max_positions_short: int=4) -> pd.DataFrame`
- [SentimentWeightCalibrator._scenario_from_row](../../backtesting/sentiment_calibration.py) — ligne 670 : `def _scenario_from_row(row: dict[str, Any]) -> SentimentCalibrationScenario`
- [SentimentWeightCalibrator.evaluate_scenarios](../../backtesting/sentiment_calibration.py) — ligne 677 : `def evaluate_scenarios(self, dataset: pd.DataFrame, scenarios: Iterable[SentimentCalibrationScenario], horizons: tuple[int, ...]=(5, 10, 20), top_n: int=20, *, direction: str='long') -> pd.DataFrame`
- [SentimentWeightCalibrator.export_results](../../backtesting/sentiment_calibration.py) — ligne 761 : `def export_results(result_df: pd.DataFrame, output_dir: Path) -> dict[str, str]`
- [SentimentWeightCalibrator.export_walk_forward_results](../../backtesting/sentiment_calibration.py) — ligne 771 : `def export_walk_forward_results(*, fold_df: pd.DataFrame, scored_oos_df: pd.DataFrame, signals_df: pd.DataFrame, report: BacktestReport, pf: Any, output_dir: Path, params: dict[str, object]) -> dict[str, str]`
- [SentimentWeightCalibrator.calibrate](../../backtesting/sentiment_calibration.py) — ligne 844 : `def calibrate(self, start_date: date, end_date: date, scenarios: Iterable[SentimentCalibrationScenario] | None=None, horizons: tuple[int, ...]=(5, 10, 20), top_n: int=20, selected_only: bool=True, output_dir: Path | None=None, capital_preset_keys: str | list[str] | None=None, symbol_source: str | None=None) -> tuple[SentimentCalibrationResult, pd.DataFrame, dict[str, str]]`
- [SentimentWeightCalibrator.walk_forward_backtest](../../backtesting/sentiment_calibration.py) — ligne 883 : `def walk_forward_backtest(self, *, start_date: date, end_date: date, scenarios: Iterable[SentimentCalibrationScenario] | None=None, horizons: tuple[int, ...]=(5, 10, 20), top_n: int=20, selected_only: bool=True, min_train_days: int=252, test_days: int=63, step_days: int | None=None, max_positions: int=20, initial_equity: float=100000.0, profit_taker_pct: float=0.08, trailing_stop_pct: float=0.05, fees_pct: float=0.001, output_dir: Path | None=None, capital_preset_keys: str | list[str] | None=None, atr_trailing_stop_multiplier: float=0.0, symbol_source: str | None=None) -> tuple[WalkForwardCalibrationResult, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, str]]`
- [_emit_run_summary](../../backtesting/sentiment_calibration.py) — ligne 1130 : `def _emit_run_summary(summary: dict[str, object]) -> None`
- [_build_arg_parser](../../backtesting/sentiment_calibration.py) — ligne 1149 : `def _build_arg_parser() -> argparse.ArgumentParser`
- [main](../../backtesting/sentiment_calibration.py) — ligne 1170 : `def main(argv: list[str] | None=None) -> int`

## `backtesting/signal_replay.py`

Source SHA-256 : `afe1a83fa850b90d81f472f2ff53b5b9f110bc645975e828c242da6bc09fa1c7`

- [_validate_prediction_policy_consistency](../../backtesting/signal_replay.py) — ligne 33 : `def _validate_prediction_policy_consistency(df: pd.DataFrame) -> None`
- [_pick_score_column](../../backtesting/signal_replay.py) — ligne 58 : `def _pick_score_column(df: pd.DataFrame, preferred: str | None, fallback_priority: Iterable[str]=SCORE_FALLBACK_PRIORITY) -> tuple[pd.Series, pd.Series]`
- [replay_signals](../../backtesting/signal_replay.py) — ligne 93 : `def replay_signals(predictions_df: pd.DataFrame, scores_df: Optional[pd.DataFrame]=None, *, score_column: str | None=None, max_positions: int=20, max_long_positions: int | None=None, max_short_positions: int | None=None, min_proba_long: float=0.0, min_proba_short: float=0.0, min_score_long: float | None=None, max_score_short: float | None=None) -> pd.DataFrame`

## `backtesting/simulator.py`

Source SHA-256 : `f08b5d24fe7f2476c1d91742f476e15f52f87852e14ffccb440c48451d25d92d`

- [_effective_trailing_pct](../../backtesting/simulator.py) — ligne 59 : `def _effective_trailing_pct(cfg: 'BacktestConfig', short: bool, derived_pct: float) -> float`
- [_production_tp_price](../../backtesting/simulator.py) — ligne 72 : `def _production_tp_price(entry_price: float, atr_pct: float | None, tp_atr_multiple: float, tp_max_pct: float, short: bool) -> float | None`
- [BacktestConfig](../../backtesting/simulator.py) — ligne 94 : `class BacktestConfig`
- [BacktestConfig.__post_init__](../../backtesting/simulator.py) — ligne 244 : `def __post_init__(self) -> None`
- [BacktestDiagnostics](../../backtesting/simulator.py) — ligne 299 : `class BacktestDiagnostics`
- [BacktestDiagnostics.to_dict](../../backtesting/simulator.py) — ligne 329 : `def to_dict(self) -> dict[str, int]`
- [_OpenPosition](../../backtesting/simulator.py) — ligne 357 : `class _OpenPosition`
- [_RunState](../../backtesting/simulator.py) — ligne 396 : `class _RunState`
- [_DailyLeverageState](../../backtesting/simulator.py) — ligne 417 : `class _DailyLeverageState`
- [_ReadableTradesAccessor](../../backtesting/simulator.py) — ligne 425 : `class _ReadableTradesAccessor`
- [_ReadableTradesAccessor.__init__](../../backtesting/simulator.py) — ligne 428 : `def __init__(self, closed_trades_df: pd.DataFrame) -> None`
- [_ReadableTradesAccessor.closed](../../backtesting/simulator.py) — ligne 432 : `def closed(self) -> _ReadableTradesAccessor`
- [_ReadableTradesAccessor.records_readable](../../backtesting/simulator.py) — ligne 436 : `def records_readable(self) -> pd.DataFrame`
- [_ReadableTradesAccessor.count](../../backtesting/simulator.py) — ligne 462 : `def count(self) -> int`
- [BacktestResult](../../backtesting/simulator.py) — ligne 467 : `class BacktestResult`
- [BacktestResult.__post_init__](../../backtesting/simulator.py) — ligne 480 : `def __post_init__(self) -> None`
- [BacktestResult.final_value](../../backtesting/simulator.py) — ligne 484 : `def final_value(self) -> float`
- [BacktestResult.value](../../backtesting/simulator.py) — ligne 487 : `def value(self) -> pd.Series`
- [BacktestEngine](../../backtesting/simulator.py) — ligne 491 : `class BacktestEngine`
- [BacktestEngine.__init__](../../backtesting/simulator.py) — ligne 529 : `def __init__(self, config: BacktestConfig) -> None`
- [BacktestEngine._resolve_cost_model](../../backtesting/simulator.py) — ligne 581 : `def _resolve_cost_model(config: BacktestConfig) -> TradingCostModel`
- [BacktestEngine.tracker_snapshot](../../backtesting/simulator.py) — ligne 605 : `def tracker_snapshot(self) -> dict[str, object]`
- [BacktestEngine.load_tracker_state](../../backtesting/simulator.py) — ligne 613 : `def load_tracker_state(self, snapshot: dict[str, object]) -> None`
- [BacktestEngine._to_scalar](../../backtesting/simulator.py) — ligne 637 : `def _to_scalar(value) -> float`
- [BacktestEngine._empty_market_frame](../../backtesting/simulator.py) — ligne 644 : `def _empty_market_frame(frame: pd.DataFrame) -> pd.DataFrame`
- [BacktestEngine._allow_fractional_shares](../../backtesting/simulator.py) — ligne 648 : `def _allow_fractional_shares(self) -> bool`
- [BacktestEngine._normalize_trade_quantity](../../backtesting/simulator.py) — ligne 651 : `def _normalize_trade_quantity(self, value: float | int | None) -> float`
- [BacktestEngine._resolve_daily_leverage_state](../../backtesting/simulator.py) — ligne 657 : `def _resolve_daily_leverage_state(self, current_equity: float, *, drawdown_scale: float=1.0) -> _DailyLeverageState`
- [BacktestEngine._resolve_margin_buying_power_multiplier](../../backtesting/simulator.py) — ligne 730 : `def _resolve_margin_buying_power_multiplier(self, current_equity: float, *, drawdown_scale: float=1.0) -> float`
- [BacktestEngine._resolve_available_entry_budget](../../backtesting/simulator.py) — ligne 743 : `def _resolve_available_entry_budget(self, *, constraints: TradingConstraintConfig, settled_cash: float, current_equity: float, current_gross_notional: float) -> float`
- [BacktestEngine.run](../../backtesting/simulator.py) — ligne 759 : `def run(self, open_df: pd.DataFrame | None=None, close: pd.DataFrame | None=None, high: pd.DataFrame | None=None, low: pd.DataFrame | None=None, signals_df: pd.DataFrame | None=None, volume: pd.DataFrame | None=None, sector_map: dict[str, str] | None=None, spread_df: pd.DataFrame | None=None, **legacy_kwargs) -> BacktestResult`
- [BacktestEngine._validate_replay_protections](../../backtesting/simulator.py) — ligne 883 : `def _validate_replay_protections(signals: pd.DataFrame, opens: pd.DataFrame) -> None`
- [BacktestEngine._schedule_signals_for_execution](../../backtesting/simulator.py) — ligne 929 : `def _schedule_signals_for_execution(signals_df: pd.DataFrame, trading_days: pd.DatetimeIndex) -> pd.DataFrame`
- [BacktestEngine._normalize_event_value](../../backtesting/simulator.py) — ligne 953 : `def _normalize_event_value(value: object) -> object | None`
- [BacktestEngine._build_signal_context](../../backtesting/simulator.py) — ligne 972 : `def _build_signal_context(self, row: pd.Series) -> dict[str, object]`
- [BacktestEngine._derive_entry_reason](../../backtesting/simulator.py) — ligne 984 : `def _derive_entry_reason(self, row: pd.Series) -> str`
- [BacktestEngine._format_event_payload](../../backtesting/simulator.py) — ligne 994 : `def _format_event_payload(payload: dict[str, object]) -> str`
- [BacktestEngine._record_trade_event](../../backtesting/simulator.py) — ligne 997 : `def _record_trade_event(self, state: _RunState, event_type: str, **payload: object) -> None`
- [BacktestEngine._run_with_constraints](../../backtesting/simulator.py) — ligne 1012 : `def _run_with_constraints(self, *, open_df: pd.DataFrame, close: pd.DataFrame, high: pd.DataFrame, low: pd.DataFrame, signals_df: pd.DataFrame, volume: pd.DataFrame | None=None, sector_map: dict[str, str] | None=None, spread_df: pd.DataFrame | None=None) -> BacktestResult`
- [BacktestEngine._compute_atr](../../backtesting/simulator.py) — ligne 1365 : `def _compute_atr(high: pd.DataFrame, low: pd.DataFrame, close: pd.DataFrame, window: int=20) -> pd.DataFrame`
- [BacktestEngine._prepare_signals_by_day](../../backtesting/simulator.py) — ligne 1390 : `def _prepare_signals_by_day(self, signals_df: pd.DataFrame, trading_days: pd.DatetimeIndex) -> dict[pd.Timestamp, pd.DataFrame]`
- [BacktestEngine._apply_settlements](../../backtesting/simulator.py) — ligne 1415 : `def _apply_settlements(self, state: _RunState, day_idx: int) -> None`
- [BacktestEngine._select_candidate_rows](../../backtesting/simulator.py) — ligne 1422 : `def _select_candidate_rows(self, *, state: _RunState, trade_day: pd.Timestamp, day_signals: pd.DataFrame | None, close_columns: pd.Index, entries_allowed_by_breaker: bool, drawdown_allocation_scale: float, entries_allowed_by_regime: bool, diagnostics: BacktestDiagnostics) -> list[pd.Series]`
- [BacktestEngine._try_open_entries](../../backtesting/simulator.py) — ligne 1501 : `def _try_open_entries(self, *, state: _RunState, candidate_rows: list[pd.Series], open_df: pd.DataFrame, high_df: pd.DataFrame | None=None, low_df: pd.DataFrame, close: pd.DataFrame, trade_day: pd.Timestamp, day_idx: int, trading_days: pd.DatetimeIndex, adv_usd_df: pd.DataFrame | None, sector_map: dict[str, str], current_equity: float, drawdown_allocation_scale: float, diagnostics: BacktestDiagnostics, spread_df: pd.DataFrame | None=None) -> None`
- [BacktestEngine._try_close_positions](../../backtesting/simulator.py) — ligne 2140 : `def _try_close_positions(self, *, state: _RunState, close: pd.DataFrame, high: pd.DataFrame, low: pd.DataFrame, trade_day: pd.Timestamp, day_idx: int, trading_days: pd.DatetimeIndex, adv_usd_df: pd.DataFrame | None, rng: np.random.Generator | None, diagnostics: BacktestDiagnostics, spread_df: pd.DataFrame | None=None, current_equity: float=0.0, atr_df: pd.DataFrame | None=None) -> None`
- [BacktestEngine._accrue_margin_interest](../../backtesting/simulator.py) — ligne 2552 : `def _accrue_margin_interest(state: _RunState, *, annual_rate: float, sessions_per_year: int=252) -> float`
- [BacktestEngine._get_spread_bps](../../backtesting/simulator.py) — ligne 2574 : `def _get_spread_bps(self, spread_df: pd.DataFrame | None, trade_day: pd.Timestamp, symbol: str, *, fallback_bps: float=1.0) -> float`
- [BacktestEngine._get_adv_usd](../../backtesting/simulator.py) — ligne 2625 : `def _get_adv_usd(adv_usd_df: pd.DataFrame | None, trade_day: pd.Timestamp, symbol: str) -> float | None`
- [BacktestEngine._resolve_signal_quantity_override](../../backtesting/simulator.py) — ligne 2638 : `def _resolve_signal_quantity_override(self, row: pd.Series) -> float | None`
- [BacktestEngine._resolve_signal_target_weight](../../backtesting/simulator.py) — ligne 2664 : `def _resolve_signal_target_weight(row: pd.Series) -> float | None`
- [BacktestEngine._resolve_signal_float](../../backtesting/simulator.py) — ligne 2678 : `def _resolve_signal_float(row: pd.Series, column_name: str) -> float | None`
- [BacktestEngine._resolve_initial_protection_state](../../backtesting/simulator.py) — ligne 2689 : `def _resolve_initial_protection_state(self, *, row: pd.Series, entry_price: float, fallback_initial_stop_pct: float, side: str='buy') -> tuple[float | None, float | None]`
- [BacktestEngine._resolve_signal_text](../../backtesting/simulator.py) — ligne 2741 : `def _resolve_signal_text(row: pd.Series, column_name: str) -> str | None`
- [BacktestEngine._resolve_signal_timestamp](../../backtesting/simulator.py) — ligne 2751 : `def _resolve_signal_timestamp(row: pd.Series, column_name: str) -> pd.Timestamp | None`
- [BacktestEngine._resolve_signal_bool](../../backtesting/simulator.py) — ligne 2764 : `def _resolve_signal_bool(row: pd.Series, column_name: str) -> bool`
- [BacktestEngine._position_uses_replayed_protection](../../backtesting/simulator.py) — ligne 2776 : `def _position_uses_replayed_protection(position: _OpenPosition) -> bool`
- [BacktestEngine._resolve_max_gross_exposure_limit](../../backtesting/simulator.py) — ligne 2787 : `def _resolve_max_gross_exposure_limit(self, current_equity: float) -> float | None`
- [BacktestEngine._research_force_close_side_aware](../../backtesting/simulator.py) — ligne 2804 : `def _research_force_close_side_aware(self, cfg, state, trade_day: pd.Timestamp, close: pd.DataFrame, mtm_close: pd.DataFrame, diagnostics, current_equity: float) -> float`
- [BacktestEngine._mark_to_market](../../backtesting/simulator.py) — ligne 2900 : `def _mark_to_market(positions: dict[str, _OpenPosition], close: pd.DataFrame, trade_day: pd.Timestamp) -> float`
- [BacktestEngine._compute_net_notional](../../backtesting/simulator.py) — ligne 2924 : `def _compute_net_notional(positions: dict[str, _OpenPosition], close: pd.DataFrame, trade_day: pd.Timestamp) -> float`
- [BacktestEngine._compute_gross_notional](../../backtesting/simulator.py) — ligne 2944 : `def _compute_gross_notional(positions: dict[str, _OpenPosition], close: pd.DataFrame, trade_day: pd.Timestamp) -> float`
- [BacktestEngine._compute_gross_notional_by_side](../../backtesting/simulator.py) — ligne 2963 : `def _compute_gross_notional_by_side(positions: dict[str, _OpenPosition], close: pd.DataFrame, trade_day: pd.Timestamp, *, short: bool) -> float`

## `backtesting/statistical_validation.py`

Source SHA-256 : `ead352d79090cf23a33a63d2f03a9207ff0d4f39095a2f61fe64a4d29b054fda`

- [BootstrapResult](../../backtesting/statistical_validation.py) — ligne 34 : `class BootstrapResult`
- [BootstrapResult.to_dict](../../backtesting/statistical_validation.py) — ligne 48 : `def to_dict(self) -> dict[str, float]`
- [bootstrap_trades](../../backtesting/statistical_validation.py) — ligne 65 : `def bootstrap_trades(closed_trades_df: pd.DataFrame, *, n_iterations: int=1000, sample_size: int | None=None, initial_equity: float=100000.0, confidence: float=0.95, seed: int | None=0) -> BootstrapResult`
- [parameter_sensitivity](../../backtesting/statistical_validation.py) — ligne 152 : `def parameter_sensitivity(base_params: dict[str, float], metric_fn: Callable[[dict[str, float]], float], *, perturbation: float=0.1, parameters: list[str] | None=None) -> pd.DataFrame`
- [WalkForwardPlan](../../backtesting/statistical_validation.py) — ligne 218 : `class WalkForwardPlan`
- [WalkForwardPlan.to_dict](../../backtesting/statistical_validation.py) — ligne 247 : `def to_dict(self) -> dict[str, object]`
- [DeflatedSharpeResult](../../backtesting/statistical_validation.py) — ligne 262 : `class DeflatedSharpeResult`
- [DeflatedSharpeResult.to_dict](../../backtesting/statistical_validation.py) — ligne 273 : `def to_dict(self) -> dict[str, float]`
- [deflated_sharpe_ratio](../../backtesting/statistical_validation.py) — ligne 285 : `def deflated_sharpe_ratio(returns: np.ndarray, *, n_trials: int=100, annual_factor: float=252.0) -> DeflatedSharpeResult`
- [block_bootstrap_sharpe](../../backtesting/statistical_validation.py) — ligne 354 : `def block_bootstrap_sharpe(returns: np.ndarray, *, n_iterations: int=1000, block_size: int=10, confidence: float=0.95, annual_factor: float=252.0, seed: int | None=42) -> dict[str, float]`
- [multiple_testing_correction](../../backtesting/statistical_validation.py) — ligne 413 : `def multiple_testing_correction(p_values: list[float], *, method: str='bonferroni') -> list[float]`
- [PromotionScoreResult](../../backtesting/statistical_validation.py) — ligne 453 : `class PromotionScoreResult`
- [PromotionScoreResult.to_dict](../../backtesting/statistical_validation.py) — ligne 468 : `def to_dict(self) -> dict[str, float]`
- [compute_promotion_score](../../backtesting/statistical_validation.py) — ligne 480 : `def compute_promotion_score(*, sharpe: float, sortino: float, calmar: float, max_drawdown_pct: float, profit_factor: float, win_rate: float, n_trades: int, cost_ratio: float, fold_stability: float, sharpe_deflated: float | None=None) -> PromotionScoreResult`
- [_skewness](../../backtesting/statistical_validation.py) — ligne 575 : `def _skewness(x: np.ndarray) -> float`
- [_kurtosis](../../backtesting/statistical_validation.py) — ligne 586 : `def _kurtosis(x: np.ndarray) -> float`

## `backtesting/trading_constraints.py`

Source SHA-256 : `40528c3f24dac5baa4d94d6985f28493cf349228b6e25e6494f1e30eb4d7a1a8`

- [TradingConstraintConfig](../../backtesting/trading_constraints.py) — ligne 11 : `class TradingConstraintConfig`
- [TradingConstraintConfig.__post_init__](../../backtesting/trading_constraints.py) — ligne 26 : `def __post_init__(self) -> None`
- [TradingConstraintConfig.restrict_same_day_exit](../../backtesting/trading_constraints.py) — ligne 37 : `def restrict_same_day_exit(self) -> bool`
- [TradingConstraintConfig.use_settled_cash_only](../../backtesting/trading_constraints.py) — ligne 41 : `def use_settled_cash_only(self) -> bool`
- [TradingConstraintConfig.requires_stateful_simulation](../../backtesting/trading_constraints.py) — ligne 44 : `def requires_stateful_simulation(self, equity: float) -> bool`
- [TradingConstraintConfig.to_dict](../../backtesting/trading_constraints.py) — ligne 48 : `def to_dict(self) -> dict[str, int | str | bool]`
- [build_current_trading_constraints](../../backtesting/trading_constraints.py) — ligne 58 : `def build_current_trading_constraints(*, account_type: AccountType, swing_only: bool=False, cash_settlement_days: int=1) -> TradingConstraintConfig`
- [TieredCommissionConfig](../../backtesting/trading_constraints.py) — ligne 76 : `class TieredCommissionConfig`
- [TieredCommissionConfig.compute_commission_usd](../../backtesting/trading_constraints.py) — ligne 92 : `def compute_commission_usd(self, notional_usd: float) -> float`
- [TieredCommissionConfig.effective_bps](../../backtesting/trading_constraints.py) — ligne 98 : `def effective_bps(self, notional_usd: float) -> float`
- [TieredCommissionConfig.is_viable](../../backtesting/trading_constraints.py) — ligne 105 : `def is_viable(self, notional_usd: float, max_bps: float=25.0) -> bool`
- [resolve_commission_preset](../../backtesting/trading_constraints.py) — ligne 123 : `def resolve_commission_preset(equity: float) -> TieredCommissionConfig`

## `backtesting/walk_forward.py`

Source SHA-256 : `c4a744bef0b71ea9827d3fee1f8a1501191abea2c2fa301101a5c9b742380a0d`

- [WalkForwardWeights](../../backtesting/walk_forward.py) — ligne 44 : `class WalkForwardWeights`
- [_candidate_roots](../../backtesting/walk_forward.py) — ligne 54 : `def _candidate_roots(search_roots: Iterable[Path] | None=None) -> list[Path]`
- [_extract_weight](../../backtesting/walk_forward.py) — ligne 65 : `def _extract_weight(payload: dict[str, Any], *names: str) -> float | None`
- [load_walk_forward_weights](../../backtesting/walk_forward.py) — ligne 77 : `def load_walk_forward_weights(path: Path) -> WalkForwardWeights | None`
- [validate_walk_forward_weights](../../backtesting/walk_forward.py) — ligne 104 : `def validate_walk_forward_weights(weights: WalkForwardWeights, *, min_weight: float=WEIGHT_MIN, max_weight: float=WEIGHT_MAX, strict: bool=False) -> WalkForwardWeights`
- [resolve_latest_walk_forward_weights](../../backtesting/walk_forward.py) — ligne 188 : `def resolve_latest_walk_forward_weights(search_roots: Iterable[Path] | None=None) -> WalkForwardWeights | None`
- [RiskParamResult](../../backtesting/walk_forward.py) — ligne 212 : `class RiskParamResult`
- [walk_forward_risk_params](../../backtesting/walk_forward.py) — ligne 231 : `def walk_forward_risk_params(returns_series: 'pd.Series[float]', param_grid: dict[str, list[Any]], *, metric_name: str='sharpe', min_observations: int=20) -> RiskParamResult`
- [apply_walk_forward_weights](../../backtesting/walk_forward.py) — ligne 342 : `def apply_walk_forward_weights(scores_df: pd.DataFrame, weights: WalkForwardWeights | None) -> pd.DataFrame`

## `backtesting/walk_forward_engine.py`

Source SHA-256 : `28fe6fc759ac76d66d516431607dccdf35339a017f41807d53e6891157252571`

- [WalkForwardConfig](../../backtesting/walk_forward_engine.py) — ligne 40 : `class WalkForwardConfig`
- [FoldFinancials](../../backtesting/walk_forward_engine.py) — ligne 72 : `class FoldFinancials`
- [FoldFinancials.to_dict](../../backtesting/walk_forward_engine.py) — ligne 123 : `def to_dict(self) -> dict[str, object]`
- [WalkForwardResult](../../backtesting/walk_forward_engine.py) — ligne 153 : `class WalkForwardResult`
- [WalkForwardResult.to_dict](../../backtesting/walk_forward_engine.py) — ligne 183 : `def to_dict(self) -> dict[str, object]`
- [_compute_equity_metrics](../../backtesting/walk_forward_engine.py) — ligne 216 : `def _compute_equity_metrics(daily_returns: np.ndarray, annual_factor: int=252, risk_free_rate: float=0.0) -> dict[str, float]`
- [_compute_trade_metrics](../../backtesting/walk_forward_engine.py) — ligne 265 : `def _compute_trade_metrics(closed_trades_df: pd.DataFrame, initial_equity: float) -> dict[str, float]`
- [run_walk_forward_fold](../../backtesting/walk_forward_engine.py) — ligne 330 : `def run_walk_forward_fold(plan: Any, config: Any, wf_config: WalkForwardConfig, data_provider: DataProviderFn, fold_index: int=0) -> FoldFinancials | None`
- [_simulate_fold_execution](../../backtesting/walk_forward_engine.py) — ligne 426 : `def _simulate_fold_execution(entries: list[Any], signals: list[pd.DataFrame], close_df: pd.DataFrame | None, high_df: pd.DataFrame | None, low_df: pd.DataFrame | None, volume_df: pd.DataFrame | None, wf_config: WalkForwardConfig, fold_index: int, plan: Any) -> FoldFinancials | None`
- [run_walk_forward](../../backtesting/walk_forward_engine.py) — ligne 515 : `def run_walk_forward(plan_folds: list[Any], config: Any, wf_config: WalkForwardConfig | None=None, data_provider: DataProviderFn | None=None, n_trials: int=100) -> WalkForwardResult`
- [WalkForwardReport](../../backtesting/walk_forward_engine.py) — ligne 638 : `class WalkForwardReport`
- [WalkForwardReport.to_dict](../../backtesting/walk_forward_engine.py) — ligne 649 : `def to_dict(self) -> dict[str, object]`
- [WalkForwardReport._compute_gates](../../backtesting/walk_forward_engine.py) — ligne 659 : `def _compute_gates(self) -> dict[str, object]`
- [WalkForwardReport.to_json](../../backtesting/walk_forward_engine.py) — ligne 708 : `def to_json(self, filepath: str) -> None`
- [_json_default](../../backtesting/walk_forward_engine.py) — ligne 722 : `def _json_default(obj: object) -> object`
- [generate_walk_forward_report](../../backtesting/walk_forward_engine.py) — ligne 733 : `def generate_walk_forward_report(result: WalkForwardResult, config: Any, plan_folds: list[Any], output_path: str | None=None) -> WalkForwardReport`
- [create_db_data_provider](../../backtesting/walk_forward_engine.py) — ligne 786 : `def create_db_data_provider(scores_df: pd.DataFrame, predictions_df: pd.DataFrame | None=None, close_df: pd.DataFrame | None=None, high_df: pd.DataFrame | None=None, low_df: pd.DataFrame | None=None, volume_df: pd.DataFrame | None=None) -> DataProviderFn`

## `backtesting/weights_calibration.py`

Source SHA-256 : `d6c94702ba2a6669b35ca20b362c50b830e56c37ae70dd2a281a25c6b1d47197`

- [normalize_market_regime_mode](../../backtesting/weights_calibration.py) — ligne 57 : `def normalize_market_regime_mode(value: object) -> str`
- [metric_information_coefficient](../../backtesting/weights_calibration.py) — ligne 68 : `def metric_information_coefficient(predictions: np.ndarray, forward_returns: np.ndarray) -> float`
- [metric_hit_rate](../../backtesting/weights_calibration.py) — ligne 79 : `def metric_hit_rate(predictions: np.ndarray, forward_returns: np.ndarray, *, threshold: float=0.5) -> float`
- [metric_strategy_sharpe](../../backtesting/weights_calibration.py) — ligne 96 : `def metric_strategy_sharpe(strategy_returns: np.ndarray) -> float`
- [metric_strategy_log_growth](../../backtesting/weights_calibration.py) — ligne 107 : `def metric_strategy_log_growth(strategy_returns: np.ndarray) -> float`
- [CalibrationCandidate](../../backtesting/weights_calibration.py) — ligne 126 : `class CalibrationCandidate`
- [CalibrationResult](../../backtesting/weights_calibration.py) — ligne 132 : `class CalibrationResult`
- [CalibrationResult.to_payload](../../backtesting/weights_calibration.py) — ligne 142 : `def to_payload(self) -> dict[str, Any]`
- [EmpiricalRiskCalibrationRun](../../backtesting/weights_calibration.py) — ligne 159 : `class EmpiricalRiskCalibrationRun`
- [CalibrationSegmentDrift](../../backtesting/weights_calibration.py) — ligne 186 : `class CalibrationSegmentDrift`
- [_conviction_grid](../../backtesting/weights_calibration.py) — ligne 203 : `def _conviction_grid(step: float=0.05) -> Iterable[ConvictionWeights]`
- [_sentiment_grid](../../backtesting/weights_calibration.py) — ligne 212 : `def _sentiment_grid(step: float=0.05) -> Iterable[SentimentFusionWeights]`
- [_kelly_grid](../../backtesting/weights_calibration.py) — ligne 247 : `def _kelly_grid(*, kelly_fraction_multipliers: Sequence[float], min_effective_probabilities: Sequence[float], assumed_payoff_ratios: Sequence[float]) -> Iterable[dict[str, float]]`
- [_subtract_months](../../backtesting/weights_calibration.py) — ligne 263 : `def _subtract_months(reference: date, months: int) -> date`
- [_build_segment_key](../../backtesting/weights_calibration.py) — ligne 273 : `def _build_segment_key(*, market_regime_mode: str, horizon_days: int, lookback_months: int | None) -> str`
- [_compute_relative_drift](../../backtesting/weights_calibration.py) — ligne 282 : `def _compute_relative_drift(current: float, reference: float) -> float | None`
- [_evaluate_live_governance](../../backtesting/weights_calibration.py) — ligne 288 : `def _evaluate_live_governance(dataset: pd.DataFrame, *, min_observations: int, min_snapshot_days: int, min_symbols: int) -> tuple[bool, str | None, int, int]`
- [compute_segment_drifts](../../backtesting/weights_calibration.py) — ligne 308 : `def compute_segment_drifts(runs: Sequence[EmpiricalRiskCalibrationRun], *, reference_horizon_days: int | None=None, reference_lookback_months: int | None=None) -> list[CalibrationSegmentDrift]`
- [calibrate_conviction](../../backtesting/weights_calibration.py) — ligne 392 : `def calibrate_conviction(*, quant_scores: Sequence[float], predicted_proba: Sequence[float | None], forward_returns: Sequence[float], metric_name: str='ic', grid_step: float=0.05, window: tuple[date, date] | None=None, market_regime_mode: str=MARKET_REGIME_ALL) -> CalibrationResult`
- [calibrate_sentiment](../../backtesting/weights_calibration.py) — ligne 452 : `def calibrate_sentiment(*, quant_scores: Sequence[float], sentiment_signal: Sequence[float], macro_signal: Sequence[float], forward_returns: Sequence[float], metric_name: str='ic', grid_step: float=0.1, window: tuple[date, date] | None=None, market_regime_mode: str=MARKET_REGIME_ALL) -> CalibrationResult`
- [_compute_kelly_fraction](../../backtesting/weights_calibration.py) — ligne 516 : `def _compute_kelly_fraction(predicted_proba: np.ndarray, historical_win_rate: np.ndarray, *, kelly_fraction_multiplier: float, min_effective_probability: float, assumed_payoff_ratio: float, prediction_confidence_weight: float=0.6, historical_win_rate_weight: float=0.4, max_position_weight: float=0.1, max_kelly_fraction: float=0.25) -> np.ndarray`
- [_weighted_daily_strategy_returns](../../backtesting/weights_calibration.py) — ligne 538 : `def _weighted_daily_strategy_returns(snapshot_dates: Sequence[date | datetime | str], conviction_scores: np.ndarray, kelly_fractions: np.ndarray, forward_returns: np.ndarray, *, top_n: int) -> np.ndarray`
- [calibrate_conviction_kelly](../../backtesting/weights_calibration.py) — ligne 571 : `def calibrate_conviction_kelly(*, snapshot_dates: Sequence[date | datetime | str], quant_scores: Sequence[float], predicted_proba: Sequence[float | None], historical_win_rate: Sequence[float | None], forward_returns: Sequence[float], metric_name: str='sharpe', conviction_grid_step: float=0.05, kelly_fraction_multipliers: Sequence[float]=(0.1, 0.25, 0.5), min_effective_probabilities: Sequence[float]=(0.5, 0.52, 0.55), assumed_payoff_ratios: Sequence[float]=(1.0, 1.5, 2.0), top_n: int=20, max_position_weight: float=0.1, window: tuple[date, date] | None=None, market_regime_mode: str=MARKET_REGIME_ALL) -> CalibrationResult`
- [calibrate_conviction_kelly_short](../../backtesting/weights_calibration.py) — ligne 678 : `def calibrate_conviction_kelly_short(*, snapshot_dates: Sequence[date | datetime | str], quant_scores: Sequence[float], predicted_proba_short: Sequence[float | None], historical_win_rate: Sequence[float | None], forward_returns: Sequence[float], metric_name: str='sharpe', conviction_grid_step: float=0.05, kelly_fraction_multipliers: Sequence[float]=(0.1, 0.25, 0.5), min_effective_probabilities: Sequence[float]=(0.5, 0.52, 0.55), assumed_payoff_ratios: Sequence[float]=(1.0, 1.5, 2.0), top_n: int=20, max_position_weight: float=0.1, window: tuple[date, date] | None=None, market_regime_mode: str=MARKET_REGIME_ALL) -> CalibrationResult`
- [EmpiricalRiskCalibrator](../../backtesting/weights_calibration.py) — ligne 787 : `class EmpiricalRiskCalibrator`
- [EmpiricalRiskCalibrator.__init__](../../backtesting/weights_calibration.py) — ligne 790 : `def __init__(self, engine: Any | None=None) -> None`
- [EmpiricalRiskCalibrator._get_table_columns](../../backtesting/weights_calibration.py) — ligne 797 : `def _get_table_columns(self, table_name: str) -> set[str]`
- [EmpiricalRiskCalibrator._resolve_market_regime_modes](../../backtesting/weights_calibration.py) — ligne 806 : `def _resolve_market_regime_modes(self, snapshot_dates: Sequence[pd.Timestamp]) -> dict[date, str]`
- [EmpiricalRiskCalibrator.load_dataset](../../backtesting/weights_calibration.py) — ligne 854 : `def load_dataset(self, *, start_date: date, end_date: date, horizon_days: int=5, selected_only: bool=True, include_market_regime: bool=True) -> pd.DataFrame`
- [EmpiricalRiskCalibrator._build_run_summary](../../backtesting/weights_calibration.py) — ligne 1058 : `def _build_run_summary(self, *, calibration: CalibrationResult, dataset: pd.DataFrame, daily_returns: np.ndarray, best_weights: dict[str, float], output_path: Path, horizon_days: int, lookback_months: int | None, calibration_batch_id: str | None, min_live_observations: int, min_live_snapshot_days: int, min_live_symbols: int) -> EmpiricalRiskCalibrationRun`
- [EmpiricalRiskCalibrator._build_backtest_signals](../../backtesting/weights_calibration.py) — ligne 1119 : `def _build_backtest_signals(self, dataset: pd.DataFrame, conviction_weights: ConvictionWeights, top_n: int, *, direction: str='long') -> pd.DataFrame`
- [EmpiricalRiskCalibrator.evaluate_kelly_in_backtest](../../backtesting/weights_calibration.py) — ligne 1168 : `def evaluate_kelly_in_backtest(self, dataset: pd.DataFrame, conviction_weights: ConvictionWeights, kelly_params: dict[str, float], top_n: int, start_date: date, end_date: date, *, initial_equity: float=100000.0, direction: str='long', enforce_net_exposure: bool=False, net_exposure_target: float | None=None, net_exposure_tolerance: float=0.1) -> dict[str, float]`
- [EmpiricalRiskCalibrator.calibrate_kelly_via_backtest](../../backtesting/weights_calibration.py) — ligne 1249 : `def calibrate_kelly_via_backtest(self, dataset: pd.DataFrame, conviction_weights: ConvictionWeights, top_n: int, start_date: date, end_date: date, *, initial_equity: float=100000.0, direction: str='long', metric_name: str='sharpe', enforce_net_exposure: bool=False, net_exposure_target: float | None=None, net_exposure_tolerance: float=0.1) -> dict[str, float] | None`
- [EmpiricalRiskCalibrator.walk_forward_optimize](../../backtesting/weights_calibration.py) — ligne 1330 : `def walk_forward_optimize(self, *, start_date: date, end_date: date, output_dir: str | Path, top_n: int=20, horizon_days: int=5, metric_name: str='sharpe', conviction_grid_step: float=0.1, kelly_fraction_multipliers: Sequence[float]=(0.1, 0.25, 0.5), min_effective_probabilities: Sequence[float]=(0.5, 0.52, 0.55), assumed_payoff_ratios: Sequence[float]=(1.0, 1.5, 2.0), selected_only: bool=True, min_train_days: int=252, test_days: int=63, step_days: int | None=None, initial_equity: float=100000.0, use_backtest_kelly: bool=False, top_n_long: int | None=None, top_n_short: int | None=None, enforce_net_exposure: bool=False, net_exposure_target: float | None=None) -> dict[str, Any]`
- [EmpiricalRiskCalibrator.walk_forward_backtest](../../backtesting/weights_calibration.py) — ligne 1586 : `def walk_forward_backtest(self, *, start_date: date, end_date: date, output_dir: str | Path, top_n: int=20, horizon_days: int=5, metric_name: str='sharpe', conviction_grid_step: float=0.1, kelly_fraction_multipliers: Sequence[float]=(0.1, 0.25, 0.5), min_effective_probabilities: Sequence[float]=(0.5, 0.52, 0.55), assumed_payoff_ratios: Sequence[float]=(1.0, 1.5, 2.0), selected_only: bool=True, market_regime_mode: str=MARKET_REGIME_ALL, dataset: pd.DataFrame | None=None, lookback_months: int | None=None, calibration_batch_id: str | None=None, min_live_observations: int=250, min_live_snapshot_days: int=20, min_live_symbols: int=10, use_backtest_kelly: bool=False, top_n_long: int | None=None, top_n_short: int | None=None, enforce_net_exposure: bool=False, net_exposure_target: float | None=None, net_exposure_tolerance: float=0.1) -> tuple[EmpiricalRiskCalibrationRun, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, str]]`
- [EmpiricalRiskCalibrator.walk_forward_backtests_by_regime](../../backtesting/weights_calibration.py) — ligne 1887 : `def walk_forward_backtests_by_regime(self, *, start_date: date, end_date: date, output_dir: str | Path, top_n: int=20, horizon_days: int=5, metric_name: str='sharpe', conviction_grid_step: float=0.1, kelly_fraction_multipliers: Sequence[float]=(0.1, 0.25, 0.5), min_effective_probabilities: Sequence[float]=(0.5, 0.52, 0.55), assumed_payoff_ratios: Sequence[float]=(1.0, 1.5, 2.0), selected_only: bool=True) -> dict[str, tuple[EmpiricalRiskCalibrationRun, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, str]]]`
- [EmpiricalRiskCalibrator.walk_forward_backtests_by_segment](../../backtesting/weights_calibration.py) — ligne 1943 : `def walk_forward_backtests_by_segment(self, *, end_date: date, output_dir: str | Path, horizon_days_values: Sequence[int], lookback_months_values: Sequence[int], top_n: int=20, metric_name: str='sharpe', conviction_grid_step: float=0.1, kelly_fraction_multipliers: Sequence[float]=(0.1, 0.25, 0.5), min_effective_probabilities: Sequence[float]=(0.5, 0.52, 0.55), assumed_payoff_ratios: Sequence[float]=(1.0, 1.5, 2.0), selected_only: bool=True, min_live_observations: int=250, min_live_snapshot_days: int=20, min_live_symbols: int=10, calibration_batch_id: str | None=None) -> dict[str, tuple[EmpiricalRiskCalibrationRun, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, str]]]`
- [persist_calibration_run](../../backtesting/weights_calibration.py) — ligne 2039 : `def persist_calibration_run(result: CalibrationResult, *, engine: Any, git_sha: str | None=None, run_id: str | None=None, run_summary: EmpiricalRiskCalibrationRun | None=None) -> str`
- [persist_segment_drifts](../../backtesting/weights_calibration.py) — ligne 2148 : `def persist_segment_drifts(drifts: Sequence[CalibrationSegmentDrift], *, engine: Any) -> int`
