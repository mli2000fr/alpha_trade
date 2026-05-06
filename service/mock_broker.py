"""Sprint S13.3 — ``MockBroker`` déterministe pour tests sandbox & CI.

API :class:`BrokerClient` 100 % implémentée en mémoire. Idéal pour :

- Tests E2E déterministes (graine ``seed`` rejouable).
- CI nightly sandbox (cf. ``.github/workflows/sandbox_nightly.yml``).
- Mock IBKR offline en attendant les credentials TWS.
"""
from __future__ import annotations

import logging
import threading
from contextlib import AbstractContextManager
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from decimal import Decimal
from random import Random
from typing import Any, Callable

from core.broker_models import (
    AccountSnapshot,
    BrokerOrderSnapshot,
    BrokerPosition,
    OrderRequest,
    OrderSide,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class _StreamCtx(AbstractContextManager):
    cb: Callable[[BrokerOrderSnapshot], None]
    broker: "MockBroker"

    def __enter__(self) -> "_StreamCtx":
        self.broker._subscribers.append(self.cb)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            self.broker._subscribers.remove(self.cb)
        except ValueError:  # pragma: no cover
            pass


@dataclass
class MockBroker:
    """Implémentation in-memory déterministe de :class:`core.interfaces.BrokerClient`.

    Tous les ``order_id`` sont dérivés du ``seed`` → reproductibilité totale.
    Les fills sont synchrones par défaut (``auto_fill=True``).
    """

    seed: int = 42
    starting_cash: Decimal = Decimal("100000")
    auto_fill: bool = True
    name: str = "mock"

    _rng: Random = field(init=False)
    _orders: dict[str, BrokerOrderSnapshot] = field(default_factory=dict, init=False)
    _positions: dict[str, BrokerPosition] = field(default_factory=dict, init=False)
    _cash: Decimal = field(init=False)
    _equity: Decimal = field(init=False)
    _counter: int = field(default=0, init=False)
    _subscribers: list[Callable[[BrokerOrderSnapshot], None]] = field(default_factory=list, init=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False)

    def __post_init__(self) -> None:
        self._rng = Random(self.seed)
        self._cash = Decimal(str(self.starting_cash))
        self._equity = Decimal(str(self.starting_cash))

    # ------------------------------------------------------------------
    # BrokerClient API
    # ------------------------------------------------------------------

    def get_account(self) -> AccountSnapshot:
        with self._lock:
            return AccountSnapshot(
                account_id=f"mock-{self.seed}",
                equity=self._equity,
                cash=self._cash,
                buying_power=self._cash * Decimal("2"),  # marge 2x
                currency="USD",
            )

    def submit_order(self, request: OrderRequest) -> BrokerOrderSnapshot:
        with self._lock:
            self._counter += 1
            order_id = f"mock-{self.seed}-{self._counter:06d}"
            now = datetime.now(timezone.utc)
            qty = Decimal(str(request.qty))
            fill_price = self._fake_price(request.symbol, request.side, request)
            status = "filled" if self.auto_fill else "accepted"
            filled_qty = qty if self.auto_fill else Decimal("0")
            snap = BrokerOrderSnapshot(
                order_id=order_id,
                client_order_id=request.client_order_id,
                symbol=request.symbol,
                side=request.side,
                qty=qty,
                filled_qty=filled_qty,
                avg_fill_price=fill_price if self.auto_fill else None,
                status=status,
                type=request.type,
                submitted_at=now,
                updated_at=now,
            )
            self._orders[order_id] = snap
            if self.auto_fill:
                self._apply_fill(request.symbol, request.side, qty, fill_price)
            self._emit(snap)
            return snap

    def get_positions(self) -> list[BrokerPosition]:
        with self._lock:
            return list(self._positions.values())

    def cancel_order(self, order_id: str) -> bool:
        with self._lock:
            snap = self._orders.get(order_id)
            if snap is None or snap.status in {"filled", "canceled", "rejected", "expired"}:
                return False
            new_snap = replace(snap, status="canceled", updated_at=datetime.now(timezone.utc))
            self._orders[order_id] = new_snap
            self._emit(new_snap)
            return True

    def get_orders(self, status: str = "all", since: datetime | None = None) -> list[BrokerOrderSnapshot]:
        with self._lock:
            out = list(self._orders.values())
        if status != "all":
            out = [o for o in out if o.status == status]
        if since is not None:
            out = [o for o in out if (o.submitted_at or datetime.min.replace(tzinfo=timezone.utc)) >= since]
        return out

    def stream_trades(self, callback: Callable[[BrokerOrderSnapshot], None]) -> _StreamCtx:
        return _StreamCtx(cb=callback, broker=self)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _fake_price(self, symbol: str, side: OrderSide, request: OrderRequest) -> Decimal:
        if request.limit_price is not None:
            return Decimal(str(request.limit_price))
        # Prix pseudo-aléatoire mais déterministe (seed-based).
        base = Decimal(str(50 + (hash(symbol) % 200)))
        jitter = Decimal(str(round(self._rng.uniform(-0.5, 0.5), 4)))
        return (base + jitter).quantize(Decimal("0.0001"))

    def _apply_fill(self, symbol: str, side: OrderSide, qty: Decimal, price: Decimal) -> None:
        signed_qty = qty if side == "buy" else -qty
        cost = price * qty
        self._cash -= cost if side == "buy" else -cost
        existing = self._positions.get(symbol)
        if existing is None:
            new_qty = signed_qty
            self._positions[symbol] = BrokerPosition(
                symbol=symbol, qty=new_qty,
                avg_entry_price=price,
                market_value=price * abs(new_qty),
                side="buy" if new_qty >= 0 else "sell",
            )
        else:
            new_qty = existing.qty + signed_qty
            if new_qty == 0:
                self._positions.pop(symbol, None)
            else:
                # Moyenne pondérée best-effort.
                total = existing.qty * existing.avg_entry_price + signed_qty * price
                avg = total / new_qty if new_qty != 0 else price
                self._positions[symbol] = BrokerPosition(
                    symbol=symbol, qty=new_qty, avg_entry_price=avg,
                    market_value=price * abs(new_qty),
                    side="buy" if new_qty >= 0 else "sell",
                )
        self._equity = self._cash + sum(
            (p.market_value for p in self._positions.values()), Decimal("0"),
        )

    def _emit(self, snap: BrokerOrderSnapshot) -> None:
        for cb in list(self._subscribers):
            try:
                cb(snap)
            except Exception:  # noqa: BLE001
                LOGGER.warning("MockBroker subscriber failed", exc_info=True)


__all__ = ["MockBroker"]



