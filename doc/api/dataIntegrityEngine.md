# Inventaire API — dataIntegrityEngine

Extraction AST du 2026-10-10 ; aucune importation ni exécution métier.

Classes, fonctions de module et méthodes déclarées ; fonctions imbriquées exclues.
Les symboles `_...` sont internes. Signature présente ≠ API publique stable.

## `dataIntegrityEngine/__init__.py`

Source SHA-256 : `b3f6285dda57e7ddc36a2b517c4307df479e57efa21b8ef43d974b8cf76825e2`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `dataIntegrityEngine/backfill_eodhd_history.py`

Source SHA-256 : `1f26f3dc6354467f1c2b962004ae5c6e98f2c3f26c59d47b2680841c2b198eb5`

- [_utc_now_naive](../../dataIntegrityEngine/backfill_eodhd_history.py) — ligne 83 : `def _utc_now_naive() -> datetime`
- [_build_run_id](../../dataIntegrityEngine/backfill_eodhd_history.py) — ligne 87 : `def _build_run_id(prefix: str='backfill-eodhd') -> str`
- [_emit_run_summary](../../dataIntegrityEngine/backfill_eodhd_history.py) — ligne 91 : `def _emit_run_summary(summary: dict[str, Any]) -> None`
- [load_bookmark](../../dataIntegrityEngine/backfill_eodhd_history.py) — ligne 103 : `def load_bookmark(path: Path) -> dict[str, Any]`
- [save_bookmark](../../dataIntegrityEngine/backfill_eodhd_history.py) — ligne 113 : `def save_bookmark(path: Path, state: dict[str, Any]) -> None`
- [_filter_remaining](../../dataIntegrityEngine/backfill_eodhd_history.py) — ligne 118 : `def _filter_remaining(symbols: list[str], bookmark: dict[str, Any]) -> list[str]`
- [_filter_symbols_missing_or_stale_in_db](../../dataIntegrityEngine/backfill_eodhd_history.py) — ligne 123 : `def _filter_symbols_missing_or_stale_in_db(session, symbols: list[str], *, today: date, freshness_days: int=DEFAULT_DB_FRESHNESS_DAYS) -> tuple[list[str], set[str], date]`
- [_eod_rows_to_raw_bars](../../dataIntegrityEngine/backfill_eodhd_history.py) — ligne 146 : `def _eod_rows_to_raw_bars(rows: list[dict]) -> list[dict]`
- [backfill_one_symbol](../../dataIntegrityEngine/backfill_eodhd_history.py) — ligne 164 : `def backfill_one_symbol(*, symbol: str, start: str, end: str, cache: EodhdDiskCache, tracker: EodhdQuotaTracker, session, dry_run: bool, fetch_eod_fn=None) -> dict[str, int]`
- [run_backfill](../../dataIntegrityEngine/backfill_eodhd_history.py) — ligne 231 : `def run_backfill(*, years: int=DEFAULT_YEARS, symbols: Optional[list[str]]=None, dry_run: bool=True, resume: bool=True, bookmark_path: Optional[Path]=None, batch_commit: int=DEFAULT_BATCH_COMMIT, config: Optional[dict]=None, session=None, tracker: Optional[EodhdQuotaTracker]=None, cache: Optional[EodhdDiskCache]=None, today: Optional[date]=None) -> dict[str, Any]`
- [_finalize](../../dataIntegrityEngine/backfill_eodhd_history.py) — ligne 430 : `def _finalize(summary, started_at, tracker, bookmark, bookmark_path)`
- [_load_config_safe](../../dataIntegrityEngine/backfill_eodhd_history.py) — ligne 456 : `def _load_config_safe() -> dict`
- [_build_arg_parser](../../dataIntegrityEngine/backfill_eodhd_history.py) — ligne 470 : `def _build_arg_parser() -> argparse.ArgumentParser`
- [main](../../dataIntegrityEngine/backfill_eodhd_history.py) — ligne 488 : `def main(argv: Optional[list[str]]=None) -> int`

## `dataIntegrityEngine/bar_importer_common.py`

Source SHA-256 : `c0bbad12e91960cd7c7891d8b01380cb8d29483081b26a2198748ceefb314b10`

- [resolve_bars_provider](../../dataIntegrityEngine/bar_importer_common.py) — ligne 8 : `def resolve_bars_provider(config: Mapping[str, Any] | None=None, *, fallback: str='alpaca') -> str`
- [normalize_symbols](../../dataIntegrityEngine/bar_importer_common.py) — ligne 22 : `def normalize_symbols(symbols: list[str] | None) -> list[str] | None`

## `dataIntegrityEngine/cn_ingestion.py`

Source SHA-256 : `ebf2e78d26eb12d0a3be156663c8b842935692b9e6d49716f20ea4117e9c767d`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `dataIntegrityEngine/cn_provider_ingestion.py`

Source SHA-256 : `1f0f10bacf99585ee72ce61692366e63ac9bd07eef970a760e2616f5905227bd`

- [CnBatchRunError](../../dataIntegrityEngine/cn_provider_ingestion.py) — ligne 29 : `class CnBatchRunError(RuntimeError)`
- [CnBatchRunError.__init__](../../dataIntegrityEngine/cn_provider_ingestion.py) — ligne 32 : `def __init__(self, message: str, counters: IngestionCounters) -> None`
- [_parse_date](../../dataIntegrityEngine/cn_provider_ingestion.py) — ligne 37 : `def _parse_date(value: Any) -> date | None`
- [load_job](../../dataIntegrityEngine/cn_provider_ingestion.py) — ligne 43 : `def load_job(path: Path, job_name: str) -> dict[str, Any]`
- [_collect_baostock](../../dataIntegrityEngine/cn_provider_ingestion.py) — ligne 52 : `def _collect_baostock(cfg: dict[str, Any], *, engine: Any, run_id: str, start: date | None, end: date, dry_run: bool) -> tuple[IngestionCounters, int]`
- [_collect_tushare](../../dataIntegrityEngine/cn_provider_ingestion.py) — ligne 87 : `def _collect_tushare(cfg: dict[str, Any], *, engine: Any, run_id: str, start: date | None, end: date, dry_run: bool) -> tuple[IngestionCounters, int]`
- [execute](../../dataIntegrityEngine/cn_provider_ingestion.py) — ligne 119 : `def execute(job_name: str, *, config_path: Path, force: bool=False, dry_run: bool=False, start_date: date | None=None, end_date: date | None=None) -> tuple[str, IngestionCounters]`
- [main](../../dataIntegrityEngine/cn_provider_ingestion.py) — ligne 212 : `def main() -> None`

## `dataIntegrityEngine/cn_sprint10a_audit.py`

Source SHA-256 : `a51f3abc5ad5b157c933686b71c0327d4beb760600baf6fbb6c74bf9897a9ca5`

- [_sha256](../../dataIntegrityEngine/cn_sprint10a_audit.py) — ligne 25 : `def _sha256(path: Path) -> str`
- [audit](../../dataIntegrityEngine/cn_sprint10a_audit.py) — ligne 33 : `def audit(root: Path, *, start_year: int=2018, end_year: int=2025) -> dict[str, Any]`
- [main](../../dataIntegrityEngine/cn_sprint10a_audit.py) — ligne 109 : `def main() -> None`

## `dataIntegrityEngine/cn_sprint10a_labels.py`

Source SHA-256 : `083d1d3989d38b218ba2cd609fc6fa691a035f891a5136cd5f65dbb7c5444add`

- [main](../../dataIntegrityEngine/cn_sprint10a_labels.py) — ligne 13 : `def main() -> None`

## `dataIntegrityEngine/cn_sprint10b_campaign.py`

Source SHA-256 : `39851e55ba0d336a34a021c69a6dd8673efc42d6fe0c4405385f409f28b49a42`

- [campaign](../../dataIntegrityEngine/cn_sprint10b_campaign.py) — ligne 23 : `def campaign(*, config_path: Path=DEFAULT_CONFIG, output_root: Path=DEFAULT_OUTPUT, horizon: int | None=None, model: str | None=None) -> dict[str, object]`
- [main](../../dataIntegrityEngine/cn_sprint10b_campaign.py) — ligne 63 : `def main() -> None`

## `dataIntegrityEngine/cn_sprint10c_campaign.py`

Source SHA-256 : `1ac5e469330da915df57b5bbc86e743b1d9f66d45e2d947bd48acc48efee5a67`

- [campaign](../../dataIntegrityEngine/cn_sprint10c_campaign.py) — ligne 23 : `def campaign(*, config_path: Path=DEFAULT_CONFIG, output_root: Path=DEFAULT_OUTPUT, horizon: int | None=None, model: str | None=None) -> dict[str, object]`
- [main](../../dataIntegrityEngine/cn_sprint10c_campaign.py) — ligne 62 : `def main() -> None`

## `dataIntegrityEngine/cn_sprint12a_migrate.py`

Source SHA-256 : `01e760a7ecbf586ea99eccae5beddb754c27d38ec4095c420b0685ff506a74e7`

- [_statements](../../dataIntegrityEngine/cn_sprint12a_migrate.py) — ligne 20 : `def _statements(source: str) -> list[str]`
- [audit](../../dataIntegrityEngine/cn_sprint12a_migrate.py) — ligne 25 : `def audit(conn) -> dict[str, object]`
- [main](../../dataIntegrityEngine/cn_sprint12a_migrate.py) — ligne 88 : `def main() -> None`

## `dataIntegrityEngine/cn_sprint18c_contract_2026.py`

Source SHA-256 : `a50217e6352e00638dcbd5003213a3e468ae98e12c78a0b3b5d56f6f68ab773e`

- [_metadata](../../dataIntegrityEngine/cn_sprint18c_contract_2026.py) — ligne 39 : `def _metadata(value: object) -> dict`
- [_database_guard](../../dataIntegrityEngine/cn_sprint18c_contract_2026.py) — ligne 46 : `def _database_guard(conn) -> None`
- [audit](../../dataIntegrityEngine/cn_sprint18c_contract_2026.py) — ligne 57 : `def audit(conn) -> dict`
- [main](../../dataIntegrityEngine/cn_sprint18c_contract_2026.py) — ligne 123 : `def main() -> None`

## `dataIntegrityEngine/cn_sprint7a_pilot.py`

Source SHA-256 : `ea3dfb70ca23cfb3030a22d4ad6f8712df502218882fa0b92ed132c68a35d157`

- [collect](../../dataIntegrityEngine/cn_sprint7a_pilot.py) — ligne 31 : `def collect(engine, *, manifest: Path, start: date, end: date, endpoints: tuple[str, ...], include_inactive: bool=False, resume: bool=False, state_key: str | None=None, batch_name: str='cn_sprint7a_pilot_collect') -> dict[str, object]`
- [_write_report](../../dataIntegrityEngine/cn_sprint7a_pilot.py) — ligne 63 : `def _write_report(payload: dict[str, object]) -> Path`
- [main](../../dataIntegrityEngine/cn_sprint7a_pilot.py) — ligne 71 : `def main() -> None`

## `dataIntegrityEngine/cn_sprint7b_full.py`

Source SHA-256 : `0340510ea926f1071be3a06beab575475fd6dd1ea8ae4a237edfdc7b713ca5cd`

- [Sprint7BState](../../dataIntegrityEngine/cn_sprint7b_full.py) — ligne 31 : `class Sprint7BState`
- [Sprint7BState.__init__](../../dataIntegrityEngine/cn_sprint7b_full.py) — ligne 32 : `def __init__(self, path: Path) -> None`
- [Sprint7BState.status](../../dataIntegrityEngine/cn_sprint7b_full.py) — ligne 36 : `def status(self, index: int) -> str | None`
- [Sprint7BState.update](../../dataIntegrityEngine/cn_sprint7b_full.py) — ligne 39 : `def update(self, index: int, *, status: str, details: dict[str, Any] | None=None) -> None`
- [_chunk_path](../../dataIntegrityEngine/cn_sprint7b_full.py) — ligne 51 : `def _chunk_path(root: Path, index: int) -> Path`
- [run_chunk](../../dataIntegrityEngine/cn_sprint7b_full.py) — ligne 58 : `def run_chunk(engine, *, index: int, chunks_root: Path, start: date, end: date, state: Sprint7BState, force: bool=False) -> dict[str, Any]`
- [_write_report](../../dataIntegrityEngine/cn_sprint7b_full.py) — ligne 94 : `def _write_report(payload: dict[str, Any]) -> Path`
- [main](../../dataIntegrityEngine/cn_sprint7b_full.py) — ligne 102 : `def main() -> None`

## `dataIntegrityEngine/cn_sprint7c_incremental.py`

Source SHA-256 : `cff26197d5d836e4a54d39af14d8bf2ad44206f4f649211603eb2cad0a6511d6`

- [verify_bounds](../../dataIntegrityEngine/cn_sprint7c_incremental.py) — ligne 35 : `def verify_bounds(start: date, end: date, *, allow_same_day_after_close: bool=False) -> None`
- [_write_new_report](../../dataIntegrityEngine/cn_sprint7c_incremental.py) — ligne 41 : `def _write_new_report(root: Path, action: str, payload: dict) -> Path`
- [prepare](../../dataIntegrityEngine/cn_sprint7c_incremental.py) — ligne 51 : `def prepare(engine, *, start: date, end: date, manifest: Path, chunks_root: Path, chunk_size: int, seed_manifest: Path, allow_same_day_after_close: bool=False) -> dict`
- [run_chunk](../../dataIntegrityEngine/cn_sprint7c_incremental.py) — ligne 77 : `def run_chunk(engine, *, start: date, end: date, manifest: Path, collect_source: bool=True, allow_same_day_after_close: bool=False) -> dict`
- [_atomic_state](../../dataIntegrityEngine/cn_sprint7c_incremental.py) — ligne 103 : `def _atomic_state(path: Path, payload: dict) -> None`
- [_retryable_baostock_failure](../../dataIntegrityEngine/cn_sprint7c_incremental.py) — ligne 122 : `def _retryable_baostock_failure(exc: Exception) -> bool`
- [_collect_chunk_with_network_retry](../../dataIntegrityEngine/cn_sprint7c_incremental.py) — ligne 146 : `def _collect_chunk_with_network_retry(engine, *, start: date, end: date, manifest: Path, max_attempts: int=5) -> dict`
- [run_all](../../dataIntegrityEngine/cn_sprint7c_incremental.py) — ligne 167 : `def run_all(engine, *, start: date, end: date, chunks_root: Path, output_root: Path, start_chunk: int=0, max_chunks: int | None=None, allow_same_day_after_close: bool=False) -> dict`
- [main](../../dataIntegrityEngine/cn_sprint7c_incremental.py) — ligne 233 : `def main() -> None`

## `dataIntegrityEngine/cn_sprint8_audit.py`

Source SHA-256 : `8c2f3fda31403bb02d21682c99b63c796ac8f0f3057609777b52b9dc97a7951f`

- [audit](../../dataIntegrityEngine/cn_sprint8_audit.py) — ligne 19 : `def audit(*, start: date, end: date, config: Path) -> dict`
- [main](../../dataIntegrityEngine/cn_sprint8_audit.py) — ligne 151 : `def main() -> None`

## `dataIntegrityEngine/cn_sprint8_universe.py`

Source SHA-256 : `48ae2195ae7575822fb773df184300135cd30fd445d40491349ef66697f64fdb`

- [main](../../dataIntegrityEngine/cn_sprint8_universe.py) — ligne 21 : `def main() -> None`

## `dataIntegrityEngine/cn_sprint9_audit.py`

Source SHA-256 : `a7ff8c85e48c17c00012ed1182080d5214170be144ff2cadaf2451f1a7134f13`

- [_sha256](../../dataIntegrityEngine/cn_sprint9_audit.py) — ligne 14 : `def _sha256(path: Path) -> str`
- [audit](../../dataIntegrityEngine/cn_sprint9_audit.py) — ligne 22 : `def audit(root: Path, *, start_year: int=2018, end_year: int=2025) -> dict[str, Any]`
- [main](../../dataIntegrityEngine/cn_sprint9_audit.py) — ligne 69 : `def main() -> None`

## `dataIntegrityEngine/cn_sprint9_features.py`

Source SHA-256 : `acdc8c5a4543124f1f49ef49c89f53ac40fa61443c6b8b33b10d8b025ccb5818`

- [main](../../dataIntegrityEngine/cn_sprint9_features.py) — ligne 13 : `def main() -> None`

## `dataIntegrityEngine/cross_check_stooq.py`

Source SHA-256 : `3d3260635d1bdc4ddabde2e8955e2f79e438cc6235b1170df41aacd9620d7fec`

- [compare_with_stooq](../../dataIntegrityEngine/cross_check_stooq.py) — ligne 35 : `def compare_with_stooq(ingested_bars: Mapping[str, Sequence[Mapping[str, Any]]], *, lookback_days: int=30, close_tolerance_pct: float=DEFAULT_CLOSE_TOLERANCE_PCT, volume_ratio_min: float=DEFAULT_VOLUME_RATIO_MIN, today: date | None=None) -> list[dict[str, Any]]`
- [_f](../../dataIntegrityEngine/cross_check_stooq.py) — ligne 121 : `def _f(value: Any) -> float | None`

## `dataIntegrityEngine/data_sanitizer_daily.py`

Source SHA-256 : `e5d87d350453fcf2d48322e940fd0551ada61d918e3442b6c6d1d1d0771b4804`

- [_utc_now_naive](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 60 : `def _utc_now_naive() -> datetime`
- [_build_run_id](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 64 : `def _build_run_id(prefix: str) -> str`
- [_emit_run_summary](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 68 : `def _emit_run_summary(summary: dict[str, object]) -> None`
- [DataQualityError](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 75 : `class DataQualityError(RuntimeError)`
- [DataSanitizer](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 79 : `class DataSanitizer`
- [DataSanitizer.__init__](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 89 : `def __init__(self, engine: Engine | None=None, db_user_env: str='LOGIN_DB', db_pass_env: str='PASSWORD_DB', db_host: str='localhost', db_name: str='alpha_trade')`
- [DataSanitizer._ensure_tables_reflected](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 113 : `def _ensure_tables_reflected(self) -> None`
- [DataSanitizer._reflect_tables](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 120 : `def _reflect_tables(self) -> None`
- [DataSanitizer._empty_bar_frame](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 129 : `def _empty_bar_frame() -> pl.DataFrame`
- [DataSanitizer._slice_cached_calendar](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 134 : `def _slice_cached_calendar(calendar: pl.DataFrame, start: date, end: date) -> pl.DataFrame`
- [DataSanitizer._covers_date_range](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 138 : `def _covers_date_range(calendar: pl.DataFrame, start: date, end: date) -> bool`
- [DataSanitizer._ensure_spy_1d_available](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 143 : `def _ensure_spy_1d_available(self, conn: Connection) -> None`
- [DataSanitizer._fetch_calendar_dates_from_spy](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 155 : `def _fetch_calendar_dates_from_spy(self, conn: Connection, start: Optional[date]) -> list[date]`
- [DataSanitizer._build_symbol_frame](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 166 : `def _build_symbol_frame(self, bars: list[dict]) -> pl.DataFrame`
- [DataSanitizer._build_audit_payload](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 193 : `def _build_audit_payload(last_sync: Optional[date], missing_days: Optional[int], anomaly_count: Optional[int], status: str, error_message: Optional[str]=None) -> dict`
- [DataSanitizer._compute_fill_streaks](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 209 : `def _compute_fill_streaks(missing_flags: list[bool]) -> list[int]`
- [DataSanitizer._compute_rebuild_start_date](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 221 : `def _compute_rebuild_start_date(last_sync: Optional[date]) -> Optional[date]`
- [DataSanitizer._compute_resume_anchor](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 227 : `def _compute_resume_anchor(*dates: Optional[date]) -> Optional[date]`
- [DataSanitizer._last_frame_date](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 234 : `def _last_frame_date(df: pl.DataFrame) -> Optional[date]`
- [DataSanitizer._should_commit](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 240 : `def _should_commit(processed_count: int, commit_every: int) -> bool`
- [DataSanitizer._format_exception_message](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 244 : `def _format_exception_message(exc: Exception) -> str`
- [DataSanitizer._commit_batch](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 255 : `def _commit_batch(self, transaction, conn: Connection)`
- [DataSanitizer._log_failed_audit_summary](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 260 : `def _log_failed_audit_summary(self, conn: Connection, limit: int=20) -> None`
- [DataSanitizer._process_symbol](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 280 : `def _process_symbol(self, conn: Connection, symbol: str) -> tuple[bool, dict, int]`
- [DataSanitizer._to_ny_date](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 307 : `def _to_ny_date(self, ts_value: date | datetime | str) -> date`
- [DataSanitizer.load_spy_calendar](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 318 : `def load_spy_calendar(self, conn: Connection, start: date, end: date) -> pl.DataFrame`
- [DataSanitizer.fetch_symbol_bars_1d](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 354 : `def fetch_symbol_bars_1d(self, conn: Connection, symbol: str, start: Optional[date]) -> pl.DataFrame`
- [DataSanitizer.sanitize_and_align](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 359 : `def sanitize_and_align(self, df: pl.DataFrame, calendar: pl.DataFrame, prev_close: Optional[float]) -> tuple[pl.DataFrame, int]`
- [DataSanitizer.detect_anomalies](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 432 : `def detect_anomalies(self, df: pl.DataFrame) -> tuple[pl.DataFrame, int]`
- [DataSanitizer.run_pipeline](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 455 : `def run_pipeline(self, symbols: Optional[list[str]]=None, commit_every: int=DEFAULT_COMMIT_EVERY) -> dict[str, object]`
- [main](../../dataIntegrityEngine/data_sanitizer_daily.py) — ligne 588 : `def main() -> None`

## `dataIntegrityEngine/data_source_health.py`

Source SHA-256 : `48f2542e698784e2a6f1c72bcf35acf645ce2ddd6e4b2a720d2c1a5b196a30d1`

- [_resolve_threshold_from_config](../../dataIntegrityEngine/data_source_health.py) — ligne 30 : `def _resolve_threshold_from_config(default: float) -> float`
- [fetch_data_source_counts](../../dataIntegrityEngine/data_source_health.py) — ligne 42 : `def fetch_data_source_counts(engine: Engine, *, recent_days: int=DEFAULT_RECENT_DAYS) -> dict[str, int]`
- [check_data_source_homogeneity](../../dataIntegrityEngine/data_source_health.py) — ligne 65 : `def check_data_source_homogeneity(engine: Engine, *, min_dominant_ratio: float | None=None, recent_days: int=DEFAULT_RECENT_DAYS, log_warning: bool=True) -> dict[str, Any]`

## `dataIntegrityEngine/eodhd/__init__.py`

Source SHA-256 : `cace40a7e728448a8fe4619d082016171428bffbad8e58265700125646f8c2c3`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `dataIntegrityEngine/eodhd/cli.py`

Source SHA-256 : `312cbca034737e26767dcb82d2ceef37f3370ce855c849ef9f0791ffcbab07a9`

- [_shim](../../dataIntegrityEngine/eodhd/cli.py) — ligne 27 : `def _shim()`
- [build_arg_parser](../../dataIntegrityEngine/eodhd/cli.py) — ligne 32 : `def build_arg_parser() -> argparse.ArgumentParser`
- [main](../../dataIntegrityEngine/eodhd/cli.py) — ligne 65 : `def main(argv: Optional[list[str]]=None) -> int`

## `dataIntegrityEngine/eodhd/orchestrator.py`

Source SHA-256 : `7f7db494c46b899c3ee3ba1e92e88b9df30864cb4870b918a2f5647dcaac229c`

- [_shim](../../dataIntegrityEngine/eodhd/orchestrator.py) — ligne 50 : `def _shim()`
- [_flush_pending_write_rows](../../dataIntegrityEngine/eodhd/orchestrator.py) — ligne 56 : `def _flush_pending_write_rows(*, session, rows_daily: list[dict], rows_bars: list[dict], summary: dict[str, Any], symbol_index: int, reason: str) -> tuple[list[dict], list[dict]]`
- [resolve_target_date](../../dataIntegrityEngine/eodhd/orchestrator.py) — ligne 95 : `def resolve_target_date(config: dict, today: Optional[date]=None) -> str`
- [run_eodhd_ingestion](../../dataIntegrityEngine/eodhd/orchestrator.py) — ligne 105 : `def run_eodhd_ingestion(*, dry_run: bool=True, target_date: Optional[str]=None, symbols: Optional[list[str]]=None, per_symbol_limit: int=DEFAULT_PER_SYMBOL_LIMIT, enable_stooq_cross_check: bool=True, write_commit_every_symbols: int=DEFAULT_WRITE_COMMIT_EVERY_SYMBOLS, config: Optional[dict]=None, session=None, tracker: Optional[EodhdQuotaTracker]=None, cache: Optional[EodhdDiskCache]=None, refresh_target_date: bool=False) -> dict[str, Any]`
- [finalize](../../dataIntegrityEngine/eodhd/orchestrator.py) — ligne 435 : `def finalize(summary: dict[str, Any], started_at: datetime, tracker: EodhdQuotaTracker) -> dict[str, Any]`

## `dataIntegrityEngine/eodhd/progress.py`

Source SHA-256 : `8d200dbc82828291fa38e221fb36a5235ec7404dfb68f6719518eb7760002a69`

- [utc_now_naive](../../dataIntegrityEngine/eodhd/progress.py) — ligne 17 : `def utc_now_naive() -> datetime`
- [build_run_id](../../dataIntegrityEngine/eodhd/progress.py) — ligne 21 : `def build_run_id(prefix: str='import-eodhd') -> str`
- [emit_run_summary](../../dataIntegrityEngine/eodhd/progress.py) — ligne 25 : `def emit_run_summary(summary: dict[str, Any]) -> None`
- [emit_live_progress_summary](../../dataIntegrityEngine/eodhd/progress.py) — ligne 32 : `def emit_live_progress_summary(summary: dict[str, Any]) -> None`
- [should_log_symbol_progress](../../dataIntegrityEngine/eodhd/progress.py) — ligne 37 : `def should_log_symbol_progress(index: int, total: int) -> bool`

## `dataIntegrityEngine/eodhd/readiness.py`

Source SHA-256 : `e07db122be54848dc365183b70404fb75980a5829baca9878fb80cd98e32db65`

- [publication_offset](../../dataIntegrityEngine/eodhd/readiness.py) — ligne 13 : `def publication_offset(config)`
- [calendar_us](../../dataIntegrityEngine/eodhd/readiness.py) — ligne 20 : `def calendar_us()`
- [publication_at](../../dataIntegrityEngine/eodhd/readiness.py) — ligne 25 : `def publication_at(day, config, *, calendar=None)`
- [latest_published_session](../../dataIntegrityEngine/eodhd/readiness.py) — ligne 33 : `def latest_published_session(config, *, now=None, calendar=None)`
- [wait_for_publication](../../dataIntegrityEngine/eodhd/readiness.py) — ligne 46 : `def wait_for_publication(day, config, *, now_fn=None, sleep_fn=None, calendar=None)`
- [target_coverage](../../dataIntegrityEngine/eodhd/readiness.py) — ligne 64 : `def target_coverage(engine, symbols, day, *, benchmark='SPY', minimum=0.95)`

## `dataIntegrityEngine/eodhd/transforms.py`

Source SHA-256 : `2200c0c55536b0f08810ebe0631085a8bac8ca9a67e8eace4087660497a8aaef`

- [normalize_date](../../dataIntegrityEngine/eodhd/transforms.py) — ligne 16 : `def normalize_date(value: date | str | datetime | None) -> Optional[date]`
- [index_bulk_by_project_symbol](../../dataIntegrityEngine/eodhd/transforms.py) — ligne 29 : `def index_bulk_by_project_symbol(bulk: Iterable[dict], universe: set[str]) -> dict[str, dict]`
- [bulk_entry_to_raw_bar](../../dataIntegrityEngine/eodhd/transforms.py) — ligne 51 : `def bulk_entry_to_raw_bar(entry: dict, target_date: str) -> dict`
- [rows_to_raw_bars](../../dataIntegrityEngine/eodhd/transforms.py) — ligne 64 : `def rows_to_raw_bars(rows: Iterable[dict]) -> list[dict]`
- [dedupe_raw_bars_by_date](../../dataIntegrityEngine/eodhd/transforms.py) — ligne 84 : `def dedupe_raw_bars_by_date(raw_bars: Iterable[dict]) -> list[dict]`
- [resolve_missing_fetch_window](../../dataIntegrityEngine/eodhd/transforms.py) — ligne 94 : `def resolve_missing_fetch_window(last_known_date: Optional[date], target_date_value: date, *, target_date_covered_by_bulk: bool) -> tuple[Optional[str], Optional[str]]`
- [is_known_unsupported_fallback_symbol](../../dataIntegrityEngine/eodhd/transforms.py) — ligne 109 : `def is_known_unsupported_fallback_symbol(symbol: str) -> bool`

## `dataIntegrityEngine/import_alpaca_assets.py`

Source SHA-256 : `62115e9c8c2d52ef96aba637abca353ebb9c308c1362100b11f149b66d49dade`

- [_utc_now_naive](../../dataIntegrityEngine/import_alpaca_assets.py) — ligne 17 : `def _utc_now_naive() -> datetime`
- [_build_run_id](../../dataIntegrityEngine/import_alpaca_assets.py) — ligne 21 : `def _build_run_id(prefix: str) -> str`
- [_emit_run_summary](../../dataIntegrityEngine/import_alpaca_assets.py) — ligne 25 : `def _emit_run_summary(summary: Dict[str, Any]) -> None`
- [import_alpaca_assets](../../dataIntegrityEngine/import_alpaca_assets.py) — ligne 32 : `def import_alpaca_assets() -> Dict[str, Any]`
- [main](../../dataIntegrityEngine/import_alpaca_assets.py) — ligne 58 : `def main() -> None`

## `dataIntegrityEngine/import_alpaca_bar.py`

Source SHA-256 : `9e1cd624a00a8611eb3f5ad1ca3474cbe1c3b439e840a73810b66151c4499ace`

- [_utc_now_naive](../../dataIntegrityEngine/import_alpaca_bar.py) — ligne 47 : `def _utc_now_naive() -> datetime`
- [_build_run_id](../../dataIntegrityEngine/import_alpaca_bar.py) — ligne 51 : `def _build_run_id(prefix: str) -> str`
- [_emit_run_summary](../../dataIntegrityEngine/import_alpaca_bar.py) — ligne 55 : `def _emit_run_summary(summary: dict[str, Any]) -> None`
- [_coerce_to_date](../../dataIntegrityEngine/import_alpaca_bar.py) — ligne 62 : `def _coerce_to_date(value: Any) -> Any`
- [_count_trading_days_between](../../dataIntegrityEngine/import_alpaca_bar.py) — ligne 68 : `def _count_trading_days_between(start_date: Any, end_date: Any) -> Optional[int]`
- [_assess_staleness](../../dataIntegrityEngine/import_alpaca_bar.py) — ligne 82 : `def _assess_staleness(last_timestamp: Any, market_date: Any) -> dict[str, Any]`
- [_get_tables](../../dataIntegrityEngine/import_alpaca_bar.py) — ligne 107 : `def _get_tables() -> tuple[Table, Table]`
- [get_active_tradable_symbols](../../dataIntegrityEngine/import_alpaca_bar.py) — ligne 115 : `def get_active_tradable_symbols(session) -> list[str]`
- [symbol_exists_in_stock_bars](../../dataIntegrityEngine/import_alpaca_bar.py) — ligne 121 : `def symbol_exists_in_stock_bars(session, symbol: str) -> bool`
- [get_last_bar_timestamp](../../dataIntegrityEngine/import_alpaca_bar.py) — ligne 127 : `def get_last_bar_timestamp(session, symbol: str, time_frame: TimeFrame)`
- [_normalize_bar_timestamp](../../dataIntegrityEngine/import_alpaca_bar.py) — ligne 135 : `def _normalize_bar_timestamp(raw_timestamp: Any) -> Any`
- [_sanitize_price](../../dataIntegrityEngine/import_alpaca_bar.py) — ligne 145 : `def _sanitize_price(value: Any, field: str, symbol: str) -> Optional[float]`
- [_sanitize_non_negative_int](../../dataIntegrityEngine/import_alpaca_bar.py) — ligne 168 : `def _sanitize_non_negative_int(value: Any, field: str, symbol: str) -> Optional[int]`
- [_validate_bar_business_rules](../../dataIntegrityEngine/import_alpaca_bar.py) — ligne 188 : `def _validate_bar_business_rules(*, symbol: str, timestamp: Any, open_price: float, high_price: float, low_price: float, close_price: float, volume: int, trade_count: int, vwa_price: Optional[float]) -> Optional[str]`
- [_build_bar_records](../../dataIntegrityEngine/import_alpaca_bar.py) — ligne 215 : `def _build_bar_records(symbol: str, bars: list[dict[str, Any]], timeframe: str) -> list[dict[str, Any]]`
- [insert_bars](../../dataIntegrityEngine/import_alpaca_bar.py) — ligne 294 : `def insert_bars(session, symbol: str, bars: list[dict[str, Any]], timeframe: str) -> int`
- [_format_last_timestamp](../../dataIntegrityEngine/import_alpaca_bar.py) — ligne 325 : `def _format_last_timestamp(last_timestamp: Any) -> Optional[str]`
- [_increment_start_timestamp](../../dataIntegrityEngine/import_alpaca_bar.py) — ligne 333 : `def _increment_start_timestamp(raw_timestamp: Optional[str]) -> Optional[str]`
- [_normalize_target_symbols](../../dataIntegrityEngine/import_alpaca_bar.py) — ligne 342 : `def _normalize_target_symbols(symbols: Optional[list[str]]) -> Optional[list[str]]`
- [import_alpaca_bars](../../dataIntegrityEngine/import_alpaca_bar.py) — ligne 346 : `def import_alpaca_bars(time_frame: TimeFrame, symbols: Optional[list[str]]=None) -> dict[str, Any]`
- [_build_arg_parser](../../dataIntegrityEngine/import_alpaca_bar.py) — ligne 537 : `def _build_arg_parser() -> argparse.ArgumentParser`
- [_resolve_bars_provider](../../dataIntegrityEngine/import_alpaca_bar.py) — ligne 564 : `def _resolve_bars_provider() -> str`
- [main](../../dataIntegrityEngine/import_alpaca_bar.py) — ligne 583 : `def main(argv: Optional[list[str]]=None) -> int`

## `dataIntegrityEngine/import_eodhd_bar.py`

Source SHA-256 : `a0a35be316fd2b03019059849bbf4a57d069171096c335d7c35d9a71565b59e0`

- [resolve_bars_provider](../../dataIntegrityEngine/import_eodhd_bar.py) — ligne 114 : `def resolve_bars_provider(config: dict | None=None) -> str`
- [_load_config_safe](../../dataIntegrityEngine/import_eodhd_bar.py) — ligne 124 : `def _load_config_safe() -> dict`
- [_get_tables](../../dataIntegrityEngine/import_eodhd_bar.py) — ligne 140 : `def _get_tables() -> tuple[Table, Table, Table]`
- [_reset_tables_cache](../../dataIntegrityEngine/import_eodhd_bar.py) — ligne 149 : `def _reset_tables_cache() -> None`
- [_get_active_tradable_symbols](../../dataIntegrityEngine/import_eodhd_bar.py) — ligne 153 : `def _get_active_tradable_symbols(session) -> list[str]`
- [_get_latest_bar_dates](../../dataIntegrityEngine/import_eodhd_bar.py) — ligne 163 : `def _get_latest_bar_dates(session, symbols: Iterable[str]) -> dict[str, date]`
- [_cached_fetch_splits](../../dataIntegrityEngine/import_eodhd_bar.py) — ligne 191 : `def _cached_fetch_splits(symbol: str, *, cache: EodhdDiskCache, tracker: EodhdQuotaTracker, ttl_seconds: float=DEFAULT_TTL_SPLITS_SECONDS, fetch_fn=None) -> list[dict]`
- [_upsert_stock_bars_daily](../../dataIntegrityEngine/import_eodhd_bar.py) — ligne 223 : `def _upsert_stock_bars_daily(session, rows: list[dict]) -> int`
- [_upsert_stock_bars](../../dataIntegrityEngine/import_eodhd_bar.py) — ligne 239 : `def _upsert_stock_bars(session, rows: list[dict]) -> int`

## `dataIntegrityEngine/sync_earnings_calendar.py`

Source SHA-256 : `1ff9d0c5d3f811e6f5de361f7765bcc9bc964a9b0efe1fe1dd59a1b493dfc4ee`

- [SyncEarningsCalendarError](../../dataIntegrityEngine/sync_earnings_calendar.py) — ligne 30 : `class SyncEarningsCalendarError(RuntimeError)`
- [SyncEarningsCalendarError.__init__](../../dataIntegrityEngine/sync_earnings_calendar.py) — ligne 31 : `def __init__(self, message: str, *, summary: dict[str, object]) -> None`
- [_utc_now_naive](../../dataIntegrityEngine/sync_earnings_calendar.py) — ligne 36 : `def _utc_now_naive() -> datetime`
- [_build_run_id](../../dataIntegrityEngine/sync_earnings_calendar.py) — ligne 40 : `def _build_run_id(prefix: str) -> str`
- [_emit_run_summary](../../dataIntegrityEngine/sync_earnings_calendar.py) — ligne 44 : `def _emit_run_summary(summary: dict[str, object]) -> None`
- [_coerce_bookmark_path](../../dataIntegrityEngine/sync_earnings_calendar.py) — ligne 51 : `def _coerce_bookmark_path(path: str | Path | None) -> Path`
- [_default_bookmark_state](../../dataIntegrityEngine/sync_earnings_calendar.py) — ligne 55 : `def _default_bookmark_state(*, context: dict[str, object]) -> dict[str, Any]`
- [load_bookmark](../../dataIntegrityEngine/sync_earnings_calendar.py) — ligne 64 : `def load_bookmark(path: str | Path | None=None) -> dict[str, Any]`
- [save_bookmark](../../dataIntegrityEngine/sync_earnings_calendar.py) — ligne 83 : `def save_bookmark(path: str | Path | None, state: dict[str, Any]) -> None`
- [clear_bookmark](../../dataIntegrityEngine/sync_earnings_calendar.py) — ligne 89 : `def clear_bookmark(path: str | Path | None=None) -> None`
- [_normalize_bookmark_symbols](../../dataIntegrityEngine/sync_earnings_calendar.py) — ligne 95 : `def _normalize_bookmark_symbols(values: object) -> list[str]`
- [_build_bookmark_context](../../dataIntegrityEngine/sync_earnings_calendar.py) — ligne 101 : `def _build_bookmark_context(*, start: date, end: date, limit: int | None, symbol_source: str | None, provider: str) -> dict[str, object]`
- [_resolve_bookmark_state](../../dataIntegrityEngine/sync_earnings_calendar.py) — ligne 111 : `def _resolve_bookmark_state(path: Path, *, resume: bool, context: dict[str, object]) -> tuple[dict[str, Any], set[str]]`
- [_normalize_rows](../../dataIntegrityEngine/sync_earnings_calendar.py) — ligne 140 : `def _normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, object]]`
- [_validate_batch_size](../../dataIntegrityEngine/sync_earnings_calendar.py) — ligne 160 : `def _validate_batch_size(batch_size: int) -> None`
- [_pick_quarterly_facts](../../dataIntegrityEngine/sync_earnings_calendar.py) — ligne 188 : `def _pick_quarterly_facts(us_gaap: dict[str, Any], tags: tuple[str, ...]) -> dict[tuple[int, str], dict[str, object]]`
- [_fetch_sec_earnings](../../dataIntegrityEngine/sync_earnings_calendar.py) — ligne 246 : `def _fetch_sec_earnings(symbol: str, *, from_date: date, to_date: date) -> list[dict[str, object]]`
- [_resolve_universe](../../dataIntegrityEngine/sync_earnings_calendar.py) — ligne 278 : `def _resolve_universe(*, symbol_source: str | None, symbols_file: str | Path | None, limit: int | None) -> tuple[list[str], str]`
- [sync_earnings_calendar](../../dataIntegrityEngine/sync_earnings_calendar.py) — ligne 315 : `def sync_earnings_calendar(*, from_date: date | None=None, to_date: date | None=None, limit: int | None=None, symbol_source: str | None=None, symbols_file: str | Path | None=None, sleep_seconds: float=MIN_REQUEST_INTERVAL_SECONDS, log_every: int=25, batch_size: int=DEFAULT_BATCH_SIZE, resume: bool=DEFAULT_RESUME, bookmark_path: str | Path | None=None, provider: str='finnhub') -> dict[str, object]`
- [_build_arg_parser](../../dataIntegrityEngine/sync_earnings_calendar.py) — ligne 513 : `def _build_arg_parser() -> argparse.ArgumentParser`
- [main](../../dataIntegrityEngine/sync_earnings_calendar.py) — ligne 544 : `def main() -> None`

## `dataIntegrityEngine/sync_latest_quotes.py`

Source SHA-256 : `b4dff3543517f099405ebb92b43ec3f50a4dc3202df1f89cd802b161c7ba91ee`

- [_parse_alpaca_timestamp](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 51 : `def _parse_alpaca_timestamp(value: object) -> datetime | None`
- [_utc_now_naive](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 97 : `def _utc_now_naive() -> datetime`
- [_market_date_from_timestamp](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 101 : `def _market_date_from_timestamp(quote_timestamp: datetime | None, *, fallback_utc_now: datetime | None=None) -> date`
- [_build_run_id](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 123 : `def _build_run_id(prefix: str) -> str`
- [_emit_run_summary](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 127 : `def _emit_run_summary(summary: dict[str, object]) -> None`
- [_to_iso_zulu](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 134 : `def _to_iso_zulu(value: datetime) -> str`
- [_month_end](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 138 : `def _month_end(value: date) -> date`
- [_iter_monthly_blocks](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 144 : `def _iter_monthly_blocks(start: date, end: date) -> list[tuple[date, date]]`
- [_iter_year_blocks](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 156 : `def _iter_year_blocks(start: date, end: date) -> list[tuple[date, date]]`
- [_session_window](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 169 : `def _session_window(session_date: date) -> list[tuple[datetime, datetime]]`
- [_resolve_account_cycler](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 177 : `def _resolve_account_cycler() -> itertools.cycle[str] | None`
- [_bump_account](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 192 : `def _bump_account(account_cycler: itertools.cycle[str] | None) -> str | None`
- [_resolve_latest_quotes_fetcher](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 199 : `def _resolve_latest_quotes_fetcher() -> tuple[object, str, object | None]`
- [_symbol_has_any_quotes_in_window](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 255 : `def _symbol_has_any_quotes_in_window(symbol: str, from_date: date, to_date: date, *, session: requests.Session, account_id: str | None=None) -> bool`
- [_fetch_near_close_quote_for_session](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 278 : `def _fetch_near_close_quote_for_session(symbol: str, session_date: date, *, session: requests.Session, account_id: str | None=None) -> tuple[dict[str, object] | None, int | None, tuple[datetime, datetime] | None]`
- [_log_historical_symbol_summary](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 298 : `def _log_historical_symbol_summary(*, symbol_source: str, index: int, total_symbols: int, symbol: str, from_date: date, to_date: date, missing_ranges: int, missing_days: int, fetched_ranges: int, skipped_existing: bool) -> None`
- [_compute_spread_bps](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 327 : `def _compute_spread_bps(bid_price: float | None, ask_price: float | None) -> float | None`
- [_to_optional_float](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 338 : `def _to_optional_float(value: object) -> float | None`
- [_to_int](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 342 : `def _to_int(value: object, default: int=0) -> int`
- [_coerce_sql_date](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 349 : `def _coerce_sql_date(value: object) -> date | None`
- [_normalize_quote_window](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 362 : `def _normalize_quote_window(from_date: date | None, to_date: date | None) -> tuple[date | None, date | None]`
- [_iter_symbol_batches](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 375 : `def _iter_symbol_batches(symbols: list[str], *, batch_size: int=500) -> list[list[str]]`
- [_resolve_quote_bias_window](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 381 : `def _resolve_quote_bias_window(from_date: date | None, to_date: date | None) -> tuple[date, date, str]`
- [_load_quote_rows_for_bias](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 392 : `def _load_quote_rows_for_bias(*, symbols: list[str], from_date: date, to_date: date) -> list[dict[str, object]]`
- [_load_consolidated_close_map](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 420 : `def _load_consolidated_close_map(*, symbols: list[str], from_date: date, to_date: date) -> dict[tuple[str, date], float]`
- [_build_quote_bias_summary_from_rows](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 456 : `def _build_quote_bias_summary_from_rows(quote_rows: list[dict[str, object]], consolidated_close_map: dict[tuple[str, date], float]) -> dict[str, object]`
- [build_quote_iex_vs_consolidated_bias_summary](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 520 : `def build_quote_iex_vs_consolidated_bias_summary(*, from_date: date | None, to_date: date | None, symbol_source: str | None, limit: int | None, start_symbol: str | None) -> dict[str, object]`
- [safe_build_quote_iex_vs_consolidated_bias_summary](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 565 : `def safe_build_quote_iex_vs_consolidated_bias_summary(*, from_date: date | None, to_date: date | None, symbol_source: str | None, limit: int | None, start_symbol: str | None) -> dict[str, object]`
- [estimate_sync_latest_quotes_cost](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 600 : `def estimate_sync_latest_quotes_cost(*, symbol_count: int, batch_size: int=DEFAULT_BATCH_SIZE, from_date: date | None=None, to_date: date | None=None) -> dict[str, object]`
- [_build_quote_snapshot_row](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 669 : `def _build_quote_snapshot_row(symbol: str, quote: dict[str, object], *, fallback_utc_now: datetime) -> dict[str, object]`
- [sync_latest_quotes](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 690 : `def sync_latest_quotes(limit: int | None=None, batch_size: int=DEFAULT_BATCH_SIZE, *, from_date: date | None=None, to_date: date | None=None, symbol_source: str | None=None, start_symbol: str | None=None) -> dict[str, int]`
- [_build_arg_parser](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 1061 : `def _build_arg_parser() -> argparse.ArgumentParser`
- [main](../../dataIntegrityEngine/sync_latest_quotes.py) — ligne 1072 : `def main() -> None`

## `dataIntegrityEngine/update_sector.py`

Source SHA-256 : `0cf8d29b31d2e81d148955ce34bcd63b0534e30be94131be5a4b0065197165e1`

- [_utc_now_naive](../../dataIntegrityEngine/update_sector.py) — ligne 49 : `def _utc_now_naive() -> datetime`
- [_build_run_id](../../dataIntegrityEngine/update_sector.py) — ligne 53 : `def _build_run_id(prefix: str) -> str`
- [_emit_run_summary](../../dataIntegrityEngine/update_sector.py) — ligne 57 : `def _emit_run_summary(summary: dict[str, Any]) -> None`
- [update_stock_metadata_sector](../../dataIntegrityEngine/update_sector.py) — ligne 67 : `def update_stock_metadata_sector(symbol: str, sector: str) -> int`
- [_normalize_provider](../../dataIntegrityEngine/update_sector.py) — ligne 71 : `def _normalize_provider(provider: str) -> FundamentalsProvider`
- [_select_target_symbols](../../dataIntegrityEngine/update_sector.py) — ligne 88 : `def _select_target_symbols(*, limit: int | None, refresh_stale_days: int | None, overwrite_existing: bool) -> tuple[list[str], list[str], list[str]]`
- [_load_symbols_from_file](../../dataIntegrityEngine/update_sector.py) — ligne 118 : `def _load_symbols_from_file(filepath: str) -> list[str]`
- [_resolve_symbol_source](../../dataIntegrityEngine/update_sector.py) — ligne 139 : `def _resolve_symbol_source(source: str, *, start_date: str | None=None, end_date: str | None=None) -> list[str]`
- [_fetch_fundamentals](../../dataIntegrityEngine/update_sector.py) — ligne 183 : `def _fetch_fundamentals(symbol: str, *, provider: FundamentalsProvider, session: requests.Session) -> dict[str, Any]`
- [_normalize_sector](../../dataIntegrityEngine/update_sector.py) — ligne 199 : `def _normalize_sector(value: Any) -> str | None`
- [_build_update_payload](../../dataIntegrityEngine/update_sector.py) — ligne 206 : `def _build_update_payload(*, symbol: str, fetched_sector: str | None, fetched_market_cap: float | None, existing_row: dict[str, Any], stale_symbols: set[str], overwrite_existing: bool) -> dict[str, Any]`
- [update_missing_sectors](../../dataIntegrityEngine/update_sector.py) — ligne 233 : `def update_missing_sectors(limit: int | None=None, sleep_seconds: float=MIN_REQUEST_INTERVAL_SECONDS, log_every: int=DEFAULT_LOG_EVERY, *, refresh_stale_days: int | None=None, provider: FundamentalsProvider='yahoo_finance', overwrite_existing: bool=False, explicit_symbols: list[str] | None=None) -> dict[str, Any]`
- [_build_arg_parser](../../dataIntegrityEngine/update_sector.py) — ligne 424 : `def _build_arg_parser() -> argparse.ArgumentParser`
- [main](../../dataIntegrityEngine/update_sector.py) — ligne 504 : `def main() -> None`
