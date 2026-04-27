"""Configuration centralisée du module de gestion de risque."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.conviction import ConvictionWeights


@dataclass(frozen=True, slots=True)
class RiskConfig:
    """Paramètres de risque — immutable après construction."""

    account_equity: float = 100_000.0
    risk_per_trade_pct: float = 0.01
    atr_window: int = 20
    atr_stop_multiple: float = 2.0

    max_positions: int = 20
    max_position_weight: float = 0.10
    max_sector_weight: float = 0.30
    max_gross_exposure: float = 1.0
    min_position_notional: float = 500.0

    max_portfolio_drawdown_pct: float = 0.15
    max_daily_loss_pct: float = 0.05

    dry_run: bool = False

    # --- Correlation filter V2 ---
    correlation_threshold: float = 0.80
    correlation_lookback_days: int = 60
    correlation_min_overlap: int = 40

    # --- Kelly sizing V2 ---
    enable_kelly_sizing: bool = False
    assumed_payoff_ratio: float = 1.5
    kelly_fraction_multiplier: float = 0.25
    min_effective_probability: float = 0.52
    default_win_rate: float = 0.55

    # --- Conviction score V2 ---
    score_weight: float = 0.40
    prediction_weight: float = 0.60
    prediction_confidence_weight: float = 0.60
    historical_win_rate_weight: float = 0.40

    def __post_init__(self) -> None:
        if self.account_equity <= 0:
            raise ValueError("account_equity doit être > 0.")
        if not 0 < self.risk_per_trade_pct < 1:
            raise ValueError("risk_per_trade_pct doit être dans ]0, 1[.")
        if self.atr_window < 1:
            raise ValueError("atr_window doit être >= 1.")
        if self.atr_stop_multiple <= 0:
            raise ValueError("atr_stop_multiple doit être > 0.")
        if self.max_positions < 1:
            raise ValueError("max_positions doit être >= 1.")
        # --- V2 validations ---
        if not (0 < self.correlation_threshold <= 1):
            raise ValueError("correlation_threshold doit être dans ]0, 1].")
        if self.correlation_lookback_days < self.correlation_min_overlap:
            raise ValueError("correlation_lookback_days doit être >= correlation_min_overlap.")
        if self.correlation_min_overlap < 1:
            raise ValueError("correlation_min_overlap doit être >= 1.")
        if self.assumed_payoff_ratio <= 0:
            raise ValueError("assumed_payoff_ratio doit être > 0.")
        if not (0 < self.kelly_fraction_multiplier <= 1):
            raise ValueError("kelly_fraction_multiplier doit être dans ]0, 1].")
        if not (0.5 <= self.min_effective_probability < 1):
            raise ValueError("min_effective_probability doit être dans [0.5, 1[.")
        if not (0.5 <= self.default_win_rate < 1):
            raise ValueError("default_win_rate doit être dans [0.5, 1[.")
        if abs((self.score_weight + self.prediction_weight) - 1.0) > 1e-6:
            raise ValueError("score_weight + prediction_weight doit == 1.0.")
        if abs((self.prediction_confidence_weight + self.historical_win_rate_weight) - 1.0) > 1e-6:
            raise ValueError("prediction_confidence_weight + historical_win_rate_weight doit == 1.0.")

    def to_conviction_weights(self) -> "ConvictionWeights":
        """Phase 5.1.b — Adapte les pondérations risk vers ``core.conviction.ConvictionWeights``.

        Centralise la fusion conviction (cf. `prompt/refactor/plan_phase5.md` §5.1.b).
        """
        from core.conviction import ConvictionWeights

        return ConvictionWeights(
            score_weight=self.score_weight,
            prediction_weight=self.prediction_weight,
        )

