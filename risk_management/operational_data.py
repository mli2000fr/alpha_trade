"""Adapters for operational account data consumed by risk management.

The risk layer must not depend on Alpaca payload details or execution database
rows.  This module normalizes both sources into one immutable snapshot used by
regime transitions, portfolio optimization and reconciliation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from execution_engine.broker_adapter import BrokerAdapter
from execution_engine.models import ExecutionFill
from risk_management.portfolio_optimizer import HoldingSnapshot
from risk_management.transition_handler import OpenOrder, OpenPosition


class OperationalDataUnavailable(RuntimeError):
    """Raised when a required operational snapshot cannot be safely built."""


@dataclass(frozen=True, slots=True)
class OperationalAccountSnapshot:
    """Account capacity normalized from a broker or historical snapshot."""

    account_id: str
    equity: float
    cash: float
    settled_cash: float
    buying_power: float
    as_of: datetime
    source: str


@dataclass(frozen=True, slots=True)
class OperationalDataSnapshot:
    """Complete operational input for one risk decision cycle."""

    account: OperationalAccountSnapshot
    positions: tuple[OpenPosition, ...]
    holdings: tuple[HoldingSnapshot, ...]
    open_orders: tuple[OpenOrder, ...]
    fills: tuple[ExecutionFill, ...] = ()

    @classmethod
    def from_raw(
        cls,
        *,
        account_id: str,
        account: Mapping[str, Any],
        positions: Iterable[Mapping[str, Any]],
        orders: Iterable[Mapping[str, Any]],
        fills: Iterable[ExecutionFill] = (),
        source: str,
        as_of: datetime | None = None,
    ) -> "OperationalDataSnapshot":
        captured_at = as_of or datetime.now(timezone.utc)
        normalized_account = _normalize_account(account_id, account, captured_at, source)
        normalized_positions = tuple(_normalize_position(raw) for raw in positions)
        normalized_orders = tuple(
            _normalize_order(raw)
            for raw in orders
            if _is_open_order(raw)
        )
        holdings = tuple(
            HoldingSnapshot(
                symbol=position.symbol,
                side=position.side,
                quantity=position.quantity,
                entry_price=position.avg_entry_price,
                current_price=position.current_price or position.avg_entry_price,
                has_open_order=any(order.symbol == position.symbol for order in normalized_orders),
            )
            for position in normalized_positions
        )
        return cls(
            account=normalized_account,
            positions=normalized_positions,
            holdings=holdings,
            open_orders=normalized_orders,
            fills=tuple(fills),
        )


class LiveBrokerOperationalDataAdapter:
    """Builds a fail-closed risk snapshot from the current broker state."""

    def __init__(self, broker: BrokerAdapter, *, account_id: str, broker_mode: str) -> None:
        self._broker = broker
        self._account_id = account_id
        self._broker_mode = broker_mode

    def capture(self, *, fills: Iterable[ExecutionFill] = ()) -> OperationalDataSnapshot:
        try:
            account = self._broker.get_account_snapshot()
            positions = self._broker.get_all_positions()
            orders = self._broker.list_recent_orders(status="open", limit=500)
        except Exception as exc:  # noqa: BLE001
            raise OperationalDataUnavailable("snapshot opérationnel broker indisponible") from exc
        if not isinstance(account, Mapping):
            raise OperationalDataUnavailable("snapshot compte broker invalide")
        return OperationalDataSnapshot.from_raw(
            account_id=self._account_id,
            account=account,
            positions=positions,
            orders=orders,
            fills=fills,
            source=f"broker:{self._broker_mode}",
        )


class BacktestOperationalDataAdapter:
    """Builds the same contract from explicitly supplied historical snapshots."""

    @staticmethod
    def build(
        *,
        account_id: str,
        account: Mapping[str, Any],
        positions: Iterable[Mapping[str, Any]] = (),
        orders: Iterable[Mapping[str, Any]] = (),
        fills: Iterable[ExecutionFill] = (),
        as_of: datetime,
        source: str = "backtest_historical_snapshot",
    ) -> OperationalDataSnapshot:
        return OperationalDataSnapshot.from_raw(
            account_id=account_id,
            account=account,
            positions=positions,
            orders=orders,
            fills=fills,
            source=source,
            as_of=as_of,
        )


def _normalize_account(
    account_id: str,
    account: Mapping[str, Any],
    as_of: datetime,
    source: str,
) -> OperationalAccountSnapshot:
    equity = _required_positive_float(account, "equity")
    buying_power = _required_non_negative_float(account, "buying_power")
    cash = _optional_float(account.get("cash"), default=0.0)
    settled_cash = _optional_float(account.get("settled_cash"), default=cash)
    return OperationalAccountSnapshot(
        account_id=account_id,
        equity=equity,
        cash=cash,
        settled_cash=settled_cash,
        buying_power=buying_power,
        as_of=as_of,
        source=source,
    )


def _normalize_position(raw: Mapping[str, Any]) -> OpenPosition:
    symbol = str(raw.get("symbol") or "").strip().upper()
    side = str(raw.get("side") or "").strip().lower()
    quantity = abs(_required_positive_float(raw, "qty"))
    if not symbol or side not in {"long", "short"}:
        raise OperationalDataUnavailable(f"position broker invalide pour {symbol or 'symbole absent'}")
    entry_price = _optional_float(raw.get("avg_entry_price"), default=0.0)
    current_price = _optional_float(raw.get("current_price"), default=0.0)
    return OpenPosition(
        symbol=symbol,
        side=side,
        quantity=quantity,
        avg_entry_price=entry_price,
        current_price=current_price if current_price > 0 else None,
        unrealized_pnl_pct=_optional_float(raw.get("unrealized_plpc"), default=0.0),
    )


def _normalize_order(raw: Mapping[str, Any]) -> OpenOrder:
    order_id = str(raw.get("id") or "").strip()
    symbol = str(raw.get("symbol") or "").strip().upper()
    side = str(raw.get("side") or "").strip().lower()
    if not order_id or not symbol or side not in {"buy", "sell"}:
        raise OperationalDataUnavailable("ordre broker ouvert invalide")
    return OpenOrder(
        order_id=order_id,
        symbol=symbol,
        side=side,
        order_type=str(raw.get("type") or "market").strip().lower(),
        quantity=_required_positive_float(raw, "qty"),
        filled_quantity=_optional_float(raw.get("filled_qty"), default=0.0),
        status=str(raw.get("status") or "open").strip().lower(),
    )


def _is_open_order(raw: Mapping[str, Any]) -> bool:
    return str(raw.get("status") or "open").strip().lower() not in {
        "filled", "canceled", "cancelled", "rejected", "expired", "failed",
    }


def _required_positive_float(raw: Mapping[str, Any], key: str) -> float:
    value = _optional_float(raw.get(key), default=0.0)
    if value <= 0:
        raise OperationalDataUnavailable(f"champ broker invalide: {key}")
    return value


def _required_non_negative_float(raw: Mapping[str, Any], key: str) -> float:
    value = _optional_float(raw.get(key), default=-1.0)
    if value < 0:
        raise OperationalDataUnavailable(f"champ broker invalide: {key}")
    return value


def _optional_float(value: Any, *, default: float) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except (TypeError, ValueError) as exc:
        raise OperationalDataUnavailable("champ broker non numérique") from exc