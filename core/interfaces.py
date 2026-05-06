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

from datetime import date, datetime
from typing import Any, Iterator, Mapping, Optional, Protocol, Sequence, runtime_checkable

import pandas as pd

from core.types import AccountId, Adjustment, Feed, Symbol
from core.broker_models import (  # noqa: F401  (re-export pour BrokerClient Protocol)
    AccountSnapshot,
    BrokerOrderSnapshot,
    BrokerPosition,
    OrderRequest,
)


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


@runtime_checkable
class BrokerPort(Protocol):
    """Interface d’abstraction pour un broker (Alpaca, IBKR, etc.)."""

    def submit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        type_: str = "market",
        **kwargs,
    ) -> str:
        """Soumet un ordre. Retourne l’ID de l’ordre broker."""
        ...

    def cancel_order(self, order_id: str) -> bool:
        """Annule un ordre en attente. Retourne True si annulé."""
        ...

    def get_order_status(self, order_id: str) -> str:
        """Retourne le statut de l’ordre (ex: FILLED, REJECTED, etc.)."""
        ...

    def get_positions(self) -> list:
        """Retourne la liste des positions courantes."""
        ...


# ---------------------------------------------------------------------------
# Sprint S13.1 — Interface ``BrokerClient`` formalisée multi-broker.
# ---------------------------------------------------------------------------

@runtime_checkable
class BrokerClient(Protocol):
    """Contrat unifié multi-broker (Alpaca, IBKR, Mock, …).

    Les implémentations doivent être substituables (Liskov) — vérification
    par ``tests/test_broker_interface_contract.py``.
    """

    name: str  # ex. "alpaca", "ibkr", "mock"

    def get_account(self) -> "AccountSnapshot":  # noqa: F821
        """Snapshot du compte (equity, cash, buying_power)."""
        ...

    def submit_order(self, request: "OrderRequest") -> "BrokerOrderSnapshot":  # noqa: F821
        """Soumet un ordre normalisé. Retourne le snapshot initial."""
        ...

    def get_positions(self) -> list["BrokerPosition"]:  # noqa: F821
        """Liste des positions courantes."""
        ...

    def cancel_order(self, order_id: str) -> bool:
        """Annule un ordre. Retourne ``True`` si l'annulation a été acceptée."""
        ...

    def get_orders(
        self,
        status: str = "all",
        since: datetime | None = None,
    ) -> list["BrokerOrderSnapshot"]:  # noqa: F821
        """Liste des ordres filtrés par statut et date de soumission."""
        ...

    def stream_trades(self, callback) -> Any:  # noqa: ANN001
        """Stream temps réel des trades. Retourne un context manager (`__enter__`/`__exit__`)."""
        ...


# ---------------------------------------------------------------------------
# Phase 2 — Protocols complémentaires (audit_core_common §2.1)
# ---------------------------------------------------------------------------

@runtime_checkable
class MarketDataPort(Protocol):
    """Fournisseur de données de marché temps quasi-réel (Alpaca, Finnhub...)."""

    def fetch_bars(
        self,
        symbol: Symbol | str,
        timeframe: str,
        start_date: Optional[str] = None,
        *,
        adjustment: Adjustment = "split",
        feed: Feed = "iex",
    ) -> list[dict[str, Any]]:
        """Retourne les bars OHLCV bruts (format provider) pour ``symbol``."""
        ...

    def fetch_latest_quotes(
        self, symbols: Sequence[Symbol | str]
    ) -> dict[str, dict[str, Any]]:
        """Retourne les dernières quotes (NBBO IEX) par symbole."""
        ...


@runtime_checkable
class BarsRepository(Protocol):
    """Persistance OHLCV (`stock_bars`, `stock_bars_daily`)."""

    def upsert_bars(
        self,
        symbol: Symbol | str,
        bars: pd.DataFrame,
        *,
        data_adjustment: str = "split",
        data_source: str = "alpaca_iex",
    ) -> int:
        """Insère/met à jour des bars. Retourne le nb de lignes affectées."""
        ...

    def load_bars(
        self,
        symbol: Symbol | str,
        start: date | None = None,
        end: date | None = None,
    ) -> pd.DataFrame:
        """Charge les bars sur ``[start, end]`` triés par date asc."""
        ...


@runtime_checkable
class ScoresRepository(Protocol):
    """Persistance et lecture de `stock_scores` (snapshot screener / selector)."""

    def list_candidates(self, *, limit: int | None = None) -> list[str]:
        """Liste de symboles candidats issus du dernier snapshot."""
        ...

    def upsert_scores(self, scores: pd.DataFrame) -> int:
        """Persiste un snapshot de scores. Retourne le nombre de lignes affectées."""
        ...


@runtime_checkable
class RiskRepository(Protocol):
    """Persistance des décisions risk_management (`risk_runs`, `risk_decisions`)."""

    def load_latest_decisions(self, account_id: AccountId | str) -> pd.DataFrame:
        """Décisions du dernier run risk pour un compte."""
        ...

    def record_run(self, run_payload: Mapping[str, Any]) -> str:
        """Persiste un run risk complet. Retourne le ``run_id``."""
        ...


@runtime_checkable
class ExecutionRepository(Protocol):
    """Persistance des runs et ordres execution_engine."""

    def record_run(self, run_payload: Mapping[str, Any]) -> str:
        """Persiste un run execution. Retourne le ``run_id``."""
        ...

    def load_orders(
        self, account_id: AccountId | str, since: date | datetime
    ) -> pd.DataFrame:
        """Charge les ordres exécutés depuis ``since`` pour un compte."""
        ...


@runtime_checkable
class NewsProvider(Protocol):
    """Fournisseur d'articles de presse (Alpaca News, EDGAR...)."""

    def iter_news_pages(
        self,
        start_utc: datetime,
        end_utc: datetime,
        symbols: Sequence[str] | None = None,
        limit: int = 50,
    ) -> Iterator[tuple[list[dict[str, Any]], str | None]]:
        """Itère par pages ``(items, next_page_token)``."""
        ...


@runtime_checkable
class CorporateActionProvider(Protocol):
    """Fournisseur de corporate actions (splits, dividendes, M&A...)."""

    def fetch_actions(
        self, symbol: Symbol | str, since: date
    ) -> list[dict[str, Any]]:
        """Retourne les corporate actions pour ``symbol`` depuis ``since``."""
        ...


@runtime_checkable
class ConvictionAggregator(Protocol):
    """Fusion conviction (cf. ``core/conviction.py``)."""

    def fuse(
        self,
        *,
        quant_score: float,
        predicted_proba: float | None,
    ) -> float:
        ...

