"""Couche d'isolation broker — seul ce fichier change si on change de broker."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from execution_engine.config import ExecutionConfig
from execution_engine.models import BrokerOrder, OrderIntent
from execution_engine.order_intents import intent_to_alpaca_payload
from execution_engine.state_machine import map_alpaca_status
from service.alpaca.clientAlpaca import fetch_latest_quotes
from service.alpaca.trading_client import AlpacaTradingClient

LOGGER = logging.getLogger(__name__)


class BrokerAdapter:
    """Adapte AlpacaTradingClient vers les types internes execution_engine."""

    def __init__(self, client: AlpacaTradingClient, config: ExecutionConfig) -> None:
        self._client = client
        self._config = config

    def submit_intent(self, intent: OrderIntent) -> BrokerOrder:
        payload = intent_to_alpaca_payload(intent)
        resp = self._client.submit_order(payload)
        return self._resp_to_broker_order(resp, intent.intent_id)

    def poll_order_status(self, broker_order_id: str, intent_id: str = "") -> BrokerOrder:
        resp = self._client.get_order(broker_order_id)
        return self._resp_to_broker_order(resp, intent_id)

    def cancel_broker_order(self, broker_order_id: str) -> bool:
        return self._client.cancel_order(broker_order_id)

    def list_recent_orders(
        self,
        *,
        status: str = "all",
        limit: int = 500,
        symbols: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        return self._client.list_orders(status=status, limit=limit, symbols=symbols)  # type: ignore[return-value]

    def get_all_positions(self) -> list[dict[str, Any]]:
        return self._client.get_positions()  # type: ignore[return-value]

    def is_market_open(self) -> bool:
        return self._client.is_market_open()

    def get_account_snapshot(self) -> dict[str, Any]:
        return self._client.get_account()  # type: ignore[return-value]

    def get_account_equity(self) -> float:
        acc = self.get_account_snapshot()
        return float(acc.get("equity", 0))

    def get_latest_market_price(self, symbol: str) -> float | None:
        try:
            position = self._client.get_position(symbol)
            if isinstance(position, dict):
                current_price = position.get("current_price")
                if current_price not in (None, ""):
                    return float(current_price)
                qty = float(position.get("qty", 0) or 0)
                market_value = position.get("market_value")
                if qty > 0 and market_value not in (None, ""):
                    return float(market_value) / qty
        except Exception:
            LOGGER.debug("Position broker indisponible pour %s lors de l'évaluation trailing.", symbol, exc_info=True)

        try:
            quotes = fetch_latest_quotes([symbol], account_id=self._config.account_id)
            quote = quotes.get(symbol) or quotes.get(symbol.upper())
            if isinstance(quote, dict):
                bid = quote.get("bp")
                ask = quote.get("ap")
                if bid not in (None, "") and ask not in (None, ""):
                    return (float(bid) + float(ask)) / 2.0
                if ask not in (None, ""):
                    return float(ask)
                if bid not in (None, ""):
                    return float(bid)
        except Exception:
            LOGGER.debug("Quote Alpaca indisponible pour %s lors de l'évaluation trailing.", symbol, exc_info=True)
        return None

    def broker_order_from_api(self, payload: dict[str, Any], *, intent_id: str = "") -> BrokerOrder:
        return self._resp_to_broker_order(payload, intent_id)

    @staticmethod
    def _resp_to_broker_order(resp: dict[str, Any], intent_id: str) -> BrokerOrder:
        def _ts(val: Any) -> datetime | None:
            if val is None:
                return None
            try:
                return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                return None

        return BrokerOrder(
            broker_order_id=str(resp.get("id", "")),
            client_order_id=str(resp.get("client_order_id", "")),
            intent_id=intent_id,
            symbol=str(resp.get("symbol", "")),
            side=str(resp.get("side", "")),
            qty=float(resp.get("qty", 0)),
            filled_qty=float(resp.get("filled_qty", 0)),
            avg_fill_price=float(resp["filled_avg_price"]) if resp.get("filled_avg_price") else None,
            status=map_alpaca_status(str(resp.get("status", "failed"))),
            order_type=str(resp.get("type", "")),
            limit_price=float(resp["limit_price"]) if resp.get("limit_price") else None,
            stop_price=float(resp["stop_price"]) if resp.get("stop_price") else None,
            trail_percent=float(resp["trail_percent"]) if resp.get("trail_percent") else None,
            created_at=_ts(resp.get("created_at")),
            updated_at=_ts(resp.get("updated_at")),
        )

