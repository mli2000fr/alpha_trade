# Inventaire API — execution_engine

Cet inventaire est dérivé des signatures présentes dans le code. Les symboles préfixés par `_` restent internes. Les numéros de ligne sont indicatifs ; le chemin et le nom du symbole sont les repères stables.

## `execution_engine/__main__.py`

- ligne 10 — `def _should_warn_deprecated_run_path(argv: list[str]) -> bool:`
## `execution_engine/account_state.py`

- ligne 100 — `def _resolve_snapshot_buying_power(`
- ligne 114 — `def _log_leverage_decision(`
- ligne 139 — `def _resolve_margin_buying_power(`
- ligne 239 — `def build_account_constraint_state(`
- ligne 25 — `class InvalidBrokerSnapshotError(RuntimeError):`
- ligne 338 — `def reserve_account_capacity_for_intent(`
- ligne 37 — `class _AccountConstraintState:`
- ligne 388 — `def should_defer_children(`
- ligne 55 — `class _ResolvedLeverageBudget:`
- ligne 67 — `def safe_float(value: object, *, default: float = 0.0) -> float:`
- ligne 74 — `def estimate_intent_notional(intent: OrderIntent) -> float:`
- ligne 79 — `def _resolve_leverage_activation(`
## `execution_engine/audit.py`

- ligne 108 — `def event_to_db_dict(event: ExecutionEvent) -> dict[str, Any]:`
- ligne 122 — `def build_execution_run_summary(`
- ligne 18 — `def build_run_id() -> str:`
- ligne 22 — `def make_event(`
- ligne 45 — `def order_intent_to_db_dict(intent: OrderIntent, exec_run_id: str, status: str = OrderStatus.NEW) -> dict[str, Any]:`
- ligne 72 — `def broker_order_to_db_dict(order: BrokerOrder, exec_run_id: str) -> dict[str, Any]:`
- ligne 92 — `def fill_to_db_dict(fill: ExecutionFill, exec_run_id: str) -> dict[str, Any]:`
## `execution_engine/broker_adapter.py`

- ligne 20 — `class CancelResult:`
- ligne 29 — `class BrokerAdapter:`
## `execution_engine/broker_state_sync.py`

- ligne 19 — `class BrokerStateSynchronizer:`
## `execution_engine/cash_ledger_guard.py`

- ligne 129 — `def check_cash_ledger_from_broker_snapshot(`
- ligne 19 — `def check_cash_ledger_consistency(`
## `execution_engine/children_submission.py`

- ligne 218 — `def submit_rebalance_orders(`
- ligne 45 — `def submit_children(`
## `execution_engine/cli.py`

- ligne 101 — `def build_arg_parser() -> argparse.ArgumentParser:`
- ligne 115 — `def parse_args(argv: list[str] | None = None) -> argparse.Namespace:`
- ligne 164 — `def main(argv: list[str] | None = None) -> None:`
- ligne 185 — `def _apply_feature_flags(args: argparse.Namespace) -> None:`
- ligne 199 — `def _resolve_canonical_mode(args: argparse.Namespace) -> str:`
- ligne 206 — `def _run_execution(args: argparse.Namespace) -> None:`
- ligne 268 — `def _run_cancel_all(args: argparse.Namespace) -> None:`
- ligne 33 — `def _add_run_arguments(p: argparse.ArgumentParser) -> None:`
- ligne 76 — `def _add_cancel_all_arguments(p: argparse.ArgumentParser) -> None:`
## `execution_engine/config.py`

- ligne 108 — `def load_trailing_stop_config_from_yaml(raw_config: Mapping[str, Any] | None = None) -> TrailingStopConfig:`
- ligne 130 — `def load_time_stop_config_from_yaml(raw_config: Mapping[str, Any] | None = None) -> TimeStopConfig:`
- ligne 144 — `def load_leverage_config_from_yaml(raw_config: Mapping[str, Any] | None = None) -> LeverageConfig:`
- ligne 15 — `class TrailingStopConfig:`
- ligne 175 — `class ExecutionConfig:`
- ligne 431 — `class ProtectionWatcherServiceConfig:`
- ligne 46 — `class TimeStopConfig:`
- ligne 64 — `class LeverageConfig:`
## `execution_engine/db_io.py`

- ligne 31 — `class ExecutionRepository:`
## `execution_engine/executor_phases.py`

- ligne 101 — `def phase_init_and_preflight(executor: Any, ctx: PhaseContext) -> PhaseOutcome:`
- ligne 127 — `def phase_build_and_submit(executor: Any, ctx: PhaseContext) -> PhaseOutcome:`
- ligne 142 — `def phase_poll_and_children(executor: Any, ctx: PhaseContext) -> PhaseOutcome:`
- ligne 157 — `def phase_reconcile_and_finalize(executor: Any, ctx: PhaseContext) -> PhaseOutcome:`
- ligne 179 — `def run_phases(executor: Any, ctx: PhaseContext) -> dict[str, Any]:`
- ligne 41 — `def is_phases_orchestrator_enabled() -> bool:`
- ligne 46 — `class PhaseStatus(str, Enum):`
- ligne 53 — `class PhaseOutcome:`
- ligne 64 — `class PhaseContext:`
## `execution_engine/executor.py`

- ligne 79 — `class ProductionExecutor:`
## `execution_engine/market_regime_preflight.py`

- ligne 16 — `def render_text_summary(snapshot_dict: dict[str, Any]) -> str:`
- ligne 41 — `def emit_preflight(snapshot_dict: dict[str, Any], *, also_log: bool = True) -> str:`
- ligne 50 — `def derive_entry_mode(snapshot_dict: dict[str, Any]) -> str:`
## `execution_engine/models.py`

- ligne 12 — `class OrderStatus:`
- ligne 132 — `class OrderIntent:`
- ligne 155 — `class ExecutionOrderRequest:`
- ligne 179 — `class BrokerOrder:`
- ligne 199 — `class ExecutionFill:`
- ligne 214 — `class BrokerOrderObservation:`
- ligne 239 — `class BrokerAccountSnapshot:`
- ligne 255 — `class ExecutionPosition:`
- ligne 26 — `class EventType:`
- ligne 272 — `class ExecutionPositionLot:`
- ligne 294 — `class ExecutionReconciliationResult:`
- ligne 316 — `class ExecutionEvent:`
- ligne 330 — `class ReconcileDiff:`
- ligne 340 — `class TcaSummary:`
- ligne 352 — `class ProtectionWatchItem:`
- ligne 70 — `class ReconciliationStatus:`
- ligne 76 — `class IntentRole:`
- ligne 94 — `class ExecutionTarget:`
## `execution_engine/oco_manager.py`

- ligne 14 — `class OcoManager:`
## `execution_engine/order_intents.py`

- ligne 101 — `def build_entry_intents(`
- ligne 16 — `def _make_id() -> str:`
- ligne 167 — `def apply_live_leverage_to_targets(`
- ligne 20 — `def _idempotency_key(run_id: str, symbol: str, role: str, side: str, qty: float, broker_mode: str) -> str:`
- ligne 26 — `def _submission_key(exec_run_id: str, symbol: str, role: str, side: str, qty: float, unique_id: str | None = None) -> str:`
- ligne 300 — `def _target_priority_key(target: ExecutionTarget) -> tuple[int, int, str]:`
- ligne 310 — `def _normalized_target_side(target: ExecutionTarget) -> str:`
- ligne 314 — `def filter_targets_by_live_regime_guards(`
- ligne 40 — `def _alpaca_client_order_id(exec_run_id: str, symbol: str, role: str, side: str, qty: float) -> str:`
- ligne 44 — `def resolve_initial_stop_price(`
- ligne 472 — `def split_entry_intents_by_gap_filter(`
- ligne 516 — `def build_take_profit_intent(`
- ligne 583 — `def build_initial_stop_intent(`
- ligne 641 — `def build_manual_buy_initial_stop_intent(`
- ligne 709 — `def build_trailing_stop_intent(`
- ligne 76 — `def resolve_trailing_activation_price(`
- ligne 778 — `def build_rebalance_sell_intent(`
- ligne 809 — `def build_rebalance_buy_intent(`
- ligne 840 — `def _resolve_alpaca_time_in_force(intent: OrderIntent, config: ExecutionConfig | None = None) -> str:`
- ligne 848 — `def intent_to_alpaca_payload(intent: OrderIntent, config: ExecutionConfig | None = None) -> dict[str, str]:`
- ligne 874 — `def build_oco_protection_payload(`
## `execution_engine/orphan_adoption.py`

- ligne 132 — `def _build_broker_order_from_payload(`
- ligne 177 — `def _persist_event(repo: ExecutionRepository, event) -> None:`
- ligne 184 — `def _normalize_status(raw_status: str | None) -> str:`
- ligne 202 — `def adopt_orphan_sell(`
- ligne 312 — `def adopt_orphan_buy(`
- ligne 49 — `class AdoptionResult:`
- ligne 57 — `def _stable_id(seed: str, length: int = 16) -> str:`
- ligne 61 — `def _ensure_adoption_run(`
- ligne 97 — `def _build_synthetic_intent(`
## `execution_engine/preflight.py`

- ligne 106 — `def check_no_global_kill_switch_active(ctx: PreflightContext) -> CheckResult:`
- ligne 139 — `def check_recent_dry_run(ctx: PreflightContext) -> CheckResult:`
- ligne 179 — `def check_alpaca_credentials(ctx: PreflightContext) -> CheckResult:`
- ligne 229 — `def check_ml_drift_gate(ctx: PreflightContext) -> CheckResult:`
- ligne 276 — `def check_no_literal_secrets(ctx: PreflightContext) -> CheckResult:`
- ligne 294 — `def check_no_pipeline_lock_held(ctx: PreflightContext) -> CheckResult:`
- ligne 314 — `def check_live_secret_policy(ctx: PreflightContext) -> CheckResult:`
- ligne 359 — `def run_preflight(`
- ligne 408 — `def _build_parser() -> argparse.ArgumentParser:`
- ligne 425 — `def main(argv: list[str] | None = None) -> int:`
- ligne 47 — `class CheckResult:`
- ligne 59 — `class PreflightContext:`
- ligne 72 — `class PreflightReport:`
## `execution_engine/protection_break_even.py`

- ligne 23 — `def should_promote_to_break_even(`
- ligne 41 — `def compute_break_even_stop_price(avg_fill_price: float) -> float:`
- ligne 46 — `def _parse_hhmm(s: str) -> time:`
- ligne 53 — `def is_eod_review_window(`
## `execution_engine/protection_state_bridge.py`

- ligne 118 — `def verify_fill_protection_consistency(`
- ligne 31 — `def build_protection_state_from_fill(`
- ligne 91 — `def persist_protection_state(`
## `execution_engine/protection_transition.py`

- ligne 27 — `def maybe_activate_dynamic_trailing(`
## `execution_engine/protection_watcher.py`

- ligne 141 — `class ProtectionTransitionWatcher:`
- ligne 1529 — `class ProtectionWatcherService:`
- ligne 1888 — `def parse_args(argv: list[str] | None = None) -> argparse.Namespace:`
- ligne 1921 — `def main(argv: list[str] | None = None) -> None:`
- ligne 45 — `def _build_summary(`
- ligne 83 — `def _build_service_summary(`
## `execution_engine/reconcile_statement.py`

- ligne 119 — `def build_arg_parser() -> argparse.ArgumentParser:`
- ligne 130 — `def main(argv: list[str] | None = None) -> int:`
- ligne 32 — `def _parse_trade_date(raw_value: str | None) -> date:`
- ligne 38 — `def _load_statement_activities(`
- ligne 68 — `def run_reconciliation_job(`
## `execution_engine/reconciliation.py`

- ligne 148 — `def reconcile_targets_vs_broker(`
- ligne 16 — `def _symbol_key(raw_symbol: str | None) -> str:`
- ligne 20 — `def _qty(value: Any) -> float:`
- ligne 24 — `def _effective_tolerance(tolerance: float | int) -> float:`
- ligne 28 — `def reconcile_execution_state(`
## `execution_engine/state_machine.py`

- ligne 170 — `def can_transition_phase(old: str, new: str) -> bool:`
- ligne 181 — `def require_transition_phase(old: str, new: str, *, strict: bool = False) -> None:`
- ligne 198 — `class PhaseTracker:`
- ligne 42 — `def is_terminal(status: str) -> bool:`
- ligne 46 — `def can_transition(old: str, new: str) -> bool:`
- ligne 55 — `def require_transition(old: str, new: str) -> None:`
- ligne 60 — `def map_alpaca_status(alpaca_status: str) -> str:`
- ligne 69 — `class ExecutionPhase:`
- ligne 99 — `def _terminal_phases() -> frozenset[str]:`
## `execution_engine/tca.py`

- ligne 15 — `def compute_slippage_bps(fill_price: float, decision_price: float) -> float:`
- ligne 21 — `def compute_implementation_shortfall(fill_price: float, decision_price: float, qty: float) -> float:`
- ligne 25 — `def bucket_slippage_bps(slippage_bps: float | int | None) -> str:`
- ligne 36 — `def build_tca_aggregate_frame(`
- ligne 9 — `def _series_or_default(df: pd.DataFrame, column: str, default: float | str = 0.0) -> pd.Series:`
- ligne 91 — `def build_tca_summary(fills: list[ExecutionFill], max_slippage_bps: int) -> TcaSummary:`

