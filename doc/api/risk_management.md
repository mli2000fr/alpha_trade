# Inventaire API — risk_management

Extraction AST du 2026-10-10 ; aucune importation ni exécution métier.

Classes, fonctions de module et méthodes déclarées ; fonctions imbriquées exclues.
Les symboles `_...` sont internes. Signature présente ≠ API publique stable.

## `risk_management/__init__.py`

Source SHA-256 : `45d8846a9dc4bbd7e0ec245b53d7e5d61c5891fb3fb4ac8f2387a39f707269cc`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `risk_management/__main__.py`

Source SHA-256 : `17723a1daa9a90a2dbd1668d02128ff50b5a0c8d4ba23e160faa3e75ac5fa9d3`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `risk_management/abstention.py`

Source SHA-256 : `7c479ce561315c9e372765ed0dc59f29e3979ed2d1e1461ae73ad1da01e1d9b5`

- [AbstentionDecision](../../risk_management/abstention.py) — ligne 35 : `class AbstentionDecision`
- [AbstentionDecision.is_blocked](../../risk_management/abstention.py) — ligne 53 : `def is_blocked(self) -> bool`
- [AbstentionPolicy](../../risk_management/abstention.py) — ligne 60 : `class AbstentionPolicy`
- [AbstentionPolicy.evaluate](../../risk_management/abstention.py) — ligne 89 : `def evaluate(self, candidate: MLRankedCandidate, edge: DirectionalEdgeEstimate | None=None, *, as_of_date: date | None=None) -> AbstentionDecision`
- [AbstentionPolicy.sensible_defaults](../../risk_management/abstention.py) — ligne 197 : `def sensible_defaults(cls) -> AbstentionPolicy`
- [AbstentionPolicy.permissive](../../risk_management/abstention.py) — ligne 214 : `def permissive(cls) -> AbstentionPolicy`
- [AbstentionPolicy.strict](../../risk_management/abstention.py) — ligne 219 : `def strict(cls) -> AbstentionPolicy`
- [evaluate_abstention_veto](../../risk_management/abstention.py) — ligne 233 : `def evaluate_abstention_veto(candidate: MLRankedCandidate, edge: DirectionalEdgeEstimate | None, *, min_p_side: float=0.4, min_top2_margin: float=0.03, max_uncertainty: float=0.25, require_positive_edge: bool=True) -> AbstentionDecision`

## `risk_management/audit.py`

Source SHA-256 : `3e05dae6ec72bb73e54afe9f0c7361b47217cd7ddbac8fdb89c55df2498b1d05`

- [build_run_id](../../risk_management/audit.py) — ligne 26 : `def build_run_id() -> str`
- [persist_decision_audit_log](../../risk_management/audit.py) — ligne 31 : `def persist_decision_audit_log(entries: list[PortfolioEntry], *, run_id: str, trade_date: date, config_fingerprint: str, model_run_id: str, regime_mode: str, output_dir: Path=Path('artifacts/risk_decision_audit')) -> Path`
- [persist_decisions](../../risk_management/audit.py) — ligne 101 : `def persist_decisions(repo: RiskRepository, entries: list[PortfolioEntry], run_id: str, trade_date: date, account_id: str | None=None) -> int`
- [persist_portfolio_targets](../../risk_management/audit.py) — ligne 189 : `def persist_portfolio_targets(repo: RiskRepository, entries: list[PortfolioEntry], run_id: str, trade_date: date, account_id: str | None=None) -> int`

## `risk_management/batch_diagnostics.py`

Source SHA-256 : `cf09e5f171bef23dea03875307eb319cccf0663022b70ceeb5a8dda606510bce`

- [_classify_exclusion](../../risk_management/batch_diagnostics.py) — ligne 31 : `def _classify_exclusion(sym: str, side: str, filters: BatchFilters) -> str`
- [_load_filters](../../risk_management/batch_diagnostics.py) — ligne 83 : `def _load_filters(engine: Any) -> BatchFilters | None`
- [_resolve_prefer_set](../../risk_management/batch_diagnostics.py) — ligne 104 : `def _resolve_prefer_set(filters: BatchFilters, prefer_top_n: int) -> frozenset[str]`
- [boost_candidate_scores](../../risk_management/batch_diagnostics.py) — ligne 121 : `def boost_candidate_scores(candidates: list[Any], engine: Any, *, prefer_multiplier: float | None=None, prefer_top_n: int | None=None) -> tuple[int, str | None]`
- [apply_batch_diagnostics_to_entries](../../risk_management/batch_diagnostics.py) — ligne 219 : `def apply_batch_diagnostics_to_entries(entries: list[PortfolioEntry], engine: Any) -> tuple[list[PortfolioEntry], int, str | None]`

## `risk_management/campaign_orchestrator.py`

Source SHA-256 : `dc04d6f08d367a1c3dc3e5e0e0ffcd967693a7c6ce7bc1cb75f12149dd2d928d`

- [CampaignPhase](../../risk_management/campaign_orchestrator.py) — ligne 38 : `class CampaignPhase`
- [CampaignConfig](../../risk_management/campaign_orchestrator.py) — ligne 51 : `class CampaignConfig`
- [CampaignConfig.to_dict](../../risk_management/campaign_orchestrator.py) — ligne 103 : `def to_dict(self) -> dict[str, object]`
- [CampaignConfig.is_valid](../../risk_management/campaign_orchestrator.py) — ligne 125 : `def is_valid(self) -> bool`
- [CampaignConfig.weeks_elapsed](../../risk_management/campaign_orchestrator.py) — ligne 129 : `def weeks_elapsed(self) -> float`
- [CampaignConfig.min_weeks_required](../../risk_management/campaign_orchestrator.py) — ligne 133 : `def min_weeks_required(self) -> int`
- [CampaignConfig.can_promote](../../risk_management/campaign_orchestrator.py) — ligne 139 : `def can_promote(self) -> bool`
- [CampaignDayResult](../../risk_management/campaign_orchestrator.py) — ligne 146 : `class CampaignDayResult`
- [CampaignDayResult.to_dict](../../risk_management/campaign_orchestrator.py) — ligne 197 : `def to_dict(self) -> dict[str, object]`
- [WeeklyReview](../../risk_management/campaign_orchestrator.py) — ligne 231 : `class WeeklyReview`
- [WeeklyReview.to_dict](../../risk_management/campaign_orchestrator.py) — ligne 267 : `def to_dict(self) -> dict[str, object]`
- [CampaignOrchestrator](../../risk_management/campaign_orchestrator.py) — ligne 296 : `class CampaignOrchestrator`
- [CampaignOrchestrator.__post_init__](../../risk_management/campaign_orchestrator.py) — ligne 320 : `def __post_init__(self) -> None`
- [CampaignOrchestrator.campaign_dir](../../risk_management/campaign_orchestrator.py) — ligne 325 : `def campaign_dir(self) -> Path`
- [CampaignOrchestrator.daily_dir](../../risk_management/campaign_orchestrator.py) — ligne 329 : `def daily_dir(self) -> Path`
- [CampaignOrchestrator.weekly_dir](../../risk_management/campaign_orchestrator.py) — ligne 333 : `def weekly_dir(self) -> Path`
- [CampaignOrchestrator.ramp_up_state_path](../../risk_management/campaign_orchestrator.py) — ligne 337 : `def ramp_up_state_path(self) -> Path`
- [CampaignOrchestrator.effective_risk_budget](../../risk_management/campaign_orchestrator.py) — ligne 341 : `def effective_risk_budget(self) -> float`
- [CampaignOrchestrator.init_campaign](../../risk_management/campaign_orchestrator.py) — ligne 344 : `def init_campaign(self) -> None`
- [CampaignOrchestrator.validate_frozen_state](../../risk_management/campaign_orchestrator.py) — ligne 355 : `def validate_frozen_state(self) -> bool`
- [CampaignOrchestrator.run_daily_cycle](../../risk_management/campaign_orchestrator.py) — ligne 378 : `def run_daily_cycle(self, trade_date: date | None=None) -> CampaignDayResult`
- [CampaignOrchestrator._execute_risk_run](../../risk_management/campaign_orchestrator.py) — ligne 463 : `def _execute_risk_run(self, trade_date: date) -> dict[str, Any]`
- [CampaignOrchestrator._execute_paper_run](../../risk_management/campaign_orchestrator.py) — ligne 485 : `def _execute_paper_run(self, trade_date: date, risk_run_id: str) -> dict[str, Any]`
- [CampaignOrchestrator._run_shadow_compare](../../risk_management/campaign_orchestrator.py) — ligne 505 : `def _run_shadow_compare(self, trade_date: date) -> dict[str, Any] | None`
- [CampaignOrchestrator._run_configured_entrypoint](../../risk_management/campaign_orchestrator.py) — ligne 515 : `def _run_configured_entrypoint(self, *, kind: str, command: list[str], trade_date: date, day_dir: Path, risk_run_id: str | None) -> None`
- [CampaignOrchestrator._persist_day_result](../../risk_management/campaign_orchestrator.py) — ligne 564 : `def _persist_day_result(self, result: CampaignDayResult) -> None`
- [CampaignOrchestrator._reload_history](../../risk_management/campaign_orchestrator.py) — ligne 589 : `def _reload_history(self) -> None`
- [CampaignOrchestrator._load_ramp_up_state](../../risk_management/campaign_orchestrator.py) — ligne 604 : `def _load_ramp_up_state(self) -> Any`
- [CampaignOrchestrator._persist_ramp_up_state](../../risk_management/campaign_orchestrator.py) — ligne 625 : `def _persist_ramp_up_state(self) -> None`
- [CampaignOrchestrator._persist_runtime_parameters](../../risk_management/campaign_orchestrator.py) — ligne 634 : `def _persist_runtime_parameters(self, day_dir: Path) -> None`
- [CampaignOrchestrator._write_json_atomic](../../risk_management/campaign_orchestrator.py) — ligne 643 : `def _write_json_atomic(path: Path, value: dict[str, Any]) -> None`
- [CampaignOrchestrator.transition_ramp_up](../../risk_management/campaign_orchestrator.py) — ligne 649 : `def transition_ramp_up(self, *, reviewer: str, reason: str='') -> tuple[bool, str]`
- [CampaignOrchestrator._maybe_auto_rollback](../../risk_management/campaign_orchestrator.py) — ligne 683 : `def _maybe_auto_rollback(self, result: CampaignDayResult) -> None`
- [CampaignOrchestrator._compute_and_check_drawdown](../../risk_management/campaign_orchestrator.py) — ligne 749 : `def _compute_and_check_drawdown(self, result: CampaignDayResult) -> None`
- [CampaignOrchestrator._build_weekly_review](../../risk_management/campaign_orchestrator.py) — ligne 803 : `def _build_weekly_review(self) -> WeeklyReview`
- [CampaignOrchestrator.build_campaign_report](../../risk_management/campaign_orchestrator.py) — ligne 879 : `def build_campaign_report(self) -> dict[str, Any]`
- [CampaignOrchestrator._check_promotion_gates](../../risk_management/campaign_orchestrator.py) — ligne 903 : `def _check_promotion_gates(self) -> tuple[bool, list[str]]`
- [CampaignOrchestrator.save_campaign_report](../../risk_management/campaign_orchestrator.py) — ligne 951 : `def save_campaign_report(self) -> str`
- [create_campaign](../../risk_management/campaign_orchestrator.py) — ligne 961 : `def create_campaign(*, campaign_id: str, phase: str=CampaignPhase.SHADOW, model_run_id: str='', policy_version: int=1, config_fingerprint: str='', run_mode: str='shadow', dry_run: bool=True, approved_by: str | None=None, start_date: date | None=None, auto_promote: bool=False, base_risk_budget: float=0.0, risk_command: list[str] | None=None, execution_command: list[str] | None=None, signing_key_env: str='ALPHA_TRADE_CAMPAIGN_SIGNING_KEY', frozen_model_path: str='', frozen_calibrator_path: str='', frozen_config_path: str='') -> CampaignOrchestrator`

## `risk_management/capacity.py`

Source SHA-256 : `105ff6767236dbd8c198396e0a605508bb1dee7abc68ee68355ca71ef7e7d588`

- [CapacityEstimate](../../risk_management/capacity.py) — ligne 24 : `class CapacityEstimate`
- [CapacityEstimate.max_shares_at_price](../../risk_management/capacity.py) — ligne 62 : `def max_shares_at_price(self, price: float) -> int`
- [CapacityEstimate.to_dict](../../risk_management/capacity.py) — ligne 68 : `def to_dict(self) -> dict[str, object]`
- [CapacityEstimator](../../risk_management/capacity.py) — ligne 87 : `class CapacityEstimator`
- [CapacityEstimator.estimate_symbol](../../risk_management/capacity.py) — ligne 114 : `def estimate_symbol(self, symbol: str, *, adv_usd: float, spread_bps: float | None=None, price: float | None=None) -> CapacityEstimate`
- [CapacityEstimator.estimate_sector](../../risk_management/capacity.py) — ligne 207 : `def estimate_sector(self, sector: str, symbols: list[str], adv_map: dict[str, float], spread_map: dict[str, float] | None=None) -> CapacityEstimate`
- [CapacityEstimator.estimate_strategy](../../risk_management/capacity.py) — ligne 270 : `def estimate_strategy(self, strategy_name: str, symbol_capacities: list[CapacityEstimate], *, max_positions: int=20, correlation_factor: float=0.6) -> CapacityEstimate`
- [estimate_symbol_capacity](../../risk_management/capacity.py) — ligne 323 : `def estimate_symbol_capacity(symbol: str, adv_usd: float, *, spread_bps: float | None=None, price: float | None=None, max_participation_pct: float=0.01) -> CapacityEstimate`

## `risk_management/circuit_breaker.py`

Source SHA-256 : `c0a0f5d0edde3e796d091c4769d8ef94acf3cec5effc2f99723c5e96018235b2`

- [PnLSnapshot](../../risk_management/circuit_breaker.py) — ligne 24 : `class PnLSnapshot`
- [CircuitBreakerStatus](../../risk_management/circuit_breaker.py) — ligne 32 : `class CircuitBreakerStatus`
- [_try_send_alert](../../risk_management/circuit_breaker.py) — ligne 40 : `def _try_send_alert(event: str, payload: dict) -> None`
- [CircuitBreaker](../../risk_management/circuit_breaker.py) — ligne 69 : `class CircuitBreaker`
- [CircuitBreaker.__init__](../../risk_management/circuit_breaker.py) — ligne 86 : `def __init__(self, config: RiskConfig, pnl: PnLSnapshot | None=None) -> None`
- [CircuitBreaker.is_adaptive](../../risk_management/circuit_breaker.py) — ligne 105 : `def is_adaptive(self) -> bool`
- [CircuitBreaker._ensure_episode](../../risk_management/circuit_breaker.py) — ligne 109 : `def _ensure_episode(self) -> object`
- [CircuitBreaker.set_spy_regime](../../risk_management/circuit_breaker.py) — ligne 115 : `def set_spy_regime(self, trade_date) -> None`
- [CircuitBreaker.update_adaptive](../../risk_management/circuit_breaker.py) — ligne 126 : `def update_adaptive(self, equity: float, peak_equity: float) -> bool`
- [CircuitBreaker._reference_hwm](../../risk_management/circuit_breaker.py) — ligne 159 : `def _reference_hwm(self) -> float | None`
- [CircuitBreaker.allocation_scale](../../risk_management/circuit_breaker.py) — ligne 175 : `def allocation_scale(self, entry_mode: str | None=None, side: str | None=None) -> float`
- [CircuitBreaker.update_regime_streak](../../risk_management/circuit_breaker.py) — ligne 196 : `def update_regime_streak(self, entry_mode: str | None, current_equity: float=0.0) -> None`
- [CircuitBreaker.status](../../risk_management/circuit_breaker.py) — ligne 229 : `def status(self) -> CircuitBreakerStatus`
- [CircuitBreaker.is_active](../../risk_management/circuit_breaker.py) — ligne 239 : `def is_active(self) -> bool`
- [CircuitBreaker.just_tripped](../../risk_management/circuit_breaker.py) — ligne 272 : `def just_tripped(self) -> bool`
- [CircuitBreaker.notify_if_active](../../risk_management/circuit_breaker.py) — ligne 281 : `def notify_if_active(self) -> bool`
- [CircuitBreaker._evaluate_early_warning](../../risk_management/circuit_breaker.py) — ligne 320 : `def _evaluate_early_warning(self) -> dict[str, Any] | None`
- [CircuitBreaker._evaluate_drawdown](../../risk_management/circuit_breaker.py) — ligne 358 : `def _evaluate_drawdown(self) -> CircuitBreakerStatus`
- [CircuitBreaker._evaluate_daily_loss](../../risk_management/circuit_breaker.py) — ligne 378 : `def _evaluate_daily_loss(self) -> CircuitBreakerStatus`
- [_set_cb_prometheus](../../risk_management/circuit_breaker.py) — ligne 405 : `def _set_cb_prometheus(active: bool) -> None`

## `risk_management/cli.py`

Source SHA-256 : `daef565833a575cc86604530833d880796fc87e7b8ce5743b4c3a5cd203c0049`

- [RiskRunMode](../../risk_management/cli.py) — ligne 54 : `class RiskRunMode(StrEnum)`
- [_emit_live_progress](../../risk_management/cli.py) — ligne 62 : `def _emit_live_progress(summary: dict[str, object], *, current: int, total: int, label: str, phase: str, item: str | None=None, unit: str='étapes') -> None`
- [_resolve_market_regime_snapshot](../../risk_management/cli.py) — ligne 85 : `def _resolve_market_regime_snapshot(trade_date: date, effective_equity: float, repo: RiskRepository) -> object | None`
- [_serialize_market_regime_snapshot](../../risk_management/cli.py) — ligne 128 : `def _serialize_market_regime_snapshot(snapshot: object | None) -> dict[str, object] | None`
- [_evaluate_regime_transition](../../risk_management/cli.py) — ligne 142 : `def _evaluate_regime_transition(snapshot: object | None) -> object | None`
- [_load_live_spread_snapshots](../../risk_management/cli.py) — ligne 161 : `def _load_live_spread_snapshots(symbols: list[str], *, account_id: str) -> dict[str, object]`
- [_load_live_borrow_snapshots](../../risk_management/cli.py) — ligne 193 : `def _load_live_borrow_snapshots(symbols: list[str], *, account_id: str, trade_date: date) -> dict[str, object]`
- [_parse_quote_time](../../risk_management/cli.py) — ligne 308 : `def _parse_quote_time(value: object) -> datetime | None`
- [_wire_covariance_to_optimizer](../../risk_management/cli.py) — ligne 320 : `def _wire_covariance_to_optimizer(builder: object, *, factor_cov_live: object | None, operational_snapshot: object | None, directional_win_rates: dict[str | tuple[str, str], object], config: object) -> None`
- [_check_model_compatibility](../../risk_management/cli.py) — ligne 400 : `def _check_model_compatibility(predictions: dict[str, object], *, model_registry_path: str='artifacts/model_registry.json') -> dict[str, object]`
- [_optional_quote_float](../../risk_management/cli.py) — ligne 533 : `def _optional_quote_float(value: object) -> float | None`
- [_build_reconciliation_summary](../../risk_management/cli.py) — ligne 540 : `def _build_reconciliation_summary(*, trade_date: date, operational_snapshot: object | None, target_entries: list[object]) -> dict[str, object]`
- [_persist_transition_plan_artifact](../../risk_management/cli.py) — ligne 614 : `def _persist_transition_plan_artifact(transition_plan: object, *, trade_date: date, risk_run_id: str) -> str | None`
- [_build_preflight_data_quality](../../risk_management/cli.py) — ligne 648 : `def _build_preflight_data_quality(*, trade_date: date, account_snapshot: object | None, effective_equity: float, requested_equity: float, equity_breakdown: dict[str, object], selections: list[object], prices: dict[str, object] | None, return_matrix: object | None, regime_allow_new_entries: bool) -> dict[str, object]`
- [_entries_to_shadow_compare_frame](../../risk_management/cli.py) — ligne 787 : `def _entries_to_shadow_compare_frame(entries: list[PortfolioEntry]) -> pd.DataFrame`
- [_risk_decisions_to_shadow_compare_frame](../../risk_management/cli.py) — ligne 801 : `def _risk_decisions_to_shadow_compare_frame(decisions: pd.DataFrame) -> pd.DataFrame`
- [_build_conviction_weights_calibration](../../risk_management/cli.py) — ligne 819 : `def _build_conviction_weights_calibration(candidates: list[object], retained_entries: list[PortfolioEntry], empirical_risk_calibration: dict[str, object] | None=None) -> dict[str, object]`
- [_load_empirical_risk_calibration](../../risk_management/cli.py) — ligne 945 : `def _load_empirical_risk_calibration(repo: RiskRepository, *, trade_date: date, run_id: str | None, market_regime_mode: str | None, horizon_days: int | None, lookback_months: int | None, disabled: bool) -> dict[str, object] | None`
- [_apply_empirical_risk_calibration](../../risk_management/cli.py) — ligne 974 : `def _apply_empirical_risk_calibration(config: RiskConfig, calibration: dict[str, object] | None) -> RiskConfig`
- [_top_count_items](../../risk_management/cli.py) — ligne 1020 : `def _top_count_items(counts: dict[str, int], *, limit: int=5) -> list[dict[str, object]]`
- [_build_postmortem_artifacts](../../risk_management/cli.py) — ligne 1028 : `def _build_postmortem_artifacts(*, candidates: list[object], entries: list[PortfolioEntry], retained_entries: list[PortfolioEntry], rejection_reason_code_counts: dict[str, int], reduction_reason_code_counts: dict[str, int], prices: dict[str, object], predictions: dict[str, object], win_rates: dict[str, object], return_matrix: pd.DataFrame, regime_snapshot_payload: dict[str, object] | None, config: RiskConfig, regime_allow_new_entries: bool) -> dict[str, object]`
- [_run_shadow_compare](../../risk_management/cli.py) — ligne 1094 : `def _run_shadow_compare(*, enabled: bool, reference_run_id: str | None, trade_date: date, run_id: str, account_id: str | None, entries: list[PortfolioEntry], repo: RiskRepository, dry_run: bool) -> dict[str, object]`
- [build_arg_parser](../../risk_management/cli.py) — ligne 1172 : `def build_arg_parser() -> argparse.ArgumentParser`
- [_print_summary](../../risk_management/cli.py) — ligne 1319 : `def _print_summary(entries: list[PortfolioEntry], run_id: str, trade_date: date) -> None`
- [main](../../risk_management/cli.py) — ligne 1341 : `def main(args: list[str] | None=None) -> None`

## `risk_management/concentration.py`

Source SHA-256 : `964dabfa367b89e988ac81d99e6195bf27a367492efe0e5581ce3c482e4a83eb`

- [SymbolTradeTracker](../../risk_management/concentration.py) — ligne 48 : `class SymbolTradeTracker`
- [SymbolTradeTracker.__init__](../../risk_management/concentration.py) — ligne 59 : `def __init__(self, max_trades: int=DEFAULT_MAX_TRADES_PER_SYMBOL, window_days: int=DEFAULT_CONCENTRATION_WINDOW_CALENDAR_DAYS) -> None`
- [SymbolTradeTracker.max_trades](../../risk_management/concentration.py) — ligne 71 : `def max_trades(self) -> int`
- [SymbolTradeTracker.window_days](../../risk_management/concentration.py) — ligne 75 : `def window_days(self) -> int`
- [SymbolTradeTracker._prune](../../risk_management/concentration.py) — ligne 79 : `def _prune(self, symbol: str, as_of: date) -> None`
- [SymbolTradeTracker._count](../../risk_management/concentration.py) — ligne 87 : `def _count(self, symbol: str, as_of: date) -> int`
- [SymbolTradeTracker.allow_entry](../../risk_management/concentration.py) — ligne 93 : `def allow_entry(self, symbol: str, as_of: date, side: str | None=None) -> bool`
- [SymbolTradeTracker.record](../../risk_management/concentration.py) — ligne 110 : `def record(self, symbol: str, trade_date: date, side: str | None=None) -> None`
- [SymbolTradeTracker._make_key](../../risk_management/concentration.py) — ligne 131 : `def _make_key(symbol: str, side: str | None) -> str`
- [SymbolTradeTracker.reset](../../risk_management/concentration.py) — ligne 140 : `def reset(self) -> None`
- [SymbolTradeTracker.to_summary](../../risk_management/concentration.py) — ligne 144 : `def to_summary(self) -> dict[str, object]`
- [SymbolTradeTracker.to_dict](../../risk_management/concentration.py) — ligne 153 : `def to_dict(self) -> dict[str, object]`
- [SymbolTradeTracker.from_dict](../../risk_management/concentration.py) — ligne 165 : `def from_dict(cls, data: dict[str, object]) -> SymbolTradeTracker`
- [ConsecutiveLossTracker](../../risk_management/concentration.py) — ligne 188 : `class ConsecutiveLossTracker`
- [ConsecutiveLossTracker.__init__](../../risk_management/concentration.py) — ligne 203 : `def __init__(self, max_consecutive_losses: int=DEFAULT_MAX_CONSECUTIVE_LOSSES, blacklist_duration_days: int=90) -> None`
- [ConsecutiveLossTracker.max_consecutive_losses](../../risk_management/concentration.py) — ligne 217 : `def max_consecutive_losses(self) -> int`
- [ConsecutiveLossTracker.is_blacklisted](../../risk_management/concentration.py) — ligne 221 : `def is_blacklisted(self, symbol: str, as_of: date | None=None, side: str | None=None) -> bool`
- [ConsecutiveLossTracker.record](../../risk_management/concentration.py) — ligne 240 : `def record(self, symbol: str, pnl: float, trade_date: date | None=None, side: str | None=None) -> bool`
- [ConsecutiveLossTracker.reset](../../risk_management/concentration.py) — ligne 286 : `def reset(self) -> None`
- [ConsecutiveLossTracker._make_key](../../risk_management/concentration.py) — ligne 292 : `def _make_key(symbol: str, side: str | None) -> str`
- [ConsecutiveLossTracker.to_summary](../../risk_management/concentration.py) — ligne 301 : `def to_summary(self) -> dict[str, object]`
- [ConsecutiveLossTracker.to_dict](../../risk_management/concentration.py) — ligne 316 : `def to_dict(self) -> dict[str, object]`
- [ConsecutiveLossTracker.from_dict](../../risk_management/concentration.py) — ligne 329 : `def from_dict(cls, data: dict[str, object]) -> ConsecutiveLossTracker`
- [BreakoutConfirmationTracker](../../risk_management/concentration.py) — ligne 355 : `class BreakoutConfirmationTracker`
- [BreakoutConfirmationTracker.__init__](../../risk_management/concentration.py) — ligne 368 : `def __init__(self, min_breakout_days: int=DEFAULT_MIN_BREAKOUT_DAYS) -> None`
- [BreakoutConfirmationTracker.min_breakout_days](../../risk_management/concentration.py) — ligne 377 : `def min_breakout_days(self) -> int`
- [BreakoutConfirmationTracker.record_selections](../../risk_management/concentration.py) — ligne 381 : `def record_selections(self, symbols: list[str], trade_date: date) -> None`
- [BreakoutConfirmationTracker.is_confirmed](../../risk_management/concentration.py) — ligne 414 : `def is_confirmed(self, symbol: str) -> bool`
- [BreakoutConfirmationTracker.allow_entry](../../risk_management/concentration.py) — ligne 425 : `def allow_entry(self, symbol: str) -> bool`
- [BreakoutConfirmationTracker.reset](../../risk_management/concentration.py) — ligne 429 : `def reset(self) -> None`
- [BreakoutConfirmationTracker.to_summary](../../risk_management/concentration.py) — ligne 434 : `def to_summary(self) -> dict[str, object]`
- [BreakoutConfirmationTracker.to_dict](../../risk_management/concentration.py) — ligne 447 : `def to_dict(self) -> dict[str, object]`
- [BreakoutConfirmationTracker.from_dict](../../risk_management/concentration.py) — ligne 456 : `def from_dict(cls, data: dict[str, object]) -> BreakoutConfirmationTracker`
- [build_entry_concentration_filter](../../risk_management/concentration.py) — ligne 472 : `def build_entry_concentration_filter(*, max_trades_per_symbol: int=DEFAULT_MAX_TRADES_PER_SYMBOL, window_calendar_days: int=DEFAULT_CONCENTRATION_WINDOW_CALENDAR_DAYS, max_consecutive_losses: int=DEFAULT_MAX_CONSECUTIVE_LOSSES, blacklist_duration_days: int=90) -> tuple[SymbolTradeTracker, ConsecutiveLossTracker]`

## `risk_management/concentration_constraints.py`

Source SHA-256 : `d011619038599b777ca2a5750090b686db4bd9ab46e409c6e651511da7f3f9a7`

- [ConcentrationConfig](../../risk_management/concentration_constraints.py) — ligne 24 : `class ConcentrationConfig`
- [ConcentrationConfig.__post_init__](../../risk_management/concentration_constraints.py) — ligne 54 : `def __post_init__(self) -> None`
- [ConcentrationResult](../../risk_management/concentration_constraints.py) — ligne 71 : `class ConcentrationResult`
- [ConcentrationResult.to_dict](../../risk_management/concentration_constraints.py) — ligne 97 : `def to_dict(self) -> dict[str, object]`
- [ConcentrationChecker](../../risk_management/concentration_constraints.py) — ligne 116 : `class ConcentrationChecker`
- [ConcentrationChecker.check](../../risk_management/concentration_constraints.py) — ligne 129 : `def check(self, weights: dict[str, float], *, sectors: dict[str, str] | None=None, industries: dict[str, str] | None=None, themes: dict[str, str] | None=None, countries: dict[str, str] | None=None, currencies: dict[str, str] | None=None) -> ConcentrationResult`
- [check_concentration](../../risk_management/concentration_constraints.py) — ligne 300 : `def check_concentration(weights: dict[str, float], sectors: dict[str, str] | None=None, industries: dict[str, str] | None=None, themes: dict[str, str] | None=None, countries: dict[str, str] | None=None, currencies: dict[str, str] | None=None) -> ConcentrationResult`
- [compute_portfolio_hhi](../../risk_management/concentration_constraints.py) — ligne 320 : `def compute_portfolio_hhi(weights: dict[str, float]) -> float`

## `risk_management/config.py`

Source SHA-256 : `35b0c866124a727c1f521e5747eec80cf0f843854bfdffa94c7d1f99b5ef8ec0`

- [RiskConfig](../../risk_management/config.py) — ligne 14 : `class RiskConfig`
- [RiskConfig.atr_stop_multiple_for](../../risk_management/config.py) — ligne 140 : `def atr_stop_multiple_for(self, horizon: int | None=None) -> float`
- [RiskConfig.stop_distance](../../risk_management/config.py) — ligne 152 : `def stop_distance(self, price: float, atr: float | None) -> float | None`
- [RiskConfig.tp_params_for](../../risk_management/config.py) — ligne 160 : `def tp_params_for(self, horizon: int | None=None) -> tuple[float, float]`
- [RiskConfig.__post_init__](../../risk_management/config.py) — ligne 267 : `def __post_init__(self) -> None`
- [RiskConfig.effective_min_notional](../../risk_management/config.py) — ligne 363 : `def effective_min_notional(self) -> float`
- [RiskConfig.effective_max_positions](../../risk_management/config.py) — ligne 370 : `def effective_max_positions(self) -> int`
- [RiskConfig.selection_capacity](../../risk_management/config.py) — ligne 377 : `def selection_capacity(self) -> SelectionCapacity`
- [RiskConfig.to_conviction_weights](../../risk_management/config.py) — ligne 391 : `def to_conviction_weights(self) -> ConvictionWeights`
- [RiskConfig.fingerprint](../../risk_management/config.py) — ligne 406 : `def fingerprint(self) -> str`
- [RiskConfig.to_dict](../../risk_management/config.py) — ligne 419 : `def to_dict(self, *, exclude_defaults: bool=True) -> dict[str, object]`
- [RiskConfig.from_dict](../../risk_management/config.py) — ligne 441 : `def from_dict(cls, data: dict[str, object]) -> 'RiskConfig'`
- [RiskConfig.with_overrides](../../risk_management/config.py) — ligne 460 : `def with_overrides(self, **overrides: object) -> 'RiskConfig'`
- [RiskConfig.build_sizing_config](../../risk_management/config.py) — ligne 480 : `def build_sizing_config(self) -> 'SizingConfig | None'`
- [RiskConfig.from_preset](../../risk_management/config.py) — ligne 528 : `def from_preset(cls, preset_key: str | None=None, *, equity: float | None=None, **overrides: object) -> 'RiskConfig'`
- [RiskConfig.from_yaml_section](../../risk_management/config.py) — ligne 563 : `def from_yaml_section(cls, yaml_data: dict[str, object] | None=None, *, preset_key: str | None=None, equity: float | None=None, **overrides: object) -> 'RiskConfig'`
- [load_risk_config](../../risk_management/config.py) — ligne 649 : `def load_risk_config(*, equity: float | None=None, preset_key: str | None=None, yaml_path: str | None=None, cli_overrides: dict[str, object] | None=None) -> RiskConfig`

## `risk_management/constraints.py`

Source SHA-256 : `08760fbc4ac7d046bc2225cb6355ff117993a16150144a418f9b59ffff9f5d66`

- [PortfolioState](../../risk_management/constraints.py) — ligne 39 : `class PortfolioState`
- [PortfolioState.gross_notional](../../risk_management/constraints.py) — ligne 58 : `def gross_notional(self) -> float`
- [PortfolioState.net_notional](../../risk_management/constraints.py) — ligne 63 : `def net_notional(self) -> float`
- [PortfolioState.total_notional_signed](../../risk_management/constraints.py) — ligne 68 : `def total_notional_signed(self) -> float`
- [PortfolioState.add_position](../../risk_management/constraints.py) — ligne 72 : `def add_position(self, *, notional: float, sector: str, side: str='long', symbol: str='') -> None`
- [ConstraintChecker](../../risk_management/constraints.py) — ligne 113 : `class ConstraintChecker`
- [ConstraintChecker.__init__](../../risk_management/constraints.py) — ligne 116 : `def __init__(self, config: RiskConfig) -> None`
- [ConstraintChecker._normalize_approved_shares](../../risk_management/constraints.py) — ligne 119 : `def _normalize_approved_shares(self, shares: float) -> float`
- [ConstraintChecker.reason_to_code](../../risk_management/constraints.py) — ligne 127 : `def reason_to_code(reason: str) -> DecisionReasonCode`
- [ConstraintChecker._hybrid_corr_ok](../../risk_management/constraints.py) — ligne 130 : `def _hybrid_corr_ok(self, state: PortfolioState, sector: str, symbol: str) -> bool`
- [ConstraintChecker.check](../../risk_management/constraints.py) — ligne 154 : `def check(self, symbol: str, sector: str, proposed_shares: float, price: float, state: PortfolioState, *, side: str='long', adv_usd: float | None=None, selection_rank: int | None=None) -> tuple[float, str]`
- [ConstraintChecker.revalidate_portfolio](../../risk_management/constraints.py) — ligne 311 : `def revalidate_portfolio(self, state: PortfolioState, *, positions: list[dict[str, object]] | None=None) -> list[str]`

## `risk_management/conviction.py`

Source SHA-256 : `46e061100995ebc2edbb48d15605a28bab0f9c16be226b1fd71ae7bc06602d3c`

- [compute_conviction](../../risk_management/conviction.py) — ligne 13 : `def compute_conviction(score_used: float=0.0, predicted_proba: float | None=None, score_weight: float=0.0, prediction_weight: float=1.0) -> float`

## `risk_management/correlation_filter.py`

Source SHA-256 : `6236ff4efdc7803e0a4bd444911ae407d4bcd407f69eabfb747f7e27260a79cf`

- [build_return_matrix](../../risk_management/correlation_filter.py) — ligne 24 : `def build_return_matrix(close_prices: pd.DataFrame, *, cash_dividends: pd.DataFrame | None=None, convention: str=CORRELATION_CONVENTION_PRICE_ONLY) -> pd.DataFrame`
- [filter_correlated](../../risk_management/correlation_filter.py) — ligne 55 : `def filter_correlated(candidates: list[EnrichedSelection], return_matrix: pd.DataFrame, threshold: float, min_overlap: int) -> tuple[list[EnrichedSelection], list[CorrelationRejection]]`
- [filter_correlated_signed](../../risk_management/correlation_filter.py) — ligne 109 : `def filter_correlated_signed(candidates: list[EnrichedSelection], return_matrix: pd.DataFrame, threshold: float, min_overlap: int, *, precompute: bool=False) -> tuple[list[EnrichedSelection], list[CorrelationRejection]]`

## `risk_management/daily_reconciliation.py`

Source SHA-256 : `a27b21a222330731b5a88598a2b232b72b470d1da679b5f3c7cb7bca7e4ffd29`

- [ReconStatus](../../risk_management/daily_reconciliation.py) — ligne 27 : `class ReconStatus(StrEnum)`
- [ReconItem](../../risk_management/daily_reconciliation.py) — ligne 40 : `class ReconItem`
- [ReconItem.is_matched](../../risk_management/daily_reconciliation.py) — ligne 52 : `def is_matched(self) -> bool`
- [ReconItem.to_dict](../../risk_management/daily_reconciliation.py) — ligne 55 : `def to_dict(self) -> dict[str, object]`
- [ReconciliationReport](../../risk_management/daily_reconciliation.py) — ligne 69 : `class ReconciliationReport`
- [ReconciliationReport.match_rate](../../risk_management/daily_reconciliation.py) — ligne 98 : `def match_rate(self) -> float`
- [ReconciliationReport.is_clean](../../risk_management/daily_reconciliation.py) — ligne 104 : `def is_clean(self) -> bool`
- [ReconciliationReport.to_dict](../../risk_management/daily_reconciliation.py) — ligne 108 : `def to_dict(self) -> dict[str, object]`
- [DailyReconciliation](../../risk_management/daily_reconciliation.py) — ligne 129 : `class DailyReconciliation`
- [DailyReconciliation.reconcile](../../risk_management/daily_reconciliation.py) — ligne 142 : `def reconcile(self, trade_date: date, *, intended_orders: list[dict[str, object]] | None=None, submitted_orders: list[dict[str, object]] | None=None, fills: list[dict[str, object]] | None=None, target_positions: list[dict[str, object]] | None=None, actual_positions: list[dict[str, object]] | None=None, expected_protections: list[dict[str, object]] | None=None, actual_protections: list[dict[str, object]] | None=None, calculated_pnl: float | None=None, broker_pnl: float | None=None, calculated_cash: float | None=None, broker_cash: float | None=None) -> ReconciliationReport`
- [DailyReconciliation._reconcile_orders](../../risk_management/daily_reconciliation.py) — ligne 231 : `def _reconcile_orders(self, items: list[ReconItem], intended: list[dict[str, object]], submitted: list[dict[str, object]], fills: list[dict[str, object]]) -> ReconStatus`
- [DailyReconciliation._reconcile_positions](../../risk_management/daily_reconciliation.py) — ligne 274 : `def _reconcile_positions(self, items: list[ReconItem], targets: list[dict[str, object]], actuals: list[dict[str, object]]) -> ReconStatus`
- [DailyReconciliation._reconcile_protections](../../risk_management/daily_reconciliation.py) — ligne 317 : `def _reconcile_protections(self, items: list[ReconItem], expected: list[dict[str, object]], actuals: list[dict[str, object]]) -> ReconStatus`
- [DailyReconciliation._reconcile_pnl](../../risk_management/daily_reconciliation.py) — ligne 347 : `def _reconcile_pnl(items: list[ReconItem], calculated: float | None, broker: float | None) -> ReconStatus`
- [DailyReconciliation._reconcile_cash](../../risk_management/daily_reconciliation.py) — ligne 371 : `def _reconcile_cash(items: list[ReconItem], calculated: float | None, broker: float | None) -> ReconStatus`

## `risk_management/data_criticality.py`

Source SHA-256 : `2999a8afa6febc1085eb623f4364a4e590c4d4f0335a8b2e7b42738901410d84`

- [DataCriticality](../../risk_management/data_criticality.py) — ligne 34 : `class DataCriticality(StrEnum)`
- [classify_data_source](../../risk_management/data_criticality.py) — ligne 80 : `def classify_data_source(source_name: str) -> DataCriticality`
- [AvailabilityStatus](../../risk_management/data_criticality.py) — ligne 93 : `class AvailabilityStatus`
- [AvailabilityStatus.is_blocking](../../risk_management/data_criticality.py) — ligne 120 : `def is_blocking(self) -> bool`
- [AvailabilityStatus.is_degrading](../../risk_management/data_criticality.py) — ligne 125 : `def is_degrading(self) -> bool`
- [GateResult](../../risk_management/data_criticality.py) — ligne 134 : `class GateResult`
- [GateResult.can_trade](../../risk_management/data_criticality.py) — ligne 161 : `def can_trade(self) -> bool`
- [DataAvailabilityGate](../../risk_management/data_criticality.py) — ligne 167 : `class DataAvailabilityGate`
- [DataAvailabilityGate.evaluate](../../risk_management/data_criticality.py) — ligne 191 : `def evaluate(self, *, price_data_available: bool=True, tradable_universe_available: bool=True, earnings_data_available: bool=True, corporate_actions_available: bool=True, tradability_check_available: bool=True, broker_connection_available: bool=True, account_snapshot_available: bool=True, circuit_breaker_ok: bool=True, ml_predictions_available: bool=True, market_regime_available: bool=True, atr_data_available: bool=True, volume_adv_available: bool=True, sector_mapping_available: bool=True, correlation_matrix_available: bool=True, factor_exposures_available: bool=True, sentiment_overlay_available: bool=True, macro_overlay_available: bool=True) -> GateResult`
- [DataAvailabilityGate.all_available](../../risk_management/data_criticality.py) — ligne 305 : `def all_available(cls) -> GateResult`
- [DataAvailabilityGate.critical_missing](../../risk_management/data_criticality.py) — ligne 310 : `def critical_missing(cls, *sources: str) -> GateResult`
- [check_data_availability](../../risk_management/data_criticality.py) — ligne 337 : `def check_data_availability(*, price_ok: bool=True, earnings_ok: bool=True, tradability_ok: bool=True, broker_ok: bool=True, ml_ok: bool=True, regime_ok: bool=True) -> GateResult`

## `risk_management/db_io.py`

Source SHA-256 : `61d69fe16c82c61e7782a7dcd87a7f41493ac904889b2dcf20809bb6ce4c6a65`

- [_optional_int](../../risk_management/db_io.py) — ligne 44 : `def _optional_int(value: Any) -> int | None`
- [_optional_text](../../risk_management/db_io.py) — ligne 53 : `def _optional_text(value: Any) -> str | None`
- [_build_runtime_segment_key](../../risk_management/db_io.py) — ligne 60 : `def _build_runtime_segment_key(*, market_regime_mode: str | None, horizon_days: int | None, lookback_months: int | None) -> str | None`
- [_load_empirical_calibration_fallback_levels](../../risk_management/db_io.py) — ligne 77 : `def _load_empirical_calibration_fallback_levels() -> tuple[list[str], str]`
- [RiskRepository](../../risk_management/db_io.py) — ligne 120 : `class RiskRepository`
- [RiskRepository.__init__](../../risk_management/db_io.py) — ligne 123 : `def __init__(self, engine: Engine | None=None) -> None`
- [RiskRepository.load_tradable_universe_asof](../../risk_management/db_io.py) — ligne 129 : `def load_tradable_universe_asof(self, trade_date: date, capital_preset_key: str=DEFAULT_CAPITAL_PRESET_KEY, *, tradable_only: bool=True) -> UniverseResolution`
- [RiskRepository.load_selection_inputs](../../risk_management/db_io.py) — ligne 144 : `def load_selection_inputs(self, config: RiskConfig, trade_date: date | None=None) -> list[SelectionScore]`
- [RiskRepository.load_selection_inputs_asof](../../risk_management/db_io.py) — ligne 148 : `def load_selection_inputs_asof(self, trade_date: date) -> list[SelectionScore]`
- [RiskRepository.load_score_context_asof](../../risk_management/db_io.py) — ligne 285 : `def load_score_context_asof(self, symbols: list[str], trade_date: date) -> list[SelectionScore]`
- [RiskRepository._get_table_columns](../../risk_management/db_io.py) — ligne 354 : `def _get_table_columns(self, table_name: str) -> set[str]`
- [RiskRepository._coerce_date](../../risk_management/db_io.py) — ligne 368 : `def _coerce_date(value: Any) -> date | None`
- [RiskRepository._load_latest_broker_account_snapshot_row](../../risk_management/db_io.py) — ligne 380 : `def _load_latest_broker_account_snapshot_row(self, account_id: str, trade_date: date, *, require_positive_equity: bool) -> tuple[dict[str, Any] | None, set[str]]`
- [RiskRepository.load_prices](../../risk_management/db_io.py) — ligne 419 : `def load_prices(self, symbols: list[str], atr_window: int=20, trade_date: date | None=None) -> dict[str, PriceInfo]`
- [RiskRepository.load_prices_asof](../../risk_management/db_io.py) — ligne 423 : `def load_prices_asof(self, symbols: list[str], trade_date: date, atr_window: int=20) -> dict[str, PriceInfo]`
- [RiskRepository.load_predictions](../../risk_management/db_io.py) — ligne 506 : `def load_predictions(self, symbols: list[str], trade_date: date) -> dict[str, PredictionInfo]`
- [RiskRepository.load_predictions_asof](../../risk_management/db_io.py) — ligne 512 : `def load_predictions_asof(self, symbols: list[str], trade_date: date, *, batch_id: str | None=None, sources: list[str] | None=None) -> dict[str, PredictionInfo]`
- [RiskRepository.load_oracle_scores_asof](../../risk_management/db_io.py) — ligne 616 : `def load_oracle_scores_asof(self, trade_date: date, *, batch_id: str, symbols: list[str] | None=None) -> dict[str, float]`
- [RiskRepository.load_win_rates](../../risk_management/db_io.py) — ligne 652 : `def load_win_rates(self, symbols: list[str], trade_date: date | None=None) -> dict[str, WinRateInfo]`
- [RiskRepository.load_win_rates_asof](../../risk_management/db_io.py) — ligne 656 : `def load_win_rates_asof(self, symbols: list[str], trade_date: date) -> dict[str, WinRateInfo]`
- [RiskRepository.load_directional_win_rates_asof](../../risk_management/db_io.py) — ligne 699 : `def load_directional_win_rates_asof(self, symbols: list[str], trade_date: date) -> dict[tuple[str, str], DirectionalWinRateInfo]`
- [RiskRepository.load_factor_columns_asof](../../risk_management/db_io.py) — ligne 755 : `def load_factor_columns_asof(self, symbols: list[str], trade_date: date) -> pd.DataFrame`
- [RiskRepository.load_return_matrix](../../risk_management/db_io.py) — ligne 836 : `def load_return_matrix(self, symbols: list[str], lookback_days: int, trade_date: date | None=None) -> pd.DataFrame`
- [RiskRepository.load_return_matrix_asof](../../risk_management/db_io.py) — ligne 842 : `def load_return_matrix_asof(self, symbols: list[str], trade_date: date, lookback_days: int) -> pd.DataFrame`
- [RiskRepository.load_account_risk_snapshot](../../risk_management/db_io.py) — ligne 876 : `def load_account_risk_snapshot(self, account_id: str | None, trade_date: date) -> AccountRiskSnapshot | None`
- [RiskRepository._load_broker_snapshot_as_account_risk_snapshot](../../risk_management/db_io.py) — ligne 907 : `def _load_broker_snapshot_as_account_risk_snapshot(self, account_id: str, trade_date: date) -> AccountRiskSnapshot | None`
- [RiskRepository.load_equity_history](../../risk_management/db_io.py) — ligne 970 : `def load_equity_history(self, account_id: str | None, trade_date: date, lookback_days: int=25) -> list[tuple[date, float]]`
- [RiskRepository.load_account_equity_breakdown](../../risk_management/db_io.py) — ligne 1055 : `def load_account_equity_breakdown(self, account_id: str | None, trade_date: date) -> dict[str, Any]`
- [RiskRepository.load_latest_empirical_risk_calibration](../../risk_management/db_io.py) — ligne 1170 : `def load_latest_empirical_risk_calibration(self, trade_date: date, *, run_id: str | None=None, market_regime_mode: str | None=None, horizon_days: int | None=None, lookback_months: int | None=None) -> dict[str, Any] | None`
- [RiskRepository.load_eligible_calibration_run_ids](../../risk_management/db_io.py) — ligne 1541 : `def load_eligible_calibration_run_ids(self, *, as_of_date: date | None=None, limit: int=50) -> list[dict[str, Any]]`
- [RiskRepository.load_risk_decisions_for_date](../../risk_management/db_io.py) — ligne 1596 : `def load_risk_decisions_for_date(self, trade_date: date, *, account_id: str | None=None) -> pd.DataFrame`
- [RiskRepository.load_risk_decisions_for_run_id](../../risk_management/db_io.py) — ligne 1638 : `def load_risk_decisions_for_run_id(self, run_id: str, *, account_id: str | None=None) -> pd.DataFrame`
- [RiskRepository.write_risk_decisions](../../risk_management/db_io.py) — ligne 1670 : `def write_risk_decisions(self, records: list[dict[str, Any]], account_id: str | None=None) -> int`
- [RiskRepository.write_portfolio_targets](../../risk_management/db_io.py) — ligne 1710 : `def write_portfolio_targets(self, records: list[dict[str, Any]], account_id: str | None=None) -> int`

## `risk_management/decision_fingerprint.py`

Source SHA-256 : `72444e28922961cfdc0a9bacf95d1ad255af5fd64a72696654f0d64aba3d8bfc`

- [DecisionFingerprint](../../risk_management/decision_fingerprint.py) — ligne 29 : `class DecisionFingerprint`
- [DecisionFingerprint.__post_init__](../../risk_management/decision_fingerprint.py) — ligne 66 : `def __post_init__(self) -> None`
- [DecisionFingerprint._compute](../../risk_management/decision_fingerprint.py) — ligne 70 : `def _compute(self) -> str`
- [DecisionFingerprint.to_dict](../../risk_management/decision_fingerprint.py) — ligne 85 : `def to_dict(self) -> dict[str, object]`
- [PositionDecisionFingerprint](../../risk_management/decision_fingerprint.py) — ligne 100 : `class PositionDecisionFingerprint`
- [PositionDecisionFingerprint.__post_init__](../../risk_management/decision_fingerprint.py) — ligne 134 : `def __post_init__(self) -> None`
- [PositionDecisionFingerprint._compute](../../risk_management/decision_fingerprint.py) — ligne 138 : `def _compute(self) -> str`
- [AuditLogEntry](../../risk_management/decision_fingerprint.py) — ligne 159 : `class AuditLogEntry`
- [AuditLogEntry.to_dict](../../risk_management/decision_fingerprint.py) — ligne 184 : `def to_dict(self) -> dict[str, object]`
- [AuditLogEntry.from_dict](../../risk_management/decision_fingerprint.py) — ligne 207 : `def from_dict(cls, data: dict[str, object]) -> 'AuditLogEntry'`
- [DecisionAuditLog](../../risk_management/decision_fingerprint.py) — ligne 231 : `class DecisionAuditLog`
- [DecisionAuditLog.add_entry](../../risk_management/decision_fingerprint.py) — ligne 243 : `def add_entry(self, entry: AuditLogEntry) -> None`
- [DecisionAuditLog.accepted_count](../../risk_management/decision_fingerprint.py) — ligne 247 : `def accepted_count(self) -> int`
- [DecisionAuditLog.rejected_count](../../risk_management/decision_fingerprint.py) — ligne 251 : `def rejected_count(self) -> int`
- [DecisionAuditLog.reduced_count](../../risk_management/decision_fingerprint.py) — ligne 255 : `def reduced_count(self) -> int`
- [DecisionAuditLog.to_dict](../../risk_management/decision_fingerprint.py) — ligne 258 : `def to_dict(self) -> dict[str, object]`
- [DecisionAuditLog.from_dict](../../risk_management/decision_fingerprint.py) — ligne 274 : `def from_dict(cls, data: dict[str, object]) -> 'DecisionAuditLog'`
- [ReplayVerifier](../../risk_management/decision_fingerprint.py) — ligne 302 : `class ReplayVerifier`
- [ReplayVerifier.verify](../../risk_management/decision_fingerprint.py) — ligne 308 : `def verify(self, original: DecisionAuditLog, replay: DecisionAuditLog) -> ReplayVerificationResult`
- [ReplayVerificationResult](../../risk_management/decision_fingerprint.py) — ligne 380 : `class ReplayVerificationResult`
- [ReplayVerificationResult.parity_pct](../../risk_management/decision_fingerprint.py) — ligne 391 : `def parity_pct(self) -> float`
- [ReplayVerificationResult.to_dict](../../risk_management/decision_fingerprint.py) — ligne 397 : `def to_dict(self) -> dict[str, object]`
- [IdempotencyResult](../../risk_management/decision_fingerprint.py) — ligne 413 : `class IdempotencyResult`
- [IdempotencyGate](../../risk_management/decision_fingerprint.py) — ligne 423 : `class IdempotencyGate`
- [IdempotencyGate.__init__](../../risk_management/decision_fingerprint.py) — ligne 434 : `def __init__(self) -> None`
- [IdempotencyGate.check](../../risk_management/decision_fingerprint.py) — ligne 437 : `def check(self, decision_fingerprint: DecisionFingerprint) -> IdempotencyResult`
- [IdempotencyGate.clear](../../risk_management/decision_fingerprint.py) — ligne 463 : `def clear(self) -> None`
- [build_decision_fingerprint](../../risk_management/decision_fingerprint.py) — ligne 470 : `def build_decision_fingerprint(trade_date: date, run_id: str, *, config_fingerprint: str, model_run_id: str, policy_version: int=1, universe_fingerprint: str='', regime_mode: str='normal', candidate_count: int=0) -> DecisionFingerprint`
- [build_position_fingerprint](../../risk_management/decision_fingerprint.py) — ligne 494 : `def build_position_fingerprint(symbol: str, side: str, decision_fingerprint: str, *, predicted_proba: float=0.0, p_side: float=0.0, edge: float | None=None, price: float=0.0, atr: float | None=None, adv_usd: float | None=None, config_fingerprint: str='') -> PositionDecisionFingerprint`

## `risk_management/drift_monitor.py`

Source SHA-256 : `00ac1ca26d22439743cec921c4d95fa8e8ee5f7c7f2c4bdaa4326f8e7b27ec65`

- [DriftDimension](../../risk_management/drift_monitor.py) — ligne 30 : `class DriftDimension(StrEnum)`
- [DriftStatus](../../risk_management/drift_monitor.py) — ligne 45 : `class DriftStatus(StrEnum)`
- [DriftConfig](../../risk_management/drift_monitor.py) — ligne 57 : `class DriftConfig`
- [DimensionDrift](../../risk_management/drift_monitor.py) — ligne 93 : `class DimensionDrift`
- [DimensionDrift.is_drifting](../../risk_management/drift_monitor.py) — ligne 106 : `def is_drifting(self) -> bool`
- [DimensionDrift.is_critical](../../risk_management/drift_monitor.py) — ligne 110 : `def is_critical(self) -> bool`
- [DriftReport](../../risk_management/drift_monitor.py) — ligne 118 : `class DriftReport`
- [DriftReport.to_dict](../../risk_management/drift_monitor.py) — ligne 143 : `def to_dict(self) -> dict[str, object]`
- [DriftMonitor](../../risk_management/drift_monitor.py) — ligne 169 : `class DriftMonitor`
- [DriftMonitor.evaluate](../../risk_management/drift_monitor.py) — ligne 178 : `def evaluate(self, model_id: str='', *, features_psi: float | None=None, proba_ks_pvalue: float | None=None, sides_long_pct: float | None=None, sides_flat_pct: float | None=None, sides_short_pct: float | None=None, sides_baseline_long: float | None=None, sides_baseline_flat: float | None=None, sides_baseline_short: float | None=None, calibration_brier_current: float | None=None, calibration_brier_baseline: float | None=None, pnl_drawdown_pct: float | None=None, costs_current_bps: float | None=None, costs_baseline_bps: float | None=None, exposure_current_gross: float | None=None, exposure_baseline_gross: float | None=None) -> DriftReport`
- [check_drift](../../risk_management/drift_monitor.py) — ligne 368 : `def check_drift(*, features_psi: float | None=None, proba_ks_pvalue: float | None=None, pnl_drawdown_pct: float | None=None, sides_max_change: float | None=None) -> DriftReport`

## `risk_management/edge.py`

Source SHA-256 : `fa1f130f914a7707649892d5711ec5e7735f19dffe75b5fa96e2194c1534bf9c`

- [DirectionalEdgeEstimate](../../risk_management/edge.py) — ligne 30 : `class DirectionalEdgeEstimate`
- [DirectionalEdgeEstimate.__post_init__](../../risk_management/edge.py) — ligne 68 : `def __post_init__(self) -> None`
- [DirectionalEdgeEstimate.is_tradable](../../risk_management/edge.py) — ligne 78 : `def is_tradable(self) -> bool`
- [DirectionalEdgeEstimate.to_dict](../../risk_management/edge.py) — ligne 82 : `def to_dict(self) -> dict[str, object]`
- [EdgeCalculator](../../risk_management/edge.py) — ligne 101 : `class EdgeCalculator`
- [EdgeCalculator.total_cost_bps](../../risk_management/edge.py) — ligne 130 : `def total_cost_bps(self) -> float`
- [EdgeCalculator.cost_pct](../../risk_management/edge.py) — ligne 134 : `def cost_pct(self) -> float`
- [EdgeCalculator.estimate](../../risk_management/edge.py) — ligne 137 : `def estimate(self, *, side: str, hit_rate: float, payoff: float, n_trades: int, tail_loss: float | None=None, holding_days: int=10) -> DirectionalEdgeEstimate`
- [compute_edge_from_trades](../../risk_management/edge.py) — ligne 214 : `def compute_edge_from_trades(returns: np.ndarray, *, side: str='long', cost_pct: float=0.0016, min_sample_size: int=30) -> DirectionalEdgeEstimate`

## `risk_management/enums.py`

Source SHA-256 : `08e68a71bbd6c487f1ee8b87e9c6909cf7885a6c36005d8361c5568f6795a988`

- [Decision](../../risk_management/enums.py) — ligne 11 : `class Decision(StrEnum)`
- [SizingMethod](../../risk_management/enums.py) — ligne 17 : `class SizingMethod(StrEnum)`
- [DecisionReasonCode](../../risk_management/enums.py) — ligne 29 : `class DecisionReasonCode(StrEnum)`
- [KellyFallback](../../risk_management/enums.py) — ligne 64 : `class KellyFallback(StrEnum)`

## `risk_management/factor_model.py`

Source SHA-256 : `a6e43af5d56d81faa41a6dee7443fbc00842913a775f933903511f475bcb34d3`

- [FactorCovariance](../../risk_management/factor_model.py) — ligne 49 : `class FactorCovariance`
- [PortfolioRiskDecomposition](../../risk_management/factor_model.py) — ligne 77 : `class PortfolioRiskDecomposition`
- [FactorConstraintResult](../../risk_management/factor_model.py) — ligne 114 : `class FactorConstraintResult`
- [FactorConstraintResult.has_violations](../../risk_management/factor_model.py) — ligne 132 : `def has_violations(self) -> bool`
- [FactorCorrelationRejection](../../risk_management/factor_model.py) — ligne 137 : `class FactorCorrelationRejection`
- [_cross_sectional_zscore](../../risk_management/factor_model.py) — ligne 151 : `def _cross_sectional_zscore(series: pd.Series, *, winsorize_pct: tuple[float, float]=(0.01, 0.99)) -> pd.Series`
- [compute_factor_exposures](../../risk_management/factor_model.py) — ligne 189 : `def compute_factor_exposures(symbols: list[str], as_of: date, *, market_betas: dict[str, float] | None=None, market_caps: dict[str, float] | None=None, trend_scores: dict[str, float] | None=None, value_yields: dict[str, float] | None=None) -> dict[str, FactorExposures]`
- [_ewma_weights](../../risk_management/factor_model.py) — ligne 294 : `def _ewma_weights(n: int, half_life: int) -> np.ndarray`
- [_estimate_ewma_covariance](../../risk_management/factor_model.py) — ligne 319 : `def _estimate_ewma_covariance(returns: np.ndarray, half_life: int) -> np.ndarray`
- [build_factor_returns](../../risk_management/factor_model.py) — ligne 357 : `def build_factor_returns(symbols: list[str], close_prices: pd.DataFrame, benchmark_prices: pd.DataFrame | None=None, *, factor_exposures_map: dict[str, FactorExposures] | None=None) -> pd.DataFrame | None`
- [estimate_factor_covariance](../../risk_management/factor_model.py) — ligne 434 : `def estimate_factor_covariance(factor_returns: pd.DataFrame, *, lookback_days: int=DEFAULT_LOOKBACK_DAYS, ewma_half_life: int=DEFAULT_EWMA_HALF_LIFE, estimation_date: date | None=None, stock_returns: pd.DataFrame | None=None) -> FactorCovariance | None`
- [_build_exposure_matrix](../../risk_management/factor_model.py) — ligne 517 : `def _build_exposure_matrix(symbols: list[str], exposures: dict[str, FactorExposures], factor_names: list[str]) -> np.ndarray`
- [decompose_portfolio_risk](../../risk_management/factor_model.py) — ligne 557 : `def decompose_portfolio_risk(weights: dict[str, float], exposures: dict[str, FactorExposures], factor_cov: FactorCovariance, *, annualize: bool=True, trading_days_per_year: int=252) -> PortfolioRiskDecomposition`
- [_compute_factor_implied_correlation](../../risk_management/factor_model.py) — ligne 674 : `def _compute_factor_implied_correlation(exp_i: FactorExposures, exp_j: FactorExposures, factor_cov: FactorCovariance, specific_var_i: float=0.0, specific_var_j: float=0.0) -> float`
- [check_factor_constraints](../../risk_management/factor_model.py) — ligne 715 : `def check_factor_constraints(candidates: list[EnrichedSelection], exposures: dict[str, FactorExposures], factor_cov: FactorCovariance, *, constraints: dict[str, float] | None=None, weights: dict[str, float] | None=None) -> FactorConstraintResult`
- [check_factor_constraints_on_sized_weights](../../risk_management/factor_model.py) — ligne 827 : `def check_factor_constraints_on_sized_weights(weights: dict[str, float], exposures: dict[str, FactorExposures], factor_cov: FactorCovariance, *, max_portfolio_beta: float=DEFAULT_MAX_PORTFOLIO_BETA, max_factor_concentration: float=DEFAULT_MAX_FACTOR_CONCENTRATION, min_factor_diversification: int=DEFAULT_MIN_FACTOR_DIVERSIFICATION) -> list[str]`
- [_filter_worst_offenders](../../risk_management/factor_model.py) — ligne 919 : `def _filter_worst_offenders(candidates: list[EnrichedSelection], exposures: dict[str, FactorExposures], factor_cov: FactorCovariance, constraints: dict[str, float]) -> list[EnrichedSelection]`
- [filter_by_factor_correlation](../../risk_management/factor_model.py) — ligne 958 : `def filter_by_factor_correlation(candidates: list[EnrichedSelection], exposures: dict[str, FactorExposures], factor_cov: FactorCovariance, *, max_factor_correlation: float=DEFAULT_MAX_FACTOR_CORRELATION) -> tuple[list[EnrichedSelection], list[FactorCorrelationRejection]]`
- [build_exposures_from_score_frame](../../risk_management/factor_model.py) — ligne 1038 : `def build_exposures_from_score_frame(scores_df: pd.DataFrame, as_of: date) -> dict[str, FactorExposures]`
- [format_risk_decomposition](../../risk_management/factor_model.py) — ligne 1098 : `def format_risk_decomposition(decomp: PortfolioRiskDecomposition) -> str`
- [_systematic_vol](../../risk_management/factor_model.py) — ligne 1132 : `def _systematic_vol(self: PortfolioRiskDecomposition) -> float`
- [_specific_vol](../../risk_management/factor_model.py) — ligne 1136 : `def _specific_vol(self: PortfolioRiskDecomposition) -> float`

## `risk_management/freshness_gate.py`

Source SHA-256 : `43613c7383a59dfe1a8552d0df03a16a5f8f30bdc945a344162b6ca13488e00f`

- [FreshnessDimension](../../risk_management/freshness_gate.py) — ligne 27 : `class FreshnessDimension(StrEnum)`
- [FreshnessConfig](../../risk_management/freshness_gate.py) — ligne 44 : `class FreshnessConfig`
- [FreshnessConfig.get_threshold](../../risk_management/freshness_gate.py) — ligne 59 : `def get_threshold(self, dim: FreshnessDimension) -> float | None`
- [FreshnessConfig.to_dict](../../risk_management/freshness_gate.py) — ligne 72 : `def to_dict(self) -> dict[str, float | None]`
- [DimensionFreshness](../../risk_management/freshness_gate.py) — ligne 80 : `class DimensionFreshness`
- [DimensionFreshness.status](../../risk_management/freshness_gate.py) — ligne 93 : `def status(self) -> str`
- [FreshnessResult](../../risk_management/freshness_gate.py) — ligne 105 : `class FreshnessResult`
- [FreshnessResult.to_dict](../../risk_management/freshness_gate.py) — ligne 134 : `def to_dict(self) -> dict[str, object]`
- [FreshnessGate](../../risk_management/freshness_gate.py) — ligne 158 : `class FreshnessGate`
- [FreshnessGate.evaluate](../../risk_management/freshness_gate.py) — ligne 189 : `def evaluate(self, *, price_data_at: datetime | None=None, volume_adv_at: datetime | None=None, earnings_at: datetime | None=None, corporate_actions_at: datetime | None=None, ml_model_at: datetime | None=None, calibration_at: datetime | None=None, market_regime_at: datetime | None=None, borrow_at: datetime | None=None, reference_time: datetime | None=None) -> FreshnessResult`
- [FreshnessGate.all_fresh](../../risk_management/freshness_gate.py) — ligne 286 : `def all_fresh(cls) -> FreshnessResult`
- [check_freshness](../../risk_management/freshness_gate.py) — ligne 305 : `def check_freshness(*, price_data_age_seconds: float | None=None, ml_model_age_seconds: float | None=None, market_regime_age_seconds: float | None=None, calibration_age_seconds: float | None=None) -> FreshnessResult`

## `risk_management/gradual_ramp_up.py`

Source SHA-256 : `b2e964c664743fdaae09367a397b24e8b6c7183798e832e70f5f3c9f406a868d`

- [RampUpStage](../../risk_management/gradual_ramp_up.py) — ligne 29 : `class RampUpStage(StrEnum)`
- [RampUpStage.allocation_pct](../../risk_management/gradual_ramp_up.py) — ligne 41 : `def allocation_pct(self) -> float`
- [RampUpStage.is_live](../../risk_management/gradual_ramp_up.py) — ligne 55 : `def is_live(self) -> bool`
- [RampUpStage.requires_human_review](../../risk_management/gradual_ramp_up.py) — ligne 60 : `def requires_human_review(self) -> bool`
- [RampUpStage.next_stage](../../risk_management/gradual_ramp_up.py) — ligne 64 : `def next_stage(self) -> RampUpStage | None`
- [RampUpStage.previous_stage](../../risk_management/gradual_ramp_up.py) — ligne 72 : `def previous_stage(self) -> RampUpStage | None`
- [RampUpConfig](../../risk_management/gradual_ramp_up.py) — ligne 85 : `class RampUpConfig`
- [RampUpConfig.get_min_days](../../risk_management/gradual_ramp_up.py) — ligne 129 : `def get_min_days(self, stage: RampUpStage) -> int`
- [RampUpConfig.get_max_drawdown](../../risk_management/gradual_ramp_up.py) — ligne 132 : `def get_max_drawdown(self, stage: RampUpStage) -> float`
- [StageTransition](../../risk_management/gradual_ramp_up.py) — ligne 140 : `class StageTransition`
- [StageTransition.to_dict](../../risk_management/gradual_ramp_up.py) — ligne 154 : `def to_dict(self) -> dict[str, object]`
- [RampUpManager](../../risk_management/gradual_ramp_up.py) — ligne 173 : `class RampUpManager`
- [RampUpManager.days_in_current_stage](../../risk_management/gradual_ramp_up.py) — ligne 191 : `def days_in_current_stage(self) -> int`
- [RampUpManager.current_allocation](../../risk_management/gradual_ramp_up.py) — ligne 195 : `def current_allocation(self) -> float`
- [RampUpManager.can_promote](../../risk_management/gradual_ramp_up.py) — ligne 198 : `def can_promote(self, *, checklist_passed: bool=True, shadow_convergent: bool=True, human_reviewer: str='') -> tuple[bool, str]`
- [RampUpManager.promote](../../risk_management/gradual_ramp_up.py) — ligne 234 : `def promote(self, *, checklist_passed: bool=True, shadow_convergent: bool=True, human_reviewer: str='') -> StageTransition`
- [RampUpManager.check_drawdown_breach](../../risk_management/gradual_ramp_up.py) — ligne 282 : `def check_drawdown_breach(self, current_drawdown: float) -> StageTransition | None`
- [RampUpManager.rollback](../../risk_management/gradual_ramp_up.py) — ligne 304 : `def rollback(self, reason: str) -> StageTransition | None`
- [RampUpManager.effective_risk_budget](../../risk_management/gradual_ramp_up.py) — ligne 324 : `def effective_risk_budget(self, base_budget: float) -> float`
- [RampUpManager.allocation_summary](../../risk_management/gradual_ramp_up.py) — ligne 328 : `def allocation_summary(self, account_equity: float) -> dict[str, object]`
- [create_ramp_up_manager](../../risk_management/gradual_ramp_up.py) — ligne 346 : `def create_ramp_up_manager(start_stage: RampUpStage=RampUpStage.SHADOW, start_date: date | None=None) -> RampUpManager`

## `risk_management/immutable_journal.py`

Source SHA-256 : `d639dcbca4237a858d3e0fac717759df05ef0040221b33a00465d38417e95b0e`

- [JournalEntryType](../../risk_management/immutable_journal.py) — ligne 33 : `class JournalEntryType(StrEnum)`
- [JournalEntry](../../risk_management/immutable_journal.py) — ligne 52 : `class JournalEntry`
- [JournalEntry.__post_init__](../../risk_management/immutable_journal.py) — ligne 90 : `def __post_init__(self) -> None`
- [JournalEntry._compute_hash](../../risk_management/immutable_journal.py) — ligne 94 : `def _compute_hash(self) -> str`
- [JournalEntry.to_dict](../../risk_management/immutable_journal.py) — ligne 107 : `def to_dict(self) -> dict[str, object]`
- [ImmutableJournal](../../risk_management/immutable_journal.py) — ligne 127 : `class ImmutableJournal`
- [ImmutableJournal.__init__](../../risk_management/immutable_journal.py) — ligne 136 : `def __init__(self) -> None`
- [ImmutableJournal.append](../../risk_management/immutable_journal.py) — ligne 140 : `def append(self, entry_type: JournalEntryType, operator: str, description: str, *, previous_state: dict[str, object] | None=None, new_state: dict[str, object] | None=None, reason: str='', approval: str | None=None) -> JournalEntry`
- [ImmutableJournal.verify_chain](../../risk_management/immutable_journal.py) — ligne 174 : `def verify_chain(self) -> tuple[bool, list[str]]`
- [ImmutableJournal.entries](../../risk_management/immutable_journal.py) — ligne 205 : `def entries(self) -> tuple[JournalEntry, ...]`
- [ImmutableJournal.entry_count](../../risk_management/immutable_journal.py) — ligne 209 : `def entry_count(self) -> int`
- [ImmutableJournal.get_by_type](../../risk_management/immutable_journal.py) — ligne 212 : `def get_by_type(self, entry_type: JournalEntryType) -> list[JournalEntry]`
- [ImmutableJournal.get_by_operator](../../risk_management/immutable_journal.py) — ligne 215 : `def get_by_operator(self, operator: str) -> list[JournalEntry]`
- [ImmutableJournal.to_dict](../../risk_management/immutable_journal.py) — ligne 218 : `def to_dict(self) -> dict[str, object]`
- [ImmutableJournal.from_dict](../../risk_management/immutable_journal.py) — ligne 226 : `def from_dict(cls, payload: dict[str, object]) -> 'ImmutableJournal'`
- [ImmutableJournal.load](../../risk_management/immutable_journal.py) — ligne 255 : `def load(cls, path: Path) -> 'ImmutableJournal'`
- [ImmutableJournal.save_atomic](../../risk_management/immutable_journal.py) — ligne 264 : `def save_atomic(self, path: Path) -> None`
- [ImmutableJournal._make_entry_id](../../risk_management/immutable_journal.py) — ligne 275 : `def _make_entry_id() -> str`
- [create_journal_entry](../../risk_management/immutable_journal.py) — ligne 283 : `def create_journal_entry(journal: ImmutableJournal, entry_type: JournalEntryType, operator: str, description: str, **kwargs: object) -> JournalEntry`

## `risk_management/kelly.py`

Source SHA-256 : `cbf0b35a0ba2067896897ad32e9262915c9b3be02968ab988c779f221dfc5542`

- [KellySizer](../../risk_management/kelly.py) — ligne 15 : `class KellySizer`
- [KellySizer.__init__](../../risk_management/kelly.py) — ligne 26 : `def __init__(self, config: RiskConfig) -> None`
- [KellySizer.compute](../../risk_management/kelly.py) — ligne 30 : `def compute(self, price_info: PriceInfo, predicted_proba: float | None=None, historical_win_rate: float | None=None, *, directional_stats: DirectionalWinRateInfo | None=None, fallback: KellyFallback=KellyFallback.REJECT) -> SizingResult`
- [KellySizer._min_trades_for_full_kelly](../../risk_management/kelly.py) — ligne 148 : `def _min_trades_for_full_kelly(self) -> int`
- [KellySizer._apply_shrinkage](../../risk_management/kelly.py) — ligne 153 : `def _apply_shrinkage(hit_rate: float, payoff: float, trade_count: int) -> tuple[float, float]`
- [KellySizer._handle_fallback](../../risk_management/kelly.py) — ligne 180 : `def _handle_fallback(self, price_info: PriceInfo, fallback: KellyFallback) -> SizingResult`
- [compute_kelly_fraction](../../risk_management/kelly.py) — ligne 213 : `def compute_kelly_fraction(hit_rate: float, payoff: float, *, kelly_multiplier: float=0.25, max_fraction: float=0.25, min_trades: int=30, trade_count: int=0) -> float`
- [compute_kelly_shares](../../risk_management/kelly.py) — ligne 259 : `def compute_kelly_shares(notional: float, price: float, fraction: float, atr: float | None=None, risk_per_trade_pct: float=0.01, atr_stop_multiple: float=2.0, *, allow_fractional: bool=False) -> int | float`

## `risk_management/liquidity.py`

Source SHA-256 : `00712018d2ab61be1705a0730742d461dcf05786e6612eacbc79beb3527fe598`

- [BorrowStatus](../../risk_management/liquidity.py) — ligne 39 : `class BorrowStatus(StrEnum)`
- [BorrowStatus.is_shortable](../../risk_management/liquidity.py) — ligne 52 : `def is_shortable(self) -> bool`
- [BorrowStatus.requires_locate](../../risk_management/liquidity.py) — ligne 56 : `def requires_locate(self) -> bool`
- [BorrowStatus.fee_multiplier](../../risk_management/liquidity.py) — ligne 61 : `def fee_multiplier(self) -> float`
- [alpaca_borrow_status](../../risk_management/liquidity.py) — ligne 70 : `def alpaca_borrow_status(asset: Mapping[str, object]) -> BorrowStatus`
- [SpreadSnapshot](../../risk_management/liquidity.py) — ligne 105 : `class SpreadSnapshot`
- [SpreadSnapshot.__post_init__](../../risk_management/liquidity.py) — ligne 133 : `def __post_init__(self) -> None`
- [SpreadSnapshot.is_available](../../risk_management/liquidity.py) — ligne 140 : `def is_available(self) -> bool`
- [SpreadSnapshot.is_stale](../../risk_management/liquidity.py) — ligne 151 : `def is_stale(self) -> bool`
- [SpreadSnapshot.mid_price](../../risk_management/liquidity.py) — ligne 164 : `def mid_price(self) -> float | None`
- [SpreadSnapshot.effective_spread_bps](../../risk_management/liquidity.py) — ligne 171 : `def effective_spread_bps(self) -> float | None`
- [BorrowSnapshot](../../risk_management/liquidity.py) — ligne 186 : `class BorrowSnapshot`
- [BorrowSnapshot.__post_init__](../../risk_management/liquidity.py) — ligne 223 : `def __post_init__(self) -> None`
- [BorrowSnapshot.is_shortable](../../risk_management/liquidity.py) — ligne 235 : `def is_shortable(self) -> bool`
- [BorrowSnapshot.is_htb_blocked](../../risk_management/liquidity.py) — ligne 240 : `def is_htb_blocked(self) -> bool`
- [BorrowSnapshot.effective_fee_annual](../../risk_management/liquidity.py) — ligne 249 : `def effective_fee_annual(self) -> float`
- [BorrowSnapshot.edge_cost_for_holding](../../risk_management/liquidity.py) — ligne 257 : `def edge_cost_for_holding(self, holding_days: int=10) -> float`
- [ParticipationLimit](../../risk_management/liquidity.py) — ligne 271 : `class ParticipationLimit`
- [ParticipationLimit.__post_init__](../../risk_management/liquidity.py) — ligne 294 : `def __post_init__(self) -> None`
- [ParticipationLimit.max_notional_entry](../../risk_management/liquidity.py) — ligne 304 : `def max_notional_entry(self, adv_usd: float) -> float`
- [ParticipationLimit.max_notional_liquidation](../../risk_management/liquidity.py) — ligne 310 : `def max_notional_liquidation(self, adv_usd: float) -> float`
- [ParticipationLimit.check_entry](../../risk_management/liquidity.py) — ligne 316 : `def check_entry(self, notional: float, adv_usd: float) -> tuple[bool, str | None]`
- [ParticipationLimit.check_liquidation](../../risk_management/liquidity.py) — ligne 336 : `def check_liquidation(self, notional: float, adv_usd: float) -> tuple[bool, str | None]`
- [SlippageEstimate](../../risk_management/liquidity.py) — ligne 352 : `class SlippageEstimate`
- [SlippageEstimate.total_slippage_pct](../../risk_management/liquidity.py) — ligne 378 : `def total_slippage_pct(self) -> float`
- [SlippageEstimator](../../risk_management/liquidity.py) — ligne 383 : `class SlippageEstimator`
- [SlippageEstimator.estimate](../../risk_management/liquidity.py) — ligne 406 : `def estimate(self, symbol: str, *, notional: float, adv_usd: float, spread_bps: float | None=None, daily_vol_pct: float | None=None, is_stressed: bool=False) -> SlippageEstimate`
- [SlippageEstimator.estimate_stressed](../../risk_management/liquidity.py) — ligne 470 : `def estimate_stressed(self, symbol: str, *, notional: float, adv_usd: float, spread_bps: float | None=None, daily_vol_pct: float | None=None) -> SlippageEstimate`
- [LiquidityGateResult](../../risk_management/liquidity.py) — ligne 494 : `class LiquidityGateResult`
- [LiquidityGateResult.to_dict](../../risk_management/liquidity.py) — ligne 523 : `def to_dict(self) -> dict[str, object]`
- [LiquidityGate](../../risk_management/liquidity.py) — ligne 540 : `class LiquidityGate`
- [LiquidityGate.evaluate](../../risk_management/liquidity.py) — ligne 569 : `def evaluate(self, symbol: str, side: str, notional: float, *, spread: SpreadSnapshot | None=None, borrow: BorrowSnapshot | None=None, adv_usd: float | None=None, daily_vol_pct: float | None=None) -> LiquidityGateResult`
- [check_liquidity_pre_entry](../../risk_management/liquidity.py) — ligne 706 : `def check_liquidity_pre_entry(symbol: str, side: str, notional: float, *, adv_usd: float | None=None, spread_bps: float | None=None, borrow_status: str | None=None) -> LiquidityGateResult`
- [PreSubmissionResult](../../risk_management/liquidity.py) — ligne 752 : `class PreSubmissionResult`
- [PreSubmissionResult.to_dict](../../risk_management/liquidity.py) — ligne 792 : `def to_dict(self) -> dict[str, object]`
- [PreSubmissionGate](../../risk_management/liquidity.py) — ligne 807 : `class PreSubmissionGate`
- [PreSubmissionGate.evaluate](../../risk_management/liquidity.py) — ligne 838 : `def evaluate(self, symbol: str, side: str, notional: float, *, spread: SpreadSnapshot | None=None, borrow: BorrowSnapshot | None=None, adv_usd: float | None=None, daily_vol_pct: float | None=None, intent_id: str | None=None, previous_borrow: BorrowSnapshot | None=None) -> PreSubmissionResult`
- [_borrow_degraded](../../risk_management/liquidity.py) — ligne 985 : `def _borrow_degraded(old: BorrowStatus, new: BorrowStatus) -> bool`
- [check_pre_submission](../../risk_management/liquidity.py) — ligne 995 : `def check_pre_submission(symbol: str, side: str, notional: float, *, spread: SpreadSnapshot | None=None, borrow: BorrowSnapshot | None=None, adv_usd: float | None=None, daily_vol_pct: float | None=None, intent_id: str | None=None, previous_borrow: BorrowSnapshot | None=None) -> PreSubmissionResult`

## `risk_management/live_pipeline_guards.py`

Source SHA-256 : `7a7b5a0dfccbf12573a16ac1492588dd52582d79855a68b7c4a3dd2c0a19f5cd`

- [MlCoverageGateDecision](../../risk_management/live_pipeline_guards.py) — ligne 14 : `class MlCoverageGateDecision`
- [MlCoverageGateDecision.to_summary](../../risk_management/live_pipeline_guards.py) — ligne 23 : `def to_summary(self) -> dict[str, Any]`
- [VolTargetDecision](../../risk_management/live_pipeline_guards.py) — ligne 36 : `class VolTargetDecision`
- [VolTargetDecision.to_summary](../../risk_management/live_pipeline_guards.py) — ligne 46 : `def to_summary(self) -> dict[str, Any]`
- [evaluate_ml_coverage_gate](../../risk_management/live_pipeline_guards.py) — ligne 59 : `def evaluate_ml_coverage_gate(*, selection_count: int, prediction_count: int, min_coverage_ratio: float | None, regime_allows_new_entries: bool=True, ml_gate_enabled: bool=True) -> MlCoverageGateDecision`
- [evaluate_vol_target](../../risk_management/live_pipeline_guards.py) — ligne 110 : `def evaluate_vol_target(daily_returns: pd.Series, *, target_annual_vol: float | None, lookback_days: int=60, benchmark_symbol: str='SPY', floor: float=0.25, cap: float=1.5) -> VolTargetDecision`
- [apply_vol_target_to_risk_config](../../risk_management/live_pipeline_guards.py) — ligne 171 : `def apply_vol_target_to_risk_config(config: RiskConfig, decision: VolTargetDecision) -> RiskConfig`

## `risk_management/ml_gate.py`

Source SHA-256 : `4699124c65419f385e4b5ce76b3e193b1fb8a8474b9962c86ee3b42e89285ecb`

- [MlGateState](../../risk_management/ml_gate.py) — ligne 27 : `class MlGateState`
- [MlGateState.to_summary](../../risk_management/ml_gate.py) — ligne 36 : `def to_summary(self) -> dict[str, Any]`
- [load_latest_ml_gate_decision](../../risk_management/ml_gate.py) — ligne 46 : `def load_latest_ml_gate_decision(engine: Any) -> dict | None`
- [resolve_ml_gate_state](../../risk_management/ml_gate.py) — ligne 83 : `def resolve_ml_gate_state(engine: Any) -> MlGateState`
- [apply_ml_gate_to_risk_config](../../risk_management/ml_gate.py) — ligne 127 : `def apply_ml_gate_to_risk_config(config: Any, gate_state: MlGateState) -> Any`

## `risk_management/model_registry.py`

Source SHA-256 : `b6a97679006318a61aca5a73e9f20cc3ca3b76292f4ec360c874419e89380108`

- [ModelStatus](../../risk_management/model_registry.py) — ligne 27 : `class ModelStatus(StrEnum)`
- [ModelStatus.is_active](../../risk_management/model_registry.py) — ligne 44 : `def is_active(self) -> bool`
- [ModelStatus.is_production](../../risk_management/model_registry.py) — ligne 49 : `def is_production(self) -> bool`
- [ModelStatus.can_be_promoted](../../risk_management/model_registry.py) — ligne 54 : `def can_be_promoted(self) -> bool`
- [ModelStatus.can_be_demoted](../../risk_management/model_registry.py) — ligne 59 : `def can_be_demoted(self) -> bool`
- [ModelStatus.next_in_cycle](../../risk_management/model_registry.py) — ligne 63 : `def next_in_cycle(self) -> ModelStatus`
- [ModelRegistryEntry](../../risk_management/model_registry.py) — ligne 77 : `class ModelRegistryEntry`
- [ModelRegistryEntry.__post_init__](../../risk_management/model_registry.py) — ligne 121 : `def __post_init__(self) -> None`
- [ModelRegistryEntry.to_dict](../../risk_management/model_registry.py) — ligne 129 : `def to_dict(self) -> dict[str, object]`
- [ModelRegistry](../../risk_management/model_registry.py) — ligne 150 : `class ModelRegistry`
- [ModelRegistry.__init__](../../risk_management/model_registry.py) — ligne 163 : `def __init__(self) -> None`
- [ModelRegistry.register](../../risk_management/model_registry.py) — ligne 168 : `def register(self, entry: ModelRegistryEntry) -> None`
- [ModelRegistry.promote](../../risk_management/model_registry.py) — ligne 175 : `def promote(self, model_id: str, reason: str='') -> ModelRegistryEntry`
- [ModelRegistry.degrade](../../risk_management/model_registry.py) — ligne 214 : `def degrade(self, model_id: str, reason: str) -> ModelRegistryEntry`
- [ModelRegistry.retire](../../risk_management/model_registry.py) — ligne 225 : `def retire(self, model_id: str, reason: str) -> ModelRegistryEntry`
- [ModelRegistry.rollback](../../risk_management/model_registry.py) — ligne 231 : `def rollback(self, symbol: str, reason: str) -> ModelRegistryEntry | None`
- [ModelRegistry.get_champion](../../risk_management/model_registry.py) — ligne 265 : `def get_champion(self, symbol: str) -> ModelRegistryEntry | None`
- [ModelRegistry.get_by_status](../../risk_management/model_registry.py) — ligne 272 : `def get_by_status(self, symbol: str, status: ModelStatus) -> list[ModelRegistryEntry]`
- [ModelRegistry.list_all](../../risk_management/model_registry.py) — ligne 279 : `def list_all(self, symbol: str | None=None) -> list[ModelRegistryEntry]`
- [ModelRegistry.count_by_status](../../risk_management/model_registry.py) — ligne 286 : `def count_by_status(self) -> dict[str, int]`
- [ModelRegistry.to_dict](../../risk_management/model_registry.py) — ligne 295 : `def to_dict(self) -> dict[str, object]`
- [ModelRegistry.from_dict](../../risk_management/model_registry.py) — ligne 304 : `def from_dict(cls, data: dict[str, object]) -> 'ModelRegistry'`
- [ModelRegistry.save_to_json](../../risk_management/model_registry.py) — ligne 327 : `def save_to_json(self, path: str | None=None) -> str`
- [ModelRegistry.load_from_json](../../risk_management/model_registry.py) — ligne 353 : `def load_from_json(cls, path: str='artifacts/model_registry.json') -> 'ModelRegistry | None'`
- [ModelRegistry._demote_internal](../../risk_management/model_registry.py) — ligne 369 : `def _demote_internal(self, model_id: str, reason: str, now: datetime, target: ModelStatus=ModelStatus.DEGRADED) -> ModelRegistryEntry`
- [ModelRegistry._promote_to_champion](../../risk_management/model_registry.py) — ligne 396 : `def _promote_to_champion(self, model_id: str, reason: str) -> ModelRegistryEntry`
- [create_model_entry](../../risk_management/model_registry.py) — ligne 420 : `def create_model_entry(model_id: str, symbol: str, *, architecture: str='lightgbm', version: int=1, status: ModelStatus=ModelStatus.CANDIDATE, fingerprint: str='') -> ModelRegistryEntry`
- [rollback_persisted_registry](../../risk_management/model_registry.py) — ligne 440 : `def rollback_persisted_registry(*, symbol: str, reason: str, operator: str, registry_path: str='artifacts/model_registry.json', journal_path: str='artifacts/model_registry_journal.json') -> ModelRegistryEntry`

## `risk_management/models.py`

Source SHA-256 : `f1799f999ada1d89804fe843d8f25105b1037acbc88357c5974222b36b81e7c3`

- [FactorExposures](../../risk_management/models.py) — ligne 16 : `class FactorExposures`
- [SelectionScore](../../risk_management/models.py) — ligne 35 : `class SelectionScore`
- [PriceInfo](../../risk_management/models.py) — ligne 72 : `class PriceInfo`
- [SizingResult](../../risk_management/models.py) — ligne 85 : `class SizingResult`
- [PortfolioEntry](../../risk_management/models.py) — ligne 93 : `class PortfolioEntry`
- [PredictionInfo](../../risk_management/models.py) — ligne 156 : `class PredictionInfo`
- [WinRateInfo](../../risk_management/models.py) — ligne 183 : `class WinRateInfo`
- [DirectionalWinRateInfo](../../risk_management/models.py) — ligne 193 : `class DirectionalWinRateInfo`
- [DirectionalWinRateInfo.__post_init__](../../risk_management/models.py) — ligne 231 : `def __post_init__(self) -> None`
- [CorrelationRejection](../../risk_management/models.py) — ligne 241 : `class CorrelationRejection`
- [EnrichedSelection](../../risk_management/models.py) — ligne 250 : `class EnrichedSelection`
- [AccountRiskSnapshot](../../risk_management/models.py) — ligne 283 : `class AccountRiskSnapshot`
- [RiskDecisionRow](../../risk_management/models.py) — ligne 298 : `class RiskDecisionRow`
- [PortfolioTargetRow](../../risk_management/models.py) — ligne 317 : `class PortfolioTargetRow`

## `risk_management/operational_controls.py`

Source SHA-256 : `d57f1811ec2c3167d45137b3e7ba5c517a1c7297c99137cf0112aa8d21d42395`

- [ControlFrequency](../../risk_management/operational_controls.py) — ligne 28 : `class ControlFrequency(StrEnum)`
- [ControlStatus](../../risk_management/operational_controls.py) — ligne 41 : `class ControlStatus(StrEnum)`
- [SmokeTest](../../risk_management/operational_controls.py) — ligne 52 : `class SmokeTest`
- [SmokeTest.is_blocking](../../risk_management/operational_controls.py) — ligne 64 : `def is_blocking(self) -> bool`
- [SmokeTest.to_dict](../../risk_management/operational_controls.py) — ligne 68 : `def to_dict(self) -> dict[str, object]`
- [ControlResult](../../risk_management/operational_controls.py) — ligne 82 : `class ControlResult`
- [ControlResult.is_blocking](../../risk_management/operational_controls.py) — ligne 94 : `def is_blocking(self) -> bool`
- [ControlResult.to_dict](../../risk_management/operational_controls.py) — ligne 97 : `def to_dict(self) -> dict[str, object]`
- [ControlSchedule](../../risk_management/operational_controls.py) — ligne 112 : `class ControlSchedule`
- [ControlSchedule.get_controls](../../risk_management/operational_controls.py) — ligne 162 : `def get_controls(self, frequency: ControlFrequency) -> tuple[str, ...]`
- [ControlSchedule.get_smoke_tests](../../risk_management/operational_controls.py) — ligne 171 : `def get_smoke_tests(self) -> tuple[SmokeTest, ...]`
- [OperationalControls](../../risk_management/operational_controls.py) — ligne 179 : `class OperationalControls`
- [OperationalControls.run_smoke_tests](../../risk_management/operational_controls.py) — ligne 189 : `def run_smoke_tests(self, *, connectivity_ok: bool=True, data_fresh_ok: bool=True, kill_switch_ok: bool=True, circuit_breaker_ok: bool=True, ml_ready: bool=True, cash_ok: bool=True, watcher_ok: bool=True) -> tuple[bool, list[SmokeTest]]`
- [OperationalControls.record_control](../../risk_management/operational_controls.py) — ligne 234 : `def record_control(self, control_id: str, name: str, frequency: ControlFrequency, passed: bool, detail: str='') -> ControlResult`
- [OperationalControls.daily_checks_passed](../../risk_management/operational_controls.py) — ligne 255 : `def daily_checks_passed(self, date_check: date | None=None) -> tuple[bool, list[ControlResult]]`
- [OperationalControls.is_ready_to_trade](../../risk_management/operational_controls.py) — ligne 261 : `def is_ready_to_trade(self) -> tuple[bool, str]`
- [OperationalControls.summary](../../risk_management/operational_controls.py) — ligne 283 : `def summary(self) -> dict[str, object]`
- [run_pre_session_smoke_tests](../../risk_management/operational_controls.py) — ligne 302 : `def run_pre_session_smoke_tests(*, connectivity_ok: bool=True, data_fresh_ok: bool=True, kill_switch_ok: bool=True, circuit_breaker_ok: bool=True, ml_ready: bool=True, cash_ok: bool=True, watcher_ok: bool=True) -> tuple[bool, list[SmokeTest]]`
- [build_operational_probes](../../risk_management/operational_controls.py) — ligne 327 : `def build_operational_probes(*, broker: object | None=None, circuit_breaker: object | None=None, config: object | None=None, trade_date: date | None=None, model_registry_path: str='artifacts/model_registry.json', require_broker: bool=False, require_model_registry: bool=False, watcher_healthy: bool | None=None, require_watcher: bool=False) -> dict[str, bool]`
- [persist_ramp_up_transition](../../risk_management/operational_controls.py) — ligne 424 : `def persist_ramp_up_transition(*, from_stage: str, to_stage: str, approved_by: str, reason: str='', metrics_snapshot: dict[str, object] | None=None, journal_path: str='artifacts/ramp_up_journal.json') -> str`

## `risk_management/operational_data.py`

Source SHA-256 : `7dcafb2cf63ec3691185a6dd9e5415c61bb84a1d8a78c0c2fa6da2e680a37dce`

- [OperationalDataUnavailable](../../risk_management/operational_data.py) — ligne 19 : `class OperationalDataUnavailable(RuntimeError)`
- [OperationalAccountSnapshot](../../risk_management/operational_data.py) — ligne 24 : `class OperationalAccountSnapshot`
- [OperationalDataSnapshot](../../risk_management/operational_data.py) — ligne 37 : `class OperationalDataSnapshot`
- [OperationalDataSnapshot.from_raw](../../risk_management/operational_data.py) — ligne 47 : `def from_raw(cls, *, account_id: str, account: Mapping[str, Any], positions: Iterable[Mapping[str, Any]], orders: Iterable[Mapping[str, Any]], fills: Iterable[ExecutionFill]=(), source: str, as_of: datetime | None=None) -> 'OperationalDataSnapshot'`
- [LiveBrokerOperationalDataAdapter](../../risk_management/operational_data.py) — ligne 86 : `class LiveBrokerOperationalDataAdapter`
- [LiveBrokerOperationalDataAdapter.__init__](../../risk_management/operational_data.py) — ligne 89 : `def __init__(self, broker: BrokerAdapter, *, account_id: str, broker_mode: str) -> None`
- [LiveBrokerOperationalDataAdapter.capture](../../risk_management/operational_data.py) — ligne 94 : `def capture(self, *, fills: Iterable[ExecutionFill]=()) -> OperationalDataSnapshot`
- [BacktestOperationalDataAdapter](../../risk_management/operational_data.py) — ligne 113 : `class BacktestOperationalDataAdapter`
- [BacktestOperationalDataAdapter.build](../../risk_management/operational_data.py) — ligne 117 : `def build(*, account_id: str, account: Mapping[str, Any], positions: Iterable[Mapping[str, Any]]=(), orders: Iterable[Mapping[str, Any]]=(), fills: Iterable[ExecutionFill]=(), as_of: datetime, source: str='backtest_historical_snapshot') -> OperationalDataSnapshot`
- [_normalize_account](../../risk_management/operational_data.py) — ligne 138 : `def _normalize_account(account_id: str, account: Mapping[str, Any], as_of: datetime, source: str) -> OperationalAccountSnapshot`
- [_normalize_position](../../risk_management/operational_data.py) — ligne 159 : `def _normalize_position(raw: Mapping[str, Any]) -> OpenPosition`
- [_normalize_order](../../risk_management/operational_data.py) — ligne 177 : `def _normalize_order(raw: Mapping[str, Any]) -> OpenOrder`
- [_is_open_order](../../risk_management/operational_data.py) — ligne 194 : `def _is_open_order(raw: Mapping[str, Any]) -> bool`
- [_required_positive_float](../../risk_management/operational_data.py) — ligne 200 : `def _required_positive_float(raw: Mapping[str, Any], key: str) -> float`
- [_required_non_negative_float](../../risk_management/operational_data.py) — ligne 207 : `def _required_non_negative_float(raw: Mapping[str, Any], key: str) -> float`
- [_optional_float](../../risk_management/operational_data.py) — ligne 214 : `def _optional_float(value: Any, *, default: float) -> float`

## `risk_management/portfolio_builder.py`

Source SHA-256 : `d557f00a7519ed436b478464df57b8565f2ef610d68ea1dc1de24609ed1b4fd7`

- [compute_allocation_factors](../../risk_management/portfolio_builder.py) — ligne 55 : `def compute_allocation_factors(retained: list[EnrichedSelection], sizing_cfg: object, max_positions: int) -> dict[str, float]`
- [_apply_regime_scoring_to_candidates](../../risk_management/portfolio_builder.py) — ligne 82 : `def _apply_regime_scoring_to_candidates(candidates: list[SelectionScore], regime_snapshot: object, rotation_state: object | None=None) -> list[SelectionScore]`
- [_apply_concentration_filters](../../risk_management/portfolio_builder.py) — ligne 196 : `def _apply_concentration_filters(candidates: list[SelectionScore], *, trade_tracker: object, loss_tracker: object, trade_date: date) -> list[SelectionScore]`
- [_enforce_net_exposure_neutrality](../../risk_management/portfolio_builder.py) — ligne 231 : `def _enforce_net_exposure_neutrality(accepted_entries: list[PortfolioEntry], *, equity: float, target: float, tolerance: float) -> list[PortfolioEntry]`
- [PortfolioBuilder](../../risk_management/portfolio_builder.py) — ligne 332 : `class PortfolioBuilder`
- [PortfolioBuilder.__init__](../../risk_management/portfolio_builder.py) — ligne 335 : `def __init__(self, config: RiskConfig, pnl: PnLSnapshot | None=None, circuit_breaker: CircuitBreaker | None=None, regime_snapshot: object | None=None, rotation_state: object | None=None, breakout_tracker: object | None=None, regime_transition: RegimeTransition | None=None, factor_exposures: dict[str, object] | None=None, factor_covariance: object | None=None, sector_map: dict[str, str] | None=None, concentration_trade_tracker: SymbolTradeTracker | None=None, concentration_loss_tracker: ConsecutiveLossTracker | None=None) -> None`
- [PortfolioBuilder.set_directional_win_rates](../../risk_management/portfolio_builder.py) — ligne 392 : `def set_directional_win_rates(self, directional_win_rates: Mapping[str | tuple[str, str], DirectionalWinRateInfo]) -> None`
- [PortfolioBuilder.set_liquidity_data](../../risk_management/portfolio_builder.py) — ligne 399 : `def set_liquidity_data(self, liquidity_gate: LiquidityGate, *, spread_snapshots: Mapping[str, SpreadSnapshot], borrow_snapshots: Mapping[str, BorrowSnapshot]) -> None`
- [PortfolioBuilder.set_portfolio_optimization](../../risk_management/portfolio_builder.py) — ligne 411 : `def set_portfolio_optimization(self, optimizer: PortfolioOptimizer, *, holdings: tuple[HoldingSnapshot, ...], covariance: np.ndarray | None, edge_by_symbol: Mapping[str, float]) -> None`
- [PortfolioBuilder.set_operational_snapshot](../../risk_management/portfolio_builder.py) — ligne 432 : `def set_operational_snapshot(self, snapshot: object) -> None`
- [PortfolioBuilder.operational_snapshot](../../risk_management/portfolio_builder.py) — ligne 455 : `def operational_snapshot(self) -> object | None`
- [PortfolioBuilder._emit_progress](../../risk_management/portfolio_builder.py) — ligne 459 : `def _emit_progress(self, summary: dict[str, object], *, current: int, total: int, label: str, phase: str, item: str | None=None, unit: str='candidats') -> None`
- [PortfolioBuilder._build_enriched_candidates](../../risk_management/portfolio_builder.py) — ligne 484 : `def _build_enriched_candidates(self, candidates: list[SelectionScore], predictions: dict[str, PredictionInfo], win_rates: dict[str, WinRateInfo], *, oracle_long_only: bool=False) -> list[EnrichedSelection]`
- [PortfolioBuilder._build_enriched_from_ml_candidates](../../risk_management/portfolio_builder.py) — ligne 568 : `def _build_enriched_from_ml_candidates(self, ml_candidates: list[MLRankedCandidate], win_rates: dict[str, WinRateInfo]) -> list[EnrichedSelection]`
- [PortfolioBuilder.build_from_ml_candidates](../../risk_management/portfolio_builder.py) — ligne 624 : `def build_from_ml_candidates(self, ml_candidates: list[MLRankedCandidate], prices: dict[str, PriceInfo], *, win_rates: dict[str, WinRateInfo] | None=None, directional_win_rates: Mapping[str | tuple[str, str], DirectionalWinRateInfo] | None=None, return_matrix: DataFrame | None=None, trade_date: date | None=None) -> list[PortfolioEntry]`
- [PortfolioBuilder.build](../../risk_management/portfolio_builder.py) — ligne 694 : `def build(self, candidates: list[SelectionScore], prices: dict[str, PriceInfo], predictions: dict[str, PredictionInfo] | None=None, win_rates: dict[str, WinRateInfo] | None=None, return_matrix: DataFrame | None=None, trade_date: date | None=None, directional_win_rates: Mapping[str | tuple[str, str], DirectionalWinRateInfo] | None=None, *, selection_policy: str='directional') -> list[PortfolioEntry]`
- [PortfolioBuilder._apply_portfolio_optimization](../../risk_management/portfolio_builder.py) — ligne 1520 : `def _apply_portfolio_optimization(self, entries: list[PortfolioEntry], equity: float) -> list[PortfolioEntry]`
- [PortfolioBuilder._make_entry_v2](../../risk_management/portfolio_builder.py) — ligne 1612 : `def _make_entry_v2(ec: EnrichedSelection, pi: PriceInfo | None, proposed: float, approved: float, decision: Decision, reason: str, decision_reason_code: DecisionReasonCode | None=None, sizing_method: SizingMethod=SizingMethod.UNKNOWN, correlation_blocker: str | None=None, correlation_value: float | None=None, *, trade_date: date | None=None, entry_date: date | None=None) -> PortfolioEntry`

## `risk_management/portfolio_optimizer.py`

Source SHA-256 : `428aab00721ea540e6fe765b879a313922e945830ea12b45defce5c74063c53b`

- [HoldingSnapshot](../../risk_management/portfolio_optimizer.py) — ligne 32 : `class HoldingSnapshot`
- [HoldingSnapshot.__post_init__](../../risk_management/portfolio_optimizer.py) — ligne 75 : `def __post_init__(self) -> None`
- [HoldingSnapshot.notional](../../risk_management/portfolio_optimizer.py) — ligne 80 : `def notional(self) -> float`
- [HoldingSnapshot.signed_notional](../../risk_management/portfolio_optimizer.py) — ligne 84 : `def signed_notional(self) -> float`
- [NoTradeBand](../../risk_management/portfolio_optimizer.py) — ligne 93 : `class NoTradeBand`
- [NoTradeBand.should_skip_trade](../../risk_management/portfolio_optimizer.py) — ligne 113 : `def should_skip_trade(self, current_quantity: float, target_quantity: float, price: float) -> tuple[bool, str | None]`
- [TurnoverCosts](../../risk_management/portfolio_optimizer.py) — ligne 143 : `class TurnoverCosts`
- [TurnoverCosts.cost_of_trade](../../risk_management/portfolio_optimizer.py) — ligne 163 : `def cost_of_trade(self, notional: float, adv_usd: float | None=None) -> float`
- [TurnoverCosts.cost_of_rebalance](../../risk_management/portfolio_optimizer.py) — ligne 184 : `def cost_of_rebalance(self, current_notional: float, target_notional: float, adv_usd: float | None=None) -> float`
- [TurnoverCosts.annualized_turnover_impact](../../risk_management/portfolio_optimizer.py) — ligne 199 : `def annualized_turnover_impact(self, daily_turnover_pct: float, trading_days: int=252) -> float`
- [MarginalRiskDecomposition](../../risk_management/portfolio_optimizer.py) — ligne 212 : `class MarginalRiskDecomposition`
- [MarginalRiskDecomposition.to_dict](../../risk_management/portfolio_optimizer.py) — ligne 243 : `def to_dict(self) -> dict[str, object]`
- [compute_mctr](../../risk_management/portfolio_optimizer.py) — ligne 256 : `def compute_mctr(weights: np.ndarray, covariance: np.ndarray, symbols: list[str]) -> MarginalRiskDecomposition`
- [OptimizationResult](../../risk_management/portfolio_optimizer.py) — ligne 319 : `class OptimizationResult`
- [OptimizationResult.to_dict](../../risk_management/portfolio_optimizer.py) — ligne 360 : `def to_dict(self) -> dict[str, object]`
- [PortfolioOptimizer](../../risk_management/portfolio_optimizer.py) — ligne 380 : `class PortfolioOptimizer`
- [PortfolioOptimizer.optimize](../../risk_management/portfolio_optimizer.py) — ligne 411 : `def optimize(self, candidates: list[dict[str, Any]], existing_holdings: list[HoldingSnapshot] | None=None, *, account_equity: float=100000.0, covariance: np.ndarray | None=None) -> OptimizationResult`
- [PortfolioOptimizer._reduce_worst_candidate](../../risk_management/portfolio_optimizer.py) — ligne 696 : `def _reduce_worst_candidate(self, portfolio: dict[str, dict[str, Any]], audit: list[str]) -> float | None`
- [optimize_portfolio](../../risk_management/portfolio_optimizer.py) — ligne 738 : `def optimize_portfolio(candidates: list[dict[str, Any]], holdings: list[HoldingSnapshot] | None=None, *, account_equity: float=100000.0, max_positions: int=20) -> OptimizationResult`

## `risk_management/position_sizer.py`

Source SHA-256 : `60e4a553997ad09306cfccb3561c23a3c5d29d39ae4826da48590266b07d63ef`

- [PositionSizer](../../risk_management/position_sizer.py) — ligne 15 : `class PositionSizer`
- [PositionSizer.__init__](../../risk_management/position_sizer.py) — ligne 18 : `def __init__(self, config: RiskConfig) -> None`
- [PositionSizer.compute](../../risk_management/position_sizer.py) — ligne 21 : `def compute(self, price_info: PriceInfo) -> SizingResult`

## `risk_management/pre_live_checklist.py`

Source SHA-256 : `7952aa18fd68db96124f07ac3a8a6e0387632278ef211ac724738c64ed4820a2`

- [GateStatus](../../risk_management/pre_live_checklist.py) — ligne 23 : `class GateStatus(StrEnum)`
- [ChecklistGate](../../risk_management/pre_live_checklist.py) — ligne 37 : `class ChecklistGate`
- [ChecklistGate.is_blocking](../../risk_management/pre_live_checklist.py) — ligne 67 : `def is_blocking(self) -> bool`
- [ChecklistGate.to_dict](../../risk_management/pre_live_checklist.py) — ligne 71 : `def to_dict(self) -> dict[str, object]`
- [GoLiveGate](../../risk_management/pre_live_checklist.py) — ligne 88 : `class GoLiveGate`
- [GoLiveGate.go](../../risk_management/pre_live_checklist.py) — ligne 104 : `def go(self) -> bool`
- [GoLiveGate.to_dict](../../risk_management/pre_live_checklist.py) — ligne 107 : `def to_dict(self) -> dict[str, object]`
- [PreLiveChecklist](../../risk_management/pre_live_checklist.py) — ligne 125 : `class PreLiveChecklist`
- [PreLiveChecklist.build_checklist](../../risk_management/pre_live_checklist.py) — ligne 214 : `def build_checklist(self, stage: str) -> GoLiveGate`
- [PreLiveChecklist.evaluate](../../risk_management/pre_live_checklist.py) — ligne 235 : `def evaluate(self, gate_results: dict[str, GateStatus], stage: str='live_5pct') -> GoLiveGate`
- [PreLiveChecklist.gates_by_category](../../risk_management/pre_live_checklist.py) — ligne 286 : `def gates_by_category(self) -> dict[str, list[ChecklistGate]]`
- [PreLiveChecklist.gates_by_sprint](../../risk_management/pre_live_checklist.py) — ligne 293 : `def gates_by_sprint(self) -> dict[int, list[ChecklistGate]]`
- [build_pre_live_checklist](../../risk_management/pre_live_checklist.py) — ligne 304 : `def build_pre_live_checklist(stage: str='shadow') -> GoLiveGate`
- [evaluate_pre_live_gates](../../risk_management/pre_live_checklist.py) — ligne 310 : `def evaluate_pre_live_gates(gate_results: dict[str, GateStatus], stage: str='live_5pct') -> GoLiveGate`

## `risk_management/protection_contract.py`

Source SHA-256 : `7638e4ca77a0697646ddff1e851b31d37dd992433d5e73220a2bba350cb32029`

- [ProtectionStatus](../../risk_management/protection_contract.py) — ligne 23 : `class ProtectionStatus(StrEnum)`
- [ProtectionStatus.is_safe](../../risk_management/protection_contract.py) — ligne 35 : `def is_safe(self) -> bool`
- [ProtectionStatus.requires_action](../../risk_management/protection_contract.py) — ligne 40 : `def requires_action(self) -> bool`
- [ProtectionSLA](../../risk_management/protection_contract.py) — ligne 53 : `class ProtectionSLA`
- [ProtectionSLA.is_breached](../../risk_management/protection_contract.py) — ligne 64 : `def is_breached(self, status: ProtectionStatus, time_since_last_action: float) -> bool`
- [OCOGroup](../../risk_management/protection_contract.py) — ligne 85 : `class OCOGroup`
- [OCOGroup.is_complete](../../risk_management/protection_contract.py) — ligne 107 : `def is_complete(self) -> bool`
- [OCOGroup.is_orphan](../../risk_management/protection_contract.py) — ligne 115 : `def is_orphan(self) -> bool`
- [OCOGroup.quantity_match](../../risk_management/protection_contract.py) — ligne 123 : `def quantity_match(self) -> bool`
- [OCOGroup.to_dict](../../risk_management/protection_contract.py) — ligne 127 : `def to_dict(self) -> dict[str, object]`
- [ProtectionState](../../risk_management/protection_contract.py) — ligne 150 : `class ProtectionState`
- [ProtectionState.is_protected](../../risk_management/protection_contract.py) — ligne 171 : `def is_protected(self) -> bool`
- [ProtectionState.needs_repair](../../risk_management/protection_contract.py) — ligne 175 : `def needs_repair(self) -> bool`
- [ProtectionState.to_dict](../../risk_management/protection_contract.py) — ligne 178 : `def to_dict(self) -> dict[str, object]`
- [ProtectionContract](../../risk_management/protection_contract.py) — ligne 202 : `class ProtectionContract`
- [ProtectionContract.check_state](../../risk_management/protection_contract.py) — ligne 217 : `def check_state(self, state: ProtectionState) -> tuple[bool, list[str]]`
- [ProtectionContract.should_force_close](../../risk_management/protection_contract.py) — ligne 262 : `def should_force_close(self, state: ProtectionState, time_since_last_action: float) -> tuple[bool, str | None]`
- [ProtectionContract.resolve_conflicts](../../risk_management/protection_contract.py) — ligne 289 : `def resolve_conflicts(self, open_orders: list[dict[str, object]], force_close_symbol: str) -> list[str]`
- [check_protection_state](../../risk_management/protection_contract.py) — ligne 311 : `def check_protection_state(state: ProtectionState) -> tuple[bool, list[str]]`
- [build_oco_group](../../risk_management/protection_contract.py) — ligne 317 : `def build_oco_group(oco_id: str, symbol: str, side: str, parent_intent_id: str, filled_quantity: float, *, stop_order_id: str | None=None, tp_order_id: str | None=None) -> OCOGroup`

## `risk_management/regime_apply.py`

Source SHA-256 : `2d653cfa4dcd127f777da50188ded48cb34c33785b5c2bd2dbd1cbe39e9ae0c2`

- [apply_structural_market_guards](../../risk_management/regime_apply.py) — ligne 33 : `def apply_structural_market_guards(cfg: RiskConfig, *, market_regimes_config: 'MarketRegimesConfig | None', equity: float | None) -> RiskConfig`
- [apply_snapshot](../../risk_management/regime_apply.py) — ligne 73 : `def apply_snapshot(cfg: RiskConfig, snapshot: MarketRegimeSnapshot | None) -> RiskConfig`
- [apply_account_cp_policy](../../risk_management/regime_apply.py) — ligne 123 : `def apply_account_cp_policy(cfg: RiskConfig, *, account_long_only: bool) -> RiskConfig`
- [apply_transition](../../risk_management/regime_apply.py) — ligne 141 : `def apply_transition(cfg: RiskConfig, transition: RegimeTransition | None) -> RiskConfig`

## `risk_management/regime_state_machine.py`

Source SHA-256 : `e2bf57c6517b6eff9fdce3e3c96e21c31d88fbea66ef6d78822ea18484369302`

- [RegimeState](../../risk_management/regime_state_machine.py) — ligne 39 : `class RegimeState(StrEnum)`
- [RegimeState.is_defensive](../../risk_management/regime_state_machine.py) — ligne 56 : `def is_defensive(self) -> bool`
- [RegimeState.is_blocking_entries](../../risk_management/regime_state_machine.py) — ligne 66 : `def is_blocking_entries(self) -> bool`
- [RegimeState.allows_long](../../risk_management/regime_state_machine.py) — ligne 71 : `def allows_long(self) -> bool`
- [RegimeState.allows_short](../../risk_management/regime_state_machine.py) — ligne 75 : `def allows_short(self) -> bool`
- [RegimeState.requires_exit_management](../../risk_management/regime_state_machine.py) — ligne 83 : `def requires_exit_management(self) -> bool`
- [RegimeState.from_regime_mode](../../risk_management/regime_state_machine.py) — ligne 90 : `def from_regime_mode(cls, mode: str) -> RegimeState`
- [RegimeState.to_regime_mode](../../risk_management/regime_state_machine.py) — ligne 100 : `def to_regime_mode(self) -> str`
- [TransitionAction](../../risk_management/regime_state_machine.py) — ligne 116 : `class TransitionAction(StrEnum)`
- [TransitionAction.is_destructive](../../risk_management/regime_state_machine.py) — ligne 133 : `def is_destructive(self) -> bool`
- [TransitionAction.blocks_new_entries](../../risk_management/regime_state_machine.py) — ligne 143 : `def blocks_new_entries(self) -> bool`
- [RegimeTransition](../../risk_management/regime_state_machine.py) — ligne 157 : `class RegimeTransition`
- [RegimeTransition.is_transition](../../risk_management/regime_state_machine.py) — ligne 199 : `def is_transition(self) -> bool`
- [RegimeTransition.is_escalation](../../risk_management/regime_state_machine.py) — ligne 204 : `def is_escalation(self) -> bool`
- [RegimeTransition.is_deescalation](../../risk_management/regime_state_machine.py) — ligne 217 : `def is_deescalation(self) -> bool`
- [RegimeTransition.to_dict](../../risk_management/regime_state_machine.py) — ligne 221 : `def to_dict(self) -> dict[str, object]`
- [RegimeStateMachine](../../risk_management/regime_state_machine.py) — ligne 243 : `class RegimeStateMachine`
- [RegimeStateMachine.evaluate_transition](../../risk_management/regime_state_machine.py) — ligne 266 : `def evaluate_transition(self, current_state: RegimeState, target_state: RegimeState, *, days_in_current_mode: int=0, soft_entry_streak: int=0, soft_exit_streak: int=0, hard_calm_streak: int=0, hard_triggered: bool=False, hard_trigger_immediate: bool=True) -> RegimeTransition`
- [RegimeStateMachine.evaluate_from_snapshot](../../risk_management/regime_state_machine.py) — ligne 408 : `def evaluate_from_snapshot(self, previous_state: RegimeState, snapshot: MarketRegimeSnapshot) -> RegimeTransition`
- [RegimeStateMachine._build_escalation](../../risk_management/regime_state_machine.py) — ligne 458 : `def _build_escalation(self, from_state: RegimeState, to_state: RegimeState, *, reason: str, hysteresis_applied: bool=False) -> RegimeTransition`
- [RegimeStateMachine._build_deescalation](../../risk_management/regime_state_machine.py) — ligne 481 : `def _build_deescalation(self, from_state: RegimeState, *, reason: str, hysteresis_applied: bool=False) -> RegimeTransition`
- [RegimeStateMachine._action_for_state](../../risk_management/regime_state_machine.py) — ligne 503 : `def _action_for_state(state: RegimeState) -> TransitionAction`
- [RegimeStateMachine._risk_multiplier_for_state](../../risk_management/regime_state_machine.py) — ligne 516 : `def _risk_multiplier_for_state(state: RegimeState) -> float`
- [RegimeStateMachine._max_gross_for_state](../../risk_management/regime_state_machine.py) — ligne 528 : `def _max_gross_for_state(state: RegimeState) -> float | None`
- [compute_regime_transition](../../risk_management/regime_state_machine.py) — ligne 543 : `def compute_regime_transition(previous_mode: str, current_snapshot: MarketRegimeSnapshot, *, min_hold_days: int=5) -> RegimeTransition`

## `risk_management/risk_checker.py`

Source SHA-256 : `0b7914dbedc0ab60348ea93fecf3b11b996c4fd9f5a172ccdf3ca09046f96882`

- [RiskCheckerImpl](../../risk_management/risk_checker.py) — ligne 15 : `class RiskCheckerImpl`
- [RiskCheckerImpl.__init__](../../risk_management/risk_checker.py) — ligne 18 : `def __init__(self, config: RiskConfig, state: PortfolioState | None=None, pnl: PnLSnapshot | None=None, sector_map: dict[str, str] | None=None, circuit_breaker: CircuitBreaker | None=None) -> None`
- [RiskCheckerImpl.set_sector_corr_map](../../risk_management/risk_checker.py) — ligne 34 : `def set_sector_corr_map(self, corr_map: dict[str, dict[str, float]] | None) -> None`
- [RiskCheckerImpl.check_position_size](../../risk_management/risk_checker.py) — ligne 43 : `def check_position_size(self, symbol: str, proposed_shares: float, price: float, *, side: str='buy', adv_usd: float | None=None, selection_rank: int | None=None) -> float`
- [RiskCheckerImpl.is_circuit_breaker_active](../../risk_management/risk_checker.py) — ligne 83 : `def is_circuit_breaker_active(self) -> bool`
- [RiskCheckerImpl.get_last_decision_reason](../../risk_management/risk_checker.py) — ligne 86 : `def get_last_decision_reason(self) -> str`
- [RiskCheckerImpl.get_last_decision_reason_code](../../risk_management/risk_checker.py) — ligne 89 : `def get_last_decision_reason_code(self) -> DecisionReasonCode`
- [RiskCheckerImpl.accept](../../risk_management/risk_checker.py) — ligne 93 : `def accept(self, symbol: str, sector: str, shares: float, price: float, *, side: str='buy') -> None`

## `risk_management/run_risk.py`

Source SHA-256 : `7185a1f6cead630b3c356aa830e38da0c03b4cbbcba9b399de97e3b0dd4cf361`

Module sans déclaration publique/privée de classe ou fonction au niveau module.

## `risk_management/selection_contract.py`

Source SHA-256 : `8ea9b3963da4003f225fcb6704009563008dcbe6c1d7a68772b5f61a2ce71855`

- [MLRankedCandidate](../../risk_management/selection_contract.py) — ligne 33 : `class MLRankedCandidate`
- [MLRankedCandidate.__post_init__](../../risk_management/selection_contract.py) — ligne 87 : `def __post_init__(self) -> None`
- [MLRankedCandidate.is_actionable](../../risk_management/selection_contract.py) — ligne 106 : `def is_actionable(self) -> bool`
- [MLRankedCandidate.to_dict](../../risk_management/selection_contract.py) — ligne 110 : `def to_dict(self) -> dict[str, object]`
- [SelectorVetoContext](../../risk_management/selection_contract.py) — ligne 133 : `class SelectorVetoContext`
- [SelectorVetoContext.__post_init__](../../risk_management/selection_contract.py) — ligne 167 : `def __post_init__(self) -> None`
- [RiskDecisionInput](../../risk_management/selection_contract.py) — ligne 177 : `class RiskDecisionInput`
- [RiskDecisionInput.symbol](../../risk_management/selection_contract.py) — ligne 190 : `def symbol(self) -> str`
- [RiskDecisionInput.side](../../risk_management/selection_contract.py) — ligne 194 : `def side(self) -> str`
- [RiskDecisionInput.is_vetoed](../../risk_management/selection_contract.py) — ligne 198 : `def is_vetoed(self) -> bool`
- [RiskDecisionInput.veto_reason](../../risk_management/selection_contract.py) — ligne 202 : `def veto_reason(self) -> str | None`
- [build_rankings](../../risk_management/selection_contract.py) — ligne 210 : `def build_rankings(candidates: list[MLRankedCandidate]) -> tuple[list[MLRankedCandidate], list[MLRankedCandidate]]`
- [filter_actionable](../../risk_management/selection_contract.py) — ligne 240 : `def filter_actionable(candidates: list[MLRankedCandidate]) -> list[MLRankedCandidate]`
- [validate_candidate_consistency](../../risk_management/selection_contract.py) — ligne 248 : `def validate_candidate_consistency(candidate: MLRankedCandidate) -> list[str]`
- [build_candidate_from_prediction](../../risk_management/selection_contract.py) — ligne 289 : `def build_candidate_from_prediction(*, symbol: str, trade_date: date, predicted_side: str | None, proba_long: float | None, proba_flat: float | None, proba_short: float | None, proba: float, model_run_id: str, policy_version: int=1, universe_run_id: str | None=None, feature_cutoff: datetime | None=None, decision_cutoff: datetime | None=None, research_only: bool=False) -> MLRankedCandidate`
- [compute_entry_date](../../risk_management/selection_contract.py) — ligne 352 : `def compute_entry_date(decision_date: date) -> date`
- [validate_decision_timing](../../risk_management/selection_contract.py) — ligne 366 : `def validate_decision_timing(candidate: MLRankedCandidate, *, decision_date: date | None=None) -> list[str]`
- [assert_valid_entry_timing](../../risk_management/selection_contract.py) — ligne 427 : `def assert_valid_entry_timing(candidate: MLRankedCandidate, *, decision_date: date | None=None) -> None`
- [to_selection_score](../../risk_management/selection_contract.py) — ligne 454 : `def to_selection_score(candidate: MLRankedCandidate, *, sector: str='Unknown', snapshot_date: date | None=None, selector_signal_mode: str | None=None, selection_explanation: str | None=None, selector_earnings_blackout: int=0) -> Any`
- [validate_payload_completeness](../../risk_management/selection_contract.py) — ligne 516 : `def validate_payload_completeness(candidate: MLRankedCandidate) -> list[str]`

## `risk_management/shadow_compare.py`

Source SHA-256 : `6ec562900e3cefde10858ec85cafab543ef28daff63a8b8ddc6ccf8bf409383f`

- [_number_or_none](../../risk_management/shadow_compare.py) — ligne 29 : `def _number_or_none(row: pd.Series, key: str) -> float | None`
- [ShadowDriftReport](../../risk_management/shadow_compare.py) — ligne 37 : `class ShadowDriftReport`
- [ShadowDriftReport.to_payload](../../risk_management/shadow_compare.py) — ligne 47 : `def to_payload(self) -> dict[str, Any]`
- [compare_runs](../../risk_management/shadow_compare.py) — ligne 61 : `def compare_runs(live_orders: pd.DataFrame, simulated_orders: pd.DataFrame, *, live_run_id: str, simulated_run_id: str, qty_col: str='qty', price_col: str='price', conviction_col: str='conviction', symbol_col: str='symbol') -> ShadowDriftReport`
- [_normalize](../../risk_management/shadow_compare.py) — ligne 134 : `def _normalize(df: pd.DataFrame, symbol_col: str, qty_col: str, price_col: str, conviction_col: str) -> pd.DataFrame`
- [persist_shadow_run](../../risk_management/shadow_compare.py) — ligne 160 : `def persist_shadow_run(report: ShadowDriftReport, *, engine: Any, run_id: str | None=None) -> str`

## `risk_management/shadow_engine.py`

Source SHA-256 : `9c78c59630ac960dac063b67a711737bbccb71a18d53ec89edfb4872a9192efa`

- [ShadowRunStatus](../../risk_management/shadow_engine.py) — ligne 26 : `class ShadowRunStatus(StrEnum)`
- [ShadowDecision](../../risk_management/shadow_engine.py) — ligne 41 : `class ShadowDecision`
- [ShadowDecision.is_divergent](../../risk_management/shadow_engine.py) — ligne 63 : `def is_divergent(self) -> bool`
- [ShadowDecision.to_dict](../../risk_management/shadow_engine.py) — ligne 67 : `def to_dict(self) -> dict[str, object]`
- [ShadowComparisonReport](../../risk_management/shadow_engine.py) — ligne 86 : `class ShadowComparisonReport`
- [ShadowComparisonReport.divergence_rate](../../risk_management/shadow_engine.py) — ligne 124 : `def divergence_rate(self) -> float`
- [ShadowComparisonReport.is_convergent](../../risk_management/shadow_engine.py) — ligne 132 : `def is_convergent(self) -> bool`
- [ShadowComparisonReport.side_divergence_rate](../../risk_management/shadow_engine.py) — ligne 137 : `def side_divergence_rate(self) -> float`
- [ShadowComparisonReport.to_dict](../../risk_management/shadow_engine.py) — ligne 142 : `def to_dict(self) -> dict[str, object]`
- [SimulatedFill](../../risk_management/shadow_engine.py) — ligne 164 : `class SimulatedFill`
- [SimulatedFill.fill_rate](../../risk_management/shadow_engine.py) — ligne 180 : `def fill_rate(self) -> float`
- [SimulatedFill.to_dict](../../risk_management/shadow_engine.py) — ligne 185 : `def to_dict(self) -> dict[str, object]`
- [ShadowFillSimulator](../../risk_management/shadow_engine.py) — ligne 199 : `class ShadowFillSimulator`
- [ShadowFillSimulator.simulate_fill](../../risk_management/shadow_engine.py) — ligne 214 : `def simulate_fill(self, symbol: str, side: str, requested_shares: float, *, entry_price: float, bid: float | None=None, ask: float | None=None, adv_usd: float | None=None) -> SimulatedFill`
- [ShadowEngine](../../risk_management/shadow_engine.py) — ligne 300 : `class ShadowEngine`
- [ShadowEngine.compare](../../risk_management/shadow_engine.py) — ligne 311 : `def compare(self, shadow_run_id: str, live_run_id: str, *, shadow_decisions: list[dict[str, object]], live_decisions: list[dict[str, object]]) -> ShadowComparisonReport`
- [ShadowEngine.validate_shadow](../../risk_management/shadow_engine.py) — ligne 432 : `def validate_shadow(self, report: ShadowComparisonReport, *, max_side_divergence_rate: float=0.0, max_shares_delta_pct: float=0.05) -> tuple[bool, str]`
- [compare_shadow_to_live](../../risk_management/shadow_engine.py) — ligne 464 : `def compare_shadow_to_live(shadow_run_id: str, live_run_id: str, shadow_decisions: list[dict[str, object]], live_decisions: list[dict[str, object]]) -> ShadowComparisonReport`

## `risk_management/stop_calculator.py`

Source SHA-256 : `4abddbb3a70f69814d89afbb662cf7ec6324ea69b23b52801a4ebdcb46d8e2fc`

- [StopLevels](../../risk_management/stop_calculator.py) — ligne 28 : `class StopLevels`
- [StopLevels.__post_init__](../../risk_management/stop_calculator.py) — ligne 77 : `def __post_init__(self) -> None`
- [StopLevels.is_valid](../../risk_management/stop_calculator.py) — ligne 82 : `def is_valid(self) -> bool`
- [StopLevels.is_tp_valid](../../risk_management/stop_calculator.py) — ligne 90 : `def is_tp_valid(self) -> bool | None`
- [StopLevels.recalculate_after_fill](../../risk_management/stop_calculator.py) — ligne 99 : `def recalculate_after_fill(self, fill_price: float, fill_quantity: float) -> 'StopLevels'`
- [StopLevels.to_dict](../../risk_management/stop_calculator.py) — ligne 155 : `def to_dict(self) -> dict[str, object]`
- [StopCalculator](../../risk_management/stop_calculator.py) — ligne 176 : `class StopCalculator`
- [StopCalculator.compute](../../risk_management/stop_calculator.py) — ligne 205 : `def compute(self, symbol: str, side: str, entry_price: float, *, atr: float | None=None, quantity: float | None=None, is_defensive_regime: bool=False) -> StopLevels`
- [StopCalculator.compute_for_position](../../risk_management/stop_calculator.py) — ligne 307 : `def compute_for_position(self, symbol: str, side: str, entry_price: float, atr: float | None=None, quantity: float | None=None, *, is_defensive_regime: bool=False) -> StopLevels`
- [compute_initial_stop_price](../../risk_management/stop_calculator.py) — ligne 331 : `def compute_initial_stop_price(side: str, entry_price: float, atr: float | None=None, *, atr_stop_multiple: float=2.0, min_stop_pct: float=0.005, max_stop_pct: float=0.15) -> float`
- [compute_stop_distance_pct](../../risk_management/stop_calculator.py) — ligne 370 : `def compute_stop_distance_pct(atr: float, entry_price: float, atr_stop_multiple: float=2.0) -> float`
- [is_stop_valid](../../risk_management/stop_calculator.py) — ligne 381 : `def is_stop_valid(side: str, entry_price: float, stop_price: float) -> bool`

## `risk_management/transition_handler.py`

Source SHA-256 : `3611be105983b8941bcde2f329b1d170cb2deecef64e284d9749e0d02d90ac03`

- [OrderAction](../../risk_management/transition_handler.py) — ligne 32 : `class OrderAction(StrEnum)`
- [TransitionStep](../../risk_management/transition_handler.py) — ligne 46 : `class TransitionStep`
- [TransitionStep.__post_init__](../../risk_management/transition_handler.py) — ligne 75 : `def __post_init__(self) -> None`
- [TransitionStep.is_destructive](../../risk_management/transition_handler.py) — ligne 80 : `def is_destructive(self) -> bool`
- [PositionTransitionPlan](../../risk_management/transition_handler.py) — ligne 88 : `class PositionTransitionPlan`
- [PositionTransitionPlan.has_actions](../../risk_management/transition_handler.py) — ligne 112 : `def has_actions(self) -> bool`
- [PositionTransitionPlan.is_empty](../../risk_management/transition_handler.py) — ligne 116 : `def is_empty(self) -> bool`
- [OpenPosition](../../risk_management/transition_handler.py) — ligne 124 : `class OpenPosition`
- [OpenPosition.__post_init__](../../risk_management/transition_handler.py) — ligne 140 : `def __post_init__(self) -> None`
- [OpenOrder](../../risk_management/transition_handler.py) — ligne 148 : `class OpenOrder`
- [OpenOrder.__post_init__](../../risk_management/transition_handler.py) — ligne 159 : `def __post_init__(self) -> None`
- [OpenOrder.has_partial_fill](../../risk_management/transition_handler.py) — ligne 164 : `def has_partial_fill(self) -> bool`
- [TransitionHandler](../../risk_management/transition_handler.py) — ligne 172 : `class TransitionHandler`
- [TransitionHandler.build_plan](../../risk_management/transition_handler.py) — ligne 186 : `def build_plan(self, transition: RegimeTransition, positions: list[OpenPosition], orders: list[OpenOrder]) -> PositionTransitionPlan`
- [TransitionHandler.no_op_plan](../../risk_management/transition_handler.py) — ligne 323 : `def no_op_plan(transition: RegimeTransition) -> PositionTransitionPlan`
- [build_transition_plan](../../risk_management/transition_handler.py) — ligne 334 : `def build_transition_plan(transition: RegimeTransition, positions: list[OpenPosition] | None=None, orders: list[OpenOrder] | None=None) -> PositionTransitionPlan`
