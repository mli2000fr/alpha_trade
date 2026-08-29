# Inventaire API — service

Cet inventaire est dérivé des signatures présentes dans le code. Les symboles préfixés par `_` restent internes. Les numéros de ligne sont indicatifs ; le chemin et le nom du symbole sont les repères stables.

## `service/_finnhub_cache.py`

- ligne 31 — `def _cache_root() -> Path:`
- ligne 39 — `def _cache_path(symbol: str) -> Path:`
- ligne 46 — `def get_cached_profile(`
- ligne 73 — `def store_profile(symbol: str, profile: Mapping[str, Any]) -> None:`
- ligne 89 — `def invalidate(symbol: str) -> None:`
## `service/_http_retry.py`

- ligne 104 — `def _backoff_delay(policy: RetryPolicy, attempt: int) -> float:`
- ligne 112 — `def _format_remaining_duration(seconds: float) -> str:`
- ligne 125 — `def _parse_retry_after_seconds(response: requests.Response | None) -> float | None:`
- ligne 151 — `def _retry_delay_for_exception(policy: RetryPolicy, attempt: int, exc: Exception | None) -> float:`
- ligne 160 — `def _perform_request(`
- ligne 169 — `def _ensure_response(response: Any) -> requests.Response:`
- ligne 173 — `def request_with_retry(`
- ligne 231 — `def _extract_host(url: str) -> str:`
- ligne 239 — `def _redact_sensitive_text(text: str) -> str:`
- ligne 263 — `class _RetryableHttpError(Exception):`
- ligne 35 — `class RetryPolicy:`
- ligne 46 — `class _CircuitState:`
- ligne 52 — `class CircuitBreaker:`
- ligne 96 — `class CircuitOpenError(RuntimeError):`
## `service/_telemetry.py`

- ligne 38 — `def bump(client: str, metric: str, *, by: int = 1) -> None:`
- ligne 46 — `def get_telemetry(client: str | None = None) -> Mapping[str, Mapping[str, int]] | Mapping[str, int]:`
- ligne 58 — `def reset_telemetry() -> None:`
## `service/alerting.py`

- ligne 112 — `class EmailNotifier:`
- ligne 155 — `class TelegramNotifier:`
- ligne 200 — `class DiscordNotifier:`
- ligne 242 — `class SMSNotifier:`
- ligne 301 — `def _split_recipients(value: str) -> tuple[str, ...]:`
- ligne 305 — `def build_notifiers_from_env(env: Optional[dict] = None) -> tuple[Notifier, ...]:`
- ligne 369 — `def build_notifier_from_env(env: Optional[dict] = None) -> Notifier:`
- ligne 380 — `def send_system_alert(`
- ligne 47 — `class Notifier(Protocol):`
- ligne 60 — `class LogNotifier:`
- ligne 75 — `class SlackNotifier:`
## `service/alpaca/accounts.py`

- ligne 26 — `class BrokerAccount:`
- ligne 43 — `class AccountRegistry:`
## `service/alpaca/clientAlpaca.py`

- ligne 111 — `def _default_start_date() -> str:`
- ligne 116 — `def _filter_bars_after_start_date(bars: list[dict[str, Any]], start_date: Optional[str]) -> list[dict[str, Any]]:`
- ligne 128 — `def _normalize_quotes_window_boundary(value: str, *, end_of_day: bool) -> str:`
- ligne 150 — `def _should_log_page_progress(page_index: int, *, has_next_page: bool) -> bool:`
- ligne 154 — `def fetch_alpaca_assets(session: Optional[requests.Session] = None, account_id: Optional[str] = None) -> list[dict[str, Any]]:`
- ligne 171 — `def fetch_asset_by_symbol(`
- ligne 211 — `def fetch_bars(`
- ligne 29 — `def _alpaca_retry_policy() -> RetryPolicy:`
- ligne 311 — `def fetch_latest_quotes(`
- ligne 352 — `def fetch_latest_historical_quote_in_window(`
- ligne 423 — `def fetch_historical_quotes(`
- ligne 450 — `def iter_historical_quotes_pages(`
- ligne 48 — `def _try_alert_api_failure(service: str, error: str, status_code: int | None = None) -> None:`
- ligne 74 — `class AlpacaBarsFetchError(RuntimeError):`
- ligne 81 — `def get_alpaca_credentials(account_id: Optional[str] = None) -> tuple[str, str]:`
- ligne 91 — `def _build_headers(account_id: Optional[str] = None) -> dict[str, str]:`
- ligne 99 — `def _normalize_start_date(start_date: Optional[str]) -> str:`
## `service/alpaca/clientNewsAlpaca.py`

- ligne 107 — `def iter_news_pages(`
- ligne 19 — `def _build_headers(account_id: str | None = None) -> dict[str, str]:`
- ligne 27 — `def _fmt_utc(value: datetime) -> str:`
- ligne 33 — `def fetch_news_page(`
## `service/alpaca/reconciliation.py`

- ligne 125 — `def build_reconciliation_summary(`
- ligne 167 — `def persist_statements(`
- ligne 195 — `def _normalize(account_id: str, r: Mapping[str, Any]) -> dict[str, Any]:`
- ligne 221 — `def reconcile(`
- ligne 277 — `def _load_broker_fills(engine: Engine, account_id: str, trade_date: date) -> list[dict[str, Any]]:`
- ligne 289 — `def _load_internal_fills(engine: Engine, account_id: str, trade_date: date) -> list[dict[str, Any]]:`
- ligne 303 — `def _qty_match(a: Any, b: Any) -> bool:`
- ligne 309 — `def _price_match(a: Any, b: Any) -> bool:`
- ligne 318 — `def _diff_missing_internal(b: Mapping[str, Any]) -> StatementDiff:`
- ligne 332 — `def _diff_missing_broker(c: Mapping[str, Any]) -> StatementDiff:`
- ligne 346 — `def _diff_qty(b: Mapping[str, Any], c: Mapping[str, Any]) -> StatementDiff:`
- ligne 360 — `def _diff_price(b: Mapping[str, Any], c: Mapping[str, Any]) -> StatementDiff:`
- ligne 374 — `def _to_float(v: Any) -> float | None:`
- ligne 383 — `def _iso(v: Any) -> str | None:`
- ligne 56 — `class StatementDiff:`
- ligne 71 — `def _read_csv_text(csv_source: str | Path | io.TextIOBase) -> str:`
- ligne 82 — `def _normalize_csv_key(value: object) -> str:`
- ligne 86 — `def _pick_csv_value(row: Mapping[str, Any], logical_key: str) -> Any:`
- ligne 95 — `def parse_statement_csv(csv_source: str | Path | io.TextIOBase) -> list[dict[str, Any]]:`
## `service/alpaca/statements.py`

- ligne 120 — `def load_monthly_inputs_from_db(`
- ligne 20 — `def fetch_account_activities(`
- ligne 244 — `def _to_datetime(val: Any) -> datetime | None:`
- ligne 256 — `def _compute_realized_pnl_fifo_period(`
- ligne 65 — `def _iso(d: date | datetime) -> str:`
- ligne 76 — `def _decimal_to_float(val: Any) -> float:`
- ligne 85 — `def _compute_realized_pnl_fifo(fills: list[dict[str, Any]]) -> float:`
## `service/alpaca/trading_client.py`

- ligne 21 — `class BrokerApiError(Exception):`
- ligne 30 — `class AlpacaTradingClient:`
## `service/broker_failover.py`

- ligne 154 — `def build_failover_doctrine_summary(`
- ligne 34 — `class WriteSuspendedError(RuntimeError):`
- ligne 38 — `class FailoverBrokerClient:`
## `service/cache/factory.py`

- ligne 9 — `def build_cache_from_env(`
## `service/cache/in_memory.py`

- ligne 20 — `class _Entry:`
- ligne 25 — `class InMemoryCache:`
## `service/cache/redis_cache.py`

- ligne 13 — `class RedisCache:`
## `service/eodhd/accounts.py`

- ligne 118 — `def get_eodhd_token() -> str:`
- ligne 25 — `class EodhdAuthError(RuntimeError):`
- ligne 30 — `class EodhdAccount:`
- ligne 42 — `class EodhdAccountRegistry:`
## `service/eodhd/adapters.py`

- ligne 107 — `def infer_splits_from_adjusted_close(eod_history: list[dict], *, threshold: float = 0.05) -> list[dict]:`
- ligne 153 — `def eodhd_to_split_only(raw_bars: list[dict], splits: list[dict]) -> list[dict]:`
- ligne 202 — `def _date_to_rth_open_string(date_iso: str) -> str:`
- ligne 215 — `def _date_to_close_timestamp(date_iso: str) -> datetime:`
- ligne 226 — `def _typical_price_proxy(high: float, low: float, close: float) -> float:`
- ligne 231 — `def to_stock_bars_daily_row(bar: dict, symbol: str) -> dict:`
- ligne 267 — `def to_stock_bars_row(bar: dict, symbol: str, timeframe: str = "1D") -> dict:`
- ligne 48 — `def parse_split_ratio(value: Any) -> float:`
- ligne 82 — `def cumulative_split_factor(splits: Iterable[dict], target_date: str) -> float:`
## `service/eodhd/cache.py`

- ligne 28 — `class CacheEntry:`
- ligne 40 — `class EodhdDiskCache:`
## `service/eodhd/clientEodhd.py`

- ligne 105 — `def _build_session(session: Optional[requests.Session]) -> requests.Session:`
- ligne 109 — `def _do_request(`
- ligne 179 — `def fetch_eod_bulk(`
- ligne 217 — `def fetch_eod(`
- ligne 256 — `def fetch_splits(`
- ligne 293 — `def fetch_dividends(`
- ligne 330 — `def fetch_fundamentals(`
- ligne 363 — `def fetch_symbol_fundamentals_record(`
- ligne 44 — `class EodhdBarsFetchError(RuntimeError):`
- ligne 48 — `class EodhdPermissionError(EodhdBarsFetchError):`
- ligne 52 — `class EodhdSymbolNotFound(EodhdBarsFetchError):`
- ligne 56 — `class EodhdTemporarilyUnavailable(EodhdBarsFetchError):`
- ligne 60 — `def _redact_sensitive_text(text: str) -> str:`
- ligne 82 — `def _retry_policy() -> RetryPolicy:`
- ligne 91 — `def _get_token() -> str:`
- ligne 98 — `def _get_base_url() -> str:`
## `service/eodhd/news_client.py`

- ligne 100 — `def _stable_article_id(symbol: str, raw: dict[str, Any]) -> str:`
- ligne 112 — `def _to_project_symbol(symbol: str) -> str:`
- ligne 123 — `def _normalize_symbol_list(symbol_query: str, raw_symbols: Any) -> list[str]:`
- ligne 161 — `def _normalize_payload(symbol: str, raw: dict[str, Any]) -> dict[str, Any]:`
- ligne 190 — `def _parse_published_ts(raw_date: Any) -> datetime | None:`
- ligne 202 — `def fetch_news_page(`
- ligne 311 — `def iter_news_pages(`
- ligne 63 — `class EodhdNewsFetchError(RuntimeError):`
- ligne 67 — `def _to_utc(value: datetime) -> datetime:`
- ligne 73 — `def _fmt_date(value: datetime) -> str:`
- ligne 77 — `def _retry_policy() -> RetryPolicy:`
- ligne 86 — `def _get_token() -> str:`
- ligne 93 — `def _get_base_url() -> str:`
## `service/eodhd/quota.py`

- ligne 314 — `def get_default_tracker(cache_dir: Optional[Path] = None) -> EodhdQuotaTracker:`
- ligne 323 — `def reset_default_tracker() -> None:`
- ligne 39 — `class EodhdQuotaExceeded(RuntimeError):`
- ligne 43 — `class EodhdCircuitOpen(RuntimeError):`
- ligne 48 — `class QuotaState:`
- ligne 58 — `class EodhdQuotaTracker:`
## `service/eodhd/symbols.py`

- ligne 109 — `def is_supported(symbol: str) -> bool:`
- ligne 121 — `def add_exception(project_symbol: str, eodhd_symbol: Optional[str]) -> None:`
- ligne 138 — `def _resolve_with_runtime(symbol: str) -> Optional[str]:`
- ligne 36 — `def _load_exceptions() -> dict[str, str]:`
- ligne 48 — `def reset_exceptions_cache() -> None:`
- ligne 53 — `def to_eodhd(symbol: str, exchange: str = DEFAULT_EXCHANGE) -> str:`
- ligne 90 — `def from_eodhd(eodhd_symbol: str) -> tuple[str, str]:`
## `service/finnhub/clientFinnhub.py`

- ligne 103 — `def fetch_company_profile(`
- ligne 139 — `def fetch_symbol_sector(symbol: str, session: Optional[requests.Session] = None) -> Optional[str]:`
- ligne 149 — `def fetch_symbol_sector_record(symbol: str, session: Optional[requests.Session] = None) -> dict[str, Any]:`
- ligne 162 — `def fetch_symbol_fundamentals_record(symbol: str, session: Optional[requests.Session] = None) -> dict[str, Any]:`
- ligne 178 — `def fetch_multiple_symbol_sector_records(`
- ligne 208 — `def fetch_earnings_calendar(`
- ligne 232 — `def fetch_multiple_symbols_earnings_calendar(`
- ligne 38 — `def get_finnhub_token() -> str:`
- ligne 48 — `def _normalize_symbol(symbol: str) -> str:`
- ligne 55 — `def _build_params(symbol: str) -> dict[str, str]:`
- ligne 62 — `def _request_json(`
## `service/finnhub/news_client.py`

- ligne 109 — `def _normalize_payload(symbol: str, raw: dict[str, Any]) -> dict[str, Any]:`
- ligne 155 — `def fetch_news_page(`
- ligne 264 — `def iter_news_pages(`
- ligne 55 — `def _to_utc(value: datetime) -> datetime:`
- ligne 61 — `def _fmt_date(value: datetime) -> str:`
- ligne 65 — `def _throttle_company_news_requests() -> float:`
- ligne 90 — `def _reset_company_news_rate_limit_state() -> None:`
- ligne 97 — `def _stable_article_id(symbol: str, raw: dict[str, Any]) -> str:`
## `service/fmp/clientFmp.py`

- ligne 104 — `def fetch_profile(symbol: str) -> dict[str, Any] | None:`
- ligne 118 — `def fetch_ratios(symbol: str) -> dict[str, Any] | None:`
- ligne 132 — `def fetch_key_metrics(symbol: str) -> dict[str, Any] | None:`
- ligne 146 — `def fetch_financial_growth(symbol: str) -> dict[str, Any] | None:`
- ligne 160 — `def fetch_symbol_fundamentals_record(`
- ligne 29 — `class FmpError(RuntimeError):`
- ligne 33 — `class FmpRateLimitError(FmpError):`
- ligne 37 — `class FmpSymbolNotFound(FmpError):`
- ligne 41 — `def _get_session() -> requests.Session:`
- ligne 52 — `def _rate_limit() -> None:`
- ligne 61 — `def _get_api_key() -> str:`
- ligne 71 — `def _do_get(endpoint: str, params: dict[str, Any] | None = None) -> Any:`
## `service/fred/clientFred.py`

- ligne 20 — `class FredFetchError(RuntimeError):`
- ligne 24 — `def _retry_policy() -> RetryPolicy:`
- ligne 33 — `def _resolve_api_key(api_key_env: str = DEFAULT_API_KEY_ENV) -> str:`
- ligne 40 — `def fetch_series_observations(`
## `service/ibkr/client.py`

- ligne 27 — `class IBKRUnavailableError(RuntimeError):`
- ligne 274 — `def _map_ibkr_status(s: str) -> str:`
- ligne 31 — `class IBKRBrokerClient:`
## `service/ibkr/credentials.py`

- ligne 13 — `class IBKRCredentials:`
- ligne 19 — `def get_ibkr_credentials() -> IBKRCredentials:`
## `service/market/__main__.py`

- ligne 17 — `def _default_progress_callback(step: dict[str, Any]) -> None:`
- ligne 32 — `def _cmd_populate_macro(args: argparse.Namespace) -> None:`
- ligne 53 — `def _cmd_recompute_regime(args: argparse.Namespace) -> None:`
- ligne 75 — `def main() -> None:`
## `service/market/calendar_patterns.py`

- ligne 12 — `class CalendarPatternHit:`
- ligne 20 — `def _in_md_window(d: date, start_md: str, end_md: str) -> bool:`
- ligne 36 — `def is_third_friday(d: date) -> bool:`
- ligne 44 — `def is_month_end_window(d: date, business_days_from_end: int) -> bool:`
- ligne 61 — `def evaluate_pattern(name: str, cfg: CalendarPatternConfig, d: date) -> CalendarPatternHit | None:`
- ligne 84 — `def evaluate_calendar_patterns(`
## `service/market/config.py`

- ligne 100 — `class MoveConfig:`
- ligne 108 — `class RvxConfig:`
- ligne 116 — `class EarningsShieldConfig:`
- ligne 125 — `class BuybackBlackoutConfig:`
- ligne 132 — `class SentinelConfig:`
- ligne 138 — `class RegimeHysteresisConfig:`
- ligne 14 — `class CalendarPatternConfig:`
- ligne 155 — `class MarketRegimesConfig:`
- ligne 186 — `class TrailingStopYAMLConfig:`
- ligne 201 — `def _to_pattern(name: str, raw: Mapping[str, Any] | None) -> CalendarPatternConfig:`
- ligne 217 — `def parse_market_regimes(raw: Mapping[str, Any] | None) -> MarketRegimesConfig:`
- ligne 28 — `class VixConfig:`
- ligne 38 — `class YieldsConfig:`
- ligne 413 — `def parse_trailing_stop(raw: Mapping[str, Any] | None) -> TrailingStopYAMLConfig:`
- ligne 67 — `class SentimentBreakerConfig:`
- ligne 78 — `class SectorLimitsConfig:`
- ligne 84 — `class VxnConfig:`
- ligne 92 — `class Vix3mConfig:`
## `service/market/earnings_shield.py`

- ligne 24 — `class EarningsShieldResult:`
- ligne 30 — `def default_db_lookup(trade_date: date, lookback_days: int, lookahead_days: int) -> dict[str, date]:`
- ligne 63 — `def compute_earnings_shield(`
## `service/market/macro_providers.py`

- ligne 103 — `def _is_strict_before_mode(*, yaml_cfg: Mapping[str, Any] | None, execution_context: str, macro_pit_mode: str | None) -> bool:`
- ligne 1063 — `class CompositeMacroProvider:`
- ligne 111 — `def _resolve_provider_trade_date(trade_date: date, *, strict_before: bool) -> date:`
- ligne 1114 — `def _build_primary_macro_provider(`
- ligne 1133 — `def _build_yield_macro_provider(`
- ligne 1164 — `def _build_network_macro_provider(yaml_cfg: Mapping[str, Any] | None) -> Any | None:`
- ligne 121 — `def _coerce_float(value: object) -> float | None:`
- ligne 1229 — `def build_default_macro_provider(`
- ligne 1261 — `def _snapshot_to_payload(snapshot: object) -> dict[str, Any]:`
- ligne 1269 — `def _snapshot_to_next_state(snapshot: object, payload: Mapping[str, Any] | None = None) -> MarketRegimeState | None:`
- ligne 128 — `def _effective_source_from_mapping(source_by_signal: Mapping[str, str]) -> str | None:`
- ligne 1283 — `def populate_macro_indicators_table(`
- ligne 138 — `def _build_source_summary(source_by_signal: Mapping[str, str]) -> dict[str, Any]:`
- ligne 1380 — `def recompute_macro_regime_table(`
- ligne 153 — `def _signal_key_for_method(method: str) -> str | None:`
- ligne 171 — `def _resolve_signal_source(provider: Any, signal_key: str) -> str | None:`
- ligne 188 — `def _log_successful_fetch(*, provider_name: str, key: str, symbol: str, trade_date: date, bars: Sequence[Mapping[str, Any]]) -> None:`
- ligne 231 — `def _last_close(bars: Sequence[Mapping[str, Any]], on_or_before: date) -> float | None:`
- ligne 256 — `def _close_history(bars: Sequence[Mapping[str, Any]], on_or_before: date, n: int) -> list[float]:`
- ligne 277 — `def _extract_latest_10y_close(provider: Any, trade_date: date) -> float | None:`
- ligne 300 — `class StooqMacroProvider:`
- ligne 410 — `class EodhdMacroProvider:`
- ligne 559 — `class FredMacroProvider:`
- ligne 681 — `class RoutedMacroProvider:`
- ligne 70 — `def normalize_macro_pit_mode(value: object) -> str:`
- ligne 806 — `class TableFirstMacroProvider:`
- ligne 86 — `def resolve_macro_pit_mode(`
## `service/market/macro_signals.py`

- ligne 103 — `def evaluate_vxn(`
- ligne 121 — `def evaluate_vix_term_structure(`
- ligne 15 — `class MacroDataProvider(Protocol):`
- ligne 174 — `def evaluate_yield_10y(`
- ligne 43 — `class MacroEvaluation:`
- ligne 58 — `class VixTermStructure:`
- ligne 68 — `def evaluate_vix(`
## `service/market/models.py`

- ligne 235 — `def neutral_snapshot(trade_date: date) -> MarketRegimeSnapshot:`
- ligne 31 — `class MarketRegimeState:`
- ligne 84 — `class MarketRegimeSnapshot:`
## `service/market/regime_manager.py`

- ligne 103 — `def _build_mode_why(mode: RegimeMode, reasons: list[str], trace: list[dict[str, Any]]) -> dict[str, Any]:`
- ligne 1311 — `def reset_cache() -> None:`
- ligne 134 — `def _required_macro_data_quality_keys(config: MarketRegimesConfig) -> tuple[str, ...]:`
- ligne 151 — `def _resolve_missing_macro_data_quality(`
- ligne 162 — `def _tighten_numeric_limit(current: int | float | None, candidate: int | float | None) -> int | float | None:`
- ligne 170 — `def _state_cache_key(previous_state: MarketRegimeState | None) -> tuple[Any, ...]:`
- ligne 188 — `def _count_triggered_sources(trace: list[dict[str, Any]], sources: frozenset[str]) -> int:`
- ligne 192 — `def _transition_without_hysteresis(`
- ligne 231 — `def _apply_hysteresis(`
- ligne 385 — `def build_snapshot(`
- ligne 45 — `class MacroDataUnavailableError(RuntimeError):`
- ligne 50 — `class _CacheEntry:`
- ligne 60 — `def _mode_strength(mode: RegimeMode) -> int:`
- ligne 65 — `def _escalate(current: RegimeMode, candidate: str) -> RegimeMode:`
- ligne 73 — `def _push_trace(`
## `service/market/sentiment_provider.py`

- ligne 129 — `def load_market_sentiment_reading(`
- ligne 191 — `class DbSentimentScoreProvider:`
- ligne 26 — `class MarketSentimentReading:`
- ligne 49 — `def _normalize_trade_date(value: Any) -> date | None:`
- ligne 60 — `def _query_market_sentiment(`
## `service/market/sentiment_regime.py`

- ligne 18 — `class SentimentRegimeEvaluation:`
- ligne 27 — `def evaluate_sentiment_regime(`
## `service/market/state_store.py`

- ligne 17 — `def load_regime_state(path: Path | None = None) -> MarketRegimeState | None:`
- ligne 27 — `def save_regime_state(state: MarketRegimeState | None, path: Path | None = None) -> Path:`
## `service/market/volatility.py`

- ligne 19 — `class OHLCBar:`
- ligne 25 — `def compute_atr_from_bars(bars: Sequence[OHLCBar], period: int = 14) -> float | None:`
- ligne 51 — `def compute_atr_from_eodhd_cache(symbol: str, *, period: int = 14, lookback_days: int = 60) -> float | None:`
## `service/mock_broker.py`

- ligne 32 — `class _StreamCtx(AbstractContextManager):`
- ligne 48 — `class MockBroker:`
## `service/prometheus_metrics.py`

- ligne 160 — `def bump_api_error(service: str) -> None:`
- ligne 165 — `def bump_execution_run() -> None:`
- ligne 170 — `def bump_alert(severity: str) -> None:`
- ligne 175 — `def set_circuit_breaker_active(active: bool) -> None:`
- ligne 180 — `def set_heartbeat_stale(stale: bool) -> None:`
- ligne 185 — `def set_empty_universe(empty: bool) -> None:`
- ligne 190 — `def set_kill_switch_active(active: bool) -> None:`
- ligne 195 — `def set_model_drift_active(active: bool) -> None:`
- ligne 200 — `def set_cash_ledger_aligned(aligned: bool) -> None:`
- ligne 205 — `def render_metrics() -> str:`
- ligne 210 — `def write_metrics_file(filepath: str | Path | None = None) -> Path:`
- ligne 230 — `def start_prometheus_server(`
- ligne 57 — `class _MetricsRegistry:`
## `service/sec/clientEdgar.py`

- ligne 120 — `def ticker_to_cik(ticker: str) -> str:`
- ligne 135 — `def fetch_company_facts(cik: str) -> dict[str, Any]:`
- ligne 168 — `def fetch_symbol_fundamentals_record(`
- ligne 49 — `class EdgarError(RuntimeError):`
- ligne 53 — `class EdgarSymbolNotFound(EdgarError):`
- ligne 59 — `def _rate_limit() -> None:`
- ligne 69 — `def _load_cik_mapping(force_refresh: bool = False) -> dict[str, str]:`
## `service/sec/ratio_calculator.py`

- ligne 254 — `def _compute_beta(`
- ligne 297 — `def _batch_update_market_ratios(`
- ligne 44 — `def enrich_with_market_ratios(`
## `service/sec/xbrl_mapper.py`

- ligne 157 — `def _parse_date(date_str: str | None) -> _date | None:`
- ligne 167 — `def _is_10q(form: str) -> bool:`
- ligne 171 — `def _is_10k(form: str) -> bool:`
- ligne 175 — `def _parse_frame(frame: str) -> tuple[int | None, str | None]:`
- ligne 191 — `def _build_filing_index(`
- ligne 239 — `def extract_fundamentals_from_sec(`
- ligne 390 — `def _compute_ratios(records: list[dict[str, Any]]) -> None:`
- ligne 502 — `def _to_fundamentals_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:`
- ligne 99 — `def _extract_tag_value(`
## `service/stooq/clientStooq.py`

- ligne 42 — `def _stooq_symbol(symbol: str) -> str:`
- ligne 52 — `def fetch_daily_bars(`
- ligne 86 — `def _parse_csv(raw: str) -> list[dict[str, Any]]:`
## `service/yahoo/clientYahooFinance.py`

- ligne 105 — `def fetch_latest_quotes_yahoo(`
- ligne 12 — `def _normalize_symbol(symbol: str) -> str:`
- ligne 19 — `def _import_yfinance() -> Any:`
- ligne 34 — `def _coerce_mapping(value: Any) -> dict[str, Any]:`
- ligne 52 — `def _normalize_text(value: Any) -> str | None:`
- ligne 59 — `def _normalize_market_cap(value: Any) -> float | None:`
- ligne 71 — `def fetch_symbol_fundamentals_record(symbol: str, session: Optional[object] = None) -> dict[str, Any]:`

