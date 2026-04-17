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


@dataclass(frozen=True, slots=True)
class PriceInfo:
    """Dernières informations de prix pour un symbole."""
    symbol: str
    last_close: float
    atr_20: float | None


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
