"""Tests for service.alpaca.trading_client."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests
from service.alpaca.trading_client import AlpacaTradingClient, BrokerApiError, LIVE_BASE, PAPER_BASE


@pytest.fixture()
def mock_creds():
    with patch("service.alpaca.trading_client.get_alpaca_credentials", return_value=("key", "secret")):
        yield


class TestAlpacaTradingClient:
    def test_paper_base_url(self, mock_creds) -> None:
        c = AlpacaTradingClient(broker_mode="paper")
        assert c.base_url == PAPER_BASE

    def test_live_base_url(self, mock_creds) -> None:
        c = AlpacaTradingClient(broker_mode="live")
        assert c.base_url == LIVE_BASE

    def test_submit_order_success(self, mock_creds) -> None:
        session = MagicMock(spec=requests.Session)
        session.headers = {}
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"id": "order123", "status": "accepted"}
        session.request.return_value = resp
        c = AlpacaTradingClient(broker_mode="paper", session=session)
        result = c.submit_order({"symbol": "AAPL", "qty": "100", "side": "buy", "type": "market", "time_in_force": "day"})
        assert result["id"] == "order123"

    def test_submit_order_rejection(self, mock_creds) -> None:
        session = MagicMock(spec=requests.Session)
        session.headers = {}
        resp = MagicMock()
        resp.status_code = 403
        resp.reason = "Forbidden"
        resp.text = "insufficient funds"
        session.request.return_value = resp
        c = AlpacaTradingClient(broker_mode="paper", session=session)
        with pytest.raises(BrokerApiError):
            c.submit_order({"symbol": "AAPL"})

    def test_cancel_order(self, mock_creds) -> None:
        session = MagicMock(spec=requests.Session)
        session.headers = {}
        resp = MagicMock()
        resp.status_code = 204
        resp.json.return_value = {}
        session.request.return_value = resp
        c = AlpacaTradingClient(broker_mode="paper", session=session)
        assert c.cancel_order("order123") is True

    def test_get_clock(self, mock_creds) -> None:
        session = MagicMock(spec=requests.Session)
        session.headers = {}
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"is_open": True}
        session.request.return_value = resp
        c = AlpacaTradingClient(broker_mode="paper", session=session)
        assert c.is_market_open() is True

    def test_credentials_reused(self) -> None:
        with patch("service.alpaca.trading_client.get_alpaca_credentials", return_value=("k", "s")) as mock_cred:
            AlpacaTradingClient(broker_mode="paper")
            mock_cred.assert_called_once()
