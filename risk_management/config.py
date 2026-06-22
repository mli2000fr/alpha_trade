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
    # Circuit breaker drawdown — mode dégradé et pic roulant (parité backtest Phase C.5)
    # 0.0 = blocage total (comportement original) ; > 0 = mode dégradé (sizing réduit)
    degraded_entry_allocation_pct: float = 0.0
    rolling_peak_window_days: int = 0   # 0 = pic historique absolu (comportement original)
    # Seuil de recovery : une fois trippé en mode dégradé, le breaker ne se
    # désactive que si l'equity remonte à cette fraction du pic de référence.
    recovery_pct: float = 0.92
    # Ramp-up régimed : si le régime repasse en "normal" ET que l'equity
    # progresse, l'allocation dégradée est progressivement augmentée.
    regime_ramp_up_enabled: bool = False
    regime_ramp_up_pct_per_day: float = 0.025
    regime_ramp_up_max_pct: float = 0.40
    # Fenêtre glissante pour le « pic sur N jours » : le streak s'incrémente
    # dès que l'equity dépasse le max des N jours précédents (résilience aux
    # jours de stagnation).
    regime_ramp_up_peak_window_days: int = 5

    # Concentration / diversification (Priorité 4)
    concentration_max_trades_per_symbol: int = 5
    concentration_window_calendar_days: int = 180
    concentration_max_consecutive_losses: int = 3
    concentration_blacklist_duration_days: int = 90

    # Anti-faux-départs (Quick Win 1) — nombre de jours consécutifs de
    # présence dans le top-N avant qu'un candidat soit éligible.
    # 1 = confirmation immédiate (filtre désactivé).
    # Pour le live, peut être remonté à 3 avec persistence JSON.
    min_breakout_days: int = 1

    # Quick Win 2 — score minimum pour qu'un candidat soit tradable.
    # 0.0 = filtre désactivé. 0.7 recommandé pour filtrer les entrées faibles.
    min_score_threshold: float = 0.0

    # Force-close sur circuit breaker : liquide toutes les positions quand
    # le breaker trippe (max_drawdown_pct atteint).
    force_close_on_breaker: bool = False
    # Fraction des positions à liquider (0.0-1.0). 1.0 = tout, 0.5 = moitié.
    force_close_pct: float = 0.50

    # Sprint 2 — short selling (Option C : MomentumRotationState)
    short_selling_enabled: bool = False
    short_max_positions: int = 2
    short_min_score: float = 0.30
    short_rotation_required: bool = True
    short_tp_pct: float = 0.08
    short_trailing_pct: float = 0.10
    short_time_stop_days: int = 20
    # ML Sprint 4 — seuil de score minimum pour les shorts (distinct des longs)
    min_score_threshold_short: float = 0.0

    target_annual_vol: float | None = None
    vol_target_lookback_days: int = 60

    dry_run: bool = False

    # --- Correlation filter V2 ---
    correlation_threshold: float = 0.80
    correlation_lookback_days: int = 60
    correlation_min_overlap: int = 40

    # --- Factor risk model (Priorité 3 — RisqueSectoriel.md) ---
    # Active le modèle de risque factoriel CWMS (Phases A-E).
    enable_factor_model: bool = False
    # Active le filtre de corrélation basé sur le modèle factoriel (Phase E).
    # Remplace le filtre Pearson quand activé.
    use_factor_correlation_filter: bool = False
    # Seuil de corrélation implicite max pour le filtre factoriel (Phase E).
    factor_correlation_threshold: float = 0.70
    # Beta moyen pondéré maximum du portefeuille (Phase D).
    max_portfolio_beta: float = 1.2
    # Part maximale du risque total venant d'un seul facteur (Phase D).
    max_factor_concentration_pct: float = 0.60
    # Nombre minimum de facteurs avec contribution > 10% (Phase D).
    min_factor_diversification: int = 2
    # Demi-vie EWMA pour l'estimation de la covariance factorielle (Phase B).
    factor_ewma_half_life: int = 60
    # Fenêtre de lookback pour l'estimation factorielle en jours (Phase B).
    factor_lookback_days: int = 252

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

    # --- Market-aware regime (Axe B du plan ``prompt/parttern/plan.md``) ---
    # Multiplicateur de risque appliqué au sizing ATR (1.0 = nominal).
    risk_multiplier: float = 1.0
    # Si défini, remplace ``min_position_notional`` lors du contrôle de notional
    # (typiquement 155 USD pour rester compatible Alpaca + petit capital).
    enforce_min_notional: float | None = None
    # Plafond optionnel "max_positions" calculé dynamiquement à partir de
    # l'equity et/ou du régime (None => ``max_positions`` standard utilisé).
    effective_max_positions_override: int | None = None
    # Maximum 2 tickers par secteur (en complément de ``max_sector_weight``).
    max_tickers_per_sector: int | None = None
    allow_fractional_shares: bool = False

    def __post_init__(self) -> None:
        if self.account_equity <= 0:
            raise ValueError("account_equity doit être > 0.")
        if not 0 < self.risk_per_trade_pct < 1:
            raise ValueError("risk_per_trade_pct doit être dans ]0, 1[.")
        if self.atr_window < 1:
            raise ValueError("atr_window doit être >= 1.")
        if self.atr_stop_multiple <= 0:
            raise ValueError("atr_stop_multiple doit être > 0.")
        if self.target_annual_vol is not None and self.target_annual_vol <= 0:
            raise ValueError("target_annual_vol doit être > 0 quand renseigné.")
        if self.vol_target_lookback_days < 2:
            raise ValueError("vol_target_lookback_days doit être >= 2.")
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
        # --- Market-aware validations ---
        if self.risk_multiplier < 0:
            raise ValueError("risk_multiplier doit être >= 0.")
        if self.enforce_min_notional is not None and self.enforce_min_notional < 0:
            raise ValueError("enforce_min_notional doit être >= 0 quand renseigné.")
        if self.effective_max_positions_override is not None and self.effective_max_positions_override < 0:
            raise ValueError("effective_max_positions_override doit être >= 0 quand renseigné.")
        if self.max_tickers_per_sector is not None and self.max_tickers_per_sector < 1:
            raise ValueError("max_tickers_per_sector doit être >= 1 quand renseigné.")
        # --- Factor model validations (Priorité 3) ---
        if self.factor_correlation_threshold <= 0 or self.factor_correlation_threshold > 1:
            raise ValueError("factor_correlation_threshold doit être dans ]0, 1].")
        if self.max_portfolio_beta <= 0:
            raise ValueError("max_portfolio_beta doit être > 0.")
        if not (0 < self.max_factor_concentration_pct <= 1):
            raise ValueError("max_factor_concentration_pct doit être dans ]0, 1].")
        if self.min_factor_diversification < 1:
            raise ValueError("min_factor_diversification doit être >= 1.")
        if self.factor_ewma_half_life < 2:
            raise ValueError("factor_ewma_half_life doit être >= 2.")
        if self.factor_lookback_days < 20:
            raise ValueError("factor_lookback_days doit être >= 20.")

    @property
    def effective_min_notional(self) -> float:
        """Notional minimum effectif (``enforce_min_notional`` prioritaire)."""
        if self.enforce_min_notional is not None:
            return float(self.enforce_min_notional)
        return float(self.min_position_notional)

    @property
    def effective_max_positions(self) -> int:
        """Max positions effectif (``effective_max_positions_override`` prioritaire)."""
        if self.effective_max_positions_override is not None:
            return max(0, int(self.effective_max_positions_override))
        return int(self.max_positions)

    def to_conviction_weights(self) -> ConvictionWeights:
        """Phase 5.1.b — Adapte les pondérations risk vers ``core.conviction.ConvictionWeights``.

        Centralise la fusion conviction (cf. `prompt/refactor/plan_phase5.md` §5.1.b).
        """
        from core.conviction import ConvictionWeights

        return ConvictionWeights(
            score_weight=self.score_weight,
            prediction_weight=self.prediction_weight,
        )

