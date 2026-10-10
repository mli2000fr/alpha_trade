# Inventaire API — service

Extraction AST du 2026-10-10 ; aucune importation ni exécution métier.

Classes, fonctions de module et méthodes déclarées ; fonctions imbriquées exclues.
Les symboles `_...` sont internes. Signature présente ≠ API publique stable.

## `service/__init__.py`

Source SHA-256 : `154c62749e146d6b4241e820f5c94041a98f6c55edffe617071f265a76902869`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `service/_finnhub_cache.py`

Source SHA-256 : `cfd91cd15b634ae59a98342c83a886bbda97bc2a29d83900144cf815e1ea3587`

- [_cache_root](../../service/_finnhub_cache.py) — ligne 31 : `def _cache_root() -> Path`
- [_cache_path](../../service/_finnhub_cache.py) — ligne 39 : `def _cache_path(symbol: str) -> Path`
- [get_cached_profile](../../service/_finnhub_cache.py) — ligne 46 : `def get_cached_profile(symbol: str, *, ttl_days: int=DEFAULT_CACHE_TTL_DAYS) -> dict[str, Any] | None`
- [store_profile](../../service/_finnhub_cache.py) — ligne 73 : `def store_profile(symbol: str, profile: Mapping[str, Any]) -> None`
- [invalidate](../../service/_finnhub_cache.py) — ligne 89 : `def invalidate(symbol: str) -> None`

## `service/_http_retry.py`

Source SHA-256 : `170dec65c86a539a504a00f83018420745e468a0a8d86e1b3fc80160f77270b4`

- [RetryPolicy](../../service/_http_retry.py) — ligne 36 : `class RetryPolicy`
- [_CircuitState](../../service/_http_retry.py) — ligne 47 : `class _CircuitState`
- [CircuitBreaker](../../service/_http_retry.py) — ligne 53 : `class CircuitBreaker`
- [CircuitBreaker._state](../../service/_http_retry.py) — ligne 66 : `def _state(self, host: str) -> _CircuitState`
- [CircuitBreaker.check](../../service/_http_retry.py) — ligne 70 : `def check(self, host: str) -> None`
- [CircuitBreaker.record_success](../../service/_http_retry.py) — ligne 79 : `def record_success(self, host: str) -> None`
- [CircuitBreaker.record_failure](../../service/_http_retry.py) — ligne 84 : `def record_failure(self, host: str) -> None`
- [CircuitOpenError](../../service/_http_retry.py) — ligne 97 : `class CircuitOpenError(RuntimeError)`
- [_backoff_delay](../../service/_http_retry.py) — ligne 105 : `def _backoff_delay(policy: RetryPolicy, attempt: int) -> float`
- [_format_remaining_duration](../../service/_http_retry.py) — ligne 113 : `def _format_remaining_duration(seconds: float) -> str`
- [_parse_retry_after_seconds](../../service/_http_retry.py) — ligne 126 : `def _parse_retry_after_seconds(response: requests.Response | None) -> float | None`
- [_retry_delay_for_exception](../../service/_http_retry.py) — ligne 152 : `def _retry_delay_for_exception(policy: RetryPolicy, attempt: int, exc: Exception | None) -> float`
- [_perform_request](../../service/_http_retry.py) — ligne 161 : `def _perform_request(session: requests.Session, method: str, url: str, request_kwargs: dict[str, Any]) -> requests.Response`
- [_ensure_response](../../service/_http_retry.py) — ligne 170 : `def _ensure_response(response: Any) -> requests.Response`
- [request_with_retry](../../service/_http_retry.py) — ligne 174 : `def request_with_retry(session: requests.Session, method: str, url: str, *, policy: RetryPolicy | None=None, breaker: CircuitBreaker | None=DEFAULT_CIRCUIT_BREAKER, **request_kwargs: Any) -> requests.Response`
- [_extract_host](../../service/_http_retry.py) — ligne 232 : `def _extract_host(url: str) -> str`
- [_redact_sensitive_text](../../service/_http_retry.py) — ligne 240 : `def _redact_sensitive_text(text: str) -> str`
- [_RetryableHttpError](../../service/_http_retry.py) — ligne 268 : `class _RetryableHttpError(Exception)`
- [_RetryableHttpError.__init__](../../service/_http_retry.py) — ligne 269 : `def __init__(self, response: requests.Response) -> None`
- [_RetryableHttpError.as_http_error](../../service/_http_retry.py) — ligne 273 : `def as_http_error(self) -> requests.exceptions.HTTPError`

## `service/_telemetry.py`

Source SHA-256 : `968a2021fab898bc7c5cbb4b5a008b05b6e171f78c410806cda99758ea8b7bd5`

- [bump](../../service/_telemetry.py) — ligne 38 : `def bump(client: str, metric: str, *, by: int=1) -> None`
- [get_telemetry](../../service/_telemetry.py) — ligne 46 : `def get_telemetry(client: str | None=None) -> Mapping[str, Mapping[str, int]] | Mapping[str, int]`
- [reset_telemetry](../../service/_telemetry.py) — ligne 58 : `def reset_telemetry() -> None`

## `service/alerting.py`

Source SHA-256 : `7c19d30ffc11c19b106016db5c85b4c43130e08525d97ee730f5c1a15e5800b7`

- [Notifier](../../service/alerting.py) — ligne 47 : `class Notifier(Protocol)`
- [Notifier.send](../../service/alerting.py) — ligne 50 : `def send(self, subject: str, body: str, *, severity: Severity='warning') -> None`
- [LogNotifier](../../service/alerting.py) — ligne 60 : `class LogNotifier`
- [LogNotifier.send](../../service/alerting.py) — ligne 65 : `def send(self, subject: str, body: str, *, severity: Severity='warning') -> None`
- [SlackNotifier](../../service/alerting.py) — ligne 75 : `class SlackNotifier`
- [SlackNotifier.__post_init__](../../service/alerting.py) — ligne 86 : `def __post_init__(self) -> None`
- [SlackNotifier.send](../../service/alerting.py) — ligne 90 : `def send(self, subject: str, body: str, *, severity: Severity='warning') -> None`
- [EmailNotifier](../../service/alerting.py) — ligne 112 : `class EmailNotifier`
- [EmailNotifier.__post_init__](../../service/alerting.py) — ligne 128 : `def __post_init__(self) -> None`
- [EmailNotifier.send](../../service/alerting.py) — ligne 132 : `def send(self, subject: str, body: str, *, severity: Severity='warning') -> None`
- [TelegramNotifier](../../service/alerting.py) — ligne 155 : `class TelegramNotifier`
- [TelegramNotifier.__post_init__](../../service/alerting.py) — ligne 171 : `def __post_init__(self) -> None`
- [TelegramNotifier.send](../../service/alerting.py) — ligne 175 : `def send(self, subject: str, body: str, *, severity: Severity='warning') -> None`
- [DiscordNotifier](../../service/alerting.py) — ligne 200 : `class DiscordNotifier`
- [DiscordNotifier.__post_init__](../../service/alerting.py) — ligne 213 : `def __post_init__(self) -> None`
- [DiscordNotifier.send](../../service/alerting.py) — ligne 217 : `def send(self, subject: str, body: str, *, severity: Severity='warning') -> None`
- [SMSNotifier](../../service/alerting.py) — ligne 242 : `class SMSNotifier`
- [SMSNotifier.__post_init__](../../service/alerting.py) — ligne 262 : `def __post_init__(self) -> None`
- [SMSNotifier.send](../../service/alerting.py) — ligne 266 : `def send(self, subject: str, body: str, *, severity: Severity='warning') -> None`
- [_split_recipients](../../service/alerting.py) — ligne 301 : `def _split_recipients(value: str) -> tuple[str, ...]`
- [build_notifiers_from_env](../../service/alerting.py) — ligne 305 : `def build_notifiers_from_env(env: Optional[dict]=None) -> tuple[Notifier, ...]`
- [build_notifier_from_env](../../service/alerting.py) — ligne 369 : `def build_notifier_from_env(env: Optional[dict]=None) -> Notifier`
- [send_system_alert](../../service/alerting.py) — ligne 380 : `def send_system_alert(event: str, payload: Optional[dict]=None, *, severity: Severity='warning', env: Optional[dict]=None, cooldown_seconds: float=300.0) -> None`

## `service/alpaca/accounts.py`

Source SHA-256 : `30b12a3c933f1ca713547bc3aa6d44b22afb83c6bfe18e738874337d57f1afe5`

- [BrokerAccount](../../service/alpaca/accounts.py) — ligne 26 : `class BrokerAccount`
- [BrokerAccount.__post_init__](../../service/alpaca/accounts.py) — ligne 36 : `def __post_init__(self) -> None`
- [AccountRegistry](../../service/alpaca/accounts.py) — ligne 43 : `class AccountRegistry`
- [AccountRegistry.__init__](../../service/alpaca/accounts.py) — ligne 49 : `def __init__(self) -> None`
- [AccountRegistry.get](../../service/alpaca/accounts.py) — ligne 54 : `def get(cls) -> AccountRegistry`
- [AccountRegistry.reset](../../service/alpaca/accounts.py) — ligne 60 : `def reset(cls) -> None`
- [AccountRegistry.list_accounts](../../service/alpaca/accounts.py) — ligne 72 : `def list_accounts(self) -> list[BrokerAccount]`
- [AccountRegistry.list_account_ids](../../service/alpaca/accounts.py) — ligne 75 : `def list_account_ids(self) -> list[str]`
- [AccountRegistry.resolve](../../service/alpaca/accounts.py) — ligne 78 : `def resolve(self, account_id: str | None=None) -> BrokerAccount`
- [AccountRegistry.get_credentials](../../service/alpaca/accounts.py) — ligne 91 : `def get_credentials(self, account_id: str | None=None) -> tuple[str, str]`
- [AccountRegistry._load](../../service/alpaca/accounts.py) — ligne 100 : `def _load(self) -> None`
- [AccountRegistry._load_from_yaml](../../service/alpaca/accounts.py) — ligne 115 : `def _load_from_yaml(self) -> None`
- [AccountRegistry._load_from_env_prefixed](../../service/alpaca/accounts.py) — ligne 163 : `def _load_from_env_prefixed(self) -> None`
- [AccountRegistry._load_fallback_env](../../service/alpaca/accounts.py) — ligne 197 : `def _load_fallback_env(self) -> None`

## `service/alpaca/clientAlpaca.py`

Source SHA-256 : `e0efaf23c2bce45a753425ee3ed59272d545f81d7125b10d5e855acf52b0b815`

- [_alpaca_retry_policy](../../service/alpaca/clientAlpaca.py) — ligne 29 : `def _alpaca_retry_policy() -> RetryPolicy`
- [_try_alert_api_failure](../../service/alpaca/clientAlpaca.py) — ligne 48 : `def _try_alert_api_failure(service: str, error: str, status_code: int | None=None) -> None`
- [AlpacaBarsFetchError](../../service/alpaca/clientAlpaca.py) — ligne 74 : `class AlpacaBarsFetchError(RuntimeError)`
- [get_alpaca_credentials](../../service/alpaca/clientAlpaca.py) — ligne 81 : `def get_alpaca_credentials(account_id: Optional[str]=None) -> tuple[str, str]`
- [_build_headers](../../service/alpaca/clientAlpaca.py) — ligne 91 : `def _build_headers(account_id: Optional[str]=None) -> dict[str, str]`
- [_normalize_start_date](../../service/alpaca/clientAlpaca.py) — ligne 99 : `def _normalize_start_date(start_date: Optional[str]) -> str`
- [_default_start_date](../../service/alpaca/clientAlpaca.py) — ligne 111 : `def _default_start_date() -> str`
- [_filter_bars_after_start_date](../../service/alpaca/clientAlpaca.py) — ligne 116 : `def _filter_bars_after_start_date(bars: list[dict[str, Any]], start_date: Optional[str]) -> list[dict[str, Any]]`
- [_normalize_quotes_window_boundary](../../service/alpaca/clientAlpaca.py) — ligne 128 : `def _normalize_quotes_window_boundary(value: str, *, end_of_day: bool) -> str`
- [_should_log_page_progress](../../service/alpaca/clientAlpaca.py) — ligne 150 : `def _should_log_page_progress(page_index: int, *, has_next_page: bool) -> bool`
- [fetch_alpaca_assets](../../service/alpaca/clientAlpaca.py) — ligne 154 : `def fetch_alpaca_assets(session: Optional[requests.Session]=None, account_id: Optional[str]=None) -> list[dict[str, Any]]`
- [fetch_asset_by_symbol](../../service/alpaca/clientAlpaca.py) — ligne 171 : `def fetch_asset_by_symbol(symbol: str, *, session: Optional[requests.Session]=None, account_id: Optional[str]=None) -> dict[str, Any]`
- [fetch_bars](../../service/alpaca/clientAlpaca.py) — ligne 211 : `def fetch_bars(symbol: str, timeframe: str, start_date: Optional[str]=None, session: Optional[requests.Session]=None, account_id: Optional[str]=None, feed: AlpacaFeed=DEFAULT_FEED) -> list[dict[str, Any]]`
- [fetch_latest_quotes](../../service/alpaca/clientAlpaca.py) — ligne 311 : `def fetch_latest_quotes(symbols: list[str], session: Optional[requests.Session]=None, account_id: Optional[str]=None) -> dict[str, dict[str, Any]]`
- [fetch_latest_historical_quote_in_window](../../service/alpaca/clientAlpaca.py) — ligne 352 : `def fetch_latest_historical_quote_in_window(symbol: str, *, start: str, end: str, session: Optional[requests.Session]=None, account_id: Optional[str]=None, feed: AlpacaFeed=DEFAULT_FEED) -> dict[str, Any] | None`
- [fetch_historical_quotes](../../service/alpaca/clientAlpaca.py) — ligne 423 : `def fetch_historical_quotes(symbol: str, *, start: str, end: str, limit: int=10000, session: Optional[requests.Session]=None, account_id: Optional[str]=None, feed: AlpacaFeed=DEFAULT_FEED) -> list[dict[str, Any]]`
- [iter_historical_quotes_pages](../../service/alpaca/clientAlpaca.py) — ligne 450 : `def iter_historical_quotes_pages(symbol: str, *, start: str, end: str, limit: int=10000, session: Optional[requests.Session]=None, account_id: Optional[str]=None, feed: AlpacaFeed=DEFAULT_FEED) -> Iterator[dict[str, Any]]`

## `service/alpaca/clientNewsAlpaca.py`

Source SHA-256 : `8f93f8f2abdbde87ed1665bb11cb5a96644114cbb0a036ca6b433e1a9027e91a`

- [_build_headers](../../service/alpaca/clientNewsAlpaca.py) — ligne 19 : `def _build_headers(account_id: str | None=None) -> dict[str, str]`
- [_fmt_utc](../../service/alpaca/clientNewsAlpaca.py) — ligne 27 : `def _fmt_utc(value: datetime) -> str`
- [fetch_news_page](../../service/alpaca/clientNewsAlpaca.py) — ligne 33 : `def fetch_news_page(start_utc: datetime, end_utc: datetime, page_token: Optional[str]=None, symbols: Optional[list[str]]=None, limit: int=50, session: Optional[requests.Session]=None) -> tuple[list[dict[str, Any]], Optional[str]]`
- [iter_news_pages](../../service/alpaca/clientNewsAlpaca.py) — ligne 107 : `def iter_news_pages(start_utc: datetime, end_utc: datetime, symbols: Optional[list[str]]=None, limit: int=50, page_token: Optional[str]=None, session: Optional[requests.Session]=None) -> Iterator[tuple[list[dict[str, Any]], Optional[str]]]`

## `service/alpaca/reconciliation.py`

Source SHA-256 : `cb38741c90a87a85d795fcf0e0947dc5b31894131711214ad6841b1873fc768a`

- [StatementDiff](../../service/alpaca/reconciliation.py) — ligne 56 : `class StatementDiff`
- [StatementDiff.to_dict](../../service/alpaca/reconciliation.py) — ligne 67 : `def to_dict(self) -> dict[str, object]`
- [_read_csv_text](../../service/alpaca/reconciliation.py) — ligne 71 : `def _read_csv_text(csv_source: str | Path | io.TextIOBase) -> str`
- [_normalize_csv_key](../../service/alpaca/reconciliation.py) — ligne 82 : `def _normalize_csv_key(value: object) -> str`
- [_pick_csv_value](../../service/alpaca/reconciliation.py) — ligne 86 : `def _pick_csv_value(row: Mapping[str, Any], logical_key: str) -> Any`
- [parse_statement_csv](../../service/alpaca/reconciliation.py) — ligne 95 : `def parse_statement_csv(csv_source: str | Path | io.TextIOBase) -> list[dict[str, Any]]`
- [build_reconciliation_summary](../../service/alpaca/reconciliation.py) — ligne 125 : `def build_reconciliation_summary(*, account_id: str, trade_date: date, diffs: Iterable[StatementDiff], source_kind: str, activity_count: int, inserted: int, fetched_from_api: bool, statement_path: str | None=None) -> dict[str, Any]`
- [persist_statements](../../service/alpaca/reconciliation.py) — ligne 167 : `def persist_statements(engine: Engine, account_id: str, activities: Iterable[Mapping[str, Any]]) -> int`
- [_normalize](../../service/alpaca/reconciliation.py) — ligne 195 : `def _normalize(account_id: str, r: Mapping[str, Any]) -> dict[str, Any]`
- [reconcile](../../service/alpaca/reconciliation.py) — ligne 221 : `def reconcile(engine: Engine, *, account_id: str, trade_date: date) -> list[StatementDiff]`
- [_load_broker_fills](../../service/alpaca/reconciliation.py) — ligne 277 : `def _load_broker_fills(engine: Engine, account_id: str, trade_date: date) -> list[dict[str, Any]]`
- [_load_internal_fills](../../service/alpaca/reconciliation.py) — ligne 289 : `def _load_internal_fills(engine: Engine, account_id: str, trade_date: date) -> list[dict[str, Any]]`
- [_qty_match](../../service/alpaca/reconciliation.py) — ligne 303 : `def _qty_match(a: Any, b: Any) -> bool`
- [_price_match](../../service/alpaca/reconciliation.py) — ligne 309 : `def _price_match(a: Any, b: Any) -> bool`
- [_diff_missing_internal](../../service/alpaca/reconciliation.py) — ligne 318 : `def _diff_missing_internal(b: Mapping[str, Any]) -> StatementDiff`
- [_diff_missing_broker](../../service/alpaca/reconciliation.py) — ligne 332 : `def _diff_missing_broker(c: Mapping[str, Any]) -> StatementDiff`
- [_diff_qty](../../service/alpaca/reconciliation.py) — ligne 346 : `def _diff_qty(b: Mapping[str, Any], c: Mapping[str, Any]) -> StatementDiff`
- [_diff_price](../../service/alpaca/reconciliation.py) — ligne 360 : `def _diff_price(b: Mapping[str, Any], c: Mapping[str, Any]) -> StatementDiff`
- [_to_float](../../service/alpaca/reconciliation.py) — ligne 374 : `def _to_float(v: Any) -> float | None`
- [_iso](../../service/alpaca/reconciliation.py) — ligne 383 : `def _iso(v: Any) -> str | None`

## `service/alpaca/statements.py`

Source SHA-256 : `a9ac5d18d1cd483c7b21544dcd2ddb9ff5b0b3f96d390cb1458a9d70eebfdee3`

- [fetch_account_activities](../../service/alpaca/statements.py) — ligne 20 : `def fetch_account_activities(client: AlpacaTradingClient, *, since: date | datetime | None=None, until: date | datetime | None=None, activity_types: Iterable[str]=FILL_ACTIVITY_TYPES, page_size: int=100, max_pages: int=200) -> list[dict[str, Any]]`
- [_iso](../../service/alpaca/statements.py) — ligne 65 : `def _iso(d: date | datetime) -> str`
- [_decimal_to_float](../../service/alpaca/statements.py) — ligne 76 : `def _decimal_to_float(val: Any) -> float`
- [_compute_realized_pnl_fifo](../../service/alpaca/statements.py) — ligne 85 : `def _compute_realized_pnl_fifo(fills: list[dict[str, Any]]) -> float`
- [load_monthly_inputs_from_db](../../service/alpaca/statements.py) — ligne 120 : `def load_monthly_inputs_from_db(engine: Any, *, account_id: str, period_start: date, period_end: date, table: str='broker_statements')`
- [_to_datetime](../../service/alpaca/statements.py) — ligne 244 : `def _to_datetime(val: Any) -> datetime | None`
- [_compute_realized_pnl_fifo_period](../../service/alpaca/statements.py) — ligne 256 : `def _compute_realized_pnl_fifo_period(fills: list[dict[str, Any]], period_start: date, period_end: date) -> float`

## `service/alpaca/trading_client.py`

Source SHA-256 : `527ef6631994105a0bf4a43dfe51dd24bc290bd15c34fb501ae094e3b7c0d9d8`

- [BrokerApiError](../../service/alpaca/trading_client.py) — ligne 21 : `class BrokerApiError(Exception)`
- [BrokerApiError.__init__](../../service/alpaca/trading_client.py) — ligne 24 : `def __init__(self, status_code: int, message: str, body: str='') -> None`
- [AlpacaTradingClient](../../service/alpaca/trading_client.py) — ligne 30 : `class AlpacaTradingClient`
- [AlpacaTradingClient.__init__](../../service/alpaca/trading_client.py) — ligne 33 : `def __init__(self, broker_mode: str='paper', session: requests.Session | None=None, account_id: str | None=None) -> None`
- [AlpacaTradingClient._request](../../service/alpaca/trading_client.py) — ligne 55 : `def _request(self, method: str, path: str, **kwargs: object) -> dict | list`
- [AlpacaTradingClient.submit_order](../../service/alpaca/trading_client.py) — ligne 84 : `def submit_order(self, payload: dict[str, str]) -> dict`
- [AlpacaTradingClient.get_order](../../service/alpaca/trading_client.py) — ligne 87 : `def get_order(self, order_id: str) -> dict`
- [AlpacaTradingClient.list_orders](../../service/alpaca/trading_client.py) — ligne 90 : `def list_orders(self, status: str='all', limit: int=500, symbols: list[str] | None=None) -> list[dict]`
- [AlpacaTradingClient.cancel_order](../../service/alpaca/trading_client.py) — ligne 101 : `def cancel_order(self, order_id: str) -> bool`
- [AlpacaTradingClient.replace_order](../../service/alpaca/trading_client.py) — ligne 110 : `def replace_order(self, order_id: str, payload: dict[str, str]) -> dict`
- [AlpacaTradingClient.get_positions](../../service/alpaca/trading_client.py) — ligne 117 : `def get_positions(self) -> list[dict]`
- [AlpacaTradingClient.get_position](../../service/alpaca/trading_client.py) — ligne 120 : `def get_position(self, symbol: str) -> dict | None`
- [AlpacaTradingClient.close_position](../../service/alpaca/trading_client.py) — ligne 128 : `def close_position(self, symbol: str) -> dict`
- [AlpacaTradingClient.get_account](../../service/alpaca/trading_client.py) — ligne 135 : `def get_account(self) -> dict`
- [AlpacaTradingClient.get_asset](../../service/alpaca/trading_client.py) — ligne 138 : `def get_asset(self, symbol: str) -> dict`
- [AlpacaTradingClient.get_portfolio_history](../../service/alpaca/trading_client.py) — ligne 142 : `def get_portfolio_history(self, *, period: str='1M', timeframe: str='1D', intraday_reporting: str | None=None, pnl_reset: str | None=None, extended_hours: bool | None=None) -> dict`
- [AlpacaTradingClient.get_clock](../../service/alpaca/trading_client.py) — ligne 163 : `def get_clock(self) -> dict`
- [AlpacaTradingClient.is_market_open](../../service/alpaca/trading_client.py) — ligne 166 : `def is_market_open(self) -> bool`

## `service/baostock/__init__.py`

Source SHA-256 : `4a44ee4df2e82950bb53f55d37b20511fc863871ff088e80b34b30f7d1670e3c`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `service/baostock/adapters.py`

Source SHA-256 : `6a4913b22745d261307ed824d93b5644ea116e1a4c0d1895fac73e1d7ae7e5e9`

- [parse_baostock_date](../../service/baostock/adapters.py) — ligne 11 : `def parse_baostock_date(value: Any) -> date | None`
- [_decimal](../../service/baostock/adapters.py) — ligne 23 : `def _decimal(value: Any) -> Decimal | None`
- [adapt_staging_row](../../service/baostock/adapters.py) — ligne 32 : `def adapt_staging_row(endpoint: str, row: dict[str, Any], *, run_id: str, raw_id: int | None, observed_at: datetime, available_at: datetime) -> dict[str, Any]`

## `service/baostock/client.py`

Source SHA-256 : `6b1e045dde760323666c0ead6cddcfc51b3632aecb1ae6c72d0199529f83399a`

- [BaoStockError](../../service/baostock/client.py) — ligne 13 : `class BaoStockError(RuntimeError)`
- [BaoStockClient](../../service/baostock/client.py) — ligne 17 : `class BaoStockClient`
- [BaoStockClient.__init__](../../service/baostock/client.py) — ligne 20 : `def __init__(self, backend: ModuleType | Any | None=None, *, socket_timeout_seconds: float=30.0, max_attempts: int=3, retry_delay_seconds: float=2.0) -> None`
- [BaoStockClient._is_real_backend](../../service/baostock/client.py) — ligne 41 : `def _is_real_backend(self) -> bool`
- [BaoStockClient._default_socket](../../service/baostock/client.py) — ligne 44 : `def _default_socket(self) -> Any | None`
- [BaoStockClient._configure_socket_timeout](../../service/baostock/client.py) — ligne 53 : `def _configure_socket_timeout(self) -> None`
- [BaoStockClient._drop_connection](../../service/baostock/client.py) — ligne 58 : `def _drop_connection(self) -> None`
- [BaoStockClient.connect](../../service/baostock/client.py) — ligne 67 : `def connect(self) -> None`
- [BaoStockClient.close](../../service/baostock/client.py) — ligne 84 : `def close(self) -> None`
- [BaoStockClient.__enter__](../../service/baostock/client.py) — ligne 90 : `def __enter__(self) -> BaoStockClient`
- [BaoStockClient.__exit__](../../service/baostock/client.py) — ligne 94 : `def __exit__(self, *_args: object) -> None`
- [BaoStockClient._page](../../service/baostock/client.py) — ligne 97 : `def _page(self, endpoint: str, result: Any, request: dict[str, Any]) -> BaoStockPage`
- [BaoStockClient._request](../../service/baostock/client.py) — ligne 130 : `def _request(self, endpoint: str, request: dict[str, Any], operation: Callable[[], Any]) -> BaoStockPage`
- [BaoStockClient.stock_basic](../../service/baostock/client.py) — ligne 153 : `def stock_basic(self) -> BaoStockPage`
- [BaoStockClient.trade_calendar](../../service/baostock/client.py) — ligne 157 : `def trade_calendar(self, start_date: str, end_date: str) -> BaoStockPage`
- [BaoStockClient.daily](../../service/baostock/client.py) — ligne 165 : `def daily(self, symbol: str, start_date: str, end_date: str, *, index: bool=False) -> BaoStockPage`
- [BaoStockClient.adjustment_factors](../../service/baostock/client.py) — ligne 190 : `def adjustment_factors(self, symbol: str, start_date: str, end_date: str) -> BaoStockPage`
- [BaoStockClient.dividend_data](../../service/baostock/client.py) — ligne 207 : `def dividend_data(self, symbol: str, year: int) -> BaoStockPage`

## `service/baostock/ingestion.py`

Source SHA-256 : `2bb44dd10cc457867dcffb9309e32f76d9857aa6ff11c8ee16052d5db72a24c9`

- [historical_windows](../../service/baostock/ingestion.py) — ligne 20 : `def historical_windows(start: date, end: date, *, years: int=3) -> list[tuple[date, date]]`
- [BaoStockResumeState](../../service/baostock/ingestion.py) — ligne 36 : `class BaoStockResumeState`
- [BaoStockResumeState.__init__](../../service/baostock/ingestion.py) — ligne 37 : `def __init__(self, path: Path) -> None`
- [BaoStockResumeState.completed](../../service/baostock/ingestion.py) — ligne 43 : `def completed(self, key: str) -> bool`
- [BaoStockResumeState.mark_completed](../../service/baostock/ingestion.py) — ligne 46 : `def mark_completed(self, key: str) -> None`
- [BaoStockIngestionService](../../service/baostock/ingestion.py) — ligne 54 : `class BaoStockIngestionService`
- [BaoStockIngestionService.__init__](../../service/baostock/ingestion.py) — ligne 55 : `def __init__(self, *, client: BaoStockClient, engine: Engine, run_id: str, state_root: Path=DEFAULT_STATE_ROOT, state_key: str | None=None, max_symbols: int | None=None, symbols: list[str] | tuple[str, ...] | None=None) -> None`
- [BaoStockIngestionService._stock_master](../../service/baostock/ingestion.py) — ligne 74 : `def _stock_master(self) -> BaoStockPage`
- [BaoStockIngestionService.equity_symbols](../../service/baostock/ingestion.py) — ligne 79 : `def equity_symbols(self, *, include_inactive: bool) -> list[str]`
- [BaoStockIngestionService._persist](../../service/baostock/ingestion.py) — ligne 94 : `def _persist(self, page: BaoStockPage, page_key: str, *, dry_run: bool) -> tuple[int, int]`
- [BaoStockIngestionService.collect_endpoint](../../service/baostock/ingestion.py) — ligne 120 : `def collect_endpoint(self, endpoint: str, *, start_date: date | None, end_date: date | None, dry_run: bool=False, resume: bool=True, include_inactive: bool=False) -> IngestionCounters`

## `service/baostock/models.py`

Source SHA-256 : `40cdad691ab833709f9c86877379cd5083a02a16dc5c882588331a9741a58a90`

- [BaoStockPage](../../service/baostock/models.py) — ligne 8 : `class BaoStockPage`

## `service/baostock/symbols.py`

Source SHA-256 : `702020f4eb7628c7a078e0f6edf9819215b692146e56bedd7c96a097fe7f1256`

- [BaoStockSymbol](../../service/baostock/symbols.py) — ligne 10 : `class BaoStockSymbol`
- [_board](../../service/baostock/symbols.py) — ligne 18 : `def _board(code: str, exchange: str) -> str`
- [parse_baostock_symbol](../../service/baostock/symbols.py) — ligne 26 : `def parse_baostock_symbol(value: str) -> BaoStockSymbol`

## `service/broker_failover.py`

Source SHA-256 : `ea5b5b4da8c016849ba3b040eae49c581d2df0c8340de731a556296e19c680f3`

- [WriteSuspendedError](../../service/broker_failover.py) — ligne 34 : `class WriteSuspendedError(RuntimeError)`
- [FailoverBrokerClient](../../service/broker_failover.py) — ligne 38 : `class FailoverBrokerClient`
- [FailoverBrokerClient.__init__](../../service/broker_failover.py) — ligne 43 : `def __init__(self, primary: Any, secondary: Any, *, circuit_breaker_threshold: int=3, resume_flag_path: Path=DEFAULT_RESUME_FLAG, notifier: Any | None=None) -> None`
- [FailoverBrokerClient.tripped](../../service/broker_failover.py) — ligne 66 : `def tripped(self) -> bool`
- [FailoverBrokerClient._maybe_resume](../../service/broker_failover.py) — ligne 71 : `def _maybe_resume(self) -> None`
- [FailoverBrokerClient._trip](../../service/broker_failover.py) — ligne 82 : `def _trip(self) -> None`
- [FailoverBrokerClient._read](../../service/broker_failover.py) — ligne 100 : `def _read(self, op: Callable[[Any], Any]) -> Any`
- [FailoverBrokerClient._write_guard](../../service/broker_failover.py) — ligne 118 : `def _write_guard(self) -> None`
- [FailoverBrokerClient.get_account](../../service/broker_failover.py) — ligne 131 : `def get_account(self) -> AccountSnapshot`
- [FailoverBrokerClient.get_positions](../../service/broker_failover.py) — ligne 134 : `def get_positions(self) -> list[BrokerPosition]`
- [FailoverBrokerClient.get_orders](../../service/broker_failover.py) — ligne 137 : `def get_orders(self, status: str='all', since: datetime | None=None) -> list[BrokerOrderSnapshot]`
- [FailoverBrokerClient.submit_order](../../service/broker_failover.py) — ligne 140 : `def submit_order(self, request: OrderRequest) -> BrokerOrderSnapshot`
- [FailoverBrokerClient.cancel_order](../../service/broker_failover.py) — ligne 144 : `def cancel_order(self, order_id: str) -> bool`
- [FailoverBrokerClient.stream_trades](../../service/broker_failover.py) — ligne 148 : `def stream_trades(self, callback: Callable[[BrokerOrderSnapshot], None]) -> Any`
- [build_failover_doctrine_summary](../../service/broker_failover.py) — ligne 154 : `def build_failover_doctrine_summary(*, primary_broker: str='alpaca', secondary_broker: str='ibkr', circuit_breaker_threshold: int=3, resume_flag_path: Path=DEFAULT_RESUME_FLAG) -> dict[str, Any]`

## `service/cache/__init__.py`

Source SHA-256 : `348b89ac6baebd963e775a4ddcf17b800e032cd82185ff6e2c8c1ca5a74a9bb5`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `service/cache/factory.py`

Source SHA-256 : `1d1c8e590287daf43811bd9d3d002537a3203eb19bf2fafe110d028e27278dd4`

- [build_cache_from_env](../../service/cache/factory.py) — ligne 9 : `def build_cache_from_env(*, env_var: str='ALPHA_TRADE_CACHE_URL', namespace: str='alpha_trade', max_size: int=4096, default_ttl: float | None=300.0)`

## `service/cache/in_memory.py`

Source SHA-256 : `f3ee8ebc8ad9e9c2bc5e2ee1062f68f91c9921f570945316e8b43a4297b74464`

- [_Entry](../../service/cache/in_memory.py) — ligne 20 : `class _Entry`
- [InMemoryCache](../../service/cache/in_memory.py) — ligne 25 : `class InMemoryCache`
- [InMemoryCache.__init__](../../service/cache/in_memory.py) — ligne 39 : `def __init__(self, max_size: int=1024, default_ttl: float | None=None, *, clock=time.time) -> None`
- [InMemoryCache.get](../../service/cache/in_memory.py) — ligne 60 : `def get(self, key: str, default: Any=None) -> Any`
- [InMemoryCache.set](../../service/cache/in_memory.py) — ligne 76 : `def set(self, key: str, value: Any, ttl: float | None=...) -> None`
- [InMemoryCache.invalidate](../../service/cache/in_memory.py) — ligne 92 : `def invalidate(self, key: str) -> bool`
- [InMemoryCache.clear](../../service/cache/in_memory.py) — ligne 96 : `def clear(self) -> None`
- [InMemoryCache.__contains__](../../service/cache/in_memory.py) — ligne 100 : `def __contains__(self, key: str) -> bool`
- [InMemoryCache.__len__](../../service/cache/in_memory.py) — ligne 103 : `def __len__(self) -> int`
- [InMemoryCache.stats](../../service/cache/in_memory.py) — ligne 109 : `def stats(self) -> dict[str, int]`

## `service/cache/redis_cache.py`

Source SHA-256 : `6435da7a3539ace6d998dbcfdf7b8a387e39a444d8455d321828e02e4546ebeb`

- [RedisCache](../../service/cache/redis_cache.py) — ligne 13 : `class RedisCache`
- [RedisCache.__init__](../../service/cache/redis_cache.py) — ligne 21 : `def __init__(self, url: str, *, namespace: str='alpha_trade', default_ttl: float | None=None, serialize=json.dumps, deserialize=json.loads) -> None`
- [RedisCache._k](../../service/cache/redis_cache.py) — ligne 43 : `def _k(self, key: str) -> str`
- [RedisCache.get](../../service/cache/redis_cache.py) — ligne 46 : `def get(self, key: str, default: Any=None) -> Any`
- [RedisCache.set](../../service/cache/redis_cache.py) — ligne 55 : `def set(self, key: str, value: Any, ttl: float | None=...) -> None`
- [RedisCache.invalidate](../../service/cache/redis_cache.py) — ligne 64 : `def invalidate(self, key: str) -> bool`
- [RedisCache.clear](../../service/cache/redis_cache.py) — ligne 67 : `def clear(self) -> None`

## `service/eodhd/__init__.py`

Source SHA-256 : `399250de1d65e71bad52f2eefa18992cb9109fd740c685b484d1652c58c9ba7a`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `service/eodhd/accounts.py`

Source SHA-256 : `27c15df7aecd439cf1c9838a514a109126b959a1753152849ae366f67c4f8644`

- [EodhdAuthError](../../service/eodhd/accounts.py) — ligne 25 : `class EodhdAuthError(RuntimeError)`
- [EodhdAccount](../../service/eodhd/accounts.py) — ligne 30 : `class EodhdAccount`
- [EodhdAccount.__post_init__](../../service/eodhd/accounts.py) — ligne 37 : `def __post_init__(self) -> None`
- [EodhdAccountRegistry](../../service/eodhd/accounts.py) — ligne 42 : `class EodhdAccountRegistry`
- [EodhdAccountRegistry.__init__](../../service/eodhd/accounts.py) — ligne 48 : `def __init__(self) -> None`
- [EodhdAccountRegistry.get](../../service/eodhd/accounts.py) — ligne 53 : `def get(cls) -> 'EodhdAccountRegistry'`
- [EodhdAccountRegistry.reset](../../service/eodhd/accounts.py) — ligne 59 : `def reset(cls) -> None`
- [EodhdAccountRegistry.resolve](../../service/eodhd/accounts.py) — ligne 66 : `def resolve(self) -> EodhdAccount`
- [EodhdAccountRegistry.get_token](../../service/eodhd/accounts.py) — ligne 74 : `def get_token(self) -> str`
- [EodhdAccountRegistry._load](../../service/eodhd/accounts.py) — ligne 78 : `def _load(self) -> None`
- [EodhdAccountRegistry._read_yaml](../../service/eodhd/accounts.py) — ligne 104 : `def _read_yaml(self) -> dict[str, Any]`
- [get_eodhd_token](../../service/eodhd/accounts.py) — ligne 118 : `def get_eodhd_token() -> str`

## `service/eodhd/adapters.py`

Source SHA-256 : `749674ad6a5e63522ff996e2f96cbae390d59ec015cf091859f9e09b970c4104`

- [parse_split_ratio](../../service/eodhd/adapters.py) — ligne 48 : `def parse_split_ratio(value: Any) -> float`
- [cumulative_split_factor](../../service/eodhd/adapters.py) — ligne 82 : `def cumulative_split_factor(splits: Iterable[dict], target_date: str) -> float`
- [infer_splits_from_adjusted_close](../../service/eodhd/adapters.py) — ligne 107 : `def infer_splits_from_adjusted_close(eod_history: list[dict], *, threshold: float=0.05) -> list[dict]`
- [eodhd_to_split_only](../../service/eodhd/adapters.py) — ligne 153 : `def eodhd_to_split_only(raw_bars: list[dict], splits: list[dict]) -> list[dict]`
- [_date_to_rth_open_string](../../service/eodhd/adapters.py) — ligne 202 : `def _date_to_rth_open_string(date_iso: str) -> str`
- [_date_to_close_timestamp](../../service/eodhd/adapters.py) — ligne 215 : `def _date_to_close_timestamp(date_iso: str) -> datetime`
- [_typical_price_proxy](../../service/eodhd/adapters.py) — ligne 226 : `def _typical_price_proxy(high: float, low: float, close: float) -> float`
- [to_stock_bars_daily_row](../../service/eodhd/adapters.py) — ligne 231 : `def to_stock_bars_daily_row(bar: dict, symbol: str) -> dict`
- [to_stock_bars_row](../../service/eodhd/adapters.py) — ligne 267 : `def to_stock_bars_row(bar: dict, symbol: str, timeframe: str='1D') -> dict`

## `service/eodhd/cache.py`

Source SHA-256 : `6c5383fc954c34743ec5d4567c17f3a3341cbff64bd5195c49676d9fdea9cd39`

- [CacheEntry](../../service/eodhd/cache.py) — ligne 28 : `class CacheEntry`
- [CacheEntry.age_seconds](../../service/eodhd/cache.py) — ligne 33 : `def age_seconds(self) -> float`
- [CacheEntry.is_fresh](../../service/eodhd/cache.py) — ligne 36 : `def is_fresh(self, ttl_seconds: float) -> bool`
- [EodhdDiskCache](../../service/eodhd/cache.py) — ligne 40 : `class EodhdDiskCache`
- [EodhdDiskCache.__init__](../../service/eodhd/cache.py) — ligne 43 : `def __init__(self, root: Optional[Path]=None) -> None`
- [EodhdDiskCache._safe_key](../../service/eodhd/cache.py) — ligne 48 : `def _safe_key(key: str) -> str`
- [EodhdDiskCache._path](../../service/eodhd/cache.py) — ligne 54 : `def _path(self, namespace: str, key: str) -> Path`
- [EodhdDiskCache.get](../../service/eodhd/cache.py) — ligne 58 : `def get(self, namespace: str, key: str, *, ttl_seconds: float) -> Optional[Any]`
- [EodhdDiskCache.set](../../service/eodhd/cache.py) — ligne 72 : `def set(self, namespace: str, key: str, payload: Any) -> None`
- [EodhdDiskCache.get_or_fetch](../../service/eodhd/cache.py) — ligne 83 : `def get_or_fetch(self, namespace: str, key: str, loader: Callable[[], Any], *, ttl_seconds: float) -> Any`
- [EodhdDiskCache.invalidate](../../service/eodhd/cache.py) — ligne 99 : `def invalidate(self, namespace: Optional[str]=None) -> int`

## `service/eodhd/clientEodhd.py`

Source SHA-256 : `68e270fd8430fbbcea8f4c2cd0645099021dc97ee87c7025bd2329a9af592350`

- [EodhdBarsFetchError](../../service/eodhd/clientEodhd.py) — ligne 42 : `class EodhdBarsFetchError(RuntimeError)`
- [EodhdPermissionError](../../service/eodhd/clientEodhd.py) — ligne 46 : `class EodhdPermissionError(EodhdBarsFetchError)`
- [EodhdSymbolNotFound](../../service/eodhd/clientEodhd.py) — ligne 50 : `class EodhdSymbolNotFound(EodhdBarsFetchError)`
- [EodhdTemporarilyUnavailable](../../service/eodhd/clientEodhd.py) — ligne 54 : `class EodhdTemporarilyUnavailable(EodhdBarsFetchError)`
- [_redact_sensitive_text](../../service/eodhd/clientEodhd.py) — ligne 58 : `def _redact_sensitive_text(text: str) -> str`
- [_retry_policy](../../service/eodhd/clientEodhd.py) — ligne 62 : `def _retry_policy() -> RetryPolicy`
- [_get_token](../../service/eodhd/clientEodhd.py) — ligne 71 : `def _get_token() -> str`
- [_get_base_url](../../service/eodhd/clientEodhd.py) — ligne 78 : `def _get_base_url() -> str`
- [_build_session](../../service/eodhd/clientEodhd.py) — ligne 85 : `def _build_session(session: Optional[requests.Session]) -> requests.Session`
- [_do_request](../../service/eodhd/clientEodhd.py) — ligne 89 : `def _do_request(*, endpoint: str, url: str, params: dict[str, Any], session: Optional[requests.Session], tracker: EodhdQuotaTracker, feature: str | None=None) -> Any`
- [fetch_eod_bulk](../../service/eodhd/clientEodhd.py) — ligne 159 : `def fetch_eod_bulk(*, date: Optional[str]=None, exchange: str='US', symbols: Optional[Sequence[str]]=None, fmt: str='json', session: Optional[requests.Session]=None, tracker: Optional[EodhdQuotaTracker]=None, feature: str | None=None) -> list[dict]`
- [fetch_eod](../../service/eodhd/clientEodhd.py) — ligne 197 : `def fetch_eod(symbol: str, *, start: Optional[str]=None, end: Optional[str]=None, period: PeriodLiteral='d', fmt: str='json', session: Optional[requests.Session]=None, tracker: Optional[EodhdQuotaTracker]=None, feature: str | None=None) -> list[dict]`
- [fetch_splits](../../service/eodhd/clientEodhd.py) — ligne 236 : `def fetch_splits(symbol: str, *, start: Optional[str]=None, end: Optional[str]=None, fmt: str='json', session: Optional[requests.Session]=None, tracker: Optional[EodhdQuotaTracker]=None, feature: str | None=None) -> list[dict]`
- [fetch_dividends](../../service/eodhd/clientEodhd.py) — ligne 273 : `def fetch_dividends(symbol: str, *, start: Optional[str]=None, end: Optional[str]=None, fmt: str='json', session: Optional[requests.Session]=None, tracker: Optional[EodhdQuotaTracker]=None, feature: str | None=None) -> list[dict]`
- [fetch_fundamentals](../../service/eodhd/clientEodhd.py) — ligne 310 : `def fetch_fundamentals(symbol: str, *, fmt: str='json', session: Optional[requests.Session]=None, tracker: Optional[EodhdQuotaTracker]=None, feature: str | None=None) -> dict[str, Any]`
- [fetch_symbol_fundamentals_record](../../service/eodhd/clientEodhd.py) — ligne 343 : `def fetch_symbol_fundamentals_record(symbol: str, session: Optional[requests.Session]=None) -> dict[str, Any]`

## `service/eodhd/news_client.py`

Source SHA-256 : `da28b577e6d2f132cd99a218adb43e1f6340025dcf985ac21233891f0454be6d`

- [EodhdNewsFetchError](../../service/eodhd/news_client.py) — ligne 63 : `class EodhdNewsFetchError(RuntimeError)`
- [_to_utc](../../service/eodhd/news_client.py) — ligne 67 : `def _to_utc(value: datetime) -> datetime`
- [_fmt_date](../../service/eodhd/news_client.py) — ligne 73 : `def _fmt_date(value: datetime) -> str`
- [_retry_policy](../../service/eodhd/news_client.py) — ligne 77 : `def _retry_policy() -> RetryPolicy`
- [_get_token](../../service/eodhd/news_client.py) — ligne 86 : `def _get_token() -> str`
- [_get_base_url](../../service/eodhd/news_client.py) — ligne 93 : `def _get_base_url() -> str`
- [_stable_article_id](../../service/eodhd/news_client.py) — ligne 100 : `def _stable_article_id(symbol: str, raw: dict[str, Any]) -> str`
- [_to_project_symbol](../../service/eodhd/news_client.py) — ligne 112 : `def _to_project_symbol(symbol: str) -> str`
- [_normalize_symbol_list](../../service/eodhd/news_client.py) — ligne 123 : `def _normalize_symbol_list(symbol_query: str, raw_symbols: Any) -> list[str]`
- [_normalize_payload](../../service/eodhd/news_client.py) — ligne 161 : `def _normalize_payload(symbol: str, raw: dict[str, Any]) -> dict[str, Any]`
- [_parse_published_ts](../../service/eodhd/news_client.py) — ligne 190 : `def _parse_published_ts(raw_date: Any) -> datetime | None`
- [fetch_news_page](../../service/eodhd/news_client.py) — ligne 202 : `def fetch_news_page(start_utc: datetime, end_utc: datetime, symbols: Optional[list[str]]=None, limit: int=50, offset: int=0, session: Optional[requests.Session]=None) -> tuple[list[dict[str, Any]], Optional[str]]`
- [iter_news_pages](../../service/eodhd/news_client.py) — ligne 311 : `def iter_news_pages(start_utc: datetime, end_utc: datetime, symbols: Optional[list[str]]=None, limit: int=50, page_token: Optional[str]=None, session: Optional[requests.Session]=None) -> Iterator[tuple[list[dict[str, Any]], Optional[str]]]`

## `service/eodhd/quota.py`

Source SHA-256 : `f61e9e836aab90c0a838aaa57375bc06de5ab821d587e8dd0dd932dabafe48ba`

- [EodhdQuotaExceeded](../../service/eodhd/quota.py) — ligne 39 : `class EodhdQuotaExceeded(RuntimeError)`
- [EodhdCircuitOpen](../../service/eodhd/quota.py) — ligne 43 : `class EodhdCircuitOpen(RuntimeError)`
- [QuotaState](../../service/eodhd/quota.py) — ligne 48 : `class QuotaState`
- [EodhdQuotaTracker](../../service/eodhd/quota.py) — ligne 58 : `class EodhdQuotaTracker`
- [EodhdQuotaTracker.__post_init__](../../service/eodhd/quota.py) — ligne 70 : `def __post_init__(self) -> None`
- [EodhdQuotaTracker._today](../../service/eodhd/quota.py) — ligne 75 : `def _today(self) -> str`
- [EodhdQuotaTracker._reset_if_new_day](../../service/eodhd/quota.py) — ligne 78 : `def _reset_if_new_day(self) -> None`
- [EodhdQuotaTracker._path](../../service/eodhd/quota.py) — ligne 84 : `def _path(self) -> Optional[Path]`
- [EodhdQuotaTracker._load](../../service/eodhd/quota.py) — ligne 90 : `def _load(self) -> None`
- [EodhdQuotaTracker._save](../../service/eodhd/quota.py) — ligne 110 : `def _save(self) -> None`
- [EodhdQuotaTracker.cost_for](../../service/eodhd/quota.py) — ligne 136 : `def cost_for(self, endpoint: str) -> int`
- [EodhdQuotaTracker._normalize_feature](../../service/eodhd/quota.py) — ligne 140 : `def _normalize_feature(feature: str | None, *, endpoint: str) -> str`
- [EodhdQuotaTracker.remaining_calls](../../service/eodhd/quota.py) — ligne 144 : `def remaining_calls(self) -> int`
- [EodhdQuotaTracker.build_capacity_precheck](../../service/eodhd/quota.py) — ligne 149 : `def build_capacity_precheck(self, *, estimated_cost: int, feature: str | None=None) -> dict[str, int | bool | str | dict[str, int]]`
- [EodhdQuotaTracker.ensure_capacity](../../service/eodhd/quota.py) — ligne 166 : `def ensure_capacity(self, *, estimated_cost: int, feature: str | None=None) -> dict[str, int | bool | str | dict[str, int]]`
- [EodhdQuotaTracker._format_remaining_duration](../../service/eodhd/quota.py) — ligne 182 : `def _format_remaining_duration(seconds: float) -> str`
- [EodhdQuotaTracker._format_circuit_open_until](../../service/eodhd/quota.py) — ligne 195 : `def _format_circuit_open_until(cls, epoch: float, *, now_epoch: float | None=None) -> str`
- [EodhdQuotaTracker.reserve](../../service/eodhd/quota.py) — ligne 203 : `def reserve(self, endpoint: str) -> int`
- [EodhdQuotaTracker.record_success](../../service/eodhd/quota.py) — ligne 226 : `def record_success(self, endpoint: str, *, feature: str | None=None) -> None`
- [EodhdQuotaTracker.record_failure](../../service/eodhd/quota.py) — ligne 248 : `def record_failure(self, endpoint: str, *, feature: str | None=None, count_call: bool=True, count_towards_circuit: bool=True) -> None`
- [EodhdQuotaTracker.is_circuit_open](../../service/eodhd/quota.py) — ligne 286 : `def is_circuit_open(self) -> bool`
- [EodhdQuotaTracker.snapshot](../../service/eodhd/quota.py) — ligne 292 : `def snapshot(self) -> dict[str, int | bool | dict[str, int]]`
- [get_default_tracker](../../service/eodhd/quota.py) — ligne 314 : `def get_default_tracker(cache_dir: Optional[Path]=None) -> EodhdQuotaTracker`
- [reset_default_tracker](../../service/eodhd/quota.py) — ligne 323 : `def reset_default_tracker() -> None`

## `service/eodhd/symbols.py`

Source SHA-256 : `77c046a0d84647e5c709302977c05f4e4b8fa171cb20fad37e178b4ca170c96d`

- [_load_exceptions](../../service/eodhd/symbols.py) — ligne 36 : `def _load_exceptions() -> dict[str, str]`
- [reset_exceptions_cache](../../service/eodhd/symbols.py) — ligne 48 : `def reset_exceptions_cache() -> None`
- [to_eodhd](../../service/eodhd/symbols.py) — ligne 53 : `def to_eodhd(symbol: str, exchange: str=DEFAULT_EXCHANGE) -> str`
- [from_eodhd](../../service/eodhd/symbols.py) — ligne 90 : `def from_eodhd(eodhd_symbol: str) -> tuple[str, str]`
- [is_supported](../../service/eodhd/symbols.py) — ligne 109 : `def is_supported(symbol: str) -> bool`
- [add_exception](../../service/eodhd/symbols.py) — ligne 121 : `def add_exception(project_symbol: str, eodhd_symbol: Optional[str]) -> None`
- [_resolve_with_runtime](../../service/eodhd/symbols.py) — ligne 138 : `def _resolve_with_runtime(symbol: str) -> Optional[str]`

## `service/finnhub/clientFinnhub.py`

Source SHA-256 : `1517ac0bf14bbab35954892c7a290db124ed62a3381aa64aa59177001805bab7`

- [get_finnhub_token](../../service/finnhub/clientFinnhub.py) — ligne 38 : `def get_finnhub_token() -> str`
- [_normalize_symbol](../../service/finnhub/clientFinnhub.py) — ligne 48 : `def _normalize_symbol(symbol: str) -> str`
- [_build_params](../../service/finnhub/clientFinnhub.py) — ligne 55 : `def _build_params(symbol: str) -> dict[str, str]`
- [_request_json](../../service/finnhub/clientFinnhub.py) — ligne 62 : `def _request_json(endpoint: str, params: dict[str, str], session: Optional[requests.Session]=None) -> dict[str, Any]`
- [fetch_company_profile](../../service/finnhub/clientFinnhub.py) — ligne 103 : `def fetch_company_profile(symbol: str, session: Optional[requests.Session]=None, *, use_cache: bool=True, cache_ttl_days: int=DEFAULT_CACHE_TTL_DAYS) -> dict[str, Any]`
- [fetch_symbol_sector](../../service/finnhub/clientFinnhub.py) — ligne 139 : `def fetch_symbol_sector(symbol: str, session: Optional[requests.Session]=None) -> Optional[str]`
- [fetch_symbol_sector_record](../../service/finnhub/clientFinnhub.py) — ligne 149 : `def fetch_symbol_sector_record(symbol: str, session: Optional[requests.Session]=None) -> dict[str, Any]`
- [fetch_symbol_fundamentals_record](../../service/finnhub/clientFinnhub.py) — ligne 162 : `def fetch_symbol_fundamentals_record(symbol: str, session: Optional[requests.Session]=None) -> dict[str, Any]`
- [fetch_multiple_symbol_sector_records](../../service/finnhub/clientFinnhub.py) — ligne 178 : `def fetch_multiple_symbol_sector_records(symbols: Iterable[str], sleep_seconds: float=MIN_REQUEST_INTERVAL_SECONDS, session: Optional[requests.Session]=None) -> list[dict[str, Any]]`
- [fetch_earnings_calendar](../../service/finnhub/clientFinnhub.py) — ligne 208 : `def fetch_earnings_calendar(symbol: str, from_date: str, to_date: str, session: Optional[requests.Session]=None) -> list[dict[str, Any]]`
- [fetch_multiple_symbols_earnings_calendar](../../service/finnhub/clientFinnhub.py) — ligne 232 : `def fetch_multiple_symbols_earnings_calendar(symbols: Iterable[str], from_date: str, to_date: str, sleep_seconds: float=MIN_REQUEST_INTERVAL_SECONDS, session: Optional[requests.Session]=None, log_every: int=25) -> list[dict[str, Any]]`

## `service/finnhub/news_client.py`

Source SHA-256 : `fcdc2a2a35f78a870d2c716d5d0cd3a2b8e595933d83f2c8f154dbed83aa3ac6`

- [_to_utc](../../service/finnhub/news_client.py) — ligne 55 : `def _to_utc(value: datetime) -> datetime`
- [_fmt_date](../../service/finnhub/news_client.py) — ligne 61 : `def _fmt_date(value: datetime) -> str`
- [_throttle_company_news_requests](../../service/finnhub/news_client.py) — ligne 65 : `def _throttle_company_news_requests() -> float`
- [_reset_company_news_rate_limit_state](../../service/finnhub/news_client.py) — ligne 90 : `def _reset_company_news_rate_limit_state() -> None`
- [_stable_article_id](../../service/finnhub/news_client.py) — ligne 97 : `def _stable_article_id(symbol: str, raw: dict[str, Any]) -> str`
- [_normalize_payload](../../service/finnhub/news_client.py) — ligne 109 : `def _normalize_payload(symbol: str, raw: dict[str, Any]) -> dict[str, Any]`
- [fetch_news_page](../../service/finnhub/news_client.py) — ligne 155 : `def fetch_news_page(start_utc: datetime, end_utc: datetime, symbols: Optional[list[str]]=None, limit: int=50, session: Optional[requests.Session]=None) -> tuple[list[dict[str, Any]], None]`
- [iter_news_pages](../../service/finnhub/news_client.py) — ligne 264 : `def iter_news_pages(start_utc: datetime, end_utc: datetime, symbols: Optional[list[str]]=None, limit: int=50, page_token: Optional[str]=None, session: Optional[requests.Session]=None) -> Iterator[tuple[list[dict[str, Any]], Optional[str]]]`

## `service/fmp/__init__.py`

Source SHA-256 : `576006c9444f69f75bd995569a8e151b3d665181a247daf00a0a48fac149e6d3`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `service/fmp/clientFmp.py`

Source SHA-256 : `dee99e7d1b6396e692a813f04f89ea0207189b0256725128e4f0fa1f15389c26`

- [FmpError](../../service/fmp/clientFmp.py) — ligne 29 : `class FmpError(RuntimeError)`
- [FmpRateLimitError](../../service/fmp/clientFmp.py) — ligne 33 : `class FmpRateLimitError(FmpError)`
- [FmpSymbolNotFound](../../service/fmp/clientFmp.py) — ligne 37 : `class FmpSymbolNotFound(FmpError)`
- [_get_session](../../service/fmp/clientFmp.py) — ligne 41 : `def _get_session() -> requests.Session`
- [_rate_limit](../../service/fmp/clientFmp.py) — ligne 52 : `def _rate_limit() -> None`
- [_get_api_key](../../service/fmp/clientFmp.py) — ligne 61 : `def _get_api_key() -> str`
- [_do_get](../../service/fmp/clientFmp.py) — ligne 71 : `def _do_get(endpoint: str, params: dict[str, Any] | None=None) -> Any`
- [fetch_profile](../../service/fmp/clientFmp.py) — ligne 104 : `def fetch_profile(symbol: str) -> dict[str, Any] | None`
- [fetch_ratios](../../service/fmp/clientFmp.py) — ligne 118 : `def fetch_ratios(symbol: str) -> dict[str, Any] | None`
- [fetch_key_metrics](../../service/fmp/clientFmp.py) — ligne 132 : `def fetch_key_metrics(symbol: str) -> dict[str, Any] | None`
- [fetch_financial_growth](../../service/fmp/clientFmp.py) — ligne 146 : `def fetch_financial_growth(symbol: str) -> dict[str, Any] | None`
- [fetch_symbol_fundamentals_record](../../service/fmp/clientFmp.py) — ligne 160 : `def fetch_symbol_fundamentals_record(symbol: str, session: Any=None) -> dict[str, Any]`

## `service/forward_pit/__init__.py`

Source SHA-256 : `caf4f1fcf34be0cf11cb9daa73cf2844c3e021895758c367edbeb2b227ac767f`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `service/forward_pit/__main__.py`

Source SHA-256 : `e6a957a331f05d3f9085173ed7692c27091f49c32233e07cac606faba332a136`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `service/forward_pit/batch.py`

Source SHA-256 : `621f703dccfa48b2306069600130b187e68d908d107bb3c3ef4ca38b2f7be7ce`

- [Outcome](../../service/forward_pit/batch.py) — ligne 69 : `class Outcome`
- [BatchRunError](../../service/forward_pit/batch.py) — ligne 80 : `class BatchRunError(RuntimeError)`
- [BatchRunError.__init__](../../service/forward_pit/batch.py) — ligne 83 : `def __init__(self, message: str, outcome: Outcome)`
- [_json](../../service/forward_pit/batch.py) — ligne 88 : `def _json(value: Any) -> str`
- [_hash](../../service/forward_pit/batch.py) — ligne 92 : `def _hash(value: Any) -> str`
- [_schema_hash](../../service/forward_pit/batch.py) — ligne 96 : `def _schema_hash(value: Any) -> str`
- [_utcnow](../../service/forward_pit/batch.py) — ligne 106 : `def _utcnow() -> datetime`
- [_previous_weekdays](../../service/forward_pit/batch.py) — ligne 110 : `def _previous_weekdays(reference_date: date, lookback_days: int) -> list[date]`
- [_read_sec_response_limited](../../service/forward_pit/batch.py) — ligne 127 : `def _read_sec_response_limited(response: requests.Response, *, max_content_bytes: int, probe_bytes: int) -> tuple[str | None, str, int]`
- [_sec_submission_header](../../service/forward_pit/batch.py) — ligne 161 : `def _sec_submission_header(submission_prefix: str, expected_form: str) -> tuple[datetime | None, str | None]`
- [_sec_filing_index_documents](../../service/forward_pit/batch.py) — ligne 191 : `def _sec_filing_index_documents(index_html: str, base_url: str) -> list[dict[str, Any]]`
- [_read_response_bytes_limited](../../service/forward_pit/batch.py) — ligne 229 : `def _read_response_bytes_limited(response: requests.Response, max_content_bytes: int) -> tuple[bytes | None, int]`
- [_sec_exhibit_prefixes](../../service/forward_pit/batch.py) — ligne 246 : `def _sec_exhibit_prefixes(value: Any) -> tuple[str, ...]`
- [_selected_sec_exhibits](../../service/forward_pit/batch.py) — ligne 252 : `def _selected_sec_exhibits(documents: list[dict[str, Any]], prefixes: tuple[str, ...], limit: int) -> list[dict[str, Any]]`
- [_sec_filing_index_url](../../service/forward_pit/batch.py) — ligne 269 : `def _sec_filing_index_url(submission_url: str, accession_number: str) -> str`
- [_download_sec_exhibits](../../service/forward_pit/batch.py) — ligne 274 : `def _download_sec_exhibits(engine: Engine, session: requests.Session, *, accession_number: str, submission_url: str, headers: dict[str, str], observed: datetime, run_id: str, prefixes: tuple[str, ...], max_exhibits: int, max_exhibit_bytes: int, max_requests_per_second: int) -> dict[str, Any]`
- [_download_sec_document](../../service/forward_pit/batch.py) — ligne 384 : `def _download_sec_document(session: requests.Session, submission_url: str, form_type: str, headers: dict[str, str], *, max_submission_bytes: int, max_primary_document_bytes: int, probe_bytes: int) -> dict[str, Any]`
- [_dt](../../service/forward_pit/batch.py) — ligne 449 : `def _dt(value: Any) -> datetime | None`
- [_market_dt](../../service/forward_pit/batch.py) — ligne 458 : `def _market_dt(value: Any, timezone_name: str='America/New_York') -> tuple[datetime, datetime]`
- [_chunks](../../service/forward_pit/batch.py) — ligne 466 : `def _chunks(values: list[str], size: int) -> Iterable[list[str]]`
- [_symbols](../../service/forward_pit/batch.py) — ligne 471 : `def _symbols(cfg: dict[str, Any]) -> list[str]`
- [_collection_symbols](../../service/forward_pit/batch.py) — ligne 482 : `def _collection_symbols(cfg: dict[str, Any]) -> list[str]`
- [_assets_in_universe](../../service/forward_pit/batch.py) — ligne 494 : `def _assets_in_universe(assets: Iterable[dict[str, Any]], symbols: Iterable[str]) -> list[dict[str, Any]]`
- [_secret](../../service/forward_pit/batch.py) — ligne 513 : `def _secret(cfg: dict[str, Any], default_env: str) -> str`
- [_safe_error_message](../../service/forward_pit/batch.py) — ligne 521 : `def _safe_error_message(error: Exception) -> str`
- [_request_json](../../service/forward_pit/batch.py) — ligne 530 : `def _request_json(session: requests.Session, url: str, *, params: dict[str, Any], headers: dict[str, str] | None=None, timeout: float=45, attempts: int=4) -> tuple[Any, int]`
- [_paginated_json](../../service/forward_pit/batch.py) — ligne 546 : `def _paginated_json(session: requests.Session, url: str, *, params: dict[str, Any], headers: dict[str, str], page_key: str, max_pages: int, pause_seconds: float=0.0) -> list[tuple[dict[str, Any], int]]`
- [_option_contract_parts](../../service/forward_pit/batch.py) — ligne 579 : `def _option_contract_parts(contract_symbol: str) -> tuple[date | None, float | None, str | None]`
- [_nearest_option_expirations](../../service/forward_pit/batch.py) — ligne 591 : `def _nearest_option_expirations(contracts: Iterable[str], target_dtes: Iterable[int], as_of: date) -> set[date]`
- [_select_option_surface_contracts](../../service/forward_pit/batch.py) — ligne 605 : `def _select_option_surface_contracts(snapshots: dict[str, dict[str, Any]], *, expirations: set[date], spot: float, moneyness_targets: Iterable[float]) -> set[str]`
- [_underlying_price](../../service/forward_pit/batch.py) — ligne 629 : `def _underlying_price(snapshot: dict[str, Any]) -> float | None`
- [_option_is_liquid](../../service/forward_pit/batch.py) — ligne 646 : `def _option_is_liquid(item: dict[str, Any], *, min_bid: float, max_relative_spread: float, require_two_sided_quote: bool) -> bool`
- [_SystemTrustAdapter](../../service/forward_pit/batch.py) — ligne 664 : `class _SystemTrustAdapter(HTTPAdapter)`
- [_SystemTrustAdapter.init_poolmanager](../../service/forward_pit/batch.py) — ligne 667 : `def init_poolmanager(self, *args: Any, **kwargs: Any) -> None`
- [_configure_alpaca_session](../../service/forward_pit/batch.py) — ligne 672 : `def _configure_alpaca_session(session: requests.Session, *, use_system_trust_store: bool) -> None`
- [market_datetime](../../service/forward_pit/batch.py) — ligne 679 : `def market_datetime(value: Any, timezone_name: str='America/New_York') -> tuple[datetime, datetime]`
- [paginated_json](../../service/forward_pit/batch.py) — ligne 684 : `def paginated_json(session: requests.Session, url: str, *, params: dict[str, Any], headers: dict[str, str], page_key: str, max_pages: int, pause_seconds: float=0.0) -> list[tuple[dict[str, Any], int]]`
- [configure_alpaca_session](../../service/forward_pit/batch.py) — ligne 706 : `def configure_alpaca_session(session: requests.Session, *, use_system_trust_store: bool) -> None`
- [_request_text_optional](../../service/forward_pit/batch.py) — ligne 716 : `def _request_text_optional(session: requests.Session, url: str, *, timeout: float=45, attempts: int=4) -> tuple[str | None, int]`
- [_parse_finra_short_volume](../../service/forward_pit/batch.py) — ligne 737 : `def _parse_finra_short_volume(content: str) -> list[dict[str, Any]]`
- [_raw](../../service/forward_pit/batch.py) — ligne 764 : `def _raw(conn: Connection, run_id: str, batch: str, provider: str, endpoint: str, entity: str, payload: Any, status: int=200, observed: datetime | None=None) -> None`
- [_data_blocks](../../service/forward_pit/batch.py) — ligne 773 : `def _data_blocks(payload: Any) -> Iterable[tuple[str, list[dict[str, Any]], dict[str, Any]]]`
- [_security_changes](../../service/forward_pit/batch.py) — ligne 789 : `def _security_changes(previous: dict[str, dict[str, Any]], current: dict[str, dict[str, Any]]) -> list[dict[str, Any]]`
- [market_cap_sync](../../service/forward_pit/batch.py) — ligne 811 : `def market_cap_sync(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome`
- [_apply_market_cap_coverage_policy](../../service/forward_pit/batch.py) — ligne 928 : `def _apply_market_cap_coverage_policy(outcome: Outcome, uncovered: list[str], coverage_ratio: float, min_coverage_ratio: float) -> None`
- [_market_cap_covered_symbols](../../service/forward_pit/batch.py) — ligne 946 : `def _market_cap_covered_symbols(engine: Engine, symbols: Iterable[str], as_of: date, max_age_days: int, sources: tuple[str, ...]) -> set[str]`
- [daily_bars_sync](../../service/forward_pit/batch.py) — ligne 981 : `def daily_bars_sync(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome`
- [_nasdaq_rows](../../service/forward_pit/batch.py) — ligne 1029 : `def _nasdaq_rows(session: requests.Session) -> list[dict[str, Any]]`
- [security_master_snapshot](../../service/forward_pit/batch.py) — ligne 1042 : `def security_master_snapshot(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome`
- [corporate_actions_sync](../../service/forward_pit/batch.py) — ligne 1111 : `def corporate_actions_sync(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome`
- [sec_edgar_incremental](../../service/forward_pit/batch.py) — ligne 1146 : `def sec_edgar_incremental(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome`
- [borrow_status_snapshot](../../service/forward_pit/batch.py) — ligne 1323 : `def borrow_status_snapshot(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome`
- [finra_short_volume_sync](../../service/forward_pit/batch.py) — ligne 1351 : `def finra_short_volume_sync(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome`
- [business_quant_analyst_snapshot](../../service/forward_pit/batch.py) — ligne 1422 : `def business_quant_analyst_snapshot(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome`
- [options_snapshot](../../service/forward_pit/batch.py) — ligne 1447 : `def options_snapshot(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome`
- [_alpaca_opening_row](../../service/forward_pit/batch.py) — ligne 1703 : `def _alpaca_opening_row(symbol: str, item: dict[str, Any], *, observed: datetime, cumulative_volume: int, run_id: str, feed: str, adjustment: str) -> dict[str, Any]`
- [_opening_window_single_session](../../service/forward_pit/batch.py) — ligne 1731 : `def _opening_window_single_session(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome`
- [_opening_window_session_complete](../../service/forward_pit/batch.py) — ligne 1925 : `def _opening_window_session_complete(engine: Engine, cfg: dict[str, Any], session_date: date, symbol_count: int) -> bool`
- [opening_window_sync](../../service/forward_pit/batch.py) — ligne 1951 : `def opening_window_sync(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome`
- [normalize_sec_events](../../service/forward_pit/batch.py) — ligne 1983 : `def normalize_sec_events(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome`
- [normalize_sec_ownership](../../service/forward_pit/batch.py) — ligne 2004 : `def normalize_sec_ownership(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome`
- [fred_alfred_sync](../../service/forward_pit/batch.py) — ligne 2027 : `def fred_alfred_sync(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome`
- [latest_quotes_sync_batch](../../service/forward_pit/batch.py) — ligne 2061 : `def latest_quotes_sync_batch(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome`
- [quality_daily](../../service/forward_pit/batch.py) — ligne 2138 : `def quality_daily(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome`
- [ml_artifacts_backup](../../service/forward_pit/batch.py) — ligne 2192 : `def ml_artifacts_backup(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome`
- [database_backup](../../service/forward_pit/batch.py) — ligne 2236 : `def database_backup(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool) -> Outcome`
- [us_pipeline](../../service/forward_pit/batch.py) — ligne 2294 : `def us_pipeline(engine, cfg, run_id, dry_run)`
- [execute](../../service/forward_pit/batch.py) — ligne 2324 : `def execute(batch_name: str, *, dry_run: bool=False, config_path: str | None=None) -> tuple[str, Outcome]`
- [main](../../service/forward_pit/batch.py) — ligne 2381 : `def main() -> None`

## `service/forward_pit/guidance_audit.py`

Source SHA-256 : `f302b317f5efa8908149348b352f3953b2c2581c2cff5d5d06edd2df490f8554`

- [VisibleText](../../service/forward_pit/guidance_audit.py) — ligne 17 : `class VisibleText(HTMLParser)`
- [VisibleText.__init__](../../service/forward_pit/guidance_audit.py) — ligne 18 : `def __init__(self)`
- [VisibleText.handle_starttag](../../service/forward_pit/guidance_audit.py) — ligne 22 : `def handle_starttag(self, tag, attrs)`
- [VisibleText.handle_endtag](../../service/forward_pit/guidance_audit.py) — ligne 28 : `def handle_endtag(self, tag)`
- [VisibleText.handle_data](../../service/forward_pit/guidance_audit.py) — ligne 34 : `def handle_data(self, data)`
- [money_range_candidates](../../service/forward_pit/guidance_audit.py) — ligne 39 : `def money_range_candidates(content)`
- [guidance_candidates](../../service/forward_pit/guidance_audit.py) — ligne 77 : `def guidance_candidates(content)`
- [run](../../service/forward_pit/guidance_audit.py) — ligne 103 : `def run(output, universe_path, sample_limit=100)`
- [main](../../service/forward_pit/guidance_audit.py) — ligne 180 : `def main()`

## `service/forward_pit/guidance_backfill.py`

Source SHA-256 : `179abaa8388283abbe3a7bd92c79f2ef8e46a65f08247c06b4d94fbecaf22645`

- [submission_filings](../../service/forward_pit/guidance_backfill.py) — ligne 25 : `def submission_filings(payload, start, end, maximum)`
- [history_pages](../../service/forward_pit/guidance_backfill.py) — ligne 41 : `def history_pages(payload, start, end)`
- [merge_history](../../service/forward_pit/guidance_backfill.py) — ligne 47 : `def merge_history(payload, history)`
- [directory_exhibit_candidates](../../service/forward_pit/guidance_backfill.py) — ligne 56 : `def directory_exhibit_candidates(items, base, primary_document=None, maximum=2)`
- [run](../../service/forward_pit/guidance_backfill.py) — ligne 75 : `def run(output, symbols, start, end, maximum, directory_index=False, max_history_pages=0)`
- [main](../../service/forward_pit/guidance_backfill.py) — ligne 212 : `def main()`

## `service/forward_pit/guidance_role_evaluation.py`

Source SHA-256 : `c3bc8d397229a857cc9cfa74872e17c95241fa5ddfd44c2fe743e9ab3c299523`

- [evaluate](../../service/forward_pit/guidance_role_evaluation.py) — ligne 8 : `def evaluate(rows, labels, known_missed=None)`
- [main](../../service/forward_pit/guidance_role_evaluation.py) — ligne 61 : `def main()`

## `service/forward_pit/guidance_structured.py`

Source SHA-256 : `1fbdaa909f52b52a04c88c037819862d5e62c5bbf9fd0e7941683279c623f540`

- [statement_role](../../service/forward_pit/guidance_structured.py) — ligne 24 : `def statement_role(visible, start, end, explicit_range=False)`
- [extract](../../service/forward_pit/guidance_structured.py) — ligne 64 : `def extract(content, source)`
- [availability](../../service/forward_pit/guidance_structured.py) — ligne 135 : `def availability(row)`
- [compare](../../service/forward_pit/guidance_structured.py) — ligne 152 : `def compare(old, new)`
- [pair_reviewed](../../service/forward_pit/guidance_structured.py) — ligne 185 : `def pair_reviewed(rows)`
- [run](../../service/forward_pit/guidance_structured.py) — ligne 208 : `def run(manifests, output, reviewed=None)`
- [main](../../service/forward_pit/guidance_structured.py) — ligne 260 : `def main()`

## `service/forward_pit/guidance_tables.py`

Source SHA-256 : `773bf6297a2a062e6ed96ac01a7d09889816e40e5bce77b3a7c6b23a8d5e4b35`

- [TableLayout](../../service/forward_pit/guidance_tables.py) — ligne 6 : `class TableLayout(VisibleText)`
- [TableLayout.__init__](../../service/forward_pit/guidance_tables.py) — ligne 7 : `def __init__(self)`
- [TableLayout.sync](../../service/forward_pit/guidance_tables.py) — ligne 15 : `def sync(self)`
- [TableLayout.handle_starttag](../../service/forward_pit/guidance_tables.py) — ligne 23 : `def handle_starttag(self, tag, attrs)`
- [TableLayout.handle_data](../../service/forward_pit/guidance_tables.py) — ligne 39 : `def handle_data(self, data)`
- [TableLayout.handle_endtag](../../service/forward_pit/guidance_tables.py) — ligne 43 : `def handle_endtag(self, tag)`
- [table_context](../../service/forward_pit/guidance_tables.py) — ligne 64 : `def table_context(layout, start, end)`

## `service/forward_pit/options_delayed.py`

Source SHA-256 : `29dbb5d5f3c694b267dfe9a7017d7c139bbf39b3fab22877d9ba9eb1d5725875`

- [_last_trading_day](../../service/forward_pit/options_delayed.py) — ligne 30 : `def _last_trading_day(day: date) -> date`
- [_float](../../service/forward_pit/options_delayed.py) — ligne 38 : `def _float(value: Any) -> float | None`
- [_int](../../service/forward_pit/options_delayed.py) — ligne 46 : `def _int(value: Any) -> int | None`
- [parse_occ_rss](../../service/forward_pit/options_delayed.py) — ligne 53 : `def parse_occ_rss(content: str | bytes) -> list[dict[str, Any]]`
- [select_atm_contracts](../../service/forward_pit/options_delayed.py) — ligne 97 : `def select_atm_contracts(contracts: Iterable[dict[str, Any]], *, spot: float, as_of: date, target_dtes: Iterable[int], tolerance_days: int) -> list[dict[str, Any]]`
- [_contract_row](../../service/forward_pit/options_delayed.py) — ligne 128 : `def _contract_row(item: dict[str, Any], *, observed: datetime, run_id: str) -> dict[str, Any]`
- [options_delayed_bars_sync](../../service/forward_pit/options_delayed.py) — ligne 145 : `def options_delayed_bars_sync(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool)`
- [option_contract_adjustment_sync](../../service/forward_pit/options_delayed.py) — ligne 249 : `def option_contract_adjustment_sync(engine: Engine, cfg: dict[str, Any], run_id: str, dry: bool)`
- [trade_bar_comparison](../../service/forward_pit/options_delayed.py) — ligne 273 : `def trade_bar_comparison(trades: list[dict[str, Any]], bars: list[dict[str, Any]]) -> dict[str, Any]`
- [main](../../service/forward_pit/options_delayed.py) — ligne 291 : `def main(argv: list[str] | None=None) -> int`

## `service/forward_pit/recovery_gate.py`

Source SHA-256 : `d5d02c2f1f01056eaba66def1483a061bd132baf21b57d902a9ca9e3f70b06ab`

- [has_recent_success](../../service/forward_pit/recovery_gate.py) — ligne 12 : `def has_recent_success(batch_name: str, lookback_hours: float) -> bool`
- [main](../../service/forward_pit/recovery_gate.py) — ligne 28 : `def main() -> None`

## `service/forward_pit/us_pipeline.py`

Source SHA-256 : `ae13d3aede470c7535a340d5fcd8dea5f127f089cde59ba37699a314331e67e1`

- [load_pipeline_policy](../../service/forward_pit/us_pipeline.py) — ligne 22 : `def load_pipeline_policy()`
- [selected_steps](../../service/forward_pit/us_pipeline.py) — ligne 29 : `def selected_steps(numbers, *, config_key='steps')`
- [session_steps](../../service/forward_pit/us_pipeline.py) — ligne 41 : `def session_steps(policy, day)`
- [require_paper_account](../../service/forward_pit/us_pipeline.py) — ligne 47 : `def require_paper_account(account_id)`
- [execution_options](../../service/forward_pit/us_pipeline.py) — ligne 54 : `def execution_options(options, policy, steps)`
- [collection_options](../../service/forward_pit/us_pipeline.py) — ligne 73 : `def collection_options(options, cfg, day)`
- [session_plan](../../service/forward_pit/us_pipeline.py) — ligne 110 : `def session_plan(now, *, calendar=None)`
- [execute_pipeline](../../service/forward_pit/us_pipeline.py) — ligne 130 : `def execute_pipeline(engine, cfg, run_id, dry_run, *, now=None)`

## `service/forward_pit/watcher_startup.py`

Source SHA-256 : `dd3db2b4b318dd47824d59c398c7b70334f2f7aa49be073cd6ccaf58185cf670`

- [_is_watcher_command](../../service/forward_pit/watcher_startup.py) — ligne 27 : `def _is_watcher_command(command)`
- [_compatible](../../service/forward_pit/watcher_startup.py) — ligne 39 : `def _compatible(command, account_id)`
- [find_running_service](../../service/forward_pit/watcher_startup.py) — ligne 46 : `def find_running_service(account_id)`
- [healthy_service](../../service/forward_pit/watcher_startup.py) — ligne 62 : `def healthy_service(repo, account_id)`
- [ensure_watcher](../../service/forward_pit/watcher_startup.py) — ligne 86 : `def ensure_watcher(engine, options, *, directory, stop_event, timeout_seconds=STARTUP_TIMEOUT_SECONDS)`

## `service/fr/__init__.py`

Source SHA-256 : `8033d3197817a86fca596e15b3adc5823b0335eec2921131e2526ad1f297ebf1`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `service/fr/anchor_replay_16g2.py`

Source SHA-256 : `6f4100da637d067c9557d1f996cd4681b393d680e735585963ee92acca6e63e7`

- [final_record](../../service/fr/anchor_replay_16g2.py) — ligne 19 : `def final_record(versions, end)`
- [compare](../../service/fr/anchor_replay_16g2.py) — ligne 27 : `def compare(history, master, candidates, end)`
- [replay](../../service/fr/anchor_replay_16g2.py) — ligne 54 : `def replay(confirmation_report, anchor_dir, historical_dir, *, root=ROOT, progress=None)`
- [main](../../service/fr/anchor_replay_16g2.py) — ligne 139 : `def main()`

## `service/fr/backup_qualification_15d.py`

Source SHA-256 : `92fb3006cdfe68cfa76a1ae6a75316b9f670d5a0c32c41e8052b0ee379d431a9`

- [digest_file](../../service/fr/backup_qualification_15d.py) — ligne 32 : `def digest_file(path)`
- [_write](../../service/fr/backup_qualification_15d.py) — ligne 40 : `def _write(path, payload)`
- [safe_member](../../service/fr/backup_qualification_15d.py) — ligne 57 : `def safe_member(name, root_name)`
- [verified_archive](../../service/fr/backup_qualification_15d.py) — ligne 65 : `def verified_archive(source, destination, *, keep=3, extract=False, progress=None)`
- [validate_sql](../../service/fr/backup_qualification_15d.py) — ligne 154 : `def validate_sql(archive)`
- [_inventory](../../service/fr/backup_qualification_15d.py) — ligne 165 : `def _inventory(engine, database)`
- [database_probe](../../service/fr/backup_qualification_15d.py) — ligne 184 : `def database_probe(cfg)`
- [main](../../service/fr/backup_qualification_15d.py) — ligne 234 : `def main()`

## `service/fr/bars.py`

Source SHA-256 : `ed557063e382c8bd69ab6524146366e61a3faa49344ea2d2f7ff5b7c66c30e76`

- [FRBarError](../../service/fr/bars.py) — ligne 17 : `class FRBarError(ValueError)`
- [_price](../../service/fr/bars.py) — ligne 21 : `def _price(value: Any, name: str) -> Decimal`
- [FRProviderBar](../../service/fr/bars.py) — ligne 32 : `class FRProviderBar`
- [normalize_eod_bar](../../service/fr/bars.py) — ligne 44 : `def normalize_eod_bar(payload: Mapping[str, Any], *, observed_at: datetime, published_at: datetime | None=None) -> FRProviderBar`

## `service/fr/bnains_price_reference_pilot.py`

Source SHA-256 : `dbddfcf12291833f280424e1abcf26cb3e70b70bf7238eefc92c17b327178b6f`

- [read_archive](../../service/fr/bnains_price_reference_pilot.py) — ligne 21 : `def read_archive(path: Path, target_isins: set[str])`
- [compare](../../service/fr/bnains_price_reference_pilot.py) — ligne 50 : `def compare(*, root: Path, archive_path: Path) -> dict`
- [main](../../service/fr/bnains_price_reference_pilot.py) — ligne 149 : `def main() -> None`

## `service/fr/bootstrap_qualification_16c.py`

Source SHA-256 : `68b1af6d4793e0bf72e859796b3b255e2c65e301ba53e204298523b28d8c390b`

- [qualify](../../service/fr/bootstrap_qualification_16c.py) — ligne 22 : `def qualify(bootstrap: Path, *, root: Path=ROOT, audit_at: datetime | None=None, calendar=None, manifest=None) -> dict`
- [main](../../service/fr/bootstrap_qualification_16c.py) — ligne 115 : `def main()`

## `service/fr/broker_contract_17a.py`

Source SHA-256 : `a1fcdbce523c06e812fa951d1fa7da0eb8484e0db744ebaa32b3b1f982857653`

- [valid_isin](../../service/fr/broker_contract_17a.py) — ligne 8 : `def valid_isin(value: str) -> bool`
- [FrenchTestIntent](../../service/fr/broker_contract_17a.py) — ligne 20 : `class FrenchTestIntent`
- [FrenchTestIntent.validate](../../service/fr/broker_contract_17a.py) — ligne 33 : `def validate(self)`
- [FrenchIntentHarness](../../service/fr/broker_contract_17a.py) — ligne 50 : `class FrenchIntentHarness`
- [FrenchIntentHarness.__init__](../../service/fr/broker_contract_17a.py) — ligne 55 : `def __init__(self, *, max_intent_notional_eur: Decimal)`
- [FrenchIntentHarness.accept](../../service/fr/broker_contract_17a.py) — ligne 64 : `def accept(self, intent: FrenchTestIntent)`
- [FrenchIntentHarness.status](../../service/fr/broker_contract_17a.py) — ligne 76 : `def status(self, intent_id)`
- [FrenchIntentHarness.cancel](../../service/fr/broker_contract_17a.py) — ligne 82 : `def cancel(self, intent_id)`
- [FrenchIntentHarness.kill](../../service/fr/broker_contract_17a.py) — ligne 88 : `def kill(self)`
- [readiness](../../service/fr/broker_contract_17a.py) — ligne 95 : `def readiness()`

## `service/fr/collection_coverage_remediation.py`

Source SHA-256 : `ce8fca1f208adbb5bbc441fcbb88ce9b71534a6903e4faebf0df962df92d6bb6`

- [coverage](../../service/fr/collection_coverage_remediation.py) — ligne 30 : `def coverage(symbols, sessions, observed)`
- [audit_sql](../../service/fr/collection_coverage_remediation.py) — ligne 47 : `def audit_sql(conn, symbols, sessions)`
- [audit_files](../../service/fr/collection_coverage_remediation.py) — ligne 82 : `def audit_files(symbols, sessions, *, root=ROOT, daily_root=None)`
- [dila_reserves](../../service/fr/collection_coverage_remediation.py) — ligne 123 : `def dila_reserves(*, root=ROOT)`
- [recheck](../../service/fr/collection_coverage_remediation.py) — ligne 137 : `def recheck(output, sessions)`
- [main](../../service/fr/collection_coverage_remediation.py) — ligne 168 : `def main()`

## `service/fr/consensus_daily.py`

Source SHA-256 : `5303b8ca15f88e40e02436a6cc755a66291e57e55963274eb9d9dc32c4b5cf18`

- [normal_name](../../service/fr/consensus_daily.py) — ligne 22 : `def normal_name(value)`
- [reference_scope](../../service/fr/consensus_daily.py) — ligne 32 : `def reference_scope(path)`
- [is_rate_limit](../../service/fr/consensus_daily.py) — ligne 66 : `def is_rate_limit(exc)`
- [IdentityMismatch](../../service/fr/consensus_daily.py) — ligne 70 : `class IdentityMismatch(ValueError)`
- [CheckedTicker](../../service/fr/consensus_daily.py) — ligne 74 : `class CheckedTicker`
- [CheckedTicker.__init__](../../service/fr/consensus_daily.py) — ligne 75 : `def __init__(self, ticker, symbol, names, reserve)`
- [CheckedTicker.call](../../service/fr/consensus_daily.py) — ligne 78 : `def call(self, method, **kwargs)`
- [CheckedTicker.get_info](../../service/fr/consensus_daily.py) — ligne 87 : `def get_info(self)`
- [CheckedTicker.__getattr__](../../service/fr/consensus_daily.py) — ligne 97 : `def __getattr__(self, method)`
- [collect_daily](../../service/fr/consensus_daily.py) — ligne 103 : `def collect_daily(cfg, result, *, root, identities, dry_run=False, max_symbols=None, ticker_factory=None, sleep=None)`

## `service/fr/consensus_revision_compare.py`

Source SHA-256 : `e8276fc50226f00ad82230b7aed0350dffa1de8c4b9a5a3809fd70161996b6e5`

- [load_observations](../../service/fr/consensus_revision_compare.py) — ligne 13 : `def load_observations(folder)`
- [flatten](../../service/fr/consensus_revision_compare.py) — ligne 42 : `def flatten(value, prefix='')`
- [compare](../../service/fr/consensus_revision_compare.py) — ligne 49 : `def compare(baseline, later)`
- [main](../../service/fr/consensus_revision_compare.py) — ligne 89 : `def main()`

## `service/fr/consensus_snapshot.py`

Source SHA-256 : `aaf076d74d942846176b3a890d0b4a6a1ed46b43717937599b0a8865d67f642e`

- [library_version](../../service/fr/consensus_snapshot.py) — ligne 29 : `def library_version()`
- [archive_endpoint](../../service/fr/consensus_snapshot.py) — ligne 36 : `def archive_endpoint(root, symbol, method, value, metadata, reference)`
- [CollectionPause](../../service/fr/consensus_snapshot.py) — ligne 53 : `class CollectionPause(RuntimeError)`
- [clean](../../service/fr/consensus_snapshot.py) — ligne 57 : `def clean(value)`
- [has_value](../../service/fr/consensus_snapshot.py) — ligne 71 : `def has_value(value)`
- [numeric_field](../../service/fr/consensus_snapshot.py) — ligne 79 : `def numeric_field(value, field)`
- [collect](../../service/fr/consensus_snapshot.py) — ligne 90 : `def collect(cfg, result, *, root, identities, dry_run=False, max_symbols=None, ticker_factory=None, sleep=time.sleep)`
- [main](../../service/fr/consensus_snapshot.py) — ligne 228 : `def main()`

## `service/fr/corporate_actions_audit.py`

Source SHA-256 : `62d13bd3b4fb840b15f507b00e546cec3ce32e342c0e564d1be933be1c1c239b`

- [split_ratio](../../service/fr/corporate_actions_audit.py) — ligne 21 : `def split_ratio(raw: str) -> Decimal | None`
- [price_jump_status](../../service/fr/corporate_actions_audit.py) — ligne 33 : `def price_jump_status(ratio: Decimal, before: Decimal, after: Decimal, *, max_deviation: Decimal=Decimal('0.25')) -> tuple[str, float]`
- [_rows](../../service/fr/corporate_actions_audit.py) — ligne 43 : `def _rows(root: Path, meta: dict, kind: str) -> list[dict]`
- [audit](../../service/fr/corporate_actions_audit.py) — ligne 52 : `def audit(root: Path) -> dict`
- [main](../../service/fr/corporate_actions_audit.py) — ligne 105 : `def main() -> None`

## `service/fr/daily_feature_adapter_16b.py`

Source SHA-256 : `dc7aad14f46f9b437b488d33f36f2b76c0241ce028f91f82e1e26bfb5b78fa0c`

- [read_json](../../service/fr/daily_feature_adapter_16b.py) — ligne 24 : `def read_json(path: Path, root: Path, proofs: dict) -> dict`
- [observed_payloads](../../service/fr/daily_feature_adapter_16b.py) — ligne 32 : `def observed_payloads(folder: Path, cutoff, root: Path, proofs: dict) -> tuple[list, list]`
- [select_bars](../../service/fr/daily_feature_adapter_16b.py) — ligne 63 : `def select_bars(payloads: list, symbol: str, sessions: list[date], calendar, cutoff) -> tuple[list, list]`
- [action_checks](../../service/fr/daily_feature_adapter_16b.py) — ligne 101 : `def action_checks(payloads: list, symbol: str, sessions: list[date]) -> list[str]`
- [master_at](../../service/fr/daily_feature_adapter_16b.py) — ligne 133 : `def master_at(folder: Path, cutoff, feature_day: date, root: Path, proofs: dict)`
- [identity_resolution](../../service/fr/daily_feature_adapter_16b.py) — ligne 163 : `def identity_resolution(state: dict | None, identity: dict, day: date) -> dict`
- [identity_reasons](../../service/fr/daily_feature_adapter_16b.py) — ligne 209 : `def identity_reasons(state: dict | None, identity: dict, day: date) -> list[str]`
- [assemble](../../service/fr/daily_feature_adapter_16b.py) — ligne 213 : `def assemble(decision_day: date, *, root: Path=ROOT, calendar=None, manifest=None, bootstrap_dir: Path | None=None) -> dict`
- [main](../../service/fr/daily_feature_adapter_16b.py) — ligne 296 : `def main()`

## `service/fr/data_readiness_16c.py`

Source SHA-256 : `0f5d024ccbed7f0bb00324c10a5f614bcc7261de1bffbf4a5cdc1cde401a6ffd`

- [reserve_audit](../../service/fr/data_readiness_16c.py) — ligne 19 : `def reserve_audit(root: Path=ROOT) -> dict`
- [run](../../service/fr/data_readiness_16c.py) — ligne 36 : `def run(output: Path, end: date, *, resume=False, max_symbols=None) -> dict`
- [main](../../service/fr/data_readiness_16c.py) — ligne 107 : `def main()`

## `service/fr/decision_qualification_16e.py`

Source SHA-256 : `813c7da76f9c3ffc29118a4a8d5a8e9d4a85863df461610b16ffa74e5d05b442`

- [evidence_at](../../service/fr/decision_qualification_16e.py) — ligne 19 : `def evidence_at(archive: Path, review: dict, cutoff: datetime) -> dict`
- [audit](../../service/fr/decision_qualification_16e.py) — ligne 51 : `def audit(decision_day: date, bootstrap: Path, archive: Path, *, now=None, root=ROOT, calendar=None)`
- [main](../../service/fr/decision_qualification_16e.py) — ligne 75 : `def main()`

## `service/fr/economic_decision_13c.py`

Source SHA-256 : `d02768a43263e999cb1eede785890c302dcdeab232538fe358730b922035b7bc`

- [attribution](../../service/fr/economic_decision_13c.py) — ligne 11 : `def attribution(result, instruments)`
- [run](../../service/fr/economic_decision_13c.py) — ligne 32 : `def run(source, output)`

## `service/fr/economic_preflight_11a.py`

Source SHA-256 : `8f03bc60fd637ecad5933d9448d8e6809dabb7fe53f1572a3e33bf8b6bebdd5d`

- [score_candidates](../../service/fr/economic_preflight_11a.py) — ligne 19 : `def score_candidates(candidates: pd.DataFrame, models: dict) -> pd.DataFrame`
- [selection_ledger](../../service/fr/economic_preflight_11a.py) — ligne 37 : `def selection_ledger(frame: pd.DataFrame, cfg: dict) -> pd.DataFrame`
- [load_protocol](../../service/fr/economic_preflight_11a.py) — ligne 58 : `def load_protocol(path: Path) -> dict`
- [candidate_audit](../../service/fr/economic_preflight_11a.py) — ligne 77 : `def candidate_audit(panel: pd.DataFrame, predictions: pd.DataFrame, folds: list[dict], cfg: dict) -> tuple[pd.DataFrame, list]`
- [readiness_checks](../../service/fr/economic_preflight_11a.py) — ligne 107 : `def readiness_checks(missing_scores: int, evidence: dict, costs: dict) -> list[dict]`
- [audit](../../service/fr/economic_preflight_11a.py) — ligne 118 : `def audit(cfg: dict) -> tuple[dict, pd.DataFrame]`

## `service/fr/economic_qualification_12a.py`

Source SHA-256 : `9b6fdf7e75c7a02f57d534d206f55ecd83fc416385584360c7e6f6bb9d80b393`

- [ttf_rate](../../service/fr/economic_qualification_12a.py) — ligne 33 : `def ttf_rate(acquisition_settlement_date: date) -> Decimal`
- [ttf_accrual](../../service/fr/economic_qualification_12a.py) — ligne 40 : `def ttf_accrual(settlement_date: date, net_acquired_quantity: int, average_purchase_price: Decimal, *, issuer_liability: bool | None) -> Decimal`
- [normalize_name](../../service/fr/economic_qualification_12a.py) — ligne 59 : `def normalize_name(value: str) -> str`
- [parse_issuer_list](../../service/fr/economic_qualification_12a.py) — ligne 64 : `def parse_issuer_list(html: str) -> list[str]`
- [dividend_check](../../service/fr/economic_qualification_12a.py) — ligne 74 : `def dividend_check(event: dict) -> list[str]`
- [run](../../service/fr/economic_qualification_12a.py) — ligne 95 : `def run(preflight: Path, output: Path, *, fetch_tax_sources: bool=True) -> dict`

## `service/fr/eodhd_backfill.py`

Source SHA-256 : `89c1db119a7402aa17cf8b192067928eccbfcc475ef9b0b197eeee2415692733`

- [_fetch](../../service/fr/eodhd_backfill.py) — ligne 29 : `def _fetch(endpoint: str, token: str, params: dict[str, str], *, pace: float) -> list[dict]`
- [_atomic_json](../../service/fr/eodhd_backfill.py) — ligne 70 : `def _atomic_json(path: Path, data: object) -> None`
- [_archive](../../service/fr/eodhd_backfill.py) — ligne 77 : `def _archive(root: Path, symbol: str, kind: str, rows: list[dict]) -> dict`
- [_archive_matches](../../service/fr/eodhd_backfill.py) — ligne 91 : `def _archive_matches(root: Path, item: dict) -> bool`
- [_collect_symbol](../../service/fr/eodhd_backfill.py) — ligne 100 : `def _collect_symbol(root: Path, record: dict, token: str, start: str, end: str, pace: float) -> dict`
- [run](../../service/fr/eodhd_backfill.py) — ligne 128 : `def run(*, root: Path, start: str, end: str, workers: int, pace: float, max_symbols: int | None=None) -> dict`
- [main](../../service/fr/eodhd_backfill.py) — ligne 192 : `def main() -> None`

## `service/fr/eodhd_daily_15b.py`

Source SHA-256 : `264c53a4f8e963c26b538d4e21d0b77bf111186fe1a12e1b94b355ef7ce0a1e3`

- [atomic](../../service/fr/eodhd_daily_15b.py) — ligne 21 : `def atomic(path: Path, payload: dict)`
- [symbols_from_identities](../../service/fr/eodhd_daily_15b.py) — ligne 45 : `def symbols_from_identities(path: Path) -> list[str]`
- [collect](../../service/fr/eodhd_daily_15b.py) — ligne 55 : `def collect(cfg: dict, result: dict, *, root: Path, identities: Path, dry_run=False, today: date | None=None, resume=False, max_symbols: int | None=None, selected_symbols: list[str] | None=None)`

## `service/fr/eodhd_id_mapping_audit.py`

Source SHA-256 : `e68418b01854742f7e66839ed2caa6baebb95168ada4afd07bbfcfb72b27b20a`

- [run](../../service/fr/eodhd_id_mapping_audit.py) — ligne 19 : `def run(archive_root: Path, output_root: Path) -> dict`
- [main](../../service/fr/eodhd_id_mapping_audit.py) — ligne 96 : `def main() -> None`

## `service/fr/eodhd_quality.py`

Source SHA-256 : `9df21f9ed3c68e41f0a9d35e713819fd124c6e34755f97deae86bcd7e5e0bc8c`

- [audit](../../service/fr/eodhd_quality.py) — ligne 17 : `def audit(root: Path) -> dict`
- [main](../../service/fr/eodhd_quality.py) — ligne 111 : `def main() -> None`

## `service/fr/esma_firds_annual_chain.py`

Source SHA-256 : `5d9336504b55c697b55c935059e191c69d600b83724d237fc46cdbf690a57eb0`

- [validate_history](../../service/fr/esma_firds_annual_chain.py) — ligne 27 : `def validate_history(path: Path, expected_end: date) -> dict`
- [_select_latest_full_date](../../service/fr/esma_firds_annual_chain.py) — ligne 42 : `def _select_latest_full_date(file_names: list[str], end: date) -> date`
- [latest_full_date](../../service/fr/esma_firds_annual_chain.py) — ligne 57 : `def latest_full_date(end: date, *, lookback_days: int=45) -> date`
- [_run](../../service/fr/esma_firds_annual_chain.py) — ligne 79 : `def _run(command: list[str], log_dir: Path, label: str) -> None`
- [_wait_for_report](../../service/fr/esma_firds_annual_chain.py) — ligne 96 : `def _wait_for_report(path: Path, expected_end: date, timeout_hours: float) -> dict`
- [run_chain](../../service/fr/esma_firds_annual_chain.py) — ligne 105 : `def run_chain(*, start_year: int, end_date: date, replay_root: Path, output_root: Path, log_root: Path, state_path: Path, wait_for_first: bool, wait_timeout_hours: float) -> dict`
- [main](../../service/fr/esma_firds_annual_chain.py) — ligne 187 : `def main() -> None`

## `service/fr/esma_firds_bar_coverage.py`

Source SHA-256 : `ac68caeb724cb5c9cd463c68d196c669dfd8d4fd5466a1c07dfe68da3ff9d767`

- [classify](../../service/fr/esma_firds_bar_coverage.py) — ligne 18 : `def classify(day: str, markets: list[dict], missing_days: set[str], first_full: str) -> str`
- [valid_bar](../../service/fr/esma_firds_bar_coverage.py) — ligne 47 : `def valid_bar(row: dict) -> bool`
- [audit](../../service/fr/esma_firds_bar_coverage.py) — ligne 60 : `def audit(history: dict, root: Path, *, start: str, end: str) -> dict`
- [main](../../service/fr/esma_firds_bar_coverage.py) — ligne 115 : `def main() -> None`

## `service/fr/esma_firds_download.py`

Source SHA-256 : `eeaf6a798d496d578a6df383bfb62d59793127b2564bb74592a45cc4c0ba477f`

- [_tls_context](../../service/fr/esma_firds_download.py) — ligne 30 : `def _tls_context() -> ssl.SSLContext`
- [_get_json](../../service/fr/esma_firds_download.py) — ligne 39 : `def _get_json(url: str, context: ssl.SSLContext) -> dict`
- [list_files](../../service/fr/esma_firds_download.py) — ligne 44 : `def list_files(start: date, end: date, full_date: date, context: ssl.SSLContext) -> list[dict]`
- [_check](../../service/fr/esma_firds_download.py) — ligne 93 : `def _check(path: Path, expected_md5: str | None) -> dict`
- [_download](../../service/fr/esma_firds_download.py) — ligne 110 : `def _download(item: dict, root: Path, context: ssl.SSLContext) -> dict`
- [run](../../service/fr/esma_firds_download.py) — ligne 136 : `def run(start: date, end: date, full_date: date, root: Path, *, max_files: int | None=None, workers: int=3) -> dict`
- [main](../../service/fr/esma_firds_download.py) — ligne 176 : `def main() -> None`

## `service/fr/esma_firds_full_reconcile.py`

Source SHA-256 : `4ccd68e3450e33801bf5dc01e6228c4a40aff002cce4a929153d2da39984336d`

- [_comparable_value](../../service/fr/esma_firds_full_reconcile.py) — ligne 17 : `def _comparable_value(field: str, value)`
- [_is_equity_cfi](../../service/fr/esma_firds_full_reconcile.py) — ligne 36 : `def _is_equity_cfi(value: object) -> bool`
- [_asof_state](../../service/fr/esma_firds_full_reconcile.py) — ligne 46 : `def _asof_state(history: dict, asof: date) -> tuple[dict[tuple[str, str], dict], list[dict], list[dict]]`
- [reconcile](../../service/fr/esma_firds_full_reconcile.py) — ligne 73 : `def reconcile(history: dict, archives: list[Path], asof: date) -> dict`
- [main](../../service/fr/esma_firds_full_reconcile.py) — ligne 114 : `def main() -> None`

## `service/fr/esma_firds_gap_audit.py`

Source SHA-256 : `d519d10c1b2ae0c43211ce12679de8ce7327bbf47b387b7a7f1c1e88194d178c`

- [audit](../../service/fr/esma_firds_gap_audit.py) — ligne 17 : `def audit(root: Path, *, end: date) -> dict`
- [main](../../service/fr/esma_firds_gap_audit.py) — ligne 76 : `def main() -> None`

## `service/fr/esma_firds_history.py`

Source SHA-256 : `f4734c2aaac5e8c629ab30cdd2bd8e84065107711f037e614b324792de88403e`

- [_value](../../service/fr/esma_firds_history.py) — ligne 26 : `def _value(parent: ET.Element | None, path: str) -> str | None`
- [archive_records](../../service/fr/esma_firds_history.py) — ligne 31 : `def archive_records(path: Path, target_isins: set[str], target_mics: set[str])`
- [_day](../../service/fr/esma_firds_history.py) — ligne 68 : `def _day(value: str | None) -> date | None`
- [apply_event](../../service/fr/esma_firds_history.py) — ligne 74 : `def apply_event(history: dict[tuple[str, str], list[dict]], record: dict, archive_day: date, source: str, anomalies: list[dict]) -> None`
- [_observed_interval](../../service/fr/esma_firds_history.py) — ligne 108 : `def _observed_interval(version: dict) -> dict | None`
- [_trading_episodes](../../service/fr/esma_firds_history.py) — ligne 126 : `def _trading_episodes(versions: list[dict]) -> list[dict]`
- [replay](../../service/fr/esma_firds_history.py) — ligne 169 : `def replay(index_path: Path, subset_path: Path, root: Path, *, end: date, mics: set[str]=DEFAULT_MICS, require_complete: bool=True, resume_from: Path | None=None) -> dict`
- [main](../../service/fr/esma_firds_history.py) — ligne 258 : `def main() -> None`

## `service/fr/esma_firds_reference_pilot.py`

Source SHA-256 : `ca5ca5b668504db3d04b07503e58574f4c8c195ea3d68f825ca464c26bc9d513`

- [_value](../../service/fr/esma_firds_reference_pilot.py) — ligne 21 : `def _value(parent: ET.Element | None, path: str) -> str | None`
- [extract_reference_files](../../service/fr/esma_firds_reference_pilot.py) — ligne 26 : `def extract_reference_files(archives: list[Path], target_isins: set[str], expected_md5: dict[str, str]) -> tuple[list[dict], list[dict]]`
- [summarize](../../service/fr/esma_firds_reference_pilot.py) — ligne 69 : `def summarize(subset: dict, matches: list[dict], files: list[dict]) -> dict`
- [main](../../service/fr/esma_firds_reference_pilot.py) — ligne 108 : `def main() -> None`

## `service/fr/esma_firds_reframe.py`

Source SHA-256 : `90f762ab2035059e888fe5077d2b9760dc21c1ebb2c587a086db15a142153449`

- [reframe](../../service/fr/esma_firds_reframe.py) — ligne 20 : `def reframe(report: dict, source_sha256: str) -> dict`
- [main](../../service/fr/esma_firds_reframe.py) — ligne 53 : `def main() -> None`

## `service/fr/euronext_delisted_reference.py`

Source SHA-256 : `c3c57a3dacf2f38eb583d5d74ca01b17ff8c25ab30773cda85500108a84420a9`

- [_evp_bytes_to_key](../../service/fr/euronext_delisted_reference.py) — ligne 31 : `def _evp_bytes_to_key(password: bytes, salt: bytes, length: int=48) -> bytes`
- [decrypt_ajax](../../service/fr/euronext_delisted_reference.py) — ligne 40 : `def decrypt_ajax(payload: dict[str, str], password: str) -> Any`
- [parse_page_settings](../../service/fr/euronext_delisted_reference.py) — ligne 54 : `def parse_page_settings(html: str, isin: str) -> dict[str, str]`
- [discover_instrument](../../service/fr/euronext_delisted_reference.py) — ligne 75 : `def discover_instrument(session: requests.Session, isin: str) -> dict[str, str]`
- [_number](../../service/fr/euronext_delisted_reference.py) — ligne 90 : `def _number(value: str | None) -> float | None`
- [parse_historical_html](../../service/fr/euronext_delisted_reference.py) — ligne 102 : `def parse_historical_html(html: str) -> dict[str, dict[str, float | int | None]]`
- [fetch_history](../../service/fr/euronext_delisted_reference.py) — ligne 126 : `def fetch_history(session: requests.Session, instrument: dict[str, str], *, start: str, end: str, maximum_sessions: int=800) -> tuple[dict[str, dict], str]`
- [read_eodhd](../../service/fr/euronext_delisted_reference.py) — ligne 150 : `def read_eodhd(path: Path) -> dict[str, dict]`
- [audit_rows](../../service/fr/euronext_delisted_reference.py) — ligne 155 : `def audit_rows(reference: dict[str, dict], provider: dict[str, dict], *, tolerance_ratio: float=0.001) -> dict`
- [_write_normalized](../../service/fr/euronext_delisted_reference.py) — ligne 193 : `def _write_normalized(path: Path, *, symbol: str, isin: str, instrument: dict[str, str], rows: dict[str, dict]) -> str`
- [archive_path](../../service/fr/euronext_delisted_reference.py) — ligne 210 : `def archive_path(archive_root: Path, symbol: str) -> Path`
- [collect](../../service/fr/euronext_delisted_reference.py) — ligne 216 : `def collect(*, subset_path: Path, archive_root: Path, output: Path, cutoff: str | None=None, minimum_rows: int=1, verify_tls: bool=True) -> dict`
- [main](../../service/fr/euronext_delisted_reference.py) — ligne 280 : `def main() -> None`

## `service/fr/euronext_price_reference_pilot.py`

Source SHA-256 : `e7d67b875c24f80fc5b8600a4b61ea984cba6db9b3490c3a6aa54ea4c60179ae`

- [read_euronext](../../service/fr/euronext_price_reference_pilot.py) — ligne 22 : `def read_euronext(path: Path) -> dict[str, dict]`
- [audit](../../service/fr/euronext_price_reference_pilot.py) — ligne 39 : `def audit(euronext_path: Path, eodhd_path: Path, *, isin: str, tolerance: float=0.0001, compare_volume: bool=False) -> dict`
- [main](../../service/fr/euronext_price_reference_pilot.py) — ligne 80 : `def main() -> None`

## `service/fr/event_data_qualification_11b.py`

Source SHA-256 : `c8178fe07d610810ebebbfbb7828edf5af69d427aa94c0ce9bda23fe5528eaa1`

- [digest](../../service/fr/event_data_qualification_11b.py) — ligne 24 : `def digest(raw: bytes) -> str`
- [fetch](../../service/fr/event_data_qualification_11b.py) — ligne 28 : `def fetch(url: str) -> bytes`
- [parse_positions](../../service/fr/event_data_qualification_11b.py) — ligne 36 : `def parse_positions(raw: bytes) -> tuple[list[dict], list[dict]]`
- [inventory](../../service/fr/event_data_qualification_11b.py) — ligne 68 : `def inventory(records: list[dict], isins: set[str]) -> dict`
- [public_day](../../service/fr/event_data_qualification_11b.py) — ligne 92 : `def public_day(row: dict) -> str | None`
- [recent_count](../../service/fr/event_data_qualification_11b.py) — ligne 110 : `def recent_count(days: list[str], decision: str, window: int=7) -> int`
- [pool_coverage](../../service/fr/event_data_qualification_11b.py) — ligne 117 : `def pool_coverage(pool_path: Path, reference: list[dict], records: list[dict], metadata: list[dict], output: Path) -> dict`
- [run](../../service/fr/event_data_qualification_11b.py) — ligne 164 : `def run(output: Path, identities: Path, guidance: Path, pool_path: Path | None=None) -> dict`

## `service/fr/event_direction_11c.py`

Source SHA-256 : `a090dea15a2cd226aa73bc91fa297032b96f1a3f52551e3ca1ea38ac56b09902`

- [available_day](../../service/fr/event_direction_11c.py) — ligne 28 : `def available_day(day: str, lag: int) -> str`
- [amf_events](../../service/fr/event_direction_11c.py) — ligne 34 : `def amf_events(records: list[dict]) -> tuple[list[dict], dict]`
- [dila_events](../../service/fr/event_direction_11c.py) — ligne 67 : `def dila_events(metadata: list[dict]) -> tuple[list[dict], dict]`
- [event_features](../../service/fr/event_direction_11c.py) — ligne 86 : `def event_features(pool: pd.DataFrame, identity: dict, amf: list[dict], dila: list[dict], collected: set[str], lag: int) -> pd.DataFrame`
- [validate_review](../../service/fr/event_direction_11c.py) — ligne 111 : `def validate_review(review: dict, audit: list[dict]) -> list[dict]`
- [run](../../service/fr/event_direction_11c.py) — ligne 125 : `def run(profile: Path, output: Path) -> dict`

## `service/fr/evidence_archive_16e.py`

Source SHA-256 : `3aff0642fdf2f9f1e7ca6e020cd133ba6678ebc7e420a17968900e45cd7d6ae7`

- [validate_url](../../service/fr/evidence_archive_16e.py) — ligne 21 : `def validate_url(url)`
- [download](../../service/fr/evidence_archive_16e.py) — ligne 27 : `def download(url)`
- [available](../../service/fr/evidence_archive_16e.py) — ligne 42 : `def available(record, cutoff)`
- [verify_record](../../service/fr/evidence_archive_16e.py) — ligne 56 : `def verify_record(record, output)`
- [collect](../../service/fr/evidence_archive_16e.py) — ligne 67 : `def collect(output, spec, *, fetch=download)`
- [main](../../service/fr/evidence_archive_16e.py) — ligne 114 : `def main()`

## `service/fr/execution_costs.py`

Source SHA-256 : `bb4ca7b95adefb872715985ea688fc81f726766e59c899774c15efbd6a5fd0cf`

- [number](../../service/fr/execution_costs.py) — ligne 13 : `def number(value) -> Decimal`
- [load_cost_profile](../../service/fr/execution_costs.py) — ligne 20 : `def load_cost_profile(path: Path) -> dict`
- [resolve_liability](../../service/fr/execution_costs.py) — ligne 47 : `def resolve_liability(path: Path, *, isin: str, ticker: str, settlement_date: date) -> bool`
- [execution_costs](../../service/fr/execution_costs.py) — ligne 61 : `def execution_costs(cfg: dict, *, side: str, quantity: int, reference_price: Decimal, settlement_date: date | None=None, issuer_liability: bool | None=None, executed: bool=True, stress_multiplier: Decimal=Decimal(1)) -> dict`
- [costs_for_instrument](../../service/fr/execution_costs.py) — ligne 99 : `def costs_for_instrument(cfg: dict, *, isin: str, ticker: str, side: str, quantity: int, reference_price: Decimal, settlement_date: date, executed: bool=True) -> dict`

## `service/fr/execution_evidence_12c.py`

Source SHA-256 : `638d88333524a1e978c9aaacd32d91b6c338061a1920e67b96e3be398e71f5ef`

- [standard_settlement](../../service/fr/execution_evidence_12c.py) — ligne 36 : `def standard_settlement(day: date) -> date`
- [issuer_match](../../service/fr/execution_evidence_12c.py) — ligne 50 : `def issuer_match(identity: dict, official_name: str, year: int) -> list[dict]`
- [collect_source](../../service/fr/execution_evidence_12c.py) — ligne 66 : `def collect_source(url: str, output: Path) -> dict`
- [run](../../service/fr/execution_evidence_12c.py) — ligne 78 : `def run(output: Path, qualification: Path, *, collect: bool=True) -> dict`

## `service/fr/exploitable_scope_12e.py`

Source SHA-256 : `717e61047f51bb2d269a550cc09f10e89d87eadfe7874e0b7b69b07c235c3551`

- [sha](../../service/fr/exploitable_scope_12e.py) — ligne 17 : `def sha(path: Path) -> str`
- [audit_paths](../../service/fr/exploitable_scope_12e.py) — ligne 21 : `def audit_paths(paths: pd.DataFrame, tax: pd.DataFrame, settlements: dict, identities: list[dict]) -> pd.DataFrame`
- [policy_coverage](../../service/fr/exploitable_scope_12e.py) — ligne 79 : `def policy_coverage(paths: pd.DataFrame, intents: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]`
- [run](../../service/fr/exploitable_scope_12e.py) — ligne 106 : `def run(output: Path, preflight: Path, qualification: Path, fiscal: Path, evidence: Path, public: Path, identity_path: Path) -> dict`

## `service/fr/feature_parity_16g.py`

Source SHA-256 : `1f802650d3b6fab87e197f9236b10c7429585960c150053abfaed07aaa64ffc9`

- [manual_features](../../service/fr/feature_parity_16g.py) — ligne 22 : `def manual_features(rows)`
- [parity](../../service/fr/feature_parity_16g.py) — ligne 57 : `def parity(rows, sessions, *, compute=compute_symbol_features, transform=feature_matrix)`
- [run](../../service/fr/feature_parity_16g.py) — ligne 76 : `def run(packet_path, *, root=ROOT)`
- [main](../../service/fr/feature_parity_16g.py) — ligne 141 : `def main()`

## `service/fr/free_blocker_review.py`

Source SHA-256 : `836dfa71e901e45876ec088c8301f43a81c531426414f3a6a4dd58218ed6ad1f`

- [alias_versions](../../service/fr/free_blocker_review.py) — ligne 20 : `def alias_versions(identity: dict, alias: dict, official_name: str, year: int) -> list[dict]`
- [reuse_verified_source](../../service/fr/free_blocker_review.py) — ligne 35 : `def reuse_verified_source(alias: dict, output: Path, directories: list[Path]) -> dict | None`
- [run](../../service/fr/free_blocker_review.py) — ligne 53 : `def run(output: Path) -> dict`

## `service/fr/guidance_completion_11e.py`

Source SHA-256 : `d71bff29444255d8d47ff424c03b4b3c856d0a91c99ed80c4548a0974144037e`

- [prepare](../../service/fr/guidance_completion_11e.py) — ligne 22 : `def prepare(output: Path, prior: Path)`
- [supplement](../../service/fr/guidance_completion_11e.py) — ligne 91 : `def supplement(output: Path, prior: Path)`
- [pair_direction](../../service/fr/guidance_completion_11e.py) — ligne 119 : `def pair_direction(old, new)`
- [check_second_review](../../service/fr/guidance_completion_11e.py) — ligne 129 : `def check_second_review(payload)`
- [resolved_manifest_records](../../service/fr/guidance_completion_11e.py) — ligne 158 : `def resolved_manifest_records(path: Path, seen=None)`
- [screen_documents](../../service/fr/guidance_completion_11e.py) — ligne 177 : `def screen_documents(documents)`
- [publication_day](../../service/fr/guidance_completion_11e.py) — ligne 195 : `def publication_day(doc)`
- [package](../../service/fr/guidance_completion_11e.py) — ligne 211 : `def package(output: Path, manifest_path: Path, roots=None)`
- [support](../../service/fr/guidance_completion_11e.py) — ligne 305 : `def support(output: Path)`
- [main](../../service/fr/guidance_completion_11e.py) — ligne 370 : `def main()`

## `service/fr/guidance_corpus_11d.py`

Source SHA-256 : `7deb0781e23d117334e6008ac7c6bba9f93ba7b746d8d76cd7e97a7532c38f5a`

- [sha](../../service/fr/guidance_corpus_11d.py) — ligne 28 : `def sha(raw: bytes) -> str`
- [dump](../../service/fr/guidance_corpus_11d.py) — ligne 32 : `def dump(path: Path, value) -> None`
- [normalized](../../service/fr/guidance_corpus_11d.py) — ligne 36 : `def normalized(value: str) -> str`
- [title_kind](../../service/fr/guidance_corpus_11d.py) — ligne 40 : `def title_kind(title: str) -> str | None`
- [fetch](../../service/fr/guidance_corpus_11d.py) — ligne 60 : `def fetch(url: str, max_bytes: int=35000000) -> bytes`
- [select](../../service/fr/guidance_corpus_11d.py) — ligne 69 : `def select(candidates: list[dict], old_isins: set[str], per_side: int=10) -> list[dict]`
- [collect](../../service/fr/guidance_corpus_11d.py) — ligne 87 : `def collect(output: Path, identities: Path, prior: Path) -> dict`
- [pdf_stage](../../service/fr/guidance_corpus_11d.py) — ligne 162 : `def pdf_stage(output: Path) -> dict`
- [validate_pair](../../service/fr/guidance_corpus_11d.py) — ligne 236 : `def validate_pair(pair: dict, publication_day: date) -> None`
- [review_stage](../../service/fr/guidance_corpus_11d.py) — ligne 258 : `def review_stage(output: Path, review_path: Path) -> dict`

## `service/fr/guidance_free_sources_11f.py`

Source SHA-256 : `1800fef7d900c60784c51d918b794d1c7b7c5a6f0efd575485cb771a9efbb799`

- [within_archive_boundary](../../service/fr/guidance_free_sources_11f.py) — ligne 20 : `def within_archive_boundary(payload, cutoff)`
- [collect](../../service/fr/guidance_free_sources_11f.py) — ligne 27 : `def collect(output: Path)`
- [main](../../service/fr/guidance_free_sources_11f.py) — ligne 94 : `def main()`

## `service/fr/http.py`

Source SHA-256 : `1ebb04a4922bc0a1b7d8e9d4c83ad65a9941c2b8db9f8cbe508c76bdc66349b2`

- [SystemTrustAdapter](../../service/fr/http.py) — ligne 14 : `class SystemTrustAdapter(HTTPAdapter)`
- [SystemTrustAdapter.__init__](../../service/fr/http.py) — ligne 15 : `def __init__(self, **kwargs)`
- [SystemTrustAdapter.init_poolmanager](../../service/fr/http.py) — ligne 19 : `def init_poolmanager(self, *args, **kwargs)`
- [SystemTrustAdapter.proxy_manager_for](../../service/fr/http.py) — ligne 23 : `def proxy_manager_for(self, *args, **kwargs)`
- [verified_system_session](../../service/fr/http.py) — ligne 28 : `def verified_system_session() -> requests.Session`

## `service/fr/identity.py`

Source SHA-256 : `a5da9ffdc6f30daed4f9548026a0c0b3ae29b86c225fb30686c2fa7c3ca1c517`

- [FrIdentityConflict](../../service/fr/identity.py) — ligne 13 : `class FrIdentityConflict(ValueError)`
- [Validity](../../service/fr/identity.py) — ligne 18 : `class Validity`
- [Validity.__post_init__](../../service/fr/identity.py) — ligne 25 : `def __post_init__(self) -> None`
- [assert_no_overlap](../../service/fr/identity.py) — ligne 32 : `def assert_no_overlap(rows: Iterable[Validity]) -> None`

## `service/fr/import_eodhd_archive.py`

Source SHA-256 : `2dd5a602139b0751e0546170d537fadb6f700b73164c02c6249109697e692174`

- [archive_rows](../../service/fr/import_eodhd_archive.py) — ligne 18 : `def archive_rows(root: Path) -> tuple[dict, list[dict]]`
- [import_archive](../../service/fr/import_eodhd_archive.py) — ligne 45 : `def import_archive(root: Path) -> dict`
- [main](../../service/fr/import_eodhd_archive.py) — ligne 87 : `def main() -> None`

## `service/fr/issuer_pilot_16g.py`

Source SHA-256 : `ca43263c677f66036ac1713b75603ff05e6b71ecda1ba4cc37974e0a0d79c408`

- [checked](../../service/fr/issuer_pilot_16g.py) — ligne 15 : `def checked(path, expected=None)`
- [select_candidates](../../service/fr/issuer_pilot_16g.py) — ligne 23 : `def select_candidates(packet)`
- [metadata_inventory](../../service/fr/issuer_pilot_16g.py) — ligne 39 : `def metadata_inventory(folder, *, cutoff, start, end)`
- [run](../../service/fr/issuer_pilot_16g.py) — ligne 79 : `def run(packet_path, output_dir, *, root=ROOT)`
- [main](../../service/fr/issuer_pilot_16g.py) — ligne 121 : `def main()`

## `service/fr/load_eodhd_staging.py`

Source SHA-256 : `07f21132e47ab27ddfb1033460714beddba8c18998eacfda90aada25d7db80d4`

- [_decimal](../../service/fr/load_eodhd_staging.py) — ligne 26 : `def _decimal(value)`
- [classify_bar](../../service/fr/load_eodhd_staging.py) — ligne 34 : `def classify_bar(row: dict, sessions: set[date]) -> tuple[date, str, dict]`
- [_read_payload](../../service/fr/load_eodhd_staging.py) — ligne 64 : `def _read_payload(root: Path, item: dict) -> list[dict]`
- [load](../../service/fr/load_eodhd_staging.py) — ligne 75 : `def load(root: Path, *, max_symbols: int | None=None) -> dict`
- [main](../../service/fr/load_eodhd_staging.py) — ligne 195 : `def main() -> None`

## `service/fr/local_shadow_simulation.py`

Source SHA-256 : `490454dbed049de1130e4b1421ddb32acb834965d9f6fe1a9bebc494cf7bbd22`

- [digest](../../service/fr/local_shadow_simulation.py) — ligne 30 : `def digest(path)`
- [implementation_hashes](../../service/fr/local_shadow_simulation.py) — ligne 34 : `def implementation_hashes()`
- [read_subset](../../service/fr/local_shadow_simulation.py) — ligne 42 : `def read_subset(path, manifest)`
- [rank_scores](../../service/fr/local_shadow_simulation.py) — ligne 62 : `def rank_scores(rows, probabilities, day, *, fraction=0.2)`
- [validate_protocol](../../service/fr/local_shadow_simulation.py) — ligne 78 : `def validate_protocol(protocol, manifest, source, bootstrap)`
- [write](../../service/fr/local_shadow_simulation.py) — ligne 95 : `def write(output, name, payload)`
- [run](../../service/fr/local_shadow_simulation.py) — ligne 100 : `def run(*, phase, output, subset, bootstrap, decision_day=None, protocol_path=None)`
- [main](../../service/fr/local_shadow_simulation.py) — ligne 222 : `def main()`

## `service/fr/mifir_equity_currency_16g.py`

Source SHA-256 : `053a5c8b858be622467fec9f5279ff948ed6003eb2e197eea05485e34e3a47be`

- [select_rows](../../service/fr/mifir_equity_currency_16g.py) — ligne 26 : `def select_rows(raw)`
- [analyze](../../service/fr/mifir_equity_currency_16g.py) — ligne 59 : `def analyze(rows, observed_at)`
- [run](../../service/fr/mifir_equity_currency_16g.py) — ligne 115 : `def run(output_dir, archive_report=None)`

## `service/fr/mifir_options_daily.py`

Source SHA-256 : `e5b536f416b9e191c2380666be8bd64c512eb9e689c36296b06e6d901be13993`

- [_archive](../../service/fr/mifir_options_daily.py) — ligne 13 : `def _archive(root, raw, receipt)`
- [collect](../../service/fr/mifir_options_daily.py) — ligne 28 : `def collect(cfg, result, *, root, identities, dry_run=False, max_symbols=None, fetch=None, clock=None)`

## `service/fr/mifir_options_poc.py`

Source SHA-256 : `f419724f0481e9cd1c72a9b3059d500c9c4a2ed4ab4f4762f883712c29d228c0`

- [now](../../service/fr/mifir_options_poc.py) — ligne 33 : `def now()`
- [instant](../../service/fr/mifir_options_poc.py) — ligne 37 : `def instant(value)`
- [number](../../service/fr/mifir_options_poc.py) — ligne 44 : `def number(value)`
- [write_json](../../service/fr/mifir_options_poc.py) — ligne 54 : `def write_json(path, value)`
- [fetch](../../service/fr/mifir_options_poc.py) — ligne 58 : `def fetch(url, limit)`
- [read_trades](../../service/fr/mifir_options_poc.py) — ligne 75 : `def read_trades(data)`
- [query_url](../../service/fr/mifir_options_poc.py) — ligne 95 : `def query_url(isins)`
- [valid_isin](../../service/fr/mifir_options_poc.py) — ligne 105 : `def valid_isin(value)`
- [reference_index](../../service/fr/mifir_options_poc.py) — ligne 116 : `def reference_index(docs)`
- [option_contract](../../service/fr/mifir_options_poc.py) — ligne 131 : `def option_contract(doc, universe=None)`
- [analyze](../../service/fr/mifir_options_poc.py) — ligne 157 : `def analyze(trades, docs, observed_at, universe=None)`
- [run](../../service/fr/mifir_options_poc.py) — ligne 236 : `def run(output_root, *, download_public_poc=False, trades_zip=None, reference_json=None)`
- [main](../../service/fr/mifir_options_poc.py) — ligne 313 : `def main()`

## `service/fr/mifir_options_qualification.py`

Source SHA-256 : `32bb2a90f11a86630bba5617328d571e0c6a9170e56cf37d97a6eb2d1d3e08f7`

- [audit](../../service/fr/mifir_options_qualification.py) — ligne 16 : `def audit(snapshot)`
- [main](../../service/fr/mifir_options_qualification.py) — ligne 72 : `def main()`

## `service/fr/observed_reference_16d.py`

Source SHA-256 : `f6b969a9e4f3fe1caf0a3cdbfb2a58146c6aa5d4171febff5fa6fa89dd4d8ae4`

- [load_policy](../../service/fr/observed_reference_16d.py) — ligne 18 : `def load_policy(path: Path=POLICY) -> dict`
- [validate_policy](../../service/fr/observed_reference_16d.py) — ligne 23 : `def validate_policy(policy: dict) -> dict`
- [select_reference](../../service/fr/observed_reference_16d.py) — ligne 37 : `def select_reference(decision_at: str, feature_day: date, *, root: Path=ROOT, policy: dict | None=None, calendar=None, manifest=None) -> dict`
- [main](../../service/fr/observed_reference_16d.py) — ligne 88 : `def main()`

## `service/fr/opening_confirmation_16f.py`

Source SHA-256 : `d1e323d5dd5d210b23f200f0488c95d0a44a740a1ff30d21356ad55fb78df70f`

- [validate](../../service/fr/opening_confirmation_16f.py) — ligne 18 : `def validate(protocol)`
- [execute](../../service/fr/opening_confirmation_16f.py) — ligne 27 : `def execute(protocol, phase, *, now=None, root=ROOT, calendar=None)`
- [main](../../service/fr/opening_confirmation_16f.py) — ligne 83 : `def main()`

## `service/fr/opening_evidence_overlay.py`

Source SHA-256 : `4e1ecfd848a3020de25a67f9f472162901d2d26c5295123e984d71c33c9ee7c4`

- [qualify_no_open](../../service/fr/opening_evidence_overlay.py) — ligne 16 : `def qualify_no_open(row: dict) -> None`
- [run](../../service/fr/opening_evidence_overlay.py) — ligne 23 : `def run(output: Path) -> dict`

## `service/fr/opening_remediation_16f.py`

Source SHA-256 : `72543f55411c31eb12102c6eb683ed868fb778b078e2993100901ed0a80897e3`

- [hash_file](../../service/fr/opening_remediation_16f.py) — ligne 25 : `def hash_file(path)`
- [probe_catalogue](../../service/fr/opening_remediation_16f.py) — ligne 29 : `def probe_catalogue(days, now, *, loader=delta_index, context_factory=_tls_context)`
- [audit](../../service/fr/opening_remediation_16f.py) — ligne 52 : `def audit(bootstrap, *, root=ROOT, now=None, probe_days=())`
- [main](../../service/fr/opening_remediation_16f.py) — ligne 92 : `def main()`

## `service/fr/operational_batch_15a.py`

Source SHA-256 : `5db5fc3c0e691805ffda11d905a170c3a1a889b6d689b2dff8bf8f393e20b125`

- [load_section](../../service/fr/operational_batch_15a.py) — ligne 22 : `def load_section(name: str, config_path: Path) -> dict`
- [run](../../service/fr/operational_batch_15a.py) — ligne 34 : `def run(name: str, *, config_path: Path=ROOT / 'batch_fr.yaml', dry_run=False, today: date | None=None, resume=False, max_symbols: int | None=None) -> dict`
- [_handle](../../service/fr/operational_batch_15a.py) — ligne 65 : `def _handle(name, cfg, result, *, dry_run, today, resume=False, max_symbols=None)`
- [latest_run](../../service/fr/operational_batch_15a.py) — ligne 264 : `def latest_run(name: str) -> dict | None`
- [main](../../service/fr/operational_batch_15a.py) — ligne 273 : `def main()`

## `service/fr/operational_closure_15g.py`

Source SHA-256 : `cc3ebe418e65e5264ab584afc49fe3fe21e79d15866c463f8290b3fb0ab39317`

- [observed_day](../../service/fr/operational_closure_15g.py) — ligne 18 : `def observed_day(row: dict) -> str | None`
- [run_evidence](../../service/fr/operational_closure_15g.py) — ligne 26 : `def run_evidence(rows: list[dict], expected_days: list[str]) -> dict`
- [audit](../../service/fr/operational_closure_15g.py) — ligne 47 : `def audit(root: Path, *, as_of: date, expected_days: list[str]) -> dict`
- [main](../../service/fr/operational_closure_15g.py) — ligne 92 : `def main()`

## `service/fr/operational_collectors_15c.py`

Source SHA-256 : `b0aa809701b38a7d18a92e9d29b40638a76c6a8c39542beb74eaea96830984de`

- [reference](../../service/fr/operational_collectors_15c.py) — ligne 22 : `def reference(path)`
- [window](../../service/fr/operational_collectors_15c.py) — ligne 27 : `def window(cfg, today=None)`
- [archive](../../service/fr/operational_collectors_15c.py) — ligne 35 : `def archive(root, payload)`
- [observe](../../service/fr/operational_collectors_15c.py) — ligne 46 : `def observe(root, payload)`
- [validate_actions](../../service/fr/operational_collectors_15c.py) — ligne 52 : `def validate_actions(rows, kind, start, end)`
- [corporate](../../service/fr/operational_collectors_15c.py) — ligne 76 : `def corporate(cfg, result, *, root, identities, dry_run=False, today=None, resume=False, max_symbols=None)`
- [public_collection](../../service/fr/operational_collectors_15c.py) — ligne 133 : `def public_collection(name, cfg, result, *, root, identities, dry_run=False, today=None)`
- [quality](../../service/fr/operational_collectors_15c.py) — ligne 189 : `def quality(cfg, result, *, operations, dry_run=False, today=None)`

## `service/fr/operations_preparation_18.py`

Source SHA-256 : `c2d429c5f1bb0c0d7c607f9ab4507bb7557182605b49d50ac52c71e2e3868c80`

- [number](../../service/fr/operations_preparation_18.py) — ligne 24 : `def number(value, name, *, positive=False)`
- [Limits](../../service/fr/operations_preparation_18.py) — ligne 37 : `class Limits`
- [Limits.validate](../../service/fr/operations_preparation_18.py) — ligne 45 : `def validate(self)`
- [load_policy](../../service/fr/operations_preparation_18.py) — ligne 58 : `def load_policy(path=DEFAULT_POLICY, *, root=ROOT)`
- [SyntheticObservation](../../service/fr/operations_preparation_18.py) — ligne 81 : `class SyntheticObservation`
- [aware](../../service/fr/operations_preparation_18.py) — ligne 101 : `def aware(value)`
- [evaluate_synthetic](../../service/fr/operations_preparation_18.py) — ligne 107 : `def evaluate_synthetic(observation, limits, *, now)`
- [build_report](../../service/fr/operations_preparation_18.py) — ligne 169 : `def build_report(*, policy_path=DEFAULT_POLICY, root=ROOT, now=None)`
- [run_drills](../../service/fr/operations_preparation_18.py) — ligne 220 : `def run_drills(*, policy_path=DEFAULT_POLICY, root=ROOT, now=None)`
- [notification_preview](../../service/fr/operations_preparation_18.py) — ligne 257 : `def notification_preview(report)`
- [main](../../service/fr/operations_preparation_18.py) — ligne 264 : `def main()`

## `service/fr/pilot_documents_16g.py`

Source SHA-256 : `2cb1bf9a10b9b812ef1cdbf843c28d761e98678659c40bf6858b95533a424c3d`

- [official_url](../../service/fr/pilot_documents_16g.py) — ligne 20 : `def official_url(url)`
- [NoRedirects](../../service/fr/pilot_documents_16g.py) — ligne 35 : `class NoRedirects(HTTPRedirectHandler)`
- [NoRedirects.redirect_request](../../service/fr/pilot_documents_16g.py) — ligne 36 : `def redirect_request(self, req, fp, code, msg, headers, newurl)`
- [fetch](../../service/fr/pilot_documents_16g.py) — ligne 40 : `def fetch(url)`
- [collect](../../service/fr/pilot_documents_16g.py) — ligne 53 : `def collect(inventory, output, *, root=ROOT, fetcher=fetch)`
- [main](../../service/fr/pilot_documents_16g.py) — ligne 108 : `def main()`

## `service/fr/portfolio_replay_12b.py`

Source SHA-256 : `e1243708ab9c7acfbfd238e507506f8575ebc6e806ec4884f22dcfba07ecb91a`

- [ReplayBlocked](../../service/fr/portfolio_replay_12b.py) — ligne 15 : `class ReplayBlocked(ValueError)`
- [ReplayBlocked.__init__](../../service/fr/portfolio_replay_12b.py) — ligne 18 : `def __init__(self, message, ledger)`
- [amount](../../service/fr/portfolio_replay_12b.py) — ligne 23 : `def amount(value)`
- [replay](../../service/fr/portfolio_replay_12b.py) — ligne 30 : `def replay(tape: dict, cost_profile: dict, eligibility_path, *, stress_multiplier=Decimal(1)) -> dict`

## `service/fr/preanchor_replay_16g.py`

Source SHA-256 : `65ee13b7c1e03c6ddc651123f829b970d7276f98f9632b198cf551342a01ca1c`

- [check_chain](../../service/fr/preanchor_replay_16g.py) — ligne 17 : `def check_chain(index, start, end)`
- [qualify](../../service/fr/preanchor_replay_16g.py) — ligne 27 : `def qualify(history, candidates, sessions, anomalies)`
- [run](../../service/fr/preanchor_replay_16g.py) — ligne 54 : `def run(packet_path, output_dir, *, root=ROOT, full_date='2026-09-12')`
- [main](../../service/fr/preanchor_replay_16g.py) — ligne 125 : `def main()`

## `service/fr/prediction_contract_16a.py`

Source SHA-256 : `1ea271d07d09030015319466fede2924b3b5a70a006476ecca6d03e59d0ca294`

- [scoped_path](../../service/fr/prediction_contract_16a.py) — ligne 24 : `def scoped_path(relative: str, root: Path) -> Path`
- [evidence](../../service/fr/prediction_contract_16a.py) — ligne 31 : `def evidence(relative: str, root: Path) -> dict`
- [prepare_manifest](../../service/fr/prediction_contract_16a.py) — ligne 36 : `def prepare_manifest(*, root: Path=ROOT) -> dict`
- [aware](../../service/fr/prediction_contract_16a.py) — ligne 78 : `def aware(value: str) -> datetime`
- [preflight](../../service/fr/prediction_contract_16a.py) — ligne 85 : `def preflight(manifest: dict, dataset: dict | None, *, root: Path=ROOT) -> dict`
- [main](../../service/fr/prediction_contract_16a.py) — ligne 181 : `def main() -> None`

## `service/fr/priority_evidence_12f.py`

Source SHA-256 : `147d848ce0ae5d2035b6cb155cba269bb1d394b2e9825be5dbc32fbbe2898df9`

- [run](../../service/fr/priority_evidence_12f.py) — ligne 12 : `def run(output: Path) -> dict`

## `service/fr/priority_review_12f.py`

Source SHA-256 : `e828f7012d43bbba0aa5f39421023ffff8873f6a467a50c079360986c63143d8`

- [priority_table](../../service/fr/priority_review_12f.py) — ligne 17 : `def priority_table(frame: pd.DataFrame) -> pd.DataFrame`
- [verified_sources](../../service/fr/priority_review_12f.py) — ligne 33 : `def verified_sources(source_root: Path) -> dict`
- [run](../../service/fr/priority_review_12f.py) — ligne 44 : `def run(output: Path, source_root: Path, intentions: Path) -> dict`

## `service/fr/prospective_window_16g.py`

Source SHA-256 : `e99391c56ec2101c09ce97fcf396bf83fa2302e545ca786b735c1bd8bcde5ee9`

- [window](../../service/fr/prospective_window_16g.py) — ligne 16 : `def window(calendar, anchor, count)`
- [validate](../../service/fr/prospective_window_16g.py) — ligne 28 : `def validate(protocol)`
- [prepare](../../service/fr/prospective_window_16g.py) — ligne 42 : `def prepare(protocol, *, root=ROOT, now=None, calendar=None, phase='prepare')`
- [main](../../service/fr/prospective_window_16g.py) — ligne 121 : `def main()`

## `service/fr/provider_exploratory_13b.py`

Source SHA-256 : `35f9a645487b43514d3f34d6c59791f518633f351788cbf026103c79220a8ca0`

- [write_json](../../service/fr/provider_exploratory_13b.py) — ligne 24 : `def write_json(path, payload)`
- [repair_prices](../../service/fr/provider_exploratory_13b.py) — ligne 28 : `def repair_prices(rows, symbol, repairs)`
- [repair_dividend](../../service/fr/provider_exploratory_13b.py) — ligne 38 : `def repair_dividend(row, symbol, repairs)`
- [load_frozen](../../service/fr/provider_exploratory_13b.py) — ligne 53 : `def load_frozen(config)`
- [build_shared](../../service/fr/provider_exploratory_13b.py) — ligne 77 : `def build_shared(scores, cfg, archive, fold, repairs=None)`
- [run](../../service/fr/provider_exploratory_13b.py) — ligne 160 : `def run(output: Path, config_path: Path)`

## `service/fr/provider_exploratory_engine_13b.py`

Source SHA-256 : `3fea324913f5163cbefea49e02937310449437aa06456f6e5cb0c4d027be2821`

- [ReplayBlocked](../../service/fr/provider_exploratory_engine_13b.py) — ligne 14 : `class ReplayBlocked(ValueError)`
- [ReplayBlocked.__init__](../../service/fr/provider_exploratory_engine_13b.py) — ligne 17 : `def __init__(self, message, ledger)`
- [amount](../../service/fr/provider_exploratory_engine_13b.py) — ligne 22 : `def amount(value)`
- [replay_assumed](../../service/fr/provider_exploratory_engine_13b.py) — ligne 29 : `def replay_assumed(tape: dict, cost_profile: dict, tax_scenario, *, stress_multiplier=Decimal(1)) -> dict`
- [resolve_assumed_liability](../../service/fr/provider_exploratory_engine_13b.py) — ligne 256 : `def resolve_assumed_liability(scenario, ticker, settlement_date)`

## `service/fr/provider_exploratory_metrics_13b.py`

Source SHA-256 : `d3e273b011a4f30bc08b350456c2ebf26315fc8c53f72cb237e914e56baf5f82`

- [ledger_metrics](../../service/fr/provider_exploratory_metrics_13b.py) — ligne 5 : `def ledger_metrics(result: dict, *, data_kind: str) -> dict`

## `service/fr/provider_repairs_13c.py`

Source SHA-256 : `42a56aa493dbd1cb1f87d89634cced85bb4dfa2a9a1c9a877d1226774fabb300`

- [public_sources](../../service/fr/provider_repairs_13c.py) — ligne 16 : `def public_sources(output)`
- [price_overlay](../../service/fr/provider_repairs_13c.py) — ligne 34 : `def price_overlay(refresh)`
- [supplement_payments](../../service/fr/provider_repairs_13c.py) — ligne 54 : `def supplement_payments(output, source=Path('config/research_fr/public_payment_review_13c.json'))`
- [collect](../../service/fr/provider_repairs_13c.py) — ligne 68 : `def collect(output)`

## `service/fr/public_evidence_requests.py`

Source SHA-256 : `907f92d147771a3f75004a9003c3092393ea935e601c214455334583824919dd`

- [request_packet](../../service/fr/public_evidence_requests.py) — ligne 55 : `def request_packet(paths: pd.DataFrame, tax: pd.DataFrame, identities: list[dict], events: list[dict]) -> dict`
- [run](../../service/fr/public_evidence_requests.py) — ligne 92 : `def run(output: Path, qualification: Path, evidence: Path, *, collect: bool=True) -> dict`

## `service/fr/publish_daily_bars_staging.py`

Source SHA-256 : `b2908333576151e1b041413756a6863945554d8344336c00080b28b200f65268`

- [timestamp](../../service/fr/publish_daily_bars_staging.py) — ligne 29 : `def timestamp(value)`
- [prepare](../../service/fr/publish_daily_bars_staging.py) — ligne 38 : `def prepare(root, symbols, start, end)`
- [assert_fr](../../service/fr/publish_daily_bars_staging.py) — ligne 104 : `def assert_fr(conn)`
- [publish_payload](../../service/fr/publish_daily_bars_staging.py) — ligne 109 : `def publish_payload(conn, payload, *, run_id, published_at)`
- [run](../../service/fr/publish_daily_bars_staging.py) — ligne 154 : `def run(*, start, end, write=False, root=None, identities=None, output=None, selected_symbols=None)`
- [main](../../service/fr/publish_daily_bars_staging.py) — ligne 249 : `def main()`

## `service/fr/qualification_dossier_16g.py`

Source SHA-256 : `47619255154ad46ea418956567a986415392c16a7ea5f7406044c856dc1e5a4c`

- [read_proof](../../service/fr/qualification_dossier_16g.py) — ligne 19 : `def read_proof(path)`
- [build](../../service/fr/qualification_dossier_16g.py) — ligne 24 : `def build(report_path, *, root=ROOT, now=None)`
- [inspect_anchor](../../service/fr/qualification_dossier_16g.py) — ligne 98 : `def inspect_anchor(dossier, anchor_dir, *, root=ROOT)`
- [main](../../service/fr/qualification_dossier_16g.py) — ligne 158 : `def main()`

## `service/fr/release_review_16g3.py`

Source SHA-256 : `a1c30a3a1a8f25d1bcc5de720538d059132b265609e15cb365fbd386b72a4a73`

- [effective_events](../../service/fr/release_review_16g3.py) — ligne 19 : `def effective_events(payloads, symbol, sessions)`
- [validate_review](../../service/fr/release_review_16g3.py) — ligne 44 : `def validate_review(review, packet_hash, *, now=None, packet_created_at=None)`
- [packet](../../service/fr/release_review_16g3.py) — ligne 70 : `def packet(confirmation_report, replay_report, *, root=ROOT)`
- [main](../../service/fr/release_review_16g3.py) — ligne 145 : `def main()`

## `service/fr/release_review_check_16g.py`

Source SHA-256 : `c2b4dd7b1a29822d5ef6c010ffb8f645820f846f6bb0662c882d17320db782b3`

- [check](../../service/fr/release_review_check_16g.py) — ligne 15 : `def check(packet_path, review_path=None, *, root=ROOT, now=None)`
- [main](../../service/fr/release_review_check_16g.py) — ligne 81 : `def main()`

## `service/fr/research_catalog_14a.py`

Source SHA-256 : `0f7a09beb4c594bcc6f354594473ece059db42cf8963f3aa0d3c3d215ff76b96`

- [load_campaign](../../service/fr/research_catalog_14a.py) — ligne 20 : `def load_campaign(identifier: str, *, root: Path=RESEARCH) -> dict`
- [economic_rows](../../service/fr/research_catalog_14a.py) — ligne 57 : `def economic_rows(campaign: dict) -> list[dict]`
- [main](../../service/fr/research_catalog_14a.py) — ligne 80 : `def main() -> None`

## `service/fr/research_replay_14b.py`

Source SHA-256 : `ff326607b8ba3b29a63772e31d07966de1d6adb8714ac521f1274baaa966cfdb`

- [FRResearchReplayOptions](../../service/fr/research_replay_14b.py) — ligne 19 : `class FRResearchReplayOptions`
- [validate_options](../../service/fr/research_replay_14b.py) — ligne 30 : `def validate_options(options: FRResearchReplayOptions, *, require_output=False) -> None`
- [preflight](../../service/fr/research_replay_14b.py) — ligne 51 : `def preflight(options: FRResearchReplayOptions) -> dict`
- [latest_progress_event](../../service/fr/research_replay_14b.py) — ligne 86 : `def latest_progress_event(journal: str) -> dict | None`
- [run](../../service/fr/research_replay_14b.py) — ligne 99 : `def run(options: FRResearchReplayOptions) -> dict`
- [main](../../service/fr/research_replay_14b.py) — ligne 167 : `def main()`

## `service/fr/robustness_13d.py`

Source SHA-256 : `6685492876e8d4f3d3e9eb04e31826c80a88aa4967c967928e8196afc2c9d8c3`

- [delayed_tape](../../service/fr/robustness_13d.py) — ligne 26 : `def delayed_tape(tape, delay)`
- [run](../../service/fr/robustness_13d.py) — ligne 48 : `def run(source, output)`

## `service/fr/robustness_engine_13d.py`

Source SHA-256 : `844f05ee828bafbaf780f43758e95ebd81b2dacfeb0820fd260f423fed0247d5`

- [ReplayBlocked](../../service/fr/robustness_engine_13d.py) — ligne 15 : `class ReplayBlocked(ValueError)`
- [ReplayBlocked.__init__](../../service/fr/robustness_engine_13d.py) — ligne 18 : `def __init__(self, message, ledger)`
- [amount](../../service/fr/robustness_engine_13d.py) — ligne 23 : `def amount(value)`
- [replay_assumed](../../service/fr/robustness_engine_13d.py) — ligne 30 : `def replay_assumed(tape: dict, cost_profile: dict, tax_scenario, *, stress_multiplier=Decimal(1), position_cap_pct=None) -> dict`
- [resolve_assumed_liability](../../service/fr/robustness_engine_13d.py) — ligne 262 : `def resolve_assumed_liability(scenario, ticker, settlement_date)`

## `service/fr/security_master_daily_15e.py`

Source SHA-256 : `0378520b16d1327cd515444a60db2ca5d96b6f2b3ec7b5b03f59df479e954e18`

- [validate_index](../../service/fr/security_master_daily_15e.py) — ligne 25 : `def validate_index(rows, start, end)`
- [delta_index](../../service/fr/security_master_daily_15e.py) — ligne 53 : `def delta_index(start, end, context)`
- [initial_checkpoint](../../service/fr/security_master_daily_15e.py) — ligne 74 : `def initial_checkpoint(base, identities, base_hash)`
- [advance](../../service/fr/security_master_daily_15e.py) — ligne 89 : `def advance(prior, paths, *, end, observed_at)`
- [collect](../../service/fr/security_master_daily_15e.py) — ligne 119 : `def collect(cfg, result, *, root, identities, base_path, dry_run=False, today=None)`
- [main](../../service/fr/security_master_daily_15e.py) — ligne 186 : `def main()`

## `service/fr/sprint5_gate.py`

Source SHA-256 : `5a525515be908f249715c712af07aa5ec5ccd6047522fd6357e6d1fa7caedeea`

- [evaluate](../../service/fr/sprint5_gate.py) — ligne 17 : `def evaluate(root: Path) -> dict`
- [main](../../service/fr/sprint5_gate.py) — ligne 94 : `def main() -> None`

## `service/fr/sprint5_limited_manifest.py`

Source SHA-256 : `7905056e04282e264f66bed24162a8b1f6a259971b74887955d4cae75982db4e`

- [_sha256](../../service/fr/sprint5_limited_manifest.py) — ligne 28 : `def _sha256(path: Path) -> str`
- [_price_windows](../../service/fr/sprint5_limited_manifest.py) — ligne 36 : `def _price_windows(yahoo_report: dict, euronext_dir: Path, euronext_delisted_report: dict | None=None) -> dict[str, list[dict]]`
- [price_proof](../../service/fr/sprint5_limited_manifest.py) — ligne 85 : `def price_proof(symbol: str, day: str, windows: dict[str, list[dict]]) -> tuple[bool, bool, list[str]]`
- [reference_state](../../service/fr/sprint5_limited_manifest.py) — ligne 102 : `def reference_state(day: str, markets: list[dict], missing_days: set[str], first_full: str) -> dict`
- [passes_survivorship_gate](../../service/fr/sprint5_limited_manifest.py) — ligne 131 : `def passes_survivorship_gate(status_counts: Counter, total: int, *, minimum_delisted: int, minimum_delisted_ratio: float) -> bool`
- [_bar_rows](../../service/fr/sprint5_limited_manifest.py) — ligne 139 : `def _bar_rows(root: Path, symbol: str) -> Iterable[dict]`
- [build_manifest](../../service/fr/sprint5_limited_manifest.py) — ligne 151 : `def build_manifest(*, history: dict, subset: dict, archive_root: Path, yahoo_report: dict, euronext_dir: Path, euronext_delisted_report: dict | None=None, policy: dict, output_jsonl_gz: Path) -> dict`
- [main](../../service/fr/sprint5_limited_manifest.py) — ligne 320 : `def main() -> None`

## `service/fr/sprint5_subset_audit.py`

Source SHA-256 : `e0f003b81f434b37eb8c7ed6f182acc6cab9cf871bf3116cb9fbd6ec0a0a4e69`

- [valid_isin](../../service/fr/sprint5_subset_audit.py) — ligne 24 : `def valid_isin(value: str | None) -> bool`
- [qualify](../../service/fr/sprint5_subset_audit.py) — ligne 41 : `def qualify(rows: list[dict], bars: dict[str, dict], actions: dict[str, dict]) -> dict`
- [run](../../service/fr/sprint5_subset_audit.py) — ligne 114 : `def run(output: Path) -> dict`
- [main](../../service/fr/sprint5_subset_audit.py) — ligne 151 : `def main() -> None`

## `service/fr/tape_reporting_13b.py`

Source SHA-256 : `eca34ee095fe1d2380ffe009d320579cfcfba11460f3fbd65d84d9520ed1da02`

- [validate_intents](../../service/fr/tape_reporting_13b.py) — ligne 19 : `def validate_intents(intents, cfg)`
- [assemble_tape](../../service/fr/tape_reporting_13b.py) — ligne 33 : `def assemble_tape(shared: dict, intentions: pd.DataFrame, cfg: dict, fold: int, policy: str) -> dict`
- [ledger_metrics](../../service/fr/tape_reporting_13b.py) — ligne 80 : `def ledger_metrics(result: dict, *, data_kind: str) -> dict`
- [prepare](../../service/fr/tape_reporting_13b.py) — ligne 139 : `def prepare(output: Path, frozen: Path) -> dict`

## `service/fr/technical_counter_review_16g.py`

Source SHA-256 : `975aa4ef9c8596fd5562c6543951110f0311e941841aba288ad8dc9c451b3d5f`

- [TargetReader](../../service/fr/technical_counter_review_16g.py) — ligne 31 : `class TargetReader(ContentHandler)`
- [TargetReader.__init__](../../service/fr/technical_counter_review_16g.py) — ligne 33 : `def __init__(self, pairs)`
- [TargetReader.startElement](../../service/fr/technical_counter_review_16g.py) — ligne 38 : `def startElement(self, name, attrs)`
- [TargetReader.characters](../../service/fr/technical_counter_review_16g.py) — ligne 49 : `def characters(self, content)`
- [TargetReader.endElement](../../service/fr/technical_counter_review_16g.py) — ligne 52 : `def endElement(self, name)`
- [scan](../../service/fr/technical_counter_review_16g.py) — ligne 67 : `def scan(path, pairs)`
- [publication_check](../../service/fr/technical_counter_review_16g.py) — ligne 82 : `def publication_check(files, start, end)`
- [run](../../service/fr/technical_counter_review_16g.py) — ligne 110 : `def run(packet_path, *, root=ROOT, progress=None)`
- [main](../../service/fr/technical_counter_review_16g.py) — ligne 159 : `def main()`

## `service/fr/trading212_demo_17b.py`

Source SHA-256 : `76a8f3794ad0147900fa80c5cb212539e6bcc25dc6bd204f90f3091bc51672d9`

- [SafeReadError](../../service/fr/trading212_demo_17b.py) — ligne 26 : `class SafeReadError(RuntimeError)`
- [DemoReader](../../service/fr/trading212_demo_17b.py) — ligne 30 : `class DemoReader`
- [DemoReader.__init__](../../service/fr/trading212_demo_17b.py) — ligne 31 : `def __init__(self, key, secret, session=None)`
- [DemoReader.get](../../service/fr/trading212_demo_17b.py) — ligne 38 : `def get(self, name)`
- [DemoReader.close](../../service/fr/trading212_demo_17b.py) — ligne 75 : `def close(self)`
- [match_instruments](../../service/fr/trading212_demo_17b.py) — ligne 79 : `def match_instruments(matrix, instruments, exchanges)`
- [run](../../service/fr/trading212_demo_17b.py) — ligne 105 : `def run(*, output_dir, packet=DEFAULT_PACKET, root=ROOT, reader=None)`
- [main](../../service/fr/trading212_demo_17b.py) — ligne 173 : `def main()`

## `service/fr/trading212_durable_17e.py`

Source SHA-256 : `4c903ad2acfa4b1eb0bcb71e5c5c96daf8c51f107b8d6688d5941982ec770574`

- [canonical](../../service/fr/trading212_durable_17e.py) — ligne 15 : `def canonical(value)`
- [JournalBlocked](../../service/fr/trading212_durable_17e.py) — ligne 19 : `class JournalBlocked(RuntimeError)`
- [FakeTransport](../../service/fr/trading212_durable_17e.py) — ligne 23 : `class FakeTransport`
- [FakeTransport.__init__](../../service/fr/trading212_durable_17e.py) — ligne 25 : `def __init__(self, outcome='accepted')`
- [FakeTransport.submit](../../service/fr/trading212_durable_17e.py) — ligne 31 : `def submit(self, intent_id)`
- [DurableSyntheticJournal](../../service/fr/trading212_durable_17e.py) — ligne 41 : `class DurableSyntheticJournal`
- [DurableSyntheticJournal.__init__](../../service/fr/trading212_durable_17e.py) — ligne 45 : `def __init__(self, *, directory, max_intent_notional_eur, root=ROOT)`
- [DurableSyntheticJournal._config](../../service/fr/trading212_durable_17e.py) — ligne 89 : `def _config(self)`
- [DurableSyntheticJournal._acquire](../../service/fr/trading212_durable_17e.py) — ligne 94 : `def _acquire(self)`
- [DurableSyntheticJournal._ensure](../../service/fr/trading212_durable_17e.py) — ligne 111 : `def _ensure(self)`
- [DurableSyntheticJournal._apply](../../service/fr/trading212_durable_17e.py) — ligne 116 : `def _apply(state, event)`
- [DurableSyntheticJournal._append](../../service/fr/trading212_durable_17e.py) — ligne 139 : `def _append(self, event)`
- [DurableSyntheticJournal._change](../../service/fr/trading212_durable_17e.py) — ligne 155 : `def _change(self, event)`
- [DurableSyntheticJournal._change_locked](../../service/fr/trading212_durable_17e.py) — ligne 159 : `def _change_locked(self, event)`
- [DurableSyntheticJournal.register](../../service/fr/trading212_durable_17e.py) — ligne 178 : `def register(self, intent)`
- [DurableSyntheticJournal.submit_fake](../../service/fr/trading212_durable_17e.py) — ligne 184 : `def submit_fake(self, intent_id, transport)`
- [DurableSyntheticJournal._submit_fake_locked](../../service/fr/trading212_durable_17e.py) — ligne 188 : `def _submit_fake_locked(self, intent_id, transport)`
- [DurableSyntheticJournal.observe](../../service/fr/trading212_durable_17e.py) — ligne 198 : `def observe(self, intent_id, *, broker_id, status, filled, sequence)`
- [DurableSyntheticJournal.request_cancel](../../service/fr/trading212_durable_17e.py) — ligne 203 : `def request_cancel(self, intent_id)`
- [DurableSyntheticJournal.kill](../../service/fr/trading212_durable_17e.py) — ligne 206 : `def kill(self)`
- [DurableSyntheticJournal.snapshot](../../service/fr/trading212_durable_17e.py) — ligne 209 : `def snapshot(self, intent_id)`
- [DurableSyntheticJournal.close](../../service/fr/trading212_durable_17e.py) — ligne 214 : `def close(self)`
- [DurableSyntheticJournal.__enter__](../../service/fr/trading212_durable_17e.py) — ligne 220 : `def __enter__(self)`
- [DurableSyntheticJournal.__exit__](../../service/fr/trading212_durable_17e.py) — ligne 223 : `def __exit__(self, *_)`

## `service/fr/trading212_mapping_17c.py`

Source SHA-256 : `a671aff3d4a9bd2dfd8cba305585f2a4837dc86daa4c343865bd900ea9868267`

- [qualify](../../service/fr/trading212_mapping_17c.py) — ligne 13 : `def qualify(rows)`
- [run](../../service/fr/trading212_mapping_17c.py) — ligne 45 : `def run(*, snapshot_dir, output_dir, root=ROOT)`
- [main](../../service/fr/trading212_mapping_17c.py) — ligne 91 : `def main()`

## `service/fr/trading212_protection_17f.py`

Source SHA-256 : `05dbeeca48cd1d2417133d4ac5e6c63bbfdc3288e16d5c84c1a6d7eb82879156`

- [quantity](../../service/fr/trading212_protection_17f.py) — ligne 8 : `def quantity(value, name)`
- [ExitLeg](../../service/fr/trading212_protection_17f.py) — ligne 15 : `class ExitLeg`
- [ExitLeg.validate](../../service/fr/trading212_protection_17f.py) — ligne 23 : `def validate(self)`
- [ExitLeg.potentially_executable](../../service/fr/trading212_protection_17f.py) — ligne 42 : `def potentially_executable(self)`
- [audit_protection](../../service/fr/trading212_protection_17f.py) — ligne 47 : `def audit_protection(*, entry_filled, position_quantity, legs, position_reconciled, entry_terminal, context='fr_simulated')`
- [replacement_preflight](../../service/fr/trading212_protection_17f.py) — ligne 103 : `def replacement_preflight(*, entry_filled, position_quantity, legs, old_broker_id, position_reconciled, entry_terminal)`
- [readiness](../../service/fr/trading212_protection_17f.py) — ligne 126 : `def readiness()`

## `service/fr/trading212_reconciliation_17d.py`

Source SHA-256 : `311855bc6ffb8413a27c603b972e0ea63ef19a9ee698db954d937ebfeccf6a7f`

- [OrderEvidence](../../service/fr/trading212_reconciliation_17d.py) — ligne 18 : `class OrderEvidence`
- [SyntheticOrderJournal](../../service/fr/trading212_reconciliation_17d.py) — ligne 30 : `class SyntheticOrderJournal`
- [SyntheticOrderJournal.__init__](../../service/fr/trading212_reconciliation_17d.py) — ligne 35 : `def __init__(self, max_intent_notional_eur: Decimal)`
- [SyntheticOrderJournal.register](../../service/fr/trading212_reconciliation_17d.py) — ligne 45 : `def register(self, intent: FrenchTestIntent)`
- [SyntheticOrderJournal.begin_dispatch](../../service/fr/trading212_reconciliation_17d.py) — ligne 55 : `def begin_dispatch(self, intent_id)`
- [SyntheticOrderJournal.submission_timeout](../../service/fr/trading212_reconciliation_17d.py) — ligne 65 : `def submission_timeout(self, intent_id)`
- [SyntheticOrderJournal.observe](../../service/fr/trading212_reconciliation_17d.py) — ligne 73 : `def observe(self, intent_id, *, broker_id, status, filled: Decimal, sequence: int)`
- [SyntheticOrderJournal.request_cancel](../../service/fr/trading212_reconciliation_17d.py) — ligne 118 : `def request_cancel(self, intent_id)`
- [SyntheticOrderJournal.kill](../../service/fr/trading212_reconciliation_17d.py) — ligne 127 : `def kill(self)`
- [SyntheticOrderJournal.snapshot](../../service/fr/trading212_reconciliation_17d.py) — ligne 135 : `def snapshot(self, intent_id)`

## `service/fr/universe_contract_6a.py`

Source SHA-256 : `078caab9f03377fc86cd8660fe88dd400461c45499bdeade54acab76c9b41489`

- [_sha256](../../service/fr/universe_contract_6a.py) — ligne 26 : `def _sha256(path: Path) -> str`
- [_fingerprint](../../service/fr/universe_contract_6a.py) — ligne 34 : `def _fingerprint(value: Any) -> str`
- [_resolve_path](../../service/fr/universe_contract_6a.py) — ligne 39 : `def _resolve_path(value: str | Path, *, root: Path=ROOT) -> Path`
- [FRUniversePolicy](../../service/fr/universe_contract_6a.py) — ligne 45 : `class FRUniversePolicy`
- [FRUniversePolicy.from_yaml](../../service/fr/universe_contract_6a.py) — ligne 66 : `def from_yaml(cls, path: Path) -> 'FRUniversePolicy'`
- [FRUniversePolicy.validate](../../service/fr/universe_contract_6a.py) — ligne 96 : `def validate(self) -> None`
- [ScopeDecision](../../service/fr/universe_contract_6a.py) — ligne 123 : `class ScopeDecision`
- [classify_manifest_row](../../service/fr/universe_contract_6a.py) — ligne 136 : `def classify_manifest_row(row: dict[str, Any], policy: FRUniversePolicy) -> ScopeDecision`
- [audit_contract](../../service/fr/universe_contract_6a.py) — ligne 178 : `def audit_contract(policy: FRUniversePolicy, *, source_report_path: Path | None=None, source_manifest_path: Path | None=None) -> dict[str, Any]`
- [_atomic_json](../../service/fr/universe_contract_6a.py) — ligne 254 : `def _atomic_json(path: Path, payload: dict[str, Any]) -> None`
- [main](../../service/fr/universe_contract_6a.py) — ligne 264 : `def main() -> None`

## `service/fr/universe_liquidity_6b.py`

Source SHA-256 : `c1070b433754bef91bd04ca3e66f1c002d88811b09223f8ceb72d3dc847ee06b`

- [_resolve_path](../../service/fr/universe_liquidity_6b.py) — ligne 21 : `def _resolve_path(value: str | Path) -> Path`
- [FRLiquidityPolicy](../../service/fr/universe_liquidity_6b.py) — ligne 27 : `class FRLiquidityPolicy`
- [FRLiquidityPolicy.from_yaml](../../service/fr/universe_liquidity_6b.py) — ligne 54 : `def from_yaml(cls, path: Path) -> 'FRLiquidityPolicy'`
- [FRLiquidityPolicy.validate](../../service/fr/universe_liquidity_6b.py) — ligne 91 : `def validate(self) -> None`
- [_iter_manifest](../../service/fr/universe_liquidity_6b.py) — ligne 118 : `def _iter_manifest(path: Path) -> Iterator[dict[str, Any]]`
- [_load_symbol_bars](../../service/fr/universe_liquidity_6b.py) — ligne 124 : `def _load_symbol_bars(archive_root: Path, symbol: str) -> dict[str, dict[str, Any]]`
- [build_symbol_snapshots](../../service/fr/universe_liquidity_6b.py) — ligne 150 : `def build_symbol_snapshots(*, symbol: str, manifest_rows: Iterable[dict[str, Any]], bars_by_date: dict[str, dict[str, Any]], policy: FRLiquidityPolicy, session_index: dict[date, int], sessions: list[date]) -> list[dict[str, Any]]`
- [_validate_source](../../service/fr/universe_liquidity_6b.py) — ligne 233 : `def _validate_source(policy: FRLiquidityPolicy, report_path: Path, manifest_path: Path) -> tuple[str, int]`
- [build_liquidity_artifact](../../service/fr/universe_liquidity_6b.py) — ligne 252 : `def build_liquidity_artifact(policy: FRLiquidityPolicy, *, output_root: Path, source_report_path: Path | None=None, source_manifest_path: Path | None=None, archive_root: Path | None=None) -> dict[str, Any]`
- [_snapshot_batches](../../service/fr/universe_liquidity_6b.py) — ligne 342 : `def _snapshot_batches(path: Path, size: int=5000) -> Iterator[list[dict[str, Any]]]`
- [persist_liquidity](../../service/fr/universe_liquidity_6b.py) — ligne 354 : `def persist_liquidity(report: dict[str, Any]) -> None`
- [main](../../service/fr/universe_liquidity_6b.py) — ligne 444 : `def main() -> None`

## `service/fr/universe_reference_6c.py`

Source SHA-256 : `a5ec06473476508e43776087f955f3bf906e222648e4e97f0e1489ce2d995c07`

- [resolve_path](../../service/fr/universe_reference_6c.py) — ligne 31 : `def resolve_path(value: str | Path) -> Path`
- [load_policy](../../service/fr/universe_reference_6c.py) — ligne 36 : `def load_policy(path: Path) -> dict[str, Any]`
- [build_identities](../../service/fr/universe_reference_6c.py) — ligne 58 : `def build_identities(symbols: list[str], history: dict[str, Any]) -> list[dict[str, Any]]`
- [sector_asof](../../service/fr/universe_reference_6c.py) — ligne 100 : `def sector_asof(memberships: list[dict], symbol: str, decision_at: datetime) -> dict`
- [build_benchmark](../../service/fr/universe_reference_6c.py) — ligne 136 : `def build_benchmark(snapshots: list[dict], bars: dict[str, dict[str, dict]], identities: dict[str, dict], sessions: list[date], config: dict) -> tuple[list[dict], list[dict]]`
- [_write_rows](../../service/fr/universe_reference_6c.py) — ligne 230 : `def _write_rows(path: Path, rows: list[dict]) -> None`
- [build_artifact](../../service/fr/universe_reference_6c.py) — ligne 243 : `def build_artifact(policy: dict, output: Path) -> dict`
- [persist](../../service/fr/universe_reference_6c.py) — ligne 340 : `def persist(report: dict) -> None`
- [main](../../service/fr/universe_reference_6c.py) — ligne 445 : `def main() -> None`

## `service/fr/usable_subset_qualification.py`

Source SHA-256 : `4ae20df65acfc3607dd9da3724beaa0228a7f186ff4fe9c8bf784a439a0c5f60`

- [classify](../../service/fr/usable_subset_qualification.py) — ligne 25 : `def classify(identity, diagnostic, resolution, *, missing, retained, nonpositive, sql_missing, archive_errors)`
- [run](../../service/fr/usable_subset_qualification.py) — ligne 61 : `def run(output: Path, *, decision_day: date, bootstrap: Path, start: date)`
- [main](../../service/fr/usable_subset_qualification.py) — ligne 164 : `def main()`

## `service/fr/validation_protocol_13a.py`

Source SHA-256 : `9aa1e01e4e9cb64e62d6cfd12e83bfb4cf185e628743bde11c5d22efd14cce8f`

- [build_protocol](../../service/fr/validation_protocol_13a.py) — ligne 15 : `def build_protocol(cfg: dict) -> dict`
- [inspect_scope](../../service/fr/validation_protocol_13a.py) — ligne 39 : `def inspect_scope(paths: pd.DataFrame, intents: pd.DataFrame, cfg: dict) -> dict`
- [run](../../service/fr/validation_protocol_13a.py) — ligne 60 : `def run(output: Path, *, scope: Path, preflight: Path, protocol_path=Path('config/research_fr/economic_references_11a_v1.yaml'), costs=Path('config/markets/fr_execution_research_v1.yaml'), eligibility=Path('config/taxes/fr_ttf_eligibility.yaml')) -> dict`

## `service/fr/yahoo_price_reference_pilot.py`

Source SHA-256 : `c9f852702a74d677c5aa1e9404faa5e019e496a73be88535f37f0b85aacf3661`

- [verified_tls_context](../../service/fr/yahoo_price_reference_pilot.py) — ligne 27 : `def verified_tls_context() -> ssl.SSLContext`
- [_epoch](../../service/fr/yahoo_price_reference_pilot.py) — ligne 48 : `def _epoch(day: date) -> int`
- [chart_url](../../service/fr/yahoo_price_reference_pilot.py) — ligne 52 : `def chart_url(symbol: str, start: date, end: date) -> str`
- [fetch_chart](../../service/fr/yahoo_price_reference_pilot.py) — ligne 64 : `def fetch_chart(symbol: str, start: date, end: date, *, timeout: float=30, urlopen: Callable=request.urlopen) -> dict`
- [normalize_chart](../../service/fr/yahoo_price_reference_pilot.py) — ligne 78 : `def normalize_chart(payload: dict) -> tuple[dict[str, dict], dict]`
- [compare](../../service/fr/yahoo_price_reference_pilot.py) — ligne 120 : `def compare(reference: dict[str, dict], provider_rows: list[dict], *, start: str, end: str, tolerance: float=0.0001) -> dict`
- [audit_symbol](../../service/fr/yahoo_price_reference_pilot.py) — ligne 164 : `def audit_symbol(root: Path, cache_dir: Path, symbol: str, *, start: date, end: date, timeout: float=30, force: bool=False) -> dict`
- [main](../../service/fr/yahoo_price_reference_pilot.py) — ligne 201 : `def main() -> None`

## `service/fred/__init__.py`

Source SHA-256 : `fbb203ad39411b79fa715ecb0aa4ff6a8c684b3cad02d3591d2e1061cef8a04b`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `service/fred/clientFred.py`

Source SHA-256 : `7aea554fdbf83ea23aab95ab2ff180664453b631849fa3e97f43d23ce2c4f6a6`

- [FredFetchError](../../service/fred/clientFred.py) — ligne 20 : `class FredFetchError(RuntimeError)`
- [_retry_policy](../../service/fred/clientFred.py) — ligne 24 : `def _retry_policy() -> RetryPolicy`
- [_resolve_api_key](../../service/fred/clientFred.py) — ligne 33 : `def _resolve_api_key(api_key_env: str=DEFAULT_API_KEY_ENV) -> str`
- [fetch_series_observations](../../service/fred/clientFred.py) — ligne 40 : `def fetch_series_observations(series_id: str, *, start: str | None=None, end: str | None=None, api_key_env: str=DEFAULT_API_KEY_ENV, session: Optional[requests.Session]=None, base_url: str=FRED_API_BASE_URL) -> list[dict[str, Any]]`

## `service/ibkr/__init__.py`

Source SHA-256 : `8b17a06a4bf13115591577d6522da9aaa4ab650e74762be8982c4cade399a3b9`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `service/ibkr/client.py`

Source SHA-256 : `633609baeb192923723db0927c3ecdc82bcc6b007711a855ba20ba966a2d4954`

- [IBKRUnavailableError](../../service/ibkr/client.py) — ligne 27 : `class IBKRUnavailableError(RuntimeError)`
- [IBKRBrokerClient](../../service/ibkr/client.py) — ligne 31 : `class IBKRBrokerClient`
- [IBKRBrokerClient.__init__](../../service/ibkr/client.py) — ligne 36 : `def __init__(self, *, host: str='127.0.0.1', port: int=7497, client_id: int=1, readonly: bool=True) -> None`
- [IBKRBrokerClient.get_account](../../service/ibkr/client.py) — ligne 65 : `def get_account(self) -> AccountSnapshot`
- [IBKRBrokerClient.get_positions](../../service/ibkr/client.py) — ligne 79 : `def get_positions(self) -> list[BrokerPosition]`
- [IBKRBrokerClient.get_orders](../../service/ibkr/client.py) — ligne 94 : `def get_orders(self, status: str='all', since: datetime | None=None) -> list[BrokerOrderSnapshot]`
- [IBKRBrokerClient.submit_order](../../service/ibkr/client.py) — ligne 115 : `def submit_order(self, request: OrderRequest) -> BrokerOrderSnapshot`
- [IBKRBrokerClient.cancel_order](../../service/ibkr/client.py) — ligne 158 : `def cancel_order(self, order_id: str) -> bool`
- [IBKRBrokerClient.stream_trades](../../service/ibkr/client.py) — ligne 173 : `def stream_trades(self, callback: Callable[[BrokerOrderSnapshot], None]) -> Any`
- [IBKRBrokerClient._build_contract](../../service/ibkr/client.py) — ligne 200 : `def _build_contract(self, symbol: str, *, sec_type: str='STK', currency: str='USD', exchange: str='SMART', primary_exchange: str='NASDAQ') -> Any`
- [IBKRBrokerClient._build_order](../../service/ibkr/client.py) — ligne 215 : `def _build_order(self, req: OrderRequest) -> Any`
- [IBKRBrokerClient._snapshot_from_trade](../../service/ibkr/client.py) — ligne 246 : `def _snapshot_from_trade(self, trade: Any, request: OrderRequest | None) -> BrokerOrderSnapshot`
- [IBKRBrokerClient.close](../../service/ibkr/client.py) — ligne 267 : `def close(self) -> None`
- [_map_ibkr_status](../../service/ibkr/client.py) — ligne 274 : `def _map_ibkr_status(s: str) -> str`

## `service/ibkr/credentials.py`

Source SHA-256 : `8b8575175bb36f88bf185492b9f3c2f565e15ed06749093a090bbf36fb2ffd77`

- [IBKRCredentials](../../service/ibkr/credentials.py) — ligne 13 : `class IBKRCredentials`
- [get_ibkr_credentials](../../service/ibkr/credentials.py) — ligne 19 : `def get_ibkr_credentials() -> IBKRCredentials`

## `service/inpi/__init__.py`

Source SHA-256 : `649117e5dc7cc957739e2ea2f00baf1b978213f2711ce51afeadcf77910f2de8`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `service/inpi/accounts_pilot.py`

Source SHA-256 : `faaff2b29e95a53bcbf2d9d9390574f8aeeade937359c4bd93ae79790caec3ea`

- [normal_name](../../service/inpi/accounts_pilot.py) — ligne 22 : `def normal_name(value)`
- [number](../../service/inpi/accounts_pilot.py) — ligne 27 : `def number(value)`
- [accounting_checks](../../service/inpi/accounts_pilot.py) — ligne 39 : `def accounting_checks(payload, siren)`
- [collect_pages](../../service/inpi/accounts_pilot.py) — ligne 79 : `def collect_pages(client, siren, kind, max_pages=4)`
- [validate_manifest](../../service/inpi/accounts_pilot.py) — ligne 96 : `def validate_manifest(manifest)`
- [run](../../service/inpi/accounts_pilot.py) — ligne 112 : `def run(client, manifest, folder)`
- [main](../../service/inpi/accounts_pilot.py) — ligne 170 : `def main()`

## `service/inpi/accounts_smoke.py`

Source SHA-256 : `70a37ddc66516654ea5e507c3c9c5acc5fb622a2f30b5b4e8dee68045c281e6e`

- [summary](../../service/inpi/accounts_smoke.py) — ligne 13 : `def summary(payload, siren)`
- [run](../../service/inpi/accounts_smoke.py) — ligne 31 : `def run(client, *, siren='438479941')`
- [main](../../service/inpi/accounts_smoke.py) — ligne 57 : `def main()`

## `service/inpi/client.py`

Source SHA-256 : `46ae7d6993c5d8c2a74d049b7f7e613bfe58924f35368220186d35a12391e1a7`

- [InpiError](../../service/inpi/client.py) — ligne 15 : `class InpiError(RuntimeError)`
- [credential](../../service/inpi/client.py) — ligne 19 : `def credential(name)`
- [NoRedirect](../../service/inpi/client.py) — ligne 32 : `class NoRedirect(urllib.request.HTTPRedirectHandler)`
- [NoRedirect.redirect_request](../../service/inpi/client.py) — ligne 33 : `def redirect_request(self, req, fp, code, msg, headers, newurl)`
- [InpiClient](../../service/inpi/client.py) — ligne 37 : `class InpiClient`
- [InpiClient.__init__](../../service/inpi/client.py) — ligne 38 : `def __init__(self, *, username_env='INPI_USERNAME', password_env='INPI_PASSWORD', opener=None)`
- [InpiClient._request](../../service/inpi/client.py) — ligne 44 : `def _request(self, path, *, data=None, authenticated=True)`
- [InpiClient.login](../../service/inpi/client.py) — ligne 69 : `def login(self)`
- [InpiClient.accounts](../../service/inpi/client.py) — ligne 77 : `def accounts(self, siren, *, kind='bilans-saisis', page_size=3, search_after=None)`
- [InpiClient.account](../../service/inpi/client.py) — ligne 90 : `def account(self, identifier)`
- [InpiClient.close](../../service/inpi/client.py) — ligne 96 : `def close(self)`

## `service/inpi/files.py`

Source SHA-256 : `437feb03c2bc0ed956d6cba276a41ad3a148042f7ec0bab4c72047b6011e0507`

- [atomic](../../service/inpi/files.py) — ligne 8 : `def atomic(path: Path, payload)`

## `service/inpi/pilot_review.py`

Source SHA-256 : `c0910f8e127b47edcd1e53947c8601cad02195ca9a9783fc470c5598e725e77b`

- [review](../../service/inpi/pilot_review.py) — ligne 9 : `def review(report, evidence)`
- [main](../../service/inpi/pilot_review.py) — ligne 39 : `def main()`

## `service/inpi/secure_collection.py`

Source SHA-256 : `a32bfd2b3b8399fd1e3b2a332466dc8d2574154dd6c8e1d239c977c811a075ce`

- [DocumentExcluded](../../service/inpi/secure_collection.py) — ligne 13 : `class DocumentExcluded(InpiError)`
- [ArchiveClient](../../service/inpi/secure_collection.py) — ligne 17 : `class ArchiveClient`
- [ArchiveClient.__init__](../../service/inpi/secure_collection.py) — ligne 18 : `def __init__(self, client, manifest, root, *, max_requests, max_bytes)`
- [ArchiveClient.calls](../../service/inpi/secure_collection.py) — ligne 24 : `def calls(self)`
- [ArchiveClient._budget](../../service/inpi/secure_collection.py) — ligne 26 : `def _budget(self)`
- [ArchiveClient.login](../../service/inpi/secure_collection.py) — ligne 29 : `def login(self)`
- [ArchiveClient.accounts](../../service/inpi/secure_collection.py) — ligne 32 : `def accounts(self, *args, **kwargs)`
- [ArchiveClient.account](../../service/inpi/secure_collection.py) — ligne 35 : `def account(self, identifier)`
- [ArchiveClient.close](../../service/inpi/secure_collection.py) — ligne 73 : `def close(self)`
- [collect](../../service/inpi/secure_collection.py) — ligne 76 : `def collect(cfg, result, *, root, manifest_path, dry_run=False, max_symbols=None, client=None)`

## `service/inpi/universe_catchup.py`

Source SHA-256 : `506f27840870e70e2e676a228e6f55e6c1d45de04404c3c2595bb7eff8853e4b`

- [main](../../service/inpi/universe_catchup.py) — ligne 10 : `def main()`

## `service/inpi/universe_collection.py`

Source SHA-256 : `d56ca820e7241562bac1013f901b1da580f5b38e4b87fde57c5c95b8ab255941`

- [QuotaPause](../../service/inpi/universe_collection.py) — ligne 15 : `class QuotaPause(RuntimeError)`
- [validate](../../service/inpi/universe_collection.py) — ligne 18 : `def validate(manifest)`
- [collect](../../service/inpi/universe_collection.py) — ligne 49 : `def collect(cfg, result, *, root, manifest_path, dry_run=False, max_symbols=None, client=None)`

## `service/inpi/universe_mapping.py`

Source SHA-256 : `aa12d46608d51f6820d91abddac36e699a814e4fe8127c9c08f84c29e7b7e55f`

- [valid_siren](../../service/inpi/universe_mapping.py) — ligne 23 : `def valid_siren(value)`
- [registry_siren](../../service/inpi/universe_mapping.py) — ligne 29 : `def registry_siren(value)`
- [evaluate](../../service/inpi/universe_mapping.py) — ligne 34 : `def evaluate(payload, isin)`
- [Gleif](../../service/inpi/universe_mapping.py) — ligne 61 : `class Gleif`
- [Gleif.__init__](../../service/inpi/universe_mapping.py) — ligne 62 : `def __init__(self, budget=1200, pace=0.25)`
- [Gleif.get](../../service/inpi/universe_mapping.py) — ligne 66 : `def get(self, path)`
- [lookup](../../service/inpi/universe_mapping.py) — ligne 78 : `def lookup(client, isin)`
- [build](../../service/inpi/universe_mapping.py) — ligne 101 : `def build(*, root=DEFAULT_ROOT, budget=1200, client=None, refresh=False, retry_reasons=())`
- [main](../../service/inpi/universe_mapping.py) — ligne 161 : `def main()`

## `service/llm_directional/__init__.py`

Source SHA-256 : `bbacb0419fe1426b6afea259f826c548c0d0511ce5afdc9bdb93337f5bbf58da`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `service/llm_directional/config.py`

Source SHA-256 : `a669a72f0d20f566513e846b657139837ae40bbf30d6b84c3c12d40bef697565`

- [FilterConfig](../../service/llm_directional/config.py) — ligne 8 : `class FilterConfig`
- [FilterConfig.__post_init__](../../service/llm_directional/config.py) — ligne 29 : `def __post_init__(self)`
- [FilterConfig.snapshot](../../service/llm_directional/config.py) — ligne 63 : `def snapshot(self)`
- [load_filter_config](../../service/llm_directional/config.py) — ligne 67 : `def load_filter_config(path=None)`

## `service/llm_directional/evaluate.py`

Source SHA-256 : `b2e6c9c101a7cd262ef009386426ebc40a365c23c6ace0bc5efa8b7f8e68deb9`

- [evaluate](../../service/llm_directional/evaluate.py) — ligne 10 : `def evaluate(engine, run_id, *, as_of=None, horizons=(5, 10, 20))`
- [main](../../service/llm_directional/evaluate.py) — ligne 81 : `def main()`

## `service/llm_directional/openai_client.py`

Source SHA-256 : `9ff42a3bc70af43818d6ffbaefa568c84ca09de65f0521733a7086354ee288e0`

- [build_request](../../service/llm_directional/openai_client.py) — ligne 43 : `def build_request(context, config)`
- [ResponsesClient](../../service/llm_directional/openai_client.py) — ligne 55 : `class ResponsesClient`
- [ResponsesClient.__init__](../../service/llm_directional/openai_client.py) — ligne 56 : `def __init__(self, config, session=None)`
- [ResponsesClient.__call__](../../service/llm_directional/openai_client.py) — ligne 64 : `def __call__(self, payload)`

## `service/llm_directional/pipeline.py`

Source SHA-256 : `4fb26b04a8d177fb93492a67e04e611536d9392b562e76b2a7fe1aa139284a4f`

- [main](../../service/llm_directional/pipeline.py) — ligne 16 : `def main()`
- [_validate_targets](../../service/llm_directional/pipeline.py) — ligne 126 : `def _validate_targets(targets, holdings, selected, trade_date)`
- [_check_protection_choice](../../service/llm_directional/pipeline.py) — ligne 161 : `def _check_protection_choice(run, choice)`
- [_check_watcher_ready](../../service/llm_directional/pipeline.py) — ligne 167 : `def _check_watcher_ready(engine, run)`
- [_check_short_watcher_code](../../service/llm_directional/pipeline.py) — ligne 181 : `def _check_short_watcher_code(repo)`

## `service/llm_directional/preflight.py`

Source SHA-256 : `dda3fee19b43d6331cdcc835fa4fa6aa2b9f15a9b46fe871de4769b5dd9d6db8`

- [main](../../service/llm_directional/preflight.py) — ligne 10 : `def main()`

## `service/llm_directional/protections.py`

Source SHA-256 : `dbe1720dbc011687c3e057abcf28d91b86273e2ad3fd889ae16f6fc880f52c84`

- [ProtectionProfile](../../service/llm_directional/protections.py) — ligne 14 : `class ProtectionProfile`
- [ProtectionProfile.__post_init__](../../service/llm_directional/protections.py) — ligne 20 : `def __post_init__(self)`
- [archived_profile](../../service/llm_directional/protections.py) — ligne 31 : `def archived_profile(config_json)`
- [profile_for_risk](../../service/llm_directional/protections.py) — ligne 39 : `def profile_for_risk(engine, risk_run_id, symbol, *, account_id, broker_mode)`
- [scoped_execution_config](../../service/llm_directional/protections.py) — ligne 59 : `def scoped_execution_config(config, profile)`
- [safe_trailing_trigger](../../service/llm_directional/protections.py) — ligne 70 : `def safe_trailing_trigger(fill_price, profile, side='buy')`
- [persist_order](../../service/llm_directional/protections.py) — ligne 85 : `def persist_order(repo, intent, order, *, account_id)`
- [submit_order](../../service/llm_directional/protections.py) — ligne 93 : `def submit_order(repo, broker, intent, *, account_id)`
- [exit_open](../../service/llm_directional/protections.py) — ligne 113 : `def exit_open(opened_at, profile, *, calendar=None)`
- [exit_action](../../service/llm_directional/protections.py) — ligne 128 : `def exit_action(due, *, now=None, calendar=None)`
- [apply_scheduled_exit](../../service/llm_directional/protections.py) — ligne 149 : `def apply_scheduled_exit(watcher, row, profile, metrics, *, now=None)`
- [_parent_context](../../service/llm_directional/protections.py) — ligne 216 : `def _parent_context(parent, row)`

## `service/llm_directional/report.py`

Source SHA-256 : `5ac1fa5da19f45c7fc111f2950c15ef1280d1f451fc1a9b769e59edbe1e200b1`

- [report](../../service/llm_directional/report.py) — ligne 8 : `def report(engine, run_id)`
- [main](../../service/llm_directional/report.py) — ligne 35 : `def main()`

## `service/llm_directional/repository.py`

Source SHA-256 : `b4299642d657f5c39256a5b64143c1ebd3d9e61d1afab547bc8400027c00b704`

- [utcnow](../../service/llm_directional/repository.py) — ligne 60 : `def utcnow()`
- [dumps](../../service/llm_directional/repository.py) — ligne 64 : `def dumps(value)`
- [digest](../../service/llm_directional/repository.py) — ligne 68 : `def digest(value)`
- [Repository](../../service/llm_directional/repository.py) — ligne 72 : `class Repository`
- [Repository.__init__](../../service/llm_directional/repository.py) — ligne 73 : `def __init__(self, engine)`
- [Repository.create](../../service/llm_directional/repository.py) — ligne 78 : `def create(self, **values)`
- [Repository.record](../../service/llm_directional/repository.py) — ligne 82 : `def record(self, **values)`
- [Repository.finish](../../service/llm_directional/repository.py) — ligne 86 : `def finish(self, run_id, status, selected, error=None)`
- [Repository.finalize_assessment](../../service/llm_directional/repository.py) — ligne 97 : `def finalize_assessment(self, run_id, symbol, *, status, parsed, error=None)`
- [Repository.get](../../service/llm_directional/repository.py) — ligne 107 : `def get(self, run_id)`
- [Repository.bind_risk](../../service/llm_directional/repository.py) — ligne 114 : `def bind_risk(self, run_id, risk_run_id)`
- [Repository.claim_risk](../../service/llm_directional/repository.py) — ligne 122 : `def claim_risk(self, run_id)`
- [Repository.claim_execution](../../service/llm_directional/repository.py) — ligne 130 : `def claim_execution(self, run_id)`

## `service/llm_directional/risk_adapter.py`

Source SHA-256 : `43b4b7d30140f188cc911675916440b4c6fc778f973cc15ec539ff02fe0f1932`

- [validate_short_broker](../../service/llm_directional/risk_adapter.py) — ligne 6 : `def validate_short_broker(broker, symbols, *, account=None)`
- [capture_paper_snapshot](../../service/llm_directional/risk_adapter.py) — ligne 33 : `def capture_paper_snapshot()`
- [load_candidates](../../service/llm_directional/risk_adapter.py) — ligne 49 : `def load_candidates(engine, run_id, trade_date, account_id, universe_run_id, universe_symbols)`
- [build_entries](../../service/llm_directional/risk_adapter.py) — ligne 75 : `def build_entries(builder, candidates, prices, sector_map, trade_date, return_matrix)`

## `service/llm_directional/runner.py`

Source SHA-256 : `676c3d1c1a24891f75ea8497119f0c4405e43ec2bd82947a148e719f5c72ec0e`

- [assert_paper_account](../../service/llm_directional/runner.py) — ligne 15 : `def assert_paper_account(account_id='default')`
- [load_inputs](../../service/llm_directional/runner.py) — ligne 22 : `def load_inputs(engine, batch_id, trade_date, symbol_source, config, capital_preset_key)`
- [validate_analysis_window](../../service/llm_directional/runner.py) — ligne 65 : `def validate_analysis_window(trade_date, *, now=None, calendar=None)`
- [analyze](../../service/llm_directional/runner.py) — ligne 83 : `def analyze(*, engine, batch_id, trade_date, symbol_source, capital_preset_key='capital_2001_5000', config=None, run_id=None, client=None, inputs=None, check_account=True)`
- [qualified_selection](../../service/llm_directional/runner.py) — ligne 157 : `def qualified_selection(engine, run_id, trade_date, account_id, *, now=None, allow_consumed=False)`
- [main](../../service/llm_directional/runner.py) — ligne 197 : `def main()`

## `service/llm_directional/validation.py`

Source SHA-256 : `d952c74ae6f73353523b321db143e7eaa0147ce52ce70ea6594ee5693300f514`

- [parse_response](../../service/llm_directional/validation.py) — ligne 10 : `def parse_response(response, symbol, config, observed_at)`
- [select_symbols](../../service/llm_directional/validation.py) — ligne 59 : `def select_symbols(items, config)`

## `service/market/__init__.py`

Source SHA-256 : `93f67f6db7d4ccec7da0a148cf4ae80cd59aea4ca5774b8aa077115d57e3204c`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `service/market/__main__.py`

Source SHA-256 : `8fed4a9e57d8acd9fcf17a9feff955affcb7750526395a7ef18d1b6d413588ee`

- [_default_progress_callback](../../service/market/__main__.py) — ligne 17 : `def _default_progress_callback(step: dict[str, Any]) -> None`
- [_cmd_populate_macro](../../service/market/__main__.py) — ligne 32 : `def _cmd_populate_macro(args: argparse.Namespace) -> None`
- [_cmd_recompute_regime](../../service/market/__main__.py) — ligne 53 : `def _cmd_recompute_regime(args: argparse.Namespace) -> None`
- [main](../../service/market/__main__.py) — ligne 75 : `def main() -> None`

## `service/market/bootstrap_us_instruments.py`

Source SHA-256 : `30e999034a6d02824ef7325c54a914e65d40effc4cdfa6e3b2192716f8700ec2`

- [_load_state](../../service/market/bootstrap_us_instruments.py) — ligne 77 : `def _load_state(path: Path) -> dict[str, Any]`
- [_save_state](../../service/market/bootstrap_us_instruments.py) — ligne 83 : `def _save_state(path: Path, state: dict[str, Any]) -> None`
- [bootstrap_us_instruments](../../service/market/bootstrap_us_instruments.py) — ligne 90 : `def bootstrap_us_instruments(engine: Engine) -> dict[str, int]`
- [_table_strategy](../../service/market/bootstrap_us_instruments.py) — ligne 198 : `def _table_strategy(engine: Engine, table: str) -> tuple[str, str | None]`
- [_update_range](../../service/market/bootstrap_us_instruments.py) — ligne 218 : `def _update_range(engine: Engine, table: str, predicate: str, params: dict[str, Any], *, symbol_lookup: bool=False, straight_join: bool=False) -> int`
- [_update_symbol_mappings](../../service/market/bootstrap_us_instruments.py) — ligne 255 : `def _update_symbol_mappings(engine: Engine, table: str, mappings: list[dict[str, Any]]) -> int`
- [_update_symbol_range](../../service/market/bootstrap_us_instruments.py) — ligne 270 : `def _update_symbol_range(engine: Engine, table: str, lower: int, upper: int, *, workers: int=4) -> int`
- [_advance_months](../../service/market/bootstrap_us_instruments.py) — ligne 308 : `def _advance_months(value: date, months: int) -> date`
- [backfill_us_facts](../../service/market/bootstrap_us_instruments.py) — ligne 313 : `def backfill_us_facts(engine: Engine, state_path: Path=DEFAULT_STATE, *, id_chunk: int=250000, symbol_chunk: int=500, symbol_workers: int=4, date_chunk_months: int=1) -> dict[str, Any]`
- [reconcile_us_facts](../../service/market/bootstrap_us_instruments.py) — ligne 400 : `def reconcile_us_facts(engine: Engine, state_path: Path) -> dict[str, Any]`
- [audit_us_fact_coverage](../../service/market/bootstrap_us_instruments.py) — ligne 427 : `def audit_us_fact_coverage(engine: Engine) -> dict[str, Any]`
- [main](../../service/market/bootstrap_us_instruments.py) — ligne 472 : `def main() -> None`

## `service/market/calendar_patterns.py`

Source SHA-256 : `dd850c97a07cbcde7edec463faf721acf4b602f56931c5bcbb2b155d36ceb432`

- [CalendarPatternHit](../../service/market/calendar_patterns.py) — ligne 12 : `class CalendarPatternHit`
- [_in_md_window](../../service/market/calendar_patterns.py) — ligne 20 : `def _in_md_window(d: date, start_md: str, end_md: str) -> bool`
- [is_third_friday](../../service/market/calendar_patterns.py) — ligne 36 : `def is_third_friday(d: date) -> bool`
- [is_month_end_window](../../service/market/calendar_patterns.py) — ligne 44 : `def is_month_end_window(d: date, business_days_from_end: int) -> bool`
- [evaluate_pattern](../../service/market/calendar_patterns.py) — ligne 61 : `def evaluate_pattern(name: str, cfg: CalendarPatternConfig, d: date) -> CalendarPatternHit | None`
- [evaluate_calendar_patterns](../../service/market/calendar_patterns.py) — ligne 84 : `def evaluate_calendar_patterns(cfg: MarketRegimesConfig, trade_date: date) -> list[CalendarPatternHit]`

## `service/market/cn_backup_restore_17b.py`

Source SHA-256 : `092913cc1702b56a993d24f7aa24b61d5215929dd502f78a53629a80fbed15cb`

- [validate_archive](../../service/market/cn_backup_restore_17b.py) — ligne 32 : `def validate_archive(path: Path, *, backup_root: Path=CN_BACKUP_ROOT) -> Path`
- [validate_restore_name](../../service/market/cn_backup_restore_17b.py) — ligne 40 : `def validate_restore_name(name: str) -> str`
- [_mysql](../../service/market/cn_backup_restore_17b.py) — ligne 46 : `def _mysql(command: list[str], *, executable: Path, host: str, user: str, password: str) -> subprocess.CompletedProcess[str]`
- [_base_tables](../../service/market/cn_backup_restore_17b.py) — ligne 56 : `def _base_tables(engine, database: str) -> list[str]`
- [_row_counts](../../service/market/cn_backup_restore_17b.py) — ligne 68 : `def _row_counts(engine, names: list[str]) -> dict[str, int]`
- [restore_probe](../../service/market/cn_backup_restore_17b.py) — ligne 74 : `def restore_probe(*, archive: Path, mysql_executable: Path, host: str='localhost', cleanup_on_success: bool=False, backup_root: Path=CN_BACKUP_ROOT) -> dict`
- [main](../../service/market/cn_backup_restore_17b.py) — ligne 176 : `def main() -> None`

## `service/market/cn_canonical_full.py`

Source SHA-256 : `71db9ce9485acbba4733f86870a5417345c8a05d2fc78a8082eee20e777da429`

- [select_full_universe](../../service/market/cn_canonical_full.py) — ligne 24 : `def select_full_universe(engine: Engine, *, start: date, end: date) -> list[str]`
- [write_chunks](../../service/market/cn_canonical_full.py) — ligne 49 : `def write_chunks(symbols: list[str], root: Path, *, chunk_size: int) -> list[Path]`
- [price_limit_policy](../../service/market/cn_canonical_full.py) — ligne 68 : `def price_limit_policy(*, board: str, session_date: date, is_st: bool, observed_number: int) -> tuple[str, Decimal | None, bool]`
- [_rounded](../../service/market/cn_canonical_full.py) — ligne 83 : `def _rounded(value: Decimal) -> Decimal`
- [derived_limit_for_bar](../../service/market/cn_canonical_full.py) — ligne 87 : `def derived_limit_for_bar(*, board: str, session_date: date, is_st: bool, observed_number: int, pre_close: Decimal | None, high: Decimal, low: Decimal) -> dict[str, Any]`
- [enrich_manifest](../../service/market/cn_canonical_full.py) — ligne 118 : `def enrich_manifest(engine: Engine, *, manifest_path: Path, business_start_date: date | None=None, business_end_date: date | None=None, allow_same_day_after_close: bool=False) -> dict[str, int]`
- [remediate_historical_quality](../../service/market/cn_canonical_full.py) — ligne 213 : `def remediate_historical_quality(engine: Engine, *, start: date, end: date) -> dict[str, int]`
- [measure_coverage](../../service/market/cn_canonical_full.py) — ligne 275 : `def measure_coverage(engine: Engine, *, manifest_path: Path, start: date, end: date) -> dict[str, Any]`
- [audit_full](../../service/market/cn_canonical_full.py) — ligne 371 : `def audit_full(engine: Engine, *, manifest_path: Path) -> dict[str, Any]`

## `service/market/cn_canonicalizer.py`

Source SHA-256 : `aa605912b16b769d8cb565fd0db59412ae1b5575d33e26940d64400f49fdf7a1`

- [CanonicalizationReport](../../service/market/cn_canonicalizer.py) — ligne 36 : `class CanonicalizationReport`
- [_json](../../service/market/cn_canonicalizer.py) — ligne 53 : `def _json(value: Any) -> dict[str, Any]`
- [_latest](../../service/market/cn_canonicalizer.py) — ligne 61 : `def _latest(rows: Iterable[dict[str, Any]], key_fields: tuple[str, ...]) -> tuple[list[dict[str, Any]], int]`
- [_spread_pick](../../service/market/cn_canonicalizer.py) — ligne 76 : `def _spread_pick(values: list[str], count: int) -> list[str]`
- [select_pilot_symbols](../../service/market/cn_canonicalizer.py) — ligne 86 : `def select_pilot_symbols(engine: Engine, *, quotas: dict[str, int] | None=None, as_of: date | None=None, history_start: date | None=None) -> list[str]`
- [write_pilot_manifest](../../service/market/cn_canonicalizer.py) — ligne 139 : `def write_pilot_manifest(symbols: list[str], path: Path) -> str`
- [read_pilot_manifest](../../service/market/cn_canonicalizer.py) — ligne 147 : `def read_pilot_manifest(path: Path) -> list[str]`
- [_mic](../../service/market/cn_canonicalizer.py) — ligne 151 : `def _mic(exchange: str) -> str`
- [_utc_session](../../service/market/cn_canonicalizer.py) — ligne 155 : `def _utc_session(session_date: date) -> tuple[datetime, datetime, str]`
- [_pit_close](../../service/market/cn_canonicalizer.py) — ligne 169 : `def _pit_close(session_date: date) -> datetime`
- [_valid_bar](../../service/market/cn_canonicalizer.py) — ligne 174 : `def _valid_bar(row: dict[str, Any]) -> bool`
- [canonical_trading_status](../../service/market/cn_canonicalizer.py) — ligne 190 : `def canonical_trading_status(raw_status: str, volume: Any, amount: Any) -> str`
- [_incremental_insert_sql](../../service/market/cn_canonicalizer.py) — ligne 202 : `def _incremental_insert_sql(statement: str) -> str`
- [_incremental_timestamps](../../service/market/cn_canonicalizer.py) — ligne 211 : `def _incremental_timestamps(row: dict[str, Any], day: date) -> tuple[datetime, datetime]`
- [promote_pilot](../../service/market/cn_canonicalizer.py) — ligne 223 : `def promote_pilot(engine: Engine, *, manifest_path: Path, staging_cutoff: datetime | None=None, business_start_date: date | None=None, business_end_date: date | None=None, allow_same_day_after_close: bool=False) -> CanonicalizationReport`
- [audit_pilot](../../service/market/cn_canonicalizer.py) — ligne 386 : `def audit_pilot(engine: Engine, *, manifest_path: Path) -> dict[str, Any]`

## `service/market/cn_catalog_contract_17d.py`

Source SHA-256 : `970e5f8808000f134a33c423c18f9e35884b0297dd399b61ada81b483d42e474`

- [validate](../../service/market/cn_catalog_contract_17d.py) — ligne 10 : `def validate(batch_config: Path, config: dict, batch_name: str) -> dict`

## `service/market/cn_catalog_plan_17d.py`

Source SHA-256 : `bb44679b31b9b9bf8dfb84a6c33081782094cee78d94cdc5728597f74705f386`

- [_load](../../service/market/cn_catalog_plan_17d.py) — ligne 15 : `def _load(path: Path) -> dict`
- [prepare](../../service/market/cn_catalog_plan_17d.py) — ligne 22 : `def prepare(*, us_batch_path: Path, cn_batch_path: Path, quality_root: Path) -> dict`
- [main](../../service/market/cn_catalog_plan_17d.py) — ligne 62 : `def main() -> None`

## `service/market/cn_catalog_preflight_17d.py`

Source SHA-256 : `b2039ac4a7415dedd9144af7631c241b2df76e60551a7adc248b56913c8205fe`

- [_load](../../service/market/cn_catalog_preflight_17d.py) — ligne 32 : `def _load(path: Path) -> dict`
- [_latest_quality_report](../../service/market/cn_catalog_preflight_17d.py) — ligne 39 : `def _latest_quality_report(root: Path) -> dict | None`
- [_complete_real_cycle](../../service/market/cn_catalog_preflight_17d.py) — ligne 54 : `def _complete_real_cycle(report: dict) -> bool`
- [inspect](../../service/market/cn_catalog_preflight_17d.py) — ligne 73 : `def inspect(*, us_batch_path: Path, cn_batch_path: Path, quality_root: Path) -> dict`
- [main](../../service/market/cn_catalog_preflight_17d.py) — ligne 131 : `def main() -> None`

## `service/market/cn_catalog_snapshot_validate_17d.py`

Source SHA-256 : `57845ceae58a5ef850d9119f01664881c4929c7f517fdec422863558d4036725`

- [validate](../../service/market/cn_catalog_snapshot_validate_17d.py) — ligne 24 : `def validate(snapshot: Path, *, current_root: Path | None=None) -> dict`
- [main](../../service/market/cn_catalog_snapshot_validate_17d.py) — ligne 89 : `def main() -> None`

## `service/market/cn_completed_session_guard.py`

Source SHA-256 : `1497c93c84acda923f486d9a3ba29e7b58d6dd10788ad897884d0641411822b3`

- [require_completed_session_end](../../service/market/cn_completed_session_guard.py) — ligne 11 : `def require_completed_session_end(end: date, *, allow_same_day_after_close: bool=False, now: datetime | None=None) -> None`

## `service/market/cn_daily_quality_17c.py`

Source SHA-256 : `350c3f66234dca8af0d5f138924fb8a878d88bc1c4de2e6881f32c236b4bf178`

- [_path](../../service/market/cn_daily_quality_17c.py) — ligne 32 : `def _path(base: Path, value: str) -> Path`
- [plan](../../service/market/cn_daily_quality_17c.py) — ligne 37 : `def plan(now: datetime, calendar: dict, *, earliest: time=time(23, 30), audit_previous_day_before_open: bool=False) -> dict`
- [_read_json](../../service/market/cn_daily_quality_17c.py) — ligne 55 : `def _read_json(path: Path) -> dict | None`
- [_digest](../../service/market/cn_daily_quality_17c.py) — ligne 64 : `def _digest(path: Path) -> str | None`
- [_latest_run](../../service/market/cn_daily_quality_17c.py) — ligne 74 : `def _latest_run(folder: Path, session: str, *, now: datetime) -> dict | None`
- [_snapshot](../../service/market/cn_daily_quality_17c.py) — ligne 83 : `def _snapshot(folder: Path, phase: str, *, next_session: str, now: datetime) -> dict | None`
- [read_evidence](../../service/market/cn_daily_quality_17c.py) — ligne 96 : `def read_evidence(engine, *, cfg: dict, d9_cfg: dict, base: Path, session: date, previous: date, next_session: date, now: datetime) -> dict`
- [evaluate](../../service/market/cn_daily_quality_17c.py) — ligne 204 : `def evaluate(evidence: dict, *, minimum_bar_ratio: float=0.995) -> list[dict]`
- [execute](../../service/market/cn_daily_quality_17c.py) — ligne 288 : `def execute(*, batch_config: Path=ROOT / 'batch_cn.yaml', research_config: Path=ROOT / 'batch.yaml', now: datetime | None=None, dry_run: bool=False) -> dict`
- [main](../../service/market/cn_daily_quality_17c.py) — ligne 359 : `def main() -> None`

## `service/market/cn_db_backup_17b.py`

Source SHA-256 : `77fcfbc6d808aaebc1b8bcaa606e4c3dec74f119e683d6d06985112b4387903f`

- [run](../../service/market/cn_db_backup_17b.py) — ligne 21 : `def run(*, config_path: Path=ROOT / 'batch_cn.yaml', dry_run: bool=False, force: bool=False) -> dict`
- [main](../../service/market/cn_db_backup_17b.py) — ligne 76 : `def main() -> None`

## `service/market/cn_dragon_tiger_coverage_15d4.py`

Source SHA-256 : `261861a95a7ad483158c42d4d9bbce4d8d79320c378e4862e194dd3f4bbc3137`

- [collect_sanitized](../../service/market/cn_dragon_tiger_coverage_15d4.py) — ligne 32 : `def collect_sanitized(*, max_pages: int=80) -> tuple[pd.DataFrame, list[dict]]`
- [resolve_events](../../service/market/cn_dragon_tiger_coverage_15d4.py) — ligne 81 : `def resolve_events(rows: pd.DataFrame, mappings: pd.DataFrame) -> tuple[pd.DataFrame, dict]`
- [assign_availability](../../service/market/cn_dragon_tiger_coverage_15d4.py) — ligne 107 : `def assign_availability(events: pd.DataFrame, sessions: pd.DatetimeIndex, lag: int) -> pd.DataFrame`
- [join_coverage](../../service/market/cn_dragon_tiger_coverage_15d4.py) — ligne 123 : `def join_coverage(top: pd.DataFrame, events: pd.DataFrame, sessions: pd.DatetimeIndex, lag: int) -> pd.DataFrame`
- [summarize](../../service/market/cn_dragon_tiger_coverage_15d4.py) — ligne 143 : `def summarize(joined: pd.DataFrame, lag: int) -> dict`
- [run](../../service/market/cn_dragon_tiger_coverage_15d4.py) — ligne 158 : `def run(output: Path, oracle_root: Path, *, max_pages: int=80) -> dict`
- [main](../../service/market/cn_dragon_tiger_coverage_15d4.py) — ligne 197 : `def main() -> None`

## `service/market/cn_dragon_tiger_cumulative_15d11.py`

Source SHA-256 : `eb0f71710cd25f507f7387b308454e322582fa2cf0216f36c3d8afa635545b87`

- [_digest](../../service/market/cn_dragon_tiger_cumulative_15d11.py) — ligne 31 : `def _digest(path: Path) -> str`
- [_standardized_difference](../../service/market/cn_dragon_tiger_cumulative_15d11.py) — ligne 39 : `def _standardized_difference(pairs: pd.DataFrame, column: str) -> float | None`
- [inspect](../../service/market/cn_dragon_tiger_cumulative_15d11.py) — ligne 50 : `def inspect(*, daily_root: Path, oracle_root: Path, protocol_path: Path, now: datetime | None=None) -> dict`
- [main](../../service/market/cn_dragon_tiger_cumulative_15d11.py) — ligne 175 : `def main() -> None`

## `service/market/cn_dragon_tiger_daily_15d10.py`

Source SHA-256 : `694c35530a2445e0d4de5ac8f20d0279b20d5cdb20cc8e5d53759217e91082f6`

- [_path](../../service/market/cn_dragon_tiger_daily_15d10.py) — ligne 29 : `def _path(value: str | Path, base: Path) -> Path`
- [plan](../../service/market/cn_dragon_tiger_daily_15d10.py) — ligne 34 : `def plan(now: datetime, calendar: dict) -> dict`
- [execute](../../service/market/cn_dragon_tiger_daily_15d10.py) — ligne 46 : `def execute(*, batch_config: Path=ROOT / 'batch.yaml', now: datetime | None=None, dry_run: bool=False) -> dict`
- [main](../../service/market/cn_dragon_tiger_daily_15d10.py) — ligne 116 : `def main() -> None`

## `service/market/cn_dragon_tiger_matched_15d7.py`

Source SHA-256 : `05e6711830857c50532c29a9d540466d652d742930c5140b4f3fb8a9986737de`

- [_digest](../../service/market/cn_dragon_tiger_matched_15d7.py) — ligne 31 : `def _digest(path: Path) -> str`
- [load_protocol](../../service/market/cn_dragon_tiger_matched_15d7.py) — ligne 39 : `def load_protocol(path: Path) -> dict`
- [_timestamp](../../service/market/cn_dragon_tiger_matched_15d7.py) — ligne 54 : `def _timestamp(value: str) -> datetime`
- [_boolean](../../service/market/cn_dragon_tiger_matched_15d7.py) — ligne 61 : `def _boolean(value: object) -> bool`
- [load_timely_snapshots](../../service/market/cn_dragon_tiger_matched_15d7.py) — ligne 71 : `def load_timely_snapshots(root: Path, calendar: dict, *, now: datetime | None=None, include_future_cutoffs: bool=False) -> tuple[dict, dict]`
- [load_candidates](../../service/market/cn_dragon_tiger_matched_15d7.py) — ligne 148 : `def load_candidates(path: Path, protocol: dict, snapshots: dict) -> pd.DataFrame`
- [match_candidates](../../service/market/cn_dragon_tiger_matched_15d7.py) — ligne 191 : `def match_candidates(frame: pd.DataFrame, protocol: dict) -> tuple[pd.DataFrame, dict]`
- [audit](../../service/market/cn_dragon_tiger_matched_15d7.py) — ligne 231 : `def audit(*, snapshot_root: Path, calendar_path: Path, protocol_path: Path, output: Path, candidates_path: Path | None=None, now: datetime | None=None) -> dict`
- [main](../../service/market/cn_dragon_tiger_matched_15d7.py) — ligne 286 : `def main() -> None`

## `service/market/cn_dragon_tiger_pilot_15d2.py`

Source SHA-256 : `94d2869ca0a7847f1329dbe04234b24baea4b6331bbc2f6f9925a4c45074272a`

- [_get](../../service/market/cn_dragon_tiger_pilot_15d2.py) — ligne 36 : `def _get(url: str, params: dict[str, str], referer: str, *, attempts: int=3) -> bytes`
- [_json](../../service/market/cn_dragon_tiger_pilot_15d2.py) — ligne 53 : `def _json(raw: bytes) -> Any`
- [_digest](../../service/market/cn_dragon_tiger_pilot_15d2.py) — ligne 57 : `def _digest(raw: bytes) -> str`
- [_code](../../service/market/cn_dragon_tiger_pilot_15d2.py) — ligne 61 : `def _code(value: Any) -> str`
- [is_cn_a_equity_code](../../service/market/cn_dragon_tiger_pilot_15d2.py) — ligne 68 : `def is_cn_a_equity_code(market: str, code: str) -> bool`
- [official_sse](../../service/market/cn_dragon_tiger_pilot_15d2.py) — ligne 75 : `def official_sse(day: str) -> tuple[list[dict[str, str]], dict[str, Any]]`
- [parse_szse_page](../../service/market/cn_dragon_tiger_pilot_15d2.py) — ligne 113 : `def parse_szse_page(response: Any, day: str, expected_page: int) -> tuple[list[dict[str, str]], dict[str, int]]`
- [official_szse](../../service/market/cn_dragon_tiger_pilot_15d2.py) — ligne 139 : `def official_szse(day: str) -> tuple[list[dict[str, str]], dict[str, Any]]`
- [sanitize_vendor](../../service/market/cn_dragon_tiger_pilot_15d2.py) — ligne 170 : `def sanitize_vendor(row: dict[str, Any], day: str) -> dict[str, str] | None`
- [vendor_eastmoney](../../service/market/cn_dragon_tiger_pilot_15d2.py) — ligne 184 : `def vendor_eastmoney(day: str) -> tuple[list[dict[str, str]], dict[str, Any]]`
- [compare](../../service/market/cn_dragon_tiger_pilot_15d2.py) — ligne 229 : `def compare(day: str, sse: list[dict[str, str]], szse: list[dict[str, str]], vendor: list[dict[str, str]]) -> dict[str, Any]`
- [run](../../service/market/cn_dragon_tiger_pilot_15d2.py) — ligne 245 : `def run(output: Path, dates: tuple[str, ...]=SAMPLE_DATES) -> dict[str, Any]`
- [main](../../service/market/cn_dragon_tiger_pilot_15d2.py) — ligne 285 : `def main() -> None`

## `service/market/cn_dragon_tiger_prospective_15d5.py`

Source SHA-256 : `59e1e2e8d199f378a35c3dfc06d28cd400787fea6ed9886379d9c67a16685716`

- [_fingerprint](../../service/market/cn_dragon_tiger_prospective_15d5.py) — ligne 23 : `def _fingerprint(value: dict) -> str`
- [sanitize_official](../../service/market/cn_dragon_tiger_prospective_15d5.py) — ligne 29 : `def sanitize_official(sse: list[dict], szse: list[dict]) -> list[dict]`
- [prior_observations](../../service/market/cn_dragon_tiger_prospective_15d5.py) — ligne 49 : `def prior_observations(folder: Path) -> list[dict]`
- [build_snapshot](../../service/market/cn_dragon_tiger_prospective_15d5.py) — ligne 62 : `def build_snapshot(day: date, sse: list[dict], szse: list[dict], prior: list[dict], observed_at: datetime, provenance: dict, collection_context: dict | None=None) -> dict`
- [run](../../service/market/cn_dragon_tiger_prospective_15d5.py) — ligne 116 : `def run(day: date, root: Path, *, collection_context: dict | None=None) -> Path`
- [main](../../service/market/cn_dragon_tiger_prospective_15d5.py) — ligne 132 : `def main() -> None`

## `service/market/cn_dragon_tiger_robustness_15d3.py`

Source SHA-256 : `2a50c078e2e8133ed34cb0232f0becb7ea80411a192c6349e54234a2cf77784a`

- [choose_dates](../../service/market/cn_dragon_tiger_robustness_15d3.py) — ligne 26 : `def choose_dates(sessions: list[str]) -> tuple[str, str]`
- [selected_calendar_dates](../../service/market/cn_dragon_tiger_robustness_15d3.py) — ligne 33 : `def selected_calendar_dates() -> tuple[str, ...]`
- [_parts](../../service/market/cn_dragon_tiger_robustness_15d3.py) — ligne 51 : `def _parts(value: str) -> list[str]`
- [seat_integrity](../../service/market/cn_dragon_tiger_robustness_15d3.py) — ligne 55 : `def seat_integrity(row: dict[str, str]) -> dict[str, Any]`
- [szse_detail](../../service/market/cn_dragon_tiger_robustness_15d3.py) — ligne 77 : `def szse_detail(day: str, code: str, reason_code: str) -> dict[str, Any]`
- [run](../../service/market/cn_dragon_tiger_robustness_15d3.py) — ligne 112 : `def run(output: Path) -> dict[str, Any]`
- [main](../../service/market/cn_dragon_tiger_robustness_15d3.py) — ligne 181 : `def main() -> None`

## `service/market/cn_dragon_tiger_schedule_15d6.py`

Source SHA-256 : `092407b7e15195d2556a0f20ee5718a2e3f918dcd4d613463459f10d22ef2eef`

- [load_calendar](../../service/market/cn_dragon_tiger_schedule_15d6.py) — ligne 26 : `def load_calendar(path: Path) -> dict`
- [is_open](../../service/market/cn_dragon_tiger_schedule_15d6.py) — ligne 44 : `def is_open(day: date, calendar: dict) -> bool`
- [adjacent_open](../../service/market/cn_dragon_tiger_schedule_15d6.py) — ligne 50 : `def adjacent_open(day: date, calendar: dict, direction: int) -> date`
- [plan](../../service/market/cn_dragon_tiger_schedule_15d6.py) — ligne 60 : `def plan(batch_name: str, cfg: dict, calendar: dict, now: datetime, *, force: bool=False) -> dict`
- [_write_report](../../service/market/cn_dragon_tiger_schedule_15d6.py) — ligne 90 : `def _write_report(output_root: Path, report: dict) -> Path`
- [execute](../../service/market/cn_dragon_tiger_schedule_15d6.py) — ligne 100 : `def execute(batch_name: str, batch_config: Path, calendar_path: Path, *, now: datetime | None=None, force: bool=False, probe: bool=False) -> dict`
- [main](../../service/market/cn_dragon_tiger_schedule_15d6.py) — ligne 163 : `def main() -> None`

## `service/market/cn_execution_contract.py`

Source SHA-256 : `2a265648392fa60e6f29782bcd595b79824d346c7913e81ac381caa4d0501e18`

- [CNExecutionContractError](../../service/market/cn_execution_contract.py) — ligne 21 : `class CNExecutionContractError(RuntimeError)`
- [ExecutionRule](../../service/market/cn_execution_contract.py) — ligne 26 : `class ExecutionRule`
- [CostProfile](../../service/market/cn_execution_contract.py) — ligne 44 : `class CostProfile`
- [InventoryLot](../../service/market/cn_execution_contract.py) — ligne 62 : `class InventoryLot`
- [OrderDecision](../../service/market/cn_execution_contract.py) — ligne 68 : `class OrderDecision`
- [CostBreakdown](../../service/market/cn_execution_contract.py) — ligne 75 : `class CostBreakdown`
- [_metadata](../../service/market/cn_execution_contract.py) — ligne 83 : `def _metadata(value: Any) -> dict[str, Any]`
- [_date_value](../../service/market/cn_execution_contract.py) — ligne 90 : `def _date_value(value: date | str | None) -> date | None`
- [_exactly_one](../../service/market/cn_execution_contract.py) — ligne 96 : `def _exactly_one(rows: list[Any], kind: str) -> Any`
- [resolve_rule](../../service/market/cn_execution_contract.py) — ligne 102 : `def resolve_rule(conn: Connection, *, exchange_mic: str, board_code: str, session_date: date, allow_research_rules: bool=False) -> ExecutionRule`
- [resolve_cost_profile](../../service/market/cn_execution_contract.py) — ligne 152 : `def resolve_cost_profile(conn: Connection, *, profile_key: str, session_date: date, allow_research_proxy: bool=False) -> CostProfile`
- [estimate_cost](../../service/market/cn_execution_contract.py) — ligne 187 : `def estimate_cost(*, profile: CostProfile, side: Literal['BUY', 'SELL'], notional_cny: Decimal) -> CostBreakdown`
- [prepare_buy](../../service/market/cn_execution_contract.py) — ligne 206 : `def prepare_buy(*, rule: ExecutionRule, price_cny: Decimal, budget_cny: Decimal, profile: CostProfile) -> OrderDecision`
- [prepare_sell](../../service/market/cn_execution_contract.py) — ligne 222 : `def prepare_sell(*, rule: ExecutionRule, lots: tuple[InventoryLot, ...], session_date: date, requested_shares: int) -> OrderDecision`
- [assess_fill_proxy](../../service/market/cn_execution_contract.py) — ligne 239 : `def assess_fill_proxy(*, side: Literal['BUY', 'SELL'], bar_present: bool, trading_status: str | None, limit_policy: str | None, locked_up: bool | None, locked_down: bool | None) -> OrderDecision`

## `service/market/cn_guidance_pilot_15d1.py`

Source SHA-256 : `27dc36adbd6676ff71d51679b17c65928e74cc91262c5fc9ac2c52e5a7a2a510`

- [_request_json](../../service/market/cn_guidance_pilot_15d1.py) — ligne 49 : `def _request_json(url: str, params: dict[str, Any], *, post: bool=False, attempts: int=3) -> dict[str, Any] | list[dict[str, Any]]`
- [_sha256](../../service/market/cn_guidance_pilot_15d1.py) — ligne 68 : `def _sha256(path: Path) -> str`
- [discover_eastmoney](../../service/market/cn_guidance_pilot_15d1.py) — ligne 76 : `def discover_eastmoney(*, max_pages_per_period: int=40) -> tuple[pd.DataFrame, list[dict[str, Any]]]`
- [select_top20](../../service/market/cn_guidance_pilot_15d1.py) — ligne 121 : `def select_top20(frame: pd.DataFrame, top_pct: float=0.2) -> pd.DataFrame`
- [load_oracle_top20](../../service/market/cn_guidance_pilot_15d1.py) — ligne 135 : `def load_oracle_top20(oracle_root: Path) -> tuple[pd.DataFrame, list[dict[str, str]]]`
- [join_prior_announcements](../../service/market/cn_guidance_pilot_15d1.py) — ligne 167 : `def join_prior_announcements(top: pd.DataFrame, discovery: pd.DataFrame) -> pd.DataFrame`
- [coverage_summary](../../service/market/cn_guidance_pilot_15d1.py) — ligne 180 : `def coverage_summary(joined: pd.DataFrame) -> dict[str, Any]`
- [classify_document](../../service/market/cn_guidance_pilot_15d1.py) — ligne 193 : `def classify_document(title: str, text_content: str) -> dict[str, Any]`
- [_cninfo_post](../../service/market/cn_guidance_pilot_15d1.py) — ligne 207 : `def _cninfo_post(path: str, values: dict[str, Any]) -> Any`
- [cninfo_sample](../../service/market/cn_guidance_pilot_15d1.py) — ligne 211 : `def cninfo_sample(out: Path, *, max_pdfs: int=8) -> list[dict[str, Any]]`
- [run](../../service/market/cn_guidance_pilot_15d1.py) — ligne 276 : `def run(*, output: Path, max_pages_per_period: int=40, max_pdfs: int=8, oracle_root: Path=Path('artifacts/cn/oracle/sprint10b')) -> dict[str, Any]`
- [main](../../service/market/cn_guidance_pilot_15d1.py) — ligne 300 : `def main() -> None`

## `service/market/cn_margin_lending_blocker_audit.py`

Source SHA-256 : `983b5d69b75d909415b83c7dafb01bc0c2840d7cc798ebbe77870a10e23c2ba3`

- [economic_panel](../../service/market/cn_margin_lending_blocker_audit.py) — ligne 42 : `def economic_panel(raw: bytes, day: str) -> dict`
- [compare_panels](../../service/market/cn_margin_lending_blocker_audit.py) — ligne 58 : `def compare_panels(old: dict, new: dict) -> dict`
- [eligibility_match](../../service/market/cn_margin_lending_blocker_audit.py) — ligne 65 : `def eligibility_match(raw: bytes, detail_raw: bytes) -> dict`
- [szse_summary](../../service/market/cn_margin_lending_blocker_audit.py) — ligne 73 : `def szse_summary(raw: bytes) -> dict`
- [archive](../../service/market/cn_margin_lending_blocker_audit.py) — ligne 110 : `def archive(root: Path, name: str, url: str, report: dict) -> bytes`
- [run](../../service/market/cn_margin_lending_blocker_audit.py) — ligne 133 : `def run(output_root: Path) -> dict`
- [main](../../service/market/cn_margin_lending_blocker_audit.py) — ligne 242 : `def main()`

## `service/market/cn_margin_lending_contract_audit.py`

Source SHA-256 : `513d6d4b4995ab565743492aa11c08e40c9f81794cf32896c0a218078996b16c`

- [eligibility_rows](../../service/market/cn_margin_lending_contract_audit.py) — ligne 28 : `def eligibility_rows(raw: bytes) -> dict[str, dict[str, bool]]`
- [classify_presence](../../service/market/cn_margin_lending_contract_audit.py) — ligne 43 : `def classify_presence(*, observed: bool, eligible: bool | None, all_values_zero: bool=False) -> str`
- [proxy_available_at](../../service/market/cn_margin_lending_contract_audit.py) — ligne 54 : `def proxy_available_at(day: date, sessions: list[tuple[date, datetime]]) -> datetime`
- [reconcile_eligibility](../../service/market/cn_margin_lending_contract_audit.py) — ligne 67 : `def reconcile_eligibility(eligible: dict, detail: list[dict], active: set[str]) -> dict`
- [audit_identities](../../service/market/cn_margin_lending_contract_audit.py) — ligne 80 : `def audit_identities(root: Path, session_days: list[date]) -> dict`
- [run](../../service/market/cn_margin_lending_contract_audit.py) — ligne 113 : `def run(*, anchors: Path, weeks: Path, output_root: Path) -> dict`
- [main](../../service/market/cn_margin_lending_contract_audit.py) — ligne 179 : `def main() -> None`

## `service/market/cn_margin_lending_pilot.py`

Source SHA-256 : `1f6ed4a0263c80583e4d4f951868ca07b39485ed2fadee916c7a05f100a6f38e`

- [selected_sessions](../../service/market/cn_margin_lending_pilot.py) — ligne 38 : `def selected_sessions(engine, start_year: int, end_year: int, sample_mode: str='anchors') -> list[date]`
- [active_equities](../../service/market/cn_margin_lending_pilot.py) — ligne 72 : `def active_equities(engine, day: date) -> dict[str, set[str]]`
- [request_bytes](../../service/market/cn_margin_lending_pilot.py) — ligne 88 : `def request_bytes(url: str, *, referer: str, timeout: int=30, retries: int=2) -> bytes`
- [sse_request](../../service/market/cn_margin_lending_pilot.py) — ligne 105 : `def sse_request(day: date) -> bytes`
- [szse_request](../../service/market/cn_margin_lending_pilot.py) — ligne 116 : `def szse_request(day: date) -> bytes`
- [analyse_sse](../../service/market/cn_margin_lending_pilot.py) — ligne 127 : `def analyse_sse(raw: bytes, day: date, active: set[str]) -> dict`
- [read_xlsx_rows](../../service/market/cn_margin_lending_pilot.py) — ligne 162 : `def read_xlsx_rows(raw: bytes) -> list[dict[str, str]]`
- [analyse_szse](../../service/market/cn_margin_lending_pilot.py) — ligne 207 : `def analyse_szse(raw: bytes, active: set[str]) -> dict`
- [_write_json](../../service/market/cn_margin_lending_pilot.py) — ligne 238 : `def _write_json(path: Path, payload: dict) -> None`
- [completed_raw_verified](../../service/market/cn_margin_lending_pilot.py) — ligne 244 : `def completed_raw_verified(root: Path, session: dict) -> bool`
- [run](../../service/market/cn_margin_lending_pilot.py) — ligne 254 : `def run(*, output_root: Path, start_year: int=2018, end_year: int=2025, pause_seconds: float=0.5, sample_mode: str='anchors') -> dict`
- [main](../../service/market/cn_margin_lending_pilot.py) — ligne 312 : `def main() -> None`

## `service/market/cn_operations_audit_17a.py`

Source SHA-256 : `1a810d431ed76467b8f4699978da4242609f3bf35b065f7aba83fa8331613fdc`

- [inspect](../../service/market/cn_operations_audit_17a.py) — ligne 19 : `def inspect(*, us_batch_path: Path, cn_batch_path: Path) -> dict`
- [main](../../service/market/cn_operations_audit_17a.py) — ligne 89 : `def main() -> None`

## `service/market/cn_oracle_daily_15d9.py`

Source SHA-256 : `b11924b36d09cdba0bca66d67719c90462cec08ffd8e9eaf159b990f44960b4c`

- [_path](../../service/market/cn_oracle_daily_15d9.py) — ligne 34 : `def _path(value: str | Path, *, base: Path) -> Path`
- [plan](../../service/market/cn_oracle_daily_15d9.py) — ligne 39 : `def plan(now: datetime, calendar: dict, *, earliest: time=time(18, 0)) -> dict`
- [_digest](../../service/market/cn_oracle_daily_15d9.py) — ligne 55 : `def _digest(path: Path) -> str`
- [verify_published](../../service/market/cn_oracle_daily_15d9.py) — ligne 63 : `def verify_published(folder: Path, *, decision: date) -> dict`
- [_verify_manifest_chunks](../../service/market/cn_oracle_daily_15d9.py) — ligne 78 : `def _verify_manifest_chunks(manifest: Path, chunks_root: Path) -> int`
- [_write_report](../../service/market/cn_oracle_daily_15d9.py) — ligne 96 : `def _write_report(root: Path, report: dict) -> Path`
- [execute](../../service/market/cn_oracle_daily_15d9.py) — ligne 105 : `def execute(*, batch_config: Path=ROOT / 'batch.yaml', now: datetime | None=None, dry_run: bool=False) -> dict`
- [_execute_locked](../../service/market/cn_oracle_daily_15d9.py) — ligne 153 : `def _execute_locked(cfg: dict, base: Path, output_root: Path, oracle_folder: Path, session: date, decision_day: date, decision: dict, catalog_identity: dict) -> dict`
- [main](../../service/market/cn_oracle_daily_15d9.py) — ligne 214 : `def main() -> None`

## `service/market/cn_oracle_export_readiness_15d7.py`

Source SHA-256 : `7a15158fe5956d8385e32098fb500a7531ac54a7b563f0d76ed40d7db2aec29d`

- [inspect](../../service/market/cn_oracle_export_readiness_15d7.py) — ligne 19 : `def inspect(*, snapshot_root: Path, calendar_path: Path, oracle_root: Path, candidate_export: Path | None=None, protocol_path: Path=Path('config/research_cn/sprint15d7_dragon_tiger_protocol.yaml'), engine=None, now: datetime | None=None) -> dict`
- [main](../../service/market/cn_oracle_export_readiness_15d7.py) — ligne 118 : `def main() -> None`

## `service/market/cn_portfolio_replay.py`

Source SHA-256 : `4f72909d9fdac15be7cfb6b9d19d73376c43452e868277135da245e5aa321f04`

- [CNInstrument](../../service/market/cn_portfolio_replay.py) — ligne 33 : `class CNInstrument`
- [CNBar](../../service/market/cn_portfolio_replay.py) — ligne 42 : `class CNBar`
- [CNIntent](../../service/market/cn_portfolio_replay.py) — ligne 56 : `class CNIntent`
- [CNAction](../../service/market/cn_portfolio_replay.py) — ligne 68 : `class CNAction`
- [ReplayConfig](../../service/market/cn_portfolio_replay.py) — ligne 79 : `class ReplayConfig`
- [ReplayConfig.__post_init__](../../service/market/cn_portfolio_replay.py) — ligne 92 : `def __post_init__(self) -> None`
- [_Lot](../../service/market/cn_portfolio_replay.py) — ligne 102 : `class _Lot`
- [_Pending](../../service/market/cn_portfolio_replay.py) — ligne 109 : `class _Pending`
- [ReplayResult](../../service/market/cn_portfolio_replay.py) — ligne 115 : `class ReplayResult`
- [_event](../../service/market/cn_portfolio_replay.py) — ligne 125 : `def _event(day: date, kind: str, **fields: Any) -> dict[str, Any]`
- [_positive_price](../../service/market/cn_portfolio_replay.py) — ligne 129 : `def _positive_price(value: Decimal | None) -> bool`
- [CNPortfolioReplay](../../service/market/cn_portfolio_replay.py) — ligne 133 : `class CNPortfolioReplay`
- [CNPortfolioReplay.__init__](../../service/market/cn_portfolio_replay.py) — ligne 136 : `def __init__(self, conn: Connection, config: ReplayConfig) -> None`
- [CNPortfolioReplay._rule](../../service/market/cn_portfolio_replay.py) — ligne 156 : `def _rule(self, instrument: CNInstrument, day: date)`
- [CNPortfolioReplay._cost](../../service/market/cn_portfolio_replay.py) — ligne 163 : `def _cost(self, day: date)`
- [CNPortfolioReplay._settle](../../service/market/cn_portfolio_replay.py) — ligne 169 : `def _settle(self, day: date) -> None`
- [CNPortfolioReplay._spend_cash](../../service/market/cn_portfolio_replay.py) — ligne 188 : `def _spend_cash(self, amount: Decimal) -> None`
- [CNPortfolioReplay._actions](../../service/market/cn_portfolio_replay.py) — ligne 205 : `def _actions(self, day: date, actions: list[CNAction]) -> None`
- [CNPortfolioReplay._attempt](../../service/market/cn_portfolio_replay.py) — ligne 240 : `def _attempt(self, day: date, pending: _Pending, instrument: CNInstrument, bar: CNBar | None) -> Literal['DONE', 'KEEP']`
- [CNPortfolioReplay.run](../../service/market/cn_portfolio_replay.py) — ligne 374 : `def run(self, *, sessions: list[date], instruments: list[CNInstrument], bars: list[CNBar], intents: list[CNIntent], actions: list[CNAction] | None=None) -> ReplayResult`

## `service/market/cn_shadow_execution_18b.py`

Source SHA-256 : `d3b0e325d15463ed82e8a2595147ec7980bafe9588d632f8fd8b81a12cc47076`

- [ShadowIntent](../../service/market/cn_shadow_execution_18b.py) — ligne 30 : `class ShadowIntent`
- [ShadowPlan](../../service/market/cn_shadow_execution_18b.py) — ligne 46 : `class ShadowPlan`
- [ShadowBar](../../service/market/cn_shadow_execution_18b.py) — ligne 54 : `class ShadowBar`
- [ShadowAttempt](../../service/market/cn_shadow_execution_18b.py) — ligne 71 : `class ShadowAttempt`
- [ShadowMark](../../service/market/cn_shadow_execution_18b.py) — ligne 99 : `class ShadowMark`
- [_fingerprint](../../service/market/cn_shadow_execution_18b.py) — ligne 110 : `def _fingerprint(value: object) -> str`
- [_shanghai_date](../../service/market/cn_shadow_execution_18b.py) — ligne 115 : `def _shanghai_date(value: datetime) -> date`
- [plan_shadow_intent](../../service/market/cn_shadow_execution_18b.py) — ligne 121 : `def plan_shadow_intent(intent: ShadowIntent, *, listing_date: date | None, delisting_date: date | None, known_trading_status: str | None=None, status_available_at: datetime | None=None, known_limit_policy: str | None=None, limit_available_at: datetime | None=None, delisting_available_at: datetime | None=None) -> ShadowPlan`
- [assess_shadow_attempt](../../service/market/cn_shadow_execution_18b.py) — ligne 170 : `def assess_shadow_attempt(plan: ShadowPlan, *, bar: ShadowBar | None, rule: ExecutionRule, profile: CostProfile, lots: tuple[InventoryLot, ...]=(), cash_available_cny: Decimal=Decimal(0), scenario: str='base', allow_research_rules: bool=False, allow_research_proxy: bool=False) -> ShadowAttempt`
- [mark_shadow_attempt](../../service/market/cn_shadow_execution_18b.py) — ligne 258 : `def mark_shadow_attempt(attempt: ShadowAttempt, *, next_bar: ShadowBar) -> ShadowMark`
- [write_shadow_audit](../../service/market/cn_shadow_execution_18b.py) — ligne 284 : `def write_shadow_audit(path: Path, *, plan: ShadowPlan, attempt: ShadowAttempt, mark: ShadowMark | None=None) -> None`

## `service/market/cn_shadow_runner_18c.py`

Source SHA-256 : `dea4a4795c8d4d5b7f288478abf5d9964b1ab86b3fdbe2419b594b05de8839f0`

- [_iso](../../service/market/cn_shadow_runner_18c.py) — ligne 38 : `def _iso(value: Any) -> datetime`
- [_utc_from_db](../../service/market/cn_shadow_runner_18c.py) — ligne 45 : `def _utc_from_db(value: datetime | str | None) -> datetime | None`
- [_date_from_db](../../service/market/cn_shadow_runner_18c.py) — ligne 53 : `def _date_from_db(value: date | str | None) -> date | None`
- [_sha](../../service/market/cn_shadow_runner_18c.py) — ligne 57 : `def _sha(path: Path) -> str`
- [_engine](../../service/market/cn_shadow_runner_18c.py) — ligne 65 : `def _engine(engine)`
- [_write_new](../../service/market/cn_shadow_runner_18c.py) — ligne 75 : `def _write_new(path: Path, payload: dict) -> None`
- [_symbol](../../service/market/cn_shadow_runner_18c.py) — ligne 82 : `def _symbol(exchange: str, code: str) -> tuple[str, str]`
- [_validate_export](../../service/market/cn_shadow_runner_18c.py) — ligne 89 : `def _validate_export(folder: Path, decision: date, now: datetime) -> tuple[dict, pd.DataFrame]`
- [_mapping](../../service/market/cn_shadow_runner_18c.py) — ligne 112 : `def _mapping(conn, symbols: list[str], decision: date, cutoff: datetime) -> dict[str, dict]`
- [prepare_plan](../../service/market/cn_shadow_runner_18c.py) — ligne 135 : `def prepare_plan(*, decision: date, output_path: Path, oracle_root: Path=DEFAULT_ORACLE_ROOT, now: datetime | None=None, sample_size: int=12, selection_seed: str='CN_SHADOW_18C_V1', budget_cny: Decimal=Decimal('10000'), engine=None) -> dict`
- [contract_readiness](../../service/market/cn_shadow_runner_18c.py) — ligne 210 : `def contract_readiness(*, decision: date, boards: list[tuple[str, str]], profile_key: str=PROFILE_KEY, engine=None) -> dict`
- [_decode_plan](../../service/market/cn_shadow_runner_18c.py) — ligne 241 : `def _decode_plan(raw: dict) -> ShadowPlan`
- [load_frozen_plan](../../service/market/cn_shadow_runner_18c.py) — ligne 256 : `def load_frozen_plan(path: Path, *, now: datetime | None=None) -> dict`
- [_session_close](../../service/market/cn_shadow_runner_18c.py) — ligne 293 : `def _session_close(conn, day: date) -> datetime`
- [_observed_bar](../../service/market/cn_shadow_runner_18c.py) — ligne 304 : `def _observed_bar(conn, *, instrument_id: int, day: date, now: datetime) -> ShadowBar | None`
- [_decode_bar](../../service/market/cn_shadow_runner_18c.py) — ligne 350 : `def _decode_bar(raw: dict | None) -> ShadowBar | None`
- [observation_readiness](../../service/market/cn_shadow_runner_18c.py) — ligne 367 : `def observation_readiness(*, plan_path: Path, now: datetime | None=None, engine=None) -> dict`
- [_decode_attempt](../../service/market/cn_shadow_runner_18c.py) — ligne 455 : `def _decode_attempt(raw: dict) -> ShadowAttempt`
- [assess_frozen_session](../../service/market/cn_shadow_runner_18c.py) — ligne 484 : `def assess_frozen_session(*, plan_path: Path, output_root: Path=DEFAULT_OUTPUT_ROOT, now: datetime | None=None, scenario: str='base', profile_key: str=PROFILE_KEY, allow_research_rules: bool=False, allow_research_proxy: bool=False, engine=None) -> dict`
- [mark_frozen_session](../../service/market/cn_shadow_runner_18c.py) — ligne 554 : `def mark_frozen_session(*, plan_path: Path, mark_session: date, output_root: Path=DEFAULT_OUTPUT_ROOT, now: datetime | None=None, engine=None) -> dict`
- [main](../../service/market/cn_shadow_runner_18c.py) — ligne 619 : `def main() -> None`

## `service/market/cn_szse_margin_dataset.py`

Source SHA-256 : `75e69158dd5abf51c0df0ab9f44187ded66b0f34302f7afe55459806d857944a`

- [sha](../../service/market/cn_szse_margin_dataset.py) — ligne 33 : `def sha(path: Path) -> str`
- [checkpoint](../../service/market/cn_szse_margin_dataset.py) — ligne 37 : `def checkpoint(path: Path, obj: dict) -> None`
- [integer_value](../../service/market/cn_szse_margin_dataset.py) — ligne 48 : `def integer_value(value: str) -> int`
- [fetch_day](../../service/market/cn_szse_margin_dataset.py) — ligne 55 : `def fetch_day(output: Path, key: str, catalog: str, tab: str, name: str, sources: dict) -> bytes`
- [reference_snapshot](../../service/market/cn_szse_margin_dataset.py) — ligne 61 : `def reference_snapshot(instruments: list[dict], sessions: list) -> dict`
- [dated_equities](../../service/market/cn_szse_margin_dataset.py) — ligne 71 : `def dated_equities(instruments: list[dict], day: date) -> dict`
- [build_rows](../../service/market/cn_szse_margin_dataset.py) — ligne 85 : `def build_rows(day: date, eligible_raw: bytes, detail_raw: bytes, active: dict, bars: dict, proxy: str | None) -> tuple[list[dict], dict]`
- [run](../../service/market/cn_szse_margin_dataset.py) — ligne 135 : `def run(*, config: Path, output: Path, start: date | None, end: date | None, pause: float, plan_only: bool=False) -> dict`
- [main](../../service/market/cn_szse_margin_dataset.py) — ligne 261 : `def main()`

## `service/market/cn_szse_margin_dataset_audit.py`

Source SHA-256 : `d5f3cc660ea9286ec610c43e35d1633f793714604ba29349bb99a94edd008c26`

- [validate_row](../../service/market/cn_szse_margin_dataset_audit.py) — ligne 19 : `def validate_row(row: dict, day: str, proxy: str | None, reference: dict) -> None`
- [run](../../service/market/cn_szse_margin_dataset_audit.py) — ligne 49 : `def run(root: Path, report_path: Path) -> dict`
- [main](../../service/market/cn_szse_margin_dataset_audit.py) — ligne 139 : `def main()`

## `service/market/cn_tradability_contract.py`

Source SHA-256 : `de2caecd36655f942ffc1f62cb04eec2fc1fa145b54af144d421b3a99360223e`

- [TradabilityAssessment](../../service/market/cn_tradability_contract.py) — ligne 13 : `class TradabilityAssessment`
- [_known_at](../../service/market/cn_tradability_contract.py) — ligne 18 : `def _known_at(available_at: datetime | None, decision_at: datetime) -> bool`
- [assess_pretrade](../../service/market/cn_tradability_contract.py) — ligne 22 : `def assess_pretrade(*, session_date: date, decision_at: datetime, listing_date: date | None, delisting_date: date | None, trading_status: str | None=None, status_available_at: datetime | None=None, limit_policy: str | None=None, limit_available_at: datetime | None=None) -> TradabilityAssessment`
- [assess_execution_data](../../service/market/cn_tradability_contract.py) — ligne 53 : `def assess_execution_data(*, bar_present: bool, trading_status: str | None, limit_policy: str | None, locked_up: bool | None=None, locked_down: bool | None=None) -> TradabilityAssessment`

## `service/market/cn_universe_pit.py`

Source SHA-256 : `e1f5fc44952ad64bc72f7e6881172f74e8324ad0d6b0c4f4e9278c1479094f31`

- [CNUniversePolicy](../../service/market/cn_universe_pit.py) — ligne 20 : `class CNUniversePolicy`
- [CNUniversePolicy.from_yaml](../../service/market/cn_universe_pit.py) — ligne 30 : `def from_yaml(cls, path: Path) -> CNUniversePolicy`
- [_fingerprint](../../service/market/cn_universe_pit.py) — ligne 47 : `def _fingerprint(value: Any) -> str`
- [decide_member](../../service/market/cn_universe_pit.py) — ligne 51 : `def decide_member(instrument: dict[str, Any], observation: dict[str, Any] | None, *, session_date: date, decision_at: datetime, previous_session: date | None, policy: CNUniversePolicy) -> dict[str, Any]`
- [_session_context](../../service/market/cn_universe_pit.py) — ligne 94 : `def _session_context(conn: Any, session_date: date, policy: CNUniversePolicy) -> tuple[datetime, date | None, date, date, datetime]`
- [build_snapshot](../../service/market/cn_universe_pit.py) — ligne 115 : `def build_snapshot(engine: Engine, *, session_date: date, policy: CNUniversePolicy, persist: bool=True) -> dict[str, Any]`
- [_persist_snapshot](../../service/market/cn_universe_pit.py) — ligne 186 : `def _persist_snapshot(engine: Engine, summary: dict[str, Any], members: list[dict[str, Any]], audits: list[dict[str, Any]]) -> None`
- [candidate_symbols](../../service/market/cn_universe_pit.py) — ligne 221 : `def candidate_symbols(engine: Engine, run_id: str) -> list[str]`

## `service/market/config.py`

Source SHA-256 : `e9fef265582287c9946a83d6f27086c0353d8a8346572ffc501c3510002b1e34`

- [CalendarPatternConfig](../../service/market/config.py) — ligne 14 : `class CalendarPatternConfig`
- [VixConfig](../../service/market/config.py) — ligne 28 : `class VixConfig`
- [YieldsConfig](../../service/market/config.py) — ligne 38 : `class YieldsConfig`
- [SentimentBreakerConfig](../../service/market/config.py) — ligne 67 : `class SentimentBreakerConfig`
- [SectorLimitsConfig](../../service/market/config.py) — ligne 78 : `class SectorLimitsConfig`
- [VxnConfig](../../service/market/config.py) — ligne 84 : `class VxnConfig`
- [Vix3mConfig](../../service/market/config.py) — ligne 92 : `class Vix3mConfig`
- [MoveConfig](../../service/market/config.py) — ligne 100 : `class MoveConfig`
- [RvxConfig](../../service/market/config.py) — ligne 108 : `class RvxConfig`
- [EarningsShieldConfig](../../service/market/config.py) — ligne 116 : `class EarningsShieldConfig`
- [BuybackBlackoutConfig](../../service/market/config.py) — ligne 125 : `class BuybackBlackoutConfig`
- [SentinelConfig](../../service/market/config.py) — ligne 132 : `class SentinelConfig`
- [RegimeHysteresisConfig](../../service/market/config.py) — ligne 138 : `class RegimeHysteresisConfig`
- [MarketRegimesConfig](../../service/market/config.py) — ligne 155 : `class MarketRegimesConfig`
- [TrailingStopYAMLConfig](../../service/market/config.py) — ligne 186 : `class TrailingStopYAMLConfig`
- [_to_pattern](../../service/market/config.py) — ligne 201 : `def _to_pattern(name: str, raw: Mapping[str, Any] | None) -> CalendarPatternConfig`
- [parse_market_regimes](../../service/market/config.py) — ligne 217 : `def parse_market_regimes(raw: Mapping[str, Any] | None) -> MarketRegimesConfig`
- [parse_trailing_stop](../../service/market/config.py) — ligne 413 : `def parse_trailing_stop(raw: Mapping[str, Any] | None) -> TrailingStopYAMLConfig`

## `service/market/earnings_shield.py`

Source SHA-256 : `796dd76e5dfe04fe0dbda6e232afdcc5d26baabfe2ebf0d37d17ba217d715890`

- [EarningsShieldResult](../../service/market/earnings_shield.py) — ligne 24 : `class EarningsShieldResult`
- [default_db_lookup](../../service/market/earnings_shield.py) — ligne 30 : `def default_db_lookup(trade_date: date, lookback_days: int, lookahead_days: int) -> dict[str, date]`
- [compute_earnings_shield](../../service/market/earnings_shield.py) — ligne 63 : `def compute_earnings_shield(trade_date: date, *, shield_cfg: EarningsShieldConfig, blackout_cfg: BuybackBlackoutConfig, lookup: EarningsLookup | None=None) -> EarningsShieldResult`

## `service/market/macro_providers.py`

Source SHA-256 : `06e3171d2d86d6be6e52b64d8b145924d9bd4a514e466f2fc15e9140ad704ee8`

- [normalize_macro_pit_mode](../../service/market/macro_providers.py) — ligne 70 : `def normalize_macro_pit_mode(value: object) -> str`
- [resolve_macro_pit_mode](../../service/market/macro_providers.py) — ligne 86 : `def resolve_macro_pit_mode(yaml_cfg: Mapping[str, Any] | None, *, execution_context: str='live', macro_pit_mode: str | None=None) -> str`
- [_is_strict_before_mode](../../service/market/macro_providers.py) — ligne 103 : `def _is_strict_before_mode(*, yaml_cfg: Mapping[str, Any] | None, execution_context: str, macro_pit_mode: str | None) -> bool`
- [_resolve_provider_trade_date](../../service/market/macro_providers.py) — ligne 111 : `def _resolve_provider_trade_date(trade_date: date, *, strict_before: bool) -> date`
- [_coerce_float](../../service/market/macro_providers.py) — ligne 121 : `def _coerce_float(value: object) -> float | None`
- [_effective_source_from_mapping](../../service/market/macro_providers.py) — ligne 128 : `def _effective_source_from_mapping(source_by_signal: Mapping[str, str]) -> str | None`
- [_build_source_summary](../../service/market/macro_providers.py) — ligne 138 : `def _build_source_summary(source_by_signal: Mapping[str, str]) -> dict[str, Any]`
- [_signal_key_for_method](../../service/market/macro_providers.py) — ligne 153 : `def _signal_key_for_method(method: str) -> str | None`
- [_resolve_signal_source](../../service/market/macro_providers.py) — ligne 171 : `def _resolve_signal_source(provider: Any, signal_key: str) -> str | None`
- [_log_successful_fetch](../../service/market/macro_providers.py) — ligne 188 : `def _log_successful_fetch(*, provider_name: str, key: str, symbol: str, trade_date: date, bars: Sequence[Mapping[str, Any]]) -> None`
- [_last_close](../../service/market/macro_providers.py) — ligne 231 : `def _last_close(bars: Sequence[Mapping[str, Any]], on_or_before: date) -> float | None`
- [_close_history](../../service/market/macro_providers.py) — ligne 256 : `def _close_history(bars: Sequence[Mapping[str, Any]], on_or_before: date, n: int) -> list[float]`
- [_extract_latest_10y_close](../../service/market/macro_providers.py) — ligne 277 : `def _extract_latest_10y_close(provider: Any, trade_date: date) -> float | None`
- [StooqMacroProvider](../../service/market/macro_providers.py) — ligne 300 : `class StooqMacroProvider`
- [StooqMacroProvider.__init__](../../service/market/macro_providers.py) — ligne 305 : `def __init__(self, symbols: Mapping[str, str] | None=None) -> None`
- [StooqMacroProvider._fetch](../../service/market/macro_providers.py) — ligne 312 : `def _fetch(self, key: str, trade_date: date, days_back: int) -> list[dict[str, Any]]`
- [StooqMacroProvider.get_vix_close](../../service/market/macro_providers.py) — ligne 343 : `def get_vix_close(self, trade_date: date) -> float | None`
- [StooqMacroProvider.get_vix_short_term_close](../../service/market/macro_providers.py) — ligne 352 : `def get_vix_short_term_close(self, trade_date: date) -> float | None`
- [StooqMacroProvider.get_us10y_history](../../service/market/macro_providers.py) — ligne 361 : `def get_us10y_history(self, trade_date: date, lookback_days: int) -> list[float] | None`
- [StooqMacroProvider.get_us10y_close](../../service/market/macro_providers.py) — ligne 375 : `def get_us10y_close(self, trade_date: date) -> float | None`
- [StooqMacroProvider.get_vxn_close](../../service/market/macro_providers.py) — ligne 385 : `def get_vxn_close(self, trade_date: date) -> float | None`
- [StooqMacroProvider.get_vix3m_close](../../service/market/macro_providers.py) — ligne 389 : `def get_vix3m_close(self, trade_date: date) -> float | None`
- [StooqMacroProvider.get_move_close](../../service/market/macro_providers.py) — ligne 393 : `def get_move_close(self, trade_date: date) -> float | None`
- [StooqMacroProvider.get_rvx_close](../../service/market/macro_providers.py) — ligne 397 : `def get_rvx_close(self, trade_date: date) -> float | None`
- [StooqMacroProvider.get_macro_source_summary](../../service/market/macro_providers.py) — ligne 401 : `def get_macro_source_summary(self) -> dict[str, Any]`
- [EodhdMacroProvider](../../service/market/macro_providers.py) — ligne 410 : `class EodhdMacroProvider`
- [EodhdMacroProvider.__init__](../../service/market/macro_providers.py) — ligne 418 : `def __init__(self, symbols: Mapping[str, str] | None=None) -> None`
- [EodhdMacroProvider._fetch](../../service/market/macro_providers.py) — ligne 425 : `def _fetch(self, key: str, trade_date: date, days_back: int) -> list[dict[str, Any]]`
- [EodhdMacroProvider.get_vix_close](../../service/market/macro_providers.py) — ligne 474 : `def get_vix_close(self, trade_date: date) -> float | None`
- [EodhdMacroProvider.get_vix_short_term_close](../../service/market/macro_providers.py) — ligne 483 : `def get_vix_short_term_close(self, trade_date: date) -> float | None`
- [EodhdMacroProvider.get_us10y_history](../../service/market/macro_providers.py) — ligne 492 : `def get_us10y_history(self, trade_date: date, lookback_days: int) -> list[float] | None`
- [EodhdMacroProvider.get_us10y_close](../../service/market/macro_providers.py) — ligne 505 : `def get_us10y_close(self, trade_date: date) -> float | None`
- [EodhdMacroProvider.get_vxn_close](../../service/market/macro_providers.py) — ligne 514 : `def get_vxn_close(self, trade_date: date) -> float | None`
- [EodhdMacroProvider.get_vix3m_close](../../service/market/macro_providers.py) — ligne 523 : `def get_vix3m_close(self, trade_date: date) -> float | None`
- [EodhdMacroProvider.get_move_close](../../service/market/macro_providers.py) — ligne 532 : `def get_move_close(self, trade_date: date) -> float | None`
- [EodhdMacroProvider.get_rvx_close](../../service/market/macro_providers.py) — ligne 541 : `def get_rvx_close(self, trade_date: date) -> float | None`
- [EodhdMacroProvider.get_macro_source_summary](../../service/market/macro_providers.py) — ligne 550 : `def get_macro_source_summary(self) -> dict[str, Any]`
- [FredMacroProvider](../../service/market/macro_providers.py) — ligne 559 : `class FredMacroProvider`
- [FredMacroProvider.__init__](../../service/market/macro_providers.py) — ligne 564 : `def __init__(self, *, series: Mapping[str, str] | None=None, api_key_env: str='KEY_FRED') -> None`
- [FredMacroProvider._fetch](../../service/market/macro_providers.py) — ligne 572 : `def _fetch(self, key: str, trade_date: date, days_back: int) -> list[dict[str, Any]]`
- [FredMacroProvider.get_vix_close](../../service/market/macro_providers.py) — ligne 630 : `def get_vix_close(self, trade_date: date) -> float | None`
- [FredMacroProvider.get_vix_short_term_close](../../service/market/macro_providers.py) — ligne 634 : `def get_vix_short_term_close(self, trade_date: date) -> float | None`
- [FredMacroProvider.get_vxn_close](../../service/market/macro_providers.py) — ligne 639 : `def get_vxn_close(self, trade_date: date) -> float | None`
- [FredMacroProvider.get_vix3m_close](../../service/market/macro_providers.py) — ligne 643 : `def get_vix3m_close(self, trade_date: date) -> float | None`
- [FredMacroProvider.get_move_close](../../service/market/macro_providers.py) — ligne 647 : `def get_move_close(self, trade_date: date) -> float | None`
- [FredMacroProvider.get_rvx_close](../../service/market/macro_providers.py) — ligne 651 : `def get_rvx_close(self, trade_date: date) -> float | None`
- [FredMacroProvider.get_us10y_history](../../service/market/macro_providers.py) — ligne 655 : `def get_us10y_history(self, trade_date: date, lookback_days: int) -> list[float] | None`
- [FredMacroProvider.get_us10y_close](../../service/market/macro_providers.py) — ligne 668 : `def get_us10y_close(self, trade_date: date) -> float | None`
- [FredMacroProvider.get_macro_source_summary](../../service/market/macro_providers.py) — ligne 677 : `def get_macro_source_summary(self) -> dict[str, Any]`
- [RoutedMacroProvider](../../service/market/macro_providers.py) — ligne 681 : `class RoutedMacroProvider`
- [RoutedMacroProvider.__init__](../../service/market/macro_providers.py) — ligne 686 : `def __init__(self, *, vix_provider: Any | None=None, vix_short_provider: Any | None=None, yield_provider: Any | None=None) -> None`
- [RoutedMacroProvider._record_source](../../service/market/macro_providers.py) — ligne 698 : `def _record_source(self, signal_key: str, provider: Any | None, value: Any) -> None`
- [RoutedMacroProvider.get_vix_close](../../service/market/macro_providers.py) — ligne 708 : `def get_vix_close(self, trade_date: date) -> float | None`
- [RoutedMacroProvider.get_vix_short_term_close](../../service/market/macro_providers.py) — ligne 720 : `def get_vix_short_term_close(self, trade_date: date) -> float | None`
- [RoutedMacroProvider.get_us10y_history](../../service/market/macro_providers.py) — ligne 732 : `def get_us10y_history(self, trade_date: date, lookback_days: int) -> list[float] | None`
- [RoutedMacroProvider.get_us10y_close](../../service/market/macro_providers.py) — ligne 744 : `def get_us10y_close(self, trade_date: date) -> float | None`
- [RoutedMacroProvider.get_vxn_close](../../service/market/macro_providers.py) — ligne 754 : `def get_vxn_close(self, trade_date: date) -> float | None`
- [RoutedMacroProvider.get_vix3m_close](../../service/market/macro_providers.py) — ligne 766 : `def get_vix3m_close(self, trade_date: date) -> float | None`
- [RoutedMacroProvider.get_move_close](../../service/market/macro_providers.py) — ligne 778 : `def get_move_close(self, trade_date: date) -> float | None`
- [RoutedMacroProvider.get_rvx_close](../../service/market/macro_providers.py) — ligne 790 : `def get_rvx_close(self, trade_date: date) -> float | None`
- [RoutedMacroProvider.get_macro_source_summary](../../service/market/macro_providers.py) — ligne 802 : `def get_macro_source_summary(self) -> dict[str, Any]`
- [TableFirstMacroProvider](../../service/market/macro_providers.py) — ligne 806 : `class TableFirstMacroProvider`
- [TableFirstMacroProvider.__init__](../../service/market/macro_providers.py) — ligne 816 : `def __init__(self, provider: Any | None, *, engine=None, strict_before: bool=False, persist_fallback_hits: bool=True) -> None`
- [TableFirstMacroProvider._load_cached_row](../../service/market/macro_providers.py) — ligne 830 : `def _load_cached_row(self, trade_date: date) -> dict[str, Any] | None`
- [TableFirstMacroProvider._load_cached_history](../../service/market/macro_providers.py) — ligne 841 : `def _load_cached_history(self, trade_date: date, *, column: str, lookback_days: int) -> list[float] | None`
- [TableFirstMacroProvider._persist_fallback_value](../../service/market/macro_providers.py) — ligne 854 : `def _persist_fallback_value(self, *, trade_date: date, value_key: str, value: Any) -> None`
- [TableFirstMacroProvider._record_source](../../service/market/macro_providers.py) — ligne 884 : `def _record_source(self, signal_key: str, source: str | None) -> None`
- [TableFirstMacroProvider.get_vix_close](../../service/market/macro_providers.py) — ligne 891 : `def get_vix_close(self, trade_date: date) -> float | None`
- [TableFirstMacroProvider.get_vix_short_term_close](../../service/market/macro_providers.py) — ligne 913 : `def get_vix_short_term_close(self, trade_date: date) -> float | None`
- [TableFirstMacroProvider.get_us10y_history](../../service/market/macro_providers.py) — ligne 935 : `def get_us10y_history(self, trade_date: date, lookback_days: int) -> list[float] | None`
- [TableFirstMacroProvider.get_us10y_close](../../service/market/macro_providers.py) — ligne 967 : `def get_us10y_close(self, trade_date: date) -> float | None`
- [TableFirstMacroProvider._get_cached_or_fallback](../../service/market/macro_providers.py) — ligne 987 : `def _get_cached_or_fallback(self, trade_date: date, *, db_column: str, signal_key: str, provider_method: str, persist_value_key: str) -> float | None`
- [TableFirstMacroProvider.get_vxn_close](../../service/market/macro_providers.py) — ligne 1018 : `def get_vxn_close(self, trade_date: date) -> float | None`
- [TableFirstMacroProvider.get_vix3m_close](../../service/market/macro_providers.py) — ligne 1027 : `def get_vix3m_close(self, trade_date: date) -> float | None`
- [TableFirstMacroProvider.get_move_close](../../service/market/macro_providers.py) — ligne 1036 : `def get_move_close(self, trade_date: date) -> float | None`
- [TableFirstMacroProvider.get_rvx_close](../../service/market/macro_providers.py) — ligne 1045 : `def get_rvx_close(self, trade_date: date) -> float | None`
- [TableFirstMacroProvider.get_macro_source_summary](../../service/market/macro_providers.py) — ligne 1054 : `def get_macro_source_summary(self) -> dict[str, Any]`
- [CompositeMacroProvider](../../service/market/macro_providers.py) — ligne 1063 : `class CompositeMacroProvider`
- [CompositeMacroProvider.__init__](../../service/market/macro_providers.py) — ligne 1066 : `def __init__(self, providers: Sequence[Any]) -> None`
- [CompositeMacroProvider._first_non_none](../../service/market/macro_providers.py) — ligne 1070 : `def _first_non_none(self, method: str, *args: Any) -> Any`
- [CompositeMacroProvider.get_vix_close](../../service/market/macro_providers.py) — ligne 1086 : `def get_vix_close(self, trade_date: date) -> float | None`
- [CompositeMacroProvider.get_vix_short_term_close](../../service/market/macro_providers.py) — ligne 1089 : `def get_vix_short_term_close(self, trade_date: date) -> float | None`
- [CompositeMacroProvider.get_us10y_history](../../service/market/macro_providers.py) — ligne 1092 : `def get_us10y_history(self, trade_date: date, lookback_days: int) -> list[float] | None`
- [CompositeMacroProvider.get_us10y_close](../../service/market/macro_providers.py) — ligne 1095 : `def get_us10y_close(self, trade_date: date) -> float | None`
- [CompositeMacroProvider.get_vxn_close](../../service/market/macro_providers.py) — ligne 1098 : `def get_vxn_close(self, trade_date: date) -> float | None`
- [CompositeMacroProvider.get_vix3m_close](../../service/market/macro_providers.py) — ligne 1101 : `def get_vix3m_close(self, trade_date: date) -> float | None`
- [CompositeMacroProvider.get_move_close](../../service/market/macro_providers.py) — ligne 1104 : `def get_move_close(self, trade_date: date) -> float | None`
- [CompositeMacroProvider.get_rvx_close](../../service/market/macro_providers.py) — ligne 1107 : `def get_rvx_close(self, trade_date: date) -> float | None`
- [CompositeMacroProvider.get_macro_source_summary](../../service/market/macro_providers.py) — ligne 1110 : `def get_macro_source_summary(self) -> dict[str, Any]`
- [_build_primary_macro_provider](../../service/market/macro_providers.py) — ligne 1114 : `def _build_primary_macro_provider(choice: str, *, stooq_overrides: Mapping[str, str] | None, eodhd_overrides: Mapping[str, str] | None) -> Any | None`
- [_build_yield_macro_provider](../../service/market/macro_providers.py) — ligne 1133 : `def _build_yield_macro_provider(*, yields_cfg: Mapping[str, Any], fred_cfg: Mapping[str, Any], stooq_overrides: Mapping[str, str] | None, eodhd_overrides: Mapping[str, str] | None, default_provider: Any | None) -> Any | None`
- [_build_network_macro_provider](../../service/market/macro_providers.py) — ligne 1164 : `def _build_network_macro_provider(yaml_cfg: Mapping[str, Any] | None) -> Any | None`
- [build_default_macro_provider](../../service/market/macro_providers.py) — ligne 1229 : `def build_default_macro_provider(yaml_cfg: Mapping[str, Any] | None, *, execution_context: str='live', macro_pit_mode: str | None=None, engine=None) -> Any | None`
- [_snapshot_to_payload](../../service/market/macro_providers.py) — ligne 1261 : `def _snapshot_to_payload(snapshot: object) -> dict[str, Any]`
- [_snapshot_to_next_state](../../service/market/macro_providers.py) — ligne 1269 : `def _snapshot_to_next_state(snapshot: object, payload: Mapping[str, Any] | None=None) -> MarketRegimeState | None`
- [populate_macro_indicators_table](../../service/market/macro_providers.py) — ligne 1283 : `def populate_macro_indicators_table(*, start_date: date, end_date: date, yaml_cfg: Mapping[str, Any] | None=None, equity: float | None=None, engine=None, progress_callback: Callable[[dict[str, Any]], None] | None=None) -> dict[str, Any]`
- [recompute_macro_regime_table](../../service/market/macro_providers.py) — ligne 1380 : `def recompute_macro_regime_table(*, start_date: date, end_date: date, yaml_cfg: Mapping[str, Any] | None=None, equity: float | None=None, engine=None, progress_callback: Callable[[dict[str, Any]], None] | None=None) -> dict[str, Any]`

## `service/market/macro_signals.py`

Source SHA-256 : `1bb1fb21190fd41a510c2900ed9f1db675f70aa2c066580418509ee4c712a0f3`

- [MacroDataProvider](../../service/market/macro_signals.py) — ligne 15 : `class MacroDataProvider(Protocol)`
- [MacroDataProvider.get_vix_close](../../service/market/macro_signals.py) — ligne 23 : `def get_vix_close(self, trade_date: date) -> float | None`
- [MacroDataProvider.get_vix_short_term_close](../../service/market/macro_signals.py) — ligne 24 : `def get_vix_short_term_close(self, trade_date: date) -> float | None`
- [MacroDataProvider.get_vxn_close](../../service/market/macro_signals.py) — ligne 27 : `def get_vxn_close(self, trade_date: date) -> float | None`
- [MacroDataProvider.get_vix3m_close](../../service/market/macro_signals.py) — ligne 30 : `def get_vix3m_close(self, trade_date: date) -> float | None`
- [MacroDataProvider.get_move_close](../../service/market/macro_signals.py) — ligne 33 : `def get_move_close(self, trade_date: date) -> float | None`
- [MacroDataProvider.get_rvx_close](../../service/market/macro_signals.py) — ligne 36 : `def get_rvx_close(self, trade_date: date) -> float | None`
- [MacroDataProvider.get_us10y_history](../../service/market/macro_signals.py) — ligne 39 : `def get_us10y_history(self, trade_date: date, lookback_days: int) -> list[float] | None`
- [MacroEvaluation](../../service/market/macro_signals.py) — ligne 43 : `class MacroEvaluation`
- [MacroEvaluation.__post_init__](../../service/market/macro_signals.py) — ligne 52 : `def __post_init__(self) -> None`
- [VixTermStructure](../../service/market/macro_signals.py) — ligne 58 : `class VixTermStructure`
- [evaluate_vix](../../service/market/macro_signals.py) — ligne 68 : `def evaluate_vix(provider: MacroDataProvider | None, trade_date: date, *, high_threshold: float, inverted_curve_min_spread: float=0.0, inverted_curve_min_ratio: float=1.0) -> tuple[float | None, bool, bool, dict[str, str]]`
- [evaluate_vxn](../../service/market/macro_signals.py) — ligne 103 : `def evaluate_vxn(provider: MacroDataProvider | None, trade_date: date, *, high_threshold: float) -> tuple[float | None, bool, dict[str, str]]`
- [evaluate_vix_term_structure](../../service/market/macro_signals.py) — ligne 121 : `def evaluate_vix_term_structure(provider: MacroDataProvider | None, trade_date: date, *, backwardation_threshold: float=1.0) -> VixTermStructure`
- [evaluate_yield_10y](../../service/market/macro_signals.py) — ligne 174 : `def evaluate_yield_10y(provider: MacroDataProvider | None, trade_date: date, *, lookback_days: int, relative_spike_threshold: float) -> tuple[float | None, bool, dict[str, str]]`

## `service/market/models.py`

Source SHA-256 : `b27c98525ca06db3adbbb429febb5742e78ccb7d3b452470beb2970a0aedcb66`

- [MarketRegimeState](../../service/market/models.py) — ligne 31 : `class MarketRegimeState`
- [MarketRegimeState.to_dict](../../service/market/models.py) — ligne 46 : `def to_dict(self) -> dict[str, Any]`
- [MarketRegimeState.from_dict](../../service/market/models.py) — ligne 62 : `def from_dict(cls, payload: Mapping[str, Any]) -> 'MarketRegimeState'`
- [MarketRegimeSnapshot](../../service/market/models.py) — ligne 84 : `class MarketRegimeSnapshot`
- [MarketRegimeSnapshot.is_defensive](../../service/market/models.py) — ligne 145 : `def is_defensive(self) -> bool`
- [MarketRegimeSnapshot.blocks_entry_for](../../service/market/models.py) — ligne 148 : `def blocks_entry_for(self, symbol: str, sector: str | None, side: str='buy') -> tuple[bool, str | None]`
- [MarketRegimeSnapshot.to_summary_dict](../../service/market/models.py) — ligne 177 : `def to_summary_dict(self) -> dict`
- [MarketRegimeSnapshot.to_dict](../../service/market/models.py) — ligne 226 : `def to_dict(self) -> dict`
- [neutral_snapshot](../../service/market/models.py) — ligne 235 : `def neutral_snapshot(trade_date: date) -> MarketRegimeSnapshot`

## `service/market/new_entry_data_guard.py`

Source SHA-256 : `c9311c0320baa8c6cd6d124e005276366206b5c9b7f16d9070e31456fd4c4271`

- [entry_sessions](../../service/market/new_entry_data_guard.py) — ligne 13 : `def entry_sessions(trade_date, *, now=None, min_sessions=61, publication_delay_minutes=15)`
- [validate_entry_bars](../../service/market/new_entry_data_guard.py) — ligne 34 : `def validate_entry_bars(frame, symbols, sessions, *, now)`
- [check_new_entry_data](../../service/market/new_entry_data_guard.py) — ligne 70 : `def check_new_entry_data(engine, symbols, trade_date, *, now=None, required_sessions=21, raw_config=None)`
- [validate_entry_prices](../../service/market/new_entry_data_guard.py) — ligne 104 : `def validate_entry_prices(prices, symbols, trade_date)`

## `service/market/oracle_atr_missing_report.py`

Source SHA-256 : `bb4350e813c47c859c8766cc63897fd80dfa8d88bbb73c9446048bfa92a9f660`

- [explain_day](../../service/market/oracle_atr_missing_report.py) — ligne 21 : `def explain_day(scores, atr, labels, *, as_of, available_date)`
- [run](../../service/market/oracle_atr_missing_report.py) — ligne 60 : `def run(*, batch_id, start_date, end_date, symbol_source, output, horizon=20)`
- [main](../../service/market/oracle_atr_missing_report.py) — ligne 111 : `def main()`

## `service/market/oracle_atr_repair.py`

Source SHA-256 : `287dc0fa3badd67324c687646a926be25a8021e13a61a241fad2a038e78a4dac`

- [save](../../service/market/oracle_atr_repair.py) — ligne 32 : `def save(path, payload)`
- [calendar_changes](../../service/market/oracle_atr_repair.py) — ligne 53 : `def calendar_changes(groups, calendar)`
- [rebuild_dates](../../service/market/oracle_atr_repair.py) — ligne 72 : `def rebuild_dates(wrong_exits, synthetic_days, invalid, *, include_invalid=False)`
- [fetch_price_evidence](../../service/market/oracle_atr_repair.py) — ligne 80 : `def fetch_price_evidence(symbol, start, end, *, session)`
- [coverage](../../service/market/oracle_atr_repair.py) — ligne 91 : `def coverage(engine, batch_id, horizon, start, end)`
- [qualify_static_extension](../../service/market/oracle_atr_repair.py) — ligne 100 : `def qualify_static_extension(engine, batch_id, horizon, reference_day)`
- [run](../../service/market/oracle_atr_repair.py) — ligne 120 : `def run(*, batch_id, horizon, start_date, end_date, symbol_source, output, apply=False, fetch_prices=False, rebuild_invalid_labels=False, engine=None)`
- [main](../../service/market/oracle_atr_repair.py) — ligne 301 : `def main()`

## `service/market/oracle_atr_study.py`

Source SHA-256 : `39a45005d59544e8b88b5091444cbdcbee835e88e1dc711f646cf6518f562f6e`

- [resolve_returns_policy](../../service/market/oracle_atr_study.py) — ligne 30 : `def resolve_returns_policy(value=None) -> str`
- [summarize_day](../../service/market/oracle_atr_study.py) — ligne 39 : `def summarize_day(scores, atr, labels, macro, *, as_of: date, missing_returns_policy='strict', expected_available_date=None) -> dict`
- [run](../../service/market/oracle_atr_study.py) — ligne 202 : `def run(*, batch_id: str, symbol_source: str, start_date: str, end_date: str, artifacts_dir='artifacts/models', engine=None, progress_callback=None, date_batch_size: int=20, resume: bool=True, trade_dates: list[str] | None=None, missing_returns_policy=None) -> dict`
- [_calculate_tranche](../../service/market/oracle_atr_study.py) — ligne 275 : `def _calculate_tranche(engine, symbols, days, batch_id, horizon, as_of, policy='strict')`
- [_persist_tranche](../../service/market/oracle_atr_study.py) — ligne 312 : `def _persist_tranche(engine, records)`
- [main](../../service/market/oracle_atr_study.py) — ligne 322 : `def main()`

## `service/market/regime_manager.py`

Source SHA-256 : `2352e6de9e4579180b89e3ef77dbb4e11dda0441b8cca848a4d3b1cbb7559618`

- [MacroDataUnavailableError](../../service/market/regime_manager.py) — ligne 45 : `class MacroDataUnavailableError(RuntimeError)`
- [_CacheEntry](../../service/market/regime_manager.py) — ligne 50 : `class _CacheEntry`
- [_mode_strength](../../service/market/regime_manager.py) — ligne 60 : `def _mode_strength(mode: RegimeMode) -> int`
- [_escalate](../../service/market/regime_manager.py) — ligne 65 : `def _escalate(current: RegimeMode, candidate: str) -> RegimeMode`
- [_push_trace](../../service/market/regime_manager.py) — ligne 73 : `def _push_trace(trace: list[dict[str, Any]], *, source: str, label: str, triggered: bool, severity: str, message: str, resulting_mode: str='normal', value: Any=None, threshold: Any=None, details: dict[str, Any] | None=None) -> None`
- [_build_mode_why](../../service/market/regime_manager.py) — ligne 103 : `def _build_mode_why(mode: RegimeMode, reasons: list[str], trace: list[dict[str, Any]]) -> dict[str, Any]`
- [_required_macro_data_quality_keys](../../service/market/regime_manager.py) — ligne 134 : `def _required_macro_data_quality_keys(config: MarketRegimesConfig) -> tuple[str, ...]`
- [_resolve_missing_macro_data_quality](../../service/market/regime_manager.py) — ligne 151 : `def _resolve_missing_macro_data_quality(config: MarketRegimesConfig, data_quality: dict[str, str]) -> dict[str, str]`
- [_tighten_numeric_limit](../../service/market/regime_manager.py) — ligne 162 : `def _tighten_numeric_limit(current: int | float | None, candidate: int | float | None) -> int | float | None`
- [_state_cache_key](../../service/market/regime_manager.py) — ligne 170 : `def _state_cache_key(previous_state: MarketRegimeState | None) -> tuple[Any, ...]`
- [_count_triggered_sources](../../service/market/regime_manager.py) — ligne 188 : `def _count_triggered_sources(trace: list[dict[str, Any]], sources: frozenset[str]) -> int`
- [_transition_without_hysteresis](../../service/market/regime_manager.py) — ligne 192 : `def _transition_without_hysteresis(trade_date: date, *, raw_mode: RegimeMode, previous_state: MarketRegimeState | None, hard_triggered: bool) -> tuple[RegimeMode, MarketRegimeState, str, int]`
- [_apply_hysteresis](../../service/market/regime_manager.py) — ligne 231 : `def _apply_hysteresis(trade_date: date, *, raw_mode: RegimeMode, previous_state: MarketRegimeState | None, soft_signal_count: int, hard_triggered: bool, config: MarketRegimesConfig) -> tuple[RegimeMode, MarketRegimeState, str, int]`
- [build_snapshot](../../service/market/regime_manager.py) — ligne 385 : `def build_snapshot(trade_date: date, *, config: MarketRegimesConfig, equity: float | None=None, execution_context: ExecutionContext='live', macro_provider: MacroDataProvider | None=None, sentiment_score_provider: Callable[[int], float | None] | None=None, earnings_lookup: EarningsLookup | None=None, previous_state: MarketRegimeState | None=None, use_cache: bool=True) -> MarketRegimeSnapshot`
- [reset_cache](../../service/market/regime_manager.py) — ligne 1311 : `def reset_cache() -> None`

## `service/market/sentiment_provider.py`

Source SHA-256 : `420c3452e2ff5a0a31f82ef500f5c76f784f0d251750813735c278c5feb7adf6`

- [MarketSentimentReading](../../service/market/sentiment_provider.py) — ligne 26 : `class MarketSentimentReading`
- [MarketSentimentReading.to_dict](../../service/market/sentiment_provider.py) — ligne 36 : `def to_dict(self) -> dict[str, Any]`
- [_normalize_trade_date](../../service/market/sentiment_provider.py) — ligne 49 : `def _normalize_trade_date(value: Any) -> date | None`
- [_query_market_sentiment](../../service/market/sentiment_provider.py) — ligne 60 : `def _query_market_sentiment(engine: Engine, *, trade_date: date, lookback_days: int, table_name: str, news_col: str, sentiment_col: str) -> MarketSentimentReading`
- [load_market_sentiment_reading](../../service/market/sentiment_provider.py) — ligne 129 : `def load_market_sentiment_reading(trade_date: date, lookback_days: int, *, engine: Engine | None=None) -> MarketSentimentReading`
- [DbSentimentScoreProvider](../../service/market/sentiment_provider.py) — ligne 191 : `class DbSentimentScoreProvider`
- [DbSentimentScoreProvider.__init__](../../service/market/sentiment_provider.py) — ligne 194 : `def __init__(self, trade_date: date, *, engine: Engine | None=None) -> None`
- [DbSentimentScoreProvider.__call__](../../service/market/sentiment_provider.py) — ligne 200 : `def __call__(self, lookback_days: int) -> float | None`

## `service/market/sentiment_regime.py`

Source SHA-256 : `0587a91f4462990b84af4bf35050090a5b8b015e91299592de218fe883e5752f`

- [SentimentRegimeEvaluation](../../service/market/sentiment_regime.py) — ligne 18 : `class SentimentRegimeEvaluation`
- [evaluate_sentiment_regime](../../service/market/sentiment_regime.py) — ligne 27 : `def evaluate_sentiment_regime(cfg: SentimentBreakerConfig, *, score_provider: Callable[[int], float | None] | None, execution_context: Literal['live', 'backtest']) -> SentimentRegimeEvaluation`

## `service/market/state_store.py`

Source SHA-256 : `5d6f1cd896346196fe8e7ea967c5717187bc5b0c5922834f7dfcf0f5f291af27`

- [load_regime_state](../../service/market/state_store.py) — ligne 17 : `def load_regime_state(path: Path | None=None) -> MarketRegimeState | None`
- [save_regime_state](../../service/market/state_store.py) — ligne 27 : `def save_regime_state(state: MarketRegimeState | None, path: Path | None=None) -> Path`

## `service/market/volatility.py`

Source SHA-256 : `04ea074c9f5a35f0cbbd9060762e8ccfa8d4560662485a841fb609a4fc5416f9`

- [OHLCBar](../../service/market/volatility.py) — ligne 19 : `class OHLCBar`
- [compute_atr_from_bars](../../service/market/volatility.py) — ligne 25 : `def compute_atr_from_bars(bars: Sequence[OHLCBar], period: int=14) -> float | None`
- [compute_atr_from_eodhd_cache](../../service/market/volatility.py) — ligne 51 : `def compute_atr_from_eodhd_cache(symbol: str, *, period: int=14, lookback_days: int=60) -> float | None`

## `service/market_calendar_sync.py`

Source SHA-256 : `e9e20fd728d8faf53221fb528bb8d0661044c953fa08d19d74807342eb1ba07c`

- [main](../../service/market_calendar_sync.py) — ligne 14 : `def main() -> None`

## `service/mock_broker.py`

Source SHA-256 : `16fd3b6b3b2859d4619ef386ad232928fad955b166720bbb8811eb23f291403b`

- [_StreamCtx](../../service/mock_broker.py) — ligne 32 : `class _StreamCtx(AbstractContextManager)`
- [_StreamCtx.__enter__](../../service/mock_broker.py) — ligne 36 : `def __enter__(self) -> '_StreamCtx'`
- [_StreamCtx.__exit__](../../service/mock_broker.py) — ligne 40 : `def __exit__(self, exc_type, exc, tb) -> None`
- [MockBroker](../../service/mock_broker.py) — ligne 48 : `class MockBroker`
- [MockBroker.__post_init__](../../service/mock_broker.py) — ligne 69 : `def __post_init__(self) -> None`
- [MockBroker.get_account](../../service/mock_broker.py) — ligne 78 : `def get_account(self) -> AccountSnapshot`
- [MockBroker.submit_order](../../service/mock_broker.py) — ligne 88 : `def submit_order(self, request: OrderRequest) -> BrokerOrderSnapshot`
- [MockBroker.get_positions](../../service/mock_broker.py) — ligne 116 : `def get_positions(self) -> list[BrokerPosition]`
- [MockBroker.cancel_order](../../service/mock_broker.py) — ligne 120 : `def cancel_order(self, order_id: str) -> bool`
- [MockBroker.get_orders](../../service/mock_broker.py) — ligne 130 : `def get_orders(self, status: str='all', since: datetime | None=None) -> list[BrokerOrderSnapshot]`
- [MockBroker.stream_trades](../../service/mock_broker.py) — ligne 139 : `def stream_trades(self, callback: Callable[[BrokerOrderSnapshot], None]) -> _StreamCtx`
- [MockBroker._fake_price](../../service/mock_broker.py) — ligne 146 : `def _fake_price(self, symbol: str, side: OrderSide, request: OrderRequest) -> Decimal`
- [MockBroker._apply_fill](../../service/mock_broker.py) — ligne 154 : `def _apply_fill(self, symbol: str, side: OrderSide, qty: Decimal, price: Decimal) -> None`
- [MockBroker._emit](../../service/mock_broker.py) — ligne 184 : `def _emit(self, snap: BrokerOrderSnapshot) -> None`

## `service/prometheus_metrics.py`

Source SHA-256 : `26cb9811d3a95a22dd70aa8e8a01f1539ffe5915694e389c38615b74f58e5fdc`

- [_MetricsRegistry](../../service/prometheus_metrics.py) — ligne 57 : `class _MetricsRegistry`
- [_MetricsRegistry.bump_api_error](../../service/prometheus_metrics.py) — ligne 78 : `def bump_api_error(self, service: str) -> None`
- [_MetricsRegistry.bump_execution_run](../../service/prometheus_metrics.py) — ligne 82 : `def bump_execution_run(self) -> None`
- [_MetricsRegistry.bump_alert](../../service/prometheus_metrics.py) — ligne 86 : `def bump_alert(self, severity: str) -> None`
- [_MetricsRegistry.set_gauge](../../service/prometheus_metrics.py) — ligne 90 : `def set_gauge(self, attr: str, value: int) -> None`
- [_MetricsRegistry.render](../../service/prometheus_metrics.py) — ligne 94 : `def render(self) -> str`
- [bump_api_error](../../service/prometheus_metrics.py) — ligne 160 : `def bump_api_error(service: str) -> None`
- [bump_execution_run](../../service/prometheus_metrics.py) — ligne 165 : `def bump_execution_run() -> None`
- [bump_alert](../../service/prometheus_metrics.py) — ligne 170 : `def bump_alert(severity: str) -> None`
- [set_circuit_breaker_active](../../service/prometheus_metrics.py) — ligne 175 : `def set_circuit_breaker_active(active: bool) -> None`
- [set_heartbeat_stale](../../service/prometheus_metrics.py) — ligne 180 : `def set_heartbeat_stale(stale: bool) -> None`
- [set_empty_universe](../../service/prometheus_metrics.py) — ligne 185 : `def set_empty_universe(empty: bool) -> None`
- [set_kill_switch_active](../../service/prometheus_metrics.py) — ligne 190 : `def set_kill_switch_active(active: bool) -> None`
- [set_model_drift_active](../../service/prometheus_metrics.py) — ligne 195 : `def set_model_drift_active(active: bool) -> None`
- [set_cash_ledger_aligned](../../service/prometheus_metrics.py) — ligne 200 : `def set_cash_ledger_aligned(aligned: bool) -> None`
- [render_metrics](../../service/prometheus_metrics.py) — ligne 205 : `def render_metrics() -> str`
- [write_metrics_file](../../service/prometheus_metrics.py) — ligne 210 : `def write_metrics_file(filepath: str | Path | None=None) -> Path`
- [start_prometheus_server](../../service/prometheus_metrics.py) — ligne 230 : `def start_prometheus_server(port: int | None=None, *, blocking: bool=False) -> Optional[threading.Thread]`

## `service/sec/__init__.py`

Source SHA-256 : `9580f203de04c1a805533be78dfc318586ef4f6eee29b0ece8a2dd2bf6fc40b3`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `service/sec/clientEdgar.py`

Source SHA-256 : `ccda686de2e13ad128dd7d5cbc78fcffd3879c66e4abc9889295dc3e9b1d83e8`

- [EdgarError](../../service/sec/clientEdgar.py) — ligne 52 : `class EdgarError(RuntimeError)`
- [EdgarSymbolNotFound](../../service/sec/clientEdgar.py) — ligne 56 : `class EdgarSymbolNotFound(EdgarError)`
- [_rate_limit](../../service/sec/clientEdgar.py) — ligne 62 : `def _rate_limit() -> None`
- [_load_cik_mapping](../../service/sec/clientEdgar.py) — ligne 72 : `def _load_cik_mapping(force_refresh: bool=False) -> dict[str, str]`
- [ticker_to_cik](../../service/sec/clientEdgar.py) — ligne 123 : `def ticker_to_cik(ticker: str) -> str`
- [fetch_company_facts](../../service/sec/clientEdgar.py) — ligne 138 : `def fetch_company_facts(cik: str) -> dict[str, Any]`
- [fetch_symbol_fundamentals_record](../../service/sec/clientEdgar.py) — ligne 189 : `def fetch_symbol_fundamentals_record(symbol: str, session: Any=None) -> dict[str, Any]`

## `service/sec/ratio_calculator.py`

Source SHA-256 : `563adc13ce89da398a37ecc084960a03d107db6ee1133e6f321d2457d596fbeb`

- [enrich_with_market_ratios](../../service/sec/ratio_calculator.py) — ligne 43 : `def enrich_with_market_ratios(engine: Any, symbols: list[str], *, start_date: str | None=None, end_date: str | None=None) -> dict[str, int]`
- [_compute_beta](../../service/sec/ratio_calculator.py) — ligne 253 : `def _compute_beta(sym_prices: pd.DataFrame, spy_returns: pd.Series, ref_date: pd.Timestamp, window: int=_BETA_WINDOW) -> float | None`
- [_batch_update_market_ratios](../../service/sec/ratio_calculator.py) — ligne 296 : `def _batch_update_market_ratios(engine: Any, rows: list[dict[str, Any]]) -> None`

## `service/sec/xbrl_mapper.py`

Source SHA-256 : `85401661fa6ad1c591da5a40bcd3d9d4180aef737f84a853428f0893149648fa`

- [_extract_tag_value](../../service/sec/xbrl_mapper.py) — ligne 107 : `def _extract_tag_value(us_gaap_facts: dict[str, Any], tag_list: list[str]) -> list[dict[str, Any]]`
- [_parse_date](../../service/sec/xbrl_mapper.py) — ligne 165 : `def _parse_date(date_str: str | None) -> _date | None`
- [_is_10q](../../service/sec/xbrl_mapper.py) — ligne 175 : `def _is_10q(form: str) -> bool`
- [_is_10k](../../service/sec/xbrl_mapper.py) — ligne 179 : `def _is_10k(form: str) -> bool`
- [_parse_frame](../../service/sec/xbrl_mapper.py) — ligne 183 : `def _parse_frame(frame: str) -> tuple[int | None, str | None]`
- [_build_filing_index](../../service/sec/xbrl_mapper.py) — ligne 199 : `def _build_filing_index(entries: list[dict[str, Any]], metric_name: str) -> dict[tuple[int, str], dict[str, Any]]`
- [extract_fundamentals_from_sec](../../service/sec/xbrl_mapper.py) — ligne 248 : `def extract_fundamentals_from_sec(raw_facts: dict[str, Any], symbol: str) -> list[dict[str, Any]]`
- [_compute_ratios](../../service/sec/xbrl_mapper.py) — ligne 408 : `def _compute_ratios(records: list[dict[str, Any]]) -> None`
- [_to_fundamentals_rows](../../service/sec/xbrl_mapper.py) — ligne 520 : `def _to_fundamentals_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]`

## `service/stooq/__init__.py`

Source SHA-256 : `b45ba8e8f758e577d715427d0bfb5f575876c8ffa83b0c0a618b47279f0a87af`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `service/stooq/clientStooq.py`

Source SHA-256 : `c5f0f916d549f14a76e9859d30e3d120313bc73f69e0d58665d9f79097e4e430`

- [_stooq_symbol](../../service/stooq/clientStooq.py) — ligne 42 : `def _stooq_symbol(symbol: str) -> str`
- [fetch_daily_bars](../../service/stooq/clientStooq.py) — ligne 52 : `def fetch_daily_bars(symbol: str, *, start: date | None=None, end: date | None=None, timeout: float=DEFAULT_TIMEOUT_SECONDS) -> list[dict[str, Any]]`
- [_parse_csv](../../service/stooq/clientStooq.py) — ligne 86 : `def _parse_csv(raw: str) -> list[dict[str, Any]]`

## `service/telegram.py`

Source SHA-256 : `c1ed55b9e646348a7baf0839c85ff154100adc2db1b8930b8534a17d9836aa8d`

- [_windows_trust_available](../../service/telegram.py) — ligne 48 : `def _windows_trust_available() -> bool`
- [_post_with_windows_trust](../../service/telegram.py) — ligne 52 : `def _post_with_windows_trust(url: str, payload: dict, timeout: float) -> int`
- [TelegramConfigError](../../service/telegram.py) — ligne 65 : `class TelegramConfigError(RuntimeError)`
- [get_bot_token](../../service/telegram.py) — ligne 74 : `def get_bot_token() -> str`
- [get_default_chat_id](../../service/telegram.py) — ligne 87 : `def get_default_chat_id() -> Optional[str]`
- [is_telegram_configured](../../service/telegram.py) — ligne 93 : `def is_telegram_configured() -> bool`
- [TelegramClient](../../service/telegram.py) — ligne 104 : `class TelegramClient`
- [TelegramClient._resolve_token](../../service/telegram.py) — ligne 123 : `def _resolve_token(self) -> str`
- [TelegramClient._resolve_chat_id](../../service/telegram.py) — ligne 128 : `def _resolve_chat_id(self, chat_id: Optional[str]) -> str`
- [TelegramClient.send](../../service/telegram.py) — ligne 137 : `def send(self, text: str, *, chat_id: Optional[str]=None, parse_mode: Optional[str]=None, raise_on_error: bool=False) -> bool`
- [send_telegram_message](../../service/telegram.py) — ligne 199 : `def send_telegram_message(text: str, *, chat_id: Optional[str]=None, parse_mode: Optional[str]=None, bot_token: Optional[str]=None, timeout_seconds: float=5.0, raise_on_error: bool=False) -> bool`

## `service/tushare/__init__.py`

Source SHA-256 : `49bf37a362d6dbc79cfffc5c01b47a4ead1456034a4b3ce21d2e87a58a2c304c`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `service/tushare/accounts.py`

Source SHA-256 : `f652710cc0783b78af066317ef07fb43944736a599066f0893b9a9bbc1239cc6`

- [TushareAccount](../../service/tushare/accounts.py) — ligne 11 : `class TushareAccount`
- [TushareAccount.fingerprint](../../service/tushare/accounts.py) — ligne 16 : `def fingerprint(self) -> str`
- [load_account](../../service/tushare/accounts.py) — ligne 20 : `def load_account(token_env: str='TUSHARE_TOKEN') -> TushareAccount`

## `service/tushare/adapters.py`

Source SHA-256 : `42471fcbf97837b4f6b2982e32dd0c8fc875a41ea5712febb1eb70c8c1d0df62`

- [canonical_json](../../service/tushare/adapters.py) — ligne 13 : `def canonical_json(value: Any) -> str`
- [payload_hash](../../service/tushare/adapters.py) — ligne 17 : `def payload_hash(value: Any) -> str`
- [parse_provider_date](../../service/tushare/adapters.py) — ligne 21 : `def parse_provider_date(value: Any) -> date | None`
- [_decimal](../../service/tushare/adapters.py) — ligne 33 : `def _decimal(value: Any) -> Decimal | None`
- [_first](../../service/tushare/adapters.py) — ligne 42 : `def _first(row: dict[str, Any], fields: tuple[str, ...]) -> Any`
- [adapt_staging_row](../../service/tushare/adapters.py) — ligne 49 : `def adapt_staging_row(endpoint: str, row: dict[str, Any], *, run_id: str, raw_id: int | None, observed_at: datetime, available_at: datetime) -> dict[str, Any]`

## `service/tushare/bootstrap_database.py`

Source SHA-256 : `ed87a4c99572d38123354e8dc4d1938792b0b370ad2c6dae393d865991b4fd2f`

- [create_database](../../service/tushare/bootstrap_database.py) — ligne 41 : `def create_database() -> None`
- [upgrade_database](../../service/tushare/bootstrap_database.py) — ligne 59 : `def upgrade_database() -> None`
- [audit_database](../../service/tushare/bootstrap_database.py) — ligne 65 : `def audit_database() -> dict[str, object]`
- [main](../../service/tushare/bootstrap_database.py) — ligne 87 : `def main() -> None`

## `service/tushare/client.py`

Source SHA-256 : `f7a951784aaada127ecf36b2cc7fd5b79c0b93b921d28d888beb68c02d572902`

- [TushareClient](../../service/tushare/client.py) — ligne 18 : `class TushareClient`
- [TushareClient.__init__](../../service/tushare/client.py) — ligne 21 : `def __init__(self, token: str, *, session: requests.Session | None=None, quota: QuotaBudget | None=None, retry_policy: RetryPolicy | None=None, timeout_seconds: float=30.0, sleeper: Callable[[float], None] | None=None) -> None`
- [TushareClient.query](../../service/tushare/client.py) — ligne 40 : `def query(self, api_name: str, *, params: Mapping[str, Any] | None=None, fields: tuple[str, ...] | list[str] | str | None=None) -> TusharePage`

## `service/tushare/errors.py`

Source SHA-256 : `7e6ec77add37ce877165f71c00cf574cb1ac98efa8cf3fc0489350b659d8ffd0`

- [TushareError](../../service/tushare/errors.py) — ligne 1 : `class TushareError(RuntimeError)`
- [TushareAuthenticationError](../../service/tushare/errors.py) — ligne 5 : `class TushareAuthenticationError(TushareError)`
- [TushareQuotaError](../../service/tushare/errors.py) — ligne 9 : `class TushareQuotaError(TushareError)`
- [TushareResponseError](../../service/tushare/errors.py) — ligne 13 : `class TushareResponseError(TushareError)`

## `service/tushare/ingestion.py`

Source SHA-256 : `e8f6142c55965cf504eeb839212a5d9aaa99e9379aec41c5170cfcf2c228b0d6`

- [IngestionCounters](../../service/tushare/ingestion.py) — ligne 20 : `class IngestionCounters`
- [IngestionCounters.merge](../../service/tushare/ingestion.py) — ligne 29 : `def merge(self, other: IngestionCounters) -> None`
- [IngestionCounters.to_dict](../../service/tushare/ingestion.py) — ligne 35 : `def to_dict(self) -> dict[str, Any]`
- [_date_text](../../service/tushare/ingestion.py) — ligne 39 : `def _date_text(value: date | None) -> str | None`
- [_parameter_variants](../../service/tushare/ingestion.py) — ligne 43 : `def _parameter_variants(endpoint: str) -> list[dict[str, Any]]`
- [ResumeState](../../service/tushare/ingestion.py) — ligne 53 : `class ResumeState`
- [ResumeState.__init__](../../service/tushare/ingestion.py) — ligne 54 : `def __init__(self, path: Path) -> None`
- [ResumeState.completed](../../service/tushare/ingestion.py) — ligne 60 : `def completed(self, endpoint: str, variant: str) -> bool`
- [ResumeState.offset](../../service/tushare/ingestion.py) — ligne 63 : `def offset(self, endpoint: str, variant: str) -> int`
- [ResumeState.update](../../service/tushare/ingestion.py) — ligne 66 : `def update(self, endpoint: str, variant: str, *, offset: int, status: str) -> None`
- [TushareIngestionService](../../service/tushare/ingestion.py) — ligne 74 : `class TushareIngestionService`
- [TushareIngestionService.__init__](../../service/tushare/ingestion.py) — ligne 75 : `def __init__(self, *, client: TushareClient, engine: Engine, run_id: str, page_limit: int=5000, max_pages: int=100000, state_root: Path=DEFAULT_STATE_ROOT, state_key: str | None=None) -> None`
- [TushareIngestionService.collect_endpoint](../../service/tushare/ingestion.py) — ligne 93 : `def collect_endpoint(self, endpoint: str, *, start_date: date | None=None, end_date: date | None=None, dry_run: bool=False, resume: bool=True) -> IngestionCounters`

## `service/tushare/models.py`

Source SHA-256 : `2603fb844aede9a7f7ff5f4c6d9b880dcff6e32a6d59f10f9ae0186e67f9e12b`

- [TusharePage](../../service/tushare/models.py) — ligne 8 : `class TusharePage`
- [EndpointSpec](../../service/tushare/models.py) — ligne 19 : `class EndpointSpec`

## `service/tushare/quality.py`

Source SHA-256 : `2ee316140f3ef08f76d62077b27e8844cae6d9340cfab7d132e986fcfd525b22`

- [QualityResult](../../service/tushare/quality.py) — ligne 13 : `class QualityResult`
- [audit_staging](../../service/tushare/quality.py) — ligne 22 : `def audit_staging(engine: Engine, *, run_id: str, endpoints: list[str], max_age_days: int=5) -> list[QualityResult]`

## `service/tushare/quota.py`

Source SHA-256 : `68fe423b150248f126616853ed73035dae930527c48f27100ce4d8c911f07cf4`

- [QuotaBudget](../../service/tushare/quota.py) — ligne 11 : `class QuotaBudget`
- [QuotaBudget.__init__](../../service/tushare/quota.py) — ligne 14 : `def __init__(self, *, max_calls_per_minute: int=180, max_calls_per_run: int=10000, clock: Callable[[], float]=time.monotonic, sleeper: Callable[[float], None]=time.sleep) -> None`
- [QuotaBudget.calls](../../service/tushare/quota.py) — ligne 31 : `def calls(self) -> int`
- [QuotaBudget.acquire](../../service/tushare/quota.py) — ligne 34 : `def acquire(self) -> None`

## `service/tushare/retry.py`

Source SHA-256 : `c61949dad50a8527575dbbc3bd6726f298e243c14cddd927fdd60103f880646b`

- [RetryPolicy](../../service/tushare/retry.py) — ligne 13 : `class RetryPolicy`
- [with_retry](../../service/tushare/retry.py) — ligne 19 : `def with_retry(operation: Callable[[], T], *, policy: RetryPolicy, sleeper: Callable[[float], None]=time.sleep) -> T`

## `service/tushare/storage.py`

Source SHA-256 : `0dcf6dde7afdaa2b8b923d62b86dc5b854c503e1c1673cb495ccd9c4090d8a65`

- [utcnow_naive](../../service/tushare/storage.py) — ligne 29 : `def utcnow_naive() -> datetime`
- [start_run](../../service/tushare/storage.py) — ligne 33 : `def start_run(engine: Engine, *, run_id: str, batch_name: str, market_code: str, database_alias: str, provider: str='tushare') -> None`
- [finish_run](../../service/tushare/storage.py) — ligne 60 : `def finish_run(engine: Engine, *, run_id: str, status: str, counters: dict[str, Any], quota_calls: int, error_message: str | None=None) -> None`
- [persist_page](../../service/tushare/storage.py) — ligne 96 : `def persist_page(engine: Engine, *, page: TusharePage, page_key: str, run_id: str, observed_at: datetime, available_at: datetime, adapted_rows: list[dict[str, Any]], provider: str='tushare') -> tuple[int, int]`

## `service/tushare/symbols.py`

Source SHA-256 : `2e00f8195191413e67866f3981677e45c7def7f69e64753c5997d8a454d635e3`

- [TushareSymbol](../../service/tushare/symbols.py) — ligne 10 : `class TushareSymbol`
- [_board](../../service/tushare/symbols.py) — ligne 18 : `def _board(code: str, exchange: str) -> str`
- [parse_tushare_symbol](../../service/tushare/symbols.py) — ligne 30 : `def parse_tushare_symbol(value: str) -> TushareSymbol`

## `service/yahoo/__init__.py`

Source SHA-256 : `edb48c19d0a90a717cc48303609bede20858075623802859bd5942516bf00b13`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `service/yahoo/clientYahooFinance.py`

Source SHA-256 : `cb4ef0a5c58e06a0af76ff92d84e94ad8bc301e01ccfb78eb222d779d557bc98`

- [_normalize_symbol](../../service/yahoo/clientYahooFinance.py) — ligne 12 : `def _normalize_symbol(symbol: str) -> str`
- [_import_yfinance](../../service/yahoo/clientYahooFinance.py) — ligne 19 : `def _import_yfinance() -> Any`
- [_coerce_mapping](../../service/yahoo/clientYahooFinance.py) — ligne 34 : `def _coerce_mapping(value: Any) -> dict[str, Any]`
- [_normalize_text](../../service/yahoo/clientYahooFinance.py) — ligne 52 : `def _normalize_text(value: Any) -> str | None`
- [_normalize_market_cap](../../service/yahoo/clientYahooFinance.py) — ligne 59 : `def _normalize_market_cap(value: Any) -> float | None`
- [fetch_symbol_fundamentals_record](../../service/yahoo/clientYahooFinance.py) — ligne 71 : `def fetch_symbol_fundamentals_record(symbol: str, session: Optional[object]=None) -> dict[str, Any]`
- [fetch_latest_quotes_yahoo](../../service/yahoo/clientYahooFinance.py) — ligne 105 : `def fetch_latest_quotes_yahoo(symbols: list[str], *, session: Any=None, account_id: str | None=None, max_workers: int=8, per_symbol_timeout: float=5.0) -> dict[str, dict[str, Any]]`
