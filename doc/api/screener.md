# Inventaire API — screener

Extraction AST du 2026-10-10 ; aucune importation ni exécution métier.

Classes, fonctions de module et méthodes déclarées ; fonctions imbriquées exclues.
Les symboles `_...` sont internes. Signature présente ≠ API publique stable.

## `screener/__init__.py`

Source SHA-256 : `9f233cb3518ec888472e5c075e349d40ebf10a1bd2d48fab9716bd3bc5d49d01`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `screener/db_io.py`

Source SHA-256 : `12372c77a9fcd14afd5b91e1726bee3ae5a9a7976ba5e485ae0078f502753679`

- [get_engine](../../screener/db_io.py) — ligne 93 : `def get_engine() -> Engine`
- [_get_scores_table](../../screener/db_io.py) — ligne 97 : `def _get_scores_table(engine: Engine) -> Table`
- [_get_table_columns](../../screener/db_io.py) — ligne 102 : `def _get_table_columns(engine: Engine, table_name: str, fallback: set[str]) -> set[str]`
- [_purge_missing_scores](../../screener/db_io.py) — ligne 109 : `def _purge_missing_scores(engine: Engine, symbols: list[str]) -> None`
- [load_symbols_from_file](../../screener/db_io.py) — ligne 117 : `def load_symbols_from_file(filepath: str) -> list[str]`
- [iter_symbol_chunks](../../screener/db_io.py) — ligne 156 : `def iter_symbol_chunks(engine: Engine, chunk_size: int) -> Iterator[list[str]]`
- [_resolve_reference_date](../../screener/db_io.py) — ligne 196 : `def _resolve_reference_date(as_of_date: Optional[date]) -> date`
- [_load_price_frame](../../screener/db_io.py) — ligne 201 : `def _load_price_frame(engine: Engine, symbols: list[str], *, cutoff_lower: date, as_of_date: Optional[date]=None) -> pd.DataFrame`
- [load_recent_prices_for_chunk](../../screener/db_io.py) — ligne 232 : `def load_recent_prices_for_chunk(engine: Engine, symbols: list[str], config: ScreenerConfig, as_of_date: Optional[date]=None) -> pd.DataFrame`
- [load_prices_for_chunk](../../screener/db_io.py) — ligne 253 : `def load_prices_for_chunk(engine: Engine, symbols: list[str], config: ScreenerConfig, as_of_date: Optional[date]=None) -> pd.DataFrame`
- [load_historical_range_stats_for_symbols](../../screener/db_io.py) — ligne 279 : `def load_historical_range_stats_for_symbols(engine: Engine, symbols: list[str], config: ScreenerConfig, as_of_date: Optional[date]=None) -> pd.DataFrame`
- [load_spy_return_6m](../../screener/db_io.py) — ligne 316 : `def load_spy_return_6m(engine: Engine, config: ScreenerConfig, as_of_date: Optional[date]=None) -> float`
- [_load_metadata_sectors](../../screener/db_io.py) — ligne 354 : `def _load_metadata_sectors(engine: Engine, symbols: list[str]) -> pd.DataFrame`
- [_enrich_scores_with_metadata_sector](../../screener/db_io.py) — ligne 369 : `def _enrich_scores_with_metadata_sector(engine: Engine, scores_df: pd.DataFrame) -> pd.DataFrame`
- [_load_latest_audit_metrics](../../screener/db_io.py) — ligne 385 : `def _load_latest_audit_metrics(engine: Engine, symbols: list[str]) -> pd.DataFrame`
- [_enrich_scores_with_audit](../../screener/db_io.py) — ligne 403 : `def _enrich_scores_with_audit(engine: Engine, scores_df: pd.DataFrame) -> pd.DataFrame`
- [_normalize_scores_snapshot](../../screener/db_io.py) — ligne 419 : `def _normalize_scores_snapshot(scores_df: pd.DataFrame) -> pd.DataFrame`
- [_coerce_mysql_scalar](../../screener/db_io.py) — ligne 453 : `def _coerce_mysql_scalar(value: object) -> object`
- [_records_with_mysql_nulls](../../screener/db_io.py) — ligne 465 : `def _records_with_mysql_nulls(records: list[dict[str, object]]) -> list[dict[str, object]]`
- [archive_scores_snapshot](../../screener/db_io.py) — ligne 472 : `def archive_scores_snapshot(engine: Engine, snapshot_date: Optional[date]=None, *, capital_preset_key: str=DEFAULT_CAPITAL_PRESET_KEY, config_fingerprint: str | None=None) -> int`
- [upsert_scores_snapshot](../../screener/db_io.py) — ligne 525 : `def upsert_scores_snapshot(engine: Engine, scores_df: pd.DataFrame, chunksize: int=1000, snapshot_date: Optional[date]=None, *, capital_preset_key: str=DEFAULT_CAPITAL_PRESET_KEY, config_fingerprint: str | None=None, delete_existing_on_empty: bool=False, purge_missing: bool=True, archive_snapshot: bool=True) -> None`

## `screener/models.py`

Source SHA-256 : `38df17b4957cb67cafe692bc91f0d782d51d8e61356c44de48b1da4dae70a199`

- [ScreenerConfig](../../screener/models.py) — ligne 15 : `class ScreenerConfig`
- [ScreenerConfig.__post_init__](../../screener/models.py) — ligne 44 : `def __post_init__(self) -> None`
- [ScreenerConfig.to_dict](../../screener/models.py) — ligne 80 : `def to_dict(self) -> dict[str, Any]`
- [ScreenerConfig.min_calendar_window_for_history_days](../../screener/models.py) — ligne 84 : `def min_calendar_window_for_history_days(cls, history_days: int) -> int`
- [ScreenerConfig.effective_first_pass_window_days](../../screener/models.py) — ligne 99 : `def effective_first_pass_window_days(self) -> int`
- [ScreenerConfig.from_dict](../../screener/models.py) — ligne 107 : `def from_dict(payload: dict[str, Any]) -> 'ScreenerConfig'`
- [ScreenerConfig.from_filter_profile](../../screener/models.py) — ligne 114 : `def from_filter_profile(cls, profile: StrictFilterProfile, **overrides: Any) -> 'ScreenerConfig'`
- [ScreenerConfig.strict_swing_cash](../../screener/models.py) — ligne 142 : `def strict_swing_cash(cls, **overrides: Any) -> 'ScreenerConfig'`
- [ScreenerChunkMetrics](../../screener/models.py) — ligne 148 : `class ScreenerChunkMetrics`
- [ScreenerRunReport](../../screener/models.py) — ligne 166 : `class ScreenerRunReport`
- [ScreenerRunReport.chunk_failure_ratio](../../screener/models.py) — ligne 201 : `def chunk_failure_ratio(self) -> float`
- [ScreenerRunReport.to_summary_dict](../../screener/models.py) — ligne 207 : `def to_summary_dict(self) -> dict[str, object]`

## `screener/pipeline.py`

Source SHA-256 : `f3480d9886070060fe3d7e18cb54a7e8714f222698e4c4d5d8a1fbd7dd604f35`

- [_empty_result](../../screener/pipeline.py) — ligne 30 : `def _empty_result() -> pd.DataFrame`
- [_empty_candidates](../../screener/pipeline.py) — ligne 34 : `def _empty_candidates() -> pd.DataFrame`
- [_empty_historical_range](../../screener/pipeline.py) — ligne 38 : `def _empty_historical_range() -> pd.DataFrame`
- [evaluate_objective_tradability](../../screener/pipeline.py) — ligne 42 : `def evaluate_objective_tradability(prices_df: pd.DataFrame, symbols: list[str], config: ScreenerConfig, as_of_date: Optional[date]=None) -> tuple[UniverseMember, ...]`
- [_percentile_score](../../screener/pipeline.py) — ligne 113 : `def _percentile_score(series: pd.Series) -> pd.Series`
- [_prepare_prices](../../screener/pipeline.py) — ligne 122 : `def _prepare_prices(prices_df: pd.DataFrame, as_of_date: Optional[date]=None) -> pd.DataFrame`
- [screen_recent_prices](../../screener/pipeline.py) — ligne 139 : `def screen_recent_prices(prices_df: pd.DataFrame, spy_return_6m: float, config: ScreenerConfig, as_of_date: Optional[date]=None) -> tuple[pd.DataFrame, dict[str, int]]`
- [compute_historical_range_stats_from_prices](../../screener/pipeline.py) — ligne 229 : `def compute_historical_range_stats_from_prices(prices_df: pd.DataFrame, symbols: list[str], config: ScreenerConfig, as_of_date: Optional[date]=None) -> pd.DataFrame`
- [finalize_scores_with_historical_range](../../screener/pipeline.py) — ligne 263 : `def finalize_scores_with_historical_range(candidate_df: pd.DataFrame, historical_range_df: pd.DataFrame, config: ScreenerConfig) -> pd.DataFrame`
- [compute_scores_from_prices](../../screener/pipeline.py) — ligne 314 : `def compute_scores_from_prices(prices_df: pd.DataFrame, spy_return_6m: float, config: ScreenerConfig, as_of_date: Optional[date]=None) -> pd.DataFrame`

## `screener/stock_screener.py`

Source SHA-256 : `dd1337315c566eeb3a5053d96113ab2953c595bd29acd4410f698969b6213119`

- [_utc_now_naive](../../screener/stock_screener.py) — ligne 48 : `def _utc_now_naive() -> datetime`
- [_build_run_id](../../screener/stock_screener.py) — ligne 52 : `def _build_run_id(prefix: str) -> str`
- [_emit_run_summary](../../screener/stock_screener.py) — ligne 56 : `def _emit_run_summary(summary: dict[str, object]) -> None`
- [_emit_live_progress](../../screener/stock_screener.py) — ligne 78 : `def _emit_live_progress(progress_callback: Callable[[dict[str, object]], None] | None, summary: dict[str, object]) -> None`
- [_estimate_full_history_rows](../../screener/stock_screener.py) — ligne 96 : `def _estimate_full_history_rows(symbol_count: int, config: ScreenerConfig) -> int`
- [_process_chunk_two_passes](../../screener/stock_screener.py) — ligne 101 : `def _process_chunk_two_passes(symbols: List[str], config_dict: dict, spy_return_6m: float, as_of_date_iso: Optional[str]) -> tuple[pd.DataFrame, ScreenerChunkMetrics]`
- [_process_chunk](../../screener/stock_screener.py) — ligne 189 : `def _process_chunk(symbols: List[str], config_dict: dict, spy_return_6m: float, as_of_date_iso: Optional[str]) -> pd.DataFrame`
- [_resolve_worker_count](../../screener/stock_screener.py) — ligne 200 : `def _resolve_worker_count(max_workers: Optional[int]) -> int`
- [_empty_scores](../../screener/stock_screener.py) — ligne 209 : `def _empty_scores() -> pd.DataFrame`
- [_merge_run_metrics](../../screener/stock_screener.py) — ligne 213 : `def _merge_run_metrics(summary: dict[str, object], chunk_metrics: ScreenerChunkMetrics) -> None`
- [_record_chunk_error_sample](../../screener/stock_screener.py) — ligne 226 : `def _record_chunk_error_sample(summary: dict[str, object], chunk_metrics: ScreenerChunkMetrics, chunk_symbols: List[str]) -> None`
- [_append_completed_results](../../screener/stock_screener.py) — ligne 247 : `def _append_completed_results(done, all_results: List[pd.DataFrame], all_universe_members: list[UniverseMember], summary: dict[str, object], pending: dict) -> None`
- [_build_run_report](../../screener/stock_screener.py) — ligne 264 : `def _build_run_report(summary: dict[str, object]) -> ScreenerRunReport`
- [_log_run_report](../../screener/stock_screener.py) — ligne 268 : `def _log_run_report(report: ScreenerRunReport) -> None`
- [_log_chunk_error_samples](../../screener/stock_screener.py) — ligne 272 : `def _log_chunk_error_samples(report: ScreenerRunReport) -> None`
- [run_screener_with_report](../../screener/stock_screener.py) — ligne 288 : `def run_screener_with_report(config: ScreenerConfig, max_workers: Optional[int]=None, as_of_date: Optional[date]=None, snapshot_date: Optional[date]=None, progress_callback: Callable[[dict[str, object]], None] | None=None, capital_preset_key: str=DEFAULT_CAPITAL_PRESET_KEY, market_code: str='US_EQ') -> tuple[pd.DataFrame, ScreenerRunReport]`
- [run_screener](../../screener/stock_screener.py) — ligne 559 : `def run_screener(config: ScreenerConfig, max_workers: Optional[int]=None, as_of_date: Optional[date]=None) -> pd.DataFrame`
- [_build_arg_parser](../../screener/stock_screener.py) — ligne 577 : `def _build_arg_parser() -> argparse.ArgumentParser`
- [main](../../screener/stock_screener.py) — ligne 619 : `def main() -> None`
