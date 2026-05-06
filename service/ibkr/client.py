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

    def submit_order(self, request: OrderRequest) -> BrokerOrderSnapshot:  # noqa: ARG002
        if self._readonly:
            raise IBKRUnavailableError(
                "IBKRBrokerClient est en mode lecture seule (Sprint S13.2)."
            )
        raise NotImplementedError("submit_order IBKR sera livré en Sprint S13-bis.")

    def cancel_order(self, order_id: str) -> bool:  # noqa: ARG002
        if self._readonly:
            raise IBKRUnavailableError("IBKRBrokerClient en lecture seule.")
        raise NotImplementedError

    def stream_trades(self, callback: Callable[[BrokerOrderSnapshot], None]) -> Any:
        raise NotImplementedError("stream_trades IBKR sera livré en Sprint S13-bis.")

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

