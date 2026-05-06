"""Sprint S13.2 — Adapter Interactive Brokers (lecture seule).

Limité à ``get_account`` / ``get_positions`` / ``get_orders`` afin de
permettre le **failover read-only** (Sprint S13.5) sans exposer la
soumission d'ordres tant que la qualification TWS paper n'est pas faite.

Dépend de ``ib_insync`` (optionnel). En l'absence du package, l'adapter
reste importable mais lève :class:`IBKRUnavailableError` à l'instanciation.
"""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable

from core.broker_models import (
    AccountSnapshot,
    BrokerOrderSnapshot,
    BrokerPosition,
    OrderRequest,
)

LOGGER = logging.getLogger(__name__)


class IBKRUnavailableError(RuntimeError):
    """Levée quand ``ib_insync`` n'est pas installé ou TWS injoignable."""


class IBKRBrokerClient:
    """Adapter read-only Interactive Brokers."""

    name = "ibkr"

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 1,
        readonly: bool = True,
    ) -> None:
        try:
            import ib_insync  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            raise IBKRUnavailableError(
                "Le package 'ib_insync' n'est pas installé : pip install ib_insync"
            ) from exc

        self._ib_insync = ib_insync
        self._readonly = readonly
        self._ib = ib_insync.IB()
        try:
            self._ib.connect(host, port, clientId=client_id, readonly=readonly)
        except Exception as exc:  # noqa: BLE001
            raise IBKRUnavailableError(
                f"Connexion TWS impossible ({host}:{port}): {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # BrokerClient API
    # ------------------------------------------------------------------

    def get_account(self) -> AccountSnapshot:
        summary = {row.tag: row.value for row in self._ib.accountSummary()}
        equity = Decimal(str(summary.get("NetLiquidation", "0")))
        cash = Decimal(str(summary.get("TotalCashValue", "0")))
        buying_power = Decimal(str(summary.get("BuyingPower", str(cash))))
        return AccountSnapshot(
            account_id=str(summary.get("AccountCode", "ibkr")),
            equity=equity,
            cash=cash,
            buying_power=buying_power,
            currency=str(summary.get("Currency", "USD")),
            raw=summary,
        )

    def get_positions(self) -> list[BrokerPosition]:
        out: list[BrokerPosition] = []
        for pos in self._ib.positions():
            qty = Decimal(str(pos.position))
            avg = Decimal(str(pos.avgCost))
            out.append(BrokerPosition(
                symbol=str(pos.contract.symbol),
                qty=qty,
                avg_entry_price=avg,
                market_value=avg * abs(qty),
                side="buy" if qty >= 0 else "sell",
                raw={"contract": str(pos.contract), "account": pos.account},
            ))
        return out

    def get_orders(self, status: str = "all", since: datetime | None = None) -> list[BrokerOrderSnapshot]:
        trades = self._ib.openTrades() if status in {"all", "open", "new", "accepted"} else self._ib.trades()
        out: list[BrokerOrderSnapshot] = []
        for t in trades:
            o = t.order
            os_ = t.orderStatus
            out.append(BrokerOrderSnapshot(
                order_id=str(o.orderId),
                client_order_id=getattr(o, "orderRef", None) or None,
                symbol=str(t.contract.symbol),
                side="buy" if o.action.lower() == "buy" else "sell",
                qty=Decimal(str(o.totalQuantity)),
                filled_qty=Decimal(str(os_.filled)),
                avg_fill_price=(
                    Decimal(str(os_.avgFillPrice)) if os_.avgFillPrice else None
                ),
                status=_map_ibkr_status(os_.status),
                type=str(o.orderType).lower(),  # type: ignore[arg-type]
            ))
        return out

    def submit_order(self, request: OrderRequest) -> BrokerOrderSnapshot:
        """Soumet un ordre à TWS/Gateway (Sprint S21.3).

        Supporte ``market``, ``limit``, ``stop`` et ``stop_limit`` ; TIF
        ``day/gtc/ioc/fok``. Le bracket OCO peut être passé via
        ``request.extra = {"bracket": {"take_profit": ..., "stop_loss": ...}}``
        — il est alors transmis à ``ib_insync.IB.bracketOrder()``.
        """
        if self._readonly:
            raise IBKRUnavailableError(
                "IBKRBrokerClient est en mode lecture seule (readonly=True)."
            )
        contract = self._build_contract(request.symbol)
        order = self._build_order(request)
        bracket_cfg = (request.extra or {}).get("bracket") if request.extra else None

        if bracket_cfg:
            tp = float(bracket_cfg.get("take_profit"))
            sl = float(bracket_cfg.get("stop_loss"))
            qty = float(request.qty)
            limit_price = float(request.limit_price or 0.0)
            action = "BUY" if request.side == "buy" else "SELL"
            bracket = self._ib.bracketOrder(
                action, qty,
                limitPrice=limit_price,
                takeProfitPrice=tp,
                stopLossPrice=sl,
            )
            parent_trade = None
            for sub in bracket:
                if request.client_order_id and getattr(sub, "orderRef", "") == "":
                    sub.orderRef = request.client_order_id
                trade = self._ib.placeOrder(contract, sub)
                if parent_trade is None:
                    parent_trade = trade
            self._ib.waitOnUpdate(timeout=2)
            assert parent_trade is not None
            return self._snapshot_from_trade(parent_trade, request)

        trade = self._ib.placeOrder(contract, order)
        self._ib.waitOnUpdate(timeout=2)
        return self._snapshot_from_trade(trade, request)

    def cancel_order(self, order_id: str) -> bool:
        """Annule un ordre via son ``orderId`` IBKR (string)."""
        if self._readonly:
            raise IBKRUnavailableError("IBKRBrokerClient en lecture seule.")
        try:
            target_id = int(order_id)
        except (TypeError, ValueError):
            return False
        for trade in self._ib.openTrades():
            if int(getattr(trade.order, "orderId", -1)) == target_id:
                self._ib.cancelOrder(trade.order)
                self._ib.waitOnUpdate(timeout=2)
                return True
        return False

    def stream_trades(self, callback: Callable[[BrokerOrderSnapshot], None]) -> Any:
        """Abonne ``callback`` au flux ``orderStatusEvent`` de ib_insync.

        Retourne un handle (``unsubscribe``) qui détache l'écouteur.
        """

        def _handler(trade: Any) -> None:
            try:
                snap = self._snapshot_from_trade(trade, None)
                callback(snap)
            except Exception:  # noqa: BLE001
                LOGGER.exception("stream_trades callback failed")

        self._ib.orderStatusEvent += _handler

        def _unsubscribe() -> None:
            try:
                self._ib.orderStatusEvent -= _handler
            except Exception:  # noqa: BLE001
                pass

        return _unsubscribe

    # ------------------------------------------------------------------
    # Helpers internes (Sprint S21.3)
    # ------------------------------------------------------------------

    def _build_contract(
        self,
        symbol: str,
        *,
        sec_type: str = "STK",
        currency: str = "USD",
        exchange: str = "SMART",
        primary_exchange: str = "NASDAQ",
    ) -> Any:
        Stock = self._ib_insync.Stock
        return Stock(symbol, exchange, currency, primaryExchange=primary_exchange) \
            if sec_type == "STK" else self._ib_insync.Contract(
                symbol=symbol, secType=sec_type, currency=currency, exchange=exchange,
            )

    def _build_order(self, req: OrderRequest) -> Any:
        ib = self._ib_insync
        action = "BUY" if req.side == "buy" else "SELL"
        qty = float(req.qty)
        tif = (req.time_in_force or "day").upper()
        otype = req.type or "market"

        if otype == "market":
            order = ib.MarketOrder(action, qty)
        elif otype == "limit":
            if req.limit_price is None:
                raise ValueError("limit order requires limit_price")
            order = ib.LimitOrder(action, qty, float(req.limit_price))
        elif otype == "stop":
            if req.stop_price is None:
                raise ValueError("stop order requires stop_price")
            order = ib.StopOrder(action, qty, float(req.stop_price))
        elif otype == "stop_limit":
            if req.stop_price is None or req.limit_price is None:
                raise ValueError("stop_limit order requires stop_price and limit_price")
            order = ib.StopLimitOrder(
                action, qty, float(req.limit_price), float(req.stop_price),
            )
        else:
            raise ValueError(f"unsupported order type: {otype}")

        order.tif = tif
        if req.client_order_id:
            order.orderRef = req.client_order_id
        return order

    def _snapshot_from_trade(
        self, trade: Any, request: OrderRequest | None,
    ) -> BrokerOrderSnapshot:
        o = trade.order
        os_ = trade.orderStatus
        symbol = str(getattr(trade.contract, "symbol", request.symbol if request else ""))
        side: Any = "buy" if str(o.action).lower() == "buy" else "sell"
        return BrokerOrderSnapshot(
            order_id=str(getattr(o, "orderId", "")),
            client_order_id=getattr(o, "orderRef", None) or None,
            symbol=symbol,
            side=side,
            qty=Decimal(str(o.totalQuantity)),
            filled_qty=Decimal(str(getattr(os_, "filled", 0))),
            avg_fill_price=(
                Decimal(str(os_.avgFillPrice)) if getattr(os_, "avgFillPrice", 0) else None
            ),
            status=_map_ibkr_status(getattr(os_, "status", "")),
            type=str(getattr(o, "orderType", "")).lower(),  # type: ignore[arg-type]
        )

    def close(self) -> None:
        try:
            self._ib.disconnect()
        except Exception:  # noqa: BLE001
            pass


def _map_ibkr_status(s: str) -> str:
    s = (s or "").lower()
    return {
        "submitted": "accepted",
        "presubmitted": "pending",
        "filled": "filled",
        "cancelled": "canceled",
        "apicancelled": "canceled",
        "inactive": "rejected",
    }.get(s, "unknown")


__all__ = ["IBKRBrokerClient", "IBKRUnavailableError"]

