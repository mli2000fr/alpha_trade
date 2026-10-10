# Inventaire API — execution_engine

Extraction AST du 2026-10-10 ; aucune importation ni exécution métier.

Classes, fonctions de module et méthodes déclarées ; fonctions imbriquées exclues.
Les symboles `_...` sont internes. Signature présente ≠ API publique stable.

## `execution_engine/__init__.py`

Source SHA-256 : `58891cefb9f314875d2786a99ef7e63543570bdb506c5119616b57b994bf2dc2`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `execution_engine/__main__.py`

Source SHA-256 : `68b787285e6539e53c4b9aeb1da3f202033c95a95c7db54b03b2771c8c6b6bb6`

- [_should_warn_deprecated_run_path](../../execution_engine/__main__.py) — ligne 10 : `def _should_warn_deprecated_run_path(argv: list[str]) -> bool`

## `execution_engine/account_state.py`

Source SHA-256 : `9764c00e98e52552b95d83f3c1e48284f68b1bf4474b33b9b79895e163ab0598`

- [InvalidBrokerSnapshotError](../../execution_engine/account_state.py) — ligne 25 : `class InvalidBrokerSnapshotError(RuntimeError)`
- [_AccountConstraintState](../../execution_engine/account_state.py) — ligne 37 : `class _AccountConstraintState`
- [_ResolvedLeverageBudget](../../execution_engine/account_state.py) — ligne 55 : `class _ResolvedLeverageBudget`
- [safe_float](../../execution_engine/account_state.py) — ligne 67 : `def safe_float(value: object, *, default: float=0.0) -> float`
- [estimate_intent_notional](../../execution_engine/account_state.py) — ligne 74 : `def estimate_intent_notional(intent: OrderIntent) -> float`
- [_resolve_leverage_activation](../../execution_engine/account_state.py) — ligne 79 : `def _resolve_leverage_activation(cfg: 'ExecutionConfig', *, equity: float) -> tuple[bool, str | None]`
- [_resolve_snapshot_buying_power](../../execution_engine/account_state.py) — ligne 100 : `def _resolve_snapshot_buying_power(snapshot: dict[str, object], cfg: 'ExecutionConfig') -> tuple[float | None, str | None]`
- [_log_leverage_decision](../../execution_engine/account_state.py) — ligne 114 : `def _log_leverage_decision(cfg: 'ExecutionConfig', state: _ResolvedLeverageBudget, *, equity: float) -> None`
- [_resolve_margin_buying_power](../../execution_engine/account_state.py) — ligne 139 : `def _resolve_margin_buying_power(cfg: 'ExecutionConfig', *, equity: float, snapshot: dict[str, object] | None=None) -> _ResolvedLeverageBudget`
- [build_account_constraint_state](../../execution_engine/account_state.py) — ligne 239 : `def build_account_constraint_state(cfg: 'ExecutionConfig', broker: 'ExecutionBrokerPort') -> _AccountConstraintState`
- [reserve_account_capacity_for_intent](../../execution_engine/account_state.py) — ligne 338 : `def reserve_account_capacity_for_intent(intent: OrderIntent, account_state: _AccountConstraintState, exec_run_id: str, events: list[ExecutionEvent], metrics: dict[str, int]) -> bool`
- [should_defer_children](../../execution_engine/account_state.py) — ligne 388 : `def should_defer_children(account_state: _AccountConstraintState) -> tuple[bool, str | None]`

## `execution_engine/audit.py`

Source SHA-256 : `bb7467da40130cbd667a5a1089c87985a858aae2b4d2643b49f03e8c549b3405`

- [build_run_id](../../execution_engine/audit.py) — ligne 18 : `def build_run_id() -> str`
- [make_event](../../execution_engine/audit.py) — ligne 22 : `def make_event(exec_run_id: str, event_type: str, message: str, *, symbol: str | None=None, broker_order_id: str | None=None, intent_id: str | None=None, payload: dict[str, Any] | None=None) -> ExecutionEvent`
- [order_intent_to_db_dict](../../execution_engine/audit.py) — ligne 45 : `def order_intent_to_db_dict(intent: OrderIntent, exec_run_id: str, status: str=OrderStatus.NEW) -> dict[str, Any]`
- [broker_order_to_db_dict](../../execution_engine/audit.py) — ligne 72 : `def broker_order_to_db_dict(order: BrokerOrder, exec_run_id: str) -> dict[str, Any]`
- [fill_to_db_dict](../../execution_engine/audit.py) — ligne 92 : `def fill_to_db_dict(fill: ExecutionFill, exec_run_id: str) -> dict[str, Any]`
- [event_to_db_dict](../../execution_engine/audit.py) — ligne 108 : `def event_to_db_dict(event: ExecutionEvent) -> dict[str, Any]`
- [build_execution_run_summary](../../execution_engine/audit.py) — ligne 122 : `def build_execution_run_summary(metrics: dict[str, Any], *, started_at: datetime, finished_at: datetime, execution_mode: str, broker_mode: str, account_id: str | None, account_type: str, swing_only: bool, dry_run: bool, allow_outside_rth: bool) -> dict[str, Any]`

## `execution_engine/broker_adapter.py`

Source SHA-256 : `6efd38fd7a1e4ba53e15b0c1a15227707ddd4f6462c9a3b94ddc6b39c16c85a7`

- [BrokerAdapter](../../execution_engine/broker_adapter.py) — ligne 18 : `class BrokerAdapter`
- [BrokerAdapter.__init__](../../execution_engine/broker_adapter.py) — ligne 23 : `def __init__(self, client: AlpacaTradingClient, config: ExecutionConfig) -> None`
- [BrokerAdapter.submit_intent](../../execution_engine/broker_adapter.py) — ligne 31 : `def submit_intent(self, intent: OrderIntent) -> BrokerOrder`
- [BrokerAdapter.submit_market_order](../../execution_engine/broker_adapter.py) — ligne 36 : `def submit_market_order(self, *, symbol: str, qty: float, side: str, intent_id: str) -> BrokerOrder`
- [BrokerAdapter.submit_oco_protection](../../execution_engine/broker_adapter.py) — ligne 60 : `def submit_oco_protection(self, parent_intent: OrderIntent, tp_intent: OrderIntent, stop_intent: OrderIntent) -> tuple[BrokerOrder, BrokerOrder]`
- [BrokerAdapter.get_position](../../execution_engine/broker_adapter.py) — ligne 97 : `def get_position(self, symbol: str) -> dict[str, Any] | None`
- [BrokerAdapter.poll_order_status](../../execution_engine/broker_adapter.py) — ligne 105 : `def poll_order_status(self, broker_order_id: str, intent_id: str='') -> BrokerOrder`
- [BrokerAdapter.cancel_broker_order](../../execution_engine/broker_adapter.py) — ligne 109 : `def cancel_broker_order(self, broker_order_id: str) -> bool`
- [BrokerAdapter.replace_stop_order](../../execution_engine/broker_adapter.py) — ligne 112 : `def replace_stop_order(self, existing_broker_order_id: str, new_stop_intent: OrderIntent) -> BrokerOrder`
- [BrokerAdapter.cancel_all_open_orders](../../execution_engine/broker_adapter.py) — ligne 137 : `def cancel_all_open_orders(self, *, dry_run: bool=False) -> list[CancelResult]`
- [BrokerAdapter.list_recent_orders](../../execution_engine/broker_adapter.py) — ligne 177 : `def list_recent_orders(self, *, status: str='all', limit: int=500, symbols: list[str] | None=None) -> list[dict[str, Any]]`
- [BrokerAdapter.get_all_positions](../../execution_engine/broker_adapter.py) — ligne 186 : `def get_all_positions(self) -> list[dict[str, Any]]`
- [BrokerAdapter.is_market_open](../../execution_engine/broker_adapter.py) — ligne 189 : `def is_market_open(self) -> bool`
- [BrokerAdapter.get_account_snapshot](../../execution_engine/broker_adapter.py) — ligne 192 : `def get_account_snapshot(self) -> dict[str, Any]`
- [BrokerAdapter.get_account_equity](../../execution_engine/broker_adapter.py) — ligne 195 : `def get_account_equity(self) -> float`
- [BrokerAdapter.get_latest_market_price](../../execution_engine/broker_adapter.py) — ligne 199 : `def get_latest_market_price(self, symbol: str) -> float | None`
- [BrokerAdapter.broker_order_from_api](../../execution_engine/broker_adapter.py) — ligne 229 : `def broker_order_from_api(self, payload: dict[str, Any], *, intent_id: str='') -> BrokerOrder`
- [BrokerAdapter._resp_to_broker_order](../../execution_engine/broker_adapter.py) — ligne 233 : `def _resp_to_broker_order(resp: dict[str, Any], intent_id: str) -> BrokerOrder`

## `execution_engine/broker_doubles_18d.py`

Source SHA-256 : `00f7bd429355b12f6b34d23785f9f872e18126a60badabf0d3434520467150f5`

- [ReplayMismatch](../../execution_engine/broker_doubles_18d.py) — ligne 19 : `class ReplayMismatch(RuntimeError)`
- [MockBrokerAdapter](../../execution_engine/broker_doubles_18d.py) — ligne 37 : `class MockBrokerAdapter`
- [MockBrokerAdapter.__init__](../../execution_engine/broker_doubles_18d.py) — ligne 43 : `def __init__(self, *, account: Mapping[str, Any] | None=None, positions: Mapping[str, Mapping[str, Any]] | None=None, prices: Mapping[str, float] | None=None, market_open: bool=True) -> None`
- [MockBrokerAdapter._new_order](../../execution_engine/broker_doubles_18d.py) — ligne 56 : `def _new_order(self, *, intent_id: str, symbol: str, side: str, qty: float, order_type: str, limit_price: float | None=None, stop_price: float | None=None, trail_percent: float | None=None) -> BrokerOrder`
- [MockBrokerAdapter.submit_intent](../../execution_engine/broker_doubles_18d.py) — ligne 79 : `def submit_intent(self, intent: OrderIntent) -> BrokerOrder`
- [MockBrokerAdapter.submit_market_order](../../execution_engine/broker_doubles_18d.py) — ligne 87 : `def submit_market_order(self, *, symbol: str, qty: float, side: str, intent_id: str) -> BrokerOrder`
- [MockBrokerAdapter.submit_oco_protection](../../execution_engine/broker_doubles_18d.py) — ligne 92 : `def submit_oco_protection(self, parent_intent: OrderIntent, tp_intent: OrderIntent, stop_intent: OrderIntent) -> tuple[BrokerOrder, BrokerOrder]`
- [MockBrokerAdapter.set_order_status](../../execution_engine/broker_doubles_18d.py) — ligne 108 : `def set_order_status(self, broker_order_id: str, status: str, *, filled_qty: float=0, avg_fill_price: float | None=None) -> BrokerOrder`
- [MockBrokerAdapter.poll_order_status](../../execution_engine/broker_doubles_18d.py) — ligne 130 : `def poll_order_status(self, broker_order_id: str, intent_id: str='') -> BrokerOrder`
- [MockBrokerAdapter.cancel_broker_order](../../execution_engine/broker_doubles_18d.py) — ligne 136 : `def cancel_broker_order(self, broker_order_id: str) -> bool`
- [MockBrokerAdapter.replace_stop_order](../../execution_engine/broker_doubles_18d.py) — ligne 144 : `def replace_stop_order(self, existing_broker_order_id: str, new_stop_intent: OrderIntent) -> BrokerOrder`
- [MockBrokerAdapter.cancel_all_open_orders](../../execution_engine/broker_doubles_18d.py) — ligne 150 : `def cancel_all_open_orders(self, *, dry_run: bool=False) -> list[CancelResult]`
- [MockBrokerAdapter.list_recent_orders](../../execution_engine/broker_doubles_18d.py) — ligne 163 : `def list_recent_orders(self, *, status: str='all', limit: int=500, symbols: list[str] | None=None) -> list[dict[str, Any]]`
- [MockBrokerAdapter.broker_order_from_api](../../execution_engine/broker_doubles_18d.py) — ligne 189 : `def broker_order_from_api(self, payload: dict[str, Any], *, intent_id: str='') -> BrokerOrder`
- [MockBrokerAdapter.get_position](../../execution_engine/broker_doubles_18d.py) — ligne 215 : `def get_position(self, symbol: str) -> dict[str, Any] | None`
- [MockBrokerAdapter.get_all_positions](../../execution_engine/broker_doubles_18d.py) — ligne 219 : `def get_all_positions(self) -> list[dict[str, Any]]`
- [MockBrokerAdapter.get_account_snapshot](../../execution_engine/broker_doubles_18d.py) — ligne 222 : `def get_account_snapshot(self) -> dict[str, Any]`
- [MockBrokerAdapter.get_account_equity](../../execution_engine/broker_doubles_18d.py) — ligne 225 : `def get_account_equity(self) -> float`
- [MockBrokerAdapter.get_latest_market_price](../../execution_engine/broker_doubles_18d.py) — ligne 228 : `def get_latest_market_price(self, symbol: str) -> float | None`
- [MockBrokerAdapter.is_market_open](../../execution_engine/broker_doubles_18d.py) — ligne 231 : `def is_market_open(self) -> bool`
- [ReplayBrokerAdapter](../../execution_engine/broker_doubles_18d.py) — ligne 235 : `class ReplayBrokerAdapter(MockBrokerAdapter)`
- [ReplayBrokerAdapter.__init__](../../execution_engine/broker_doubles_18d.py) — ligne 238 : `def __init__(self, *, submissions: Mapping[str, BrokerOrder], polls: Mapping[str, Sequence[BrokerOrder]] | None=None, cancellations: frozenset[str]=frozenset(), account: Mapping[str, Any] | None=None, positions: Mapping[str, Mapping[str, Any]] | None=None, prices: Mapping[str, float] | None=None, market_open: bool=True) -> None`
- [ReplayBrokerAdapter._recorded_submit](../../execution_engine/broker_doubles_18d.py) — ligne 252 : `def _recorded_submit(self, *, intent_id: str, symbol: str, side: str, qty: float) -> BrokerOrder`
- [ReplayBrokerAdapter.submit_intent](../../execution_engine/broker_doubles_18d.py) — ligne 264 : `def submit_intent(self, intent: OrderIntent) -> BrokerOrder`
- [ReplayBrokerAdapter.submit_market_order](../../execution_engine/broker_doubles_18d.py) — ligne 268 : `def submit_market_order(self, *, symbol: str, qty: float, side: str, intent_id: str) -> BrokerOrder`
- [ReplayBrokerAdapter.poll_order_status](../../execution_engine/broker_doubles_18d.py) — ligne 273 : `def poll_order_status(self, broker_order_id: str, intent_id: str='') -> BrokerOrder`
- [ReplayBrokerAdapter.cancel_broker_order](../../execution_engine/broker_doubles_18d.py) — ligne 291 : `def cancel_broker_order(self, broker_order_id: str) -> bool`
- [ReplayBrokerAdapter.set_order_status](../../execution_engine/broker_doubles_18d.py) — ligne 296 : `def set_order_status(self, broker_order_id: str, status: str, *, filled_qty: float=0, avg_fill_price: float | None=None) -> BrokerOrder`

## `execution_engine/broker_router.py`

Source SHA-256 : `13af13faf1b7f2a6a86be4d58cda5a60f4e6abf7a4e4c9c8d2b0734fd475699f`

- [BrokerRouteError](../../execution_engine/broker_router.py) — ligne 16 : `class BrokerRouteError(RuntimeError)`
- [ExecutionBrokerPort](../../execution_engine/broker_router.py) — ligne 21 : `class ExecutionBrokerPort(Protocol)`
- [ExecutionBrokerPort.submit_intent](../../execution_engine/broker_router.py) — ligne 26 : `def submit_intent(self, intent: OrderIntent) -> BrokerOrder`
- [ExecutionBrokerPort.poll_order_status](../../execution_engine/broker_router.py) — ligne 28 : `def poll_order_status(self, broker_order_id: str, intent_id: str='') -> BrokerOrder`
- [ExecutionBrokerPort.cancel_broker_order](../../execution_engine/broker_router.py) — ligne 30 : `def cancel_broker_order(self, broker_order_id: str) -> bool`
- [ExecutionBrokerPort.submit_market_order](../../execution_engine/broker_router.py) — ligne 32 : `def submit_market_order(self, *, symbol: str, qty: float, side: str, intent_id: str) -> BrokerOrder`
- [ExecutionBrokerPort.submit_oco_protection](../../execution_engine/broker_router.py) — ligne 35 : `def submit_oco_protection(self, parent_intent: OrderIntent, tp_intent: OrderIntent, stop_intent: OrderIntent) -> tuple[BrokerOrder, BrokerOrder]`
- [ExecutionBrokerPort.replace_stop_order](../../execution_engine/broker_router.py) — ligne 39 : `def replace_stop_order(self, existing_broker_order_id: str, new_stop_intent: OrderIntent) -> BrokerOrder`
- [ExecutionBrokerPort.get_position](../../execution_engine/broker_router.py) — ligne 42 : `def get_position(self, symbol: str) -> dict[str, Any] | None`
- [ExecutionBrokerPort.get_all_positions](../../execution_engine/broker_router.py) — ligne 44 : `def get_all_positions(self) -> list[dict[str, Any]]`
- [ExecutionBrokerPort.get_account_snapshot](../../execution_engine/broker_router.py) — ligne 46 : `def get_account_snapshot(self) -> dict[str, Any]`
- [ExecutionBrokerPort.get_account_equity](../../execution_engine/broker_router.py) — ligne 48 : `def get_account_equity(self) -> float`
- [ExecutionBrokerPort.get_latest_market_price](../../execution_engine/broker_router.py) — ligne 50 : `def get_latest_market_price(self, symbol: str) -> float | None`
- [ExecutionBrokerPort.is_market_open](../../execution_engine/broker_router.py) — ligne 52 : `def is_market_open(self) -> bool`
- [ExecutionBrokerPort.cancel_all_open_orders](../../execution_engine/broker_router.py) — ligne 54 : `def cancel_all_open_orders(self, *, dry_run: bool=False) -> list[CancelResult]`
- [ExecutionBrokerPort.list_recent_orders](../../execution_engine/broker_router.py) — ligne 56 : `def list_recent_orders(self, *, status: str='all', limit: int=500, symbols: list[str] | None=None) -> list[dict[str, Any]]`
- [ExecutionBrokerPort.broker_order_from_api](../../execution_engine/broker_router.py) — ligne 59 : `def broker_order_from_api(self, payload: dict[str, Any], *, intent_id: str='') -> BrokerOrder`
- [BrokerRouter](../../execution_engine/broker_router.py) — ligne 63 : `class BrokerRouter`
- [BrokerRouter.__init__](../../execution_engine/broker_router.py) — ligne 66 : `def __init__(self, *, us_factory: Callable[[ExecutionConfig], ExecutionBrokerPort]) -> None`
- [BrokerRouter.validate](../../execution_engine/broker_router.py) — ligne 70 : `def validate(config: ExecutionConfig) -> None`
- [BrokerRouter.resolve](../../execution_engine/broker_router.py) — ligne 81 : `def resolve(self, config: ExecutionConfig) -> ExecutionBrokerPort`
- [build_alpaca_broker](../../execution_engine/broker_router.py) — ligne 91 : `def build_alpaca_broker(config: ExecutionConfig) -> ExecutionBrokerPort`

## `execution_engine/broker_state_sync.py`

Source SHA-256 : `779975f2cce76cc53bc0ed2d4f4ec35c7111a817cc6a532adfffd19b73b0e375`

- [BrokerStateSynchronizer](../../execution_engine/broker_state_sync.py) — ligne 19 : `class BrokerStateSynchronizer`
- [BrokerStateSynchronizer.__init__](../../execution_engine/broker_state_sync.py) — ligne 22 : `def __init__(self, repo: ExecutionRepository, broker: ExecutionBrokerPort, *, broker_mode: str) -> None`
- [BrokerStateSynchronizer.sync](../../execution_engine/broker_state_sync.py) — ligne 33 : `def sync(self, *, exec_run_id: str, account_id: str, order_limit: int=200, symbols: list[str] | None=None) -> dict[str, int]`
- [BrokerStateSynchronizer._maybe_adopt_orphan](../../execution_engine/broker_state_sync.py) — ligne 115 : `def _maybe_adopt_orphan(self, *, account_id: str, raw_order: dict[str, Any])`
- [BrokerStateSynchronizer._resolve_request](../../execution_engine/broker_state_sync.py) — ligne 153 : `def _resolve_request(self, *, account_id: str, raw_order: dict[str, Any]) -> ExecutionOrderRequest | None`
- [BrokerStateSynchronizer._request_to_intent](../../execution_engine/broker_state_sync.py) — ligne 177 : `def _request_to_intent(request: ExecutionOrderRequest) -> OrderIntent`
- [BrokerStateSynchronizer._build_missing_fill](../../execution_engine/broker_state_sync.py) — ligne 198 : `def _build_missing_fill(*, request: ExecutionOrderRequest, broker_order, missing_fill_qty: float) -> ExecutionFill`

## `execution_engine/cash_ledger_guard.py`

Source SHA-256 : `49a95ba60325db2d347ece9ca195b198a9d0f168885ab94e8ed957130611873f`

- [check_cash_ledger_consistency](../../execution_engine/cash_ledger_guard.py) — ligne 19 : `def check_cash_ledger_consistency(settled_cash: float, unsettled_cash: float=0.0, market_value: float=0.0, reported_equity: float=0.0, *, tolerance_pct: float=DEFAULT_TOLERANCE_PCT, account_id: str | None=None) -> bool`
- [check_cash_ledger_from_broker_snapshot](../../execution_engine/cash_ledger_guard.py) — ligne 129 : `def check_cash_ledger_from_broker_snapshot(snapshot: dict, *, tolerance_pct: float=DEFAULT_TOLERANCE_PCT) -> bool`

## `execution_engine/children_submission.py`

Source SHA-256 : `525a724da712c199a03fd416e7b0acfa5f3ae14872105ee538ba8343832d4675`

- [submit_children](../../execution_engine/children_submission.py) — ligne 45 : `def submit_children(executor: 'ProductionExecutor', parent: OrderIntent, filled_order: BrokerOrder, exec_run_id: str, *, account_state: _AccountConstraintState, metrics: dict[str, int], target: Any | None=None) -> list[ExecutionEvent]`
- [submit_rebalance_orders](../../execution_engine/children_submission.py) — ligne 246 : `def submit_rebalance_orders(executor: 'ProductionExecutor', action_diffs: list, exec_run_id: str, targets: list, metrics: dict[str, int], account_state: _AccountConstraintState) -> list[ExecutionEvent]`

## `execution_engine/cli.py`

Source SHA-256 : `5814f90fe72ff30fb37b75349585021c285f11a6aab1b077185a93152e912828`

- [_add_run_arguments](../../execution_engine/cli.py) — ligne 34 : `def _add_run_arguments(p: argparse.ArgumentParser) -> None`
- [_add_cancel_all_arguments](../../execution_engine/cli.py) — ligne 77 : `def _add_cancel_all_arguments(p: argparse.ArgumentParser) -> None`
- [build_arg_parser](../../execution_engine/cli.py) — ligne 102 : `def build_arg_parser() -> argparse.ArgumentParser`
- [parse_args](../../execution_engine/cli.py) — ligne 116 : `def parse_args(argv: list[str] | None=None) -> argparse.Namespace`
- [main](../../execution_engine/cli.py) — ligne 165 : `def main(argv: list[str] | None=None) -> None`
- [_apply_feature_flags](../../execution_engine/cli.py) — ligne 186 : `def _apply_feature_flags(args: argparse.Namespace) -> None`
- [_resolve_canonical_mode](../../execution_engine/cli.py) — ligne 200 : `def _resolve_canonical_mode(args: argparse.Namespace) -> str`
- [_run_execution](../../execution_engine/cli.py) — ligne 207 : `def _run_execution(args: argparse.Namespace) -> None`
- [_run_cancel_all](../../execution_engine/cli.py) — ligne 269 : `def _run_cancel_all(args: argparse.Namespace) -> None`

## `execution_engine/config.py`

Source SHA-256 : `c179458a54d3535b60b875181edbbd8ac0872c680898f59fd8df890def1a26ff`

- [TrailingStopConfig](../../execution_engine/config.py) — ligne 15 : `class TrailingStopConfig`
- [TrailingStopConfig.__post_init__](../../execution_engine/config.py) — ligne 32 : `def __post_init__(self) -> None`
- [TimeStopConfig](../../execution_engine/config.py) — ligne 46 : `class TimeStopConfig`
- [TimeStopConfig.__post_init__](../../execution_engine/config.py) — ligne 54 : `def __post_init__(self) -> None`
- [LeverageConfig](../../execution_engine/config.py) — ligne 64 : `class LeverageConfig`
- [LeverageConfig.__post_init__](../../execution_engine/config.py) — ligne 79 : `def __post_init__(self) -> None`
- [LeverageConfig.capped_live_max_leverage](../../execution_engine/config.py) — ligne 103 : `def capped_live_max_leverage(self) -> float`
- [load_trailing_stop_config_from_yaml](../../execution_engine/config.py) — ligne 108 : `def load_trailing_stop_config_from_yaml(raw_config: Mapping[str, Any] | None=None) -> TrailingStopConfig`
- [load_time_stop_config_from_yaml](../../execution_engine/config.py) — ligne 130 : `def load_time_stop_config_from_yaml(raw_config: Mapping[str, Any] | None=None) -> TimeStopConfig`
- [load_leverage_config_from_yaml](../../execution_engine/config.py) — ligne 144 : `def load_leverage_config_from_yaml(raw_config: Mapping[str, Any] | None=None) -> LeverageConfig`
- [ExecutionConfig](../../execution_engine/config.py) — ligne 175 : `class ExecutionConfig`
- [ExecutionConfig.__post_init__](../../execution_engine/config.py) — ligne 282 : `def __post_init__(self) -> None`
- [ExecutionConfig.resolved_account_id](../../execution_engine/config.py) — ligne 358 : `def resolved_account_id(self) -> str`
- [ExecutionConfig.is_overnight_profile](../../execution_engine/config.py) — ligne 362 : `def is_overnight_profile(self) -> bool`
- [ExecutionConfig.is_paper](../../execution_engine/config.py) — ligne 366 : `def is_paper(self) -> bool`
- [ExecutionConfig.is_live](../../execution_engine/config.py) — ligne 369 : `def is_live(self) -> bool`
- [ExecutionConfig.fractional_live_entries_enabled](../../execution_engine/config.py) — ligne 373 : `def fractional_live_entries_enabled(self) -> bool`
- [ExecutionConfig.resolved_fractional_live_mode](../../execution_engine/config.py) — ligne 378 : `def resolved_fractional_live_mode(self) -> Literal['entry_only', 'intraday_only', 'full_if_supported']`
- [ExecutionConfig.fractional_live_protections_enabled](../../execution_engine/config.py) — ligne 387 : `def fractional_live_protections_enabled(self) -> bool`
- [ExecutionConfig.can_submit_fractional_protection_orders](../../execution_engine/config.py) — ligne 391 : `def can_submit_fractional_protection_orders(self, qty: float, *, trade_date: date | None=None, context: Literal['children', 'watcher']='children') -> tuple[bool, str | None]`
- [ExecutionConfig.resolve_fractional_protection_time_in_force](../../execution_engine/config.py) — ligne 414 : `def resolve_fractional_protection_time_in_force(self, qty: float) -> str`
- [ExecutionConfig.effective_reconcile_tolerance_shares](../../execution_engine/config.py) — ligne 429 : `def effective_reconcile_tolerance_shares(self) -> float`
- [ExecutionConfig.blocks_new_entries](../../execution_engine/config.py) — ligne 434 : `def blocks_new_entries(self) -> bool`
- [ProtectionWatcherServiceConfig](../../execution_engine/config.py) — ligne 440 : `class ProtectionWatcherServiceConfig`
- [ProtectionWatcherServiceConfig.__post_init__](../../execution_engine/config.py) — ligne 450 : `def __post_init__(self) -> None`

## `execution_engine/db_io.py`

Source SHA-256 : `76f5a5105edfba59f4abcb4f067c03a55f48a92f35f36077da8a1aa49d2aa7f3`

- [ExecutionRepository](../../execution_engine/db_io.py) — ligne 31 : `class ExecutionRepository`
- [ExecutionRepository.__init__](../../execution_engine/db_io.py) — ligne 34 : `def __init__(self, engine: Engine | None=None) -> None`
- [ExecutionRepository.persist_kill_switch_run](../../execution_engine/db_io.py) — ligne 40 : `def persist_kill_switch_run(self, *, run_id: str, account_id: str, broker_mode: str, reason: str, results: list[dict[str, Any]], dry_run: bool, started_at: datetime, finished_at: datetime) -> None`
- [ExecutionRepository._has_table](../../execution_engine/db_io.py) — ligne 98 : `def _has_table(self, table_name: str) -> bool`
- [ExecutionRepository.load_llm_protection_profile](../../execution_engine/db_io.py) — ligne 104 : `def load_llm_protection_profile(self, risk_run_id, symbol, *, account_id, broker_mode)`
- [ExecutionRepository.load_entry_fill_price](../../execution_engine/db_io.py) — ligne 109 : `def load_entry_fill_price(self, parent_intent_id: str) -> float | None`
- [ExecutionRepository._get_table_columns](../../execution_engine/db_io.py) — ligne 121 : `def _get_table_columns(self, table_name: str) -> set[str]`
- [ExecutionRepository._optional_int](../../execution_engine/db_io.py) — ligne 132 : `def _optional_int(value: Any) -> int | None`
- [ExecutionRepository._optional_text](../../execution_engine/db_io.py) — ligne 141 : `def _optional_text(value: Any) -> str | None`
- [ExecutionRepository._portfolio_targets_select_clause](../../execution_engine/db_io.py) — ligne 147 : `def _portfolio_targets_select_clause(self) -> str`
- [ExecutionRepository.load_fractionable_asset_map](../../execution_engine/db_io.py) — ligne 171 : `def load_fractionable_asset_map(self, symbols: list[str]) -> dict[str, bool]`
- [ExecutionRepository._execution_targets_snapshot_select_clause](../../execution_engine/db_io.py) — ligne 202 : `def _execution_targets_snapshot_select_clause(self) -> str`
- [ExecutionRepository._resolve_latest_risk_run_from_summary](../../execution_engine/db_io.py) — ligne 226 : `def _resolve_latest_risk_run_from_summary(self, *, account_id: str, trade_date: date | None) -> tuple[str | None, bool]`
- [ExecutionRepository.load_portfolio_targets](../../execution_engine/db_io.py) — ligne 289 : `def load_portfolio_targets(self, risk_run_id: str | None=None, trade_date: date | None=None, account_id: str | None=None) -> list[ExecutionTarget]`
- [ExecutionRepository.load_previous_closes_asof](../../execution_engine/db_io.py) — ligne 393 : `def load_previous_closes_asof(self, *, symbols: list[str], trade_date: date) -> dict[str, float]`
- [ExecutionRepository.load_submitted_idempotency_keys](../../execution_engine/db_io.py) — ligne 429 : `def load_submitted_idempotency_keys(self, exec_run_id: str) -> set[str]`
- [ExecutionRepository.find_order_request_by_submission_key](../../execution_engine/db_io.py) — ligne 438 : `def find_order_request_by_submission_key(self, *, account_id: str, submission_key: str) -> ExecutionOrderRequest | None`
- [ExecutionRepository.find_order_request_by_broker_order_id](../../execution_engine/db_io.py) — ligne 458 : `def find_order_request_by_broker_order_id(self, *, account_id: str, broker_order_id: str) -> ExecutionOrderRequest | None`
- [ExecutionRepository.load_cumulative_filled_qty](../../execution_engine/db_io.py) — ligne 480 : `def load_cumulative_filled_qty(self, *, request_id: str) -> float`
- [ExecutionRepository.load_execution_position_lot_inputs](../../execution_engine/db_io.py) — ligne 490 : `def load_execution_position_lot_inputs(self, *, account_id: str) -> list[dict[str, Any]]`
- [ExecutionRepository.load_execution_targets_snapshot](../../execution_engine/db_io.py) — ligne 503 : `def load_execution_targets_snapshot(self, *, exec_run_id: str) -> list[ExecutionTarget]`
- [ExecutionRepository.load_open_reconciliation_order_state](../../execution_engine/db_io.py) — ligne 544 : `def load_open_reconciliation_order_state(self, *, account_id: str) -> list[dict[str, Any]]`
- [ExecutionRepository.load_reconciliation_protection_state](../../execution_engine/db_io.py) — ligne 562 : `def load_reconciliation_protection_state(self, *, account_id: str) -> list[dict[str, Any]]`
- [ExecutionRepository.load_latest_broker_account_snapshot](../../execution_engine/db_io.py) — ligne 589 : `def load_latest_broker_account_snapshot(self, *, account_id: str, snapshot_kind: str='preflight') -> dict[str, Any] | None`
- [ExecutionRepository.load_internal_ledger_for_run](../../execution_engine/db_io.py) — ligne 608 : `def load_internal_ledger_for_run(self, *, exec_run_id: str, account_id: str) -> dict[str, float | None]`
- [ExecutionRepository.load_execution_run_context](../../execution_engine/db_io.py) — ligne 672 : `def load_execution_run_context(self, *, exec_run_id: str) -> dict[str, Any] | None`
- [ExecutionRepository.load_execution_run_context_for_risk_run_id](../../execution_engine/db_io.py) — ligne 684 : `def load_execution_run_context_for_risk_run_id(self, *, risk_run_id: str, account_id: str | None=None, trade_date: date | None=None) -> dict[str, Any] | None`
- [ExecutionRepository.load_latest_execution_run_id_for_date](../../execution_engine/db_io.py) — ligne 723 : `def load_latest_execution_run_id_for_date(self, *, trade_date: date, account_id: str | None=None) -> str | None`
- [ExecutionRepository.load_latest_execution_targets_snapshot_for_date](../../execution_engine/db_io.py) — ligne 753 : `def load_latest_execution_targets_snapshot_for_date(self, *, trade_date: date, account_id: str | None=None) -> list[ExecutionTarget]`
- [ExecutionRepository.load_execution_fills_for_run](../../execution_engine/db_io.py) — ligne 767 : `def load_execution_fills_for_run(self, *, exec_run_id: str, account_id: str | None=None) -> pd.DataFrame`
- [ExecutionRepository.load_reconciliation_orders_for_run](../../execution_engine/db_io.py) — ligne 829 : `def load_reconciliation_orders_for_run(self, *, exec_run_id: str, account_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]`
- [ExecutionRepository.load_reconciliation_protections_for_run](../../execution_engine/db_io.py) — ligne 854 : `def load_reconciliation_protections_for_run(self, *, exec_run_id: str, account_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]`
- [ExecutionRepository.load_execution_position_lots_for_open_run](../../execution_engine/db_io.py) — ligne 886 : `def load_execution_position_lots_for_open_run(self, *, open_exec_run_id: str, account_id: str | None=None) -> pd.DataFrame`
- [ExecutionRepository.load_open_child_orders](../../execution_engine/db_io.py) — ligne 975 : `def load_open_child_orders(self, parent_intent_id: str) -> list[BrokerOrder]`
- [ExecutionRepository.has_open_exit_order_for_symbol](../../execution_engine/db_io.py) — ligne 1002 : `def has_open_exit_order_for_symbol(self, *, account_id: str, symbol: str) -> bool`
- [ExecutionRepository.load_time_stop_positions](../../execution_engine/db_io.py) — ligne 1026 : `def load_time_stop_positions(self, *, account_id: str | None=None, limit: int=500) -> list[dict[str, Any]]`
- [ExecutionRepository.load_unprotected_filled_parents](../../execution_engine/db_io.py) — ligne 1102 : `def load_unprotected_filled_parents(self, *, exec_run_id: str | None=None, account_id: str | None=None, limit: int=200) -> list[dict[str, Any]]`
- [ExecutionRepository.load_orphan_filled_buy_positions](../../execution_engine/db_io.py) — ligne 1271 : `def load_orphan_filled_buy_positions(self, *, account_id: str | None=None, limit: int=200) -> list[dict[str, Any]]`
- [ExecutionRepository.load_latest_broker_order_status](../../execution_engine/db_io.py) — ligne 1315 : `def load_latest_broker_order_status(self, *, account_id: str, broker_order_id: str) -> dict[str, Any] | None`
- [ExecutionRepository.load_pending_protection_watch_items](../../execution_engine/db_io.py) — ligne 1341 : `def load_pending_protection_watch_items(self, *, exec_run_id: str | None=None, account_id: str | None=None, limit: int=100) -> list[ProtectionWatchItem]`
- [ExecutionRepository._rows_to_protection_watch_items](../../execution_engine/db_io.py) — ligne 1413 : `def _rows_to_protection_watch_items(rows: list[Any]) -> list[ProtectionWatchItem]`
- [ExecutionRepository._row_to_broker_order](../../execution_engine/db_io.py) — ligne 1437 : `def _row_to_broker_order(r: Any) -> BrokerOrder`
- [ExecutionRepository._row_to_execution_order_request](../../execution_engine/db_io.py) — ligne 1457 : `def _row_to_execution_order_request(r: Any) -> ExecutionOrderRequest`
- [ExecutionRepository.acquire_execution_lock](../../execution_engine/db_io.py) — ligne 1484 : `def acquire_execution_lock(self, *, account_id: str | None, exec_run_id: str, ttl_seconds: int=3600) -> bool`
- [ExecutionRepository.release_execution_lock](../../execution_engine/db_io.py) — ligne 1517 : `def release_execution_lock(self, *, account_id: str | None, exec_run_id: str) -> None`
- [ExecutionRepository.refresh_execution_lock](../../execution_engine/db_io.py) — ligne 1527 : `def refresh_execution_lock(self, *, account_id: str | None, exec_run_id: str, ttl_seconds: int=3600) -> bool`
- [ExecutionRepository.force_release_execution_lock](../../execution_engine/db_io.py) — ligne 1551 : `def force_release_execution_lock(self, *, account_id: str | None) -> int`
- [ExecutionRepository.upsert_watcher_heartbeat](../../execution_engine/db_io.py) — ligne 1566 : `def upsert_watcher_heartbeat(self, *, watcher_name: str, account_id: str | None=None, hostname: str | None=None, pid: int | None=None, status: str='RUNNING', last_error: str | None=None) -> None`
- [ExecutionRepository.is_watcher_healthy](../../execution_engine/db_io.py) — ligne 1612 : `def is_watcher_healthy(self, *, account_id: str | None=None, max_age_seconds: int=900) -> bool`
- [ExecutionRepository.snapshot_execution_targets](../../execution_engine/db_io.py) — ligne 1646 : `def snapshot_execution_targets(self, *, exec_run_id: str, account_id: str | None, targets: list[ExecutionTarget]) -> int`
- [ExecutionRepository.insert_execution_run](../../execution_engine/db_io.py) — ligne 1711 : `def insert_execution_run(self, exec_run_id: str, risk_run_id: str, trade_date: date, broker_mode: str, dry_run: bool, total_targets: int, account_id: str | None=None, execution_profile: str | None=None, submission_window: str | None=None, market_code: str | None=None) -> None`
- [ExecutionRepository.update_execution_run_status](../../execution_engine/db_io.py) — ligne 1778 : `def update_execution_run_status(self, exec_run_id: str, status: str, total_submitted: int=0, total_filled: int=0, error_message: str | None=None) -> None`
- [ExecutionRepository._next_request_attempt_no](../../execution_engine/db_io.py) — ligne 1805 : `def _next_request_attempt_no(self, account_id: str, business_key: str) -> int`
- [ExecutionRepository._load_request_attempt_no](../../execution_engine/db_io.py) — ligne 1816 : `def _load_request_attempt_no(self, request_id: str) -> int | None`
- [ExecutionRepository.upsert_execution_order_request_from_intent](../../execution_engine/db_io.py) — ligne 1822 : `def upsert_execution_order_request_from_intent(self, intent: OrderIntent, *, account_id: str, status: str, failure_reason: str | None=None) -> int`
- [ExecutionRepository.upsert_execution_broker_order](../../execution_engine/db_io.py) — ligne 1904 : `def upsert_execution_broker_order(self, intent: OrderIntent, order: BrokerOrder, *, account_id: str, raw_payload: dict[str, Any] | None=None, raw_response: dict[str, Any] | None=None) -> None`
- [ExecutionRepository.insert_execution_broker_fill](../../execution_engine/db_io.py) — ligne 1982 : `def insert_execution_broker_fill(self, fill: ExecutionFill, *, account_id: str, raw_fill: dict[str, Any] | None=None) -> None`
- [ExecutionRepository.snapshot_broker_account](../../execution_engine/db_io.py) — ligne 2036 : `def snapshot_broker_account(self, exec_run_id: str, *, account_id: str, broker_mode: str, snapshot: dict[str, Any], snapshot_kind: str='preflight', allow_zero_equity: bool=False) -> None`
- [ExecutionRepository.insert_execution_event](../../execution_engine/db_io.py) — ligne 2088 : `def insert_execution_event(self, event_dict: dict[str, Any]) -> None`
- [ExecutionRepository.snapshot_broker_positions](../../execution_engine/db_io.py) — ligne 2100 : `def snapshot_broker_positions(self, exec_run_id: str, broker_mode: str, positions: list[dict[str, Any]], account_id: str | None=None) -> None`
- [ExecutionRepository.replace_execution_positions](../../execution_engine/db_io.py) — ligne 2135 : `def replace_execution_positions(self, *, exec_run_id: str, account_id: str, broker_mode: str, positions: list[dict[str, Any]]) -> int`
- [ExecutionRepository.rebuild_execution_position_lots](../../execution_engine/db_io.py) — ligne 2201 : `def rebuild_execution_position_lots(self, *, account_id: str) -> int`
- [ExecutionRepository.replace_execution_reconciliation_results](../../execution_engine/db_io.py) — ligne 2280 : `def replace_execution_reconciliation_results(self, *, exec_run_id: str, account_id: str, results: list[ExecutionReconciliationResult]) -> int`
- [ExecutionRepository.load_execution_positions](../../execution_engine/db_io.py) — ligne 2335 : `def load_execution_positions(self, *, account_id: str | None=None) -> list[ExecutionPosition]`
- [ExecutionRepository.load_execution_position_lots](../../execution_engine/db_io.py) — ligne 2364 : `def load_execution_position_lots(self, *, account_id: str | None=None) -> list[ExecutionPositionLot]`
- [ExecutionRepository.load_execution_reconciliation_results](../../execution_engine/db_io.py) — ligne 2399 : `def load_execution_reconciliation_results(self, *, exec_run_id: str | None=None, account_id: str | None=None) -> list[ExecutionReconciliationResult]`

## `execution_engine/executor.py`

Source SHA-256 : `0bebc87f53e4a7dac7672c0a43afc4431fb1a1e7714315234d43cc4d610f34e3`

- [ProductionExecutor](../../execution_engine/executor.py) — ligne 79 : `class ProductionExecutor`
- [ProductionExecutor.__init__](../../execution_engine/executor.py) — ligne 82 : `def __init__(self, config: ExecutionConfig, repo: ExecutionRepository, broker: ExecutionBrokerPort, oco: OcoManager, circuit_breaker: Optional[Any]=None, progress_callback: Callable[[dict[str, object]], None] | None=None) -> None`
- [ProductionExecutor.set_pre_submission_data](../../execution_engine/executor.py) — ligne 105 : `def set_pre_submission_data(self, *, spreads: dict[str, object] | None=None, borrows: dict[str, object] | None=None, adv: dict[str, float] | None=None, daily_vol: dict[str, float] | None=None) -> None`
- [ProductionExecutor.set_decision_fingerprints](../../execution_engine/executor.py) — ligne 135 : `def set_decision_fingerprints(self, fingerprints: dict[str, str]) -> None`
- [ProductionExecutor._emit_progress](../../execution_engine/executor.py) — ligne 146 : `def _emit_progress(self, metrics: dict[str, Any], *, current: int, total: int, label: str, phase: str, item: str | None=None, unit: str='symboles') -> None`
- [ProductionExecutor.execute_run](../../execution_engine/executor.py) — ligne 177 : `def execute_run(self, risk_run_id: str | None=None, trade_date: date | None=None) -> dict[str, Any]`
- [ProductionExecutor._build_account_constraint_state](../../execution_engine/executor.py) — ligne 1372 : `def _build_account_constraint_state(self) -> _AccountConstraintState`
- [ProductionExecutor._safe_float](../../execution_engine/executor.py) — ligne 1376 : `def _safe_float(value: object, *, default: float=0.0) -> float`
- [ProductionExecutor._estimate_intent_notional](../../execution_engine/executor.py) — ligne 1379 : `def _estimate_intent_notional(self, intent: OrderIntent) -> float`
- [ProductionExecutor._reserve_account_capacity_for_intent](../../execution_engine/executor.py) — ligne 1382 : `def _reserve_account_capacity_for_intent(self, intent: OrderIntent, account_state: _AccountConstraintState, exec_run_id: str, events: list[ExecutionEvent], metrics: dict[str, int]) -> bool`
- [ProductionExecutor._should_defer_children](../../execution_engine/executor.py) — ligne 1394 : `def _should_defer_children(self, account_state: _AccountConstraintState) -> tuple[bool, str | None]`
- [ProductionExecutor._poll_until_terminal](../../execution_engine/executor.py) — ligne 1400 : `def _poll_until_terminal(self, broker_order_id: str, intent_id: str, exec_run_id: str) -> BrokerOrder | None`
- [ProductionExecutor._build_fill](../../execution_engine/executor.py) — ligne 1414 : `def _build_fill(self, order: BrokerOrder, intent: OrderIntent) -> ExecutionFill`
- [ProductionExecutor._snapshot_account_constraints](../../execution_engine/executor.py) — ligne 1431 : `def _snapshot_account_constraints(self, exec_run_id: str, account_state: _AccountConstraintState) -> None`
- [ProductionExecutor._persist_order_request_state](../../execution_engine/executor.py) — ligne 1469 : `def _persist_order_request_state(self, intent: OrderIntent, *, status: str, failure_reason: str | None=None) -> None`
- [ProductionExecutor._persist_broker_order_state](../../execution_engine/executor.py) — ligne 1486 : `def _persist_broker_order_state(self, intent: OrderIntent, order: BrokerOrder) -> None`
- [ProductionExecutor._persist_child_order_state](../../execution_engine/executor.py) — ligne 1500 : `def _persist_child_order_state(self, intent: OrderIntent, order: BrokerOrder) -> None`
- [ProductionExecutor._cancel_child_for_transition](../../execution_engine/executor.py) — ligne 1508 : `def _cancel_child_for_transition(self, intent: OrderIntent, order: BrokerOrder, exec_run_id: str) -> tuple[bool, BrokerOrder]`
- [ProductionExecutor._maybe_activate_dynamic_trailing](../../execution_engine/executor.py) — ligne 1538 : `def _maybe_activate_dynamic_trailing(self, parent: OrderIntent, fill_qty: float, fill_price: float, exec_run_id: str, *, target: Any | None, initial_stop_intent: OrderIntent | None, initial_stop_order: BrokerOrder | None, metrics: dict[str, int]) -> list[ExecutionEvent]`
- [ProductionExecutor._submit_children](../../execution_engine/executor.py) — ligne 1562 : `def _submit_children(self, parent: OrderIntent, filled_order: BrokerOrder, exec_run_id: str, *, account_state: _AccountConstraintState, metrics: dict[str, int], target: Any | None=None) -> list[ExecutionEvent]`
- [ProductionExecutor._reconstruct_parent_for_arming](../../execution_engine/executor.py) — ligne 1586 : `def _reconstruct_parent_for_arming(self, row: dict[str, Any]) -> tuple[OrderIntent, BrokerOrder]`
- [ProductionExecutor._submit_rebalance_orders](../../execution_engine/executor.py) — ligne 1633 : `def _submit_rebalance_orders(self, action_diffs: list, exec_run_id: str, targets: list, metrics: dict[str, int], account_state: _AccountConstraintState) -> list[ExecutionEvent]`
- [ProductionExecutor._persist_events](../../execution_engine/executor.py) — ligne 1650 : `def _persist_events(self, events: list[ExecutionEvent]) -> None`

## `execution_engine/executor_phases.py`

Source SHA-256 : `e7f387cbbd4f9b0b66415135c6d245c51cf6faff53acf129e565f0b5f1a7afe8`

- [is_phases_orchestrator_enabled](../../execution_engine/executor_phases.py) — ligne 41 : `def is_phases_orchestrator_enabled() -> bool`
- [PhaseStatus](../../execution_engine/executor_phases.py) — ligne 46 : `class PhaseStatus(str, Enum)`
- [PhaseOutcome](../../execution_engine/executor_phases.py) — ligne 53 : `class PhaseOutcome`
- [PhaseOutcome.should_continue](../../execution_engine/executor_phases.py) — ligne 59 : `def should_continue(self) -> bool`
- [PhaseContext](../../execution_engine/executor_phases.py) — ligne 64 : `class PhaseContext`
- [phase_init_and_preflight](../../execution_engine/executor_phases.py) — ligne 101 : `def phase_init_and_preflight(executor: Any, ctx: PhaseContext) -> PhaseOutcome`
- [phase_build_and_submit](../../execution_engine/executor_phases.py) — ligne 127 : `def phase_build_and_submit(executor: Any, ctx: PhaseContext) -> PhaseOutcome`
- [phase_poll_and_children](../../execution_engine/executor_phases.py) — ligne 142 : `def phase_poll_and_children(executor: Any, ctx: PhaseContext) -> PhaseOutcome`
- [phase_reconcile_and_finalize](../../execution_engine/executor_phases.py) — ligne 157 : `def phase_reconcile_and_finalize(executor: Any, ctx: PhaseContext) -> PhaseOutcome`
- [run_phases](../../execution_engine/executor_phases.py) — ligne 179 : `def run_phases(executor: Any, ctx: PhaseContext) -> dict[str, Any]`

## `execution_engine/market_regime_preflight.py`

Source SHA-256 : `b7866bf29c1efe9f43d106cb324df476d14fc1c06ff2f29396636ab2bac5f913`

- [render_text_summary](../../execution_engine/market_regime_preflight.py) — ligne 16 : `def render_text_summary(snapshot_dict: dict[str, Any]) -> str`
- [emit_preflight](../../execution_engine/market_regime_preflight.py) — ligne 41 : `def emit_preflight(snapshot_dict: dict[str, Any], *, also_log: bool=True) -> str`
- [derive_entry_mode](../../execution_engine/market_regime_preflight.py) — ligne 50 : `def derive_entry_mode(snapshot_dict: dict[str, Any]) -> str`

## `execution_engine/models.py`

Source SHA-256 : `ac1b842b6c1019a5476c4712fbd3e23b8df19035788b4827a0a0c65d3be87a41`

- [OrderStatus](../../execution_engine/models.py) — ligne 12 : `class OrderStatus`
- [CancelResult](../../execution_engine/models.py) — ligne 27 : `class CancelResult`
- [EventType](../../execution_engine/models.py) — ligne 36 : `class EventType`
- [ReconciliationStatus](../../execution_engine/models.py) — ligne 80 : `class ReconciliationStatus`
- [IntentRole](../../execution_engine/models.py) — ligne 86 : `class IntentRole`
- [ExecutionTarget](../../execution_engine/models.py) — ligne 104 : `class ExecutionTarget`
- [OrderIntent](../../execution_engine/models.py) — ligne 142 : `class OrderIntent`
- [ExecutionOrderRequest](../../execution_engine/models.py) — ligne 166 : `class ExecutionOrderRequest`
- [BrokerOrder](../../execution_engine/models.py) — ligne 190 : `class BrokerOrder`
- [ExecutionFill](../../execution_engine/models.py) — ligne 210 : `class ExecutionFill`
- [BrokerOrderObservation](../../execution_engine/models.py) — ligne 225 : `class BrokerOrderObservation`
- [BrokerAccountSnapshot](../../execution_engine/models.py) — ligne 250 : `class BrokerAccountSnapshot`
- [ExecutionPosition](../../execution_engine/models.py) — ligne 266 : `class ExecutionPosition`
- [ExecutionPositionLot](../../execution_engine/models.py) — ligne 283 : `class ExecutionPositionLot`
- [ExecutionReconciliationResult](../../execution_engine/models.py) — ligne 305 : `class ExecutionReconciliationResult`
- [ExecutionEvent](../../execution_engine/models.py) — ligne 327 : `class ExecutionEvent`
- [ReconcileDiff](../../execution_engine/models.py) — ligne 341 : `class ReconcileDiff`
- [TcaSummary](../../execution_engine/models.py) — ligne 351 : `class TcaSummary`
- [ProtectionWatchItem](../../execution_engine/models.py) — ligne 363 : `class ProtectionWatchItem`

## `execution_engine/oco_manager.py`

Source SHA-256 : `06f9d53a8b43c70173efb2381288f5fcf55e99557d453d4c15a2e7a069590a0b`

- [OcoManager](../../execution_engine/oco_manager.py) — ligne 14 : `class OcoManager`
- [OcoManager.__init__](../../execution_engine/oco_manager.py) — ligne 17 : `def __init__(self, broker: ExecutionBrokerPort, repo: ExecutionRepository) -> None`
- [OcoManager.check_and_cancel_sibling](../../execution_engine/oco_manager.py) — ligne 21 : `def check_and_cancel_sibling(self, filled_intent: OrderIntent, exec_run_id: str) -> list[ExecutionEvent]`

## `execution_engine/order_intents.py`

Source SHA-256 : `a4489b25caf7c7b5b6d342237e718f10699a2cd9db051a4c9c88aecbd1e3afe8`

- [_make_id](../../execution_engine/order_intents.py) — ligne 16 : `def _make_id() -> str`
- [_idempotency_key](../../execution_engine/order_intents.py) — ligne 20 : `def _idempotency_key(run_id: str, symbol: str, role: str, side: str, qty: float, broker_mode: str) -> str`
- [_submission_key](../../execution_engine/order_intents.py) — ligne 26 : `def _submission_key(exec_run_id: str, symbol: str, role: str, side: str, qty: float, unique_id: str | None=None) -> str`
- [_alpaca_client_order_id](../../execution_engine/order_intents.py) — ligne 40 : `def _alpaca_client_order_id(exec_run_id: str, symbol: str, role: str, side: str, qty: float) -> str`
- [resolve_initial_stop_price](../../execution_engine/order_intents.py) — ligne 44 : `def resolve_initial_stop_price(reference_price: float, target: ExecutionTarget | None=None, side: str='buy') -> float | None`
- [resolve_trailing_activation_price](../../execution_engine/order_intents.py) — ligne 76 : `def resolve_trailing_activation_price(fill_price: float, config: ExecutionConfig, target: ExecutionTarget | None=None, side: str='buy') -> tuple[float | None, str | None]`
- [build_entry_intents](../../execution_engine/order_intents.py) — ligne 105 : `def build_entry_intents(targets: list[ExecutionTarget], config: ExecutionConfig, exec_run_id: str, *, decision_fingerprints: dict[str, str] | None=None) -> list[OrderIntent]`
- [apply_live_leverage_to_targets](../../execution_engine/order_intents.py) — ligne 171 : `def apply_live_leverage_to_targets(*, targets: list[ExecutionTarget], effective_leverage: float, active: bool, allow_fractional_shares: bool, exposure_multiplier: float=1.0) -> tuple[list[ExecutionTarget], dict[str, float | int | bool]]`
- [_target_priority_key](../../execution_engine/order_intents.py) — ligne 304 : `def _target_priority_key(target: ExecutionTarget) -> tuple[int, int, str]`
- [_normalized_target_side](../../execution_engine/order_intents.py) — ligne 314 : `def _normalized_target_side(target: ExecutionTarget) -> str`
- [filter_targets_by_live_regime_guards](../../execution_engine/order_intents.py) — ligne 318 : `def filter_targets_by_live_regime_guards(*, targets: list[ExecutionTarget], config: ExecutionConfig, fractionable_by_symbol: dict[str, bool] | None=None) -> tuple[list[ExecutionTarget], list[dict[str, float | int | str | None]]]`
- [split_entry_intents_by_gap_filter](../../execution_engine/order_intents.py) — ligne 476 : `def split_entry_intents_by_gap_filter(*, targets: list[ExecutionTarget], intents: list[OrderIntent], config: ExecutionConfig, latest_market_prices: dict[str, float] | None=None) -> tuple[list[OrderIntent], list[dict[str, float | str | None]]]`
- [build_take_profit_intent](../../execution_engine/order_intents.py) — ligne 520 : `def build_take_profit_intent(parent: OrderIntent, fill_qty: float, avg_fill_price: float, config: ExecutionConfig, target: ExecutionTarget | None=None) -> OrderIntent | None`
- [build_initial_stop_intent](../../execution_engine/order_intents.py) — ligne 589 : `def build_initial_stop_intent(parent: OrderIntent, fill_qty: float, avg_fill_price: float, config: ExecutionConfig, target: ExecutionTarget | None=None) -> OrderIntent | None`
- [build_manual_buy_initial_stop_intent](../../execution_engine/order_intents.py) — ligne 650 : `def build_manual_buy_initial_stop_intent(parent: OrderIntent, fill_qty: float, avg_fill_price: float, config: ExecutionConfig, *, atr_value: float | None=None) -> OrderIntent | None`
- [build_trailing_stop_intent](../../execution_engine/order_intents.py) — ligne 718 : `def build_trailing_stop_intent(parent: OrderIntent, fill_qty: float, avg_fill_price: float, config: ExecutionConfig, target: ExecutionTarget | None=None) -> OrderIntent`
- [build_rebalance_sell_intent](../../execution_engine/order_intents.py) — ligne 790 : `def build_rebalance_sell_intent(exec_run_id: str, risk_run_id: str, symbol: str, qty: float, broker_mode: str, current_price: float=0.0) -> OrderIntent`
- [build_rebalance_buy_intent](../../execution_engine/order_intents.py) — ligne 821 : `def build_rebalance_buy_intent(exec_run_id: str, risk_run_id: str, symbol: str, qty: float, broker_mode: str, current_price: float=0.0) -> OrderIntent`
- [_resolve_alpaca_time_in_force](../../execution_engine/order_intents.py) — ligne 852 : `def _resolve_alpaca_time_in_force(intent: OrderIntent, config: ExecutionConfig | None=None) -> str`
- [intent_to_alpaca_payload](../../execution_engine/order_intents.py) — ligne 866 : `def intent_to_alpaca_payload(intent: OrderIntent, config: ExecutionConfig | None=None) -> dict[str, str]`
- [build_oco_protection_payload](../../execution_engine/order_intents.py) — ligne 892 : `def build_oco_protection_payload(parent: OrderIntent, tp_intent: OrderIntent, stop_intent: OrderIntent, oco_id: str | None=None, config: ExecutionConfig | None=None) -> dict[str, str | dict[str, str]]`

## `execution_engine/orphan_adoption.py`

Source SHA-256 : `5008a83e4f900cd0cfa0feb8e966377edc3743b6133cec7f827ed0f423f57052`

- [AdoptionResult](../../execution_engine/orphan_adoption.py) — ligne 49 : `class AdoptionResult`
- [_stable_id](../../execution_engine/orphan_adoption.py) — ligne 57 : `def _stable_id(seed: str, length: int=16) -> str`
- [_ensure_adoption_run](../../execution_engine/orphan_adoption.py) — ligne 61 : `def _ensure_adoption_run(repo: ExecutionRepository, *, account_id: str, broker_mode: str, trade_date) -> str`
- [_build_synthetic_intent](../../execution_engine/orphan_adoption.py) — ligne 100 : `def _build_synthetic_intent(*, exec_run_id: str, symbol: str, side: str, qty: float, order_type: str, broker_mode: str, decision_price: float, role: str, business_key: str, submission_key: str | None, limit_price: float | None=None, stop_price: float | None=None) -> OrderIntent`
- [_build_broker_order_from_payload](../../execution_engine/orphan_adoption.py) — ligne 135 : `def _build_broker_order_from_payload(*, intent: OrderIntent, broker_order_id: str, client_order_id: str | None, raw_order: dict[str, Any] | None, qty: float, filled_qty: float, avg_fill_price: float | None, status: str) -> BrokerOrder`
- [_persist_event](../../execution_engine/orphan_adoption.py) — ligne 180 : `def _persist_event(repo: ExecutionRepository, event) -> None`
- [_normalize_status](../../execution_engine/orphan_adoption.py) — ligne 187 : `def _normalize_status(raw_status: str | None) -> str`
- [adopt_orphan_sell](../../execution_engine/orphan_adoption.py) — ligne 205 : `def adopt_orphan_sell(repo: ExecutionRepository, *, broker_mode: str, account_id: str, raw_order: dict[str, Any], trade_date=None) -> AdoptionResult | None`
- [adopt_orphan_buy](../../execution_engine/orphan_adoption.py) — ligne 315 : `def adopt_orphan_buy(repo: ExecutionRepository, *, broker_mode: str, account_id: str, raw_order: dict[str, Any] | None=None, broker_position: dict[str, Any] | None=None, trade_date=None) -> AdoptionResult | None`

## `execution_engine/preflight.py`

Source SHA-256 : `1834a6dac9e2273615bc8af5350921c6cb9a3783b8cd61baa802e43fdc23475d`

- [CheckResult](../../execution_engine/preflight.py) — ligne 47 : `class CheckResult`
- [CheckResult.to_dict](../../execution_engine/preflight.py) — ligne 53 : `def to_dict(self) -> dict[str, Any]`
- [PreflightContext](../../execution_engine/preflight.py) — ligne 59 : `class PreflightContext`
- [PreflightReport](../../execution_engine/preflight.py) — ligne 72 : `class PreflightReport`
- [PreflightReport.passed](../../execution_engine/preflight.py) — ligne 81 : `def passed(self) -> bool`
- [PreflightReport.to_dict](../../execution_engine/preflight.py) — ligne 84 : `def to_dict(self) -> dict[str, Any]`
- [check_no_global_kill_switch_active](../../execution_engine/preflight.py) — ligne 106 : `def check_no_global_kill_switch_active(ctx: PreflightContext) -> CheckResult`
- [check_recent_dry_run](../../execution_engine/preflight.py) — ligne 139 : `def check_recent_dry_run(ctx: PreflightContext) -> CheckResult`
- [check_alpaca_credentials](../../execution_engine/preflight.py) — ligne 179 : `def check_alpaca_credentials(ctx: PreflightContext) -> CheckResult`
- [check_ml_drift_gate](../../execution_engine/preflight.py) — ligne 229 : `def check_ml_drift_gate(ctx: PreflightContext) -> CheckResult`
- [check_no_literal_secrets](../../execution_engine/preflight.py) — ligne 276 : `def check_no_literal_secrets(ctx: PreflightContext) -> CheckResult`
- [check_no_pipeline_lock_held](../../execution_engine/preflight.py) — ligne 294 : `def check_no_pipeline_lock_held(ctx: PreflightContext) -> CheckResult`
- [check_live_secret_policy](../../execution_engine/preflight.py) — ligne 314 : `def check_live_secret_policy(ctx: PreflightContext) -> CheckResult`
- [run_preflight](../../execution_engine/preflight.py) — ligne 359 : `def run_preflight(account_id: str, *, broker_mode: str='live', engine: Any | None=None, registry: Any | None=None, config_path: Path | None=None, alpaca_client_factory: Callable[..., Any] | None=None, pipeline_lock_module: Any | None=None, max_dry_run_age_hours: int=24, skip_network: bool=False, checks: tuple[Callable[[PreflightContext], CheckResult], ...] | None=None) -> PreflightReport`
- [_build_parser](../../execution_engine/preflight.py) — ligne 408 : `def _build_parser() -> argparse.ArgumentParser`
- [main](../../execution_engine/preflight.py) — ligne 425 : `def main(argv: list[str] | None=None) -> int`

## `execution_engine/protection_break_even.py`

Source SHA-256 : `37ef05668b1b196a54a71fa2c766d4caae2907b1da68a5b38dfa00b5e0bdc772`

- [should_promote_to_break_even](../../execution_engine/protection_break_even.py) — ligne 23 : `def should_promote_to_break_even(*, avg_fill_price: float, current_price: float, atr_value: float | None, shares: float, cfg: 'TrailingStopConfig') -> bool`
- [compute_break_even_stop_price](../../execution_engine/protection_break_even.py) — ligne 41 : `def compute_break_even_stop_price(avg_fill_price: float) -> float`
- [_parse_hhmm](../../execution_engine/protection_break_even.py) — ligne 46 : `def _parse_hhmm(s: str) -> time`
- [is_eod_review_window](../../execution_engine/protection_break_even.py) — ligne 53 : `def is_eod_review_window(*, now_eastern: datetime, cfg: 'TrailingStopConfig') -> bool`

## `execution_engine/protection_state_bridge.py`

Source SHA-256 : `805b8b5c7fe3f96013408e8a14554a421af92b23406b095e39db862c119c3371`

- [build_protection_state_from_fill](../../execution_engine/protection_state_bridge.py) — ligne 31 : `def build_protection_state_from_fill(symbol: str, side: str, fill_qty: float, fill_price: float, *, decision_price: float | None=None, atr: float | None=None, parent_intent_id: str | None=None, stop_price_initial: float | None=None, risk_per_share: float | None=None, decision_fingerprint: str | None=None) -> dict[str, Any]`
- [persist_protection_state](../../execution_engine/protection_state_bridge.py) — ligne 91 : `def persist_protection_state(state_dict: dict[str, Any], *, exec_run_id: str, root_dir: Path | None=None) -> Path`
- [verify_fill_protection_consistency](../../execution_engine/protection_state_bridge.py) — ligne 118 : `def verify_fill_protection_consistency(state_dict: dict[str, Any]) -> tuple[bool, list[str]]`

## `execution_engine/protection_transition.py`

Source SHA-256 : `978b878b54c2bbe73d9ecae16af28b43630cdbb80ad935ca00693c73b45aec83`

- [maybe_activate_dynamic_trailing](../../execution_engine/protection_transition.py) — ligne 27 : `def maybe_activate_dynamic_trailing(executor: 'ProductionExecutor', parent: OrderIntent, fill_qty: float, fill_price: float, exec_run_id: str, *, target: Any | None, initial_stop_intent: OrderIntent | None, initial_stop_order: BrokerOrder | None, metrics: dict[str, int]) -> list[ExecutionEvent]`

## `execution_engine/protection_watcher.py`

Source SHA-256 : `258ce3f748e059ce2f7bf9c3db32bcd31df7f411e39ee9cf3b8cbe324076e109`

- [_build_summary](../../execution_engine/protection_watcher.py) — ligne 47 : `def _build_summary(metrics: dict[str, Any], *, watch_run_id: str, started_at: datetime, finished_at: datetime) -> dict[str, Any]`
- [_build_service_summary](../../execution_engine/protection_watcher.py) — ligne 85 : `def _build_service_summary(metrics: dict[str, Any], *, service_run_id: str, started_at: datetime, finished_at: datetime | None, exec_run_id: str | None, account_id: str | None, limit: int) -> dict[str, Any]`
- [ProtectionTransitionWatcher](../../execution_engine/protection_watcher.py) — ligne 143 : `class ProtectionTransitionWatcher`
- [ProtectionTransitionWatcher.__init__](../../execution_engine/protection_watcher.py) — ligne 146 : `def __init__(self, repo: ExecutionRepository, broker_factory: Callable[[str, str | None], ExecutionBrokerPort], config_factory: Callable[[str, str | None], ExecutionConfig], *, default_broker_mode: str='paper') -> None`
- [ProtectionTransitionWatcher.run](../../execution_engine/protection_watcher.py) — ligne 161 : `def run(self, *, exec_run_id: str | None=None, account_id: str | None=None, limit: int=100) -> list[dict[str, Any]]`
- [ProtectionTransitionWatcher._load_watch_inputs](../../execution_engine/protection_watcher.py) — ligne 361 : `def _load_watch_inputs(self, *, exec_run_id: str | None, account_id: str | None, limit: int) -> tuple[list[ProtectionWatchItem], list[dict[str, Any]], list[dict[str, Any]]]`
- [ProtectionTransitionWatcher._resolve_refresh_context](../../execution_engine/protection_watcher.py) — ligne 392 : `def _resolve_refresh_context(self, *, exec_run_id: str | None, account_id: str | None) -> tuple[str, str] | None`
- [ProtectionTransitionWatcher._refresh_broker_state_if_needed](../../execution_engine/protection_watcher.py) — ligne 413 : `def _refresh_broker_state_if_needed(self, *, exec_run_id: str | None, account_id: str | None, limit: int) -> dict[str, Any] | None`
- [ProtectionTransitionWatcher._config_for](../../execution_engine/protection_watcher.py) — ligne 451 : `def _config_for(self, broker_mode: str, account_id: str | None) -> ExecutionConfig`
- [ProtectionTransitionWatcher._gpt_profile](../../execution_engine/protection_watcher.py) — ligne 457 : `def _gpt_profile(self, risk_run_id, symbol, account_id, broker_mode)`
- [ProtectionTransitionWatcher._broker_for](../../execution_engine/protection_watcher.py) — ligne 464 : `def _broker_for(self, broker_mode: str, account_id: str | None) -> ExecutionBrokerPort`
- [ProtectionTransitionWatcher._persist_event](../../execution_engine/protection_watcher.py) — ligne 470 : `def _persist_event(self, event) -> None`
- [ProtectionTransitionWatcher._persist_order_state](../../execution_engine/protection_watcher.py) — ligne 478 : `def _persist_order_state(self, intent: OrderIntent, order: BrokerOrder, *, account_id: str | None=None) -> None`
- [ProtectionTransitionWatcher._persist_order_request_failure](../../execution_engine/protection_watcher.py) — ligne 498 : `def _persist_order_request_failure(self, intent: OrderIntent, exc: Exception, *, account_id: str | None=None) -> None`
- [ProtectionTransitionWatcher._coerce_trade_date](../../execution_engine/protection_watcher.py) — ligne 511 : `def _coerce_trade_date(value: Any) -> date | None`
- [ProtectionTransitionWatcher._is_protection_rejection_likely_due_to_open_exit](../../execution_engine/protection_watcher.py) — ligne 524 : `def _is_protection_rejection_likely_due_to_open_exit(exc: Exception) -> bool`
- [ProtectionTransitionWatcher._is_unprocessable_protection_error](../../execution_engine/protection_watcher.py) — ligne 529 : `def _is_unprocessable_protection_error(exc: Exception) -> bool`
- [ProtectionTransitionWatcher._get_error_message](../../execution_engine/protection_watcher.py) — ligne 538 : `def _get_error_message(exc: Exception) -> str`
- [ProtectionTransitionWatcher._reconcile_position_closed](../../execution_engine/protection_watcher.py) — ligne 548 : `def _reconcile_position_closed(self, parent_intent: OrderIntent, broker: ExecutionBrokerPort, *, broker_mode: str, account_id: str, exec_run_id: str, symbol: str) -> bool`
- [ProtectionTransitionWatcher._build_existing_child_intent](../../execution_engine/protection_watcher.py) — ligne 662 : `def _build_existing_child_intent(parent: OrderIntent, child_order: BrokerOrder, role: str) -> OrderIntent`
- [ProtectionTransitionWatcher._cancel_existing_protection_children](../../execution_engine/protection_watcher.py) — ligne 690 : `def _cancel_existing_protection_children(self, parent_intent: OrderIntent, broker: ExecutionBrokerPort, *, account_id: str | None, leg: str) -> int`
- [ProtectionTransitionWatcher._cancel_existing_take_profit_children](../../execution_engine/protection_watcher.py) — ligne 753 : `def _cancel_existing_take_profit_children(self, parent_intent: OrderIntent, broker: ExecutionBrokerPort, *, account_id: str | None) -> int`
- [ProtectionTransitionWatcher._build_parent_intent](../../execution_engine/protection_watcher.py) — ligne 765 : `def _build_parent_intent(item: ProtectionWatchItem, stop_order: BrokerOrder) -> OrderIntent`
- [ProtectionTransitionWatcher._build_existing_stop_intent](../../execution_engine/protection_watcher.py) — ligne 785 : `def _build_existing_stop_intent(item: ProtectionWatchItem, stop_order: BrokerOrder) -> OrderIntent`
- [ProtectionTransitionWatcher._cancel_initial_stop](../../execution_engine/protection_watcher.py) — ligne 805 : `def _cancel_initial_stop(self, broker: ExecutionBrokerPort, config: ExecutionConfig, item: ProtectionWatchItem, stop_order: BrokerOrder) -> tuple[bool, BrokerOrder]`
- [ProtectionTransitionWatcher._arm_missing_protections](../../execution_engine/protection_watcher.py) — ligne 826 : `def _arm_missing_protections(self, row: dict[str, Any], metrics: dict[str, Any], *, use_manual_buy_stop: bool=False) -> None`
- [ProtectionTransitionWatcher._compute_business_days_held](../../execution_engine/protection_watcher.py) — ligne 1259 : `def _compute_business_days_held(opened_at: datetime, as_of: date) -> int`
- [ProtectionTransitionWatcher._arm_gpt_stop](../../execution_engine/protection_watcher.py) — ligne 1266 : `def _arm_gpt_stop(self, row, metrics, profile, config, broker)`
- [ProtectionTransitionWatcher._resolve_time_stop_take_profit_price](../../execution_engine/protection_watcher.py) — ligne 1314 : `def _resolve_time_stop_take_profit_price(self, *, entry_price: float, risk_per_share: float | None, open_children: list[BrokerOrder], config: ExecutionConfig) -> float`
- [ProtectionTransitionWatcher._apply_time_stop_exits](../../execution_engine/protection_watcher.py) — ligne 1334 : `def _apply_time_stop_exits(self, metrics: dict[str, Any]) -> None`
- [ProtectionTransitionWatcher._process_item](../../execution_engine/protection_watcher.py) — ligne 1479 : `def _process_item(self, item: ProtectionWatchItem, metrics: dict[str, Any]) -> None`
- [ProtectionWatcherService](../../execution_engine/protection_watcher.py) — ligne 1696 : `class ProtectionWatcherService`
- [ProtectionWatcherService.__init__](../../execution_engine/protection_watcher.py) — ligne 1699 : `def __init__(self, watcher: ProtectionTransitionWatcher, service_config: ProtectionWatcherServiceConfig, *, sleep_fn: Callable[[float], None]=time.sleep, monotonic_fn: Callable[[], float]=time.monotonic) -> None`
- [ProtectionWatcherService.run](../../execution_engine/protection_watcher.py) — ligne 1712 : `def run(self, *, exec_run_id: str | None=None, account_id: str | None=None, limit: int=100) -> dict[str, Any]`
- [ProtectionWatcherService._aggregate_cycle_summaries](../../execution_engine/protection_watcher.py) — ligne 1934 : `def _aggregate_cycle_summaries(summaries: list[dict[str, Any]]) -> dict[str, int]`
- [ProtectionWatcherService._maybe_log_heartbeat](../../execution_engine/protection_watcher.py) — ligne 1958 : `def _maybe_log_heartbeat(self, metrics: dict[str, Any], *, account_id: str | None, exec_run_id: str | None, service_run_id: str, leader_lock_account: str, leader_ttl_seconds: int, last_heartbeat: float) -> tuple[bool, float]`
- [ProtectionWatcherService._persist_service_summary](../../execution_engine/protection_watcher.py) — ligne 2015 : `def _persist_service_summary(self, *, service_run_id: str, metrics: dict[str, Any], started_at: datetime, finished_at: datetime | None, exec_run_id: str | None, account_id: str | None, limit: int) -> None`
- [parse_args](../../execution_engine/protection_watcher.py) — ligne 2055 : `def parse_args(argv: list[str] | None=None) -> argparse.Namespace`
- [main](../../execution_engine/protection_watcher.py) — ligne 2088 : `def main(argv: list[str] | None=None) -> None`

## `execution_engine/reconcile_statement.py`

Source SHA-256 : `cefa00223bdd5721070a477f36497ccaf9b7d63c4c6ce84ebfb13ea0a5b12aae`

- [_parse_trade_date](../../execution_engine/reconcile_statement.py) — ligne 32 : `def _parse_trade_date(raw_value: str | None) -> date`
- [_load_statement_activities](../../execution_engine/reconcile_statement.py) — ligne 38 : `def _load_statement_activities(*, statement_path: str | None, trade_date: date, account_id: str, broker_mode: str, no_fetch: bool) -> tuple[list[dict[str, Any]], str, bool]`
- [run_reconciliation_job](../../execution_engine/reconcile_statement.py) — ligne 68 : `def run_reconciliation_job(*, account_id: str, trade_date: date, broker_mode: str='paper', statement_path: str | None=None, no_fetch: bool=False, report_out: Path | None=None) -> dict[str, Any]`
- [build_arg_parser](../../execution_engine/reconcile_statement.py) — ligne 119 : `def build_arg_parser() -> argparse.ArgumentParser`
- [main](../../execution_engine/reconcile_statement.py) — ligne 130 : `def main(argv: list[str] | None=None) -> int`

## `execution_engine/reconciliation.py`

Source SHA-256 : `9b938a248b56096a17f27d311036923ea12e21f7aab2973baffb2e02045aae5b`

- [_symbol_key](../../execution_engine/reconciliation.py) — ligne 16 : `def _symbol_key(raw_symbol: str | None) -> str`
- [_qty](../../execution_engine/reconciliation.py) — ligne 20 : `def _qty(value: Any) -> float`
- [_effective_tolerance](../../execution_engine/reconciliation.py) — ligne 24 : `def _effective_tolerance(tolerance: float | int) -> float`
- [reconcile_execution_state](../../execution_engine/reconciliation.py) — ligne 28 : `def reconcile_execution_state(*, exec_run_id: str, account_id: str, targets: list[ExecutionTarget], broker_positions: list[dict[str, Any]], internal_positions: list[ExecutionPosition], open_order_state: list[dict[str, Any]] | None=None, protection_state: list[dict[str, Any]] | None=None, tolerance: float=0.0, buying_power_available: float | None=None) -> list[ExecutionReconciliationResult]`
- [reconcile_targets_vs_broker](../../execution_engine/reconciliation.py) — ligne 148 : `def reconcile_targets_vs_broker(targets: list[ExecutionTarget], broker_positions: list[dict], tolerance: float=0.0) -> list[ReconcileDiff]`

## `execution_engine/state_machine.py`

Source SHA-256 : `a5f259b03d04d87de5782de886d6cb702ecc8bdeef9651220cba7162a0d809e7`

- [is_terminal](../../execution_engine/state_machine.py) — ligne 42 : `def is_terminal(status: str) -> bool`
- [can_transition](../../execution_engine/state_machine.py) — ligne 46 : `def can_transition(old: str, new: str) -> bool`
- [require_transition](../../execution_engine/state_machine.py) — ligne 55 : `def require_transition(old: str, new: str) -> None`
- [map_alpaca_status](../../execution_engine/state_machine.py) — ligne 60 : `def map_alpaca_status(alpaca_status: str) -> str`
- [ExecutionPhase](../../execution_engine/state_machine.py) — ligne 69 : `class ExecutionPhase`
- [_terminal_phases](../../execution_engine/state_machine.py) — ligne 99 : `def _terminal_phases() -> frozenset[str]`
- [can_transition_phase](../../execution_engine/state_machine.py) — ligne 170 : `def can_transition_phase(old: str, new: str) -> bool`
- [require_transition_phase](../../execution_engine/state_machine.py) — ligne 181 : `def require_transition_phase(old: str, new: str, *, strict: bool=False) -> None`
- [PhaseTracker](../../execution_engine/state_machine.py) — ligne 198 : `class PhaseTracker`
- [PhaseTracker.transition](../../execution_engine/state_machine.py) — ligne 209 : `def transition(self, new_phase: str) -> None`
- [PhaseTracker.force](../../execution_engine/state_machine.py) — ligne 214 : `def force(self, new_phase: str) -> None`
- [PhaseTracker.last_phase](../../execution_engine/state_machine.py) — ligne 220 : `def last_phase(self) -> str`

## `execution_engine/tca.py`

Source SHA-256 : `5be910adcc24eb259441c56d3eaf4b705d513d718282caa42f0c86f87cc1d71c`

- [_series_or_default](../../execution_engine/tca.py) — ligne 9 : `def _series_or_default(df: pd.DataFrame, column: str, default: float | str=0.0) -> pd.Series`
- [compute_slippage_bps](../../execution_engine/tca.py) — ligne 15 : `def compute_slippage_bps(fill_price: float, decision_price: float) -> float`
- [compute_implementation_shortfall](../../execution_engine/tca.py) — ligne 21 : `def compute_implementation_shortfall(fill_price: float, decision_price: float, qty: float) -> float`
- [bucket_slippage_bps](../../execution_engine/tca.py) — ligne 25 : `def bucket_slippage_bps(slippage_bps: float | int | None) -> str`
- [build_tca_aggregate_frame](../../execution_engine/tca.py) — ligne 36 : `def build_tca_aggregate_frame(fills_df: pd.DataFrame, *, group_by: tuple[str, ...]) -> pd.DataFrame`
- [build_tca_summary](../../execution_engine/tca.py) — ligne 91 : `def build_tca_summary(fills: list[ExecutionFill], max_slippage_bps: int) -> TcaSummary`
