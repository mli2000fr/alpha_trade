# Inventaire API — selector

Extraction AST du 2026-10-10 ; aucune importation ni exécution métier.

Classes, fonctions de module et méthodes déclarées ; fonctions imbriquées exclues.
Les symboles `_...` sont internes. Signature présente ≠ API publique stable.

## `selector/__init__.py`

Source SHA-256 : `b5fda683ae902d735af7e1a8a240567721506e043366a82ee00ebf2235e1b48e`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `selector/ablation.py`

Source SHA-256 : `524c6486a1509452af999109b2c79e53016b4c9cc3f1b371c3c16a511ccceb06`

- [RuntimeSelectorVariant](../../selector/ablation.py) — ligne 24 : `class RuntimeSelectorVariant`
- [resolve_runtime_variants](../../selector/ablation.py) — ligne 34 : `def resolve_runtime_variants(*, base_config: AlphaScannerConfig, primary_runtime_config: AlphaScannerConfig, data_quality_gate: dict[str, object] | None=None) -> tuple[RuntimeSelectorVariant, ...]`
- [_extract_selected_symbols](../../selector/ablation.py) — ligne 86 : `def _extract_selected_symbols(selected_df: pd.DataFrame) -> list[str]`
- [_build_variant_payload](../../selector/ablation.py) — ligne 93 : `def _build_variant_payload(*, variant: RuntimeSelectorVariant, selected_df: pd.DataFrame, rejected_by_filter: dict[str, int], primary_symbols: list[str] | None=None, include_selected_symbols: bool) -> dict[str, object]`
- [build_ablation_summary_and_artifact](../../selector/ablation.py) — ligne 140 : `def build_ablation_summary_and_artifact(*, plan: SelectorAblationPlan, runtime_variants: tuple[RuntimeSelectorVariant, ...], selected_by_variant: dict[str, pd.DataFrame], rejected_by_filter_by_variant: dict[str, dict[str, int]], artifact_path: str | None) -> tuple[dict[str, object], dict[str, object]]`
- [write_ablation_artifact](../../selector/ablation.py) — ligne 206 : `def write_ablation_artifact(*, plan: SelectorAblationPlan, artifact_payload: dict[str, object], artifact_stem: str) -> str`

## `selector/alpha_scanner.py`

Source SHA-256 : `5c947ac2cca1db4bcb8df941ea05c225ed93933bca7c043321843f53af889cc3`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `selector/cli.py`

Source SHA-256 : `bd9aee8f5c5b1a9f55269a5d27daa29f6b17d1720366810bb0ac7b5a6947462e`

- [_build_arg_parser](../../selector/cli.py) — ligne 31 : `def _build_arg_parser() -> argparse.ArgumentParser`
- [_build_config_from_args](../../selector/cli.py) — ligne 100 : `def _build_config_from_args(args: argparse.Namespace) -> AlphaScannerConfig`
- [main](../../selector/cli.py) — ligne 164 : `def main() -> None`

## `selector/config.py`

Source SHA-256 : `f57f1a6e56277259720d2f8833f840cb8e5ff9f75231b12df02f1d9d90ea7d15`

- [_normalize_ablation_filter_keys](../../selector/config.py) — ligne 77 : `def _normalize_ablation_filter_keys(filter_keys: tuple[str, ...] | list[str]) -> tuple[str, ...]`
- [_normalize_ablation_overrides](../../selector/config.py) — ligne 94 : `def _normalize_ablation_overrides(raw_overrides: dict[str, object] | None) -> dict[str, object]`
- [SelectorVariantSpec](../../selector/config.py) — ligne 106 : `class SelectorVariantSpec`
- [SelectorVariantSpec.__post_init__](../../selector/config.py) — ligne 112 : `def __post_init__(self) -> None`
- [SelectorAblationPlan](../../selector/config.py) — ligne 130 : `class SelectorAblationPlan`
- [SelectorAblationPlan.__post_init__](../../selector/config.py) — ligne 135 : `def __post_init__(self) -> None`
- [build_selector_variant_spec_from_mapping](../../selector/config.py) — ligne 157 : `def build_selector_variant_spec_from_mapping(payload: dict[str, object]) -> SelectorVariantSpec`
- [build_selector_ablation_plan_from_mapping](../../selector/config.py) — ligne 173 : `def build_selector_ablation_plan_from_mapping(payload: dict[str, object]) -> SelectorAblationPlan`
- [load_selector_ablation_plan_from_file](../../selector/config.py) — ligne 193 : `def load_selector_ablation_plan_from_file(file_path: str | Path) -> SelectorAblationPlan`
- [get_ablation_filter_config_overrides](../../selector/config.py) — ligne 207 : `def get_ablation_filter_config_overrides(filter_key: str) -> dict[str, object]`
- [is_filter_effectively_enabled](../../selector/config.py) — ligne 216 : `def is_filter_effectively_enabled(config: AlphaScannerConfig, filter_key: str) -> bool`
- [apply_variant_spec_to_config](../../selector/config.py) — ligne 245 : `def apply_variant_spec_to_config(base_config: AlphaScannerConfig, variant: SelectorVariantSpec) -> AlphaScannerConfig`
- [compute_config_diff](../../selector/config.py) — ligne 256 : `def compute_config_diff(base_config: AlphaScannerConfig, other_config: AlphaScannerConfig) -> dict[str, object]`
- [AlphaScannerConfig](../../selector/config.py) — ligne 280 : `class AlphaScannerConfig`
- [AlphaScannerConfig.from_filter_profile](../../selector/config.py) — ligne 338 : `def from_filter_profile(cls, profile: StrictFilterProfile, **overrides: object) -> AlphaScannerConfig`
- [AlphaScannerConfig.strict_swing_cash](../../selector/config.py) — ligne 357 : `def strict_swing_cash(cls, **overrides: object) -> AlphaScannerConfig`
- [AlphaScannerConfig._yaml_defaults](../../selector/config.py) — ligne 361 : `def _yaml_defaults() -> dict[str, object]`
- [AlphaScannerConfig.__post_init__](../../selector/config.py) — ligne 370 : `def __post_init__(self) -> None`
- [resolve_symmetric_grid](../../selector/config.py) — ligne 467 : `def resolve_symmetric_grid(label: str) -> tuple[int, int]`

## `selector/db_io.py`

Source SHA-256 : `87951d0fa33c768c7c5bdb1c9af760b702c2a08fd9d118727ab57dee8c6295ce`

- [_build_data_quality_check_payload](../../selector/db_io.py) — ligne 123 : `def _build_data_quality_check_payload(*, enabled: bool, fallback_mode: str, filter_key: str, healthy: bool, reason: str, recommended_action: str, **extra: object) -> dict[str, object]`
- [_has_table](../../selector/db_io.py) — ligne 150 : `def _has_table(engine: Engine, table_name: str) -> bool`
- [get_table_columns](../../selector/db_io.py) — ligne 158 : `def get_table_columns(engine: Engine, table_name: str, *, fallback_columns: set[str] | None=None) -> set[str]`
- [_read_scalar_date](../../selector/db_io.py) — ligne 171 : `def _read_scalar_date(engine: Engine, stmt, params: dict[str, object] | None=None) -> date | None`
- [build_data_quality_gate](../../selector/db_io.py) — ligne 190 : `def build_data_quality_gate(engine: Engine, config: AlphaScannerConfig, *, reference_date: date | None=None) -> dict[str, object]`
- [_build_quotes_quality_check](../../selector/db_io.py) — ligne 219 : `def _build_quotes_quality_check(engine: Engine, config: AlphaScannerConfig, reference_date: date) -> dict[str, object]`
- [_build_earnings_quality_check](../../selector/db_io.py) — ligne 274 : `def _build_earnings_quality_check(engine: Engine, config: AlphaScannerConfig, reference_date: date) -> dict[str, object]`
- [_build_market_cap_quality_check](../../selector/db_io.py) — ligne 349 : `def _build_market_cap_quality_check(engine: Engine, config: AlphaScannerConfig, reference_date: date) -> dict[str, object]`
- [get_stock_metadata_columns](../../selector/db_io.py) — ligne 415 : `def get_stock_metadata_columns(engine: Engine) -> set[str]`
- [get_stock_quote_snapshots_columns](../../selector/db_io.py) — ligne 426 : `def get_stock_quote_snapshots_columns(engine: Engine) -> set[str]`
- [fetch_market_data](../../selector/db_io.py) — ligne 436 : `def fetch_market_data(engine: Engine, config: AlphaScannerConfig, symbols: Sequence[str]) -> pd.DataFrame`
- [fetch_scores](../../selector/db_io.py) — ligne 463 : `def fetch_scores(engine: Engine, config: AlphaScannerConfig, symbols: Sequence[str]) -> pd.DataFrame`
- [fetch_instrument_metadata](../../selector/db_io.py) — ligne 502 : `def fetch_instrument_metadata(engine: Engine, available_columns: set[str], symbols: Sequence[str]) -> pd.DataFrame`
- [load_benchmark_returns](../../selector/db_io.py) — ligne 551 : `def load_benchmark_returns(engine: Engine, config: AlphaScannerConfig, start_date: date, end_date: date) -> pd.DataFrame`
- [fetch_quote_snapshots](../../selector/db_io.py) — ligne 580 : `def fetch_quote_snapshots(engine: Engine, available_columns: set[str], symbols: Sequence[str], *, reference_date: date | None=None) -> pd.DataFrame`
- [fetch_next_earnings](../../selector/db_io.py) — ligne 671 : `def fetch_next_earnings(engine: Engine, config: AlphaScannerConfig, symbols: Sequence[str], *, reference_date: date | None=None) -> pd.DataFrame`
- [_classify_preselection_rejection_reason](../../selector/db_io.py) — ligne 721 : `def _classify_preselection_rejection_reason(row: Mapping[str, object], config: AlphaScannerConfig, *, history_status_enabled: bool) -> str | None`
- [build_preselection_rejection_audit](../../selector/db_io.py) — ligne 759 : `def build_preselection_rejection_audit(engine: Engine, config: AlphaScannerConfig, metadata_columns: set[str], *, sample_limit: int=PRESELECTION_AUDIT_SAMPLE_LIMIT) -> dict[str, object]`
- [iter_eligible_symbol_chunks](../../selector/db_io.py) — ligne 880 : `def iter_eligible_symbol_chunks(engine: Engine, config: AlphaScannerConfig, metadata_columns: set[str]) -> Iterator[list[str]]`
- [reset_selector_outputs](../../selector/db_io.py) — ligne 958 : `def reset_selector_outputs(engine: Engine, config: AlphaScannerConfig) -> None`
- [prepare_scores_snapshot](../../selector/db_io.py) — ligne 985 : `def prepare_scores_snapshot(scored_df: pd.DataFrame | None) -> list[dict[str, object]]`
- [update_database](../../selector/db_io.py) — ligne 1017 : `def update_database(engine: Engine, config: AlphaScannerConfig, selected_df: pd.DataFrame, scored_df: pd.DataFrame | None=None, *, progress: Callable[..., None] | None=None, snapshot_date_override: date | None=None) -> int`

## `selector/dip_filter.py`

Source SHA-256 : `28f968e1b1658856001f3ebb04f1134d92a9f00e6434e8ebe0ecef9e97eef7cc`

- [_load_yaml_config](../../selector/dip_filter.py) — ligne 67 : `def _load_yaml_config() -> dict[str, Any]`
- [load_dip_filter_config](../../selector/dip_filter.py) — ligne 77 : `def load_dip_filter_config(execution_context: str) -> dict[str, Any]`
- [_rank_column](../../selector/dip_filter.py) — ligne 96 : `def _rank_column(config: dict[str, Any], best_h: int | None=None) -> str`
- [_dip_pass](../../selector/dip_filter.py) — ligne 107 : `def _dip_pass(ret: float, dip_pct: float) -> bool`
- [load_rank_history_df](../../selector/dip_filter.py) — ligne 117 : `def load_rank_history_df(engine: Any, batch_id: str, trade_date: str, persist_days: int, rank_col: str, *, extra_days: int=0) -> pd.DataFrame`
- [load_oracle_rank_history_df](../../selector/dip_filter.py) — ligne 154 : `def load_oracle_rank_history_df(engine: Any, batch_id: str, trade_date: str, persist_days: int, *, extra_days: int=0) -> pd.DataFrame`
- [load_price_history_df](../../selector/dip_filter.py) — ligne 193 : `def load_price_history_df(engine: Any, symbols: list[str], trade_date: str, persist_days: int, *, extra_days: int=0) -> pd.DataFrame`
- [evaluate_dip_filter](../../selector/dip_filter.py) — ligne 233 : `def evaluate_dip_filter(symbol: str, as_of_date: str, rank_history: pd.DataFrame, price_history: pd.DataFrame, config: dict[str, Any], rank_col: str | None=None) -> bool`
- [filter_day_candidates](../../selector/dip_filter.py) — ligne 350 : `def filter_day_candidates(ranks_day: pd.DataFrame, engine: Any, batch_id: str, trade_date: str, config: dict[str, Any], *, best_h: int | None=None, rank_source: str='global') -> pd.DataFrame`

## `selector/explainability.py`

Source SHA-256 : `5eb01949f81899c6345385c594aa9cc9473fc59e91d700949a8370b0af5d4492`

- [_is_missing](../../selector/explainability.py) — ligne 17 : `def _is_missing(value: object) -> bool`
- [_clean_text](../../selector/explainability.py) — ligne 28 : `def _clean_text(value: object) -> str | None`
- [_clean_int](../../selector/explainability.py) — ligne 35 : `def _clean_int(value: object) -> int | None`
- [_clean_float](../../selector/explainability.py) — ligne 44 : `def _clean_float(value: object, *, digits: int=4) -> float | None`
- [_clean_date](../../selector/explainability.py) — ligne 53 : `def _clean_date(value: object) -> str | None`
- [build_selection_explainability_payload](../../selector/explainability.py) — ligne 62 : `def build_selection_explainability_payload(row: Mapping[str, object]) -> dict[str, object]`

## `selector/factors.py`

Source SHA-256 : `0645ce891febc0aa5838dbbb0d1ec8e088f265d73d05d752846496a81ab58cd2`

- [winsorize_and_normalize](../../selector/factors.py) — ligne 54 : `def winsorize_and_normalize(series: pd.Series | None, lower_pct: float=0.01, upper_pct: float=0.99) -> pd.Series`
- [compute_factor_frame](../../selector/factors.py) — ligne 88 : `def compute_factor_frame(market_data: pd.DataFrame, benchmark_returns: pd.DataFrame, config: AlphaScannerConfig) -> pd.DataFrame`

## `selector/filters.py`

Source SHA-256 : `c9d67822e992d8447ce77f4516dd66487eff16a08fbd0e0208f0669d60e48cb8`

- [apply_filters_with_stats](../../selector/filters.py) — ligne 62 : `def apply_filters_with_stats(merged_df: pd.DataFrame, config: AlphaScannerConfig) -> tuple[pd.DataFrame, dict[str, int]]`
- [log_filter_stats](../../selector/filters.py) — ligne 360 : `def log_filter_stats(stats: dict[str, int]) -> None`
- [enrich_and_filter_equities](../../selector/filters.py) — ligne 387 : `def enrich_and_filter_equities(merged_df: pd.DataFrame, metadata_df: pd.DataFrame) -> pd.DataFrame`
- [merge_optional_symbol_overlays](../../selector/filters.py) — ligne 488 : `def merge_optional_symbol_overlays(merged_df: pd.DataFrame, quotes_df: pd.DataFrame, earnings_df: pd.DataFrame) -> pd.DataFrame`

## `selector/ranking.py`

Source SHA-256 : `4f7d4cdb3a48cedf717ac35a61bdecea3d1cc7beb0e6befe47a62fd1f55d99a3`

- [_safe_float](../../selector/ranking.py) — ligne 135 : `def _safe_float(value: object) -> float | None`
- [_build_selection_explanation](../../selector/ranking.py) — ligne 144 : `def _build_selection_explanation(row: pd.Series) -> str`
- [_apply_selection_explainability](../../selector/ranking.py) — ligne 161 : `def _apply_selection_explainability(df: pd.DataFrame, *, trend_vcp_component: pd.Series, total_score_component: pd.Series, rsi_component: pd.Series, aux_mode_label: str) -> pd.DataFrame`
- [merge_scores](../../selector/ranking.py) — ligne 195 : `def merge_scores(computed_df: pd.DataFrame, scores_df: pd.DataFrame, config: AlphaScannerConfig) -> pd.DataFrame`
- [apply_factor_neutralization](../../selector/ranking.py) — ligne 271 : `def apply_factor_neutralization(df: pd.DataFrame, config: AlphaScannerConfig) -> pd.DataFrame`
- [apply_sector_neutrality](../../selector/ranking.py) — ligne 373 : `def apply_sector_neutrality(ranked_df: pd.DataFrame, config: AlphaScannerConfig) -> pd.DataFrame`
- [rank_and_select](../../selector/ranking.py) — ligne 440 : `def rank_and_select(merged_df: pd.DataFrame, config: AlphaScannerConfig) -> pd.DataFrame`
- [rank_and_select_short](../../selector/ranking.py) — ligne 471 : `def rank_and_select_short(merged_df: pd.DataFrame, config: AlphaScannerConfig, *, long_selected_symbols: set[str] | None=None) -> pd.DataFrame`

## `selector/regime_filters.py`

Source SHA-256 : `84f9c8655d462847791e9ecd426a381fe0d2ab291577a810ab387302594e6fc4`

- [_normalize_symbol_set](../../selector/regime_filters.py) — ligne 30 : `def _normalize_symbol_set(values: Iterable[object] | None) -> set[str]`
- [_normalize_sector_set](../../selector/regime_filters.py) — ligne 38 : `def _normalize_sector_set(values: Iterable[object] | None) -> set[str]`
- [apply_earnings_shield_to_candidates](../../selector/regime_filters.py) — ligne 46 : `def apply_earnings_shield_to_candidates(df: pd.DataFrame | None, snapshot: MarketRegimeSnapshot | None, *, score_column: str='score', symbol_column: str='symbol') -> pd.DataFrame`
- [apply_buyback_blackout_to_candidates](../../selector/regime_filters.py) — ligne 85 : `def apply_buyback_blackout_to_candidates(df: pd.DataFrame | None, snapshot: MarketRegimeSnapshot | None, *, score_column: str='score', symbol_column: str='symbol') -> pd.DataFrame`
- [apply_yield_filter_to_candidates](../../selector/regime_filters.py) — ligne 122 : `def apply_yield_filter_to_candidates(df: pd.DataFrame | None, snapshot: MarketRegimeSnapshot | None, *, sector_column: str='sector', symbol_column: str='symbol') -> pd.DataFrame`
- [apply_full_regime_to_candidates](../../selector/regime_filters.py) — ligne 150 : `def apply_full_regime_to_candidates(df: pd.DataFrame | None, snapshot: MarketRegimeSnapshot | None, *, score_column: str='score', sector_column: str='sector', symbol_column: str='symbol') -> pd.DataFrame`

## `selector/regime_scoring.py`

Source SHA-256 : `ad7f18a99932c0ee3404e279542d61ab73bf3b17e7e786d6af095833b978b260`

- [MomentumRotationState](../../selector/regime_scoring.py) — ligne 82 : `class MomentumRotationState`
- [MomentumRotationState.__init__](../../selector/regime_scoring.py) — ligne 98 : `def __init__(self, lookback_weeks: int=DEFAULT_ROTATION_LOOKBACK_WEEKS, threshold: float=DEFAULT_ROTATION_THRESHOLD) -> None`
- [MomentumRotationState.lookback_weeks](../../selector/regime_scoring.py) — ligne 109 : `def lookback_weeks(self) -> int`
- [MomentumRotationState.threshold](../../selector/regime_scoring.py) — ligne 113 : `def threshold(self) -> float`
- [MomentumRotationState.record](../../selector/regime_scoring.py) — ligne 116 : `def record(self, daily_return: float) -> None`
- [MomentumRotationState.cumulative_return](../../selector/regime_scoring.py) — ligne 128 : `def cumulative_return(self) -> float | None`
- [MomentumRotationState.should_rotate](../../selector/regime_scoring.py) — ligne 144 : `def should_rotate(self) -> bool`
- [MomentumRotationState.is_ready](../../selector/regime_scoring.py) — ligne 156 : `def is_ready(self) -> bool`
- [MomentumRotationState.reset](../../selector/regime_scoring.py) — ligne 160 : `def reset(self) -> None`
- [evaluate_momentum_rotation](../../selector/regime_scoring.py) — ligne 165 : `def evaluate_momentum_rotation(rotation_state: MomentumRotationState | None, snapshot: MarketRegimeSnapshot | None=None) -> bool`
- [_safe_float_series](../../selector/regime_scoring.py) — ligne 203 : `def _safe_float_series(series: pd.Series | None) -> pd.Series`
- [_invert_and_normalize](../../selector/regime_scoring.py) — ligne 213 : `def _invert_and_normalize(series: pd.Series) -> pd.Series`
- [_compute_defensive_beta_score](../../selector/regime_scoring.py) — ligne 219 : `def _compute_defensive_beta_score(df: pd.DataFrame) -> pd.Series`
- [_compute_defensive_size_score](../../selector/regime_scoring.py) — ligne 226 : `def _compute_defensive_size_score(df: pd.DataFrame) -> pd.Series`
- [_compute_defensive_low_vol_score](../../selector/regime_scoring.py) — ligne 234 : `def _compute_defensive_low_vol_score(df: pd.DataFrame) -> pd.Series`
- [apply_regime_filters](../../selector/regime_scoring.py) — ligne 244 : `def apply_regime_filters(df: pd.DataFrame, snapshot: MarketRegimeSnapshot | None) -> pd.DataFrame`
- [get_regime_weights](../../selector/regime_scoring.py) — ligne 309 : `def get_regime_weights(snapshot: MarketRegimeSnapshot | None, rotation_state: MomentumRotationState | None=None) -> dict[str, float]`
- [apply_regime_weights](../../selector/regime_scoring.py) — ligne 333 : `def apply_regime_weights(df: pd.DataFrame, snapshot: MarketRegimeSnapshot | None, config: AlphaScannerConfig | None=None, rotation_state: MomentumRotationState | None=None) -> pd.DataFrame`

## `selector/run_summary.py`

Source SHA-256 : `8d1b2893b1444680d84a01baa50fcd2e198247ca553b637955571b0cc1a3a9a1`

- [_utc_now_naive](../../selector/run_summary.py) — ligne 27 : `def _utc_now_naive() -> datetime`
- [_build_run_id](../../selector/run_summary.py) — ligne 31 : `def _build_run_id(prefix: str) -> str`
- [_emit_run_summary](../../selector/run_summary.py) — ligne 38 : `def _emit_run_summary(summary: dict[str, object]) -> None`
- [_build_top_selection_explanations](../../selector/run_summary.py) — ligne 60 : `def _build_top_selection_explanations(result: pd.DataFrame, *, limit: int=5) -> list[dict[str, object]]`
- [_build_cli_run_summary](../../selector/run_summary.py) — ligne 93 : `def _build_cli_run_summary(*, config: AlphaScannerConfig, result: pd.DataFrame, started_at: datetime, finished_at: datetime, rejected_by_filter: dict[str, int] | None=None, run_status: str='completed', failure_reason: str | None=None, data_quality_gate: dict[str, object] | None=None, preselection_rejections: dict[str, object] | None=None, ablation: dict[str, object] | None=None) -> dict[str, object]`
- [_summarize_zero_candidate_filters](../../selector/run_summary.py) — ligne 191 : `def _summarize_zero_candidate_filters(rejected_by_filter: dict[str, int] | None) -> str`

## `selector/scanner.py`

Source SHA-256 : `577b54f36a434facf66a60b111d6a439c6b567d080dc5cf015d2d4cf39c52bb6`

- [SelectorDataQualityError](../../selector/scanner.py) — ligne 61 : `class SelectorDataQualityError(RuntimeError)`
- [SelectorDataQualityError.__init__](../../selector/scanner.py) — ligne 64 : `def __init__(self, payload: dict[str, object]) -> None`
- [AlphaScanner](../../selector/scanner.py) — ligne 69 : `class AlphaScanner`
- [AlphaScanner.__init__](../../selector/scanner.py) — ligne 76 : `def __init__(self, engine: Engine | None=None, config: AlphaScannerConfig | None=None) -> None`
- [AlphaScanner.get_aggregated_filter_stats](../../selector/scanner.py) — ligne 95 : `def get_aggregated_filter_stats(self) -> dict[str, int]`
- [AlphaScanner.get_last_data_quality_gate](../../selector/scanner.py) — ligne 100 : `def get_last_data_quality_gate(self) -> dict[str, object] | None`
- [AlphaScanner.get_last_preselection_audit](../../selector/scanner.py) — ligne 103 : `def get_last_preselection_audit(self) -> dict[str, object] | None`
- [AlphaScanner.get_last_ablation_summary](../../selector/scanner.py) — ligne 106 : `def get_last_ablation_summary(self) -> dict[str, object] | None`
- [AlphaScanner.preflight_data_quality](../../selector/scanner.py) — ligne 109 : `def preflight_data_quality(self, *, reference_date: date | None=None) -> dict[str, object]`
- [AlphaScanner._build_runtime_config_from_data_quality_gate](../../selector/scanner.py) — ligne 119 : `def _build_runtime_config_from_data_quality_gate(self, data_quality_gate: Mapping[str, object]) -> AlphaScannerConfig`
- [AlphaScanner._capture_preselection_audit](../../selector/scanner.py) — ligne 153 : `def _capture_preselection_audit(self) -> dict[str, object]`
- [AlphaScanner._get_stock_metadata_columns](../../selector/scanner.py) — ligne 162 : `def _get_stock_metadata_columns(self) -> set[str]`
- [AlphaScanner._get_stock_quote_snapshots_columns](../../selector/scanner.py) — ligne 167 : `def _get_stock_quote_snapshots_columns(self) -> set[str]`
- [AlphaScanner.fetch_market_data](../../selector/scanner.py) — ligne 177 : `def fetch_market_data(self, symbols: Sequence[str]) -> pd.DataFrame`
- [AlphaScanner.fetch_scores](../../selector/scanner.py) — ligne 180 : `def fetch_scores(self, symbols: Sequence[str]) -> pd.DataFrame`
- [AlphaScanner.fetch_instrument_metadata](../../selector/scanner.py) — ligne 183 : `def fetch_instrument_metadata(self, symbols: Sequence[str]) -> pd.DataFrame`
- [AlphaScanner._load_benchmark_returns](../../selector/scanner.py) — ligne 188 : `def _load_benchmark_returns(self, start_date: date, end_date: date) -> pd.DataFrame`
- [AlphaScanner.fetch_quote_snapshots](../../selector/scanner.py) — ligne 191 : `def fetch_quote_snapshots(self, symbols: Sequence[str], *, reference_date: date | None=None) -> pd.DataFrame`
- [AlphaScanner.fetch_next_earnings](../../selector/scanner.py) — ligne 201 : `def fetch_next_earnings(self, symbols: Sequence[str], *, reference_date: date | None=None) -> pd.DataFrame`
- [AlphaScanner.compute_factors](../../selector/scanner.py) — ligne 211 : `def compute_factors(self, market_data: pd.DataFrame) -> pd.DataFrame`
- [AlphaScanner.merge_scores](../../selector/scanner.py) — ligne 222 : `def merge_scores(self, computed_df: pd.DataFrame, scores_df: pd.DataFrame) -> pd.DataFrame`
- [AlphaScanner._apply_factor_neutralization](../../selector/scanner.py) — ligne 225 : `def _apply_factor_neutralization(self, df: pd.DataFrame) -> pd.DataFrame`
- [AlphaScanner._apply_filters_with_stats](../../selector/scanner.py) — ligne 228 : `def _apply_filters_with_stats(self, merged_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]`
- [AlphaScanner.apply_filters](../../selector/scanner.py) — ligne 231 : `def apply_filters(self, merged_df: pd.DataFrame) -> pd.DataFrame`
- [AlphaScanner._log_filter_stats](../../selector/scanner.py) — ligne 236 : `def _log_filter_stats(self, stats: dict[str, int]) -> None`
- [AlphaScanner.apply_sector_neutrality](../../selector/scanner.py) — ligne 239 : `def apply_sector_neutrality(self, ranked_df: pd.DataFrame) -> pd.DataFrame`
- [AlphaScanner.rank_and_select](../../selector/scanner.py) — ligne 242 : `def rank_and_select(self, merged_df: pd.DataFrame) -> pd.DataFrame`
- [AlphaScanner.rank_and_select_short](../../selector/scanner.py) — ligne 245 : `def rank_and_select_short(self, merged_df: pd.DataFrame, long_selected: pd.DataFrame) -> pd.DataFrame`
- [AlphaScanner._enrich_short_score](../../selector/scanner.py) — ligne 249 : `def _enrich_short_score(self, merged_df: pd.DataFrame) -> None`
- [AlphaScanner._enrich_and_filter_equities](../../selector/scanner.py) — ligne 265 : `def _enrich_and_filter_equities(self, merged_df: pd.DataFrame, metadata_df: pd.DataFrame) -> pd.DataFrame`
- [AlphaScanner._merge_optional_symbol_overlays](../../selector/scanner.py) — ligne 270 : `def _merge_optional_symbol_overlays(self, merged_df: pd.DataFrame, quotes_df: pd.DataFrame, earnings_df: pd.DataFrame) -> pd.DataFrame`
- [AlphaScanner.update_database](../../selector/scanner.py) — ligne 281 : `def update_database(self, selected_df: pd.DataFrame, scored_df: pd.DataFrame | None=None) -> int`
- [AlphaScanner._reset_selector_outputs](../../selector/scanner.py) — ligne 293 : `def _reset_selector_outputs(self) -> None`
- [AlphaScanner._prepare_scores_snapshot](../../selector/scanner.py) — ligne 298 : `def _prepare_scores_snapshot(self, scored_df: pd.DataFrame | None) -> list[dict[str, object]]`
- [AlphaScanner._iter_eligible_symbol_chunks](../../selector/scanner.py) — ligne 301 : `def _iter_eligible_symbol_chunks(self)`
- [AlphaScanner._scan_primary_selections](../../selector/scanner.py) — ligne 306 : `def _scan_primary_selections(self) -> tuple[pd.DataFrame, dict[str, int]]`
- [AlphaScanner._process_chunk_variants](../../selector/scanner.py) — ligne 378 : `def _process_chunk_variants(self, symbols: Sequence[str], runtime_variants: Sequence[RuntimeSelectorVariant], as_of_date: date | None=None) -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, int]]]`
- [AlphaScanner._collect_completed_variant_results](../../selector/scanner.py) — ligne 426 : `def _collect_completed_variant_results(self, done: set[Future[tuple[dict[str, pd.DataFrame], dict[str, dict[str, int]]]]], all_frames_by_variant: dict[str, list[pd.DataFrame]], aggregated_stats_by_variant: dict[str, Counter[str]]) -> int`
- [AlphaScanner._scan_ablation_selections](../../selector/scanner.py) — ligne 445 : `def _scan_ablation_selections(self, runtime_variants: Sequence[RuntimeSelectorVariant]) -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, int]], dict[str, int]]`
- [AlphaScanner.run](../../selector/scanner.py) — ligne 522 : `def run(self) -> pd.DataFrame`
- [AlphaScanner._process_chunk](../../selector/scanner.py) — ligne 683 : `def _process_chunk(self, symbols: Sequence[str], as_of_date: date | None=None) -> pd.DataFrame`
- [AlphaScanner._collect_completed](../../selector/scanner.py) — ligne 725 : `def _collect_completed(self, done: set[Future[pd.DataFrame]], all_frames: list[pd.DataFrame]) -> int`
- [AlphaScanner._resolve_worker_count](../../selector/scanner.py) — ligne 736 : `def _resolve_worker_count(self) -> int`
- [AlphaScanner._emit_live_progress](../../selector/scanner.py) — ligne 741 : `def _emit_live_progress(self, *, current: int, total: int, label: str, phase: str, extra_summary: dict[str, object] | None=None) -> None`
- [AlphaScanner._progress_emitter](../../selector/scanner.py) — ligne 768 : `def _progress_emitter(self)`
- [AlphaScanner._winsorize_and_normalize](../../selector/scanner.py) — ligne 780 : `def _winsorize_and_normalize(series: pd.Series | None, lower_pct: float=0.01, upper_pct: float=0.99) -> pd.Series`
- [AlphaScanner._normalize_zero_one](../../selector/scanner.py) — ligne 788 : `def _normalize_zero_one(series: pd.Series | None) -> pd.Series`

## `selector/short_score.py`

Source SHA-256 : `e4bdf70f11fb3281b9e7db5c277a998295d7267884809bf39241d4be439a45bb`

- [ShortTrigger](../../selector/short_score.py) — ligne 45 : `class ShortTrigger`
- [ShortTrigger.active](../../selector/short_score.py) — ligne 65 : `def active(self) -> bool`
- [resolve_short_trigger](../../selector/short_score.py) — ligne 70 : `def resolve_short_trigger(snap: object | None, rotation_state: 'MomentumRotationState | None', short_selling_enabled: bool) -> ShortTrigger`
- [resolve_regime_adaptive_short_params](../../selector/short_score.py) — ligne 117 : `def resolve_regime_adaptive_short_params(risk_config: object, short_by_regime: bool) -> tuple[int, float]`
- [inject_predicted_side](../../selector/short_score.py) — ligne 151 : `def inject_predicted_side(day_df: pd.DataFrame, predictions_df: pd.DataFrame, trade_date: pd.Timestamp) -> pd.DataFrame`
- [compute_short_score](../../selector/short_score.py) — ligne 185 : `def compute_short_score(day_df: pd.DataFrame, close_df: pd.DataFrame | None=None, trade_day: pd.Timestamp | None=None, *, sma_50_col: str='sma_50', sma_200_col: str='sma_200') -> pd.Series`
- [enrich_with_short_score](../../selector/short_score.py) — ligne 263 : `def enrich_with_short_score(day_df: pd.DataFrame, close_df: pd.DataFrame | None=None, trade_day: pd.Timestamp | None=None) -> pd.DataFrame`
- [_get_close](../../selector/short_score.py) — ligne 312 : `def _get_close(close_df: pd.DataFrame, symbol: str, trade_day: pd.Timestamp) -> float | None`
- [compute_sma_column](../../selector/short_score.py) — ligne 327 : `def compute_sma_column(close_df: pd.DataFrame, symbol: str, trade_day: pd.Timestamp, window: int=50) -> float | None`
- [tag_short_candidates](../../selector/short_score.py) — ligne 373 : `def tag_short_candidates(day_df: pd.DataFrame, *, max_short_positions: int=2, min_score_for_short: float=0.3, max_long_positions: int=3, all_shorts: bool=False) -> pd.DataFrame`

## `selector/strict_filter_profiles.py`

Source SHA-256 : `1004fa849839dff5a413a17d812a1294819f862d3e49569689ee80b56d7edf0f`

Module sans déclaration publique/privée de classe ou fonction au niveau module.
