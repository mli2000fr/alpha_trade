"""Package ``core`` — contrats Protocols, types, helpers transverses.

Phase 2 du refactor (`prompt/refactor/plan.md`).

Expose une API publique stable que les modules amont consomment au lieu
d'importer directement des implémentations.
"""
from __future__ import annotations

from core.conviction import ConvictionWeights, compute_conviction, fuse
from core.filter_profiles import STRICT_SWING_CASH_FILTERS, StrictFilterProfile
from core.interfaces import (
    BarsRepository,
    BrokerPort,
    ConvictionAggregator,
    CorporateActionProvider,
    ExecutionRepository,
    FactorEngine,
    MarketDataPort,
    NewsProvider,
    OrderManager,
    PriceRepository,
    RiskChecker,
    RiskRepository,
    ScoreRepository,
    ScoresRepository,
    ScoringEngine,
    SentimentProvider,
)
from core.run_summary import attach_schema_version, merge_iex_bias_counters
from core.types import (
    AccountId,
    AccountMode,
    Adjustment,
    ExecutionRunId,
    Feed,
    OrderSide,
    OrderType,
    RiskRunId,
    RunId,
    Symbol,
    TimeInForce,
)

__all__ = [
    "BarsRepository", "BrokerPort", "ConvictionAggregator",
    "CorporateActionProvider", "ExecutionRepository", "FactorEngine",
    "MarketDataPort", "NewsProvider", "OrderManager", "PriceRepository",
    "RiskChecker", "RiskRepository", "ScoreRepository", "ScoresRepository",
    "ScoringEngine", "SentimentProvider",
    "AccountId", "AccountMode", "Adjustment", "ExecutionRunId", "Feed",
    "OrderSide", "OrderType", "RiskRunId", "RunId", "Symbol", "TimeInForce",
    "ConvictionWeights", "compute_conviction", "fuse",
    "STRICT_SWING_CASH_FILTERS", "StrictFilterProfile",
    "attach_schema_version", "merge_iex_bias_counters",
]

