# Inventaire API — dataIntegrityEngine

Cet inventaire est dérivé des signatures présentes dans le code. Les symboles préfixés par `_` restent internes. Les numéros de ligne sont indicatifs ; le chemin et le nom du symbole sont les repères stables.

## `dataIntegrityEngine/backfill_eodhd_history.py`

- ligne 103 — `def load_bookmark(path: Path) -> dict[str, Any]:`
- ligne 113 — `def save_bookmark(path: Path, state: dict[str, Any]) -> None:`
- ligne 118 — `def _filter_remaining(symbols: list[str], bookmark: dict[str, Any]) -> list[str]:`
- ligne 123 — `def _filter_symbols_missing_or_stale_in_db(`
- ligne 146 — `def _eod_rows_to_raw_bars(rows: list[dict]) -> list[dict]:`
- ligne 164 — `def backfill_one_symbol(`
- ligne 231 — `def run_backfill(`
- ligne 430 — `def _finalize(summary, started_at, tracker, bookmark, bookmark_path):`
- ligne 456 — `def _load_config_safe() -> dict:`
- ligne 470 — `def _build_arg_parser() -> argparse.ArgumentParser:`
- ligne 488 — `def main(argv: Optional[list[str]] = None) -> int:`
- ligne 83 — `def _utc_now_naive() -> datetime:`
- ligne 87 — `def _build_run_id(prefix: str = "backfill-eodhd") -> str:`
- ligne 91 — `def _emit_run_summary(summary: dict[str, Any]) -> None:`
## `dataIntegrityEngine/bar_importer_common.py`

- ligne 22 — `def normalize_symbols(symbols: list[str] | None) -> list[str] | None:`
- ligne 8 — `def resolve_bars_provider(config: Mapping[str, Any] | None = None, *, fallback: str = "alpaca") -> str:`
## `dataIntegrityEngine/cross_check_stooq.py`

- ligne 121 — `def _f(value: Any) -> float | None:`
- ligne 35 — `def compare_with_stooq(`
## `dataIntegrityEngine/data_sanitizer_daily.py`

- ligne 588 — `def main() -> None:`
- ligne 60 — `def _utc_now_naive() -> datetime:`
- ligne 64 — `def _build_run_id(prefix: str) -> str:`
- ligne 68 — `def _emit_run_summary(summary: dict[str, object]) -> None:`
- ligne 75 — `class DataQualityError(RuntimeError):`
- ligne 79 — `class DataSanitizer:`
## `dataIntegrityEngine/data_source_health.py`

- ligne 30 — `def _resolve_threshold_from_config(default: float) -> float:`
- ligne 42 — `def fetch_data_source_counts(`
- ligne 65 — `def check_data_source_homogeneity(`
## `dataIntegrityEngine/eodhd/cli.py`

- ligne 26 — `def _shim():`
- ligne 31 — `def build_arg_parser() -> argparse.ArgumentParser:`
- ligne 59 — `def main(argv: Optional[list[str]] = None) -> int:`
## `dataIntegrityEngine/eodhd/orchestrator.py`

- ligne 115 — `def run_eodhd_ingestion(`
- ligne 443 — `def finalize(`
- ligne 50 — `def _shim():`
- ligne 56 — `def _flush_pending_write_rows(`
- ligne 95 — `def resolve_target_date(config: dict, today: Optional[date] = None) -> str:`
## `dataIntegrityEngine/eodhd/progress.py`

- ligne 17 — `def utc_now_naive() -> datetime:`
- ligne 21 — `def build_run_id(prefix: str = "import-eodhd") -> str:`
- ligne 25 — `def emit_run_summary(summary: dict[str, Any]) -> None:`
- ligne 32 — `def emit_live_progress_summary(summary: dict[str, Any]) -> None:`
- ligne 37 — `def should_log_symbol_progress(index: int, total: int) -> bool:`
## `dataIntegrityEngine/eodhd/transforms.py`

- ligne 109 — `def is_known_unsupported_fallback_symbol(symbol: str) -> bool:`
- ligne 16 — `def normalize_date(value: date | str | datetime | None) -> Optional[date]:`
- ligne 29 — `def index_bulk_by_project_symbol(`
- ligne 51 — `def bulk_entry_to_raw_bar(entry: dict, target_date: str) -> dict:`
- ligne 64 — `def rows_to_raw_bars(rows: Iterable[dict]) -> list[dict]:`
- ligne 84 — `def dedupe_raw_bars_by_date(raw_bars: Iterable[dict]) -> list[dict]:`
- ligne 94 — `def resolve_missing_fetch_window(`
## `dataIntegrityEngine/import_alpaca_assets.py`

- ligne 17 — `def _utc_now_naive() -> datetime:`
- ligne 21 — `def _build_run_id(prefix: str) -> str:`
- ligne 25 — `def _emit_run_summary(summary: Dict[str, Any]) -> None:`
- ligne 32 — `def import_alpaca_assets() -> Dict[str, Any]:`
- ligne 58 — `def main() -> None:`
## `dataIntegrityEngine/import_alpaca_bar.py`

- ligne 107 — `def _get_tables() -> tuple[Table, Table]:`
- ligne 115 — `def get_active_tradable_symbols(session) -> list[str]:`
- ligne 121 — `def symbol_exists_in_stock_bars(session, symbol: str) -> bool:`
- ligne 127 — `def get_last_bar_timestamp(session, symbol: str, time_frame: TimeFrame):`
- ligne 135 — `def _normalize_bar_timestamp(raw_timestamp: Any) -> Any:`
- ligne 145 — `def _sanitize_price(value: Any, field: str, symbol: str) -> Optional[float]:`
- ligne 168 — `def _sanitize_non_negative_int(value: Any, field: str, symbol: str) -> Optional[int]:`
- ligne 188 — `def _validate_bar_business_rules(`
- ligne 215 — `def _build_bar_records(symbol: str, bars: list[dict[str, Any]], timeframe: str) -> list[dict[str, Any]]:`
- ligne 294 — `def insert_bars(session, symbol: str, bars: list[dict[str, Any]], timeframe: str) -> int:`
- ligne 325 — `def _format_last_timestamp(last_timestamp: Any) -> Optional[str]:`
- ligne 333 — `def _increment_start_timestamp(raw_timestamp: Optional[str]) -> Optional[str]:`
- ligne 342 — `def _normalize_target_symbols(symbols: Optional[list[str]]) -> Optional[list[str]]:`
- ligne 346 — `def import_alpaca_bars(time_frame: TimeFrame, symbols: Optional[list[str]] = None) -> dict[str, Any]:`
- ligne 47 — `def _utc_now_naive() -> datetime:`
- ligne 51 — `def _build_run_id(prefix: str) -> str:`
- ligne 537 — `def _build_arg_parser() -> argparse.ArgumentParser:`
- ligne 55 — `def _emit_run_summary(summary: dict[str, Any]) -> None:`
- ligne 564 — `def _resolve_bars_provider() -> str:`
- ligne 583 — `def main(argv: Optional[list[str]] = None) -> int:`
- ligne 62 — `def _coerce_to_date(value: Any) -> Any:`
- ligne 68 — `def _count_trading_days_between(start_date: Any, end_date: Any) -> Optional[int]:`
- ligne 82 — `def _assess_staleness(last_timestamp: Any, market_date: Any) -> dict[str, Any]:`
## `dataIntegrityEngine/import_eodhd_bar.py`

- ligne 114 — `def resolve_bars_provider(config: dict | None = None) -> str:`
- ligne 124 — `def _load_config_safe() -> dict:`
- ligne 140 — `def _get_tables() -> tuple[Table, Table, Table]:`
- ligne 149 — `def _reset_tables_cache() -> None:`
- ligne 153 — `def _get_active_tradable_symbols(session) -> list[str]:`
- ligne 163 — `def _get_latest_bar_dates(session, symbols: Iterable[str]) -> dict[str, date]:`
- ligne 191 — `def _cached_fetch_splits(`
- ligne 223 — `def _upsert_stock_bars_daily(session, rows: list[dict]) -> int:`
- ligne 239 — `def _upsert_stock_bars(session, rows: list[dict]) -> int:`
## `dataIntegrityEngine/sync_earnings_calendar.py`

- ligne 101 — `def _build_bookmark_context(*, start: date, end: date, limit: int | None, symbol_source: str | None, provider: str) -> dict[str, object]:`
- ligne 111 — `def _resolve_bookmark_state(`
- ligne 140 — `def _normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, object]]:`
- ligne 160 — `def _validate_batch_size(batch_size: int) -> None:`
- ligne 188 — `def _pick_quarterly_facts(`
- ligne 246 — `def _fetch_sec_earnings(symbol: str, *, from_date: date, to_date: date) -> list[dict[str, object]]:`
- ligne 278 — `def sync_earnings_calendar(`
- ligne 30 — `class SyncEarningsCalendarError(RuntimeError):`
- ligne 36 — `def _utc_now_naive() -> datetime:`
- ligne 40 — `def _build_run_id(prefix: str) -> str:`
- ligne 44 — `def _emit_run_summary(summary: dict[str, object]) -> None:`
- ligne 472 — `def _build_arg_parser() -> argparse.ArgumentParser:`
- ligne 502 — `def main() -> None:`
- ligne 51 — `def _coerce_bookmark_path(path: str | Path | None) -> Path:`
- ligne 55 — `def _default_bookmark_state(*, context: dict[str, object]) -> dict[str, Any]:`
- ligne 64 — `def load_bookmark(path: str | Path | None = None) -> dict[str, Any]:`
- ligne 83 — `def save_bookmark(path: str | Path | None, state: dict[str, Any]) -> None:`
- ligne 89 — `def clear_bookmark(path: str | Path | None = None) -> None:`
- ligne 95 — `def _normalize_bookmark_symbols(values: object) -> list[str]:`
## `dataIntegrityEngine/sync_latest_quotes.py`

- ligne 101 — `def _market_date_from_timestamp(`
- ligne 1061 — `def _build_arg_parser() -> argparse.ArgumentParser:`
- ligne 1072 — `def main() -> None:`
- ligne 123 — `def _build_run_id(prefix: str) -> str:`
- ligne 127 — `def _emit_run_summary(summary: dict[str, object]) -> None:`
- ligne 134 — `def _to_iso_zulu(value: datetime) -> str:`
- ligne 138 — `def _month_end(value: date) -> date:`
- ligne 144 — `def _iter_monthly_blocks(start: date, end: date) -> list[tuple[date, date]]:`
- ligne 156 — `def _iter_year_blocks(start: date, end: date) -> list[tuple[date, date]]:`
- ligne 169 — `def _session_window(session_date: date) -> list[tuple[datetime, datetime]]:`
- ligne 177 — `def _resolve_account_cycler() -> itertools.cycle[str] | None:`
- ligne 192 — `def _bump_account(account_cycler: itertools.cycle[str] | None) -> str | None:`
- ligne 199 — `def _resolve_latest_quotes_fetcher() -> tuple[`
- ligne 255 — `def _symbol_has_any_quotes_in_window(`
- ligne 278 — `def _fetch_near_close_quote_for_session(`
- ligne 298 — `def _log_historical_symbol_summary(`
- ligne 327 — `def _compute_spread_bps(bid_price: float | None, ask_price: float | None) -> float | None:`
- ligne 338 — `def _to_optional_float(value: object) -> float | None:`
- ligne 342 — `def _to_int(value: object, default: int = 0) -> int:`
- ligne 349 — `def _coerce_sql_date(value: object) -> date | None:`
- ligne 362 — `def _normalize_quote_window(`
- ligne 375 — `def _iter_symbol_batches(symbols: list[str], *, batch_size: int = 500) -> list[list[str]]:`
- ligne 381 — `def _resolve_quote_bias_window(`
- ligne 392 — `def _load_quote_rows_for_bias(`
- ligne 420 — `def _load_consolidated_close_map(`
- ligne 456 — `def _build_quote_bias_summary_from_rows(`
- ligne 51 — `def _parse_alpaca_timestamp(value: object) -> datetime | None:`
- ligne 520 — `def build_quote_iex_vs_consolidated_bias_summary(`
- ligne 565 — `def safe_build_quote_iex_vs_consolidated_bias_summary(`
- ligne 600 — `def estimate_sync_latest_quotes_cost(`
- ligne 669 — `def _build_quote_snapshot_row(`
- ligne 690 — `def sync_latest_quotes(`
- ligne 97 — `def _utc_now_naive() -> datetime:`
## `dataIntegrityEngine/update_sector.py`

- ligne 113 — `def _load_symbols_from_file(filepath: str) -> list[str]:`
- ligne 134 — `def _resolve_symbol_source(`
- ligne 177 — `def _fetch_fundamentals(`
- ligne 193 — `def _normalize_sector(value: Any) -> str | None:`
- ligne 200 — `def _build_update_payload(`
- ligne 227 — `def update_missing_sectors(`
- ligne 418 — `def _build_arg_parser() -> argparse.ArgumentParser:`
- ligne 44 — `def _utc_now_naive() -> datetime:`
- ligne 48 — `def _build_run_id(prefix: str) -> str:`
- ligne 492 — `def main() -> None:`
- ligne 52 — `def _emit_run_summary(summary: dict[str, Any]) -> None:`
- ligne 62 — `def update_stock_metadata_sector(symbol: str, sector: str) -> int:`
- ligne 66 — `def _normalize_provider(provider: str) -> FundamentalsProvider:`
- ligne 83 — `def _select_target_symbols(`

