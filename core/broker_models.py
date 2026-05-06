"""Sprint S13.1 — Modèles partagés pour l'interface ``BrokerClient``.

Placés dans ``core/`` pour éviter le cycle import ``execution_engine`` ↔
``service``. Les implémentations (Alpaca, IBKR, Mock) consomment ces
dataclasses.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

OrderSide = Literal["buy", "sell"]
OrderType = Literal["market", "limit", "stop", "stop_limit"]
TimeInForce = Literal["day", "gtc", "ioc", "fok", "opg", "cls"]
OrderStatus = Literal[
    "new", "accepted", "pending", "partially_filled", "filled",
    "canceled", "rejected", "expired", "unknown",
]


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    """Snapshot lecture seule du compte broker."""

    account_id: str
    equity: Decimal
    cash: Decimal
    buying_power: Decimal
    currency: str = "USD"
    pattern_day_trader: bool = False
    trading_blocked: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BrokerPosition:
    """Position broker temps quasi-réel."""

    symbol: str
    qty: Decimal
    avg_entry_price: Decimal
    market_value: Decimal
    unrealized_pl: Decimal | None = None
    side: OrderSide = "buy"
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OrderRequest:
    """Requête d'ordre normalisée broker-agnostic."""

    symbol: str
    qty: Decimal
    side: OrderSide
    type: OrderType = "market"
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: TimeInForce = "day"
    client_order_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BrokerOrderSnapshot:
    """État d'un ordre côté broker (vue lecture)."""

    order_id: str
    client_order_id: str | None
    symbol: str
    side: OrderSide
    qty: Decimal
    filled_qty: Decimal
    avg_fill_price: Decimal | None
    status: OrderStatus
    type: OrderType
    submitted_at: datetime | None = None
    updated_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "AccountSnapshot",
    "BrokerPosition",
    "OrderRequest",
    "BrokerOrderSnapshot",
    "OrderSide",
    "OrderType",
    "TimeInForce",
    "OrderStatus",
]

