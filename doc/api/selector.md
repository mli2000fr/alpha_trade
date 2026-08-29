# Inventaire API — selector

Cet inventaire est dérivé des signatures présentes dans le code. Les symboles préfixés par `_` restent internes. Les numéros de ligne sont indicatifs ; le chemin et le nom du symbole sont les repères stables.

## `selector/ablation.py`

- ligne 140 — `def build_ablation_summary_and_artifact(`
- ligne 206 — `def write_ablation_artifact(`
- ligne 24 — `class RuntimeSelectorVariant:`
- ligne 34 — `def resolve_runtime_variants(`
- ligne 86 — `def _extract_selected_symbols(selected_df: pd.DataFrame) -> list[str]:`
- ligne 93 — `def _build_variant_payload(`
## `selector/cli.py`

- ligne 100 — `def _build_config_from_args(args: argparse.Namespace) -> AlphaScannerConfig:`
- ligne 164 — `def main() -> None:`
- ligne 31 — `def _build_arg_parser() -> argparse.ArgumentParser:`
## `selector/config.py`

- ligne 106 — `class SelectorVariantSpec:`
- ligne 130 — `class SelectorAblationPlan:`
- ligne 157 — `def build_selector_variant_spec_from_mapping(payload: dict[str, object]) -> SelectorVariantSpec:`
- ligne 173 — `def build_selector_ablation_plan_from_mapping(payload: dict[str, object]) -> SelectorAblationPlan:`
- ligne 193 — `def load_selector_ablation_plan_from_file(file_path: str | Path) -> SelectorAblationPlan:`
- ligne 207 — `def get_ablation_filter_config_overrides(filter_key: str) -> dict[str, object]:`
- ligne 216 — `def is_filter_effectively_enabled(config: AlphaScannerConfig, filter_key: str) -> bool:`
- ligne 245 — `def apply_variant_spec_to_config(`
- ligne 256 — `def compute_config_diff(`
- ligne 280 — `class AlphaScannerConfig:`
- ligne 467 — `def resolve_symmetric_grid(label: str) -> tuple[int, int]:`
- ligne 77 — `def _normalize_ablation_filter_keys(filter_keys: tuple[str, ...] | list[str]) -> tuple[str, ...]:`
- ligne 94 — `def _normalize_ablation_overrides(raw_overrides: dict[str, object] | None) -> dict[str, object]:`
## `selector/db_io.py`

- ligne 1014 — `def update_database(`
- ligne 123 — `def _build_data_quality_check_payload(`
- ligne 150 — `def _has_table(engine: Engine, table_name: str) -> bool:`
- ligne 158 — `def get_table_columns(`
- ligne 171 — `def _read_scalar_date(`
- ligne 190 — `def build_data_quality_gate(`
- ligne 219 — `def _build_quotes_quality_check(`
- ligne 274 — `def _build_earnings_quality_check(`
- ligne 349 — `def _build_market_cap_quality_check(`
- ligne 415 — `def get_stock_metadata_columns(engine: Engine) -> set[str]:`
- ligne 426 — `def get_stock_quote_snapshots_columns(engine: Engine) -> set[str]:`
- ligne 436 — `def fetch_market_data(engine: Engine, config: AlphaScannerConfig, symbols: Sequence[str]) -> pd.DataFrame:`
- ligne 463 — `def fetch_scores(engine: Engine, config: AlphaScannerConfig, symbols: Sequence[str]) -> pd.DataFrame:`
- ligne 502 — `def fetch_instrument_metadata(`
- ligne 551 — `def load_benchmark_returns(`
- ligne 580 — `def fetch_quote_snapshots(`
- ligne 671 — `def fetch_next_earnings(`
- ligne 721 — `def _classify_preselection_rejection_reason(`
- ligne 759 — `def build_preselection_rejection_audit(`
- ligne 878 — `def iter_eligible_symbol_chunks(`
- ligne 955 — `def reset_selector_outputs(engine: Engine, config: AlphaScannerConfig) -> None:`
- ligne 982 — `def prepare_scores_snapshot(scored_df: pd.DataFrame | None) -> list[dict[str, object]]:`
## `selector/dip_filter.py`

- ligne 107 — `def _dip_pass(ret: float, dip_pct: float) -> bool:`
- ligne 117 — `def load_rank_history_df(`
- ligne 154 — `def load_oracle_rank_history_df(`
- ligne 193 — `def load_price_history_df(`
- ligne 233 — `def evaluate_dip_filter(`
- ligne 350 — `def filter_day_candidates(`
- ligne 67 — `def _load_yaml_config() -> dict[str, Any]:`
- ligne 77 — `def load_dip_filter_config(execution_context: str) -> dict[str, Any]:`
- ligne 96 — `def _rank_column(config: dict[str, Any], best_h: int | None = None) -> str:`
## `selector/explainability.py`

- ligne 17 — `def _is_missing(value: object) -> bool:`
- ligne 28 — `def _clean_text(value: object) -> str | None:`
- ligne 35 — `def _clean_int(value: object) -> int | None:`
- ligne 44 — `def _clean_float(value: object, *, digits: int = 4) -> float | None:`
- ligne 53 — `def _clean_date(value: object) -> str | None:`
- ligne 62 — `def build_selection_explainability_payload(row: Mapping[str, object]) -> dict[str, object]:`
## `selector/factors.py`

- ligne 54 — `def winsorize_and_normalize(`
- ligne 88 — `def compute_factor_frame(`
## `selector/filters.py`

- ligne 374 — `def log_filter_stats(stats: dict[str, int]) -> None:`
- ligne 401 — `def enrich_and_filter_equities(`
- ligne 502 — `def merge_optional_symbol_overlays(`
- ligne 76 — `def apply_filters_with_stats(`
## `selector/ranking.py`

- ligne 135 — `def _safe_float(value: object) -> float | None:`
- ligne 144 — `def _build_selection_explanation(row: pd.Series) -> str:`
- ligne 161 — `def _apply_selection_explainability(`
- ligne 195 — `def merge_scores(`
- ligne 271 — `def apply_factor_neutralization(`
- ligne 373 — `def apply_sector_neutrality(`
- ligne 440 — `def rank_and_select(`
- ligne 471 — `def rank_and_select_short(`
## `selector/regime_filters.py`

- ligne 122 — `def apply_yield_filter_to_candidates(`
- ligne 150 — `def apply_full_regime_to_candidates(`
- ligne 30 — `def _normalize_symbol_set(values: Iterable[object] | None) -> set[str]:`
- ligne 38 — `def _normalize_sector_set(values: Iterable[object] | None) -> set[str]:`
- ligne 46 — `def apply_earnings_shield_to_candidates(`
- ligne 85 — `def apply_buyback_blackout_to_candidates(`
## `selector/regime_scoring.py`

- ligne 165 — `def evaluate_momentum_rotation(`
- ligne 203 — `def _safe_float_series(series: pd.Series | None) -> pd.Series:`
- ligne 213 — `def _invert_and_normalize(series: pd.Series) -> pd.Series:`
- ligne 219 — `def _compute_defensive_beta_score(df: pd.DataFrame) -> pd.Series:`
- ligne 226 — `def _compute_defensive_size_score(df: pd.DataFrame) -> pd.Series:`
- ligne 234 — `def _compute_defensive_low_vol_score(df: pd.DataFrame) -> pd.Series:`
- ligne 244 — `def apply_regime_filters(`
- ligne 309 — `def get_regime_weights(`
- ligne 333 — `def apply_regime_weights(`
- ligne 82 — `class MomentumRotationState:`
## `selector/run_summary.py`

- ligne 191 — `def _summarize_zero_candidate_filters(rejected_by_filter: dict[str, int] | None) -> str:`
- ligne 27 — `def _utc_now_naive() -> datetime:`
- ligne 31 — `def _build_run_id(prefix: str) -> str:`
- ligne 38 — `def _emit_run_summary(summary: dict[str, object]) -> None:`
- ligne 60 — `def _build_top_selection_explanations(result: pd.DataFrame, *, limit: int = 5) -> list[dict[str, object]]:`
- ligne 93 — `def _build_cli_run_summary(`
## `selector/scanner.py`

- ligne 61 — `class SelectorDataQualityError(RuntimeError):`
- ligne 69 — `class AlphaScanner:`
## `selector/short_score.py`

- ligne 117 — `def resolve_regime_adaptive_short_params(`
- ligne 151 — `def inject_predicted_side(`
- ligne 185 — `def compute_short_score(`
- ligne 263 — `def enrich_with_short_score(`
- ligne 312 — `def _get_close(`
- ligne 327 — `def compute_sma_column(`
- ligne 373 — `def tag_short_candidates(`
- ligne 45 — `class ShortTrigger:`
- ligne 70 — `def resolve_short_trigger(`

