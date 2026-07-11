"""Garde-fous live du pipeline risk (vol targeting + gate de couverture ML)."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import pandas as pd

from risk_management.config import RiskConfig


@dataclass(frozen=True, slots=True)
class MlCoverageGateDecision:
    enabled: bool
    allowed: bool
    required_ratio: float | None = None
    coverage_ratio: float | None = None
    selection_count: int = 0
    prediction_count: int = 0
    reason: str = "disabled"

    def to_summary(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "allowed": bool(self.allowed),
            "required_ratio": float(self.required_ratio) if self.required_ratio is not None else None,
            "coverage_ratio": float(self.coverage_ratio) if self.coverage_ratio is not None else None,
            "candidate_count": int(self.selection_count),
            "prediction_count": int(self.prediction_count),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class VolTargetDecision:
    enabled: bool
    applied: bool
    target_annual_vol: float | None = None
    realized_annual_vol: float | None = None
    scaler: float = 1.0
    lookback_days: int = 60
    benchmark_symbol: str = "SPY"
    reason: str = "disabled"

    def to_summary(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "applied": bool(self.applied),
            "target_annual_vol": float(self.target_annual_vol) if self.target_annual_vol is not None else None,
            "realized_annual_vol": float(self.realized_annual_vol) if self.realized_annual_vol is not None else None,
            "scaler": float(self.scaler),
            "lookback_days": int(self.lookback_days),
            "benchmark_symbol": self.benchmark_symbol,
            "reason": self.reason,
        }


def evaluate_ml_coverage_gate(
    *,
    candidate_count: int,
    prediction_count: int,
    min_coverage_ratio: float | None,
    regime_allows_new_entries: bool = True,
    ml_gate_enabled: bool = True,
) -> MlCoverageGateDecision:
    required_ratio = float(min_coverage_ratio or 0.0)
    if required_ratio <= 0:
        return MlCoverageGateDecision(enabled=False, allowed=True, reason="disabled")

    if not regime_allows_new_entries:
        return MlCoverageGateDecision(
            enabled=True,
            allowed=True,
            required_ratio=required_ratio,
            reason="skipped_by_regime",
        )

    normalized_candidates = max(int(candidate_count), 0)
    normalized_predictions = max(int(prediction_count), 0)
    if normalized_candidates == 0:
        return MlCoverageGateDecision(
            enabled=True,
            allowed=True,
            required_ratio=required_ratio,
            coverage_ratio=1.0,
            selection_count=0,
            prediction_count=normalized_predictions,
            reason="no_candidates",
        )

    coverage_ratio = normalized_predictions / normalized_candidates
    reason = "ok"
    if not ml_gate_enabled and normalized_predictions == 0:
        reason = "ml_gate_disabled"
    elif coverage_ratio < required_ratio:
        reason = "coverage_below_threshold"

    return MlCoverageGateDecision(
        enabled=True,
        allowed=coverage_ratio >= required_ratio,
        required_ratio=required_ratio,
        coverage_ratio=coverage_ratio,
        selection_count=normalized_candidates,
        prediction_count=normalized_predictions,
        reason=reason,
    )


def evaluate_vol_target(
    daily_returns: pd.Series,
    *,
    target_annual_vol: float | None,
    lookback_days: int = 60,
    benchmark_symbol: str = "SPY",
    floor: float = 0.25,
    cap: float = 1.5,
) -> VolTargetDecision:
    target = float(target_annual_vol or 0.0)
    if target <= 0:
        return VolTargetDecision(enabled=False, applied=False, benchmark_symbol=benchmark_symbol, reason="disabled")

    window = daily_returns.tail(max(int(lookback_days), 1)).dropna()
    min_required = max(20, int(max(int(lookback_days), 1) / 3))
    if window.empty:
        return VolTargetDecision(
            enabled=True,
            applied=False,
            target_annual_vol=target,
            lookback_days=int(lookback_days),
            benchmark_symbol=benchmark_symbol,
            reason="missing_history",
        )
    if len(window) < min_required:
        return VolTargetDecision(
            enabled=True,
            applied=False,
            target_annual_vol=target,
            lookback_days=int(lookback_days),
            benchmark_symbol=benchmark_symbol,
            reason="insufficient_history",
        )

    realized = float(window.std(ddof=0)) * float(np.sqrt(252.0))
    if realized <= 0:
        return VolTargetDecision(
            enabled=True,
            applied=False,
            target_annual_vol=target,
            realized_annual_vol=realized,
            lookback_days=int(lookback_days),
            benchmark_symbol=benchmark_symbol,
            reason="non_positive_realized_vol",
        )

    raw_scaler = target / realized
    scaler = float(np.clip(raw_scaler, floor, cap))
    effective_scaler = min(scaler, 1.0)
    return VolTargetDecision(
        enabled=True,
        applied=effective_scaler < 0.999999,
        target_annual_vol=target,
        realized_annual_vol=realized,
        scaler=effective_scaler,
        lookback_days=int(lookback_days),
        benchmark_symbol=benchmark_symbol,
        reason="applied" if effective_scaler < 0.999999 else "within_target",
    )


def apply_vol_target_to_risk_config(config: RiskConfig, decision: VolTargetDecision) -> RiskConfig:
    if not decision.enabled or not decision.applied:
        return config
    scaler = min(max(float(decision.scaler), 0.0), 1.0)
    return replace(
        config,
        risk_multiplier=float(config.risk_multiplier) * scaler,
        max_gross_exposure=float(config.max_gross_exposure) * scaler,
    )


__all__ = [
    "MlCoverageGateDecision",
    "VolTargetDecision",
    "apply_vol_target_to_risk_config",
    "evaluate_ml_coverage_gate",
    "evaluate_vol_target",
]
