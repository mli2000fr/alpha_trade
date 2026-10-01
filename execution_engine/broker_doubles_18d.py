"""Doubles OMS hors route paper/live : mock en mémoire et replay strict.

Ils n'importent ni client broker ni base de données. BrokerRouter refuse
explicitement ``simulated=True`` ; ces classes servent aux tests et aux
relectures déterministes, jamais à l'envoi d'ordres.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from execution_engine.models import BrokerOrder, CancelResult, OrderIntent, OrderStatus
from execution_engine.state_machine import map_alpaca_status


class ReplayMismatch(RuntimeError):
    """Une action OMS n'existe pas dans la bande de replay figée."""


_RAW_STATUS = {
    OrderStatus.NEW: "new",
    OrderStatus.HELD: "held",
    OrderStatus.SIMULATED: "accepted",
    OrderStatus.SUBMITTED: "accepted",
    OrderStatus.PARTIALLY_FILLED: "partially_filled",
    OrderStatus.FILLED: "filled",
    OrderStatus.CANCELED: "canceled",
    OrderStatus.REJECTED: "rejected",
    OrderStatus.FAILED: "failed",
    OrderStatus.EXPIRED: "expired",
}


class MockBrokerAdapter:
    """Accepte des intentions US localement, mais ne simule aucun fill automatique."""

    market_code = "US_EQ"
    simulated = True

    def __init__(self, *, account: Mapping[str, Any] | None = None,
                 positions: Mapping[str, Mapping[str, Any]] | None = None,
                 prices: Mapping[str, float] | None = None,
                 market_open: bool = True) -> None:
        self._account = dict(account or {"equity": "0", "cash": "0", "buying_power": "0"})
        self._positions = {symbol: dict(value) for symbol, value in (positions or {}).items()}
        self._prices = dict(prices or {})
        self._market_open = market_open
        self._orders: dict[str, BrokerOrder] = {}
        self._intent_to_order: dict[str, str] = {}
        self._oco_sibling: dict[str, str] = {}
        self._sequence = 0

    def _new_order(self, *, intent_id: str, symbol: str, side: str, qty: float,
                   order_type: str, limit_price: float | None = None,
                   stop_price: float | None = None,
                   trail_percent: float | None = None) -> BrokerOrder:
        if not intent_id or not symbol or side not in {"buy", "sell"} or qty <= 0:
            raise ValueError("Intention mock incomplète")
        if intent_id in self._intent_to_order:
            raise ReplayMismatch(f"Intention déjà soumise : {intent_id}")
        self._sequence += 1
        now = datetime.now(UTC)
        order = BrokerOrder(
            broker_order_id=f"mock-{self._sequence:06d}",
            client_order_id=intent_id, intent_id=intent_id,
            symbol=symbol, side=side, qty=float(qty), filled_qty=0,
            avg_fill_price=None, status=OrderStatus.SUBMITTED,
            order_type=order_type, limit_price=limit_price,
            stop_price=stop_price, trail_percent=trail_percent,
            created_at=now, updated_at=now,
        )
        self._orders[order.broker_order_id] = order
        self._intent_to_order[intent_id] = order.broker_order_id
        return order

    def submit_intent(self, intent: OrderIntent) -> BrokerOrder:
        return self._new_order(
            intent_id=intent.intent_id, symbol=intent.symbol,
            side=intent.side, qty=intent.qty, order_type=intent.order_type,
            limit_price=intent.limit_price, stop_price=intent.stop_price,
            trail_percent=intent.trail_percent,
        )

    def submit_market_order(self, *, symbol: str, qty: float, side: str,
                            intent_id: str) -> BrokerOrder:
        return self._new_order(intent_id=intent_id, symbol=symbol, side=side,
                               qty=qty, order_type="market")

    def submit_oco_protection(self, parent_intent: OrderIntent,
                              tp_intent: OrderIntent, stop_intent: OrderIntent
                              ) -> tuple[BrokerOrder, BrokerOrder]:
        if (len({parent_intent.symbol, tp_intent.symbol, stop_intent.symbol}) != 1
                or tp_intent.side != stop_intent.side
                or tp_intent.qty != stop_intent.qty
                or tp_intent.intent_id == stop_intent.intent_id
                or tp_intent.intent_id in self._intent_to_order
                or stop_intent.intent_id in self._intent_to_order):
            raise ValueError("Groupe OCO mock incohérent")
        tp = self.submit_intent(tp_intent)
        stop = self.submit_intent(stop_intent)
        self._oco_sibling[tp.broker_order_id] = stop.broker_order_id
        self._oco_sibling[stop.broker_order_id] = tp.broker_order_id
        return tp, stop

    def set_order_status(self, broker_order_id: str, status: str, *,
                         filled_qty: float = 0, avg_fill_price: float | None = None
                         ) -> BrokerOrder:
        """Injection explicite d'observation de test, jamais événement marché."""
        current = self._orders[broker_order_id]
        if current.status in OrderStatus.TERMINAL:
            raise ReplayMismatch("Ordre mock déjà terminal")
        if status not in _RAW_STATUS or not 0 <= filled_qty <= current.qty:
            raise ValueError("Statut/quantité mock invalide")
        if status == OrderStatus.FILLED and (filled_qty != current.qty or avg_fill_price is None):
            raise ValueError("Fill mock sans quantité/prix complet")
        changed = replace(current, status=status, filled_qty=float(filled_qty),
                          avg_fill_price=avg_fill_price, updated_at=datetime.now(UTC))
        self._orders[broker_order_id] = changed
        if status == OrderStatus.FILLED and broker_order_id in self._oco_sibling:
            sibling_id = self._oco_sibling[broker_order_id]
            sibling = self._orders[sibling_id]
            if sibling.status not in OrderStatus.TERMINAL:
                self._orders[sibling_id] = replace(
                    sibling, status=OrderStatus.CANCELED, updated_at=datetime.now(UTC))
        return changed

    def poll_order_status(self, broker_order_id: str, intent_id: str = "") -> BrokerOrder:
        order = self._orders[broker_order_id]
        if intent_id and order.intent_id != intent_id:
            raise ReplayMismatch("Identité d'intention différente de l'ordre mock")
        return order

    def cancel_broker_order(self, broker_order_id: str) -> bool:
        order = self._orders[broker_order_id]
        if order.status in OrderStatus.TERMINAL:
            return False
        self._orders[broker_order_id] = replace(
            order, status=OrderStatus.CANCELED, updated_at=datetime.now(UTC))
        return True

    def replace_stop_order(self, existing_broker_order_id: str,
                           new_stop_intent: OrderIntent) -> BrokerOrder:
        if not self.cancel_broker_order(existing_broker_order_id):
            raise ReplayMismatch("Ancien stop non annulable")
        return self.submit_intent(new_stop_intent)

    def cancel_all_open_orders(self, *, dry_run: bool = False) -> list[CancelResult]:
        results = []
        for order in list(self._orders.values()):
            if order.status in OrderStatus.TERMINAL:
                continue
            if dry_run:
                results.append(CancelResult(order.broker_order_id, order.symbol,
                                            canceled=True, error="dry_run"))
            else:
                results.append(CancelResult(order.broker_order_id, order.symbol,
                                            canceled=self.cancel_broker_order(order.broker_order_id)))
        return results

    def list_recent_orders(self, *, status: str = "all", limit: int = 500,
                           symbols: list[str] | None = None) -> list[dict[str, Any]]:
        if status not in {"all", "open", "closed"} or limit < 1:
            raise ValueError("Filtre de liste mock invalide")
        allowed = set(symbols) if symbols is not None else None
        result = []
        for order in reversed(tuple(self._orders.values())):
            if allowed is not None and order.symbol not in allowed:
                continue
            terminal = order.status in OrderStatus.TERMINAL
            if (status == "open" and terminal) or (status == "closed" and not terminal):
                continue
            result.append({
                "id": order.broker_order_id, "client_order_id": order.client_order_id,
                "symbol": order.symbol, "side": order.side, "qty": str(order.qty),
                "filled_qty": str(order.filled_qty), "filled_avg_price": order.avg_fill_price,
                "status": _RAW_STATUS[order.status], "type": order.order_type,
                "limit_price": order.limit_price, "stop_price": order.stop_price,
                "trail_percent": order.trail_percent,
                "created_at": order.created_at.isoformat() if order.created_at else None,
                "updated_at": order.updated_at.isoformat() if order.updated_at else None,
            })
            if len(result) >= limit:
                break
        return result

    def broker_order_from_api(self, payload: dict[str, Any], *,
                              intent_id: str = "") -> BrokerOrder:
        """Convertit une ligne de bande mock ; aucun accès réseau."""
        def _timestamp(value: Any) -> datetime | None:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else None

        return BrokerOrder(
            broker_order_id=str(payload.get("id") or ""),
            client_order_id=str(payload.get("client_order_id") or ""),
            intent_id=intent_id, symbol=str(payload.get("symbol") or ""),
            side=str(payload.get("side") or ""), qty=float(payload.get("qty") or 0),
            filled_qty=float(payload.get("filled_qty") or 0),
            avg_fill_price=float(payload["filled_avg_price"])
            if payload.get("filled_avg_price") not in (None, "") else None,
            status=map_alpaca_status(str(payload.get("status") or "failed")),
            order_type=str(payload.get("type") or ""),
            limit_price=float(payload["limit_price"])
            if payload.get("limit_price") not in (None, "") else None,
            stop_price=float(payload["stop_price"])
            if payload.get("stop_price") not in (None, "") else None,
            trail_percent=float(payload["trail_percent"])
            if payload.get("trail_percent") not in (None, "") else None,
            created_at=_timestamp(payload.get("created_at")),
            updated_at=_timestamp(payload.get("updated_at")),
        )

    def get_position(self, symbol: str) -> dict[str, Any] | None:
        value = self._positions.get(symbol)
        return dict(value) if value is not None else None

    def get_all_positions(self) -> list[dict[str, Any]]:
        return [dict(value) for _, value in sorted(self._positions.items())]

    def get_account_snapshot(self) -> dict[str, Any]:
        return dict(self._account)

    def get_account_equity(self) -> float:
        return float(self._account.get("equity") or 0)

    def get_latest_market_price(self, symbol: str) -> float | None:
        return self._prices.get(symbol)

    def is_market_open(self) -> bool:
        return self._market_open


class ReplayBrokerAdapter(MockBrokerAdapter):
    """Rejoue uniquement les soumissions et observations pré-enregistrées."""

    def __init__(self, *, submissions: Mapping[str, BrokerOrder],
                 polls: Mapping[str, Sequence[BrokerOrder]] | None = None,
                 cancellations: frozenset[str] = frozenset(),
                 account: Mapping[str, Any] | None = None,
                 positions: Mapping[str, Mapping[str, Any]] | None = None,
                 prices: Mapping[str, float] | None = None,
                 market_open: bool = True) -> None:
        super().__init__(account=account, positions=positions, prices=prices,
                         market_open=market_open)
        self._submissions = dict(submissions)
        self._polls = {key: tuple(value) for key, value in (polls or {}).items()}
        self._poll_index: dict[str, int] = {}
        self._cancellations = cancellations

    def _recorded_submit(self, *, intent_id: str, symbol: str, side: str,
                         qty: float) -> BrokerOrder:
        order = self._submissions.get(intent_id)
        if (order is None or intent_id in self._intent_to_order
                or order.intent_id != intent_id or order.symbol != symbol
                or order.side != side or order.qty != qty
                or order.broker_order_id in self._orders):
            raise ReplayMismatch(f"Soumission absente ou divergente du replay : {intent_id}")
        self._orders[order.broker_order_id] = order
        self._intent_to_order[intent_id] = order.broker_order_id
        return order

    def submit_intent(self, intent: OrderIntent) -> BrokerOrder:
        return self._recorded_submit(intent_id=intent.intent_id, symbol=intent.symbol,
                                     side=intent.side, qty=intent.qty)

    def submit_market_order(self, *, symbol: str, qty: float, side: str,
                            intent_id: str) -> BrokerOrder:
        return self._recorded_submit(intent_id=intent_id, symbol=symbol,
                                     side=side, qty=qty)

    def poll_order_status(self, broker_order_id: str, intent_id: str = "") -> BrokerOrder:
        current = super().poll_order_status(broker_order_id, intent_id)
        events = self._polls.get(broker_order_id)
        if not events:
            raise ReplayMismatch(f"Aucun polling enregistré : {broker_order_id}")
        index = self._poll_index.get(broker_order_id, 0)
        if index >= len(events):
            raise ReplayMismatch(f"Bande de polling épuisée : {broker_order_id}")
        observed = events[index]
        if (observed.broker_order_id != broker_order_id
                or observed.intent_id != current.intent_id
                or observed.symbol != current.symbol
                or observed.side != current.side or observed.qty != current.qty):
            raise ReplayMismatch("Observation broker étrangère à l'ordre rejoué")
        self._poll_index[broker_order_id] = index + 1
        self._orders[broker_order_id] = observed
        return observed

    def cancel_broker_order(self, broker_order_id: str) -> bool:
        if broker_order_id not in self._cancellations:
            raise ReplayMismatch(f"Annulation absente du replay : {broker_order_id}")
        return super().cancel_broker_order(broker_order_id)

    def set_order_status(self, broker_order_id: str, status: str, *,
                         filled_qty: float = 0, avg_fill_price: float | None = None
                         ) -> BrokerOrder:
        raise ReplayMismatch("Le replay ne peut observer que sa bande de polling")
