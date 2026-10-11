# Inventaire API — common

Extraction AST du 2026-10-10 ; aucune importation ni exécution métier.

Classes, fonctions de module et méthodes déclarées ; fonctions imbriquées exclues.
Les symboles `_...` sont internes. Signature présente ≠ API publique stable.

## `common/capital_presets.py`

Source SHA-256 : `f57279d16cb2e6e558d55d68cada31a3317e9c7d988cb53dbf3b7f98ea4daae5`

- [CapitalPreset](../../common/capital_presets.py) — ligne 45 : `class CapitalPreset`
- [CapitalPreset.matches_equity](../../common/capital_presets.py) — ligne 54 : `def matches_equity(self, equity: float | None) -> bool`
- [CapitalPreset.to_session_state_values](../../common/capital_presets.py) — ligne 63 : `def to_session_state_values(self, *, detected_equity: float | None=None) -> dict[str, Any]`
- [_normalize_option_value](../../common/capital_presets.py) — ligne 83 : `def _normalize_option_value(option_key: str, raw_value: Any) -> Any`
- [_coerce_float](../../common/capital_presets.py) — ligne 94 : `def _coerce_float(value: object, *, field_name: str) -> float`
- [_canonicalize_strict_profile_key](../../common/capital_presets.py) — ligne 101 : `def _canonicalize_strict_profile_key(selector_key: str) -> str`
- [_normalize_scalar_for_comparison](../../common/capital_presets.py) — ligne 108 : `def _normalize_scalar_for_comparison(value: Any) -> Any`
- [_extract_selector_rs_value](../../common/capital_presets.py) — ligne 116 : `def _extract_selector_rs_value(values: dict[str, Any]) -> Any`
- [collect_strict_profile_deviations](../../common/capital_presets.py) — ligne 128 : `def collect_strict_profile_deviations(preset: CapitalPreset) -> dict[str, dict[str, Any]]`
- [_normalize_strict_profile_justifications](../../common/capital_presets.py) — ligne 148 : `def _normalize_strict_profile_justifications(raw_value: Any, *, preset_key: str) -> dict[str, str]`
- [_validate_capital_preset_strict_profile_alignment](../../common/capital_presets.py) — ligne 176 : `def _validate_capital_preset_strict_profile_alignment(preset: CapitalPreset) -> None`
- [_load_capital_presets_uncached](../../common/capital_presets.py) — ligne 198 : `def _load_capital_presets_uncached(config_path: Path) -> tuple[CapitalPreset, ...]`
- [_load_default_capital_presets](../../common/capital_presets.py) — ligne 253 : `def _load_default_capital_presets() -> tuple[CapitalPreset, ...]`
- [load_capital_presets](../../common/capital_presets.py) — ligne 257 : `def load_capital_presets(config_path: str | Path | None=None) -> tuple[CapitalPreset, ...]`
- [get_capital_preset_by_key](../../common/capital_presets.py) — ligne 263 : `def get_capital_preset_by_key(key: str, *, config_path: str | Path | None=None) -> CapitalPreset | None`
- [resolve_capital_preset_for_equity](../../common/capital_presets.py) — ligne 273 : `def resolve_capital_preset_for_equity(equity: float | None, *, config_path: str | Path | None=None) -> CapitalPreset | None`
- [require_capital_preset](../../common/capital_presets.py) — ligne 282 : `def require_capital_preset(key: str, *, config_path: str | Path | None=None) -> CapitalPreset`
- [get_default_capital_preset](../../common/capital_presets.py) — ligne 289 : `def get_default_capital_preset(*, config_path: str | Path | None=None) -> CapitalPreset`
- [resolve_effective_capital_preset](../../common/capital_presets.py) — ligne 299 : `def resolve_effective_capital_preset(*, capital_preset_key: str | None=None, equity: float | None=None, config_path: str | Path | None=None) -> tuple[CapitalPreset, str]`
- [capital_preset_fingerprint](../../common/capital_presets.py) — ligne 316 : `def capital_preset_fingerprint(preset: CapitalPreset) -> str`
- [build_screener_config_kwargs_from_preset](../../common/capital_presets.py) — ligne 325 : `def build_screener_config_kwargs_from_preset(preset: CapitalPreset) -> dict[str, Any]`
- [adaptive_min_adv](../../common/capital_presets.py) — ligne 343 : `def adaptive_min_adv(equity: float, max_position_weight: float=0.1, target_pct_of_adv: float=0.01) -> float`
- [resolve_adaptive_liquidity_threshold](../../common/capital_presets.py) — ligne 364 : `def resolve_adaptive_liquidity_threshold(equity: float, static_threshold: float | None=None, max_position_weight: float=0.1, target_pct_of_adv: float=0.01) -> float`
- [build_selector_config_kwargs_from_preset](../../common/capital_presets.py) — ligne 382 : `def build_selector_config_kwargs_from_preset(preset: CapitalPreset) -> dict[str, Any]`
- [build_risk_config_kwargs_from_preset](../../common/capital_presets.py) — ligne 451 : `def build_risk_config_kwargs_from_preset(preset: CapitalPreset) -> dict[str, Any]`
- [apply_backtest_defaults_from_preset](../../common/capital_presets.py) — ligne 482 : `def apply_backtest_defaults_from_preset(values: dict[str, Any], preset: CapitalPreset, *, explicit_flags: set[str]) -> dict[str, Any]`
- [build_capital_preset_executability_summary](../../common/capital_presets.py) — ligne 525 : `def build_capital_preset_executability_summary(preset: CapitalPreset, *, detected_equity: float | None=None) -> dict[str, Any]`

## `common/config_loader.py`

Source SHA-256 : `d5bd780e26a4d6ccc40e0a29ec1d8b62e3aeb930b4c2fede644cab590cc6294b`

- [resolve_config_path](../../common/config_loader.py) — ligne 34 : `def resolve_config_path(path: str | os.PathLike[str] | None=None) -> Path`
- [resolve_batch_config_path](../../common/config_loader.py) — ligne 56 : `def resolve_batch_config_path(path: str | os.PathLike[str] | None=None) -> Path`
- [override_config_path](../../common/config_loader.py) — ligne 74 : `def override_config_path(path: str | os.PathLike[str] | None) -> Iterator[None]`
- [resolve_markets_config_dir](../../common/config_loader.py) — ligne 90 : `def resolve_markets_config_dir(path: str | os.PathLike[str] | None=None) -> Path`
- [load_market_registry](../../common/config_loader.py) — ligne 100 : `def load_market_registry(path: str | os.PathLike[str] | None=None)`
- [resolve_market_context](../../common/config_loader.py) — ligne 109 : `def resolve_market_context(market_code: str | None=None, *, path: str | os.PathLike[str] | None=None, require_enabled: bool=False)`
- [_walk_substitute](../../common/config_loader.py) — ligne 121 : `def _walk_substitute(node: Any, vault: Any) -> Any`
- [_apply_vault_overrides](../../common/config_loader.py) — ligne 143 : `def _apply_vault_overrides(cfg: dict, vault: Any) -> dict`
- [load_config](../../common/config_loader.py) — ligne 148 : `def load_config(path: Optional[str]=None, *, vault: Any=None) -> dict`
- [load_batch_config](../../common/config_loader.py) — ligne 184 : `def load_batch_config(path: Optional[str]=None, *, vault: Any=None) -> dict`

## `common/config_vault.py`

Source SHA-256 : `dfac4f49d8c2378464cfc1104d580c280837dac35a3dfde3e2ad9b588a5e43e4`

- [ConfigVault](../../common/config_vault.py) — ligne 39 : `class ConfigVault(Protocol)`
- [ConfigVault.get](../../common/config_vault.py) — ligne 42 : `def get(self, key: str, *, version: int | None=None) -> str | None`
- [ConfigVault.put](../../common/config_vault.py) — ligne 44 : `def put(self, key: str, value: str) -> int`
- [ConfigVault.list_versions](../../common/config_vault.py) — ligne 46 : `def list_versions(self, key: str) -> list[int]`
- [ConfigVault.rotate](../../common/config_vault.py) — ligne 48 : `def rotate(self, key: str, new_value: str) -> int`
- [EnvFallbackVault](../../common/config_vault.py) — ligne 57 : `class EnvFallbackVault`
- [EnvFallbackVault.__post_init__](../../common/config_vault.py) — ligne 67 : `def __post_init__(self) -> None`
- [EnvFallbackVault._key_dir](../../common/config_vault.py) — ligne 72 : `def _key_dir(self, key: str) -> Path`
- [EnvFallbackVault._version_files](../../common/config_vault.py) — ligne 77 : `def _version_files(self, key: str) -> list[tuple[int, Path]]`
- [EnvFallbackVault.get](../../common/config_vault.py) — ligne 90 : `def get(self, key: str, *, version: int | None=None) -> str | None`
- [EnvFallbackVault.put](../../common/config_vault.py) — ligne 110 : `def put(self, key: str, value: str) -> int`
- [EnvFallbackVault.list_versions](../../common/config_vault.py) — ligne 122 : `def list_versions(self, key: str) -> list[int]`
- [EnvFallbackVault.rotate](../../common/config_vault.py) — ligne 125 : `def rotate(self, key: str, new_value: str) -> int`
- [EnvFallbackVault._purge_expired](../../common/config_vault.py) — ligne 130 : `def _purge_expired(self, key: str) -> None`
- [HashiCorpVault](../../common/config_vault.py) — ligne 146 : `class HashiCorpVault`
- [HashiCorpVault.__post_init__](../../common/config_vault.py) — ligne 158 : `def __post_init__(self) -> None`
- [HashiCorpVault._path](../../common/config_vault.py) — ligne 169 : `def _path(self, key: str) -> str`
- [HashiCorpVault.get](../../common/config_vault.py) — ligne 172 : `def get(self, key: str, *, version: int | None=None) -> str | None`
- [HashiCorpVault.put](../../common/config_vault.py) — ligne 183 : `def put(self, key: str, value: str) -> int`
- [HashiCorpVault.list_versions](../../common/config_vault.py) — ligne 191 : `def list_versions(self, key: str) -> list[int]`
- [HashiCorpVault.rotate](../../common/config_vault.py) — ligne 202 : `def rotate(self, key: str, new_value: str) -> int`
- [build_vault_from_env](../../common/config_vault.py) — ligne 211 : `def build_vault_from_env() -> ConfigVault`
- [get_live_secret_policy](../../common/config_vault.py) — ligne 220 : `def get_live_secret_policy() -> str`
- [is_live_secret_policy_satisfied](../../common/config_vault.py) — ligne 241 : `def is_live_secret_policy_satisfied() -> tuple[bool, dict[str, str]]`
- [_safe](../../common/config_vault.py) — ligne 274 : `def _safe(key: str) -> str`

## `common/daily_quality_report.py`

Source SHA-256 : `fe537357fc820eaab4972fbf747694bdf97b602309612eccffe2266f6b5fdcc5`

- [UniverseAnomalyReport](../../common/daily_quality_report.py) — ligne 51 : `class UniverseAnomalyReport`
- [UniverseAnomalyReport.to_dict](../../common/daily_quality_report.py) — ligne 65 : `def to_dict(self) -> dict[str, Any]`
- [detect_universe_anomalies](../../common/daily_quality_report.py) — ligne 81 : `def detect_universe_anomalies(current_symbols: list[str], previous_symbols: list[str] | None, current_date: str, previous_date: str | None=None, *, max_count_change_pct: float=0.2, max_added_without_removed: int=3, max_removed_without_added: int=3) -> UniverseAnomalyReport`
- [CombinedDailyReport](../../common/daily_quality_report.py) — ligne 178 : `class CombinedDailyReport`
- [CombinedDailyReport.to_dict](../../common/daily_quality_report.py) — ligne 185 : `def to_dict(self) -> dict[str, Any]`
- [_load_previous_symbols](../../common/daily_quality_report.py) — ligne 198 : `def _load_previous_symbols(artifact_dir: Path, previous_date: str) -> list[str] | None`
- [_persist_report](../../common/daily_quality_report.py) — ligne 221 : `def _persist_report(report: CombinedDailyReport, artifact_dir: Path, symbols: list[str]) -> Path`
- [build_and_persist_daily_report](../../common/daily_quality_report.py) — ligne 245 : `def build_and_persist_daily_report(trade_date: date, symbols: list[str], availability_map: dict[str, DataAvailabilityInfo], *, artifact_dir: Path | str | None=None, previous_symbols: list[str] | None=None, previous_date: str | None=None, max_age_hours: float=24.0, decision_cutoff: datetime | None=None) -> CombinedDailyReport`

## `common/data_availability.py`

Source SHA-256 : `5fb60bd6cab702916ee2899792404958c3eacc1c19c50be69c2a4f6d33afae03`

- [QualityState](../../common/data_availability.py) — ligne 44 : `class QualityState(str, Enum)`
- [DataAvailabilityInfo](../../common/data_availability.py) — ligne 65 : `class DataAvailabilityInfo`
- [DataAvailabilityInfo.__post_init__](../../common/data_availability.py) — ligne 101 : `def __post_init__(self) -> None`
- [FutureDataError](../../common/data_availability.py) — ligne 119 : `class FutureDataError(RuntimeError)`
- [FutureDataError.__init__](../../common/data_availability.py) — ligne 122 : `def __init__(self, availability: DataAvailabilityInfo, cutoff: datetime) -> None`
- [StaleDataError](../../common/data_availability.py) — ligne 131 : `class StaleDataError(RuntimeError)`
- [StaleDataError.__init__](../../common/data_availability.py) — ligne 134 : `def __init__(self, availability: DataAvailabilityInfo, max_age_hours: float) -> None`
- [validate_availability](../../common/data_availability.py) — ligne 143 : `def validate_availability(availability: DataAvailabilityInfo, decision_cutoff: datetime, *, max_age_hours: float | None=None) -> None`
- [validate_availability_or_degraded](../../common/data_availability.py) — ligne 177 : `def validate_availability_or_degraded(availability: DataAvailabilityInfo, decision_cutoff: datetime, *, max_age_hours: float | None=None, critical: bool=True) -> QualityState`
- [DailyQualityReport](../../common/data_availability.py) — ligne 222 : `class DailyQualityReport`
- [DailyQualityReport.to_dict](../../common/data_availability.py) — ligne 235 : `def to_dict(self) -> dict[str, Any]`
- [build_daily_quality_report](../../common/data_availability.py) — ligne 249 : `def build_daily_quality_report(symbols: list[str], availability_map: dict[str, DataAvailabilityInfo], decision_cutoff: datetime, *, max_age_hours: float=24.0) -> DailyQualityReport`
- [enrich_dataframe_with_pit](../../common/data_availability.py) — ligne 332 : `def enrich_dataframe_with_pit(df: 'pd.DataFrame', *, source: str, event_time_col: str | None=None, available_at_col: str | None=None, default_available_at: datetime | None=None, source_revision: str | None=None, ingested_at: datetime | None=None, tz_name: str='America/New_York', quality: QualityState=QualityState.PRESENT, date_col: str='date', available_at_hour_utc: int=21) -> 'pd.DataFrame'`
- [build_availability_from_row](../../common/data_availability.py) — ligne 423 : `def build_availability_from_row(row: 'pd.Series', *, fallback_source: str='unknown') -> DataAvailabilityInfo`
- [make_availability_from_bar_date](../../common/data_availability.py) — ligne 494 : `def make_availability_from_bar_date(bar_date: str | Any, source: str='eodhd', *, market_close_hour_utc: int=21) -> DataAvailabilityInfo`
- [make_market_availability_from_bar_date](../../common/data_availability.py) — ligne 530 : `def make_market_availability_from_bar_date(bar_date: str | Any, *, context: MarketContext, source: str, dataset: str='daily_bars', engine: Any=None, source_available_at: datetime | None=None) -> DataAvailabilityInfo`

## `common/entry_data_gate.py`

Source SHA-256 : `28b3f778f1bf83503157da7ef4bccecab51f7e0a1ffaa2ddc291413e8df833a6`

- [SourceGateResult](../../common/entry_data_gate.py) — ligne 76 : `class SourceGateResult`
- [EntryDataGateResult](../../common/entry_data_gate.py) — ligne 89 : `class EntryDataGateResult`
- [EntryDataGateResult.to_dict](../../common/entry_data_gate.py) — ligne 99 : `def to_dict(self) -> dict`
- [EntryDataGate](../../common/entry_data_gate.py) — ligne 120 : `class EntryDataGate`
- [EntryDataGate.__init__](../../common/entry_data_gate.py) — ligne 138 : `def __init__(self, critical_sources: tuple[str, ...]=CANONICAL_CRITICAL_SOURCES, required_sources: tuple[str, ...]=CANONICAL_REQUIRED_SOURCES, optional_sources: tuple[str, ...]=CANONICAL_OPTIONAL_SOURCES, max_age_hours: float=26.0) -> None`
- [EntryDataGate._criticality](../../common/entry_data_gate.py) — ligne 163 : `def _criticality(self, source: str) -> str`
- [EntryDataGate.check](../../common/entry_data_gate.py) — ligne 170 : `def check(self, symbol: str, availability_map: dict[str, DataAvailabilityInfo], decision_cutoff: datetime) -> EntryDataGateResult`
- [check_entry_data_readiness](../../common/entry_data_gate.py) — ligne 299 : `def check_entry_data_readiness(symbol: str, availability_map: dict[str, DataAvailabilityInfo], decision_cutoff: datetime, *, critical_sources: tuple[str, ...]=CANONICAL_CRITICAL_SOURCES, max_age_hours: float=26.0) -> EntryDataGateResult`
- [EntryDataBlocked](../../common/entry_data_gate.py) — ligne 340 : `class EntryDataBlocked(RuntimeError)`
- [EntryDataBlocked.__init__](../../common/entry_data_gate.py) — ligne 343 : `def __init__(self, result: EntryDataGateResult) -> None`

## `common/instrument_policy.py`

Source SHA-256 : `df0ed1b91d33b05b3bd05e81895948fac4d001c9ea6c4a0742e40beea9032a7c`

- [excluded_collective_instrument_reason](../../common/instrument_policy.py) — ligne 58 : `def excluded_collective_instrument_reason(company_name: object) -> str | None`

## `common/logging_setup.py`

Source SHA-256 : `0a5679e9b027a34945c2db87b9a6119ff6a622a097abea872796dab1c03ad90b`

- [_is_windows_sharing_violation](../../common/logging_setup.py) — ligne 31 : `def _is_windows_sharing_violation(exc: BaseException) -> bool`
- [_WindowsSafeRolloverMixin](../../common/logging_setup.py) — ligne 35 : `class _WindowsSafeRolloverMixin`
- [_WindowsSafeRolloverMixin._recover_after_rollover_failure](../../common/logging_setup.py) — ligne 44 : `def _recover_after_rollover_failure(self) -> None`
- [SafeRotatingFileHandler](../../common/logging_setup.py) — ligne 56 : `class SafeRotatingFileHandler(_WindowsSafeRolloverMixin, RotatingFileHandler)`
- [SafeRotatingFileHandler.doRollover](../../common/logging_setup.py) — ligne 59 : `def doRollover(self) -> None`
- [SafeTimedRotatingFileHandler](../../common/logging_setup.py) — ligne 68 : `class SafeTimedRotatingFileHandler(_WindowsSafeRolloverMixin, TimedRotatingFileHandler)`
- [SafeTimedRotatingFileHandler.doRollover](../../common/logging_setup.py) — ligne 71 : `def doRollover(self) -> None`
- [_gzip_rotator](../../common/logging_setup.py) — ligne 84 : `def _gzip_rotator(source: str, dest: str) -> None`
- [_gzip_namer](../../common/logging_setup.py) — ligne 92 : `def _gzip_namer(name: str) -> str`
- [_resolve_log_path](../../common/logging_setup.py) — ligne 97 : `def _resolve_log_path(log_path: str) -> Path`
- [_configure_utf8_stdio](../../common/logging_setup.py) — ligne 105 : `def _configure_utf8_stdio() -> None`
- [_reset_root_logging_handlers](../../common/logging_setup.py) — ligne 119 : `def _reset_root_logging_handlers(logger: logging.Logger) -> None`
- [configure_root_logging](../../common/logging_setup.py) — ligne 128 : `def configure_root_logging(*, level: int=logging.INFO, log_path: str | None=None, fmt: str=DEFAULT_LOG_FORMAT, datefmt: str | None=None, max_bytes: int=5000000, backup_count: int=3, use_timed_rotation: bool=False, timed_rotation_when: str='midnight', timed_rotation_backup_count: int=14) -> logging.Logger`
- [setup_logging_with_file_handler](../../common/logging_setup.py) — ligne 193 : `def setup_logging_with_file_handler(log_path: str='alpha_trade.log', max_bytes: int=5000000, backup_count: int=3) -> logging.Logger`
- [JSONFormatter](../../common/logging_setup.py) — ligne 211 : `class JSONFormatter(logging.Formatter)`
- [JSONFormatter.__init__](../../common/logging_setup.py) — ligne 223 : `def __init__(self, *, include_extra: bool=True) -> None`
- [JSONFormatter.format](../../common/logging_setup.py) — ligne 227 : `def format(self, record: logging.LogRecord) -> str`
- [_resolve_log_formatter](../../common/logging_setup.py) — ligne 251 : `def _resolve_log_formatter(fmt: str, datefmt: str | None=None) -> logging.Formatter`

## `common/market_calendar.py`

Source SHA-256 : `a0b5b78f43837579d0188da750a08622cb0cf644e372819c4ce0067494d63dd9`

- [MarketCalendarError](../../common/market_calendar.py) — ligne 35 : `class MarketCalendarError(RuntimeError)`
- [MarketCalendarUnavailableError](../../common/market_calendar.py) — ligne 39 : `class MarketCalendarUnavailableError(MarketCalendarError)`
- [DatasetCutoffError](../../common/market_calendar.py) — ligne 43 : `class DatasetCutoffError(MarketCalendarError)`
- [SessionSegment](../../common/market_calendar.py) — ligne 48 : `class SessionSegment`
- [SessionSegment.__post_init__](../../common/market_calendar.py) — ligne 53 : `def __post_init__(self) -> None`
- [MarketSession](../../common/market_calendar.py) — ligne 61 : `class MarketSession`
- [MarketSession.is_open](../../common/market_calendar.py) — ligne 71 : `def is_open(self) -> bool`
- [DatasetCutoffPolicy](../../common/market_calendar.py) — ligne 76 : `class DatasetCutoffPolicy`
- [_aware_utc](../../common/market_calendar.py) — ligne 82 : `def _aware_utc(value: Any) -> datetime`
- [_local_segment](../../common/market_calendar.py) — ligne 92 : `def _local_segment(day: date, tz_name: str, name: str, start: dt_time, end: dt_time) -> SessionSegment`
- [_segments_for_context](../../common/market_calendar.py) — ligne 101 : `def _segments_for_context(context: MarketContext, day: date, market_open: datetime, market_close: datetime) -> tuple[SessionSegment, ...]`
- [_get_library_calendar](../../common/market_calendar.py) — ligne 113 : `def _get_library_calendar(calendar_id: str)`
- [_get_nyse_calendar](../../common/market_calendar.py) — ligne 124 : `def _get_nyse_calendar()`
- [MarketCalendar](../../common/market_calendar.py) — ligne 129 : `class MarketCalendar`
- [MarketCalendar.__init__](../../common/market_calendar.py) — ligne 132 : `def __init__(self, context: MarketContext, *, engine: Engine | None=None, allow_us_weekday_fallback: bool=True) -> None`
- [MarketCalendar._database_coverage](../../common/market_calendar.py) — ligne 143 : `def _database_coverage(self) -> tuple[date, date] | None`
- [MarketCalendar._database_sessions](../../common/market_calendar.py) — ligne 168 : `def _database_sessions(self, start: date, end: date) -> list[MarketSession] | None`
- [MarketCalendar._library_sessions](../../common/market_calendar.py) — ligne 220 : `def _library_sessions(self, start: date, end: date) -> list[MarketSession]`
- [MarketCalendar.sessions](../../common/market_calendar.py) — ligne 280 : `def sessions(self, start: date, end: date) -> list[MarketSession]`
- [MarketCalendar.session_dates](../../common/market_calendar.py) — ligne 286 : `def session_dates(self, start: date, end: date) -> list[date]`
- [MarketCalendar.session](../../common/market_calendar.py) — ligne 289 : `def session(self, day: date) -> MarketSession`
- [MarketCalendar.session_bounds](../../common/market_calendar.py) — ligne 295 : `def session_bounds(self, day: date) -> tuple[datetime, datetime]`
- [MarketCalendar._seek](../../common/market_calendar.py) — ligne 299 : `def _seek(self, from_date: date, nth: int, direction: int) -> date`
- [MarketCalendar.next_session](../../common/market_calendar.py) — ligne 314 : `def next_session(self, from_date: date, nth: int=1) -> date`
- [MarketCalendar.previous_session](../../common/market_calendar.py) — ligne 317 : `def previous_session(self, from_date: date, nth: int=1) -> date`
- [MarketCalendar.advance_sessions](../../common/market_calendar.py) — ligne 320 : `def advance_sessions(self, from_date: date, count: int) -> date`
- [_context](../../common/market_calendar.py) — ligne 329 : `def _context(value: MarketContext | MarketCode | str) -> MarketContext`
- [get_market_calendar](../../common/market_calendar.py) — ligne 333 : `def get_market_calendar(context: MarketContext | MarketCode | str, *, engine: Engine | None=None, allow_us_weekday_fallback: bool=True) -> MarketCalendar`
- [session_dates](../../common/market_calendar.py) — ligne 342 : `def session_dates(context, start: date, end: date, *, engine: Engine | None=None) -> list[date]`
- [session_bounds](../../common/market_calendar.py) — ligne 346 : `def session_bounds(context, day: date, *, engine: Engine | None=None) -> tuple[datetime, datetime]`
- [next_session](../../common/market_calendar.py) — ligne 350 : `def next_session(context, day: date, nth: int=1, *, engine: Engine | None=None) -> date`
- [previous_session](../../common/market_calendar.py) — ligne 354 : `def previous_session(context, day: date, nth: int=1, *, engine: Engine | None=None) -> date`
- [advance_sessions](../../common/market_calendar.py) — ligne 358 : `def advance_sessions(context, day: date, count: int, *, engine: Engine | None=None) -> date`
- [_load_cutoff_policies](../../common/market_calendar.py) — ligne 363 : `def _load_cutoff_policies(path: str=str(_DEFAULT_CUTOFFS_PATH)) -> dict[str, dict[str, DatasetCutoffPolicy]]`
- [dataset_cutoff](../../common/market_calendar.py) — ligne 380 : `def dataset_cutoff(context: MarketContext | MarketCode | str, dataset: str, day: date, *, engine: Engine | None=None, policies_path: str | Path | None=None) -> datetime`
- [is_trading_day](../../common/market_calendar.py) — ligne 403 : `def is_trading_day(d: date) -> bool`
- [nyse_session_dates](../../common/market_calendar.py) — ligne 410 : `def nyse_session_dates(start: date, end: date) -> list[date]`
- [get_nyse_session_bounds](../../common/market_calendar.py) — ligne 431 : `def get_nyse_session_bounds(session_date: date) -> tuple[datetime, datetime]`
- [is_us_market_holiday](../../common/market_calendar.py) — ligne 447 : `def is_us_market_holiday(d: date) -> bool`
- [getLastDateMarche](../../common/market_calendar.py) — ligne 451 : `def getLastDateMarche(ref_date: date | None=None) -> date`
- [next_trading_day](../../common/market_calendar.py) — ligne 459 : `def next_trading_day(from_date: date, *, nth: int=1) -> date`
- [trading_days_between](../../common/market_calendar.py) — ligne 473 : `def trading_days_between(start: date, end: date) -> int`

## `common/market_cap.py`

Source SHA-256 : `c2d9f599fc10603db9c4abe470d19d07662c407be8d705ec3df7015629b75940`

- [MarketCapConfig](../../common/market_cap.py) — ligne 27 : `class MarketCapConfig`
- [_normalize_provider](../../common/market_cap.py) — ligne 34 : `def _normalize_provider(value: Any) -> str`
- [load_market_cap_config](../../common/market_cap.py) — ligne 57 : `def load_market_cap_config(*, provider_override: str | None=None, max_age_days_override: int | None=None, policy_override: str | None=None, config: dict[str, Any] | None=None) -> MarketCapConfig`
- [compute_sec_market_cap](../../common/market_cap.py) — ligne 97 : `def compute_sec_market_cap(close_price: Any, shares_outstanding: Any) -> float | None`

## `common/market_context.py`

Source SHA-256 : `8ed8a38419dd9825d9b7deac84c2d8bf70d660b29e55a5c49119fa733e5ff44c`

- [MarketCompatibilityError](../../common/market_context.py) — ligne 27 : `class MarketCompatibilityError(ValueError)`
- [MarketCode](../../common/market_context.py) — ligne 31 : `class MarketCode(StrEnum)`
- [_required_text](../../common/market_context.py) — ligne 80 : `def _required_text(payload: Mapping[str, Any], name: str) -> str`
- [_required_bool](../../common/market_context.py) — ligne 87 : `def _required_bool(payload: Mapping[str, Any], name: str) -> bool`
- [_string_set](../../common/market_context.py) — ligne 94 : `def _string_set(values: Any, name: str) -> frozenset[str]`
- [MarketContext](../../common/market_context.py) — ligne 106 : `class MarketContext`
- [MarketContext.__post_init__](../../common/market_context.py) — ligne 123 : `def __post_init__(self) -> None`
- [MarketContext.from_mapping](../../common/market_context.py) — ligne 170 : `def from_mapping(cls, payload: Mapping[str, Any]) -> MarketContext`
- [MarketContext._manifest_payload](../../common/market_context.py) — ligne 196 : `def _manifest_payload(self) -> dict[str, Any]`
- [MarketContext.to_manifest](../../common/market_context.py) — ligne 215 : `def to_manifest(self) -> dict[str, Any]`
- [MarketContext.fingerprint](../../common/market_context.py) — ligne 219 : `def fingerprint(self) -> str`
- [MarketContext.assert_database_alias](../../common/market_context.py) — ligne 228 : `def assert_database_alias(self, database_alias: str) -> None`
- [MarketRegistry](../../common/market_context.py) — ligne 236 : `class MarketRegistry`
- [MarketRegistry.__post_init__](../../common/market_context.py) — ligne 239 : `def __post_init__(self) -> None`
- [MarketRegistry.from_contexts](../../common/market_context.py) — ligne 253 : `def from_contexts(cls, contexts: Iterable[MarketContext]) -> MarketRegistry`
- [MarketRegistry.from_directory](../../common/market_context.py) — ligne 262 : `def from_directory(cls, directory: str | Path) -> MarketRegistry`
- [MarketRegistry.market_codes](../../common/market_context.py) — ligne 275 : `def market_codes(self) -> tuple[MarketCode, ...]`
- [MarketRegistry.resolve](../../common/market_context.py) — ligne 278 : `def resolve(self, market_code: MarketCode | str | None=None, *, require_enabled: bool=False) -> MarketContext`
- [MarketRegistry.assert_compatible](../../common/market_context.py) — ligne 308 : `def assert_compatible(self, market_code: MarketCode | str, database_alias: str) -> MarketContext`

## `common/metrics.py`

Source SHA-256 : `d0a79563bd1cf0226e0ed80e26e086859ff771d8d991e961432c51d81ccd3a80`

- [is_available](../../common/metrics.py) — ligne 44 : `def is_available() -> bool`
- [_Noop](../../common/metrics.py) — ligne 47 : `class _Noop`
- [_Noop.labels](../../common/metrics.py) — ligne 48 : `def labels(self, *_a: Any, **_kw: Any) -> '_Noop'`
- [_Noop.inc](../../common/metrics.py) — ligne 51 : `def inc(self, *_a: Any, **_kw: Any) -> None`
- [_Noop.set](../../common/metrics.py) — ligne 54 : `def set(self, *_a: Any, **_kw: Any) -> None`
- [_Noop.observe](../../common/metrics.py) — ligne 57 : `def observe(self, *_a: Any, **_kw: Any) -> None`
- [Counter](../../common/metrics.py) — ligne 60 : `def Counter(*_a: Any, **_kw: Any) -> _Noop`
- [Gauge](../../common/metrics.py) — ligne 63 : `def Gauge(*_a: Any, **_kw: Any) -> _Noop`
- [Histogram](../../common/metrics.py) — ligne 66 : `def Histogram(*_a: Any, **_kw: Any) -> _Noop`
- [record_pipeline_step](../../common/metrics.py) — ligne 118 : `def record_pipeline_step(step: str) -> Generator[None, None, None]`

## `common/ml_cascade_contract.py`

Source SHA-256 : `06034ff36c913bf9c9d07b2cba9ad9e4dae166f7934cf5b78b12e75f255fbd88`

- [load_serving_directional_bundle_manifest](../../common/ml_cascade_contract.py) — ligne 11 : `def load_serving_directional_bundle_manifest(artifacts_dir: Path | str, batch_id: str | None) -> dict[str, Any] | None`
- [infer_oracle_only_cascade_mode](../../common/ml_cascade_contract.py) — ligne 42 : `def infer_oracle_only_cascade_mode(artifacts_dir: Path | str, batch_id: str | None, *, oracle_rows: int, global_rank_rows: int) -> str | None`

## `common/oracle_atr.py`

Source SHA-256 : `077af41f6067db0205a43e51c978a09f1c0421544a597eb990b920faeaf2eec3`

- [resolve_oracle_atr_enabled](../../common/oracle_atr.py) — ligne 14 : `def resolve_oracle_atr_enabled(value: Any=True) -> bool`
- [atr20_percent_panel](../../common/oracle_atr.py) — ligne 20 : `def atr20_percent_panel(bars: pd.DataFrame) -> pd.DataFrame`
- [load_oracle_atr_by_date](../../common/oracle_atr.py) — ligne 47 : `def load_oracle_atr_by_date(engine: Any, symbols: list[str], dates: list[str]) -> dict[str, dict[str, float]]`
- [filter_oracle_atr_percentiles](../../common/oracle_atr.py) — ligne 73 : `def filter_oracle_atr_percentiles(percentiles: dict[str, float], atr_values: dict[str, float], *, oracle_pool_pct: float=0.2, trade_date: str='') -> tuple[dict[str, float], dict[str, int]]`

## `common/price_convention.py`

Source SHA-256 : `36fd34a0e9f1886c5864c8cb029330545640ed8fe139a86ad13cee317afe3dc4`

- [PriceConvention](../../common/price_convention.py) — ligne 38 : `class PriceConvention(str, Enum)`
- [declare_price_convention](../../common/price_convention.py) — ligne 71 : `def declare_price_convention(df: 'pd.DataFrame', convention: PriceConvention, *, source: str | None=None) -> 'pd.DataFrame'`
- [get_price_convention](../../common/price_convention.py) — ligne 101 : `def get_price_convention(df: 'pd.DataFrame') -> PriceConvention`
- [validate_no_mixed_convention](../../common/price_convention.py) — ligne 122 : `def validate_no_mixed_convention(features_df: 'pd.DataFrame', execution_df: 'pd.DataFrame', *, strict: bool=False) -> list[str]`

## `common/publish_tradable_universe.py`

Source SHA-256 : `997db24e780d1273444305b411857ab642de6308e2a0fbac75a0d8bd1d3bc747`

- [_require_tables](../../common/publish_tradable_universe.py) — ligne 26 : `def _require_tables(engine: Engine) -> None`
- [_load_source_scope](../../common/publish_tradable_universe.py) — ligne 41 : `def _load_source_scope(engine: Engine, snapshot_date: date, preset_key: str) -> tuple[dict[str, object], pd.DataFrame]`
- [_load_objective_context](../../common/publish_tradable_universe.py) — ligne 80 : `def _load_objective_context(engine: Engine, symbols: list[str], snapshot_date: date, blackout_days: int, max_quote_age_days: int=5, market_cap_provider: str='sec_edgar') -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, set[str]]`
- [_select_market_cap_rows](../../common/publish_tradable_universe.py) — ligne 213 : `def _select_market_cap_rows(rows: pd.DataFrame, *, snapshot_date: date, max_age_days: int, provider: str) -> pd.DataFrame`
- [publish_full_tradable_universe](../../common/publish_tradable_universe.py) — ligne 250 : `def publish_full_tradable_universe(engine: Engine, *, snapshot_date: date, capital_preset_key: str=DEFAULT_CAPITAL_PRESET_KEY, max_quote_age_days: int=5, ignore_quotes: bool=False, market_cap_provider: str | None=None, market_cap_max_age_days: int | None=None, market_cap_policy: str | None=None, market_code: str='US_EQ') -> str`
- [main](../../common/publish_tradable_universe.py) — ligne 439 : `def main(argv: list[str] | None=None) -> int`

## `common/quantity_utils.py`

Source SHA-256 : `6ebf816bf07175517816465f0c62e140d0fb087556eccafa3ebb9d8af39e1a30`

- [normalize_share_quantity](../../common/quantity_utils.py) — ligne 11 : `def normalize_share_quantity(value: float | int | str | Decimal | None, *, decimals: int=QUANTITY_DECIMALS) -> float`
- [is_effectively_integer_quantity](../../common/quantity_utils.py) — ligne 32 : `def is_effectively_integer_quantity(value: float | int | str | Decimal | None, *, decimals: int=QUANTITY_DECIMALS) -> bool`
- [format_share_quantity](../../common/quantity_utils.py) — ligne 38 : `def format_share_quantity(value: float | int | str | Decimal | None, *, decimals: int=QUANTITY_DECIMALS) -> str`

## `common/run_market_scope.py`

Source SHA-256 : `4bc4ab43f0e0125d5a5f33b8ceffa9ad8314e04076c6a5098f661eccafccc92e`

- [RunMarketScope](../../common/run_market_scope.py) — ligne 17 : `class RunMarketScope`
- [RunMarketScope.as_manifest](../../common/run_market_scope.py) — ligne 25 : `def as_manifest(self) -> dict[str, str]`
- [resolve_run_market_scope](../../common/run_market_scope.py) — ligne 36 : `def resolve_run_market_scope(market_code: str | None=None, *, require_enabled: bool=False) -> RunMarketScope`
- [compute_scope_universe_fingerprint](../../common/run_market_scope.py) — ligne 52 : `def compute_scope_universe_fingerprint(*, market_code: str, symbol_source: str, universe_date: Any=None, symbols: Iterable[str] | None=None) -> str`
- [read_manifest_market_scope](../../common/run_market_scope.py) — ligne 69 : `def read_manifest_market_scope(payload: dict[str, Any]) -> RunMarketScope`

## `common/sizing.py`

Source SHA-256 : `7dbf26d5aa04ae8efd77119f921a71a698c2af09a26279b4d4660716cd9ad994`

- [SizingConfig](../../common/sizing.py) — ligne 20 : `class SizingConfig`
- [SizingConfig.compute_weights](../../common/sizing.py) — ligne 37 : `def compute_weights(self, candidates: pd.DataFrame, max_positions: int) -> pd.Series`
- [SizingConfig._apply_sector_multipliers](../../common/sizing.py) — ligne 72 : `def _apply_sector_multipliers(self, candidates: pd.DataFrame, weights: pd.Series) -> pd.Series`

## `common/tradable_universe.py`

Source SHA-256 : `d1ac88187d58c79f82a415e0b6780b8365763f85025fd03209e87741f04e77a7`

- [UniverseSnapshotNotFoundError](../../common/tradable_universe.py) — ligne 19 : `class UniverseSnapshotNotFoundError(RuntimeError)`
- [UniverseMember](../../common/tradable_universe.py) — ligne 24 : `class UniverseMember`
- [UniverseMember.__post_init__](../../common/tradable_universe.py) — ligne 40 : `def __post_init__(self) -> None`
- [UniverseResolution](../../common/tradable_universe.py) — ligne 52 : `class UniverseResolution`
- [UniverseResolution.symbols](../../common/tradable_universe.py) — ligne 67 : `def symbols(self) -> list[str]`
- [_utc_now_naive](../../common/tradable_universe.py) — ligne 73 : `def _utc_now_naive() -> datetime`
- [universe_schema_available](../../common/tradable_universe.py) — ligne 77 : `def universe_schema_available(engine: Engine) -> bool`
- [begin_universe_run](../../common/tradable_universe.py) — ligne 88 : `def begin_universe_run(engine: Engine, *, snapshot_date: date, capital_preset_key: str, config_fingerprint: str, rows_expected: int, universe_run_id: str | None=None, data_quality_grade: str='unknown', market_code: str | None=None) -> str`
- [publish_universe_run](../../common/tradable_universe.py) — ligne 151 : `def publish_universe_run(engine: Engine, universe_run_id: str, members: Iterable[UniverseMember]) -> None`
- [fail_universe_run](../../common/tradable_universe.py) — ligne 264 : `def fail_universe_run(engine: Engine, universe_run_id: str, reason: str) -> None`
- [resolve_universe_asof](../../common/tradable_universe.py) — ligne 283 : `def resolve_universe_asof(engine: Engine, trade_date: date, capital_preset_key: str, *, tradable_only: bool=True, market_code: str | None=None) -> UniverseResolution`
- [load_tradable_universe_for_period](../../common/tradable_universe.py) — ligne 357 : `def load_tradable_universe_for_period(engine: Engine, start_date: date, end_date: date, capital_preset_key: str=DEFAULT_CAPITAL_PRESET_KEY, *, tradable_only: bool=True, market_code: str | None=None) -> list[str]`
- [load_tradable_universe_by_date](../../common/tradable_universe.py) — ligne 419 : `def load_tradable_universe_by_date(engine: Engine, dates: Iterable[str | date], capital_preset_key: str=DEFAULT_CAPITAL_PRESET_KEY, *, market_code: str | None=None) -> dict[str, set[str]]`
- [compute_universe_fingerprint](../../common/tradable_universe.py) — ligne 479 : `def compute_universe_fingerprint(universe_run_id: str, symbols: list[str], snapshot_date: str | date | None=None, capital_preset_key: str | None=None) -> str`

## `common/trading_costs.py`

Source SHA-256 : `c8c877dc1762aee0a7c9261c2cc1ac6ea0998941989bd16eb90d80100e3b0642`

- [TradingCostModel](../../common/trading_costs.py) — ligne 26 : `class TradingCostModel`
- [TradingCostModel.per_leg_cost_bps](../../common/trading_costs.py) — ligne 57 : `def per_leg_cost_bps(self) -> float`
- [TradingCostModel.round_trip_cost_bps](../../common/trading_costs.py) — ligne 62 : `def round_trip_cost_bps(self) -> float`
- [TradingCostModel.per_leg_cost_pct](../../common/trading_costs.py) — ligne 67 : `def per_leg_cost_pct(self) -> float`
- [TradingCostModel.round_trip_cost_pct](../../common/trading_costs.py) — ligne 72 : `def round_trip_cost_pct(self) -> float`
- [TradingCostModel.deduct_round_trip](../../common/trading_costs.py) — ligne 78 : `def deduct_round_trip(self, gross_return: float) -> float`
- [TradingCostModel.borrow_cost_for_holding](../../common/trading_costs.py) — ligne 96 : `def borrow_cost_for_holding(self, holding_sessions: int, *, sessions_per_year: int=252) -> float`
- [TradingCostModel.effective_cost_for_trade](../../common/trading_costs.py) — ligne 120 : `def effective_cost_for_trade(self, gross_return: float, side: str, holding_sessions: int=1) -> float`
- [TradingCostModel.to_dict](../../common/trading_costs.py) — ligne 147 : `def to_dict(self) -> dict`
- [TradingCostModel.from_dict](../../common/trading_costs.py) — ligne 159 : `def from_dict(cls, d: dict) -> 'TradingCostModel'`

## `common/universe_files.py`

Source SHA-256 : `f8917d6da6966975d5fcbbe9f8156d243605e1beb6458d3be54749f9b60726eb`

- [_is_bare_name](../../common/universe_files.py) — ligne 21 : `def _is_bare_name(value: str) -> bool`
- [_relative_config_path](../../common/universe_files.py) — ligne 26 : `def _relative_config_path(path: Path, root: Path) -> Path`
- [list_universe_files](../../common/universe_files.py) — ligne 45 : `def list_universe_files(directory: Path=UNIVERSE_DIRECTORY) -> tuple[Path, ...]`
- [universe_file_source](../../common/universe_files.py) — ligne 57 : `def universe_file_source(filename: str) -> str`
- [universe_file_source_from_path](../../common/universe_files.py) — ligne 72 : `def universe_file_source_from_path(path: str | Path, root: str | Path=Path('.')) -> str`
- [resolve_universe_file_path](../../common/universe_files.py) — ligne 84 : `def resolve_universe_file_path(source: str, directory: Path=UNIVERSE_DIRECTORY, root: str | Path=Path('.')) -> Path`
- [validate_symbol_source](../../common/universe_files.py) — ligne 101 : `def validate_symbol_source(value: str, native_sources: Sequence[str]=()) -> str`
- [list_universe_file_sources](../../common/universe_files.py) — ligne 119 : `def list_universe_file_sources(directory: Path=UNIVERSE_DIRECTORY) -> tuple[str, ...]`
- [replace_legacy_ticket_option](../../common/universe_files.py) — ligne 123 : `def replace_legacy_ticket_option(options: tuple[str, ...], directory: Path=UNIVERSE_DIRECTORY) -> tuple[str, ...]`
- [universe_file_source_labels](../../common/universe_files.py) — ligne 132 : `def universe_file_source_labels(directory: Path=UNIVERSE_DIRECTORY) -> dict[str, str]`
- [default_universe_file_source](../../common/universe_files.py) — ligne 139 : `def default_universe_file_source(directory: Path=UNIVERSE_DIRECTORY) -> str`
- [default_universe_file_source_or](../../common/universe_files.py) — ligne 146 : `def default_universe_file_source_or(fallback: str, directory: Path=UNIVERSE_DIRECTORY) -> str`
- [is_universe_file_source](../../common/universe_files.py) — ligne 154 : `def is_universe_file_source(value: str | None) -> bool`
- [normalize_universe_file_source](../../common/universe_files.py) — ligne 158 : `def normalize_universe_file_source(value: str | None, directory: Path=UNIVERSE_DIRECTORY) -> str`
- [universe_file_label](../../common/universe_files.py) — ligne 177 : `def universe_file_label(source: str) -> str`
- [load_universe_file_symbols](../../common/universe_files.py) — ligne 184 : `def load_universe_file_symbols(source: str, directory: Path=UNIVERSE_DIRECTORY, root: str | Path=Path('.')) -> list[str]`

## `common/us_signal_date.py`

Source SHA-256 : `4e7de3884fb0ffcadb758f737ac95e0382cb80d2bb368a46ac54ec378e4c39c4`

- [resolve_us_signal_date](../../common/us_signal_date.py) — ligne 8 : `def resolve_us_signal_date(requested=None, *, now=None, calendar=None) -> date`
- [pin_command_date](../../common/us_signal_date.py) — ligne 37 : `def pin_command_date(command, phase: str, day: str) -> list[str]`

## `common/utils.py`

Source SHA-256 : `4d11396fc96326c4a85888ebaec176eeb59bd27694da7117abbac54dd821116d`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `common/verified_http.py`

Source SHA-256 : `89d5253a7fa18243d228414fe54c2d28d060f679a7b0f84bf00d80b436a7d1c6`

- [verified_context](../../common/verified_http.py) — ligne 7 : `def verified_context()`
- [VerifiedTLSAdapter](../../common/verified_http.py) — ligne 20 : `class VerifiedTLSAdapter(requests.adapters.HTTPAdapter)`
- [VerifiedTLSAdapter.__init__](../../common/verified_http.py) — ligne 21 : `def __init__(self)`
- [VerifiedTLSAdapter.build_connection_pool_key_attributes](../../common/verified_http.py) — ligne 25 : `def build_connection_pool_key_attributes(self, request, verify, cert=None)`
- [verified_session](../../common/verified_http.py) — ligne 34 : `def verified_session()`

## `common/windows_sleep_guard.py`

Source SHA-256 : `44ec449a3f6d7c34b909d686348710b0848920100c8e339ca6b932e8c481b429`

- [SleepGuardError](../../common/windows_sleep_guard.py) — ligne 18 : `class SleepGuardError(RuntimeError)`
- [_is_windows](../../common/windows_sleep_guard.py) — ligne 22 : `def _is_windows() -> bool`
- [_set_thread_execution_state](../../common/windows_sleep_guard.py) — ligne 26 : `def _set_thread_execution_state(flags: int) -> int`
- [prevent_windows_sleep](../../common/windows_sleep_guard.py) — ligne 37 : `def prevent_windows_sleep(*, enabled: bool=True) -> Iterator[bool]`
