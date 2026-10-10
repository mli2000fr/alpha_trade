# Inventaire API — database

Extraction AST du 2026-10-10 ; aucune importation ni exécution métier.

Classes, fonctions de module et méthodes déclarées ; fonctions imbriquées exclues.
Les symboles `_...` sont internes. Signature présente ≠ API publique stable.

## `database/assets.py`

Source SHA-256 : `7f5ad4958f07777d8c28cfbe767ee6c99e0d9f5bd42fccdd51ca85602488b2d5`

- [get_stock_metadata_table](../../database/assets.py) — ligne 21 : `def get_stock_metadata_table() -> Table`
- [_require_sector_column](../../database/assets.py) — ligne 42 : `def _require_sector_column(stock_metadata: Table) -> None`
- [_resolve_sector_storage_column](../../database/assets.py) — ligne 49 : `def _resolve_sector_storage_column(stock_metadata: Table)`
- [_resolve_sector_storage_column_name](../../database/assets.py) — ligne 56 : `def _resolve_sector_storage_column_name(stock_metadata: Table) -> str`
- [_require_market_cap_column](../../database/assets.py) — ligne 61 : `def _require_market_cap_column(stock_metadata: Table) -> None`
- [_has_history_status_column](../../database/assets.py) — ligne 66 : `def _has_history_status_column(stock_metadata: Table) -> bool`
- [_has_fractionable_column](../../database/assets.py) — ligne 70 : `def _has_fractionable_column(stock_metadata: Table) -> bool`
- [build_eligible_stock_metadata_filters](../../database/assets.py) — ligne 74 : `def build_eligible_stock_metadata_filters(stock_metadata: Table) -> list[Any]`
- [list_eligible_stock_symbols](../../database/assets.py) — ligne 95 : `def list_eligible_stock_symbols(limit: int | None=None, *, engine=None, stock_metadata: Table | None=None) -> list[str]`
- [_has_market_cap_refreshed_at_column](../../database/assets.py) — ligne 121 : `def _has_market_cap_refreshed_at_column(stock_metadata: Table) -> bool`
- [get_symbols_missing_sector](../../database/assets.py) — ligne 125 : `def get_symbols_missing_sector(limit: int | None=None) -> list[str]`
- [get_symbols_missing_fundamentals](../../database/assets.py) — ligne 151 : `def get_symbols_missing_fundamentals(limit: int | None=None) -> list[str]`
- [get_stock_metadata_fundamentals_map](../../database/assets.py) — ligne 179 : `def get_stock_metadata_fundamentals_map(symbols: Iterable[str]) -> dict[str, dict[str, Any]]`
- [get_symbols_with_stale_market_cap](../../database/assets.py) — ligne 216 : `def get_symbols_with_stale_market_cap(*, max_age_days: int, limit: int | None=None) -> list[str]`
- [count_eligible_symbols_with_stale_market_cap](../../database/assets.py) — ligne 265 : `def count_eligible_symbols_with_stale_market_cap(max_age_days: int) -> tuple[int, int]`
- [update_stock_metadata_sector](../../database/assets.py) — ligne 294 : `def update_stock_metadata_sector(symbol: str, sector: str) -> int`
- [update_stock_metadata_fundamentals](../../database/assets.py) — ligne 298 : `def update_stock_metadata_fundamentals(symbol: str, *, provider_sector: str | None=None, sector: str | None=None, market_cap: float | None=None) -> int`
- [insert_assets_to_db](../../database/assets.py) — ligne 339 : `def insert_assets_to_db(assets: Iterable[Mapping[str, Any]]) -> int`
- [sync_assets_from_alpaca](../../database/assets.py) — ligne 389 : `def sync_assets_from_alpaca() -> int`
- [update_bars_available_false](../../database/assets.py) — ligne 393 : `def update_bars_available_false(symbol: str) -> None`
- [mark_symbol_history_ready](../../database/assets.py) — ligne 397 : `def mark_symbol_history_ready(symbol: str) -> int`
- [update_symbol_history_status](../../database/assets.py) — ligne 401 : `def update_symbol_history_status(symbol: str, history_status: str, *, bars_available: bool | None=None) -> int`

## `database/async_engine.py`

Source SHA-256 : `ce6af253feb90d59e35c00b454f17b6ce3c13d5dabeccdca0a90df3d9bf58992`

- [is_async_enabled](../../database/async_engine.py) — ligne 24 : `def is_async_enabled() -> bool`
- [make_async_engine](../../database/async_engine.py) — ligne 29 : `def make_async_engine(dsn: Optional[str]=None) -> Any | None`

## `database/async_loaders.py`

Source SHA-256 : `16ff1d2d9bcbf6246407f56039719a9667d81558d3f89c8fa888c271af4d3e42`

- [_fetch_all](../../database/async_loaders.py) — ligne 24 : `async def _fetch_all(query: str, params: dict) -> Optional[list[dict]]`
- [fetch_market_data_async](../../database/async_loaders.py) — ligne 41 : `async def fetch_market_data_async(symbols: Sequence[str], start_date: Optional[date]=None, end_date: Optional[date]=None, *, table: str='bars_daily') -> Optional[list[dict]]`
- [fetch_scores_async](../../database/async_loaders.py) — ligne 70 : `async def fetch_scores_async(run_id: str, *, table: str='screener_scores') -> Optional[list[dict]]`
- [fetch_open_orders_async](../../database/async_loaders.py) — ligne 75 : `async def fetch_open_orders_async(account_id: str, *, table: str='execution_broker_orders') -> Optional[list[dict]]`

## `database/audit_chain.py`

Source SHA-256 : `a1f0dd1206f95a02078bdb7d1675318211b26822bdc255a55a6072d10af0f8da`

- [get_audit_hmac_key](../../database/audit_chain.py) — ligne 47 : `def get_audit_hmac_key() -> bytes`
- [get_audit_key_version](../../database/audit_chain.py) — ligne 62 : `def get_audit_key_version() -> int`
- [ChainAnomaly](../../database/audit_chain.py) — ligne 78 : `class ChainAnomaly`
- [ChainAnomaly.to_dict](../../database/audit_chain.py) — ligne 89 : `def to_dict(self) -> dict[str, object]`
- [_canonicalize](../../database/audit_chain.py) — ligne 106 : `def _canonicalize(payload: Mapping[str, Any]) -> str`
- [_compute_hmac](../../database/audit_chain.py) — ligne 110 : `def _compute_hmac(key: bytes, prev_hash: str, payload: str) -> str`
- [AuditChainRepository](../../database/audit_chain.py) — ligne 120 : `class AuditChainRepository`
- [AuditChainRepository.__init__](../../database/audit_chain.py) — ligne 123 : `def __init__(self, engine: Engine, *, key: bytes | None=None, key_version: int | None=None) -> None`
- [AuditChainRepository.latest_hash](../../database/audit_chain.py) — ligne 136 : `def latest_hash(self, run_kind: str) -> str`
- [AuditChainRepository.append](../../database/audit_chain.py) — ligne 145 : `def append(self, run_kind: str, run_id: str, payload: Mapping[str, Any]) -> str`
- [AuditChainRepository.verify_chain](../../database/audit_chain.py) — ligne 183 : `def verify_chain(self, run_kind: str | None=None) -> list[ChainAnomaly]`
- [AuditChainRepository._distinct_kinds](../../database/audit_chain.py) — ligne 194 : `def _distinct_kinds(self) -> list[str]`
- [AuditChainRepository._verify_one](../../database/audit_chain.py) — ligne 202 : `def _verify_one(self, run_kind: str) -> list[ChainAnomaly]`

## `database/bar_metadata.py`

Source SHA-256 : `e47bf82b4ab514e0bba73132967664adfd03066d2f402388e8eb5c385367e510`

- [TimeFrame](../../database/bar_metadata.py) — ligne 14 : `class TimeFrame(Enum)`
- [TimeFrame.__init__](../../database/bar_metadata.py) — ligne 21 : `def __init__(self, db_value: str, api_value: str)`
- [validate_data_integrity_timeframe](../../database/bar_metadata.py) — ligne 29 : `def validate_data_integrity_timeframe(time_frame: TimeFrame) -> None`
- [_normalize_bar_timestamp](../../database/bar_metadata.py) — ligne 37 : `def _normalize_bar_timestamp(raw_timestamp: Any) -> Any`
- [symbol_exists_in_stock_bars](../../database/bar_metadata.py) — ligne 47 : `def symbol_exists_in_stock_bars(conn, symbol: str) -> bool`
- [get_active_tradable_symbols](../../database/bar_metadata.py) — ligne 54 : `def get_active_tradable_symbols(conn) -> list[str]`
- [get_last_bar_timestamp](../../database/bar_metadata.py) — ligne 62 : `def get_last_bar_timestamp(conn, symbol: str, time_frame: TimeFrame)`
- [insert_bars](../../database/bar_metadata.py) — ligne 70 : `def insert_bars(conn, symbol: str, bars: list[dict[str, Any]], timeframe: str) -> int`

## `database/cleaning_audits.py`

Source SHA-256 : `76d2cf39e6644d61f241edd3793ba6524bde3a47488efe7dd3d1262ce8d852ac`

- [_record_run](../../database/cleaning_audits.py) — ligne 32 : `def _record_run(table: str, *, run_id: str, started_at: datetime, finished_at: datetime | None, symbols_requested: int, rows_upserted: int, status: AuditStatus, error_message: str | None) -> None`
- [record_quotes_audit_run](../../database/cleaning_audits.py) — ligne 94 : `def record_quotes_audit_run(*, run_id: str, started_at: datetime, finished_at: datetime, symbols_requested: int, rows_upserted: int, status: AuditStatus='success', error_message: str | None=None) -> None`
- [record_earnings_audit_run](../../database/cleaning_audits.py) — ligne 117 : `def record_earnings_audit_run(*, run_id: str, started_at: datetime, finished_at: datetime | None, symbols_requested: int, rows_upserted: int, status: AuditStatus='success', error_message: str | None=None) -> None`

## `database/connection.py`

Source SHA-256 : `152e49002d93527834f6f9e22bff7e6da7fd7eab6699f44b22b02d368b587b98`

- [_read_optional_env](../../database/connection.py) — ligne 42 : `def _read_optional_env(name: str) -> str | None`
- [_resolve_database_location](../../database/connection.py) — ligne 50 : `def _resolve_database_location(db_host: str, db_name: str) -> tuple[str, str]`
- [_read_database_credentials](../../database/connection.py) — ligne 68 : `def _read_database_credentials(db_user_env: str=DEFAULT_DB_USER_ENV, db_password_env: str=DEFAULT_DB_PASSWORD_ENV) -> tuple[str, str]`
- [_read_int_env](../../database/connection.py) — ligne 87 : `def _read_int_env(name: str, default: int, *, minimum: int=0) -> int`
- [_read_ssl_connect_args](../../database/connection.py) — ligne 104 : `def _read_ssl_connect_args() -> dict[str, dict[str, str]]`
- [get_database_url](../../database/connection.py) — ligne 122 : `def get_database_url(db_host: str=DEFAULT_DB_HOST, db_name: str=DEFAULT_DB_NAME, db_user_env: str=DEFAULT_DB_USER_ENV, db_password_env: str=DEFAULT_DB_PASSWORD_ENV) -> str`
- [get_sqlalchemy_engine](../../database/connection.py) — ligne 134 : `def get_sqlalchemy_engine(db_host: str=DEFAULT_DB_HOST, db_name: str=DEFAULT_DB_NAME, db_user_env: str=DEFAULT_DB_USER_ENV, db_password_env: str=DEFAULT_DB_PASSWORD_ENV, *, url: str | None=None) -> Engine`
- [get_session_factory](../../database/connection.py) — ligne 171 : `def get_session_factory() -> sessionmaker`
- [SessionLocal](../../database/connection.py) — ligne 175 : `def SessionLocal() -> Session`

## `database/macro_indicators.py`

Source SHA-256 : `95020bf2cfa818a72126a03e2f0d2cbbafdd095ec1a58a789ecfe76ca5f8ff64`

- [get_macro_indicators_daily_table](../../database/macro_indicators.py) — ligne 18 : `def get_macro_indicators_daily_table() -> Table`
- [_coerce_date](../../database/macro_indicators.py) — ligne 45 : `def _coerce_date(value: Any) -> date | None`
- [_coerce_float](../../database/macro_indicators.py) — ligne 63 : `def _coerce_float(value: Any) -> float | None`
- [_coerce_int](../../database/macro_indicators.py) — ligne 72 : `def _coerce_int(value: Any) -> int | None`
- [_coerce_bool](../../database/macro_indicators.py) — ligne 81 : `def _coerce_bool(value: Any) -> bool | None`
- [_coerce_str](../../database/macro_indicators.py) — ligne 97 : `def _coerce_str(value: Any) -> str | None`
- [_table_exists](../../database/macro_indicators.py) — ligne 103 : `def _table_exists(engine) -> bool`
- [_resolve_engine](../../database/macro_indicators.py) — ligne 112 : `def _resolve_engine(engine=None)`
- [persist_macro_indicator_daily](../../database/macro_indicators.py) — ligne 122 : `def persist_macro_indicator_daily(*, trade_date: Any, vix: Any=None, vix9d: Any=None, vxn: Any=None, vix3m: Any=None, move: Any=None, rvx: Any=None, ten_y: Any=None, mode: Any=None, risk_multiplier: Any=None, effective_max_positions: Any=None, allow_new_entries: Any=None, vix_curve_inverted: Any=None, yield_10y_5d_pct: Any=None, sentiment_score: Any=None, sentiment_level: Any=None, sentiment_source: Any=None, engine=None) -> int`
- [load_macro_indicator_daily_asof](../../database/macro_indicators.py) — ligne 192 : `def load_macro_indicator_daily_asof(*, trade_date: Any, engine=None, strict_before: bool=False) -> dict[str, Any] | None`
- [load_macro_indicator_history_asof](../../database/macro_indicators.py) — ligne 260 : `def load_macro_indicator_history_asof(*, trade_date: Any, column: str, lookback_days: int, engine=None, strict_before: bool=False) -> list[float] | None`
- [persist_market_macro_snapshot_daily](../../database/macro_indicators.py) — ligne 306 : `def persist_market_macro_snapshot_daily(*, trade_date: Any, macro_payload: object, engine=None) -> int`

## `database/repositories/__init__.py`

Source SHA-256 : `95befa18223574b8a64f9a6bc1edfb974fdddb6c8b384edceb790822eff2aad1`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `database/repositories/_base.py`

Source SHA-256 : `3e248bdb9475539bb476de791b7e31be8fab46eb02ebc0b2c971f98d338c5d1a`

- [Repository](../../database/repositories/_base.py) — ligne 15 : `class Repository`
- [Repository.__init__](../../database/repositories/_base.py) — ligne 24 : `def __init__(self, *, engine: Engine | None=None) -> None`
- [Repository.engine](../../database/repositories/_base.py) — ligne 28 : `def engine(self) -> Engine`
- [Repository.transaction](../../database/repositories/_base.py) — ligne 34 : `def transaction(self) -> Iterator[Connection]`
- [Repository.connect](../../database/repositories/_base.py) — ligne 40 : `def connect(self) -> Iterator[Connection]`

## `database/repositories/analyst_snapshots.py`

Source SHA-256 : `3794c0b43ec204632e23639d7452eed2b176863f0068771a6aa7db9e60673cc1`

- [_utcnow](../../database/repositories/analyst_snapshots.py) — ligne 31 : `def _utcnow() -> datetime`
- [_q](../../database/repositories/analyst_snapshots.py) — ligne 92 : `def _q(table: str) -> str`
- [_insert_if_absent](../../database/repositories/analyst_snapshots.py) — ligne 97 : `def _insert_if_absent(conn: Any, table: str, unique_cols: list[str], row: Mapping[str, Any]) -> bool`
- [AnalystSnapshotRepository](../../database/repositories/analyst_snapshots.py) — ligne 125 : `class AnalystSnapshotRepository(Repository)`
- [AnalystSnapshotRepository.insert_estimate_snapshots](../../database/repositories/analyst_snapshots.py) — ligne 130 : `def insert_estimate_snapshots(self, rows: Iterable[Mapping[str, Any]]) -> int`
- [AnalystSnapshotRepository.insert_target_snapshots](../../database/repositories/analyst_snapshots.py) — ligne 141 : `def insert_target_snapshots(self, rows: Iterable[Mapping[str, Any]]) -> int`
- [AnalystSnapshotRepository.insert_recommendation_snapshots](../../database/repositories/analyst_snapshots.py) — ligne 151 : `def insert_recommendation_snapshots(self, rows: Iterable[Mapping[str, Any]]) -> int`
- [AnalystSnapshotRepository.insert_eps_trend_snapshots](../../database/repositories/analyst_snapshots.py) — ligne 161 : `def insert_eps_trend_snapshots(self, rows: Iterable[Mapping[str, Any]]) -> int`
- [AnalystSnapshotRepository.insert_eps_revision_snapshots](../../database/repositories/analyst_snapshots.py) — ligne 171 : `def insert_eps_revision_snapshots(self, rows: Iterable[Mapping[str, Any]]) -> int`
- [AnalystSnapshotRepository.start_collection_run](../../database/repositories/analyst_snapshots.py) — ligne 183 : `def start_collection_run(self, run_id: str, provider: str, requested_symbols: int, started_at: datetime | None=None) -> None`
- [AnalystSnapshotRepository.finish_collection_run](../../database/repositories/analyst_snapshots.py) — ligne 194 : `def finish_collection_run(self, run_id: str, *, stats: Mapping[str, Any], status: str='COMPLETED', finished_at: datetime | None=None) -> None`
- [AnalystSnapshotRepository.get_latest_estimate_before](../../database/repositories/analyst_snapshots.py) — ligne 211 : `def get_latest_estimate_before(self, symbol: str, estimate_type: str, horizon_normalized: str, cutoff: datetime) -> dict[str, Any] | None`
- [AnalystSnapshotRepository.get_latest_target_before](../../database/repositories/analyst_snapshots.py) — ligne 230 : `def get_latest_target_before(self, symbol: str, cutoff: datetime) -> dict[str, Any] | None`
- [AnalystSnapshotRepository.get_latest_recommendation_before](../../database/repositories/analyst_snapshots.py) — ligne 240 : `def get_latest_recommendation_before(self, symbol: str, period_raw: str, cutoff: datetime) -> dict[str, Any] | None`
- [AnalystSnapshotRepository.get_latest_eps_trend_before](../../database/repositories/analyst_snapshots.py) — ligne 254 : `def get_latest_eps_trend_before(self, symbol: str, horizon_normalized: str, cutoff: datetime) -> dict[str, Any] | None`
- [AnalystSnapshotRepository.get_latest_eps_revision_before](../../database/repositories/analyst_snapshots.py) — ligne 268 : `def get_latest_eps_revision_before(self, symbol: str, horizon_normalized: str, cutoff: datetime) -> dict[str, Any] | None`
- [AnalystSnapshotRepository.get_estimate_history](../../database/repositories/analyst_snapshots.py) — ligne 284 : `def get_estimate_history(self, symbol: str, estimate_type: str | None=None, horizon_normalized: str | None=None, limit: int | None=None) -> list[dict[str, Any]]`
- [AnalystSnapshotRepository.get_target_history](../../database/repositories/analyst_snapshots.py) — ligne 310 : `def get_target_history(self, symbol: str, limit: int | None=None) -> list[dict[str, Any]]`
- [AnalystSnapshotRepository.get_recommendation_history](../../database/repositories/analyst_snapshots.py) — ligne 323 : `def get_recommendation_history(self, symbol: str, period_raw: str='0m', limit: int | None=None) -> list[dict[str, Any]]`
- [AnalystSnapshotRepository.get_last_collection_run](../../database/repositories/analyst_snapshots.py) — ligne 341 : `def get_last_collection_run(self) -> dict[str, Any] | None`
- [AnalystSnapshotRepository.get_collection_run](../../database/repositories/analyst_snapshots.py) — ligne 350 : `def get_collection_run(self, run_id: str) -> dict[str, Any] | None`
- [AnalystSnapshotRepository.count_rows](../../database/repositories/analyst_snapshots.py) — ligne 356 : `def count_rows(self) -> dict[str, int]`
- [AnalystSnapshotRepository.get_symbols_with_snapshot_on](../../database/repositories/analyst_snapshots.py) — ligne 367 : `def get_symbols_with_snapshot_on(self, snapshot_date: date) -> set[str]`

## `database/repositories/assets.py`

Source SHA-256 : `bce6a796032112eedc326438be91f13bc83d21fea7123ab62288d3d051f6b475`

- [AssetsRepository](../../database/repositories/assets.py) — ligne 13 : `class AssetsRepository(Repository)`
- [AssetsRepository.list_eligible_symbols](../../database/repositories/assets.py) — ligne 20 : `def list_eligible_symbols(self, *, limit: int | None=None) -> list[str]`
- [AssetsRepository.get_symbols_missing_sector](../../database/repositories/assets.py) — ligne 23 : `def get_symbols_missing_sector(self, *, limit: int | None=None) -> list[str]`
- [AssetsRepository.get_symbols_missing_fundamentals](../../database/repositories/assets.py) — ligne 26 : `def get_symbols_missing_fundamentals(self, *, limit: int | None=None) -> list[str]`
- [AssetsRepository.list_stale_market_cap](../../database/repositories/assets.py) — ligne 29 : `def list_stale_market_cap(self, *, max_age_days: int, limit: int | None=None) -> list[str]`
- [AssetsRepository.count_stale_market_cap](../../database/repositories/assets.py) — ligne 35 : `def count_stale_market_cap(self, *, max_age_days: int) -> tuple[int, int]`
- [AssetsRepository.update_fundamentals](../../database/repositories/assets.py) — ligne 39 : `def update_fundamentals(self, symbol: str, *, provider_sector: str | None=None, sector: str | None=None, market_cap: float | None=None) -> int`
- [AssetsRepository.insert_assets](../../database/repositories/assets.py) — ligne 54 : `def insert_assets(self, assets: Iterable[Mapping[str, object]]) -> int`
- [AssetsRepository.mark_history_status](../../database/repositories/assets.py) — ligne 57 : `def mark_history_status(self, symbol: str, history_status: str, *, bars_available: bool | None=None) -> int`

## `database/repositories/bars.py`

Source SHA-256 : `16bdee9f0541e26bc7291a8a83cb1f47e941983d39575c31d555d2ad121f0f50`

- [BarsRepository](../../database/repositories/bars.py) — ligne 17 : `class BarsRepository(Repository)`
- [BarsRepository.load_bars](../../database/repositories/bars.py) — ligne 25 : `def load_bars(self, symbol: str | None=None, start: date | None=None, end: date | None=None, *, instrument_id: int | None=None, market_code: str='US_EQ') -> pd.DataFrame`
- [BarsRepository.upsert_bars](../../database/repositories/bars.py) — ligne 59 : `def upsert_bars(self, symbol: str, bars: pd.DataFrame, *, data_adjustment: str='split', data_source: str='alpaca_iex') -> int`

## `database/repositories/instruments.py`

Source SHA-256 : `d53ef41d5abe00dd8a9a0f1c7c39c4845acc04528a08e618d82061a4687e910f`

- [InstrumentIdentityError](../../database/repositories/instruments.py) — ligne 39 : `class InstrumentIdentityError(ValueError)`
- [InstrumentAmbiguityError](../../database/repositories/instruments.py) — ligne 43 : `class InstrumentAmbiguityError(LookupError)`
- [_as_date](../../database/repositories/instruments.py) — ligne 47 : `def _as_date(value: date | str, name: str) -> date`
- [_clean](../../database/repositories/instruments.py) — ligne 56 : `def _clean(value: str, name: str) -> str`
- [build_instrument_uid](../../database/repositories/instruments.py) — ligne 63 : `def build_instrument_uid(market_code: MarketCode | str, exchange_mic: str, canonical_identity: str) -> str`
- [assert_market_mic](../../database/repositories/instruments.py) — ligne 80 : `def assert_market_mic(market_code: MarketCode | str, exchange_mic: str) -> None`
- [InstrumentRepository](../../database/repositories/instruments.py) — ligne 87 : `class InstrumentRepository(Repository)`
- [InstrumentRepository.__init__](../../database/repositories/instruments.py) — ligne 90 : `def __init__(self, *, engine=None, registry: MarketRegistry | None=None) -> None`
- [InstrumentRepository.resolve_instrument](../../database/repositories/instruments.py) — ligne 99 : `def resolve_instrument(self, market_code: MarketCode | str, mic: str, local_symbol: str) -> RowMapping[str, Any] | None`
- [InstrumentRepository.resolve_local_symbol](../../database/repositories/instruments.py) — ligne 126 : `def resolve_local_symbol(self, market_code: MarketCode | str, local_symbol: str) -> RowMapping[str, Any] | None`
- [InstrumentRepository.resolve_provider_symbol](../../database/repositories/instruments.py) — ligne 156 : `def resolve_provider_symbol(self, provider: str, provider_symbol: str, as_of: date | str) -> RowMapping[str, Any] | None`
- [InstrumentRepository.list_instruments](../../database/repositories/instruments.py) — ligne 185 : `def list_instruments(self, market_code: MarketCode | str, as_of: date | str, filters: Mapping[str, Any] | None=None) -> list[RowMapping[str, Any]]`
- [InstrumentRepository.load_status_asof](../../database/repositories/instruments.py) — ligne 218 : `def load_status_asof(self, instrument_id: int, as_of: date | str) -> RowMapping[str, Any] | None`
- [InstrumentRepository.create_instrument](../../database/repositories/instruments.py) — ligne 241 : `def create_instrument(self, *, market_code: MarketCode | str, exchange_mic: str, local_symbol: str, canonical_identity: str, currency: str, display_name: str | None=None, instrument_type: str='equity', listing_date: date | str | None=None, delisting_date: date | str | None=None) -> int`
- [InstrumentRepository.add_provider_symbol](../../database/repositories/instruments.py) — ligne 293 : `def add_provider_symbol(self, *, instrument_id: int, provider: str, provider_symbol: str, valid_from: date | str, valid_to: date | str | None=None, provider_exchange: str | None=None, is_primary: bool=True) -> int`
- [InstrumentRepository._one_or_none](../../database/repositories/instruments.py) — ligne 370 : `def _one_or_none(rows: list[RowMapping[str, Any]], identity_name: str) -> RowMapping[str, Any] | None`

## `database/repositories/market_sessions.py`

Source SHA-256 : `4477a629912912275f20132cb488fcd7a35557863906b905a55ed619cf8a7969`

- [_segments_json](../../database/repositories/market_sessions.py) — ligne 15 : `def _segments_json(session: MarketSession) -> str`
- [upsert_market_sessions](../../database/repositories/market_sessions.py) — ligne 30 : `def upsert_market_sessions(engine: Engine, sessions: Iterable[MarketSession], *, observed_at: datetime | None=None, available_at: datetime | None=None) -> int`

## `database/repositories/quotes.py`

Source SHA-256 : `31593c7d12e7b0665c06da4079d2682c758349535f9eac5af3a6b18aff04520f`

- [QuotesRepository](../../database/repositories/quotes.py) — ligne 8 : `class QuotesRepository(Repository)`
- [QuotesRepository.get_table](../../database/repositories/quotes.py) — ligne 11 : `def get_table(self)`

## `database/repositories/run_summaries.py`

Source SHA-256 : `c65bd47f483aac229de91f87a5d209827327462a605262e1ab327ae4d10b7480`

- [RunSummariesRepository](../../database/repositories/run_summaries.py) — ligne 10 : `class RunSummariesRepository(Repository)`
- [RunSummariesRepository.emit](../../database/repositories/run_summaries.py) — ligne 13 : `def emit(self, summary: Mapping[str, object]) -> None`

## `database/repositories/scores.py`

Source SHA-256 : `be80d38f9dc245b01ff744bc04cd7b44eca6b556b2857cdf95d7d73801596be5`

- [ScoresRepository](../../database/repositories/scores.py) — ligne 10 : `class ScoresRepository(Repository)`
- [ScoresRepository.list_symbols](../../database/repositories/scores.py) — ligne 18 : `def list_symbols(self, *, limit: int | None=None) -> list[str]`
- [ScoresRepository.upsert_scores](../../database/repositories/scores.py) — ligne 21 : `def upsert_scores(self, scores: pd.DataFrame) -> int`

## `database/router.py`

Source SHA-256 : `8807b1a0560a0bc845d023f9abeb01741dfe87d59fc8a3acdfea002ce28e64b6`

- [DatabaseRoute](../../database/router.py) — ligne 29 : `class DatabaseRoute`
- [_env_or_default](../../database/router.py) — ligne 40 : `def _env_or_default(name: str | None, default: str) -> str`
- [_credential](../../database/router.py) — ligne 45 : `def _credential(primary: str, fallback: str | None) -> str`
- [load_database_routes](../../database/router.py) — ligne 58 : `def load_database_routes(path: str | Path=DEFAULT_ROUTING_CONFIG) -> dict[str, DatabaseRoute]`
- [resolve_database_route](../../database/router.py) — ligne 87 : `def resolve_database_route(database_alias: str, market_code: str, *, config_path: str | Path=DEFAULT_ROUTING_CONFIG) -> DatabaseRoute`
- [build_database_url](../../database/router.py) — ligne 112 : `def build_database_url(database_alias: str, market_code: str, *, database_override: str | None=None, config_path: str | Path=DEFAULT_ROUTING_CONFIG) -> str`
- [get_market_engine](../../database/router.py) — ligne 131 : `def get_market_engine(market_code: str, *, database_alias: str, url: str | None=None, verify_schema: bool=True, config_path: str | Path=DEFAULT_ROUTING_CONFIG, **engine_options: Any) -> Engine`

## `database/run_business_summaries.py`

Source SHA-256 : `451fcbb87a20b1cc0e4b1ad45fc2eda88ec2e449dd57179b9b085aac3d5861c1`

- [_build_summary_table](../../database/run_business_summaries.py) — ligne 25 : `def _build_summary_table(table_name: str) -> Table`
- [get_run_summaries_table](../../database/run_business_summaries.py) — ligne 47 : `def get_run_summaries_table() -> Table`
- [get_run_business_summaries_table](../../database/run_business_summaries.py) — ligne 51 : `def get_run_business_summaries_table() -> Table`
- [build_summary_run_id](../../database/run_business_summaries.py) — ligne 55 : `def build_summary_run_id(prefix: str) -> str`
- [emit_run_summary](../../database/run_business_summaries.py) — ligne 60 : `def emit_run_summary(summary: Mapping[str, Any]) -> None`
- [_coerce_datetime](../../database/run_business_summaries.py) — ligne 68 : `def _coerce_datetime(value: Any) -> datetime | None`
- [_coerce_date](../../database/run_business_summaries.py) — ligne 86 : `def _coerce_date(value: Any) -> date | None`
- [_table_exists](../../database/run_business_summaries.py) — ligne 104 : `def _table_exists(engine, table_name: str) -> bool`
- [_resolve_summary_tables](../../database/run_business_summaries.py) — ligne 111 : `def _resolve_summary_tables(engine) -> tuple[Table, ...]`
- [_serialize_summary](../../database/run_business_summaries.py) — ligne 122 : `def _serialize_summary(summary: Mapping[str, Any]) -> str`
- [persist_run_business_summary](../../database/run_business_summaries.py) — ligne 126 : `def persist_run_business_summary(*, summary: Mapping[str, Any], step_key: str, run_kind: str='step', status: str | None=None, summary_run_id: str | None=None, source_run_id: str | None=None, entity_run_id: str | None=None, parent_summary_run_id: str | None=None, account_id: str | None=None, trade_date: Any=None, started_at: Any=None, finished_at: Any=None, engine=None) -> int`
- [persist_pipeline_run_record_summary](../../database/run_business_summaries.py) — ligne 181 : `def persist_pipeline_run_record_summary(record: Mapping[str, Any], *, engine=None) -> int`
- [parse_summary_json](../../database/run_business_summaries.py) — ligne 209 : `def parse_summary_json(raw_value: Any) -> dict[str, Any]`

## `database/sanitizer_db_ops.py`

Source SHA-256 : `9e77a2ec6b3af42b7ce0941a2852753c645533f3df4f9b7fe8feef9927b6da04`

- [_active_symbol_clause](../../database/sanitizer_db_ops.py) — ligne 17 : `def _active_symbol_clause(stock_metadata)`
- [_build_stock_bars_daily_records](../../database/sanitizer_db_ops.py) — ligne 21 : `def _build_stock_bars_daily_records(symbol: str, df: pl.DataFrame, data_adjustment: str='split') -> list[dict]`
- [_normalize_mysql_scalar](../../database/sanitizer_db_ops.py) — ligne 53 : `def _normalize_mysql_scalar(value)`
- [_normalize_mysql_records](../../database/sanitizer_db_ops.py) — ligne 59 : `def _normalize_mysql_records(records: list[dict]) -> tuple[list[dict], dict[str, int]]`
- [_build_mysql_update_cols](../../database/sanitizer_db_ops.py) — ligne 75 : `def _build_mysql_update_cols(table, insert_stmt, record_keys: set[str], key_columns: set[str]) -> dict`
- [_coerce_start_timestamp](../../database/sanitizer_db_ops.py) — ligne 86 : `def _coerce_start_timestamp(start: Optional[date | datetime]) -> Optional[datetime]`
- [get_stock_bars](../../database/sanitizer_db_ops.py) — ligne 94 : `def get_stock_bars(conn: Connection, stock_bars, symbol: str, timeframe: str, start: Optional[date | datetime]=None) -> list[dict]`
- [get_last_sync_date](../../database/sanitizer_db_ops.py) — ligne 146 : `def get_last_sync_date(conn: Connection, cleaning_audit_latest, symbol: str) -> Optional[date]`
- [get_failed_audits](../../database/sanitizer_db_ops.py) — ligne 155 : `def get_failed_audits(conn: Connection, cleaning_audit_latest, limit: Optional[int]=20) -> list[dict]`
- [get_first_last_actual_dates](../../database/sanitizer_db_ops.py) — ligne 173 : `def get_first_last_actual_dates(conn: Connection, stock_bars_daily, symbol: str) -> tuple[Optional[date], Optional[date]]`
- [get_last_actual_daily_date](../../database/sanitizer_db_ops.py) — ligne 179 : `def get_last_actual_daily_date(conn: Connection, stock_bars_daily, symbol: str) -> Optional[date]`
- [get_prev_close_before](../../database/sanitizer_db_ops.py) — ligne 184 : `def get_prev_close_before(conn: Connection, stock_bars_daily, symbol: str, d: date) -> Optional[float]`
- [upsert_stock_bars_daily](../../database/sanitizer_db_ops.py) — ligne 194 : `def upsert_stock_bars_daily(conn: Connection, stock_bars_daily, symbol: str, df: pl.DataFrame, data_adjustment: str='split') -> int`
- [upsert_audit](../../database/sanitizer_db_ops.py) — ligne 229 : `def upsert_audit(conn: Connection, cleaning_audit_latest, cleaning_audit_runs, symbol: str, last_sync: Optional[date], missing_days: Optional[int], anomaly_count: Optional[int], status: str, error_message: Optional[str]=None) -> None`
- [sync_audit_to_stock_scores](../../database/sanitizer_db_ops.py) — ligne 274 : `def sync_audit_to_stock_scores(conn: Connection, stock_scores, symbol: str, missing_days: Optional[int], anomaly_count: Optional[int], sanitizer_status: str) -> int`
- [get_symbols](../../database/sanitizer_db_ops.py) — ligne 300 : `def get_symbols(conn: Connection, stock_metadata) -> list[str]`

## `database/selector_reference.py`

Source SHA-256 : `21b3b7400245e987aea1e4f93159db9e7b7cfb2073cb134375c6f137423b88c6`

- [normalize_symbol_source](../../database/selector_reference.py) — ligne 15 : `def normalize_symbol_source(symbol_source: str | None) -> str`
- [normalize_start_symbol](../../database/selector_reference.py) — ligne 32 : `def normalize_start_symbol(start_symbol: str | None) -> str | None`
- [filter_symbols_from_start](../../database/selector_reference.py) — ligne 37 : `def filter_symbols_from_start(symbols: Iterable[str], *, start_symbol: str | None=None) -> list[str]`
- [get_stock_quote_snapshots_table](../../database/selector_reference.py) — ligne 50 : `def get_stock_quote_snapshots_table() -> Table`
- [get_stock_earnings_calendar_table](../../database/selector_reference.py) — ligne 56 : `def get_stock_earnings_calendar_table() -> Table`
- [list_active_tradable_symbols](../../database/selector_reference.py) — ligne 73 : `def list_active_tradable_symbols(limit: int | None=None, *, start_symbol: str | None=None) -> list[str]`
- [list_symbols_for_source](../../database/selector_reference.py) — ligne 88 : `def list_symbols_for_source(symbol_source: str | None=None, *, limit: int | None=None, start_symbol: str | None=None) -> list[str]`
- [upsert_quote_snapshots](../../database/selector_reference.py) — ligne 110 : `def upsert_quote_snapshots(records: Iterable[dict[str, Any]]) -> int`
- [_coerce_sql_date](../../database/selector_reference.py) — ligne 155 : `def _coerce_sql_date(value: object) -> date | None`
- [_collapse_contiguous_dates](../../database/selector_reference.py) — ligne 168 : `def _collapse_contiguous_dates(dates: Iterable[date], *, expected_order: Iterable[date] | None=None) -> list[tuple[date, date]]`
- [get_quote_snapshot_resume_state](../../database/selector_reference.py) — ligne 197 : `def get_quote_snapshot_resume_state(symbol: str, *, from_date: date, to_date: date, expected_dates: Iterable[date] | None=None) -> dict[str, object]`
- [upsert_earnings_calendar](../../database/selector_reference.py) — ligne 261 : `def upsert_earnings_calendar(records: Iterable[dict[str, Any]]) -> int`

## `database/sql/all_tables.py`

Source SHA-256 : `0ee8e889355578fd18ca9d85b38957b3ced8826652439481e41de719d9dc9705`

- [_get_env](../../database/sql/all_tables.py) — ligne 18 : `def _get_env(*names: str, default: str) -> str`
- [CreateJob](../../database/sql/all_tables.py) — ligne 52 : `class CreateJob(TypedDict)`
- [TableDefinition](../../database/sql/all_tables.py) — ligne 60 : `class TableDefinition`
- [get_all_sql_files](../../database/sql/all_tables.py) — ligne 68 : `def get_all_sql_files() -> list[str]`
- [_strip_sql_comments](../../database/sql/all_tables.py) — ligne 83 : `def _strip_sql_comments(sql_content: str) -> str`
- [extract_create_table_statements](../../database/sql/all_tables.py) — ligne 88 : `def extract_create_table_statements(sql_content: str) -> list[str]`
- [_normalize_table_name](../../database/sql/all_tables.py) — ligne 94 : `def _normalize_table_name(table_name: str) -> str`
- [_extract_created_table_name](../../database/sql/all_tables.py) — ligne 98 : `def _extract_created_table_name(statement: str) -> str`
- [extract_table_name](../../database/sql/all_tables.py) — ligne 105 : `def extract_table_name(statement: str) -> str`
- [_extract_referenced_table_names](../../database/sql/all_tables.py) — ligne 110 : `def _extract_referenced_table_names(statement: str) -> list[str]`
- [_is_missing_fk_dependency_error](../../database/sql/all_tables.py) — ligne 117 : `def _is_missing_fk_dependency_error(exc: Exception) -> bool`
- [_read_sql_file](../../database/sql/all_tables.py) — ligne 125 : `def _read_sql_file(path: Path) -> str`
- [_definition_priority](../../database/sql/all_tables.py) — ligne 129 : `def _definition_priority(definition: TableDefinition) -> tuple[int, int, int, str]`
- [load_table_definitions](../../database/sql/all_tables.py) — ligne 140 : `def load_table_definitions(sql_dir: str | Path=SQL_DIR) -> list[TableDefinition]`
- [find_missing_dependencies](../../database/sql/all_tables.py) — ligne 162 : `def find_missing_dependencies(definitions: list[TableDefinition]) -> dict[str, tuple[str, ...]]`
- [order_table_definitions](../../database/sql/all_tables.py) — ligne 172 : `def order_table_definitions(definitions: list[TableDefinition]) -> list[TableDefinition]`
- [_load_create_jobs](../../database/sql/all_tables.py) — ligne 197 : `def _load_create_jobs() -> list[CreateJob]`
- [_format_job_label](../../database/sql/all_tables.py) — ligne 209 : `def _format_job_label(job: CreateJob) -> str`
- [_execute_create_jobs](../../database/sql/all_tables.py) — ligne 215 : `def _execute_create_jobs(cursor, jobs: list[CreateJob]) -> None`
- [main](../../database/sql/all_tables.py) — ligne 255 : `def main() -> None`

## `database/stock_scores.py`

Source SHA-256 : `5399079bc476d83ef8770294b5374263cef7e9807e5d49b085a63665efb23a45`

- [get_stock_scores_table](../../database/stock_scores.py) — ligne 36 : `def get_stock_scores_table(*, engine=None) -> Table`
- [list_scored_symbols](../../database/stock_scores.py) — ligne 50 : `def list_scored_symbols(*, engine=None, stock_scores: Table | None=None, limit: int | None=None) -> list[str]`
- [load_score_context](../../database/stock_scores.py) — ligne 73 : `def load_score_context(*, engine=None, stock_scores: Table | None=None, limit: int | None=None) -> pd.DataFrame`
