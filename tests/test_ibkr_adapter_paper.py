"""Sprint S13.2 — Adapter IBKR : tests offline (mock ``ib_insync``).

Les tests ``paper`` réels (skipif TWS absent) seront branchés en
``S13-bis`` ; ici on valide la traduction des objets ``ib_insync`` vers
les dataclasses ``core.broker_models``.
"""
from __future__ import annotations

import sys
import types
from decimal import Decimal
from unittest.mock import MagicMock

import pytest


def _install_fake_ib_insync(monkeypatch):
    fake = types.ModuleType("ib_insync")

    class IB:  # noqa: D401
        def __init__(self):
            self.connected = False
            self._summary = [
                types.SimpleNamespace(tag="NetLiquidation", value="100000"),
                types.SimpleNamespace(tag="TotalCashValue", value="50000"),
                types.SimpleNamespace(tag="BuyingPower", value="200000"),
                types.SimpleNamespace(tag="AccountCode", value="DU123"),
                types.SimpleNamespace(tag="Currency", value="USD"),
            ]

        def connect(self, host, port, clientId, readonly):  # noqa: ARG002, N803
            self.connected = True

        def disconnect(self):
            self.connected = False

        def accountSummary(self):  # noqa: N802
            return self._summary

        def positions(self):
            contract = types.SimpleNamespace(symbol="AAPL")
            return [types.SimpleNamespace(
                contract=contract, position=10, avgCost=150.0, account="DU123",
            )]

        def openTrades(self):  # noqa: N802
            o = types.SimpleNamespace(
                orderId=1, totalQuantity=10, action="BUY", orderType="MKT", orderRef="cli-1",
            )
            os_ = types.SimpleNamespace(filled=0, avgFillPrice=0.0, status="Submitted")
            contract = types.SimpleNamespace(symbol="AAPL")
            return [types.SimpleNamespace(order=o, orderStatus=os_, contract=contract)]

        def trades(self):
            return self.openTrades()

    fake.IB = IB
    monkeypatch.setitem(sys.modules, "ib_insync", fake)


def test_ibkr_get_account(monkeypatch):
    _install_fake_ib_insync(monkeypatch)
    from service.ibkr import IBKRBrokerClient

    client = IBKRBrokerClient(host="127.0.0.1", port=7497, client_id=1)
    snap = client.get_account()
    assert snap.account_id == "DU123"
    assert snap.equity == Decimal("100000")
    assert snap.buying_power == Decimal("200000")


def test_ibkr_get_positions_and_orders(monkeypatch):
    _install_fake_ib_insync(monkeypatch)
    from service.ibkr import IBKRBrokerClient

    client = IBKRBrokerClient()
    pos = client.get_positions()
    assert pos and pos[0].symbol == "AAPL" and pos[0].qty == Decimal("10")

    orders = client.get_orders()
    assert orders and orders[0].status == "accepted"
    assert orders[0].client_order_id == "cli-1"


def test_ibkr_readonly_blocks_writes(monkeypatch):
    _install_fake_ib_insync(monkeypatch)
    from core.broker_models import OrderRequest
    from service.ibkr import IBKRBrokerClient, IBKRUnavailableError

    client = IBKRBrokerClient(readonly=True)
    with pytest.raises(IBKRUnavailableError):
        client.submit_order(OrderRequest(symbol="X", qty=Decimal("1"), side="buy"))


def test_ibkr_unavailable_when_package_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "ib_insync", None)
    # forcer ImportError
    import importlib

    if "service.ibkr.client" in sys.modules:
        del sys.modules["service.ibkr.client"]
    if "service.ibkr" in sys.modules:
        del sys.modules["service.ibkr"]

    # Patch builtins import to raise ImportError when ib_insync is imported
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "ib_insync":
            raise ImportError("simulated")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _fake_import)
    from service.ibkr.client import IBKRBrokerClient, IBKRUnavailableError

    with pytest.raises(IBKRUnavailableError):
        IBKRBrokerClient()

