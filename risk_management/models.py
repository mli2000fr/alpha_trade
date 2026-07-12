"""Modèles de données internes au module risk_management."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from risk_management.enums import Decision, DecisionReasonCode, SizingMethod


# ---------------------------------------------------------------------------
# Factor Risk Model (Priorité 3 — RisqueSectoriel.md)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FactorExposures:
    """Expositions factorielles normalisées pour un titre à une date donnée.

    Modèle CWMS à 4 facteurs (Country + World + Market-cap + Style) :
    - market_beta : beta_126 vs SPY (déjà calculé par ``compute_factor_frame``)
    - size_exposure : z-score log(market_cap) cross-sectional (≈ SMB)
    - momentum_exposure : z-score trend_score cross-sectional (≈ WML)
    - value_exposure : z-score earnings_yield cross-sectional (≈ HML)
    """

    symbol: str
    date: date
    market_beta: float = 1.0
    size_exposure: float = 0.0
    momentum_exposure: float = 0.0
    value_exposure: float = 0.0


@dataclass(frozen=True, slots=True)
class SelectionScore:
    """Score exploitable lu depuis un snapshot de scores."""
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
    selection_rank: int | None = None
    selector_signal_mode: str | None = None
    selection_explanation: str | None = None
    selector_earnings_blackout: int | None = None
    # Sprint 1 short — direction canonique
    side: str = "buy"
    # ── Section 17 Point 2.2 : lineage univers ─────────────────────────
    universe_run_id: str | None = None


@dataclass(frozen=True, slots=True)
class PriceInfo:
    """Dernières informations de prix pour un symbole."""
    symbol: str
    last_close: float
    atr_20: float | None
    price_asof_date: date | None = None
    atr_asof_date: date | None = None
    # Liquidité : ADV 20 jours en dollars (close × volume moyen).
    # None = donnée indisponible → contrainte ADV ignorée silencieusement.
    adv_usd: float | None = None


@dataclass(frozen=True, slots=True)
class SizingResult:
    """Résultat du calcul de taille de position."""
    symbol: str
    proposed_shares: float
    method: SizingMethod


@dataclass(frozen=True, slots=True)
class PortfolioEntry:
    """Ligne du portefeuille cible construit."""
    symbol: str
    sector: str
    entry_price: float
    score_used: float
    score_source: str
    atr_20: float | None
    proposed_shares: float
    approved_shares: float
    target_notional: float
    target_weight: float
    decision: Decision
    decision_reason: str
    decision_reason_code: DecisionReasonCode | None = None

    # --- V2 audit fields ---
    conviction_score: float = 0.0
    predicted_proba: float | None = None
    historical_win_rate: float | None = None
    effective_probability: float | None = None
    kelly_fraction: float | None = None
    sizing_method: SizingMethod = SizingMethod.UNKNOWN
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
    selection_rank: int | None = None
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
    # Sprint 1 short
    side: str = "buy"
    # ── Sprint Maître 0 / Section 17 Point 3 ───────────────────────────
    trade_date: date | None = None
    entry_date: date | None = None


@dataclass(frozen=True, slots=True)
class PredictionInfo:
    """Dernière prédiction ML pour un symbole."""
    symbol: str
    predicted_proba: float
    predicted_class: int
    run_id: str
    prediction_date: date | None = None
    # ML Sprint 3 — colonnes ternaires optionnelles
    predicted_side: str | None = None   # "long" | "flat" | "short"
    proba_long: float | None = None
    proba_flat: float | None = None
    proba_short: float | None = None
    # ── Sprint Maître 0 : statut research_only ─────────────────────────
    research_only: bool = False
    # ── Section 17 Point 2.2 : lineage univers ─────────────────────────
    universe_run_id: str | None = None


@dataclass(frozen=True, slots=True)
class WinRateInfo:
    """Proxy de win rate historique depuis model_metrics."""
    symbol: str
    directional_accuracy: float
    split_name: str
    run_id: str
    asof_date: date | None = None


@dataclass(frozen=True, slots=True)
class DirectionalWinRateInfo:
    """Statistiques directionnelles OOS (Sprint Maître 8).

    Remplace ``WinRateInfo`` pour le sizing Kelly directionnel.
    Permet un Kelly asymétrique long/short avec payoff réel,
    tail loss calibré et shrinkage bayésien.

    Attributes
    ----------
    symbol : str
    side : str
        ``"long"`` ou ``"short"``.
    hit_rate : float
        Taux de trades gagnants OOS (0-1).
    payoff : float
        Ratio gain moyen / perte moyenne.
    tail_loss : float | None
        Pire perte observée en % (positive, ex: 0.15 = 15%).
    trade_count : int
        Nombre de trades OOS pour ce side.
    split_name : str
        Nom du split OOS utilisé.
    run_id : str
        Identifiant du run modèle.
    asof_date : date | None
        Date de calibration des statistiques.
    """

    symbol: str
    side: str
    hit_rate: float
    payoff: float
    tail_loss: float | None = None
    trade_count: int = 0
    split_name: str = ""
    run_id: str = ""
    asof_date: date | None = None

    def __post_init__(self) -> None:
        if self.side not in ("long", "short"):
            raise ValueError(f"side invalide: {self.side!r}")
        if not (0.0 <= self.hit_rate <= 1.0):
            raise ValueError(f"hit_rate hors bornes: {self.hit_rate}")
        if self.payoff < 0:
            raise ValueError(f"payoff doit être >= 0: {self.payoff}")


@dataclass(frozen=True, slots=True)
class CorrelationRejection:
    """Résultat d'un rejet par filtre de corrélation."""
    rejected_symbol: str
    blocker_symbol: str
    correlation_value: float
    threshold: float


@dataclass(frozen=True, slots=True)
class EnrichedSelection:
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
    selection_rank: int | None = None
    selector_signal_mode: str | None = None
    selection_explanation: str | None = None
    selector_earnings_blackout: int | None = None
    # Sprint 1 short
    side: str = "buy"


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
    source: str | None = None


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
    proposed_shares: float
    approved_shares: float
    target_weight: float
    sector: str
    # Sprint 1 short
    side: str = "buy"


@dataclass(frozen=True, slots=True)
class PortfolioTargetRow:
    """Ligne à écrire dans portfolio_targets."""
    run_id: str
    trade_date: date
    symbol: str
    shares: float
    entry_price: float
    target_weight: float
    sector: str
    score_used: float
    score_source: str
    # Sprint 1 short
    side: str = "buy"
