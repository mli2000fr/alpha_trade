# Inventaire API — corporate_actions

Extraction AST du 2026-10-10 ; aucune importation ni exécution métier.

Classes, fonctions de module et méthodes déclarées ; fonctions imbriquées exclues.
Les symboles `_...` sont internes. Signature présente ≠ API publique stable.

## `corporate_actions/__init__.py`

Source SHA-256 : `2c006fa44deedd3a27b581cd1ca88ea518b81613a7b66c9c15bd0f376b86f8d6`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `corporate_actions/__main__.py`

Source SHA-256 : `a32956ee57e84f62dd42b778374f38f72ecaeede7eab627cba1a73bc2ee73318`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `corporate_actions/cli.py`

Source SHA-256 : `c25fb16f4615e6811fd79b26a3917ddf114ba324818b9b0e06fda7da7263aa5d`

- [_run_cross_check_yahoo](../../corporate_actions/cli.py) — ligne 23 : `def _run_cross_check_yahoo(repo: CorporateActionRepository, *, start_date: date, end_date: date, symbols: list[str] | None) -> tuple[list[dict[str, object]], dict[str, int]]`
- [_emit_and_persist_summary](../../corporate_actions/cli.py) — ligne 72 : `def _emit_and_persist_summary(*, summary: dict[str, object], step_key: str, status: str, account_id: str | None, trade_date: object=None, parent_summary_run_id: str | None=None, audit_run_kind: str | None=None, audit_repo: CorporateActionRepository | None=None, audit_started_at: datetime | None=None, audit_finished_at: datetime | None=None, audit_stats: dict[str, object] | None=None, audit_anomalies: list[dict[str, object]] | None=None) -> None`
- [_build_parser](../../corporate_actions/cli.py) — ligne 126 : `def _build_parser() -> argparse.ArgumentParser`
- [_resolve_provider_name](../../corporate_actions/cli.py) — ligne 199 : `def _resolve_provider_name(provider: object) -> str`
- [_validate_sync_scope_or_raise](../../corporate_actions/cli.py) — ligne 207 : `def _validate_sync_scope_or_raise(provider: object, symbols: list[str] | None) -> None`
- [_build_apply_preflight](../../corporate_actions/cli.py) — ligne 215 : `def _build_apply_preflight(repo: CorporateActionRepository, *, account_id: str | None, as_of: date, pending_events: list[object]) -> dict[str, object]`
- [_load_pending_events_list](../../corporate_actions/cli.py) — ligne 256 : `def _load_pending_events_list(engine: object, *, as_of: date) -> list[object]`
- [_resolve_sync_symbols_portfolio](../../corporate_actions/cli.py) — ligne 271 : `def _resolve_sync_symbols_portfolio(repo: CorporateActionRepository, account_id: str | None=None) -> list[str]`
- [_resolve_sync_symbols](../../corporate_actions/cli.py) — ligne 309 : `def _resolve_sync_symbols(args: argparse.Namespace, repo: CorporateActionRepository, account_id: str | None=None) -> list[str] | None`
- [_resolve_sync_symbols_bar](../../corporate_actions/cli.py) — ligne 349 : `def _resolve_sync_symbols_bar(args: argparse.Namespace, repo: CorporateActionRepository, account_id: str | None=None) -> list[str] | None`
- [_run_sync](../../corporate_actions/cli.py) — ligne 390 : `def _run_sync(args: argparse.Namespace) -> None`
- [_run_apply](../../corporate_actions/cli.py) — ligne 455 : `def _run_apply(args: argparse.Namespace) -> None`
- [_run_status](../../corporate_actions/cli.py) — ligne 535 : `def _run_status(_args: argparse.Namespace) -> None`
- [_run_all](../../corporate_actions/cli.py) — ligne 560 : `def _run_all(args: argparse.Namespace) -> None`
- [main](../../corporate_actions/cli.py) — ligne 771 : `def main() -> None`

## `corporate_actions/corporate_action_run.py`

Source SHA-256 : `5375696114cd9293de1c29d4ab8d6d5a620fc39bcae36e4c3c650988537330b9`

- [main](../../corporate_actions/corporate_action_run.py) — ligne 9 : `def main()`

## `corporate_actions/cross_check_yahoo.py`

Source SHA-256 : `b3a7a94ca78fe4df49ab4dbacc221eb43ddbf19c679ba0c35d9fbe8e43fe0b11`

- [YahooDividendCrossCheckProvider](../../corporate_actions/cross_check_yahoo.py) — ligne 30 : `class YahooDividendCrossCheckProvider(CorporateActionProvider)`
- [YahooDividendCrossCheckProvider.__init__](../../corporate_actions/cross_check_yahoo.py) — ligne 40 : `def __init__(self) -> None`
- [YahooDividendCrossCheckProvider._import_yfinance](../../corporate_actions/cross_check_yahoo.py) — ligne 43 : `def _import_yfinance(self) -> Any`
- [YahooDividendCrossCheckProvider.fetch_events](../../corporate_actions/cross_check_yahoo.py) — ligne 58 : `def fetch_events(self, symbols: list[str] | None, start_date: date | None=None, end_date: date | None=None) -> list[CorporateActionEvent]`
- [YahooDividendCrossCheckProvider._normalize_date](../../corporate_actions/cross_check_yahoo.py) — ligne 114 : `def _normalize_date(value: Any) -> date | None`
- [diff_dividends](../../corporate_actions/cross_check_yahoo.py) — ligne 144 : `def diff_dividends(*, ingested: list[CorporateActionEvent], yahoo: list[CorporateActionEvent], amount_tolerance: float=0.0001) -> list[dict[str, Any]]`

## `corporate_actions/db_io.py`

Source SHA-256 : `a8a9de947a24ab76f550a4f44e2b5bf1f18af4f7226de4344d4fb2f1ef9f9cce`

- [CorporateActionRepository](../../corporate_actions/db_io.py) — ligne 24 : `class CorporateActionRepository`
- [CorporateActionRepository.__init__](../../corporate_actions/db_io.py) — ligne 27 : `def __init__(self, engine: Engine | None=None) -> None`
- [CorporateActionRepository._is_sqlite](../../corporate_actions/db_io.py) — ligne 31 : `def _is_sqlite(self) -> bool`
- [CorporateActionRepository.insert_event](../../corporate_actions/db_io.py) — ligne 38 : `def insert_event(self, event: CorporateActionEvent, account_id: str | None=None) -> int`
- [CorporateActionRepository.insert_event_sqlite](../../corporate_actions/db_io.py) — ligne 94 : `def insert_event_sqlite(self, event: CorporateActionEvent, account_id: str | None=None) -> int`
- [CorporateActionRepository._sqlite_has_column](../../corporate_actions/db_io.py) — ligne 155 : `def _sqlite_has_column(self, table: str, column: str) -> bool`
- [CorporateActionRepository.load_pending_events](../../corporate_actions/db_io.py) — ligne 164 : `def load_pending_events(self, as_of: Any=None) -> list[CorporateActionEvent]`
- [CorporateActionRepository.is_event_applied](../../corporate_actions/db_io.py) — ligne 192 : `def is_event_applied(self, idempotency_key: str, legacy_key: str | None=None) -> bool`
- [CorporateActionRepository.mark_applied](../../corporate_actions/db_io.py) — ligne 230 : `def mark_applied(self, event_id: int) -> None`
- [CorporateActionRepository.mark_failed](../../corporate_actions/db_io.py) — ligne 239 : `def mark_failed(self, event_id: int, error_message: str) -> None`
- [CorporateActionRepository.mark_skipped](../../corporate_actions/db_io.py) — ligne 248 : `def mark_skipped(self, event_id: int, reason: str) -> None`
- [CorporateActionRepository.insert_application](../../corporate_actions/db_io.py) — ligne 261 : `def insert_application(self, app: CorporateActionApplication, account_id: str | None=None) -> None`
- [CorporateActionRepository.insert_cash_ledger](../../corporate_actions/db_io.py) — ligne 289 : `def insert_cash_ledger(self, entry: CashLedgerEntry, account_id: str | None=None) -> None`
- [CorporateActionRepository.get_total_dividends](../../corporate_actions/db_io.py) — ligne 308 : `def get_total_dividends(self, symbol: str | None=None) -> float`
- [CorporateActionRepository.load_latest_positions](../../corporate_actions/db_io.py) — ligne 323 : `def load_latest_positions(self, account_id: str | None=None) -> list[dict[str, Any]]`
- [CorporateActionRepository.load_latest_position_symbols](../../corporate_actions/db_io.py) — ligne 351 : `def load_latest_position_symbols(self) -> list[str]`
- [CorporateActionRepository.load_broker_live_position_symbols](../../corporate_actions/db_io.py) — ligne 361 : `def load_broker_live_position_symbols(self, account_id: str | None=None) -> list[str]`
- [CorporateActionRepository.load_pending_buy_order_symbols](../../corporate_actions/db_io.py) — ligne 378 : `def load_pending_buy_order_symbols(self, account_id: str | None=None) -> list[str]`
- [CorporateActionRepository.load_bars_available_symbols](../../corporate_actions/db_io.py) — ligne 397 : `def load_bars_available_symbols(self) -> list[str]`
- [CorporateActionRepository.load_existing_event_symbols](../../corporate_actions/db_io.py) — ligne 409 : `def load_existing_event_symbols(self, symbols: list[str] | None=None) -> list[str]`
- [CorporateActionRepository._row_to_event](../../corporate_actions/db_io.py) — ligne 446 : `def _row_to_event(r: Any) -> CorporateActionEvent`
- [CorporateActionRepository.persist_audit_run](../../corporate_actions/db_io.py) — ligne 476 : `def persist_audit_run(self, *, run_id: str, run_kind: str, account_id: str | None, started_at: datetime, finished_at: datetime, stats: dict[str, Any] | None=None, anomalies: list[dict[str, Any]] | None=None, status: str='completed', summary: dict[str, Any] | None=None) -> None`
- [CorporateActionRepository.load_dividend_events_in_range](../../corporate_actions/db_io.py) — ligne 554 : `def load_dividend_events_in_range(self, *, start_date: Any, end_date: Any, symbols: list[str] | None=None) -> list[CorporateActionEvent]`

## `corporate_actions/engine.py`

Source SHA-256 : `c4b9c3b91c1c049c8ef3a7bfcdd9c16a0b62e61f0132b3bc4f5b2b50ac6acd30`

- [CorporateActionEngine](../../corporate_actions/engine.py) — ligne 25 : `class CorporateActionEngine`
- [CorporateActionEngine.__init__](../../corporate_actions/engine.py) — ligne 58 : `def __init__(self, provider: CorporateActionProvider, repo: CorporateActionRepository | None=None, account_id: str | None=None) -> None`
- [CorporateActionEngine.sync](../../corporate_actions/engine.py) — ligne 72 : `def sync(self, symbols: list[str] | None=None, start_date: date | None=None, end_date: date | None=None, batch_size: int=25, skip_existing: bool=False) -> dict[str, int]`
- [CorporateActionEngine._ingest_events](../../corporate_actions/engine.py) — ligne 155 : `def _ingest_events(self, events: list[CorporateActionEvent], stats: dict[str, int]) -> None`
- [CorporateActionEngine._chunk_symbols](../../corporate_actions/engine.py) — ligne 172 : `def _chunk_symbols(symbols: list[str], batch_size: int) -> list[list[str]]`
- [CorporateActionEngine.apply](../../corporate_actions/engine.py) — ligne 181 : `def apply(self, as_of: date | None=None, positions: list[dict[str, Any]] | None=None) -> dict[str, int]`
- [CorporateActionEngine._apply_single](../../corporate_actions/engine.py) — ligne 242 : `def _apply_single(self, event: CorporateActionEvent, position_map: dict[str, PositionSnapshot], stats: dict[str, int]) -> None`

## `corporate_actions/models.py`

Source SHA-256 : `9be027194bf4d9c89b8cc718f2688a5b6d3d899d1c1d0efcda67fcf450452d31`

- [CaType](../../corporate_actions/models.py) — ligne 14 : `class CaType`
- [CaStatus](../../corporate_actions/models.py) — ligne 22 : `class CaStatus`
- [CorporateActionEvent](../../corporate_actions/models.py) — ligne 34 : `class CorporateActionEvent`
- [CorporateActionEvent.idempotency_key](../../corporate_actions/models.py) — ligne 61 : `def idempotency_key(self) -> str`
- [CorporateActionEvent.compute_idempotency_key](../../corporate_actions/models.py) — ligne 77 : `def compute_idempotency_key(self, account_id: str | None) -> str`
- [CorporateActionEvent.split_ratio](../../corporate_actions/models.py) — ligne 101 : `def split_ratio(self) -> float`
- [CorporateActionEvent.validate](../../corporate_actions/models.py) — ligne 107 : `def validate(self) -> list[str]`
- [CorporateActionApplication](../../corporate_actions/models.py) — ligne 130 : `class CorporateActionApplication`
- [CashLedgerEntry](../../corporate_actions/models.py) — ligne 148 : `class CashLedgerEntry`
- [PositionSnapshot](../../corporate_actions/models.py) — ligne 163 : `class PositionSnapshot`

## `corporate_actions/processors.py`

Source SHA-256 : `76dade9135d2dd8b5e48b2203cb9940886cc09c1a34fa30abe8586a1f8988834`

- [process_dividend](../../corporate_actions/processors.py) — ligne 22 : `def process_dividend(event: CorporateActionEvent, position: PositionSnapshot) -> tuple[CorporateActionApplication, CashLedgerEntry]`
- [process_split](../../corporate_actions/processors.py) — ligne 68 : `def process_split(event: CorporateActionEvent, position: PositionSnapshot) -> tuple[CorporateActionApplication, CashLedgerEntry | None]`

## `corporate_actions/provider.py`

Source SHA-256 : `a270817bc50fb57cb09177983bbfdfb3a37d80552d2182ab3d2da8ba9ae1ebbf`

- [CorporateActionProvider](../../corporate_actions/provider.py) — ligne 33 : `class CorporateActionProvider(ABC)`
- [CorporateActionProvider.fetch_events](../../corporate_actions/provider.py) — ligne 37 : `def fetch_events(self, symbols: list[str] | None, start_date: date | None=None, end_date: date | None=None) -> list[CorporateActionEvent]`
- [AlpacaCorporateActionProvider](../../corporate_actions/provider.py) — ligne 51 : `class AlpacaCorporateActionProvider(CorporateActionProvider)`
- [AlpacaCorporateActionProvider.__init__](../../corporate_actions/provider.py) — ligne 59 : `def __init__(self, session: requests.Session | None=None, account_id: str | None=None) -> None`
- [AlpacaCorporateActionProvider._request](../../corporate_actions/provider.py) — ligne 68 : `def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]`
- [AlpacaCorporateActionProvider.fetch_events](../../corporate_actions/provider.py) — ligne 107 : `def fetch_events(self, symbols: list[str] | None, start_date: date | None=None, end_date: date | None=None) -> list[CorporateActionEvent]`
- [AlpacaCorporateActionProvider._parse_dividend](../../corporate_actions/provider.py) — ligne 184 : `def _parse_dividend(raw: dict[str, Any]) -> CorporateActionEvent`
- [AlpacaCorporateActionProvider._parse_split](../../corporate_actions/provider.py) — ligne 200 : `def _parse_split(raw: dict[str, Any], ca_type: str) -> CorporateActionEvent`
- [AlpacaCorporateActionProvider._normalize_split_ratio](../../corporate_actions/provider.py) — ligne 220 : `def _normalize_split_ratio(old_rate: Any, new_rate: Any) -> tuple[int, int]`
- [EodhdCorporateActionProvider](../../corporate_actions/provider.py) — ligne 234 : `class EodhdCorporateActionProvider(CorporateActionProvider)`
- [EodhdCorporateActionProvider.__init__](../../corporate_actions/provider.py) — ligne 247 : `def __init__(self, *, tracker: Any=None) -> None`
- [EodhdCorporateActionProvider.fetch_events](../../corporate_actions/provider.py) — ligne 251 : `def fetch_events(self, symbols: list[str] | None, start_date: date | None=None, end_date: date | None=None) -> list[CorporateActionEvent]`
- [EodhdCorporateActionProvider._parse_dividend](../../corporate_actions/provider.py) — ligne 318 : `def _parse_dividend(symbol: str, raw: dict[str, Any]) -> CorporateActionEvent`
- [EodhdCorporateActionProvider._parse_split](../../corporate_actions/provider.py) — ligne 344 : `def _parse_split(symbol: str, raw: dict[str, Any]) -> CorporateActionEvent`
- [EodhdCorporateActionProvider._parse_split_ratio](../../corporate_actions/provider.py) — ligne 371 : `def _parse_split_ratio(ratio_str: str) -> tuple[int, int]`
- [_safe_iso_date](../../corporate_actions/provider.py) — ligne 389 : `def _safe_iso_date(value: Any) -> date | None`
- [build_corporate_action_provider](../../corporate_actions/provider.py) — ligne 402 : `def build_corporate_action_provider(*, account_id: str | None=None, config: dict | None=None) -> CorporateActionProvider`

## `corporate_actions/reconciliation.py`

Source SHA-256 : `e8bd68339a684ae9227aadefc51badda4326b5477209f02980c64d37ba684d35`

- [CaReconcileDiff](../../corporate_actions/reconciliation.py) — ligne 18 : `class CaReconcileDiff`
- [reconcile_after_corporate_actions](../../corporate_actions/reconciliation.py) — ligne 27 : `def reconcile_after_corporate_actions(internal_positions: dict[str, float], broker_positions: list[dict], tolerance: float=0.01) -> list[CaReconcileDiff]`
