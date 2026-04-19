"""Client HTTP Alpaca Trading v2 — séparé du client market-data."""
from __future__ import annotations

import logging
import time

import requests

from service.alpaca.clientAlpaca import get_alpaca_credentials

LOGGER = logging.getLogger(__name__)

PAPER_BASE = "https://paper-api.alpaca.markets"
LIVE_BASE = "https://api.alpaca.markets"

_DEFAULT_TIMEOUT = 10
_MAX_RETRIES = 5
_BACKOFF_BASE = 1.0


class BrokerApiError(Exception):
    """Erreur retournée par le broker."""

    def __init__(self, status_code: int, message: str, body: str = "") -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"[{status_code}] {message}")


class AlpacaTradingClient:
    """Client HTTP pour l'API Alpaca Trading v2."""

    def __init__(
        self,
        broker_mode: str = "paper",
        session: requests.Session | None = None,
        account_id: str | None = None,
    ) -> None:
        if broker_mode not in ("paper", "live"):
            raise ValueError(f"broker_mode invalide: {broker_mode}")
        self.broker_mode = broker_mode
        self.account_id = account_id
        self.base_url = PAPER_BASE if broker_mode == "paper" else LIVE_BASE
        self._session = session or requests.Session()
        api_key, secret_key = get_alpaca_credentials(account_id)
        self._session.headers.update({
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": secret_key,
        })

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: object) -> dict | list:  # type: ignore[type-arg]
        """HTTP request avec retry borné (timeout, 429, 5xx)."""
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", _DEFAULT_TIMEOUT)  # type: ignore[arg-type]
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = self._session.request(method, url, **kwargs)  # type: ignore[arg-type]
                if resp.status_code == 429 or resp.status_code >= 500:
                    delay = _BACKOFF_BASE * (2 ** attempt)
                    LOGGER.warning("Broker %s %s → %s, retry in %.1fs", method, path, resp.status_code, delay)
                    time.sleep(delay)
                    continue
                if resp.status_code >= 400:
                    raise BrokerApiError(resp.status_code, resp.reason, resp.text)
                if resp.status_code == 204:
                    return {}
                return resp.json()  # type: ignore[no-any-return]
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                last_exc = exc
                delay = _BACKOFF_BASE * (2 ** attempt)
                LOGGER.warning("Broker %s %s → %s, retry in %.1fs", method, path, type(exc).__name__, delay)
                time.sleep(delay)
        raise last_exc or BrokerApiError(0, "Max retries exceeded")

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def submit_order(self, payload: dict[str, str]) -> dict:  # type: ignore[type-arg]
        return self._request("POST", "/v2/orders", json=payload)  # type: ignore[return-value]

    def get_order(self, order_id: str) -> dict:  # type: ignore[type-arg]
        return self._request("GET", f"/v2/orders/{order_id}")  # type: ignore[return-value]

    def list_orders(
        self,
        status: str = "all",
        limit: int = 500,
        symbols: list[str] | None = None,
    ) -> list[dict]:  # type: ignore[type-arg]
        params: dict[str, str] = {"status": status, "limit": str(limit)}
        if symbols:
            params["symbols"] = ",".join(symbols)
        return self._request("GET", "/v2/orders", params=params)  # type: ignore[return-value]

    def cancel_order(self, order_id: str) -> bool:
        try:
            self._request("DELETE", f"/v2/orders/{order_id}")
            return True
        except BrokerApiError as exc:
            if exc.status_code == 404:
                return False
            raise

    def replace_order(self, order_id: str, payload: dict[str, str]) -> dict:  # type: ignore[type-arg]
        return self._request("PATCH", f"/v2/orders/{order_id}", json=payload)  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    def get_positions(self) -> list[dict]:  # type: ignore[type-arg]
        return self._request("GET", "/v2/positions")  # type: ignore[return-value]

    def get_position(self, symbol: str) -> dict | None:  # type: ignore[type-arg]
        try:
            return self._request("GET", f"/v2/positions/{symbol}")  # type: ignore[return-value]
        except BrokerApiError as exc:
            if exc.status_code == 404:
                return None
            raise

    def close_position(self, symbol: str) -> dict:  # type: ignore[type-arg]
        return self._request("DELETE", f"/v2/positions/{symbol}")  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Account & Clock
    # ------------------------------------------------------------------

    def get_account(self) -> dict:  # type: ignore[type-arg]
        return self._request("GET", "/v2/account")  # type: ignore[return-value]

    def get_clock(self) -> dict:  # type: ignore[type-arg]
        return self._request("GET", "/v2/clock")  # type: ignore[return-value]

    def is_market_open(self) -> bool:
        clock = self.get_clock()
        return bool(clock.get("is_open", False))

