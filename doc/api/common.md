# Inventaire API — common

Cet inventaire est dérivé des signatures présentes dans le code. Les symboles préfixés par `_` restent internes. Les numéros de ligne sont indicatifs ; le chemin et le nom du symbole sont les repères stables.

## `common/capital_presets.py`

- ligne 101 — `def _canonicalize_strict_profile_key(selector_key: str) -> str:`
- ligne 108 — `def _normalize_scalar_for_comparison(value: Any) -> Any:`
- ligne 116 — `def _extract_selector_rs_value(values: dict[str, Any]) -> Any:`
- ligne 128 — `def collect_strict_profile_deviations(preset: CapitalPreset) -> dict[str, dict[str, Any]]:`
- ligne 148 — `def _normalize_strict_profile_justifications(raw_value: Any, *, preset_key: str) -> dict[str, str]:`
- ligne 176 — `def _validate_capital_preset_strict_profile_alignment(preset: CapitalPreset) -> None:`
- ligne 198 — `def _load_capital_presets_uncached(config_path: Path) -> tuple[CapitalPreset, ...]:`
- ligne 253 — `def _load_default_capital_presets() -> tuple[CapitalPreset, ...]:`
- ligne 257 — `def load_capital_presets(config_path: str | Path | None = None) -> tuple[CapitalPreset, ...]:`
- ligne 263 — `def get_capital_preset_by_key(key: str, *, config_path: str | Path | None = None) -> CapitalPreset | None:`
- ligne 273 — `def resolve_capital_preset_for_equity(equity: float | None, *, config_path: str | Path | None = None) -> CapitalPreset | None:`
- ligne 282 — `def require_capital_preset(key: str, *, config_path: str | Path | None = None) -> CapitalPreset:`
- ligne 289 — `def get_default_capital_preset(*, config_path: str | Path | None = None) -> CapitalPreset:`
- ligne 299 — `def resolve_effective_capital_preset(`
- ligne 316 — `def capital_preset_fingerprint(preset: CapitalPreset) -> str:`
- ligne 325 — `def build_screener_config_kwargs_from_preset(preset: CapitalPreset) -> dict[str, Any]:`
- ligne 343 — `def adaptive_min_adv(equity: float, max_position_weight: float = 0.10, target_pct_of_adv: float = 0.01) -> float:`
- ligne 364 — `def resolve_adaptive_liquidity_threshold(`
- ligne 382 — `def build_selector_config_kwargs_from_preset(preset: CapitalPreset) -> dict[str, Any]:`
- ligne 45 — `class CapitalPreset:`
- ligne 451 — `def build_risk_config_kwargs_from_preset(preset: CapitalPreset) -> dict[str, Any]:`
- ligne 482 — `def apply_backtest_defaults_from_preset(`
- ligne 525 — `def build_capital_preset_executability_summary(`
- ligne 83 — `def _normalize_option_value(option_key: str, raw_value: Any) -> Any:`
- ligne 94 — `def _coerce_float(value: object, *, field_name: str) -> float:`
## `common/config_loader.py`

- ligne 30 — `def resolve_config_path(path: str | os.PathLike[str] | None = None) -> Path:`
- ligne 53 — `def override_config_path(path: str | os.PathLike[str] | None) -> Iterator[None]:`
- ligne 69 — `def _walk_substitute(node: Any, vault: Any) -> Any:`
- ligne 91 — `def _apply_vault_overrides(cfg: dict, vault: Any) -> dict:`
- ligne 96 — `def load_config(`
## `common/config_vault.py`

- ligne 146 — `class HashiCorpVault:`
- ligne 211 — `def build_vault_from_env() -> ConfigVault:`
- ligne 220 — `def get_live_secret_policy() -> str:`
- ligne 241 — `def is_live_secret_policy_satisfied() -> tuple[bool, dict[str, str]]:`
- ligne 274 — `def _safe(key: str) -> str:`
- ligne 39 — `class ConfigVault(Protocol):`
- ligne 57 — `class EnvFallbackVault:`
## `common/daily_quality_report.py`

- ligne 178 — `class CombinedDailyReport:`
- ligne 198 — `def _load_previous_symbols(`
- ligne 221 — `def _persist_report(`
- ligne 245 — `def build_and_persist_daily_report(`
- ligne 51 — `class UniverseAnomalyReport:`
- ligne 81 — `def detect_universe_anomalies(`
## `common/data_availability.py`

- ligne 112 — `class FutureDataError(RuntimeError):`
- ligne 124 — `class StaleDataError(RuntimeError):`
- ligne 136 — `def validate_availability(`
- ligne 170 — `def validate_availability_or_degraded(`
- ligne 215 — `class DailyQualityReport:`
- ligne 242 — `def build_daily_quality_report(`
- ligne 325 — `def enrich_dataframe_with_pit(`
- ligne 416 — `def build_availability_from_row(`
- ligne 42 — `class QualityState(str, Enum):`
- ligne 487 — `def make_availability_from_bar_date(`
- ligne 61 — `class DataAvailabilityInfo:`
## `common/entry_data_gate.py`

- ligne 120 — `class EntryDataGate:`
- ligne 299 — `def check_entry_data_readiness(`
- ligne 340 — `class EntryDataBlocked(RuntimeError):`
- ligne 76 — `class SourceGateResult:`
- ligne 89 — `class EntryDataGateResult:`
## `common/logging_setup.py`

- ligne 105 — `def _configure_utf8_stdio() -> None:`
- ligne 119 — `def _reset_root_logging_handlers(logger: logging.Logger) -> None:`
- ligne 128 — `def configure_root_logging(`
- ligne 193 — `def setup_logging_with_file_handler(`
- ligne 211 — `class JSONFormatter(logging.Formatter):`
- ligne 251 — `def _resolve_log_formatter(fmt: str, datefmt: str | None = None) -> logging.Formatter:`
- ligne 31 — `def _is_windows_sharing_violation(exc: BaseException) -> bool:`
- ligne 35 — `class _WindowsSafeRolloverMixin:`
- ligne 56 — `class SafeRotatingFileHandler(_WindowsSafeRolloverMixin, RotatingFileHandler):`
- ligne 68 — `class SafeTimedRotatingFileHandler(_WindowsSafeRolloverMixin, TimedRotatingFileHandler):`
- ligne 84 — `def _gzip_rotator(source: str, dest: str) -> None:`
- ligne 92 — `def _gzip_namer(name: str) -> str:`
- ligne 97 — `def _resolve_log_path(log_path: str) -> Path:`
## `common/market_calendar.py`

- ligne 108 — `def is_us_market_holiday(d: date) -> bool:`
- ligne 113 — `def getLastDateMarche(ref_date: Optional[date] = None) -> date:`
- ligne 124 — `def next_trading_day(from_date: date, *, nth: int = 1) -> date:`
- ligne 162 — `def trading_days_between(start: date, end: date) -> int:`
- ligne 19 — `def _get_nyse_calendar():`
- ligne 31 — `def is_trading_day(d: date) -> bool:`
- ligne 39 — `def nyse_session_dates(start: date, end: date) -> list[date]:`
- ligne 75 — `def get_nyse_session_bounds(session_date: date) -> tuple[datetime, datetime]:`
## `common/metrics.py`

- ligne 118 — `def record_pipeline_step(step: str) -> Generator[None, None, None]:`
## `common/price_convention.py`

- ligne 101 — `def get_price_convention(df: "pd.DataFrame") -> PriceConvention:`
- ligne 122 — `def validate_no_mixed_convention(`
- ligne 38 — `class PriceConvention(str, Enum):`
- ligne 71 — `def declare_price_convention(`
## `common/publish_tradable_universe.py`

- ligne 140 — `def publish_full_tradable_universe(`
- ligne 24 — `def _require_tables(engine: Engine) -> None:`
- ligne 241 — `def main(argv: list[str] | None = None) -> int:`
- ligne 38 — `def _load_source_scope(engine: Engine, snapshot_date: date, preset_key: str) -> tuple[dict[str, object], pd.DataFrame]:`
- ligne 77 — `def _load_objective_context(`
## `common/quantity_utils.py`

- ligne 11 — `def normalize_share_quantity(value: float | int | str | Decimal | None, *, decimals: int = QUANTITY_DECIMALS) -> float:`
- ligne 32 — `def is_effectively_integer_quantity(value: float | int | str | Decimal | None, *, decimals: int = QUANTITY_DECIMALS) -> bool:`
- ligne 38 — `def format_share_quantity(value: float | int | str | Decimal | None, *, decimals: int = QUANTITY_DECIMALS) -> str:`
## `common/sizing.py`

- ligne 20 — `class SizingConfig:`
## `common/tradable_universe.py`

- ligne 133 — `def publish_universe_run(`
- ligne 19 — `class UniverseSnapshotNotFoundError(RuntimeError):`
- ligne 24 — `class UniverseMember:`
- ligne 244 — `def fail_universe_run(engine: Engine, universe_run_id: str, reason: str) -> None:`
- ligne 263 — `def resolve_universe_asof(`
- ligne 328 — `def load_tradable_universe_for_period(`
- ligne 386 — `def compute_universe_fingerprint(`
- ligne 52 — `class UniverseResolution:`
- ligne 69 — `def _utc_now_naive() -> datetime:`
- ligne 73 — `def universe_schema_available(engine: Engine) -> bool:`
- ligne 84 — `def begin_universe_run(`
## `common/trading_costs.py`

- ligne 26 — `class TradingCostModel:`
## `common/windows_sleep_guard.py`

- ligne 18 — `class SleepGuardError(RuntimeError):`
- ligne 22 — `def _is_windows() -> bool:`
- ligne 26 — `def _set_thread_execution_state(flags: int) -> int:`
- ligne 37 — `def prevent_windows_sleep(*, enabled: bool = True) -> Iterator[bool]:`

