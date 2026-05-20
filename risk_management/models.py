"""Modèles de données internes au module risk_management."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class CandidateScore:
    """Candidat lu depuis stock_scores (is_candidate=1)."""
    symbol: str
    sector: str
    score_used: float
    score_source: str = "final_score_sentiment"
    company_idio_score: float | None = None
    macro_regime_score: float | None = None
    company_idio_signal_norm: float | None = None
    macro_regime_signal_norm: float | None = None
    company_idio_component: float | None = None
    macro_regime_component: float | None = None
    quant_component: float | None = None
    walk_forward_sentiment_weight: float | None = None
    walk_forward_macro_weight: float | None = None
    walk_forward_quant_weight: float | None = None
    calibration_run_id: str | None = None
    calibration_source: str | None = None
    snapshot_date: date | None = None
    candidate_rank: int | None = None
    selector_signal_mode: str | None = None
    selection_explanation: str | None = None
    selector_earnings_blackout: int | None = None


@dataclass(frozen=True, slots=True)
class PriceInfo:
    """Dernières informations de prix pour un symbole."""
    symbol: str
    last_close: float
    atr_20: float | None
    price_asof_date: date | None = None
    atr_asof_date: date | None = None


@dataclass(frozen=True, slots=True)
class SizingResult:
    """Résultat du calcul de taille de position."""
    symbol: str
    proposed_shares: int
    method: str  # "atr" | "equal_weight"


@dataclass(frozen=True, slots=True)
class PortfolioEntry:
    """Ligne du portefeuille cible construit."""
    symbol: str
    sector: str
    entry_price: float
    score_used: float
    score_source: str
    atr_20: float | None
    proposed_shares: int
    approved_shares: int
    target_notional: float
    target_weight: float
    decision: str          # "ACCEPTED" | "REDUCED" | "REJECTED"
    decision_reason: str

    # --- V2 audit fields ---
    conviction_score: float = 0.0
    predicted_proba: float | None = None
    historical_win_rate: float | None = None
    effective_probability: float | None = None
    kelly_fraction: float | None = None
    sizing_method: str = ""
    correlation_blocker: str | None = None
    correlation_value: float | None = None
    company_idio_score: float | None = None
    macro_regime_score: float | None = None
    company_idio_signal_norm: float | None = None
    macro_regime_signal_norm: float | None = None
    company_idio_component: float | None = None
    macro_regime_component: float | None = None
    quant_component: float | None = None
    walk_forward_sentiment_weight: float | None = None
    walk_forward_macro_weight: float | None = None
    walk_forward_quant_weight: float | None = None
    calibration_run_id: str | None = None
    calibration_source: str | None = None
    candidate_rank: int | None = None
    decision_rank: int | None = None
    stop_price_initial: float | None = None
    risk_per_share: float | None = None
    risk_budget_dollars: float | None = None
    initial_risk_dollars: float | None = None
    score_snapshot_date: date | None = None
    price_asof_date: date | None = None
    atr_asof_date: date | None = None
    prediction_asof_date: date | None = None
    ml_metrics_asof_date: date | None = None
    selector_signal_mode: str | None = None
    selection_explanation: str | None = None
    selector_earnings_blackout: int | None = None


@dataclass(frozen=True, slots=True)
class PredictionInfo:
    """Dernière prédiction ML pour un symbole."""
    symbol: str
    predicted_proba: float
    predicted_class: int
    run_id: str
    prediction_date: date | None = None


@dataclass(frozen=True, slots=True)
class WinRateInfo:
    """Proxy de win rate historique depuis model_metrics."""
    symbol: str
    directional_accuracy: float
    split_name: str
    run_id: str
    asof_date: date | None = None


@dataclass(frozen=True, slots=True)
class CorrelationRejection:
    """Résultat d'un rejet par filtre de corrélation."""
    rejected_symbol: str
    blocker_symbol: str
    correlation_value: float
    threshold: float


@dataclass(frozen=True, slots=True)
class EnrichedCandidate:
    """Candidat enrichi avec toutes les données V2 avant sizing."""
    symbol: str
    sector: str
    score_used: float
    score_source: str
    predicted_proba: float | None
    historical_win_rate: float | None
    conviction_score: float
    company_idio_score: float | None = None
    macro_regime_score: float | None = None
    company_idio_signal_norm: float | None = None
    macro_regime_signal_norm: float | None = None
    company_idio_component: float | None = None
    macro_regime_component: float | None = None
    quant_component: float | None = None
    walk_forward_sentiment_weight: float | None = None
    walk_forward_macro_weight: float | None = None
    walk_forward_quant_weight: float | None = None
    calibration_run_id: str | None = None
    calibration_source: str | None = None
    snapshot_date: date | None = None
    prediction_asof_date: date | None = None
    ml_metrics_asof_date: date | None = None
    candidate_rank: int | None = None
    selector_signal_mode: str | None = None
    selection_explanation: str | None = None
    selector_earnings_blackout: int | None = None


@dataclass(frozen=True, slots=True)
class AccountRiskSnapshot:
    """Snapshot compte utilisé par le moteur de risque."""
    account_id: str
    trade_date: date
    cash: float
    equity: float
    buying_power: float
    high_watermark: float | None = None
    daily_realized_pnl: float | None = None
    daily_unrealized_pnl: float | None = None
    daily_total_pnl: float | None = None


@dataclass(frozen=True, slots=True)
class RiskDecisionRow:
    """Ligne à écrire dans risk_decisions."""
    run_id: str
    trade_date: date
    symbol: str
    decision: str
    reason: str
    score_used: float
    score_source: str
    entry_price: float
    proposed_shares: int
    approved_shares: int
    target_weight: float
    sector: str


@dataclass(frozen=True, slots=True)
class PortfolioTargetRow:
    """Ligne à écrire dans portfolio_targets."""
    run_id: str
    trade_date: date
    symbol: str
    shares: int
    entry_price: float
    target_weight: float
    sector: str
    score_used: float
    score_source: str
