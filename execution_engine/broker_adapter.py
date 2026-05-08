"""Couche d'isolation broker — seul ce fichier change si on change de broker."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from execution_engine.config import ExecutionConfig
from execution_engine.models import BrokerOrder, OrderIntent
from execution_engine.order_intents import build_oco_protection_payload, intent_to_alpaca_payload
from execution_engine.state_machine import map_alpaca_status
from service.alpaca.clientAlpaca import fetch_latest_quotes
from service.alpaca.trading_client import AlpacaTradingClient, BrokerApiError

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CancelResult:
    """Phase 5.2.c — Résultat d'une annulation unitaire (kill switch)."""

    broker_order_id: str
    symbol: str
    canceled: bool
    error: str | None = None


class BrokerAdapter:
    """Adapte AlpacaTradingClient vers les types internes execution_engine."""

    def __init__(self, client: AlpacaTradingClient, config: ExecutionConfig) -> None:
        self._client = client
        self._config = config

    def submit_intent(self, intent: OrderIntent) -> BrokerOrder:
        payload = intent_to_alpaca_payload(intent)
        resp = self._client.submit_order(payload)
        return self._resp_to_broker_order(resp, intent.intent_id)

    def submit_oco_protection(
        self,
        parent_intent: OrderIntent,
        tp_intent: OrderIntent,
        stop_intent: OrderIntent,
    ) -> tuple[BrokerOrder, BrokerOrder]:
        """Soumet TP + SL en une seule commande Alpaca OCO.

        Évite l'erreur 403 ``insufficient qty`` provoquée par deux soumissions
        séquentielles (le premier ordre verrouille la quantité, le second se
        voit refuser la même qty). Retourne ``(tp_order, stop_order)`` —
        l'ordre TP est porté par la réponse principale et le SL par la
        première leg.
        """
        payload = build_oco_protection_payload(parent_intent, tp_intent, stop_intent)
        resp = self._client.submit_order(payload)  # type: ignore[arg-type]
        tp_order = self._resp_to_broker_order(resp, tp_intent.intent_id)
        legs = resp.get("legs") if isinstance(resp, dict) else None
        stop_leg: dict[str, Any] | None = None
        if isinstance(legs, list):
            for leg in legs:
                if isinstance(leg, dict) and str(leg.get("type", "")).startswith("stop"):
                    stop_leg = leg
                    break
            if stop_leg is None and legs:
                first = legs[0]
                if isinstance(first, dict):
                    stop_leg = first
        if stop_leg is None:
            raise BrokerApiError(
                500,
                "OCO submission did not return a stop_loss leg",
                str(resp)[:500],
            )
        stop_order = self._resp_to_broker_order(stop_leg, stop_intent.intent_id)
        return tp_order, stop_order

    def get_position(self, symbol: str) -> dict[str, Any] | None:
        """Retourne la position broker pour ``symbol`` ou ``None`` si absente."""
        try:
            return self._client.get_position(symbol)  # type: ignore[return-value]
        except Exception:
            LOGGER.debug("get_position failed for %s", symbol, exc_info=True)
            return None

    def poll_order_status(self, broker_order_id: str, intent_id: str = "") -> BrokerOrder:
        resp = self._client.get_order(broker_order_id)
        return self._resp_to_broker_order(resp, intent_id)

    def cancel_broker_order(self, broker_order_id: str) -> bool:
        return self._client.cancel_order(broker_order_id)

    def cancel_all_open_orders(self, *, dry_run: bool = False) -> list[CancelResult]:
        """Phase 5.2.c — Kill switch global : annule tous les ordres open du compte.

        En mode ``dry_run=True``, retourne les résultats sans appeler ``cancel_order``.
        Chaque erreur ``BrokerApiError`` est capturée par ordre, n'interrompt pas la
        boucle, et laisse une ligne avec ``canceled=False, error=...``.
        """
        try:
            open_orders = self._client.list_orders(status="open", limit=500)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("cancel_all_open_orders: list_orders failed: %s", exc)
            raise

        results: list[CancelResult] = []
        for order in open_orders or []:
            broker_id = str(order.get("id") or "")
            symbol = str(order.get("symbol") or "")
            if not broker_id:
                results.append(CancelResult("", symbol, canceled=False, error="missing broker_order_id"))
                continue
            if dry_run:
                results.append(CancelResult(broker_id, symbol, canceled=True, error="dry_run"))
                continue
            try:
                ok = self._client.cancel_order(broker_id)
                results.append(CancelResult(broker_id, symbol, canceled=bool(ok)))
            except BrokerApiError as exc:
                LOGGER.warning(
                    "cancel_all_open_orders: cancel failed broker_order_id=%s symbol=%s err=%s",
                    broker_id, symbol, exc,
                )
                results.append(CancelResult(broker_id, symbol, canceled=False, error=str(exc)))
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning(
                    "cancel_all_open_orders: unexpected error broker_order_id=%s symbol=%s err=%s",
                    broker_id, symbol, exc,
                )
                results.append(CancelResult(broker_id, symbol, canceled=False, error=str(exc)))
        return results

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

