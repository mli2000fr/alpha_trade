# Inventaire API — entrypoints

Extraction AST du 2026-10-10 ; aucune importation ni exécution métier.

Classes, fonctions de module et méthodes déclarées ; fonctions imbriquées exclues.
Les symboles `_...` sont internes. Signature présente ≠ API publique stable.

## `analyze_trades.py`

Source SHA-256 : `b9da82e02ea9299dc8a9621f82cb16613460273c35805e4adb56164adea40bbf`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `check_coverage.py`

Source SHA-256 : `9d9d3d4ab28858366b7550c1218a8535826761c655d0413c57cc60912716d894`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `run.py`

Source SHA-256 : `bd6bf22ef4e060b867d56d0482e49ec5250db36ab48296aeeda3c26a686b48fe`

- [_streamlit_is_available](../../run.py) — ligne 13 : `def _streamlit_is_available() -> bool`

## `run_execution.py`

Source SHA-256 : `c3696730b8079471146bd4f5419797627151a31c0495cca17ac1e2887bde6d36`

- [check_env](../../run_execution.py) — ligne 76 : `def check_env(account_id: str | None=None, mode: str | None=None) -> list[str]`
- [print_env_status](../../run_execution.py) — ligne 132 : `def print_env_status() -> bool`
- [abort_missing_env](../../run_execution.py) — ligne 154 : `def abort_missing_env(account_id: str | None=None, mode: str | None=None) -> None`
- [interactive_menu](../../run_execution.py) — ligne 180 : `def interactive_menu() -> tuple[object, ...]`
- [resolve_mode_from_broker_mode](../../run_execution.py) — ligne 380 : `def resolve_mode_from_broker_mode(*, broker_mode: str, dry_run: bool) -> str`
- [_build_execution_run_plan](../../run_execution.py) — ligne 385 : `def _build_execution_run_plan(*, mode: str, run_id: str | None, trade_date: str | None, account_id: str | None, preset: dict) -> dict[str, object]`
- [_fingerprint_execution_run_plan](../../run_execution.py) — ligne 403 : `def _fingerprint_execution_run_plan(plan: dict[str, object]) -> str`
- [_resolve_run_plan_path](../../run_execution.py) — ligne 408 : `def _resolve_run_plan_path(account_id: str | None, run_plan_file: str | None) -> Path`
- [_validate_live_approval_token](../../run_execution.py) — ligne 415 : `def _validate_live_approval_token(approval_token: str | None) -> str`
- [_validate_live_secret_policy](../../run_execution.py) — ligne 429 : `def _validate_live_secret_policy() -> None`
- [_ensure_immutable_run_plan](../../run_execution.py) — ligne 437 : `def _ensure_immutable_run_plan(*, mode: str, run_id: str | None, trade_date: str | None, account_id: str | None, preset: dict, approval_token: str, run_plan_file: str | None) -> tuple[Path, str]`
- [_build_runtime_preset](../../run_execution.py) — ligne 483 : `def _build_runtime_preset(mode: str, *, allow_fractional_shares: bool=False, allow_outside_rth: bool=False, auto_rebalance: bool=False, account_type: str='cash', swing_only: bool=True, submission_window: str | None=None, take_profit_pct: float | None=None, trailing_stop_pct: float | None=None, max_entry_gap_pct: float | None=None, trailing_activation_trigger: str | None=None, trailing_activation_r_multiple: float | None=None, trailing_activation_profit_pct: float | None=None, protection_transition_timeout_seconds: int | None=None, protection_transition_poll_interval_seconds: float | None=None, entry_order_type: str | None=None, limit_price_buffer_bps: int | None=None, max_order_retries: int | None=None, poll_interval_seconds: float | None=None, fill_timeout_seconds: int | None=None, cancel_timeout_seconds: int | None=None, max_slippage_bps: int | None=None, execution_batch_size: int | None=None, inter_order_delay_ms: int | None=None) -> dict`
- [_launch_post_watcher](../../run_execution.py) — ligne 556 : `def _launch_post_watcher(*, summary: dict, preset: dict, account_id: str | None, broker_mode: str) -> int`
- [_persist_market_macro_snapshot](../../run_execution.py) — ligne 598 : `def _persist_market_macro_snapshot(*, trade_date: date, macro_payload: object) -> int`
- [_load_pre_submission_spreads](../../run_execution.py) — ligne 607 : `def _load_pre_submission_spreads(symbols: list[str], *, account_id: str) -> dict[str, object]`
- [_load_pre_submission_borrows](../../run_execution.py) — ligne 653 : `def _load_pre_submission_borrows(symbols: list[str], *, account_id: str, trade_date: date) -> dict[str, object]`
- [_load_pre_submission_adv_vol](../../run_execution.py) — ligne 711 : `def _load_pre_submission_adv_vol(symbols: list[str], *, trade_date: date) -> tuple[dict[str, float], dict[str, float]]`
- [_resolve_pre_submission_symbols](../../run_execution.py) — ligne 741 : `def _resolve_pre_submission_symbols(repo: object, *, risk_run_id: str | None, trade_date: date | None, account_id: str | None) -> list[str]`
- [_load_transition_plan](../../run_execution.py) — ligne 772 : `def _load_transition_plan(*, trade_date: date, risk_run_id: str) -> dict | None`
- [_execute_transition_plan](../../run_execution.py) — ligne 789 : `def _execute_transition_plan(plan: dict, *, broker: object, exec_run_id: str | None=None, dry_run: bool=False) -> dict[str, int]`
- [_load_decision_fingerprints](../../run_execution.py) — ligne 870 : `def _load_decision_fingerprints(*, trade_date: date, risk_run_id: str) -> dict[str, str]`
- [run](../../run_execution.py) — ligne 901 : `def run(mode: str, run_id: str | None, trade_date: str | None, debug: bool, allow_fractional_shares: bool=False, allow_outside_rth: bool=False, auto_rebalance: bool=False, account_id: str | None=None, account_type: str='cash', swing_only: bool=True, submission_window: str='both', auto_watcher: bool=False, skip_preflight: bool=False, take_profit_pct: float | None=None, trailing_stop_pct: float | None=None, max_entry_gap_pct: float | None=None, trailing_activation_trigger: str | None=None, trailing_activation_r_multiple: float | None=None, trailing_activation_profit_pct: float | None=None, protection_transition_timeout_seconds: int | None=None, protection_transition_poll_interval_seconds: float | None=None, entry_order_type: str | None=None, limit_price_buffer_bps: int | None=None, max_order_retries: int | None=None, poll_interval_seconds: float | None=None, fill_timeout_seconds: int | None=None, cancel_timeout_seconds: int | None=None, max_slippage_bps: int | None=None, execution_batch_size: int | None=None, inter_order_delay_ms: int | None=None, approval_token: str | None=None, run_plan_file: str | None=None, summary_path: str | None=None) -> dict[str, object]`
- [build_parser](../../run_execution.py) — ligne 1890 : `def build_parser() -> argparse.ArgumentParser`
- [_apply_feature_flags](../../run_execution.py) — ligne 1981 : `def _apply_feature_flags(args) -> None`
- [main](../../run_execution.py) — ligne 1997 : `def main() -> None`

## `run_execution_protection_watch.py`

Source SHA-256 : `f09b6b8a31af789e70869a2fcbe8604143895bea39848f5bd9f273b53c4be384`

Module sans déclaration publique/privée de classe ou fonction au niveau module.
