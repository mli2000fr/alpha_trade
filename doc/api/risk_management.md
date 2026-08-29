# Inventaire API — risk_management

Cet inventaire est dérivé des signatures présentes dans le code. Les symboles préfixés par `_` restent internes. Les numéros de ligne sont indicatifs ; le chemin et le nom du symbole sont les repères stables.

## `risk_management/abstention.py`

- ligne 233 — `def evaluate_abstention_veto(`
- ligne 35 — `class AbstentionDecision:`
- ligne 60 — `class AbstentionPolicy:`
## `risk_management/audit.py`

- ligne 101 — `def persist_decisions(`
- ligne 189 — `def persist_portfolio_targets(`
- ligne 26 — `def build_run_id() -> str:`
- ligne 31 — `def persist_decision_audit_log(`
## `risk_management/batch_diagnostics.py`

- ligne 104 — `def _resolve_prefer_set(filters: BatchFilters, prefer_top_n: int) -> frozenset[str]:`
- ligne 121 — `def boost_candidate_scores(`
- ligne 219 — `def apply_batch_diagnostics_to_entries(`
- ligne 31 — `def _classify_exclusion(`
- ligne 83 — `def _load_filters(engine: Any) -> BatchFilters | None:`
## `risk_management/campaign_orchestrator.py`

- ligne 146 — `class CampaignDayResult:`
- ligne 231 — `class WeeklyReview:`
- ligne 296 — `class CampaignOrchestrator:`
- ligne 38 — `class CampaignPhase:`
- ligne 51 — `class CampaignConfig:`
- ligne 961 — `def create_campaign(`
## `risk_management/capacity.py`

- ligne 24 — `class CapacityEstimate:`
- ligne 323 — `def estimate_symbol_capacity(`
- ligne 87 — `class CapacityEstimator:`
## `risk_management/circuit_breaker.py`

- ligne 24 — `class PnLSnapshot:`
- ligne 32 — `class CircuitBreakerStatus:`
- ligne 40 — `def _try_send_alert(event: str, payload: dict) -> None:`
- ligne 405 — `def _set_cb_prometheus(active: bool) -> None:`
- ligne 69 — `class CircuitBreaker:`
## `risk_management/cli.py`

- ligne 1022 — `def _top_count_items(counts: dict[str, int], *, limit: int = 5) -> list[dict[str, object]]:`
- ligne 1030 — `def _build_postmortem_artifacts(`
- ligne 1096 — `def _run_shadow_compare(`
- ligne 1174 — `def build_arg_parser() -> argparse.ArgumentParser:`
- ligne 127 — `def _serialize_market_regime_snapshot(snapshot: object | None) -> dict[str, object] | None:`
- ligne 1302 — `def _print_summary(entries: list[PortfolioEntry], run_id: str, trade_date: date) -> None:`
- ligne 1324 — `def main(args: list[str] | None = None) -> None:`
- ligne 141 — `def _evaluate_regime_transition(snapshot: object | None) -> object | None:`
- ligne 160 — `def _load_live_spread_snapshots(`
- ligne 192 — `def _load_live_borrow_snapshots(`
- ligne 310 — `def _parse_quote_time(value: object) -> datetime | None:`
- ligne 322 — `def _wire_covariance_to_optimizer(`
- ligne 402 — `def _check_model_compatibility(`
- ligne 53 — `class RiskRunMode(StrEnum):`
- ligne 535 — `def _optional_quote_float(value: object) -> float | None:`
- ligne 542 — `def _build_reconciliation_summary(`
- ligne 61 — `def _emit_live_progress(`
- ligne 616 — `def _persist_transition_plan_artifact(`
- ligne 650 — `def _build_preflight_data_quality(`
- ligne 789 — `def _entries_to_shadow_compare_frame(entries: list[PortfolioEntry]) -> pd.DataFrame:`
- ligne 803 — `def _risk_decisions_to_shadow_compare_frame(decisions: pd.DataFrame) -> pd.DataFrame:`
- ligne 821 — `def _build_conviction_weights_calibration(`
- ligne 84 — `def _resolve_market_regime_snapshot(`
- ligne 947 — `def _load_empirical_risk_calibration(`
- ligne 976 — `def _apply_empirical_risk_calibration(`
## `risk_management/concentration_constraints.py`

- ligne 116 — `class ConcentrationChecker:`
- ligne 24 — `class ConcentrationConfig:`
- ligne 300 — `def check_concentration(`
- ligne 320 — `def compute_portfolio_hhi(weights: dict[str, float]) -> float:`
- ligne 71 — `class ConcentrationResult:`
## `risk_management/concentration.py`

- ligne 188 — `class ConsecutiveLossTracker:`
- ligne 355 — `class BreakoutConfirmationTracker:`
- ligne 472 — `def build_entry_concentration_filter(`
- ligne 48 — `class SymbolTradeTracker:`
## `risk_management/config.py`

- ligne 14 — `class RiskConfig:`
- ligne 627 — `def load_risk_config(`
## `risk_management/constraints.py`

- ligne 113 — `class ConstraintChecker:`
- ligne 39 — `class PortfolioState:`
## `risk_management/conviction.py`

- ligne 13 — `def compute_conviction(`
## `risk_management/correlation_filter.py`

- ligne 109 — `def filter_correlated_signed(`
- ligne 24 — `def build_return_matrix(`
- ligne 55 — `def filter_correlated(`
## `risk_management/daily_reconciliation.py`

- ligne 129 — `class DailyReconciliation:`
- ligne 27 — `class ReconStatus(StrEnum):`
- ligne 40 — `class ReconItem:`
- ligne 69 — `class ReconciliationReport:`
## `risk_management/data_criticality.py`

- ligne 134 — `class GateResult:`
- ligne 167 — `class DataAvailabilityGate:`
- ligne 337 — `def check_data_availability(`
- ligne 34 — `class DataCriticality(StrEnum):`
- ligne 80 — `def classify_data_source(source_name: str) -> DataCriticality:`
- ligne 93 — `class AvailabilityStatus:`
## `risk_management/db_io.py`

- ligne 120 — `class RiskRepository:`
- ligne 44 — `def _optional_int(value: Any) -> int | None:`
- ligne 53 — `def _optional_text(value: Any) -> str | None:`
- ligne 60 — `def _build_runtime_segment_key(`
- ligne 77 — `def _load_empirical_calibration_fallback_levels() -> tuple[list[str], str]:`
## `risk_management/decision_fingerprint.py`

- ligne 100 — `class PositionDecisionFingerprint:`
- ligne 159 — `class AuditLogEntry:`
- ligne 231 — `class DecisionAuditLog:`
- ligne 29 — `class DecisionFingerprint:`
- ligne 302 — `class ReplayVerifier:`
- ligne 380 — `class ReplayVerificationResult:`
- ligne 413 — `class IdempotencyResult:`
- ligne 423 — `class IdempotencyGate:`
- ligne 470 — `def build_decision_fingerprint(`
- ligne 494 — `def build_position_fingerprint(`
## `risk_management/drift_monitor.py`

- ligne 118 — `class DriftReport:`
- ligne 169 — `class DriftMonitor:`
- ligne 30 — `class DriftDimension(StrEnum):`
- ligne 368 — `def check_drift(`
- ligne 45 — `class DriftStatus(StrEnum):`
- ligne 57 — `class DriftConfig:`
- ligne 93 — `class DimensionDrift:`
## `risk_management/edge.py`

- ligne 101 — `class EdgeCalculator:`
- ligne 214 — `def compute_edge_from_trades(`
- ligne 30 — `class DirectionalEdgeEstimate:`
## `risk_management/enums.py`

- ligne 11 — `class Decision(StrEnum):`
- ligne 17 — `class SizingMethod(StrEnum):`
- ligne 29 — `class DecisionReasonCode(StrEnum):`
- ligne 64 — `class KellyFallback(StrEnum):`
## `risk_management/factor_model.py`

- ligne 1038 — `def build_exposures_from_score_frame(`
- ligne 1098 — `def format_risk_decomposition(`
- ligne 1132 — `def _systematic_vol(self: PortfolioRiskDecomposition) -> float:`
- ligne 1136 — `def _specific_vol(self: PortfolioRiskDecomposition) -> float:`
- ligne 114 — `class FactorConstraintResult:`
- ligne 137 — `class FactorCorrelationRejection:`
- ligne 151 — `def _cross_sectional_zscore(`
- ligne 189 — `def compute_factor_exposures(`
- ligne 294 — `def _ewma_weights(n: int, half_life: int) -> np.ndarray:`
- ligne 319 — `def _estimate_ewma_covariance(`
- ligne 357 — `def build_factor_returns(`
- ligne 434 — `def estimate_factor_covariance(`
- ligne 49 — `class FactorCovariance:`
- ligne 517 — `def _build_exposure_matrix(`
- ligne 557 — `def decompose_portfolio_risk(`
- ligne 674 — `def _compute_factor_implied_correlation(`
- ligne 715 — `def check_factor_constraints(`
- ligne 77 — `class PortfolioRiskDecomposition:`
- ligne 827 — `def check_factor_constraints_on_sized_weights(`
- ligne 919 — `def _filter_worst_offenders(`
- ligne 958 — `def filter_by_factor_correlation(`
## `risk_management/freshness_gate.py`

- ligne 105 — `class FreshnessResult:`
- ligne 158 — `class FreshnessGate:`
- ligne 27 — `class FreshnessDimension(StrEnum):`
- ligne 305 — `def check_freshness(`
- ligne 44 — `class FreshnessConfig:`
- ligne 80 — `class DimensionFreshness:`
## `risk_management/gradual_ramp_up.py`

- ligne 140 — `class StageTransition:`
- ligne 173 — `class RampUpManager:`
- ligne 29 — `class RampUpStage(StrEnum):`
- ligne 346 — `def create_ramp_up_manager(`
- ligne 85 — `class RampUpConfig:`
## `risk_management/immutable_journal.py`

- ligne 127 — `class ImmutableJournal:`
- ligne 283 — `def create_journal_entry(`
- ligne 33 — `class JournalEntryType(StrEnum):`
- ligne 52 — `class JournalEntry:`
## `risk_management/kelly.py`

- ligne 15 — `class KellySizer:`
- ligne 213 — `def compute_kelly_fraction(`
- ligne 259 — `def compute_kelly_shares(`
## `risk_management/liquidity.py`

- ligne 154 — `class BorrowSnapshot:`
- ligne 239 — `class ParticipationLimit:`
- ligne 320 — `class SlippageEstimate:`
- ligne 351 — `class SlippageEstimator:`
- ligne 38 — `class BorrowStatus(StrEnum):`
- ligne 462 — `class LiquidityGateResult:`
- ligne 508 — `class LiquidityGate:`
- ligne 674 — `def check_liquidity_pre_entry(`
- ligne 720 — `class PreSubmissionResult:`
- ligne 73 — `class SpreadSnapshot:`
- ligne 775 — `class PreSubmissionGate:`
- ligne 953 — `def _borrow_degraded(old: BorrowStatus, new: BorrowStatus) -> bool:`
- ligne 963 — `def check_pre_submission(`
## `risk_management/live_pipeline_guards.py`

- ligne 110 — `def evaluate_vol_target(`
- ligne 14 — `class MlCoverageGateDecision:`
- ligne 171 — `def apply_vol_target_to_risk_config(config: RiskConfig, decision: VolTargetDecision) -> RiskConfig:`
- ligne 36 — `class VolTargetDecision:`
- ligne 59 — `def evaluate_ml_coverage_gate(`
## `risk_management/ml_gate.py`

- ligne 127 — `def apply_ml_gate_to_risk_config(config: Any, gate_state: MlGateState) -> Any:`
- ligne 27 — `class MlGateState:`
- ligne 46 — `def load_latest_ml_gate_decision(engine: Any) -> dict | None:`
- ligne 83 — `def resolve_ml_gate_state(engine: Any) -> MlGateState:`
## `risk_management/model_registry.py`

- ligne 150 — `class ModelRegistry:`
- ligne 27 — `class ModelStatus(StrEnum):`
- ligne 420 — `def create_model_entry(`
- ligne 440 — `def rollback_persisted_registry(`
- ligne 77 — `class ModelRegistryEntry:`
## `risk_management/models.py`

- ligne 156 — `class PredictionInfo:`
- ligne 16 — `class FactorExposures:`
- ligne 183 — `class WinRateInfo:`
- ligne 193 — `class DirectionalWinRateInfo:`
- ligne 241 — `class CorrelationRejection:`
- ligne 250 — `class EnrichedSelection:`
- ligne 283 — `class AccountRiskSnapshot:`
- ligne 298 — `class RiskDecisionRow:`
- ligne 317 — `class PortfolioTargetRow:`
- ligne 35 — `class SelectionScore:`
- ligne 72 — `class PriceInfo:`
- ligne 85 — `class SizingResult:`
- ligne 93 — `class PortfolioEntry:`
## `risk_management/operational_controls.py`

- ligne 112 — `class ControlSchedule:`
- ligne 179 — `class OperationalControls:`
- ligne 28 — `class ControlFrequency(StrEnum):`
- ligne 302 — `def run_pre_session_smoke_tests(`
- ligne 327 — `def build_operational_probes(`
- ligne 41 — `class ControlStatus(StrEnum):`
- ligne 424 — `def persist_ramp_up_transition(`
- ligne 52 — `class SmokeTest:`
- ligne 82 — `class ControlResult:`
## `risk_management/operational_data.py`

- ligne 113 — `class BacktestOperationalDataAdapter:`
- ligne 138 — `def _normalize_account(`
- ligne 159 — `def _normalize_position(raw: Mapping[str, Any]) -> OpenPosition:`
- ligne 177 — `def _normalize_order(raw: Mapping[str, Any]) -> OpenOrder:`
- ligne 19 — `class OperationalDataUnavailable(RuntimeError):`
- ligne 194 — `def _is_open_order(raw: Mapping[str, Any]) -> bool:`
- ligne 200 — `def _required_positive_float(raw: Mapping[str, Any], key: str) -> float:`
- ligne 207 — `def _required_non_negative_float(raw: Mapping[str, Any], key: str) -> float:`
- ligne 214 — `def _optional_float(value: Any, *, default: float) -> float:`
- ligne 24 — `class OperationalAccountSnapshot:`
- ligne 37 — `class OperationalDataSnapshot:`
- ligne 86 — `class LiveBrokerOperationalDataAdapter:`
## `risk_management/portfolio_builder.py`

- ligne 196 — `def _apply_concentration_filters(`
- ligne 231 — `def _enforce_net_exposure_neutrality(`
- ligne 332 — `class PortfolioBuilder:`
- ligne 55 — `def compute_allocation_factors(`
- ligne 82 — `def _apply_regime_scoring_to_candidates(`
## `risk_management/portfolio_optimizer.py`

- ligne 143 — `class TurnoverCosts:`
- ligne 212 — `class MarginalRiskDecomposition:`
- ligne 256 — `def compute_mctr(`
- ligne 319 — `class OptimizationResult:`
- ligne 32 — `class HoldingSnapshot:`
- ligne 380 — `class PortfolioOptimizer:`
- ligne 738 — `def optimize_portfolio(`
- ligne 93 — `class NoTradeBand:`
## `risk_management/position_sizer.py`

- ligne 15 — `class PositionSizer:`
## `risk_management/pre_live_checklist.py`

- ligne 125 — `class PreLiveChecklist:`
- ligne 23 — `class GateStatus(StrEnum):`
- ligne 304 — `def build_pre_live_checklist(stage: str = "shadow") -> GoLiveGate:`
- ligne 310 — `def evaluate_pre_live_gates(`
- ligne 37 — `class ChecklistGate:`
- ligne 88 — `class GoLiveGate:`
## `risk_management/protection_contract.py`

- ligne 150 — `class ProtectionState:`
- ligne 202 — `class ProtectionContract:`
- ligne 23 — `class ProtectionStatus(StrEnum):`
- ligne 311 — `def check_protection_state(state: ProtectionState) -> tuple[bool, list[str]]:`
- ligne 317 — `def build_oco_group(`
- ligne 53 — `class ProtectionSLA:`
- ligne 85 — `class OCOGroup:`
## `risk_management/regime_apply.py`

- ligne 123 — `def apply_account_cp_policy(`
- ligne 141 — `def apply_transition(`
- ligne 33 — `def apply_structural_market_guards(`
- ligne 73 — `def apply_snapshot(`
## `risk_management/regime_state_machine.py`

- ligne 116 — `class TransitionAction(StrEnum):`
- ligne 157 — `class RegimeTransition:`
- ligne 243 — `class RegimeStateMachine:`
- ligne 39 — `class RegimeState(StrEnum):`
- ligne 543 — `def compute_regime_transition(`
## `risk_management/risk_checker.py`

- ligne 15 — `class RiskCheckerImpl:`
## `risk_management/selection_contract.py`

- ligne 133 — `class SelectorVetoContext:`
- ligne 177 — `class RiskDecisionInput:`
- ligne 210 — `def build_rankings(`
- ligne 240 — `def filter_actionable(candidates: list[MLRankedCandidate]) -> list[MLRankedCandidate]:`
- ligne 248 — `def validate_candidate_consistency(candidate: MLRankedCandidate) -> list[str]:`
- ligne 289 — `def build_candidate_from_prediction(`
- ligne 33 — `class MLRankedCandidate:`
- ligne 352 — `def compute_entry_date(decision_date: date) -> date:`
- ligne 366 — `def validate_decision_timing(`
- ligne 427 — `def assert_valid_entry_timing(`
- ligne 454 — `def to_selection_score(`
- ligne 516 — `def validate_payload_completeness(candidate: MLRankedCandidate) -> list[str]:`
## `risk_management/shadow_compare.py`

- ligne 134 — `def _normalize(`
- ligne 160 — `def persist_shadow_run(report: ShadowDriftReport, *, engine: Any, run_id: str | None = None) -> str:`
- ligne 29 — `def _number_or_none(row: pd.Series, key: str) -> float | None:`
- ligne 37 — `class ShadowDriftReport:`
- ligne 61 — `def compare_runs(`
## `risk_management/shadow_engine.py`

- ligne 164 — `class SimulatedFill:`
- ligne 199 — `class ShadowFillSimulator:`
- ligne 26 — `class ShadowRunStatus(StrEnum):`
- ligne 300 — `class ShadowEngine:`
- ligne 41 — `class ShadowDecision:`
- ligne 464 — `def compare_shadow_to_live(`
- ligne 86 — `class ShadowComparisonReport:`
## `risk_management/stop_calculator.py`

- ligne 176 — `class StopCalculator:`
- ligne 28 — `class StopLevels:`
- ligne 331 — `def compute_initial_stop_price(`
- ligne 370 — `def compute_stop_distance_pct(`
- ligne 381 — `def is_stop_valid(side: str, entry_price: float, stop_price: float) -> bool:`
## `risk_management/transition_handler.py`

- ligne 124 — `class OpenPosition:`
- ligne 148 — `class OpenOrder:`
- ligne 172 — `class TransitionHandler:`
- ligne 32 — `class OrderAction(StrEnum):`
- ligne 334 — `def build_transition_plan(`
- ligne 46 — `class TransitionStep:`
- ligne 88 — `class PositionTransitionPlan:`

