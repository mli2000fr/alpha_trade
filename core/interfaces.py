"""
core/interfaces.py
==================
Contrats (Protocol) partagés entre les modules du système Alpha Trade.

Ces interfaces permettent :
- Le remplacement facile des implémentations (ex: Alpaca → autre broker)
- Le mocking propre dans les tests (pas besoin d'un vrai engine/DB)
- La vérification statique via mypy (structural subtyping)

Usage:
    from core.interfaces import PriceRepository, ScoringEngine, RiskChecker

    def run_scan(repo: PriceRepository, scorer: ScoringEngine) -> pd.DataFrame:
        ...
"""
from __future__ import annotations

from datetime import date
from typing import Optional, Protocol, Sequence, runtime_checkable

import pandas as pd


# ---------------------------------------------------------------------------
# Couche données
# ---------------------------------------------------------------------------

@runtime_checkable
class PriceRepository(Protocol):
    """Fournisseur de données de prix journaliers (OHLCV)."""

    def load_prices(
        self,
        symbols: Sequence[str],
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> pd.DataFrame:
        """
        Retourne un DataFrame avec colonnes :
        [symbol, date, open, high, low, close, volume, adj_close]
        trié par (symbol, date).
        """
        ...

    def load_latest_close(self, symbols: Sequence[str]) -> pd.Series:
        """Retourne une Series indexée par symbol avec la dernière clôture ajustée."""
        ...


@runtime_checkable
class ScoreRepository(Protocol):
    """Fournisseur et persisteur de scores calculés (screener / selector)."""

    def load_scores(self, symbols: Sequence[str]) -> pd.DataFrame:
        """
        Retourne un DataFrame avec colonnes :
        [symbol, liquidity_val, relative_strength_index, total_score, sector, ...]
        """
        ...

    def upsert_scores(self, scores: pd.DataFrame) -> int:
        """Persiste un snapshot de scores. Retourne le nombre de lignes affectées."""
        ...


# ---------------------------------------------------------------------------
# Couche calcul / scoring
# ---------------------------------------------------------------------------

@runtime_checkable
class FactorEngine(Protocol):
    """Calcule les facteurs quantitatifs (MA, momentum, volatilité, etc.)."""

    def compute(self, prices: pd.DataFrame) -> pd.DataFrame:
        """
        Prend un DataFrame OHLCV multi-symboles et retourne un DataFrame
        avec les facteurs calculés (trend_score, vcp_score, …) par symbole.
        """
        ...


@runtime_checkable
class ScoringEngine(Protocol):
    """Combine facteurs et scores auxiliaires en un score final."""

    def score(self, factors: pd.DataFrame, aux_scores: pd.DataFrame) -> pd.DataFrame:
        """Retourne un DataFrame avec [symbol, raw_final_score, final_score, …]."""
        ...


@runtime_checkable
class SentimentProvider(Protocol):
    """Fournisseur de scores de sentiment agrégés par symbole ou secteur."""

    def get_sentiment_scores(
        self,
        symbols: Sequence[str],
        as_of: Optional[date] = None,
    ) -> pd.DataFrame:
        """
        Retourne un DataFrame avec colonnes :
        [symbol, sentiment_net_score, macro_impact_score, event_count]
        """
        ...


# ---------------------------------------------------------------------------
# Couche risque
# ---------------------------------------------------------------------------

@runtime_checkable
class RiskChecker(Protocol):
    """Vérifie les contraintes de risque avant génération d'ordres."""

    def check_position_size(self, symbol: str, proposed_shares: float, price: float) -> float:
        """
        Retourne le nombre de parts autorisé (≤ proposed_shares) selon les règles
        de sizing (ATR, Kelly, concentration sectorielle, etc.).
        """
        ...

    def is_circuit_breaker_active(self) -> bool:
        """Retourne True si le drawdown du portefeuille dépasse le seuil configuré."""
        ...


@runtime_checkable
class OrderManager(Protocol):
    """Soumission d'ordres vers le broker (Alpaca, IBKR, etc.)."""

    def submit_market_order(self, symbol: str, qty: float, side: str) -> str:
        """Soumet un ordre market. Retourne l'ID de l'ordre."""
        ...

    def cancel_order(self, order_id: str) -> bool:
        """Annule un ordre en attente. Retourne True si annulé avec succès."""
        ...

